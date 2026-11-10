//! Sign in with OpenID Connect (#241, ADR-020).
//!
//! The authorization code flow with PKCE (S256): `GET /v1/sso/login`
//! sends the browser to the identity provider, `GET /v1/sso/callback`
//! takes it back, exchanges the code, checks the ID token and starts a
//! session, `POST /v1/sso/logout` ends it. SSO is off unless all of its
//! settings are given; then every `/v1/sso` route but `GET /v1/sso`
//! answers 404.
//!
//! The one secret, the client secret, is read from a file and is never
//! printed: [`Secret`]'s `Debug` and `Display` hide it.
//!
//! | Route                      | Tier |
//! |----------------------------|------|
//! | `GET  /v1/sso`             | none: whether SSO is on |
//! | `GET  /v1/sso/login`       | none |
//! | `GET  /v1/sso/callback`    | none |
//! | `POST /v1/sso/logout`      | the session's user |

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use axum::extract::{Query, Request, State};
use axum::http::{header, HeaderMap, HeaderValue, Method, StatusCode};
use axum::middleware::Next;
use axum::response::{AppendHeaders, IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use base64::engine::general_purpose::{STANDARD, URL_SAFE_NO_PAD as B64};
use base64::Engine as _;
use serde::Deserialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::api::Shared;
use crate::auth::{hex, random};
use crate::store::participants::{self as parts, Identity, SignedIn};

/// The session cookie (ADR-020, decision 6).
pub const SESSION_COOKIE: &str = "frank_session";
/// The login's `state`, bound to the browser that started it.
pub const STATE_COOKIE: &str = "frank_sso_state";
/// How long a login may take, from `/login` to `/callback`.
const LOGIN_NS: i64 = 600 * 1_000_000_000;
/// Logins in progress at most: `/login` needs no token.
const MAX_PENDING: usize = 10_000;
/// The JWKS is fetched again for an unknown key at most this often.
const JWKS_REFETCH_NS: i64 = 60 * 1_000_000_000;

/// The settings as `frank serve` receives them, each optional.
#[derive(Debug, Default, Clone)]
pub struct Settings {
    pub issuer: Option<String>,
    pub client_id: Option<String>,
    pub client_secret_file: Option<PathBuf>,
    pub redirect_url: Option<String>,
    pub organisation: Option<String>,
}

/// A value that is never printed.
#[derive(Clone, PartialEq, Eq)]
pub struct Secret(String);

impl Secret {
    #[must_use]
    pub fn new(value: impl Into<String>) -> Secret {
        Secret(value.into())
    }

    #[must_use]
    pub fn expose(&self) -> &str {
        &self.0
    }
}

impl std::fmt::Debug for Secret {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("Secret([redacted])")
    }
}

impl std::fmt::Display for Secret {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("[redacted]")
    }
}

/// Complete SSO settings.
#[derive(Debug, Clone)]
pub struct Config {
    /// The issuer, without a trailing `/`: `iss` must equal it.
    pub issuer: String,
    pub client_id: String,
    pub client_secret: Secret,
    /// Where the identity provider sends the browser back to:
    /// `…/v1/sso/callback` on FRANK's public address.
    pub redirect_url: String,
    /// The organisation (name or id) new users are created in.
    pub organisation: String,
    /// `scheme://host[:port]` of the redirect URL: the origin a
    /// cookie-authenticated write must come from.
    pub origin: String,
}

