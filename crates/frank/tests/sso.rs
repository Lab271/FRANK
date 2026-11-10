//! Sign in with OpenID Connect (#236, #241, ADR-020) end to end, against a
//! stand-in identity provider that signs real RS256 ID tokens with a
//! test-only key (`tests/data/sso-test-key.pk8`, never used anywhere else).

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use axum::body::Body;
use axum::http::{header, Request, StatusCode};
use base64::engine::general_purpose::URL_SAFE_NO_PAD as B64;
use base64::Engine as _;
use frank::api::{router, App};
use frank::audit::Audit;
use frank::auth::hash;
use frank::sso::{Config, Http, Secret, Sso};
use frank::store::participants::{self as parts, FILE};
use frank::store::{Iocs, Participants, Registry, Sightings};
use frank_core::Tier;
use http_body_util::BodyExt;
use ring::rsa::PublicKeyComponents;
use ring::signature::{RsaKeyPair, RSA_PKCS1_SHA256};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use tower::ServiceExt;

const ISSUER: &str = "https://idp.example/oauth2/default";
const CLIENT: &str = "frank-client";
const SECRET: &str = "client-secret-value";
const ORIGIN: &str = "https://frank.example";
/// 2026-10-22 12:00 UTC.
const NOW: i64 = 1_792_670_400_000_000_000;
const NOW_S: i64 = NOW / 1_000_000_000;

fn now() -> i64 {
    NOW
}

/// The identity provider: discovery, a JWKS, and a token endpoint that
/// checks the client's secret and the PKCE verifier.
struct Idp {
    key: RsaKeyPair,
    /// Changes to the next ID token's claims and header.
    claims: Mutex<Value>,
    header: Mutex<Value>,
    /// Sign, then change the claims: the signature no longer fits.
    tamper: Mutex<bool>,
    /// From the last authorize URL.
    challenge: Mutex<String>,
    nonce: Mutex<String>,
}

impl Idp {
    fn new() -> Arc<Idp> {
        let der = include_bytes!("data/sso-test-key.pk8");
        Arc::new(Idp {
            key: RsaKeyPair::from_pkcs8(der).unwrap(),
            claims: Mutex::new(json!({})),
            header: Mutex::new(json!({})),
            tamper: Mutex::new(false),
            challenge: Mutex::new(String::new()),
            nonce: Mutex::new(String::new()),
        })
    }

    fn id_token(&self) -> String {
        let mut header = json!({ "alg": "RS256", "kid": "k1", "typ": "JWT" });
        merge(&mut header, &self.header.lock().unwrap());
        let mut claims = json!({
            "iss": ISSUER,
            "aud": CLIENT,
            "sub": "00u-alice",
            "email": "Alice@Lab271.dev",
            "email_verified": true,
            "iat": NOW_S,
            "exp": NOW_S + 300,
            "nonce": *self.nonce.lock().unwrap(),
        });
        merge(&mut claims, &self.claims.lock().unwrap());
        let h = B64.encode(header.to_string());
        let p = B64.encode(claims.to_string());
        let mut sig = vec![0; self.key.public().modulus_len()];
        self.key
            .sign(
                &RSA_PKCS1_SHA256,
                &ring::rand::SystemRandom::new(),
                format!("{h}.{p}").as_bytes(),
                &mut sig,
            )
            .unwrap();
        let p = if *self.tamper.lock().unwrap() {
            claims["email"] = json!("mallory@lab271.dev");
            B64.encode(claims.to_string())
        } else {
            p
        };
        format!("{h}.{p}.{}", B64.encode(sig))
    }
}

/// Sets `changes`' fields on `v`; `null` removes one.
fn merge(v: &mut Value, changes: &Value) {
    for (k, c) in changes.as_object().into_iter().flatten() {
        if c.is_null() {
            v.as_object_mut().unwrap().remove(k);
        } else {
            v[k] = c.clone();
        }
    }
}

