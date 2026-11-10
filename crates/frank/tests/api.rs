//! The HTTP API end to end, over a temporary data directory.

mod support;

use std::sync::Arc;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use frank::api::{rebuild_iocs, router, App};
use frank::audit::Audit;
use frank::auth::{hash, uuid4, Role};
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
    harness_with(name, false)
}

/// With `geoip`, DB-IP test databases are in place before the server
/// starts (#191).
fn harness_with(name: &str, geoip: bool) -> Harness {
    harness_setup(name, |dir| {
        if geoip {
            support::mmdb::dbip(dir, 1_792_454_400);
        }
    })
}

/// `setup` prepares the data directory before the server opens it.
fn harness_setup(name: &str, setup: impl FnOnce(&std::path::Path)) -> Harness {
    let dir = std::env::temp_dir().join(format!("frank-api-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    setup(&dir);
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
    let lists = frank::lists::Lists::open(&dir).unwrap();
    lists.refresh(now());
    let app = router(Arc::new(App {
        data: dir.clone(),
        sightings: sightings.clone(),
        iocs: iocs.clone(),
        geo: frank::geo::Geo::open(&dir, now()).unwrap(),
        lists,
        participants: Participants::open(&dir).unwrap(),
        registry: registry.clone(),
        audit: Audit::open(&dir).unwrap(),
        sso: None,
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

/// The lookup's panels (#182): grouped like the rule page, under the
/// reporter threshold, and limited to one day on request.
#[tokio::test]
async fn lookup_panels_follow_explore_rules() {
    let h = harness("lookup-panels");
    explore_fixture(&h).await;
    let get = |tok: &'static str, extra: &'static str| {
        let app = h.app.clone();
        async move {
            let url = format!("/v1/iocs?type=domain&value=evil.example{extra}");
            call(&app, "GET", &url, Some(tok), None).await
        }
    };
    let panel_keys = |v: &Value, panel: &str| -> Vec<(String, i64)> {
        v["panels"][panel]
            .as_array()
            .unwrap()
            .iter()
            .map(|c| {
                (
                    c["key"].as_str().unwrap().to_string(),
                    c["count"].as_i64().unwrap(),
                )
            })
            .collect()
    };

    let (st, c) = get("c", "").await;
    assert_eq!(st, StatusCode::OK, "{c}");
    assert_eq!(
        panel_keys(&c, "rules"),
        [("r1".into(), 3)],
        "r2 has one reporter"
    );
    assert_eq!(panel_keys(&c, "sectors"), [("energy".into(), 3)]);
    assert_eq!(
        panel_keys(&c, "severities"),
        [("high".into(), 6)],
        "r2 rows lift it, three reporters"
    );

    let (_, p) = get("p", "").await;
    let mut rules = panel_keys(&p, "rules");
    rules.sort();
    assert_eq!(
        rules,
        [("r1".into(), 3), ("r2".into(), 3)],
        "partners see exact cells"
    );

    let (_, day) = get("p", "&day=2026-10-22").await;
    assert_eq!(panel_keys(&day, "sectors").len(), 2);
    let (_, other) = get("p", "&day=2026-10-23").await;
    assert!(panel_keys(&other, "rules").is_empty(), "{other}");
    assert_eq!(
        get("p", "&day=22-10-2026").await.0,
        StatusCode::UNPROCESSABLE_ENTITY
    );
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
        .query("SELECT DISTINCT digest, received FROM sightings WHERE digest IS NOT NULL")
        .unwrap();
    assert_eq!(r.rows.len(), 1);
    let stored = frank_core::unhex(receipt["digest"].as_str().unwrap()).unwrap();
    assert_eq!(
        r.rows[0][0],
        db_core::engine::Cell::Blob(stored),
        "the receipt's digest, stored as bytes on the first row (#200)"
    );
    let firsts = h
        .sightings
        .query("SELECT count(*) FROM sightings WHERE digest IS NOT NULL AND seq <> 0")
        .unwrap();
    assert_eq!(frank::store::sightings::scalar(&firsts), 0);
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
    // #180: techniques filtered by an IoC (a 422 until 0.18). The sighting
    // has two IPv4s, so by IoC type it has two matching rows: still once.
    for uri in [
        "/v1/explore?group=technique&ioc=ipv4:198.51.100.2",
        "/v1/explore?group=technique&ioc_type=ipv4",
    ] {
        let (code, t) = ex(uri).await;
        assert_eq!(code, StatusCode::OK, "{uri}: {t}");
        assert_eq!(keys(&t), ["T1059", "T1071.001"], "{uri}: {t}");
        assert!(
            t["rows"]
                .as_array()
                .unwrap()
                .iter()
                .all(|r| r["count"] == 1),
            "{uri}: {t}"
        );
    }
    let (_, t) = ex("/v1/explore?group=technique&ioc_type=url").await;
    assert_eq!(
        keys(&t),
        Vec::<String>::new(),
        "no URL in the sighting: {t}"
    );

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
    let source = [
        include_str!("../src/api.rs"),
        include_str!("../src/admin.rs"),
        include_str!("../src/sso.rs"),
    ]
    .concat();
    let mut routes = 0;
    let lines: Vec<&str> = source.lines().map(str::trim).collect();
    for (i, line) in lines.iter().enumerate() {
        // rustfmt splits a long `.route(` over lines.
        let joined;
        let line = if *line == ".route(" {
            joined = format!(".route({} {}", lines[i + 1], lines[i + 2]);
            joined.as_str()
        } else {
            line
        };
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
            assert!(
                op.is_object(),
                "{method} {path} is not in docs/openapi.yaml"
            );
            assert!(
                op["x-min-status"].is_string(),
                "{method} {path}: x-min-status"
            );
        }
    }
    assert!(
        routes >= 29,
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

/// Every sighting id of a listing, following `next_cursor` 500 at a time.
async fn every_page(app: &axum::Router, uri: &str, token: &str) -> Vec<String> {
    let mut ids = Vec::new();
    let mut cursor: Option<String> = None;
    loop {
        let u = match &cursor {
            Some(c) => format!("{uri}&limit=500&cursor={c}"),
            None => format!("{uri}&limit=500"),
        };
        let (code, page) = call(app, "GET", &u, Some(token), None).await;
        assert_eq!(code, StatusCode::OK, "{u}: {page}");
        ids.extend(page["sightings"].as_array().unwrap().iter().map(|s| {
            let id = s["sighting_id"].as_str().unwrap();
            id.trim_start_matches("sighting--").to_string()
        }));
        match page["next_cursor"].as_str() {
            Some(c) => cursor = Some(c.to_string()),
            None => return ids,
        }
    }
}

/// #201: an IoC filter matching more sightings than db-core's literal
/// `IN` list could take (about 1,000 overflowed the stack), paged by
/// cursor both ways: every sighting exactly once, in order.
#[tokio::test]
#[ignore = "slow: make test-slow"]
async fn an_ioc_filter_pages_through_thousands() {
    const N: usize = 2_100;
    let h = harness("ioc-volume");
    let mut want = Vec::new();
    for b in 0..N / 100 {
        let batch: Vec<Value> = (b * 100..(b + 1) * 100)
            .map(|n| sighting("energy", &format!("10.0.{}.{}", n / 256, n % 256), "r1"))
            .collect();
        want.extend(batch.iter().map(|s| {
            s["submission"]["sighting"]["sighting_id"]
                .as_str()
                .unwrap()
                .to_string()
        }));
        let (code, r) = call(
            &h.app,
            "POST",
            "/v1/sightings",
            Some("c"),
            Some(json!(batch)),
        )
        .await;
        assert_eq!(code, StatusCode::CREATED, "{r}");
    }
    want.sort_unstable();

    for (uri, token) in [
        ("/v1/sightings?ioc=domain:evil.example", "p"),
        ("/v1/sightings?ioc_type=ipv4", "p"),
        ("/v1/sightings?ioc_type=ipv4&sector=Energy&rule=r1", "p"),
        ("/v1/sightings?mine=true&ioc=domain:evil.example", "c"),
        ("/v1/sightings?ioc_type=domain&order=desc", "p"),
    ] {
        let listed = every_page(&h.app, uri, token).await;
        let mut sorted = listed.clone();
        sorted.sort_unstable();
        assert_eq!(sorted, want, "{uri}: every sighting, each once");
        // All share one timestamp, so the order is the id's (#160's cursor).
        if uri.contains("desc") {
            sorted.reverse();
        }
        assert_eq!(listed, sorted, "{uri}: in order");
    }
    let none = every_page(&h.app, "/v1/sightings?mine=true&ioc_type=ipv4", "c2").await;
    assert!(none.is_empty(), "another contributor's: {none:?}");
}

/// #175: `ops` (core) with superadmin `root` (token `s`); admins `amy` of
/// `mdr` (token `a`) and `ben` of `mdr2` (token `b`).
fn admins(h: &Harness) {
    parts::add_organisation(&h.db, "ops", Tier::Core, "cyber_partner", None, None).unwrap();
    for (org, user, role, token) in [
        ("ops", "root", Role::Superadmin, "s"),
        ("mdr", "amy", Role::Admin, "a"),
        ("mdr2", "ben", Role::Admin, "b"),
    ] {
        parts::add_user(&h.db, org, user, "human", Some(role)).unwrap();
        parts::add_token_hash(&h.db, user, &hash(token)).unwrap();
    }
}

fn names(v: &Value, key: &str) -> Vec<String> {
    let mut n: Vec<String> = v[key]
        .as_array()
        .unwrap()
        .iter()
        .map(|x| {
            x["name"]
                .as_str()
                .or(x["user"].as_str())
                .unwrap()
                .to_string()
        })
        .collect();
    n.sort();
    n
}

/// #175: an admin sees and changes its own organisation only; every
/// other organisation's object answers 404.
#[tokio::test]
async fn admins_manage_their_own_organisation_only() {
    let h = harness("admin-scope");
    admins(&h);
    let mdr = parts::organisation_id(&h.db, "mdr").unwrap();
    let mdr2 = parts::organisation_id(&h.db, "mdr2").unwrap();
    let app = &h.app;

    let (_, me) = call(app, "GET", "/v1/whoami", Some("a"), None).await;
    assert_eq!(me["role"], "admin");
    let (_, me) = call(app, "GET", "/v1/whoami", Some("c"), None).await;
    assert_eq!(me["role"], Value::Null);
    for uri in [
        "/v1/admin/users",
        "/v1/admin/tokens",
        "/v1/admin/organisations",
        "/v1/admin/audit",
    ] {
        assert_eq!(
            call(app, "GET", uri, Some("c"), None).await.0,
            StatusCode::FORBIDDEN,
            "{uri}"
        );
        assert_eq!(
            call(app, "GET", uri, None, None).await.0,
            StatusCode::FORBIDDEN,
            "{uri}"
        );
    }

    // Something about mdr2, done by its own admin.
    let (st, _) = call(
        app,
        "POST",
        "/v1/admin/users",
        Some("b"),
        Some(json!({"name": "bea"})),
    )
    .await;
    assert_eq!(st, StatusCode::CREATED);

    let (_, orgs) = call(app, "GET", "/v1/admin/organisations", Some("a"), None).await;
    assert_eq!(names(&orgs, "organisations"), ["mdr"]);
    let (_, users) = call(app, "GET", "/v1/admin/users", Some("a"), None).await;
    assert_eq!(names(&users, "users"), ["amy", "mdr"]);
    let (_, users) = call(
        app,
        "GET",
        &format!("/v1/admin/users?participant={mdr2}"),
        Some("a"),
        None,
    )
    .await;
    assert_eq!(users["users"], json!([]));
    let (_, tokens) = call(app, "GET", "/v1/admin/tokens", Some("a"), None).await;
    assert_eq!(names(&tokens, "tokens"), ["amy", "mdr"]);

    let ben = &hash("b")[..12];
    for (method, uri, body) in [
        (
            "POST",
            "/v1/admin/users".to_string(),
            Some(json!({"participant": mdr2, "name": "x"})),
        ),
        (
            "PATCH",
            "/v1/admin/users/ben".to_string(),
            Some(json!({"role": null})),
        ),
        (
            "PATCH",
            "/v1/admin/users/bea".to_string(),
            Some(json!({"role": "admin"})),
        ),
        (
            "POST",
            "/v1/admin/tokens".to_string(),
            Some(json!({"user": "mdr2"})),
        ),
        ("DELETE", format!("/v1/admin/tokens/{ben}"), None),
    ] {
        let (st, _) = call(app, method, &uri, Some("a"), body).await;
        assert_eq!(st, StatusCode::NOT_FOUND, "{method} {uri}");
    }
    assert_eq!(
        call(
            app,
            "POST",
            "/v1/admin/organisations",
            Some("a"),
            Some(json!({"name": "x", "status": "core"}))
        )
        .await
        .0,
        StatusCode::FORBIDDEN
    );
    assert_eq!(
        call(
            app,
            "PATCH",
            &format!("/v1/admin/organisations/{mdr}"),
            Some("a"),
            Some(json!({"status": "core"}))
        )
        .await
        .0,
        StatusCode::FORBIDDEN
    );

    // Within its own organisation.
    let bad = [
        (
            json!({"name": "feed", "kind": "machine", "role": "admin"}),
            StatusCode::UNPROCESSABLE_ENTITY,
        ),
        (
            json!({"name": "carl", "role": "superadmin"}),
            StatusCode::FORBIDDEN,
        ),
    ];
    for (body, want) in bad {
        assert_eq!(
            call(app, "POST", "/v1/admin/users", Some("a"), Some(body))
                .await
                .0,
            want
        );
    }
    let (st, carl) = call(
        app,
        "POST",
        "/v1/admin/users",
        Some("a"),
        Some(json!({"name": "carl"})),
    )
    .await;
    assert_eq!(st, StatusCode::CREATED);
    assert_eq!(carl["participant"], mdr);
    let (st, t) = call(
        app,
        "POST",
        "/v1/admin/tokens",
        Some("a"),
        Some(json!({"user": "carl"})),
    )
    .await;
    assert_eq!(st, StatusCode::CREATED);
    let token = t["token"].as_str().unwrap().to_string();
    let (_, who) = call(app, "GET", "/v1/whoami", Some(&token), None).await;
    assert_eq!(
        (who["user"].as_str(), who["tier"].as_str()),
        (Some("carl"), Some("contributor"))
    );

    // The audit: amy's own organisation only; a token never in plain.
    let (_, log) = call(app, "GET", "/v1/admin/audit", Some("a"), None).await;
    let actions: Vec<(&str, &str)> = log["lines"]
        .as_array()
        .unwrap()
        .iter()
        .map(|l| {
            (
                l["action"].as_str().unwrap(),
                l["user"].as_str().unwrap_or(""),
            )
        })
        .collect();
    assert_eq!(actions, [("token_issued", "carl"), ("user_added", "carl")]);
    let (_, all) = call(app, "GET", "/v1/admin/audit", Some("s"), None).await;
    assert_eq!(
        all["lines"].as_array().unwrap().len(),
        3,
        "the superadmin sees bea too"
    );
    let dir = h.db.parent().unwrap().join("audit");
    for f in std::fs::read_dir(dir).unwrap() {
        let text = std::fs::read_to_string(f.unwrap().path()).unwrap();
        assert!(!text.contains(&token), "a token in the audit log");
    }
}

/// #175: superadmins manage every organisation; the guards keep an
/// organisation, and the platform, from losing its last admin.
#[tokio::test]
async fn superadmins_and_the_guards() {
    let h = harness("admin-guards");
    admins(&h);
    let ops = parts::organisation_id(&h.db, "ops").unwrap();
    let app = &h.app;

    let (_, orgs) = call(app, "GET", "/v1/admin/organisations", Some("s"), None).await;
    assert_eq!(orgs["organisations"].as_array().unwrap().len(), 6);
    let (st, new) = call(
        app,
        "POST",
        "/v1/admin/organisations",
        Some("s"),
        Some(json!({"name": "newco", "status": "contributor", "sector": "energy"})),
    )
    .await;
    assert_eq!(st, StatusCode::CREATED);
    let newco = new["id"].as_str().unwrap();
    let (st, _) = call(
        app,
        "POST",
        "/v1/admin/users",
        Some("s"),
        Some(json!({"participant": newco, "name": "nina", "role": "admin"})),
    )
    .await;
    assert_eq!(st, StatusCode::CREATED);
    let (st, _) = call(
        app,
        "PATCH",
        &format!("/v1/admin/organisations/{newco}"),
        Some("s"),
        Some(json!({"status": "observer"})),
    )
    .await;
    assert_eq!(st, StatusCode::CONFLICT, "an observer has no admins");
    let (st, _) = call(
        app,
        "PATCH",
        &format!("/v1/admin/organisations/{newco}"),
        Some("s"),
        Some(json!({"status": "partner"})),
    )
    .await;
    assert_eq!(st, StatusCode::OK);
    let (st, _) = call(
        app,
        "PATCH",
        &format!("/v1/admin/organisations/{ops}"),
        Some("s"),
        Some(json!({"status": "partner"})),
    )
    .await;
    assert_eq!(st, StatusCode::CONFLICT, "a superadmin stays in core");
    assert_eq!(
        call(
            app,
            "PATCH",
            "/v1/admin/organisations/identity--nope",
            Some("s"),
            Some(json!({"status": "core"}))
        )
        .await
        .0,
        StatusCode::NOT_FOUND
    );

    // Last admin, last superadmin, own last token.
    let role = |r: Value| Some(json!({ "role": r }));
    assert_eq!(
        call(
            app,
            "PATCH",
            "/v1/admin/users/amy",
            Some("s"),
            role(Value::Null)
        )
        .await
        .0,
        StatusCode::CONFLICT
    );
    assert_eq!(
        call(
            app,
            "PATCH",
            "/v1/admin/users/amy",
            Some("a"),
            role(json!("superadmin"))
        )
        .await
        .0,
        StatusCode::FORBIDDEN
    );
    assert_eq!(
        call(
            app,
            "PATCH",
            "/v1/admin/users/root",
            Some("s"),
            role(json!("admin"))
        )
        .await
        .0,
        StatusCode::CONFLICT
    );
    let amy = &hash("a")[..12];
    assert_eq!(
        call(
            app,
            "DELETE",
            &format!("/v1/admin/tokens/{amy}"),
            Some("a"),
            None
        )
        .await
        .0,
        StatusCode::CONFLICT
    );

    // With a second token and a second admin, both go through.
    let (_, t) = call(
        app,
        "POST",
        "/v1/admin/tokens",
        Some("s"),
        Some(json!({"user": "amy"})),
    )
    .await;
    let second = t["token"].as_str().unwrap().to_string();
    assert_eq!(
        call(
            app,
            "DELETE",
            &format!("/v1/admin/tokens/{amy}"),
            Some("a"),
            None
        )
        .await
        .0,
        StatusCode::OK
    );
    assert_eq!(
        call(app, "GET", "/v1/whoami", Some("a"), None).await.0,
        StatusCode::UNAUTHORIZED
    );
    assert_eq!(
        call(
            app,
            "PATCH",
            "/v1/admin/users/mdr",
            Some(&second),
            role(json!("admin"))
        )
        .await
        .0,
        StatusCode::OK
    );
    assert_eq!(
        call(
            app,
            "PATCH",
            "/v1/admin/users/amy",
            Some(&second),
            role(Value::Null)
        )
        .await
        .0,
        StatusCode::OK
    );
    assert_eq!(
        call(app, "GET", "/v1/admin/users", Some(&second), None)
            .await
            .0,
        StatusCode::FORBIDDEN
    );
}

/// #175: a user is disabled first and removed after; a disabled user's
/// tokens stop working, and the guards count working admins only.
#[tokio::test]
async fn users_are_disabled_then_removed() {
    let h = harness("admin-remove");
    admins(&h);
    let app = &h.app;
    let post = |uri: String| async move { call(app, "POST", &uri, Some("a"), None).await.0 };

    // amy (admin of mdr) and the plain user mdr.
    assert_eq!(
        call(app, "DELETE", "/v1/admin/users/mdr", Some("a"), None)
            .await
            .0,
        StatusCode::CONFLICT,
        "disable first"
    );
    assert_eq!(
        post("/v1/admin/users/amy/disable".into()).await,
        StatusCode::CONFLICT,
        "not yourself"
    );
    assert_eq!(
        post("/v1/admin/users/ben/disable".into()).await,
        StatusCode::NOT_FOUND,
        "not mdr2's"
    );
    assert_eq!(
        call(app, "POST", "/v1/admin/users/root/disable", Some("a"), None)
            .await
            .0,
        StatusCode::NOT_FOUND,
        "not core's"
    );

    assert_eq!(
        post("/v1/admin/users/mdr/disable".into()).await,
        StatusCode::OK
    );
    assert_eq!(
        call(app, "GET", "/v1/whoami", Some("c"), None).await.0,
        StatusCode::UNAUTHORIZED,
        "its token stops"
    );
    let (st, _) = call(
        app,
        "POST",
        "/v1/admin/tokens",
        Some("a"),
        Some(json!({"user": "mdr"})),
    )
    .await;
    assert_eq!(st, StatusCode::CONFLICT, "no new tokens while disabled");
    let (_, users) = call(app, "GET", "/v1/admin/users", Some("a"), None).await;
    let mdr = users["users"]
        .as_array()
        .unwrap()
        .iter()
        .find(|u| u["name"] == "mdr")
        .unwrap()
        .clone();
    assert_eq!(mdr["disabled"], true);
    assert_eq!(
        post("/v1/admin/users/mdr/enable".into()).await,
        StatusCode::OK
    );
    assert_eq!(
        call(app, "GET", "/v1/whoami", Some("c"), None).await.0,
        StatusCode::OK,
        "and works again"
    );

    // A disabled admin does not count: with mdr an admin but disabled, amy
    // is still mdr's last working admin.
    let role = |r: Value| Some(json!({ "role": r }));
    assert_eq!(
        call(
            app,
            "PATCH",
            "/v1/admin/users/mdr",
            Some("a"),
            role(json!("admin"))
        )
        .await
        .0,
        StatusCode::OK
    );
    assert_eq!(
        post("/v1/admin/users/mdr/disable".into()).await,
        StatusCode::OK
    );
    assert_eq!(
        call(
            app,
            "PATCH",
            "/v1/admin/users/amy",
            Some("s"),
            role(Value::Null)
        )
        .await
        .0,
        StatusCode::CONFLICT
    );
    assert_eq!(
        call(app, "POST", "/v1/admin/users/amy/disable", Some("s"), None)
            .await
            .0,
        StatusCode::CONFLICT,
        "amy is mdr's last working admin"
    );

    // Removed: gone with its tokens; its name is free again.
    let (st, gone) = call(app, "DELETE", "/v1/admin/users/mdr", Some("a"), None).await;
    assert_eq!(st, StatusCode::OK);
    assert_eq!(gone["tokens"], json!([hash("c")[..12].to_string()]));
    let (_, users) = call(app, "GET", "/v1/admin/users", Some("a"), None).await;
    assert_eq!(names(&users, "users"), ["amy"]);
    let (_, log) = call(app, "GET", "/v1/admin/audit", Some("a"), None).await;
    let actions: Vec<&str> = log["lines"]
        .as_array()
        .unwrap()
        .iter()
        .map(|l| l["action"].as_str().unwrap())
        .collect();
    assert_eq!(
        actions,
        [
            "user_removed",
            "user_disabled",
            "role_set",
            "user_enabled",
            "user_disabled"
        ]
    );
    let (st, _) = call(
        app,
        "POST",
        "/v1/admin/users",
        Some("a"),
        Some(json!({"name": "mdr"})),
    )
    .await;
    assert_eq!(st, StatusCode::CREATED);

    // The last superadmin: only a superadmin may disable one, and not the last.
    parts::add_user(&h.db, "ops", "root2", "human", Some(Role::Superadmin)).unwrap();
    parts::add_token_hash(&h.db, "root2", &hash("s2")).unwrap();
    assert_eq!(
        call(
            app,
            "POST",
            "/v1/admin/users/root2/disable",
            Some("s"),
            None
        )
        .await
        .0,
        StatusCode::OK
    );
    assert_eq!(
        call(app, "POST", "/v1/admin/users/root/disable", Some("s"), None)
            .await
            .0,
        StatusCode::CONFLICT,
        "yourself"
    );
    assert_eq!(
        call(
            app,
            "PATCH",
            "/v1/admin/users/root",
            Some("s"),
            role(json!("admin"))
        )
        .await
        .0,
        StatusCode::CONFLICT,
        "the last working superadmin"
    );
}

/// #186: the IoCs of the sightings that arrived in the window, new or seen
/// before, and those several participants report.
#[tokio::test]
async fn live_shows_recent_iocs_new_and_converging() {
    let h = harness("live");
    // Seen 31 hours ago, stored 30 hours ago: before any window.
    h.sightings
        .append(&[frank_core::SightingRow {
            ts_ns: NOW - 31 * HOUR_NS,
            sighting_id: frank_core::SightingId([0x01; 16]),
            rule_id: Some("r0".into()),
            techniques: Vec::new(),
            campaign: None,
            ioc_type: Some(frank_core::IocType::Ipv4),
            ioc_value: Some("198.51.100.7".into()),
            reporter_sector: None,
            target_sector: None,
            target_size: None,
            severity: None,
            confidence: 50,
            observations: 1,
            tlp: frank_core::Tlp::Green,
            reporter: "identity--old".into(),
            digest: Some(frank_core::Digest([0x01; 32])),
            received_ns: NOW - 30 * HOUR_NS,
            seq: 0,
            detail: None,
        }])
        .unwrap();
    // Three participants report 198.51.100.7 and evil.example; one also
    // reports 203.0.113.9 alone.
    for tok in ["c", "c2", "c3"] {
        let s = sighting("energy", "198.51.100.7", "r1");
        assert_eq!(
            call(&h.app, "POST", "/v1/sightings", Some(tok), Some(s))
                .await
                .0,
            StatusCode::CREATED
        );
    }
    let s = sighting("energy", "203.0.113.9", "r2");
    assert_eq!(
        call(&h.app, "POST", "/v1/sightings", Some("c"), Some(s))
            .await
            .0,
        StatusCode::CREATED
    );

    let values = |v: &Value, list: &str| -> Vec<String> {
        v[list]
            .as_array()
            .unwrap()
            .iter()
            .map(|i| i["value"].as_str().unwrap().to_string())
            .collect()
    };
    let (st, p) = call(&h.app, "GET", "/v1/live?window=24h", Some("p"), None).await;
    assert_eq!(st, StatusCode::OK, "{p}");
    assert_eq!(
        (
            &p["sightings"],
            &p["participants"],
            &p["iocs"],
            &p["new_iocs"]
        ),
        (&json!(4), &json!(3), &json!(3), &json!(2)),
        "{p}"
    );
    let mut feed = values(&p, "feed");
    feed.sort();
    assert_eq!(feed, ["198.51.100.7", "203.0.113.9", "evil.example"]);
    let mut converging = values(&p, "converging");
    converging.sort();
    assert_eq!(converging, ["198.51.100.7", "evil.example"]);
    let ip = p["converging"]
        .as_array()
        .unwrap()
        .iter()
        .find(|i| i["value"] == "198.51.100.7")
        .unwrap();
    assert_eq!(
        (&ip["reporters"], &ip["seen_since"]),
        (&json!(3), &json!(NOW - 31 * HOUR_NS)),
        "{ip}"
    );
    let dom = p["feed"]
        .as_array()
        .unwrap()
        .iter()
        .find(|i| i["value"] == "evil.example")
        .unwrap();
    assert!(dom["seen_since"].is_null(), "new: {dom}");
    let buckets = p["buckets"].as_array().unwrap();
    assert_eq!(buckets.len(), 24);
    assert_eq!(
        buckets
            .iter()
            .map(|b| b["sightings"].as_i64().unwrap())
            .sum::<i64>(),
        4
    );

    // Below partner, an IoC one participant reports is left out; the
    // counters stay.
    let (_, c) = call(&h.app, "GET", "/v1/live?window=24h", Some("c"), None).await;
    let mut feed = values(&c, "feed");
    feed.sort();
    assert_eq!(feed, ["198.51.100.7", "evil.example"], "{c}");
    assert_eq!((&c["iocs"], &c["min_cell"]), (&json!(3), &json!(3)));

    assert_eq!(
        call(&h.app, "GET", "/v1/live", Some("o"), None).await.0,
        StatusCode::FORBIDDEN
    );
    assert_eq!(
        call(&h.app, "GET", "/v1/live?window=2h", Some("p"), None)
            .await
            .0,
        StatusCode::UNPROCESSABLE_ENTITY
    );
}

/// #191: IP addresses get their country and ASN, for lookups, the live
/// view and partners' download; without the databases everything else works.
#[tokio::test]
async fn ip_addresses_carry_country_and_asn() {
    let h = harness_with("geo", true);
    let (_, health) = call(&h.app, "GET", "/health", None, None).await;
    assert_eq!(health["geoip"]["status"], "ok", "{health}");
    for tok in ["c", "c2", "c3"] {
        let s = sighting("energy", "192.0.2.10", "r1");
        assert_eq!(
            call(&h.app, "POST", "/v1/sightings", Some(tok), Some(s))
                .await
                .0,
            StatusCode::CREATED
        );
    }
    let (_, ip) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=ipv4&value=192.0.2.10",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(
        (&ip["geo"]["country"], &ip["geo"]["asn"]),
        (&json!("NL"), &json!(64496)),
        "{ip}"
    );
    let (_, dom) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=domain&value=evil.example",
        Some("c"),
        None,
    )
    .await;
    assert!(dom["geo"].is_null(), "only addresses: {dom}");
    let (_, live) = call(&h.app, "GET", "/v1/live?window=24h", Some("p"), None).await;
    let item = live["feed"]
        .as_array()
        .unwrap()
        .iter()
        .find(|i| i["value"] == "192.0.2.10")
        .unwrap();
    assert_eq!(item["geo"]["as_org"], "Example Net", "{item}");

    let (_, files) = call(&h.app, "GET", "/v1/files", Some("p"), None).await;
    assert_eq!(
        (&files["ip_geo"]["path"], &files["ip_geo"]["rows"]),
        (&json!("geo/ip_geo.parquet"), &json!(1)),
        "{files}"
    );
    assert!(files["ip_geo"]["attribution"]
        .as_str()
        .unwrap()
        .contains("DB-IP"));
    let req = Request::builder()
        .uri("/v1/files/geo/ip_geo.parquet")
        .header("authorization", "Bearer p")
        .body(Body::empty())
        .unwrap();
    let resp = h.app.clone().oneshot(req).await.unwrap();
    assert_eq!(resp.status(), StatusCode::OK);
    let bytes = resp.into_body().collect().await.unwrap().to_bytes();
    assert_eq!(&bytes[..4], b"PAR1");
    assert!(
        bytes.windows(5).any(|w| w == b"DB-IP"),
        "attribution in the file's metadata"
    );
    for path in [
        "../geo.db",
        "../geoip/dbip-lite/dbip-asn-lite.mmdb",
        "geoip/dbip-lite/dbip-asn-lite.mmdb",
    ] {
        assert_eq!(
            call(&h.app, "GET", &format!("/v1/files/{path}"), Some("p"), None)
                .await
                .0,
            StatusCode::NOT_FOUND,
            "{path}"
        );
    }

    // Without the databases: health stays ok, nothing is looked up or listed.
    let h = harness("nogeo");
    let (st, health) = call(&h.app, "GET", "/health", None, None).await;
    assert_eq!(
        (st, &health["status"], &health["geoip"]["status"]),
        (StatusCode::OK, &json!("ok"), &json!("missing"))
    );
    let s = sighting("energy", "192.0.2.10", "r1");
    assert_eq!(
        call(&h.app, "POST", "/v1/sightings", Some("c"), Some(s))
            .await
            .0,
        StatusCode::CREATED
    );
    let (_, ip) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=ipv4&value=192.0.2.10",
        Some("c"),
        None,
    )
    .await;
    assert!(ip["geo"].is_null() && ip["known"] == true, "{ip}");
    let (_, files) = call(&h.app, "GET", "/v1/files", Some("p"), None).await;
    assert!(files["ip_geo"].is_null());
    assert_eq!(
        call(
            &h.app,
            "GET",
            "/v1/files/geo/ip_geo.parquet",
            Some("p"),
            None
        )
        .await
        .0,
        StatusCode::NOT_FOUND
    );
}

/// #192: IoCs a warning list marks as common infrastructure are shown,
/// marked, and kept out of the converging list and Explore's IoC ranking
/// unless asked for. Counts never change.
#[tokio::test]
async fn common_infrastructure_is_marked_not_dropped() {
    let h = harness_setup("warn", |dir| {
        let w = dir.join("lists/warning");
        std::fs::create_dir_all(&w).unwrap();
        std::fs::write(
            w.join("public-dns-v4.json"),
            r#"{"name": "List of known IPv4 public DNS resolvers", "type": "cidr", "list": ["8.8.8.8/32", "9.9.9.0/24"]}"#,
        )
        .unwrap();
        std::fs::write(w.join("local.txt"), "# ours\nexample.net\n").unwrap();
    });
    for tok in ["c", "c2", "c3"] {
        for ip in ["8.8.8.8", "192.0.2.50"] {
            let s = sighting("energy", ip, "r1");
            assert_eq!(
                call(&h.app, "POST", "/v1/sightings", Some(tok), Some(s))
                    .await
                    .0,
                StatusCode::CREATED
            );
        }
    }
    let values = |v: &Value, list: &str| -> Vec<String> {
        let mut out: Vec<String> = v[list]
            .as_array()
            .unwrap()
            .iter()
            .map(|i| i["value"].as_str().unwrap().to_string())
            .collect();
        out.sort();
        out
    };
    let (_, live) = call(&h.app, "GET", "/v1/live?window=24h", Some("p"), None).await;
    assert_eq!(
        values(&live, "converging"),
        ["192.0.2.50", "evil.example"],
        "{live}"
    );
    assert_eq!(
        values(&live, "feed"),
        ["192.0.2.50", "8.8.8.8", "evil.example"],
        "still shown"
    );
    let dns = live["feed"]
        .as_array()
        .unwrap()
        .iter()
        .find(|i| i["value"] == "8.8.8.8")
        .unwrap();
    assert_eq!(
        (
            &dns["common"],
            &dns["listed"][0]["list"],
            &dns["listed"][0]["kind"]
        ),
        (&json!(true), &json!("public-dns-v4"), &json!("warning")),
        "{dns}"
    );
    assert_eq!(live["sightings"], json!(6), "counts unchanged");
    let (_, all) = call(
        &h.app,
        "GET",
        "/v1/live?window=24h&common=include",
        Some("p"),
        None,
    )
    .await;
    assert_eq!(
        values(&all, "converging"),
        ["192.0.2.50", "8.8.8.8", "evil.example"]
    );

    let keys = |v: &Value| -> Vec<String> {
        let mut k: Vec<String> = v["rows"]
            .as_array()
            .unwrap()
            .iter()
            .map(|r| r["key"].as_str().unwrap().to_string())
            .collect();
        k.sort();
        k
    };
    let (_, ex) = call(&h.app, "GET", "/v1/explore?group=ioc", Some("p"), None).await;
    assert_eq!(
        keys(&ex),
        ["domain:evil.example", "ipv4:192.0.2.50"],
        "{ex}"
    );
    let (_, ex) = call(
        &h.app,
        "GET",
        "/v1/explore?group=ioc&common=include",
        Some("p"),
        None,
    )
    .await;
    assert_eq!(keys(&ex).len(), 3);
    assert_eq!(
        call(
            &h.app,
            "GET",
            "/v1/explore?group=ioc&common=maybe",
            Some("p"),
            None
        )
        .await
        .0,
        StatusCode::UNPROCESSABLE_ENTITY
    );

    let (_, ip) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=ipv4&value=8.8.8.8",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(
        ip["listed"][0]["source"], "MISP warninglists: List of known IPv4 public DNS resolvers",
        "{ip}"
    );
    let (_, sub) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=domain&value=evil.example",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(sub["listed"], json!([]), "{sub}");
    let (_, health) = call(&h.app, "GET", "/health", None, None).await;
    let lists = health["lists"].as_array().unwrap();
    assert_eq!(lists.len(), 2, "{health}");
}

/// #193: what outside sources (abuse.ch) list about an IoC is shown as
/// context, and Explore finds the IoCs no list has yet.
#[tokio::test]
async fn reference_lists_are_context_and_a_filter() {
    let h = harness_setup("refs", |dir| {
        let r = dir.join("lists/reference");
        std::fs::create_dir_all(&r).unwrap();
        std::fs::write(
            r.join("feodo_ipblocklist.csv"),
            "# Feodo Tracker\nfirst_seen_utc,dst_ip,dst_port,c2_status,last_online,malware\n2026-10-01 00:00:00,192.0.2.66,443,online,,QakBot\n",
        )
        .unwrap();
        std::fs::write(
            r.join("urlhaus.csv"),
            "# URLhaus\n\"1\",\"2026-10-20 08:00:00\",\"http://evil.example/x.sh\",\"online\",\"\",\"malware_download\",\"mirai\",\"https://urlhaus.abuse.ch/url/1/\",\"r\"\n",
        )
        .unwrap();
    });
    for ip in ["192.0.2.66", "192.0.2.67"] {
        let s = sighting("energy", ip, "r1");
        assert_eq!(
            call(&h.app, "POST", "/v1/sightings", Some("p"), Some(s))
                .await
                .0,
            StatusCode::CREATED
        );
    }
    let (_, ip) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=ipv4&value=192.0.2.66",
        Some("c"),
        None,
    )
    .await;
    let l = &ip["listed"][0];
    assert_eq!(
        (&l["kind"], &l["source"], &l["tags"]),
        (
            &json!("reference"),
            &json!("abuse.ch Feodo Tracker"),
            &json!("QakBot")
        ),
        "{ip}"
    );
    assert!(l["first_listed"].is_i64());
    let (_, url) = call(
        &h.app,
        "GET",
        "/v1/iocs?type=url&value=http://evil.example/x.sh",
        Some("c"),
        None,
    )
    .await;
    assert_eq!(
        (&url["known"], &url["listed"][0]["tags"]),
        (&json!(false), &json!("malware_download,mirai")),
        "a lookup says what the lists say, sighted or not: {url}"
    );

    let keys = |v: &Value| -> Vec<String> {
        let mut k: Vec<String> = v["rows"]
            .as_array()
            .unwrap()
            .iter()
            .map(|r| r["key"].as_str().unwrap().to_string())
            .collect();
        k.sort();
        k
    };
    let get = |uri: &'static str| {
        let app = h.app.clone();
        async move { call(&app, "GET", uri, Some("p"), None).await }
    };
    assert_eq!(
        keys(&get("/v1/explore?group=ioc&listed=any").await.1),
        ["ipv4:192.0.2.66"]
    );
    assert_eq!(
        keys(
            &get("/v1/explore?group=ioc&listed=feodo_ipblocklist")
                .await
                .1
        ),
        ["ipv4:192.0.2.66"]
    );
    assert_eq!(
        keys(&get("/v1/explore?group=ioc&listed=none").await.1),
        ["domain:evil.example", "ipv4:192.0.2.67"],
        "what partners see that nobody lists yet"
    );
    assert!(keys(&get("/v1/explore?group=ioc&listed=urlhaus").await.1).is_empty());
    assert_eq!(
        get("/v1/explore?group=rule&listed=any").await.0,
        StatusCode::UNPROCESSABLE_ENTITY
    );
    let (_, live) = get("/v1/live?window=24h").await;
    let item = live["feed"]
        .as_array()
        .unwrap()
        .iter()
        .find(|i| i["value"] == "192.0.2.66")
        .unwrap();
    assert_eq!(item["listed"][0]["list"], "feodo_ipblocklist", "{item}");
    assert_eq!(
        live["sightings"],
        json!(2),
        "references are never sightings"
    );
}

/// #195: the live view ranks the countries and networks of the window's
/// addresses, under the reporter threshold, without warning-listed ones.
#[tokio::test]
async fn live_ranks_countries_and_networks() {
    let h = harness_setup("places", |dir| {
        support::mmdb::dbip(dir, 1_792_454_400);
        let w = dir.join("lists/warning");
        std::fs::create_dir_all(&w).unwrap();
        std::fs::write(w.join("ours.txt"), "192.0.2.99\n").unwrap();
    });
    // In the test databases 192.0.2.0/24 is NL (AS64496), 2001:db8::/32 DE
    // (AS64497); 203.0.113.0/24 is in neither.
    let send = |tok: &'static str, t: &'static str, ip: &'static str| {
        let app = h.app.clone();
        async move {
            let s = json!({"submission": {
                "submitter": {"organisation_id": "identity-secret-org", "sector": "msp"},
                "hit_target": {"organisation_id": "identity-victim", "sector": "energy"},
                "sighting": {"sighting_id": uuid4().unwrap(), "timestamp": "2026-10-22T10:00:00Z",
                    "severity": "high", "sigma_detection": {"rule_id": "r1"},
                    "observables": {"network": [{"type": t, "value": ip}]}}}});
            let (st, _) = call(&app, "POST", "/v1/sightings", Some(tok), Some(s)).await;
            assert_eq!(st, StatusCode::CREATED, "{ip}");
        }
    };
    for tok in ["c", "c2", "c3"] {
        send(tok, "ipv4", "192.0.2.10").await;
        send(tok, "ipv4", "203.0.113.5").await;
        send(tok, "ipv4", "192.0.2.99").await;
    }
    for tok in ["c", "c2"] {
        send(tok, "ipv6", "2001:db8::5").await;
    }
    let places = |v: &Value| v["places"].clone();
    let tops = |v: &Value, k: &str, key: &str| -> Vec<(Value, i64, i64)> {
        v["places"][k]["top"]
            .as_array()
            .unwrap()
            .iter()
            .map(|c| {
                (
                    c[key].clone(),
                    c["iocs"].as_i64().unwrap(),
                    c["reporters"].as_i64().unwrap(),
                )
            })
            .collect()
    };

    let (_, live) = call(&h.app, "GET", "/v1/live?window=24h", Some("p"), None).await;
    assert_eq!(live["geoip"], "ok");
    assert_eq!(
        tops(&live, "countries", "country"),
        [(json!("NL"), 1, 3), (json!("DE"), 1, 2)],
        "partner: every country; the warning-listed address left out"
    );
    assert_eq!(
        tops(&live, "networks", "asn"),
        [(json!(64496), 1, 3), (json!(64497), 1, 2)]
    );
    assert_eq!(places(&live)["networks"]["top"][0]["as_org"], "Example Net");
    assert_eq!(places(&live)["unknown"], json!({"iocs": 1, "reporters": 3}));

    let (_, all) = call(
        &h.app,
        "GET",
        "/v1/live?window=24h&common=include",
        Some("p"),
        None,
    )
    .await;
    assert_eq!(
        tops(&all, "countries", "country")[0],
        (json!("NL"), 2, 3),
        "common=include: the warning-listed address counts"
    );

    let (_, below) = call(&h.app, "GET", "/v1/live?window=24h", Some("c"), None).await;
    assert_eq!(
        tops(&below, "countries", "country"),
        [(json!("NL"), 1, 3)],
        "below partner: DE has two reporters"
    );
    assert!(places(&below)["countries"]["other"].is_null(), "{below}");

    // Without DB-IP: said so, nothing ranked.
    let h = harness("noplaces");
    let (_, live) = call(&h.app, "GET", "/v1/live?window=24h", Some("p"), None).await;
    assert_eq!(live["geoip"], "missing");
    assert_eq!(places(&live)["countries"]["top"], json!([]));
}