impl Config {
    /// `None` when no setting is given; an error naming what is missing
    /// when only some are, or when one is invalid. Never names the secret's
    /// value.
    pub fn from_settings(s: Settings) -> Result<Option<Config>, String> {
        let given = [
            ("FRANK_SSO_ISSUER", s.issuer.is_some()),
            ("FRANK_SSO_CLIENT_ID", s.client_id.is_some()),
            (
                "FRANK_SSO_CLIENT_SECRET_FILE",
                s.client_secret_file.is_some(),
            ),
            ("FRANK_SSO_REDIRECT_URL", s.redirect_url.is_some()),
            ("FRANK_SSO_ORGANISATION", s.organisation.is_some()),
        ];
        if given.iter().all(|(_, g)| !g) {
            return Ok(None);
        }
        let missing: Vec<&str> = given.iter().filter(|(_, g)| !g).map(|(n, _)| *n).collect();
        if !missing.is_empty() {
            return Err(format!(
                "SSO is partly configured: set {} too, or none of the FRANK_SSO_ settings",
                missing.join(", ")
            ));
        }
        let (
            Some(issuer),
            Some(client_id),
            Some(secret_file),
            Some(redirect_url),
            Some(organisation),
        ) = (
            s.issuer,
            s.client_id,
            s.client_secret_file,
            s.redirect_url,
            s.organisation,
        )
        else {
            unreachable!("checked above");
        };
        let issuer = issuer.trim().trim_end_matches('/').to_string();
        Url::parse(&issuer)
            .and_then(Url::secure)
            .map_err(|e| format!("FRANK_SSO_ISSUER: {e}"))?;
        let redirect = Url::parse(redirect_url.trim())
            .and_then(Url::secure)
            .map_err(|e| format!("FRANK_SSO_REDIRECT_URL: {e}"))?;
        let client_id = client_id.trim().to_string();
        if client_id.is_empty() {
            return Err("FRANK_SSO_CLIENT_ID is empty".into());
        }
        let organisation = organisation.trim().to_string();
        if organisation.is_empty() {
            return Err("FRANK_SSO_ORGANISATION is empty".into());
        }
        let secret = std::fs::read_to_string(&secret_file).map_err(|e| {
            format!(
                "FRANK_SSO_CLIENT_SECRET_FILE {}: {}",
                secret_file.display(),
                e.kind()
            )
        })?;
        let secret = secret.trim();
        if secret.is_empty() {
            return Err(format!(
                "FRANK_SSO_CLIENT_SECRET_FILE {} is empty",
                secret_file.display()
            ));
        }
        Ok(Some(Config {
            issuer,
            client_id,
            client_secret: Secret::new(secret),
            origin: redirect.origin(),
            redirect_url: redirect_url.trim().to_string(),
            organisation,
        }))
    }
}

/// The parts of an absolute `http(s)` URL that SSO needs.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Url {
    pub scheme: String,
    /// Lower case.
    pub host: String,
    pub port: Option<u16>,
    /// From the first `/`, query included; `/` when empty.
    pub path: String,
}

impl Url {
    pub fn parse(s: &str) -> Result<Url, String> {
        let (scheme, rest) = s
            .split_once("://")
            .ok_or_else(|| format!("{s:?} is not an absolute URL"))?;
        let scheme = scheme.to_ascii_lowercase();
        if scheme != "https" && scheme != "http" {
            return Err(format!("{s:?}: only http and https"));
        }
        let (authority, path) = match rest.find(['/', '?', '#']) {
            Some(i) => (&rest[..i], &rest[i..]),
            None => (rest, ""),
        };
        if authority.contains('@') {
            return Err(format!("{s:?}: no user info in the URL"));
        }
        let (host, port) = match authority.rsplit_once(':') {
            Some((h, p)) => (
                h,
                Some(
                    p.parse::<u16>()
                        .map_err(|_| format!("{s:?}: bad port {p:?}"))?,
                ),
            ),
            None => (authority, None),
        };
        if host.is_empty() {
            return Err(format!("{s:?}: no host"));
        }
        if path.contains('#') {
            return Err(format!("{s:?}: no fragment"));
        }
        Ok(Url {
            scheme,
            host: host.to_ascii_lowercase(),
            port,
            path: if path.is_empty() {
                "/".into()
            } else {
                path.into()
            },
        })
    }

    /// `https`, or `http` for `localhost` and `*.local` (the local stub).
    pub fn secure(self) -> Result<Url, String> {
        if self.scheme == "https" || self.is_local() {
            Ok(self)
        } else {
            Err(format!(
                "{}: https is required (http only for localhost and *.local)",
                self.origin()
            ))
        }
    }

    #[must_use]
    pub fn is_local(&self) -> bool {
        self.host == "localhost" || self.host.ends_with(".local")
    }

    /// `scheme://host[:port]`.
    #[must_use]
    pub fn origin(&self) -> String {
        match self.port {
            Some(p) => format!("{}://{}:{p}", self.scheme, self.host),
            None => format!("{}://{}", self.scheme, self.host),
        }
    }
}

// --- the identity provider -------------------------------------------------

