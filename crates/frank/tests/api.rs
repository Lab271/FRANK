//! The HTTP API end to end, over a temporary data directory.

use std::sync::Arc;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use frank::api::{rebuild_iocs, router, App};
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
        parts::add_user(&db, name, name, "human").unwrap();
        parts::add_token_hash(&db, name, &hash(token)).unwrap();
    }
    let sightings = Sightings::open(&dir, None, now).unwrap();
    let iocs = Iocs::open(&dir).unwrap();
    let app = router(Arc::new(App {
        sightings: sightings.clone(),
        iocs: iocs.clone(),
        participants: Participants::open(&dir).unwrap(),
        registry: Registry::open(&dir).unwrap(),
        submit_lock: std::sync::Mutex::new(()),
        now,
    }));
    Harness {
        app,
        sightings,
        iocs,
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
        json!([{"key": "energy", "count": 6, "reporters": 3}]),
        "water has 6 rows but one reporter, under the k threshold"
    );
    assert!(obs.get("top_rules").is_none());

    let (_, contrib) = call(&h.app, "GET", "/v1/statistics", Some("c"), None).await;
    assert_eq!(
        contrib["top_rules"],
        json!([{"key": "r1", "count": 6, "reporters": 3}])
    );

    let (_, partner) = call(&h.app, "GET", "/v1/statistics", Some("p"), None).await;
    assert_eq!(
        partner["by_target_sector"].as_array().unwrap().len(),
        2,
        "partners see exact cells"
    );
    assert_eq!(
        partner["top_rules"][1],
        json!({"key": "r2", "count": 6, "reporters": 1})
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
        (Some(6), Some(3))
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
        (Some(true), Some(6), Some(3))
    );
    assert_eq!(r1["sectors"][0]["key"], "energy");
    let trend = r1["trend"].as_array().unwrap();
    assert_eq!(trend.len(), 30);
    assert_eq!(
        trend.iter().map(|d| d[1].as_i64().unwrap()).sum::<i64>(),
        6,
        "every row is in the trend"
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
    parts::add_user(&h.db, "mdr", "mdr-feed", "machine").unwrap();
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
