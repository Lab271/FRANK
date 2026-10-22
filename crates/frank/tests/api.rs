//! The HTTP API end to end, over a temporary data directory.

use std::sync::Arc;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use frank::api::{rebuild_iocs, router, App};
use frank::auth::{hash, Tokens};
use frank::reporter::Reporters;
use frank::store::{Iocs, Sightings};
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
    let tokens = Tokens::parse(&format!(
        "{} observer obs\n{} contributor mdr\n{} contributor mdr2\n{} contributor mdr3\n{} partner lab\n",
        hash("o"),
        hash("c"),
        hash("c2"),
        hash("c3"),
        hash("p")
    ))
    .unwrap();
    let sightings = Sightings::open(&dir, None, now).unwrap();
    let iocs = Iocs::open(&dir).unwrap();
    let app = router(Arc::new(App {
        sightings: sightings.clone(),
        iocs: iocs.clone(),
        tokens,
        reporters: Reporters::open(&dir, now).unwrap(),
        now,
    }));
    Harness {
        app,
        sightings,
        iocs,
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

fn sighting(sector: &str, ip: &str, rule: &str) -> Value {
    json!({"submission": {
        "submitter": {"organisation_id": "identity-secret-org", "sector": "msp"},
        "hit_target": {"organisation_id": "identity-victim", "sector": sector},
        "sighting": {"timestamp": "2026-10-22T10:00:00Z", "severity": "high",
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
    assert!(body["sighting_ids"][0]
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
async fn files_hold_pseudonyms_not_tokens() {
    let h = harness("pseudonyms");
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
    for secret in [hash("c"), hash("c2"), "mdr2".to_string()] {
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