/// #222: only a superadmin lists files, one directory at a time, inside
/// the data and participants directories; each listing is audited.
#[tokio::test]
async fn superadmins_list_files_inside_the_roots_only() {
    let h = harness("admin-files");
    admins(&h);
    let app = &h.app;
    for t in ["a", "c"] {
        let (st, _) = call(app, "GET", "/v1/admin/files", Some(t), None).await;
        assert_eq!(st, StatusCode::FORBIDDEN, "token {t}");
    }
    let (st, _) = call(app, "GET", "/v1/admin/files", None, None).await;
    assert_eq!(st, StatusCode::FORBIDDEN);

    let (st, roots) = call(app, "GET", "/v1/admin/files", Some("s"), None).await;
    assert_eq!(st, StatusCode::OK);
    assert_eq!(names(&roots, "entries"), ["data", "participants"]);

    let (st, top) = call(app, "GET", "/v1/admin/files?path=data", Some("s"), None).await;
    assert_eq!(st, StatusCode::OK);
    let n = names(&top, "entries");
    assert!(n.contains(&"audit".to_string()) && n.contains(&"participants.db".to_string()));
    let db = top["entries"]
        .as_array()
        .unwrap()
        .iter()
        .find(|e| e["name"] == "participants.db")
        .unwrap();
    assert_eq!(db["kind"], "file");
    assert!(db["size"].as_u64().unwrap() > 0);
    assert!(db.get("content").is_none());

    let (st, _) = call(
        app,
        "GET",
        "/v1/admin/files?path=data/audit",
        Some("s"),
        None,
    )
    .await;
    assert_eq!(st, StatusCode::OK);
    for bad in [
        "data/..",
        "data/../x",
        "/etc",
        "etc",
        "data/nope",
        "data/audit/..%2F..",
    ] {
        let (st, _) = call(
            app,
            "GET",
            &format!("/v1/admin/files?path={bad}"),
            Some("s"),
            None,
        )
        .await;
        assert!(st.is_client_error(), "{bad}: {st}");
    }

    // A symlink out of the root is refused, not followed.
    #[cfg(unix)]
    {
        let link = h._dir.0.join("out");
        std::os::unix::fs::symlink("/", &link).unwrap();
        let (st, _) = call(app, "GET", "/v1/admin/files?path=data/out", Some("s"), None).await;
        assert_eq!(st, StatusCode::FORBIDDEN);
        let (_, top) = call(app, "GET", "/v1/admin/files?path=data", Some("s"), None).await;
        let l = top["entries"]
            .as_array()
            .unwrap()
            .iter()
            .find(|e| e["name"] == "out")
            .unwrap();
        assert_eq!(l["kind"], "link");
    }

    let (_, log) = call(app, "GET", "/v1/admin/audit", Some("s"), None).await;
    assert!(log["lines"]
        .as_array()
        .unwrap()
        .iter()
        .any(|l| l["action"] == "files_listed" && l["path"] == "data"));
}