/// The calls to the identity provider, so tests can stand in for it.
pub trait Http: Send + Sync {
    /// The body of a `GET`; an error for a status other than 2xx.
    fn get(&self, url: &str) -> Result<String, String>;
    /// The body of a form `POST` with HTTP Basic client authentication.
    fn post_form(
        &self,
        url: &str,
        basic: (&str, &Secret),
        form: &[(&str, &str)],
    ) -> Result<String, String>;
}

/// [`Http`] over ureq and rustls, with the platform's certificates.
pub struct Ureq {
    agent: ureq::Agent,
}

impl Ureq {
    #[must_use]
    pub fn new() -> Ureq {
        use ureq::tls::{RootCerts, TlsConfig, TlsProvider};
        let tls = TlsConfig::builder()
            .provider(TlsProvider::Rustls)
            .root_certs(RootCerts::PlatformVerifier)
            .build();
        let agent = ureq::Agent::config_builder()
            .tls_config(tls)
            .timeout_global(Some(Duration::from_secs(15)))
            .build()
            .new_agent();
        Ureq { agent }
    }
}

impl Default for Ureq {
    fn default() -> Self {
        Ureq::new()
    }
}

impl Http for Ureq {
    fn get(&self, url: &str) -> Result<String, String> {
        self.agent
            .get(url)
            .header("accept", "application/json")
            .call()
            .and_then(|mut r| r.body_mut().read_to_string())
            .map_err(|e| format!("GET {url}: {e}"))
    }

    fn post_form(
        &self,
        url: &str,
        (user, password): (&str, &Secret),
        form: &[(&str, &str)],
    ) -> Result<String, String> {
        // RFC 6749 2.3.1: both parts form-encoded before base64.
        let basic = STANDARD.encode(format!("{}:{}", enc(user), enc(password.expose())));
        self.agent
            .post(url)
            .header("authorization", format!("Basic {basic}"))
            .header("accept", "application/json")
            .send_form(form.iter().copied())
            .and_then(|mut r| r.body_mut().read_to_string())
            // ureq's error names the status, never the request's headers.
            .map_err(|e| format!("POST {url}: {e}"))
    }
}

/// What discovery says about the identity provider.
#[derive(Debug, Clone, Deserialize)]
struct Provider {
    issuer: String,
    authorization_endpoint: String,
    token_endpoint: String,
    jwks_uri: String,
}

#[derive(Deserialize)]
struct Jwks {
    keys: Vec<Jwk>,
}

#[derive(Deserialize)]
struct Jwk {
    kty: String,
    kid: Option<String>,
    #[serde(rename = "use")]
    usage: Option<String>,
    n: Option<String>,
    e: Option<String>,
}

/// An RSA public key: modulus and exponent, big-endian.
type RsaKey = (Vec<u8>, Vec<u8>);

/// A login between `/login` and `/callback`.
struct Pending {
    nonce: String,
    verifier: String,
    at_ns: i64,
}

#[derive(Default)]
struct Keys {
    by_kid: HashMap<String, RsaKey>,
    fetched_ns: Option<i64>,
}

/// SSO at run time: the settings, the identity provider's cached
/// discovery document and keys, and the logins in progress.
pub struct Sso {
    pub config: Config,
    http: Arc<dyn Http>,
    provider: Mutex<Option<Provider>>,
    keys: Mutex<Keys>,
    pending: Mutex<HashMap<String, Pending>>,
}

const POISONED: &str = "sso lock poisoned";

impl Sso {
    #[must_use]
    pub fn new(config: Config, http: Arc<dyn Http>) -> Sso {
        Sso {
            config,
            http,
            provider: Mutex::new(None),
            keys: Mutex::new(Keys::default()),
            pending: Mutex::new(HashMap::new()),
        }
    }

    /// The discovery document, fetched once (ADR-020, decision 2).
    fn provider(&self) -> Result<Provider, String> {
        if let Some(p) = self.provider.lock().map_err(|_| POISONED)?.clone() {
            return Ok(p);
        }
        let url = format!("{}/.well-known/openid-configuration", self.config.issuer);
        let p: Provider =
            serde_json::from_str(&self.http.get(&url)?).map_err(|e| format!("{url}: {e}"))?;
        if p.issuer.trim_end_matches('/') != self.config.issuer {
            return Err(format!(
                "discovery names issuer {:?}, not {:?}",
                p.issuer, self.config.issuer
            ));
        }
        for (what, u) in [
            ("authorization_endpoint", &p.authorization_endpoint),
            ("token_endpoint", &p.token_endpoint),
            ("jwks_uri", &p.jwks_uri),
        ] {
            Url::parse(u)
                .and_then(Url::secure)
                .map_err(|e| format!("discovery {what}: {e}"))?;
        }
        *self.provider.lock().map_err(|_| POISONED)? = Some(p.clone());
        Ok(p)
    }

