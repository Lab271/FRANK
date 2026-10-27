//! The HTTP API end to end, over a temporary data directory.

use std::sync::Arc;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use frank::api::{rebuild_iocs, router, App};
use frank::audit::Audit;
use frank::auth::{hash, uuid4};
use frank::store::participants::{self as parts, FILE};
use frank::store::{Iocs, Participants, Registry, Sightings};
use frank_core::Tier;
use http_body_util::BodyExt;
use serde_json::{json, Value};
use tower::ServiceExt;

use std::sync::atomic::{AtomicI64, Ordering};

/// 2026-10-22 12:00 UTC.
const NOW: i64 = 1_792_670_400_000_000_000;
const HOUR_NS: i64 = 3_600 * 1_000_000_000;
/// The tables' clock; one test moves it to close an hour.
static CLOCK: AtomicI64 = AtomicI64::new(NOW);
fn now() -> i64 {
    CLOCK.load(Ordering::SeqCst).max(NOW)
}

struct Harness {
    app: axum::Router,
    sightings: Sightings,
    iocs: Iocs,
    registry: Registry,
    /// `participants.db`, for changes made while the server runs.
    db: std::path::PathBuf,
    _dir: TempDir,
}

struct TempDir(std::path::PathBuf);
impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn harness(name: &str) -> Harness {
    let dir = std::env::temp_dir().join(format!("frank-api-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    // One organisation per test token, each with one user of its name.
    let db = dir.join(FILE);
    for (token, name, status) in [
        ("o", "obs", Tier::Observer),
        ("c", "mdr", Tier::Contributor),
        ("c2", "mdr2", Tier::Contributor),
        ("c3", "mdr3", Tier::Contributor),
        ("p", "lab", Tier::Partner),
    ] {
        parts::add_organisation(&db, name, status, "cyber_partner", None, None).unwrap();
        parts::add_user(&db, name, name, "human", None).unwrap();
        parts::add_token_hash(&db, name, &hash(token)).unwrap();
    }
    let sightings = Sightings::open(&dir, None, now).unwrap();
    let iocs = Iocs::open(&dir).unwrap();
    let registry = Registry::open(&dir, &sightings).unwrap();
    let app = router(Arc::new(App {
        sightings: sightings.clone(),
        iocs: iocs.clone(),
        participants: Participants::open(&dir).unwrap(),
        registry: registry.clone(),
        audit: Audit::open(&dir).unwrap(),
        submit_lock: std::sync::Mutex::new(()),
        now,
    }));
    Harness {
        app,
        sightings,
        iocs,
        registry,
        db,
        _dir: TempDir(dir),
    }
}

async fn call(
    app: &axum::Router,
    method: &str,
    uri: &str,
    token: Option<&str>,
    body: Option<Value>,
) -> (StatusCode, Value) {
    let mut req = Request::builder().method(method).uri(uri);
    if let Some(t) = token {
        req = req.header("authorization", format!("Bearer {t}"));
    }
    let req = match body {
        Some(b) => req
            .header("content-type", "application/json")
            .body(Body::from(b.to_string())),
        None => req.body(Body::empty()),
    }
    .unwrap();
    let resp = app.clone().oneshot(req).await.unwrap();
    let status = resp.status();
    let bytes = resp.into_body().collect().await.unwrap().to_bytes();
    (
        status,
        serde_json::from_slice(&bytes).unwrap_or(Value::Null),
    )
}

/// A new sighting: each call has its own sender id.
fn sighting(sector: &str, ip: &str, rule: &str) -> Value {
    json!({"submission": {
        "submitter": {"organisation_id": "identity-secret-org", "sector": "msp"},
        "hit_target": {"organisation_id": "identity-victim", "sector": sector},
        "sighting": {"sighting_id": uuid4().unwrap(), "timestamp": "2026-10-22T10:00:00Z", "severity": "high",
            "sigma_detection": {"rule_id": rule},
            "observables": {"network": [{"type": "ipv4", "value": ip}, {"type": "domain", "value": "Evil.example"}]}}}})
}

#[tokio::test]
async fn tiers_gate_the_routes() {
    let h = harness("tiers");
    let s = sighting("energy", "185.220.102.45", "r1");
    assert_eq!(
        call(&h.app, "POST", "/v1/sightings", None, Some(s.clone()))
            .await
            .0,
        StatusCode::FORBIDDEN
    );
    assert_eq!(
        call(&h.app, "POST", "/v1/sightings", Some("o"), Some(s.clone()))
            .await
            .0,
        StatusCode::FORBIDDEN
    );
    assert_eq!(
        call(
            &h.app,
            "POST",
            "/v1/sightings",
            Some("bogus"),
            Some(s.clone())
        )
        .await
        .0,
        StatusCode::UNAUTHORIZED
    );
    assert_eq!(
        call(&h.app, "GET", "/v1/files", Some("c"), None).await.0,
        StatusCode::FORBIDDEN
    );
    assert_eq!(
        call(
            &h.app,
            "GET",
            "/v1/iocs?type=ipv4&value=1.2.3.4",
            Some("o"),
            None
        )
        .await
        .0,
        StatusCode::FORBIDDEN
    );
    assert_eq!(
        call(&h.app, "GET", "/health", None, None).await.0,
        StatusCode::OK
    );
    let (st, who) = call(&h.app, "GET", "/v1/whoami", Some("p"), None).await;
    assert_eq!(
        (st, who["tier"].as_str()),
        (StatusCode::OK, Some("partner"))
    );
}

#[tokio::test]
async fn submit_then_look_up() {
    let h = harness("submit");
    let (st, body) = call(
        &h.app,
        "POST",
        "/v1/sightings",
        Some("c"),
        Some(json!([
            sighting("energy", "185.220.102.45", "r1"),
            sighting("energy", "185.220.102.46", "r1"),
        ])),
    )
    .await;
    assert_eq!(st, StatusCode::CREATED, "{body}");
    assert_eq!(body["rows"], 4);
    assert_eq!(body["receipts"].as_array().unwrap().len(), 2);
    assert!(body["receipts"][0]["sighting_id"]
        .as_str()
        .unwrap()
        .starts_with("sighting--"));

    let (st, ioc) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=domain&value=EVIL.example",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(st, StatusCode::OK);
    assert_eq!(ioc["known"], true);
    assert_eq!(ioc["count"], 2);
    assert_eq!(ioc["days"][0]["day"], "2026-10-22");
    assert_eq!(ioc["rules"][0], json!({"rule_id": "r1", "count": 2}));

    let (_, unknown) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=ipv4&value=10.0.0.1",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(unknown["known"], false);

    let (_, range) = call(
        &h.app,
        "GET",
        "/v1/iocs/range?cidr=185.220.102.0/24",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(range["addresses"].as_array().unwrap().len(), 2);

    assert_eq!(
        call(
            &h.app,
            "GET",
            "/v1/iocs?type=ipv4&value=nope",
            Some("c"),
            None
        )
        .await
        .0,
        StatusCode::UNPROCESSABLE_ENTITY
    );
}

#[tokio::test]
async fn nothing_identifying_is_stored() {
    let h = harness("anon");
    call(
        &h.app,
        "POST",
        "/v1/sightings",
        Some("c"),
        Some(sighting("energy", "1.2.3.4", "r1")),
    )
    .await;
    let r = h
        .sightings
        .query("SELECT sighting_id, reporter_sector, target_sector, ioc_value FROM sightings")
        .unwrap();
    let dump = format!("{:?}", r.rows);
    assert!(!dump.contains("identity-"), "{dump}");
    assert_eq!(r.columns.len(), 4);
    let (_, preview) = call(
        &h.app,
        "POST",
        "/v1/preview",
        None,
        Some(sighting("energy", "1.2.3.4", "r1")),
    )
    .await;
    assert!(!preview.to_string().contains("identity-"), "{preview}");
    assert_eq!(preview["rows"].as_array().unwrap().len(), 2);
}

#[tokio::test]
async fn small_cells_are_suppressed_below_partner() {
    let h = harness("stats");
    // energy: three reporters, one sighting each. water: one reporter,
    // three sightings (six rows), which is still one reporter (#148).
    for (i, tok) in ["c", "c2", "c3"].iter().enumerate() {
        let s = sighting("energy", &format!("10.0.0.{i}"), "r1");
        assert_eq!(
            call(&h.app, "POST", "/v1/sightings", Some(tok), Some(s))
                .await
                .0,
            StatusCode::CREATED
        );
    }
    let water: Vec<Value> = (0..3)
        .map(|i| sighting("water", &format!("10.0.1.{i}"), "r2"))
        .collect();
    assert_eq!(
        call(
            &h.app,
            "POST",
            "/v1/sightings",
            Some("c"),
            Some(json!(water))
        )
        .await
        .0,
        StatusCode::CREATED
    );

    let (_, public) = call(&h.app, "GET", "/v1/statistics", None, None).await;
    assert_eq!(
        public["sightings"], 0,
        "GREEN (the default) is not public: {public}"
    );
    assert!(public.get("by_target_sector").is_none(), "{public}");

    let (_, obs) = call(&h.app, "GET", "/v1/statistics?days=7", Some("o"), None).await;
    assert_eq!(
        obs["by_target_sector"],
        json!([{"key": "energy", "count": 3, "reporters": 3}]),
        "three sightings of two IoCs each; water has one reporter, under the k threshold"
    );
    assert!(obs.get("top_rules").is_none());

    let (_, contrib) = call(&h.app, "GET", "/v1/statistics", Some("c"), None).await;
    assert_eq!(
        contrib["top_rules"],
        json!([{"key": "r1", "count": 3, "reporters": 3}])
    );

    let (_, partner) = call(&h.app, "GET", "/v1/statistics", Some("p"), None).await;
    assert_eq!(
        partner["by_target_sector"].as_array().unwrap().len(),
        2,
        "partners see exact cells"
    );
    assert_eq!(
        partner["top_rules"][1],
        json!({"key": "r2", "count": 3, "reporters": 1})
    );

    assert_eq!(
        call(&h.app, "GET", "/v1/statistics?days=0", None, None)
            .await
            .0,
        StatusCode::UNPROCESSABLE_ENTITY
    );
}

#[tokio::test]
async fn lookups_count_reporters() {
    let h = harness("reporters");
    for tok in ["c", "c", "c2"] {
        call(
            &h.app,
            "POST",
            "/v1/sightings",
            Some(tok),
            Some(sighting("energy", "198.51.100.7", "r1")),
        )
        .await;
    }
    let (_, ioc) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=ipv4&value=198.51.100.7",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(
        (ioc["count"].as_i64(), ioc["reporters"].as_i64()),
        (Some(3), Some(2)),
        "{ioc}"
    );
}

#[tokio::test]
async fn files_hold_participant_ids_not_names_or_tokens() {
    let h = harness("participant-ids");
    call(
        &h.app,
        "POST",
        "/v1/sightings",
        Some("c"),
        Some(sighting("energy", "198.51.100.8", "r1")),
    )
    .await;
    call(
        &h.app,
        "POST",
        "/v1/sightings",
        Some("c2"),
        Some(sighting("energy", "198.51.100.9", "r1")),
    )
    .await;
    let req = Request::get("/v1/files/open/current.parquet")
        .header("authorization", "Bearer p")
        .body(Body::empty())
        .unwrap();
    let bytes = h
        .app
        .clone()
        .oneshot(req)
        .await
        .unwrap()
        .into_body()
        .collect()
        .await
        .unwrap()
        .to_bytes()
        .to_vec();
    let text = String::from_utf8_lossy(&bytes);
    for secret in [
        hash("c"),
        hash("c2"),
        "mdr2".to_string(),
        "identity-secret-org".to_string(),
    ] {
        assert!(
            !text.contains(&secret),
            "{secret} leaked into the Parquet file"
        );
    }
    use db_core::engine::{column::BatchEngine, Cell, Engine};
    let mut e = BatchEngine::from_bytes("sightings", bytes).unwrap();
    let r = e
        .run_query("SELECT count(DISTINCT reporter) FROM sightings")
        .unwrap();
    assert_eq!(r.rows, vec![vec![Cell::Int(2)]]);
}

#[tokio::test]
async fn bad_submissions_are_422() {
    let h = harness("bad");
    for body in [
        json!({"sighting": {}}),
        json!({"nope": 1}),
        json!({"sighting": {"confidence": 1.5, "sigma_detection": {"rule_id": "r"}}}),
    ] {
        let (st, err) = call(&h.app, "POST", "/v1/sightings", Some("c"), Some(body)).await;
        assert_eq!(st, StatusCode::UNPROCESSABLE_ENTITY, "{err}");
        assert!(err["error"].is_string());
    }
}

#[tokio::test]
async fn partners_get_listed_files_only() {
    let h = harness("files");
    call(
        &h.app,
        "POST",
        "/v1/sightings",
        Some("c"),
        Some(sighting("energy", "1.2.3.4", "r1")),
    )
    .await;
    // An hour later the submission's hour is closed and flushed to a file.
    CLOCK.store(NOW + 2 * HOUR_NS, Ordering::SeqCst);
    assert_eq!(h.sightings.flush().unwrap(), 1);
    let (st, files) = call(&h.app, "GET", "/v1/files", Some("p"), None).await;
    assert_eq!(st, StatusCode::OK);
    assert_eq!(files["files"].as_array().unwrap().len(), 1, "{files}");
    assert_eq!(files["table"], "sightings");
    for bad in [
        "/v1/files/manifest.json",
        "/v1/files/..%2F..%2Fetc%2Fpasswd",
        "/v1/files/wal/0.log",
    ] {
        assert_eq!(
            call(&h.app, "GET", bad, Some("p"), None).await.0,
            StatusCode::NOT_FOUND,
            "{bad}"
        );
    }
    // Each listed file downloads as Parquet.
    for f in files["files"].as_array().unwrap() {
        let uri = format!("/v1/files/{}", f["path"].as_str().unwrap());
        let req = Request::get(&uri)
            .header("authorization", "Bearer p")
            .body(Body::empty())
            .unwrap();
        let resp = h.app.clone().oneshot(req).await.unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        let bytes = resp.into_body().collect().await.unwrap().to_bytes();
        assert_eq!(&bytes[..4], b"PAR1");
    }
}

#[tokio::test]
async fn the_open_hour_is_a_file_too() {
    let h = harness("open");
    call(
        &h.app,
        "POST",
        "/v1/sightings",
        Some("c"),
        Some(json!([
            sighting("energy", "1.2.3.4", "r1"),
            sighting("water", "1.2.3.5", "r2")
        ])),
    )
    .await;
    let (_, files) = call(&h.app, "GET", "/v1/files", Some("p"), None).await;
    let open = files["files"]
        .as_array()
        .unwrap()
        .iter()
        .find(|f| f["open"] == true)
        .expect("open file listed");
    assert_eq!(open["rows"], 4);
    let req = Request::get("/v1/files/open/current.parquet")
        .header("authorization", "Bearer p")
        .body(Body::empty())
        .unwrap();
    let resp = h.app.clone().oneshot(req).await.unwrap();
    assert_eq!(resp.status(), StatusCode::OK);
    let bytes = resp
        .into_body()
        .collect()
        .await
        .unwrap()
        .to_bytes()
        .to_vec();
    assert_eq!(&bytes[..4], b"PAR1");
    // The browser engine reads it like any hour file.
    use db_core::engine::{column::BatchEngine, Cell, Engine};
    let mut e = BatchEngine::from_bytes("sightings", bytes).unwrap();
    let r = e
        .run_query("SELECT count(*), count(DISTINCT rule_id) FROM sightings")
        .unwrap();
    assert_eq!(r.rows, vec![vec![Cell::Int(4), Cell::Int(2)]]);
}

/// `sighting` at TLP `tlp`.
fn with_tlp(mut s: Value, tlp: &str) -> Value {
    s["submission"]["tlp_level"] = json!(tlp);
    s
}

#[tokio::test]
async fn tlp_red_is_refused() {
    let h = harness("tlp-red");
    let (st, err) = call(
        &h.app,
        "POST",
        "/v1/sightings",
        Some("c"),
        Some(with_tlp(sighting("energy", "1.2.3.4", "r1"), "TLP:RED")),
    )
    .await;
    assert_eq!(st, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(err["error"].as_str().unwrap().contains("TLP:RED"), "{err}");
}

#[tokio::test]
async fn each_tier_sees_its_tlp_levels() {
    let h = harness("tlp");
    // One sighting per level, each with its own IoC.
    let batch: Vec<Value> = [
        ("clear", "10.9.0.1"),
        ("green", "10.9.0.2"),
        ("amber", "10.9.0.3"),
        ("amber+strict", "10.9.0.4"),
    ]
    .iter()
    .map(|(t, ip)| with_tlp(sighting("energy", ip, &format!("r-{t}")), t))
    .collect();
    assert_eq!(
        call(
            &h.app,
            "POST",
            "/v1/sightings",
            Some("c"),
            Some(json!(batch))
        )
        .await
        .0,
        StatusCode::CREATED
    );

    let sightings = |v: &Value| v["sightings"].as_i64().unwrap();
    let (_, public) = call(&h.app, "GET", "/v1/statistics", None, None).await;
    let (_, obs) = call(&h.app, "GET", "/v1/statistics", Some("o"), None).await;
    let (_, contrib) = call(&h.app, "GET", "/v1/statistics", Some("c"), None).await;
    let (_, partner) = call(&h.app, "GET", "/v1/statistics", Some("p"), None).await;
    assert_eq!(
        [
            sightings(&public),
            sightings(&obs),
            sightings(&contrib),
            sightings(&partner)
        ],
        [1, 2, 3, 4]
    );
    let rules: Vec<&str> = contrib["top_rules"]
        .as_array()
        .unwrap()
        .iter()
        .map(|c| c["key"].as_str().unwrap())
        .collect();
    assert!(!rules.contains(&"r-amber+strict"), "{rules:?}");

    // AMBER+STRICT is partner-only, in the IoC table too.
    let lookup = |tok| {
        call(
            &h.app,
            "GET",
            "/v1/iocs?type=ipv4&value=10.9.0.4",
            Some(tok),
            None,
        )
    };
    assert_eq!(lookup("c").await.1["known"], false);
    assert_eq!(lookup("p").await.1["known"], true);
    let (_, range) = call(
        &h.app,
        "GET",
        "/v1/iocs/range?cidr=10.9.0.0/24",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(range["addresses"].as_array().unwrap().len(), 3, "{range}");
    // The shared domain is counted only at visible levels.
    let (_, dom) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=domain&value=evil.example",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(dom["count"], 3);
    assert_eq!(public["iocs"], 2, "the CLEAR sighting's ip and domain");

    // Partners download everything stored; nothing stored is RED.
    let req = Request::get("/v1/files/open/current.parquet")
        .header("authorization", "Bearer p")
        .body(Body::empty())
        .unwrap();
    let bytes = h
        .app
        .clone()
        .oneshot(req)
        .await
        .unwrap()
        .into_body()
        .collect()
        .await
        .unwrap()
        .to_bytes()
        .to_vec();
    use db_core::engine::{column::BatchEngine, Cell, Engine};
    let mut e = BatchEngine::from_bytes("sightings", bytes).unwrap();
    let r = e
        .run_query("SELECT count(*) FROM sightings WHERE tlp = 'red'")
        .unwrap();
    assert_eq!(r.rows, vec![vec![Cell::Int(0)]]);
    let all = e
        .run_query("SELECT count(DISTINCT tlp) FROM sightings")
        .unwrap();
    assert_eq!(all.rows, vec![vec![Cell::Int(4)]]);
}

/// Three reporters for rule r1 in energy, one reporter for r2 in water.
async fn explore_fixture(h: &Harness) {
    for (i, tok) in ["c", "c2", "c3"].iter().enumerate() {
        let s = sighting("energy", &format!("198.51.100.{i}"), "r1");
        assert_eq!(
            call(&h.app, "POST", "/v1/sightings", Some(tok), Some(s))
                .await
                .0,
            StatusCode::CREATED
        );
    }
    let water: Vec<Value> = (0..3)
        .map(|i| sighting("water", &format!("203.0.113.{i}"), "r2"))
        .collect();
    assert_eq!(
        call(
            &h.app,
            "POST",
            "/v1/sightings",
            Some("c"),
            Some(json!(water))
        )
        .await
        .0,
        StatusCode::CREATED
    );
}

fn keys(v: &Value) -> Vec<String> {
    v["rows"]
        .as_array()
        .unwrap()
        .iter()
        .map(|r| r["key"].as_str().unwrap().to_string())
        .collect()
}

#[tokio::test]
async fn explore_groups_filters_and_suppresses() {
    let h = harness("explore");
    explore_fixture(&h).await;

    let (st, rules) = call(&h.app, "GET", "/v1/explore?group=rule", Some("c"), None).await;
    assert_eq!(st, StatusCode::OK, "{rules}");
    assert_eq!(keys(&rules), ["r1"], "r2 has one reporter");
    let r1 = &rules["rows"][0];
    assert_eq!(
        (r1["count"].as_i64(), r1["reporters"].as_i64()),
        (Some(3), Some(3)),
        "sightings, not sighting x IoC rows"
    );
    assert!(r1["first_seen"].as_i64() <= r1["last_seen"].as_i64());

    let (_, partner) = call(&h.app, "GET", "/v1/explore?group=rule", Some("p"), None).await;
    assert_eq!(keys(&partner), ["r1", "r2"], "partners see exact cells");

    let (_, iocs) = call(
        &h.app,
        "GET",
        "/v1/explore?group=ioc&sector=ENERGY",
        Some("p"),
        None,
    )
    .await;
    assert!(
        keys(&iocs).contains(&"domain:evil.example".to_string()),
        "{iocs}"
    );
    assert!(
        keys(&iocs).iter().all(|k| !k.starts_with("ipv4:203.")),
        "water filtered out: {iocs}"
    );

    let (_, filtered) = call(
        &h.app,
        "GET",
        "/v1/explore?group=sector&rule=r1",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(keys(&filtered), ["energy"]);
}

#[tokio::test]
async fn explore_enforces_tiers_and_refuses_unknown_names() {
    let h = harness("explore-tiers");
    explore_fixture(&h).await;
    let status = |uri: &'static str, tok: Option<&'static str>| {
        let app = h.app.clone();
        async move { call(&app, "GET", uri, tok, None).await.0 }
    };
    assert_eq!(
        status("/v1/explore?group=sector", Some("o")).await,
        StatusCode::OK
    );
    assert_eq!(
        status("/v1/explore?group=rule", Some("o")).await,
        StatusCode::FORBIDDEN
    );
    assert_eq!(
        status("/v1/explore?group=sector&ioc=ipv4:198.51.100.1", Some("o")).await,
        StatusCode::FORBIDDEN
    );
    assert_eq!(
        status("/v1/explore?group=sector", None).await,
        StatusCode::FORBIDDEN
    );
    for bad in [
        "/v1/explore",
        "/v1/explore?group=org",
        "/v1/explore?group=rule&reporter=x",
        "/v1/explore?group=rule&days=0",
    ] {
        assert_eq!(
            status(bad, Some("p")).await,
            StatusCode::UNPROCESSABLE_ENTITY,
            "{bad}"
        );
    }
}

#[tokio::test]
async fn explore_respects_tlp() {
    let h = harness("explore-tlp");
    for tok in ["c", "c2", "c3"] {
        let s = with_tlp(
            sighting("energy", "198.51.100.50", "r-strict"),
            "amber+strict",
        );
        call(&h.app, "POST", "/v1/sightings", Some(tok), Some(s)).await;
    }
    let (_, contrib) = call(&h.app, "GET", "/v1/explore?group=rule", Some("c"), None).await;
    assert!(
        keys(&contrib).is_empty(),
        "AMBER+STRICT is partner-only: {contrib}"
    );
    let (_, partner) = call(&h.app, "GET", "/v1/explore?group=rule", Some("p"), None).await;
    assert_eq!(keys(&partner), ["r-strict"]);
}

#[tokio::test]
async fn rule_detail_shows_prevalence() {
    let h = harness("rule-detail");
    explore_fixture(&h).await;
    let (st, r1) = call(&h.app, "GET", "/v1/rules/r1", Some("c"), None).await;
    assert_eq!(st, StatusCode::OK, "{r1}");
    assert_eq!(
        (
            r1["known"].as_bool(),
            r1["count"].as_i64(),
            r1["reporters"].as_i64()
        ),
        (Some(true), Some(3), Some(3))
    );
    assert_eq!(r1["sectors"][0]["key"], "energy");
    let trend = r1["trend"].as_array().unwrap();
    assert_eq!(trend.len(), 30);
    assert_eq!(
        trend.iter().map(|d| d[1].as_i64().unwrap()).sum::<i64>(),
        3,
        "every sighting is in the trend, once"
    );
    assert_eq!(trend.last().unwrap()[0], "2026-10-22");

    let (_, r2) = call(&h.app, "GET", "/v1/rules/r2", Some("c"), None).await;
    assert_eq!(
        r2,
        json!({"rule": "r2", "known": false}),
        "one reporter: hidden below partner"
    );
    let (_, r2p) = call(&h.app, "GET", "/v1/rules/r2", Some("p"), None).await;
    assert_eq!(r2p["reporters"], 1);
    assert_eq!(
        call(&h.app, "GET", "/v1/rules/r1", Some("o"), None).await.0,
        StatusCode::FORBIDDEN
    );

    let (_, ioc) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=domain&value=evil.example",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(ioc["trend"].as_array().unwrap().len(), 30);
}

#[tokio::test]
async fn iocs_rebuild_from_sightings() {
    let h = harness("rebuild");
    call(
        &h.app,
        "POST",
        "/v1/sightings",
        Some("c"),
        Some(json!([
            sighting("energy", "1.2.3.4", "r1"),
            sighting("energy", "1.2.3.4", "r2")
        ])),
    )
    .await;
    let ioc = frank_core::Ioc::new(frank_core::IocType::Ipv4, "1.2.3.4").unwrap();
    let before = h.iocs.lookup(&ioc, &frank_core::Tlp::SHARED).unwrap();
    rebuild_iocs(&h.sightings, &h.iocs).unwrap();
    assert_eq!(
        h.iocs.lookup(&ioc, &frank_core::Tlp::SHARED).unwrap(),
        before
    );
    assert_eq!(before[0].count, 2);
}

/// The epic's acceptance criteria (#159): the organisation is the
/// reporter, its status is every user's tier, tokens revoke one by one.
#[tokio::test]
async fn participants_are_the_reporters() {
    let h = harness("participants");
    parts::add_user(&h.db, "mdr", "mdr-feed", "machine", None).unwrap();
    let feed = parts::add_token(&h.db, "mdr-feed").unwrap();

    // Two users of one organisation are one reporter.
    for (token, ip) in [("c", "198.51.100.1"), (feed.as_str(), "198.51.100.2")] {
        let (status, _) = call(
            &h.app,
            "POST",
            "/v1/sightings",
            Some(token),
            Some(sighting("energy", ip, "r9")),
        )
        .await;
        assert_eq!(status, StatusCode::CREATED);
    }
    let r = h
        .sightings
        .query("SELECT count(DISTINCT reporter), min(reporter) FROM sightings")
        .unwrap();
    let id = parts::organisation_id(&h.db, "mdr").unwrap();
    assert_eq!(
        r.rows[0][0],
        db_core::engine::Cell::Int(1),
        "one organisation, one reporter"
    );
    assert_eq!(r.rows[0][1], db_core::engine::Cell::Text(id.clone()));

    let (_, me) = call(&h.app, "GET", "/v1/whoami", Some(&feed), None).await;
    assert_eq!(me["participant"]["id"], id.as_str());
    assert_eq!(
        (me["user"].as_str(), me["label"].as_str()),
        (Some("mdr-feed"), Some("mdr-feed@mdr"))
    );

    // A status change reaches every user on the next request, without
    // new tokens or a restart.
    let s = sighting("water", "198.51.100.3", "r9");
    assert_eq!(
        call(&h.app, "POST", "/v1/sightings", Some("o"), Some(s.clone()))
            .await
            .0,
        StatusCode::FORBIDDEN
    );
    parts::set_status(&h.db, "obs", Tier::Contributor).unwrap();
    assert_eq!(
        call(&h.app, "POST", "/v1/sightings", Some("o"), Some(s))
            .await
            .0,
        StatusCode::CREATED
    );
    parts::set_status(&h.db, "mdr", Tier::Observer).unwrap();
    for t in ["c", feed.as_str()] {
        let (_, me) = call(&h.app, "GET", "/v1/whoami", Some(t), None).await;
        assert_eq!(me["tier"], "observer");
    }

    // Revoking one token leaves the organisation's other users working.
    parts::revoke(&h.db, &hash(&feed)[..12]).unwrap();
    assert_eq!(
        call(&h.app, "GET", "/v1/whoami", Some(&feed), None).await.0,
        StatusCode::UNAUTHORIZED
    );
    assert_eq!(
        call(&h.app, "GET", "/v1/whoami", Some("c"), None).await.0,
        StatusCode::OK
    );
}

/// The sender's id is the registration (#159): a resend is answered with
/// the original receipt, other content under the same id is a conflict.
#[tokio::test]
async fn a_resend_is_recognised() {
    let h = harness("resend");
    let s = sighting("energy", "198.51.100.20", "r1");
    let (status, first) = call(&h.app, "POST", "/v1/sightings", Some("c"), Some(s.clone())).await;
    assert_eq!(status, StatusCode::CREATED);
    let receipt = &first["receipts"][0];
    assert_eq!(receipt["status"], "created");
    assert!(receipt["sighting_id"]
        .as_str()
        .unwrap()
        .starts_with("sighting--"));

    // The same sighting again, keys reordered: same receipt, nothing new.
    let reordered: Value =
        serde_json::from_str(&s.to_string().replace("\"severity\":\"high\",", "")).unwrap();
    let mut reordered = reordered;
    reordered["submission"]["sighting"]["severity"] = json!("HIGH");
    let (status, again) = call(&h.app, "POST", "/v1/sightings", Some("c"), Some(reordered)).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(again["receipts"][0]["status"], "duplicate");
    assert_eq!(again["receipts"][0]["digest"], receipt["digest"]);
    assert_eq!(again["receipts"][0]["received"], receipt["received"]);
    assert_eq!(again["rows"], 0);

    // The registration is in the sightings: the index rebuilt from them
    // gives the same receipt.
    let r = h
        .sightings
        .query("SELECT DISTINCT digest, received FROM sightings")
        .unwrap();
    assert_eq!(r.rows.len(), 1);
    assert_eq!(h.registry.rebuild(&h.sightings).unwrap(), 1);
    let (status, rebuilt) = call(&h.app, "POST", "/v1/sightings", Some("c"), Some(s.clone())).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(rebuilt["receipts"][0], again["receipts"][0]);

    // Another organisation may use the same id: it is its own sighting.
    assert_eq!(
        call(&h.app, "POST", "/v1/sightings", Some("c2"), Some(s.clone()))
            .await
            .0,
        StatusCode::CREATED
    );

    // Other content under a registered id: 409, and nothing of the batch.
    let mut changed = s.clone();
    changed["submission"]["sighting"]["severity"] = json!("low");
    let fresh = sighting("energy", "198.51.100.21", "r1");
    let (status, err) = call(
        &h.app,
        "POST",
        "/v1/sightings",
        Some("c"),
        Some(json!([fresh, changed])),
    )
    .await;
    assert_eq!(status, StatusCode::CONFLICT, "{err}");
    let n = h
        .sightings
        .query("SELECT count(*) FROM sightings WHERE ioc_value = '198.51.100.21'")
        .unwrap();
    assert_eq!(
        n.rows[0][0],
        db_core::engine::Cell::Int(0),
        "the batch was refused whole"
    );

    // Each POST is one audit line naming the user, never in the Parquet.
    let mut lines = Vec::new();
    for f in std::fs::read_dir(h._dir.0.join("audit")).unwrap() {
        let text = std::fs::read_to_string(f.unwrap().path()).unwrap();
        lines.extend(
            text.lines()
                .map(|l| serde_json::from_str::<Value>(l).unwrap()),
        );
    }
    let actions: Vec<(&str, &str)> = lines
        .iter()
        .map(|l| (l["action"].as_str().unwrap(), l["by"].as_str().unwrap()))
        .collect();
    assert_eq!(
        actions,
        [
            ("submit", "mdr@mdr"),
            ("submit", "mdr@mdr"),
            ("submit", "mdr@mdr"),
            ("submit", "mdr2@mdr2"),
            ("submit_refused", "mdr@mdr"),
        ]
    );
    assert_eq!(lines[1]["receipts"][0]["status"], "duplicate");
    assert_eq!(lines[4]["conflicts"][0], receipt["sighting_id"]);
    let users = h
        .sightings
        .query("SELECT count(*) FROM sightings WHERE reporter = 'mdr'")
        .unwrap();
    assert_eq!(users.rows[0][0], db_core::engine::Cell::Int(0));

    // No id: refused, with the reason.
    let mut bare = sighting("energy", "198.51.100.22", "r1");
    bare["submission"]["sighting"]
        .as_object_mut()
        .unwrap()
        .remove("sighting_id");
    let (status, err) = call(&h.app, "POST", "/v1/sightings", Some("c"), Some(bare)).await;
    assert_eq!(status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(
        err["error"]
            .as_str()
            .unwrap()
            .contains("sighting_id is required"),
        "{err}"
    );
}

/// Who reported is shown by status (#159): never below partner, ids to a
/// partner, names to core.
#[tokio::test]
async fn reporters_are_shown_by_status() {
    let h = harness("identity");
    parts::add_organisation(&h.db, "ops", Tier::Core, "cyber_partner", None, None).unwrap();
    parts::add_user(&h.db, "ops", "ops", "human", None).unwrap();
    parts::add_token_hash(&h.db, "ops", &hash("k")).unwrap();
    let mdr = parts::organisation_id(&h.db, "mdr").unwrap();
    for t in ["c", "c2", "c3"] {
        call(
            &h.app,
            "POST",
            "/v1/sightings",
            Some(t),
            Some(sighting("energy", "198.51.100.30", "r1")),
        )
        .await;
    }
    // Every aggregate a contributor or partner can ask for: no id, no name.
    for token in ["o", "c", "p"] {
        for uri in [
            "/v1/statistics",
            "/v1/explore?group=sector",
            "/v1/explore?group=rule",
            "/v1/rules/r1",
            "/v1/iocs?type=ipv4&value=198.51.100.30",
        ] {
            let (_, body) = call(&h.app, "GET", uri, Some(token), None).await;
            let text = body.to_string();
            assert!(
                !text.contains(&mdr),
                "{uri} as {token} shows a reporter id: {text}"
            );
            assert!(
                !text.contains("\"mdr2\""),
                "{uri} as {token} shows a reporter name"
            );
        }
    }
    assert_eq!(
        call(&h.app, "GET", "/v1/participants", Some("c"), None)
            .await
            .0,
        StatusCode::FORBIDDEN
    );
    let (_, partner) = call(&h.app, "GET", "/v1/participants", Some("p"), None).await;
    let seen = partner["participants"].as_array().unwrap();
    assert!(seen
        .iter()
        .any(|p| p["id"] == mdr.as_str() && p["status"] == "contributor"));
    assert!(
        seen.iter().all(|p| p.get("name").is_none()),
        "a partner sees ids, not names"
    );
    let (_, core) = call(&h.app, "GET", "/v1/participants", Some("k"), None).await;
    let mdr_entry = core["participants"]
        .as_array()
        .unwrap()
        .iter()
        .find(|p| p["id"] == mdr.as_str())
        .unwrap()
        .clone();
    assert_eq!(
        (mdr_entry["name"].as_str(), mdr_entry["users"][0].as_str()),
        (Some("mdr"), Some("mdr"))
    );
}

/// #160: a sighting is counted once, with its observation count once, and
/// every one of its techniques is ranked.
#[tokio::test]
async fn counts_follow_the_sighting_grain() {
    let h = harness("grain");
    let s = json!({"sighting": {"sighting_id": uuid4().unwrap(), "timestamp": "2026-10-22T10:00:00Z",
        "observation_count": 10, "sigma_detection": {"rule_id": "r1"},
        "threat_context": {"mitre_attack": {"techniques": ["T1059", "T1071.001"]}},
        "observables": {"network": [{"type": "ipv4", "value": "198.51.100.1"},
            {"type": "ipv4", "value": "198.51.100.2"}, {"type": "domain", "value": "a.example"}]}}});
    assert_eq!(
        call(&h.app, "POST", "/v1/sightings", Some("p"), Some(s))
            .await
            .0,
        StatusCode::CREATED
    );
    let (_, st) = call(&h.app, "GET", "/v1/statistics", Some("p"), None).await;
    assert_eq!(
        (&st["sightings"], &st["observations"]),
        (&json!(1), &json!(10)),
        "{st}"
    );
    assert_eq!(
        st["top_rules"],
        json!([{"key": "r1", "count": 1, "reporters": 1}])
    );
    assert_eq!(
        keys_of(&st["top_techniques"]),
        ["T1059", "T1071.001"],
        "{st}"
    );
    assert_eq!(
        st["by_ioc_type"],
        json!([{"key": "ipv4", "count": 2, "reporters": 1}, {"key": "domain", "count": 1, "reporters": 1}]),
        "by IoC type counts the IoCs"
    );

    let ex = |uri: &'static str| {
        let app = h.app.clone();
        async move { call(&app, "GET", uri, Some("p"), None).await }
    };
    let (_, t) = ex("/v1/explore?group=technique&rule=r1").await;
    assert_eq!(keys(&t), ["T1059", "T1071.001"], "{t}");
    assert!(t["rows"]
        .as_array()
        .unwrap()
        .iter()
        .all(|r| r["count"] == 1));
    let (_, r) = ex("/v1/explore?group=rule&technique=t1071.001").await;
    assert_eq!(r["rows"][0]["count"], 1, "{r}");
    let (_, r) = ex("/v1/explore?group=rule&technique=T1071").await;
    assert_eq!(
        keys(&r),
        Vec::<String>::new(),
        "a technique, not a prefix: {r}"
    );
    let (_, r) = ex("/v1/explore?group=rule&ioc=ipv4:198.51.100.2").await;
    assert_eq!(r["rows"][0]["count"], 1, "an IoC past seq 0: {r}");
    let (code, _) = ex("/v1/explore?group=technique&ioc=ipv4:198.51.100.2").await;
    assert_eq!(code, StatusCode::UNPROCESSABLE_ENTITY);

    let r = h
        .sightings
        .query("SELECT seq, detail FROM sightings ORDER BY seq")
        .unwrap();
    assert_eq!(r.rows.len(), 3);
    let detail = r.rows[0][1].to_string();
    assert!(
        detail.contains("frank/1") && detail.contains("T1071.001"),
        "{detail}"
    );
    assert!(r.rows[1..]
        .iter()
        .all(|row| row[1] == db_core::engine::Cell::Null));
}

fn keys_of(v: &Value) -> Vec<String> {
    v.as_array()
        .unwrap()
        .iter()
        .map(|r| r["key"].as_str().unwrap().to_string())
        .collect()
}

/// POSTs `body` as `content_type`.
async fn post_as(app: &axum::Router, content_type: &str, body: &str) -> (StatusCode, Value) {
    let req = Request::builder()
        .method("POST")
        .uri("/v1/sightings")
        .header("authorization", "Bearer c")
        .header("content-type", content_type)
        .body(Body::from(body.to_string()))
        .unwrap();
    let resp = app.clone().oneshot(req).await.unwrap();
    let status = resp.status();
    let bytes = resp.into_body().collect().await.unwrap().to_bytes();
    (
        status,
        serde_json::from_slice(&bytes).unwrap_or(Value::Null),
    )
}

/// #160: the Content-Type picks the format; one sighting in three formats
/// is one registration.
#[tokio::test]
async fn json_yaml_and_stix_are_one_sighting() {
    let h = harness("formats");
    let formats = [
        (
            "application/json",
            include_str!("../../../examples/formats/sighting.json"),
        ),
        (
            "application/yaml",
            include_str!("../../../examples/formats/sighting.yaml"),
        ),
        (
            "application/stix+json;version=2.1",
            include_str!("../../../examples/formats/sighting.stix.json"),
        ),
    ];
    let mut statuses = Vec::new();
    for (ct, body) in formats {
        let (code, r) = post_as(&h.app, ct, body).await;
        assert!(code.is_success(), "{ct}: {r}");
        statuses.push(r["receipts"][0]["status"].as_str().unwrap().to_string());
    }
    assert_eq!(statuses, ["created", "duplicate", "duplicate"]);
    let (code, _) = post_as(&h.app, "text/plain", formats[0].1).await;
    assert_eq!(code, StatusCode::UNSUPPORTED_MEDIA_TYPE);
    let (code, r) = post_as(&h.app, "application/yaml", "a: *nope\n").await;
    assert_eq!(code, StatusCode::UNPROCESSABLE_ENTITY, "{r}");
    assert!(h.sightings.query("SELECT count(*) FROM sightings").is_ok());
}

/// #160: every route of the router is in the OpenAPI document, with the
/// lowest status it needs.
#[tokio::test]
async fn every_route_is_in_the_openapi_document() {
    let h = harness("openapi");
    let (code, doc) = call(&h.app, "GET", "/v1/openapi.json", None, None).await;
    assert_eq!(code, StatusCode::OK);
    let source = include_str!("../src/api.rs");
    let mut routes = 0;
    for line in source.lines().map(str::trim) {
        let Some(rest) = line.strip_prefix(".route(\"") else {
            continue;
        };
        let (path, handlers) = rest.split_once('"').unwrap();
        let path = path.replace("{*", "{");
        for method in ["get", "post", "put", "patch", "delete"] {
            if !(handlers.contains(&format!(" {method}("))
                || handlers.contains(&format!(".{method}(")))
            {
                continue;
            }
            routes += 1;
            let op = &doc["paths"][&path][method];
            assert!(op.is_object(), "{method} {path} is not in api/openapi.yaml");
            assert!(
                op["x-min-status"].is_string(),
                "{method} {path}: x-min-status"
            );
        }
    }
    assert!(
        routes >= 16,
        "found {routes} routes: has the router's layout changed?"
    );
}

/// #160: records for machine clients, by status.
#[tokio::test]
async fn records_are_listed_by_status() {
    let h = harness("records");
    let mut ids = Vec::new();
    for (tok, ip) in [
        ("c", "198.51.100.1"),
        ("c", "198.51.100.2"),
        ("c", "198.51.100.3"),
        ("c2", "203.0.113.9"),
    ] {
        let s = sighting("energy", ip, "r1");
        ids.push(
            s["submission"]["sighting"]["sighting_id"]
                .as_str()
                .unwrap()
                .to_string(),
        );
        let (code, r) = call(&h.app, "POST", "/v1/sightings", Some(tok), Some(s)).await;
        assert_eq!(code, StatusCode::CREATED, "{r}");
    }
    let get = |uri: String, tok: &'static str| {
        let app = h.app.clone();
        async move { call(&app, "GET", &uri, Some(tok), None).await }
    };

    let (code, all) = get("/v1/sightings".into(), "p").await;
    assert_eq!(code, StatusCode::OK, "{all}");
    assert_eq!(all["sightings"].as_array().unwrap().len(), 4);
    assert!(all["next_cursor"].is_null());
    let first = &all["sightings"][0];
    assert_eq!(first["record"]["format"], "frank/1");
    assert!(first["record"]["evidence"].as_array().unwrap().len() == 2);
    assert!(
        !all.to_string().contains("identity-victim"),
        "no target identity: {all}"
    );

    let (_, page) = get("/v1/sightings?limit=3".into(), "p").await;
    assert_eq!(page["sightings"].as_array().unwrap().len(), 3);
    let cursor = page["next_cursor"].as_str().unwrap().to_string();
    let (_, rest) = get(format!("/v1/sightings?limit=3&cursor={cursor}"), "p").await;
    assert_eq!(rest["sightings"].as_array().unwrap().len(), 1);
    assert!(rest["next_cursor"].is_null());
    let mut seen: Vec<&Value> = page["sightings"].as_array().unwrap().iter().collect();
    seen.extend(rest["sightings"].as_array().unwrap());
    let mut listed: Vec<&str> = seen
        .iter()
        .map(|s| s["sighting_id"].as_str().unwrap())
        .collect();
    listed.sort_unstable();
    listed.dedup();
    assert_eq!(listed.len(), 4, "two pages, each sighting once");

    let (_, by_ioc) = get("/v1/sightings?ioc=domain:evil.example".into(), "p").await;
    assert_eq!(
        by_ioc["sightings"].as_array().unwrap().len(),
        4,
        "an IoC on seq 1"
    );
    let (_, by_ip) = get("/v1/sightings?ioc=ipv4:203.0.113.9".into(), "p").await;
    assert_eq!(by_ip["sightings"].as_array().unwrap().len(), 1);

    let n = |v: &Value| v["sightings"].as_array().map_or(0, Vec::len);
    let (_, water) = get("/v1/sightings?sector=water".into(), "p").await;
    assert_eq!(n(&water), 0, "Explore's filters: {water}");
    let (_, energy) = get(
        "/v1/sightings?sector=Energy&ioc_type=ipv4&rule=r1".into(),
        "p",
    )
    .await;
    assert_eq!(n(&energy), 4, "{energy}");
    let (_, newest) = get("/v1/sightings?order=desc&limit=2".into(), "p").await;
    let (_, oldest) = get("/v1/sightings?limit=4".into(), "p").await;
    assert_eq!(
        newest["sightings"][0], oldest["sightings"][3],
        "newest first"
    );
    let cursor = newest["next_cursor"].as_str().unwrap().to_string();
    let (_, older) = get(
        format!("/v1/sightings?order=desc&limit=2&cursor={cursor}"),
        "p",
    )
    .await;
    assert_eq!(
        older["sightings"][1], oldest["sightings"][0],
        "and pages backwards"
    );
    let (code, _) = get("/v1/sightings?org=x".into(), "p").await;
    assert_eq!(code, StatusCode::UNPROCESSABLE_ENTITY);

    let (code, _) = get("/v1/sightings".into(), "c").await;
    assert_eq!(code, StatusCode::FORBIDDEN, "a contributor lists its own");
    let (_, mine) = get("/v1/sightings?mine=true".into(), "c").await;
    assert_eq!(mine["sightings"].as_array().unwrap().len(), 3);
    let (code, _) = get("/v1/sightings".into(), "o").await;
    assert_eq!(code, StatusCode::FORBIDDEN);

    let (code, own) = get(format!("/v1/sightings/{}", ids[0]), "c").await;
    assert_eq!(code, StatusCode::OK, "{own}");
    assert_eq!(
        own["record"]["sighting_id"],
        format!("sighting--{}", ids[0])
    );
    let (code, _) = get(format!("/v1/sightings/{}", ids[3]), "c").await;
    assert_eq!(code, StatusCode::NOT_FOUND, "another's, below partner");
    let (code, _) = get(format!("/v1/sightings/{}", ids[3]), "p").await;
    assert_eq!(code, StatusCode::OK);
    let (code, _) = get("/v1/sightings/not-an-id".into(), "p").await;
    assert_eq!(code, StatusCode::UNPROCESSABLE_ENTITY);

    let (code, sum) = get("/v1/summary".into(), "c").await;
    assert_eq!(code, StatusCode::OK, "{sum}");
    assert_eq!(
        (&sum["sightings"], &sum["iocs"]),
        (&json!(3), &json!(6)),
        "{sum}"
    );
    assert_eq!(sum["network"]["sightings"], 4);
    assert!(sum["last_received"].is_string());
}