impl Http for Idp {
    fn get(&self, url: &str) -> Result<String, String> {
        if url == format!("{ISSUER}/.well-known/openid-configuration") {
            return Ok(json!({
                "issuer": ISSUER,
                "authorization_endpoint": format!("{ISSUER}/v1/authorize"),
                "token_endpoint": format!("{ISSUER}/v1/token"),
                "jwks_uri": format!("{ISSUER}/v1/keys"),
            })
            .to_string());
        }
        if url == format!("{ISSUER}/v1/keys") {
            let k = PublicKeyComponents::<Vec<u8>>::from(self.key.public());
            return Ok(json!({ "keys": [{
                "kty": "RSA", "kid": "k1", "use": "sig", "alg": "RS256",
                "n": B64.encode(&k.n), "e": B64.encode(&k.e),
            }]})
            .to_string());
        }
        Err(format!("GET {url}: 404"))
    }

    fn post_form(
        &self,
        url: &str,
        (user, secret): (&str, &Secret),
        form: &[(&str, &str)],
    ) -> Result<String, String> {
        assert_eq!(url, format!("{ISSUER}/v1/token"));
        if user != CLIENT || secret.expose() != SECRET {
            return Err("POST token: 401".into());
        }
        let form: HashMap<&str, &str> = form.iter().copied().collect();
        assert_eq!(form["grant_type"], "authorization_code");
        assert_eq!(form["redirect_uri"], format!("{ORIGIN}/v1/sso/callback"));
        let challenge = B64.encode(Sha256::digest(form["code_verifier"].as_bytes()));
        if challenge != *self.challenge.lock().unwrap() {
            return Err("POST token: 400 invalid_grant (PKCE)".into());
        }
        Ok(
            json!({ "token_type": "Bearer", "access_token": "at", "id_token": self.id_token() })
                .to_string(),
        )
    }
}

struct Harness {
    app: axum::Router,
    idp: Arc<Idp>,
    db: std::path::PathBuf,
    dir: std::path::PathBuf,
}