    /// The key `kid` names (or the only key, for a token without `kid`),
    /// fetching the JWKS when it is not known yet, at most once a minute.
    fn key(&self, provider: &Provider, kid: Option<&str>, now_ns: i64) -> Result<RsaKey, String> {
        let find = |k: &Keys| match kid {
            Some(kid) => k.by_kid.get(kid).cloned(),
            None if k.by_kid.len() == 1 => k.by_kid.values().next().cloned(),
            None => None,
        };
        {
            let keys = self.keys.lock().map_err(|_| POISONED)?;
            if let Some(k) = find(&keys) {
                return Ok(k);
            }
            if keys
                .fetched_ns
                .is_some_and(|at| now_ns - at < JWKS_REFETCH_NS)
            {
                return Err(format!("no signing key {kid:?}"));
            }
        }
        let jwks: Jwks = serde_json::from_str(&self.http.get(&provider.jwks_uri)?)
            .map_err(|e| format!("{}: {e}", provider.jwks_uri))?;
        let mut by_kid = HashMap::new();
        for (i, k) in jwks.keys.into_iter().enumerate() {
            if k.kty != "RSA" || k.usage.as_deref().is_some_and(|u| u != "sig") {
                continue;
            }
            let (Some(n), Some(e)) = (k.n, k.e) else {
                continue;
            };
            let (Ok(n), Ok(e)) = (B64.decode(n), B64.decode(e)) else {
                continue;
            };
            by_kid.insert(k.kid.unwrap_or_else(|| format!("#{i}")), (n, e));
        }
        let mut keys = self.keys.lock().map_err(|_| POISONED)?;
        *keys = Keys {
            by_kid,
            fetched_ns: Some(now_ns),
        };
        find(&keys).ok_or_else(|| format!("no signing key {kid:?}"))
    }

    /// Starts a login: the identity provider's URL to send the browser to,
    /// and the `state` to bind to the browser.
    pub fn begin(&self, now_ns: i64) -> Result<(String, String), String> {
        let provider = self.provider()?;
        let state = hex(&random::<16>()?);
        let nonce = hex(&random::<16>()?);
        let verifier = B64.encode(random::<32>()?);
        let challenge = B64.encode(Sha256::digest(verifier.as_bytes()));
        {
            let mut pending = self.pending.lock().map_err(|_| POISONED)?;
            pending.retain(|_, p| now_ns - p.at_ns < LOGIN_NS);
            if pending.len() >= MAX_PENDING {
                return Err("too many logins in progress".into());
            }
            pending.insert(
                state.clone(),
                Pending {
                    nonce: nonce.clone(),
                    verifier,
                    at_ns: now_ns,
                },
            );
        }
        let sep = if provider.authorization_endpoint.contains('?') {
            '&'
        } else {
            '?'
        };
        let url = format!(
            "{}{sep}response_type=code&client_id={}&redirect_uri={}&scope={}&state={state}\
             &nonce={nonce}&code_challenge={challenge}&code_challenge_method=S256",
            provider.authorization_endpoint,
            enc(&self.config.client_id),
            enc(&self.config.redirect_url),
            enc("openid email profile"),
        );
        Ok((url, state))
    }

    /// Ends a login: exchanges `code`, checks the ID token (ADR-020,
    /// decision 4) and returns who it names. An error is a refusal, with
    /// the reason for the audit line.
    pub fn finish(&self, state: &str, code: &str, now_ns: i64) -> Result<Identity, String> {
        let pending = self
            .pending
            .lock()
            .map_err(|_| POISONED)?
            .remove(state)
            .ok_or("unknown or used state")?;
        if now_ns - pending.at_ns >= LOGIN_NS {
            return Err("the login took too long".into());
        }
        let provider = self.provider()?;
        let body = self.http.post_form(
            &provider.token_endpoint,
            (&self.config.client_id, &self.config.client_secret),
            &[
                ("grant_type", "authorization_code"),
                ("code", code),
                ("redirect_uri", &self.config.redirect_url),
                ("code_verifier", &pending.verifier),
            ],
        )?;
        let tokens: Value =
            serde_json::from_str(&body).map_err(|e| format!("token response: {e}"))?;
        let id_token = tokens["id_token"]
            .as_str()
            .ok_or("the token response has no id_token")?;
        let claims = self.check(&provider, id_token, &pending.nonce, now_ns)?;
        let subject = claims["sub"].as_str().unwrap_or_default().to_string();
        if subject.is_empty() {
            return Err("the ID token has no sub".into());
        }
        Ok(Identity {
            issuer: self.config.issuer.clone(),
            subject,
            email: claims["email"].as_str().map(str::to_string),
            email_verified: claims["email_verified"].as_bool().unwrap_or(false),
        })
    }