impl Drop for Harness {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

/// An organisation `lab` (partner) with a machine user `feed` and its
/// token `t-feed`; SSO on unless `off`.
fn harness(name: &str, off: bool) -> Harness {
    let dir = std::env::temp_dir().join(format!("frank-sso-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let db = dir.join(FILE);
    parts::add_organisation(&db, "lab", Tier::Partner, "cyber_partner", None, None).unwrap();
    parts::add_user(&db, "lab", "feed", "machine", None).unwrap();
    parts::add_token_hash(&db, "feed", &hash("t-feed")).unwrap();
    let idp = Idp::new();
    let sso = (!off).then(|| {
        Sso::new(
            Config {
                issuer: ISSUER.into(),
                client_id: CLIENT.into(),
                client_secret: Secret::new(SECRET),
                redirect_url: format!("{ORIGIN}/v1/sso/callback"),
                organisation: "lab".into(),
                origin: ORIGIN.into(),
            },
            idp.clone(),
        )
    });
    let sightings = Sightings::open(&dir, None, now).unwrap();
    let app = router(Arc::new(App {
        data: dir.clone(),
        iocs: Iocs::open(&dir).unwrap(),
        registry: Registry::open(&dir, &sightings).unwrap(),
        sightings,
        geo: frank::geo::Geo::open(&dir, now()).unwrap(),
        lists: frank::lists::Lists::open(&dir).unwrap(),
        participants: Participants::open(&dir).unwrap(),
        audit: Audit::open(&dir).unwrap(),
        sso,
        submit_lock: std::sync::Mutex::new(()),
        now,
    }));
    Harness { app, idp, db, dir }
}

struct Reply {
    status: StatusCode,
    location: String,
    cookies: Vec<String>,
    body: Value,
}

impl Reply {
    /// The value a `Set-Cookie` gives `name`, if any.
    fn cookie(&self, name: &str) -> Option<String> {
        self.cookies.iter().find_map(|c| {
            let (k, rest) = c.split_once('=')?;
            (k == name).then(|| rest.split(';').next().unwrap_or("").to_string())
        })
    }

    fn set_cookie(&self, name: &str) -> &str {
        self.cookies
            .iter()
            .find(|c| c.starts_with(&format!("{name}=")))
            .map_or("", String::as_str)
    }
}

async fn send(app: &axum::Router, req: Request<Body>) -> Reply {
    let resp = app.clone().oneshot(req).await.unwrap();
    let status = resp.status();
    let location = resp
        .headers()
        .get(header::LOCATION)
        .map(|v| v.to_str().unwrap().to_string())
        .unwrap_or_default();
    let cookies = resp
        .headers()
        .get_all(header::SET_COOKIE)
        .iter()
        .map(|v| v.to_str().unwrap().to_string())
        .collect();
    let bytes = resp.into_body().collect().await.unwrap().to_bytes();
    Reply {
        status,
        location,
        cookies,
        body: serde_json::from_slice(&bytes).unwrap_or(Value::Null),
    }
}

fn get(uri: &str) -> axum::http::request::Builder {
    Request::builder().method("GET").uri(uri)
}

/// The query parameters of a URL.
fn params(url: &str) -> HashMap<String, String> {
    url.split_once('?')
        .map(|(_, q)| q)
        .unwrap_or("")
        .split('&')
        .filter_map(|kv| kv.split_once('='))
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect()
}

/// Starts a login; the identity provider learns its nonce and challenge.
/// Returns the state and the state cookie's value.
async fn login(h: &Harness) -> (String, String) {
    let r = send(&h.app, get("/v1/sso/login").body(Body::empty()).unwrap()).await;
    assert_eq!(r.status, StatusCode::SEE_OTHER);
    let p = params(&r.location);
    *h.idp.nonce.lock().unwrap() = p["nonce"].clone();
    *h.idp.challenge.lock().unwrap() = p["code_challenge"].clone();
    (p["state"].clone(), r.cookie("frank_sso_state").unwrap())
}

async fn callback(h: &Harness, query: &str, state_cookie: &str) -> Reply {
    let req = get(&format!("/v1/sso/callback?{query}"))
        .header(header::COOKIE, format!("frank_sso_state={state_cookie}"))
        .body(Body::empty())
        .unwrap();
    send(&h.app, req).await
}

/// A full sign-in; returns the session cookie's value.
async fn sign_in(h: &Harness) -> String {
    let (state, cookie) = login(h).await;
    let r = callback(h, &format!("code=c1&state={state}"), &cookie).await;
    assert_eq!(r.location, "/", "{:?}", r.cookies);
    r.cookie("frank_session").unwrap()
}

async fn whoami(h: &Harness, session: Option<&str>, token: Option<&str>) -> Reply {
    let mut req = get("/v1/whoami");
    if let Some(s) = session {
        req = req.header(header::COOKIE, format!("frank_session={s}"));
    }
    if let Some(t) = token {
        req = req.header(header::AUTHORIZATION, format!("Bearer {t}"));
    }
    send(&h.app, req.body(Body::empty()).unwrap()).await
}

fn audit_actions(h: &Harness) -> Vec<String> {
    Audit::open(&h.dir)
        .unwrap()
        .read_from(0)
        .unwrap()
        .iter()
        .map(|l| l["action"].as_str().unwrap_or_default().to_string())
        .collect()
}

#[tokio::test]
async fn without_settings_sso_is_off_and_cookies_mean_nothing() {
    let h = harness("off", true);
    let r = send(&h.app, get("/v1/sso").body(Body::empty()).unwrap()).await;
    assert_eq!(r.body, json!({ "enabled": false }));
    for uri in ["/v1/sso/login", "/v1/sso/callback?code=c&state=s"] {
        let r = send(&h.app, get(uri).body(Body::empty()).unwrap()).await;
        assert_eq!(r.status, StatusCode::NOT_FOUND, "{uri}");
    }
    assert_eq!(whoami(&h, Some("abc"), None).await.body["tier"], "public");
    assert_eq!(whoami(&h, None, Some("t-feed")).await.body["user"], "feed");
}

#[tokio::test]
async fn login_sends_the_browser_with_pkce_state_and_nonce() {
    let h = harness("login", false);
    let r = send(&h.app, get("/v1/sso").body(Body::empty()).unwrap()).await;
    assert_eq!(r.body, json!({ "enabled": true }));
    let r = send(&h.app, get("/v1/sso/login").body(Body::empty()).unwrap()).await;
    assert_eq!(r.status, StatusCode::SEE_OTHER);
    assert!(r.location.starts_with(&format!("{ISSUER}/v1/authorize?")));
    let p = params(&r.location);
    assert_eq!(p["response_type"], "code");
    assert_eq!(p["client_id"], CLIENT);
    assert_eq!(
        p["redirect_uri"],
        "https%3A%2F%2Ffrank.example%2Fv1%2Fsso%2Fcallback"
    );
    assert_eq!(p["scope"], "openid%20email%20profile");
    assert_eq!(p["code_challenge_method"], "S256");
    assert_eq!(p["code_challenge"].len(), 43);
    assert_eq!(p["state"].len(), 32);
    assert_eq!(p["nonce"].len(), 32);
    let c = r.set_cookie("frank_sso_state");
    assert!(
        c.starts_with(&format!("frank_sso_state={};", p["state"])),
        "{c}"
    );
    for attr in [
        "HttpOnly",
        "SameSite=Lax",
        "Secure",
        "Path=/v1/sso",
        "Max-Age=600",
    ] {
        assert!(c.contains(attr), "{c}: {attr}");
    }
}

#[tokio::test]
async fn a_first_sign_in_provisions_the_user_and_starts_a_session() {
    let h = harness("round-trip", false);
    let (state, cookie) = login(&h).await;
    let r = callback(&h, &format!("code=c1&state={state}"), &cookie).await;
    assert_eq!(
        (r.status, r.location.as_str()),
        (StatusCode::SEE_OTHER, "/")
    );
    let session = r.cookie("frank_session").unwrap();
    assert_eq!(session.len(), 64);
    let c = r.set_cookie("frank_session");
    for attr in [
        "HttpOnly",
        "SameSite=Lax",
        "Secure",
        "Path=/",
        "Max-Age=28800",
    ] {
        assert!(c.contains(attr), "{c}: {attr}");
    }
    assert!(r.set_cookie("frank_sso_state").contains("Max-Age=0"));
    let me = whoami(&h, Some(&session), None).await.body;
    assert_eq!(me["user"], "alice@lab271.dev");
    assert_eq!(
        (me["tier"].as_str(), me["role"].is_null()),
        (Some("partner"), true)
    );
    let users = parts::users(&h.db).unwrap();
    let alice = users.iter().find(|u| u.name == "alice@lab271.dev").unwrap();
    assert_eq!((alice.kind.as_str(), alice.role), ("human", None));
    // The state is used up: replaying the callback is refused.
    let again = callback(&h, &format!("code=c1&state={state}"), &cookie).await;
    assert_eq!(again.location, "/?sso=refused");
    // A second sign-in finds the same user.
    sign_in(&h).await;
    assert_eq!(parts::users(&h.db).unwrap().len(), users.len());
    let actions = audit_actions(&h);
    for a in ["user_provisioned", "sso_login", "sso_refused"] {
        assert!(actions.iter().any(|x| x == a), "{a} in {actions:?}");
    }
    assert_eq!(
        actions.iter().filter(|a| *a == "user_provisioned").count(),
        1
    );
}

#[tokio::test]
async fn the_callback_refuses_every_bad_token() {
    let h = harness("refusals", false);
    let cases: [(&str, Value, Value, bool); 8] = [
        (
            "issuer",
            json!({ "iss": "https://evil.example" }),
            json!({}),
            false,
        ),
        (
            "audience",
            json!({ "aud": "someone-else" }),
            json!({}),
            false,
        ),
        (
            "azp",
            json!({ "aud": [CLIENT, "x"], "azp": "x" }),
            json!({}),
            false,
        ),
        ("expired", json!({ "exp": NOW_S - 1 }), json!({}), false),
        ("nonce", json!({ "nonce": "0123" }), json!({}), false),
        ("no sub", json!({ "sub": null }), json!({}), false),
        ("algorithm", json!({}), json!({ "alg": "HS256" }), false),
        ("signature", json!({}), json!({}), true),
    ];
    for (what, claims, head, tamper) in cases {
        *h.idp.claims.lock().unwrap() = claims;
        *h.idp.header.lock().unwrap() = head;
        *h.idp.tamper.lock().unwrap() = tamper;
        let (state, cookie) = login(&h).await;
        let r = callback(&h, &format!("code=c1&state={state}"), &cookie).await;
        assert_eq!(r.location, "/?sso=refused", "{what}");
        assert_eq!(r.cookie("frank_session"), None, "{what}");
    }
    *h.idp.claims.lock().unwrap() = json!({});
    *h.idp.header.lock().unwrap() = json!({});
    *h.idp.tamper.lock().unwrap() = false;
    assert!(parts::users(&h.db)
        .unwrap()
        .iter()
        .all(|u| u.name == "feed"));
    // The flow works again with a good token.
    sign_in(&h).await;
}

#[tokio::test]
async fn the_callback_refuses_a_foreign_state_and_a_wrong_verifier() {
    let h = harness("state", false);
    let (state, _) = login(&h).await;
    let r = callback(&h, &format!("code=c1&state={state}"), "another-browser").await;
    assert_eq!(r.location, "/?sso=refused", "state cookie");
    let (state, cookie) = login(&h).await;
    let r = callback(&h, &format!("state={state}"), &cookie).await;
    assert_eq!(r.location, "/?sso=refused", "no code");
    let r = callback(&h, "error=access_denied&state=x", &cookie).await;
    assert_eq!(r.location, "/?sso=refused", "provider error");
    let (state, cookie) = login(&h).await;
    *h.idp.challenge.lock().unwrap() = "not-the-challenge".into();
    let r = callback(&h, &format!("code=c1&state={state}"), &cookie).await;
    assert_eq!(r.location, "/?sso=refused", "PKCE");
    let reasons: Vec<Value> = Audit::open(&h.dir)
        .unwrap()
        .read_from(0)
        .unwrap()
        .into_iter()
        .filter(|l| l["action"] == "sso_refused")
        .collect();
    assert_eq!(reasons.len(), 4);
    let all = serde_json::to_string(&reasons).unwrap();
    assert!(
        !all.contains(SECRET),
        "the client secret is in an audit line"
    );
}

#[tokio::test]
async fn the_authorization_header_comes_before_the_session() {
    let h = harness("bearer-first", false);
    let session = sign_in(&h).await;
    let r = whoami(&h, Some(&session), Some("bogus")).await;
    assert_eq!(r.status, StatusCode::UNAUTHORIZED);
    let r = whoami(&h, Some(&session), Some("t-feed")).await;
    assert_eq!(r.body["user"], "feed");
    assert_eq!(whoami(&h, Some("nope"), None).await.body["tier"], "public");
    // A disabled user's session stops working.
    parts::set_disabled(&h.db, "alice@lab271.dev", true).unwrap();
    assert_eq!(
        whoami(&h, Some(&session), None).await.body["tier"],
        "public"
    );
}

#[tokio::test]
async fn writes_with_a_session_cookie_need_frank_s_origin() {
    let h = harness("csrf", false);
    let session = sign_in(&h).await;
    let logout = |origin: Option<&str>| {
        let mut req = Request::builder()
            .method("POST")
            .uri("/v1/sso/logout")
            .header(header::COOKIE, format!("frank_session={session}"));
        if let Some(o) = origin {
            req = req.header(header::ORIGIN, o);
        }
        req.body(Body::empty()).unwrap()
    };
    assert_eq!(
        send(&h.app, logout(None)).await.status,
        StatusCode::FORBIDDEN
    );
    let r = send(&h.app, logout(Some("https://evil.example"))).await;
    assert_eq!(r.status, StatusCode::FORBIDDEN);
    assert_eq!(
        whoami(&h, Some(&session), None).await.body["user"],
        "alice@lab271.dev"
    );
    let r = send(&h.app, logout(Some(ORIGIN))).await;
    assert_eq!(r.status, StatusCode::OK);
    assert!(r.set_cookie("frank_session").contains("Max-Age=0"));
    assert_eq!(
        whoami(&h, Some(&session), None).await.body["tier"],
        "public"
    );
    assert!(audit_actions(&h).iter().any(|a| a == "sso_logout"));
    // A bearer client's write needs no Origin.
    let req = Request::builder()
        .method("POST")
        .uri("/v1/preview")
        .header(header::AUTHORIZATION, "Bearer t-feed")
        .header(header::CONTENT_TYPE, "application/json")
        .body(Body::from("{}"))
        .unwrap();
    assert_ne!(send(&h.app, req).await.status, StatusCode::FORBIDDEN);
}