    /// The claims of a valid ID token.
    fn check(
        &self,
        provider: &Provider,
        token: &str,
        nonce: &str,
        now_ns: i64,
    ) -> Result<Value, String> {
        let mut parts = token.split('.');
        let (Some(h), Some(p), Some(sig), None) =
            (parts.next(), parts.next(), parts.next(), parts.next())
        else {
            return Err("the ID token is not a JWS".into());
        };
        let json = |part: &str, what: &str| -> Result<Value, String> {
            let bytes = B64
                .decode(part)
                .map_err(|_| format!("the ID token's {what} is not base64url"))?;
            serde_json::from_slice(&bytes).map_err(|_| format!("the ID token's {what} is not JSON"))
        };
        let header = json(h, "header")?;
        if header["alg"] != "RS256" {
            return Err(format!("ID token algorithm {}: only RS256", header["alg"]));
        }
        let (n, e) = self.key(provider, header["kid"].as_str(), now_ns)?;
        let sig = B64
            .decode(sig)
            .map_err(|_| "the ID token's signature is not base64url")?;
        ring::signature::RsaPublicKeyComponents { n: &n, e: &e }
            .verify(
                &ring::signature::RSA_PKCS1_2048_8192_SHA256,
                format!("{h}.{p}").as_bytes(),
                &sig,
            )
            .map_err(|_| "the ID token's signature does not verify")?;
        let claims = json(p, "claims")?;
        if claims["iss"].as_str() != Some(self.config.issuer.as_str()) {
            return Err(format!("ID token issuer {}", claims["iss"]));
        }
        let client_id = self.config.client_id.as_str();
        let audience_ok = match &claims["aud"] {
            Value::String(a) => a == client_id,
            Value::Array(a) => a.iter().any(|a| a.as_str() == Some(client_id)),
            _ => false,
        };
        if !audience_ok {
            return Err(format!("ID token audience {}", claims["aud"]));
        }
        if claims
            .get("azp")
            .is_some_and(|a| a.as_str() != Some(client_id))
        {
            return Err(format!("ID token azp {}", claims["azp"]));
        }
        let exp = claims["exp"].as_i64().ok_or("the ID token has no exp")?;
        if exp <= now_ns / 1_000_000_000 {
            return Err("the ID token has expired".into());
        }
        if claims["nonce"].as_str() != Some(nonce) {
            return Err("the ID token's nonce does not match".into());
        }
        Ok(claims)
    }
}

/// Form and query encoding: unreserved characters stay, the rest is %XX.
fn enc(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        if b.is_ascii_alphanumeric() || b"-._~".contains(&b) {
            out.push(char::from(b));
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}

// --- cookies -----------------------------------------------------------------

/// The value of cookie `name`, if the request carries it.
#[must_use]
pub fn cookie(headers: &HeaderMap, name: &str) -> Option<String> {
    headers
        .get_all(header::COOKIE)
        .iter()
        .filter_map(|v| v.to_str().ok())
        .flat_map(|v| v.split(';'))
        .filter_map(|c| c.trim().split_once('='))
        .find(|(k, _)| *k == name)
        .map(|(_, v)| v.to_string())
}

/// A `Set-Cookie` value: HttpOnly, SameSite=Lax, Secure on https.
fn set_cookie(config: &Config, name: &str, value: &str, path: &str, max_age: i64) -> String {
    let secure = if config.origin.starts_with("https://") {
        "; Secure"
    } else {
        ""
    };
    format!("{name}={value}; Path={path}; HttpOnly; SameSite=Lax; Max-Age={max_age}{secure}")
}

/// The session cookie's value, when SSO is on and the request has one.
#[must_use]
pub fn session_value(app: &crate::api::App, headers: &HeaderMap) -> Option<String> {
    app.sso.as_ref()?;
    cookie(headers, SESSION_COOKIE).filter(|v| !v.is_empty())
}

/// Against cross-site request forgery (ADR-020, decision 7): a request
/// that changes state and carries a session cookie must come from FRANK's
/// own origin. Requests without the cookie (bearer clients) pass as before.
pub async fn csrf(State(app): State<Shared>, req: Request, next: Next) -> Response {
    let safe = matches!(*req.method(), Method::GET | Method::HEAD | Method::OPTIONS);
    if let (false, Some(sso), Some(_)) = (safe, &app.sso, session_value(&app, req.headers())) {
        let origin = req
            .headers()
            .get(header::ORIGIN)
            .and_then(|v| v.to_str().ok());
        if origin != Some(sso.config.origin.as_str()) {
            return (
                StatusCode::FORBIDDEN,
                Json(json!({
                    "error": "a request with a session cookie must come from FRANK's own origin"
                })),
            )
                .into_response();
        }
    }
    next.run(req).await
}

// --- routes --------------------------------------------------------------------

pub fn routes() -> Router<Shared> {
    Router::new()
        .route("/v1/sso", get(status))
        .route("/v1/sso/login", get(login))
        .route("/v1/sso/callback", get(callback))
        .route("/v1/sso/logout", post(logout))
}

fn not_configured() -> Response {
    (
        StatusCode::NOT_FOUND,
        Json(json!({ "error": "sign in with SSO is not configured" })),
    )
        .into_response()
}

const NO_STORE: (header::HeaderName, HeaderValue) =
    (header::CACHE_CONTROL, HeaderValue::from_static("no-store"));

/// Whether SSO is on, for the web UI's sign-in button.
async fn status(State(app): State<Shared>) -> Json<Value> {
    Json(json!({ "enabled": app.sso.is_some() }))
}

async fn login(State(app): State<Shared>) -> Response {
    let Some(sso) = &app.sso else {
        return not_configured();
    };
    let a = app.clone();
    let begun = tokio::task::spawn_blocking(move || match &a.sso {
        Some(sso) => sso.begin((a.now)()),
        None => Err("sign in with SSO is not configured".into()),
    })
    .await
    .unwrap_or_else(|e| Err(e.to_string()));
    match begun {
        Ok((url, state)) => (
            StatusCode::SEE_OTHER,
            [NO_STORE],
            AppendHeaders([
                (header::LOCATION, url),
                (
                    header::SET_COOKIE,
                    set_cookie(
                        &sso.config,
                        STATE_COOKIE,
                        &state,
                        "/v1/sso",
                        LOGIN_NS / 1_000_000_000,
                    ),
                ),
            ]),
        )
            .into_response(),
        Err(e) => {
            tracing::warn!("sso login: {e}");
            (
                StatusCode::BAD_GATEWAY,
                Json(json!({ "error": "the identity provider is not available" })),
            )
                .into_response()
        }
    }
}

/// What a callback came to.
enum Outcome {
    SignedIn {
        /// The session cookie's value.
        session: String,
        /// `user@organisation`.
        label: String,
        user: String,
        how: SignedIn,
    },
    Refused(String),
}

/// Keeps a value from the query fit for an audit line.
fn tidy(s: &str) -> String {
    s.chars()
        .filter(|c| c.is_ascii_alphanumeric() || " ._-".contains(*c))
        .take(100)
        .collect()
}

async fn callback(
    State(app): State<Shared>,
    headers: HeaderMap,
    Query(q): Query<HashMap<String, String>>,
) -> Response {
    let Some(sso) = &app.sso else {
        return not_configured();
    };
    let state = q.get("state").cloned().unwrap_or_default();
    let early = if let Some(e) = q.get("error") {
        Some(format!("the identity provider answered {}", tidy(e)))
    } else if state.is_empty() || !q.contains_key("code") {
        Some("the callback has no code or state".to_string())
    } else if cookie(&headers, STATE_COOKIE).as_deref() != Some(state.as_str()) {
        Some("the state is not this browser's".to_string())
    } else {
        None
    };
    let outcome = match early {
        Some(reason) => Outcome::Refused(reason),
        None => {
            let a = app.clone();
            let code = q.get("code").cloned().unwrap_or_default();
            tokio::task::spawn_blocking(move || sign_in(&a, &state, &code))
                .await
                .unwrap_or_else(|e| Outcome::Refused(e.to_string()))
        }
    };
    let clear_state = set_cookie(&sso.config, STATE_COOKIE, "", "/v1/sso", 0);
    match outcome {
        Outcome::SignedIn {
            session,
            label,
            user,
            how,
        } => {
            if how == SignedIn::Provisioned {
                audit(
                    &app,
                    &label,
                    "user_provisioned",
                    json!({ "user": user, "via": "sso" }),
                );
            }
            audit(
                &app,
                &label,
                "sso_login",
                json!({ "user": user, "how": how.as_str() }),
            );
            let cookie = set_cookie(
                &sso.config,
                SESSION_COOKIE,
                &session,
                "/",
                parts::SESSION_SECONDS,
            );
            (
                StatusCode::SEE_OTHER,
                [NO_STORE],
                AppendHeaders([
                    (header::LOCATION, "/".to_string()),
                    (header::SET_COOKIE, clear_state),
                    (header::SET_COOKIE, cookie),
                ]),
            )
                .into_response()
        }
        Outcome::Refused(reason) => {
            tracing::warn!("sso refused: {reason}");
            audit(&app, "sso", "sso_refused", json!({ "reason": reason }));
            (
                StatusCode::SEE_OTHER,
                [NO_STORE],
                AppendHeaders([
                    (header::LOCATION, "/?sso=refused".to_string()),
                    (header::SET_COOKIE, clear_state),
                ]),
            )
                .into_response()
        }
    }
}

/// The blocking part of the callback: the identity provider, then the
/// user and the session in `participants.db`.
fn sign_in(app: &crate::api::App, state: &str, code: &str) -> Outcome {
    let Some(sso) = &app.sso else {
        return Outcome::Refused("sign in with SSO is not configured".into());
    };
    let now = (app.now)();
    let id = match sso.finish(state, code, now) {
        Ok(id) => id,
        Err(e) => return Outcome::Refused(e),
    };
    let path = app.participants.path();
    let (user, how) = match parts::sign_in(path, &id, &sso.config.organisation) {
        Ok(Ok(found)) => found,
        Ok(Err(reason)) => return Outcome::Refused(reason),
        Err(e) => return Outcome::Refused(format!("store: {e}")),
    };
    let session = match parts::add_session(path, &user) {
        Ok(v) => v,
        Err(e) => return Outcome::Refused(e),
    };
    let label = app
        .participants
        .session_caller(&session, now / 1_000_000_000)
        .ok()
        .flatten()
        .map_or_else(|| user.clone(), |c| c.label());
    Outcome::SignedIn {
        session,
        label,
        user,
        how,
    }
}

async fn logout(State(app): State<Shared>, headers: HeaderMap) -> Response {
    let Some(sso) = &app.sso else {
        return not_configured();
    };
    if let Some(value) = session_value(&app, &headers) {
        let a = app.clone();
        let ended = tokio::task::spawn_blocking(move || {
            let who = a
                .participants
                .session_caller(&value, (a.now)() / 1_000_000_000)
                .ok()
                .flatten();
            parts::end_session(a.participants.path(), &value).map(|ended| (ended, who))
        })
        .await
        .unwrap_or_else(|e| Err(e.to_string()));
        match ended {
            Ok((true, Some(c))) => audit(&app, &c.label(), "sso_logout", json!({ "user": c.user })),
            Ok(_) => {}
            Err(e) => tracing::error!("sso logout: {e}"),
        }
    }
    (
        StatusCode::OK,
        [NO_STORE],
        AppendHeaders([(
            header::SET_COOKIE,
            set_cookie(&sso.config, SESSION_COOKIE, "", "/", 0),
        )]),
        Json(json!({ "signed_out": true })),
    )
        .into_response()
}

fn audit(app: &crate::api::App, by: &str, action: &str, fields: Value) {
    if let Err(e) = app.audit.record((app.now)(), by, action, fields) {
        tracing::error!("audit {action}: {e}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn encoding_and_cookies() {
        assert_eq!(enc("openid email profile"), "openid%20email%20profile");
        assert_eq!(enc("https://a/b?c=d"), "https%3A%2F%2Fa%2Fb%3Fc%3Dd");
        let mut h = HeaderMap::new();
        h.append(
            header::COOKIE,
            HeaderValue::from_static("a=1; frank_session=abc"),
        );
        h.append(
            header::COOKIE,
            HeaderValue::from_static("frank_sso_state=s1"),
        );
        assert_eq!(cookie(&h, "frank_session").as_deref(), Some("abc"));
        assert_eq!(cookie(&h, "frank_sso_state").as_deref(), Some("s1"));
        assert_eq!(cookie(&h, "frank"), None);
    }

    struct TempFile(PathBuf);
    impl Drop for TempFile {
        fn drop(&mut self) {
            let _ = std::fs::remove_file(&self.0);
        }
    }

    fn secret_file(name: &str, value: &str) -> TempFile {
        let p = std::env::temp_dir().join(format!("frank-sso-{name}-{}", std::process::id()));
        std::fs::write(&p, value).unwrap();
        TempFile(p)
    }

    fn full(file: &TempFile) -> Settings {
        Settings {
            issuer: Some("https://lab271.okta.com/oauth2/default/".into()),
            client_id: Some("0oa123".into()),
            client_secret_file: Some(file.0.clone()),
            redirect_url: Some("https://frank.lab271.dev/v1/sso/callback".into()),
            organisation: Some("lab271".into()),
        }
    }

    #[test]
    fn none_given_is_off() {
        assert!(Config::from_settings(Settings::default())
            .unwrap()
            .is_none());
    }

    #[test]
    fn complete_settings() {
        let f = secret_file("complete", "s3cr3t-value\n");
        let c = Config::from_settings(full(&f)).unwrap().unwrap();
        assert_eq!(c.issuer, "https://lab271.okta.com/oauth2/default");
        assert_eq!(c.client_secret.expose(), "s3cr3t-value");
        assert_eq!(c.origin, "https://frank.lab271.dev");
    }

    #[test]
    fn partial_settings_name_what_is_missing() {
        let f = secret_file("partial", "s3cr3t-value");
        let mut s = full(&f);
        s.client_id = None;
        s.organisation = None;
        let e = Config::from_settings(s).unwrap_err();
        assert!(e.contains("FRANK_SSO_CLIENT_ID"), "{e}");
        assert!(e.contains("FRANK_SSO_ORGANISATION"), "{e}");
        assert!(!e.contains("FRANK_SSO_ISSUER,"), "{e}");
    }

    #[test]
    fn the_secret_is_never_printed() {
        let f = secret_file("printed", "s3cr3t-value");
        let c = Config::from_settings(full(&f)).unwrap().unwrap();
        let shown = format!("{c:?} {}", c.client_secret);
        assert!(!shown.contains("s3cr3t-value"), "{shown}");
    }

    #[test]
    fn an_empty_or_missing_secret_file_is_refused() {
        let f = secret_file("empty", " \n");
        let e = Config::from_settings(full(&f)).unwrap_err();
        assert!(e.contains("is empty"), "{e}");
        let mut s = full(&f);
        s.client_secret_file = Some("/nonexistent/frank-sso-secret".into());
        let e = Config::from_settings(s).unwrap_err();
        assert!(e.contains("not found"), "{e}");
    }

    #[test]
    fn http_only_for_local_hosts() {
        let f = secret_file("http", "x");
        let mut s = full(&f);
        s.issuer = Some("http://lab271.okta.com".into());
        let e = Config::from_settings(s).unwrap_err();
        assert!(e.contains("https is required"), "{e}");
        let mut s = full(&f);
        s.issuer = Some("http://sso.frank.local:9400".into());
        s.redirect_url = Some("https://frank.local:8443/v1/sso/callback".into());
        let c = Config::from_settings(s).unwrap().unwrap();
        assert_eq!(c.origin, "https://frank.local:8443");
    }

    #[test]
    fn urls() {
        let u = Url::parse("HTTPS://Frank.Local:8443/v1/sso/callback?x=1").unwrap();
        assert_eq!(u.host, "frank.local");
        assert_eq!(u.port, Some(8443));
        assert_eq!(u.path, "/v1/sso/callback?x=1");
        assert_eq!(Url::parse("https://a.example").unwrap().path, "/");
        assert!(Url::parse("ftp://a").is_err());
        assert!(Url::parse("https://u:p@a").is_err());
        assert!(Url::parse("https://a:x").is_err());
        assert!(Url::parse("https://a/#f").is_err());
        assert!(Url::parse("a.example").is_err());
    }
}
