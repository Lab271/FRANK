//! What the API asks of an S3 store, per endpoint, cold and warm (#284).
//!
//! 30 days of sightings, four hours a day, compacted into day files, the
//! last day's hours still in `live/`, in an in-memory bucket that counts
//! requests. Each endpoint runs first in a fresh process (an empty read
//! cache, as after a restart), then again. `cargo test --test s3_requests
//! -- --nocapture` prints the table that ADR-019 quotes. The numbers are
//! requests, not latency: against AWS each GET costs 20-100 ms before its
//! first byte (#228 measures that). The fake adds 1 ms to every GET, so
//! a cold call's wall time in ms is about the number of GETs that ran one
//! after another: times 20-100 for AWS.

#[path = "support/fake_s3.rs"]
mod fake_s3;

use std::sync::atomic::{AtomicI64, Ordering};
use std::sync::Arc;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use fake_s3::{Counts, FakeS3};
use frank::api::{router, App};
use frank::audit::Audit;
use frank::auth::hash;
use frank::store::participants::{self as parts, FILE};
use frank::store::{Iocs, Participants, Registry, Sightings};
use frank_core::{Digest, IocType, SightingId, SightingRow, Tier, Tlp};
use tower::ServiceExt;

const HOUR: i64 = 3_600 * 1_000_000_000;
const DAY: i64 = 24 * HOUR;
/// 2026-10-01 00:00 UTC, the first day.
const START: i64 = 1_790_812_800_000_000_000;
const DAYS: i64 = 30;

static CLOCK: AtomicI64 = AtomicI64::new(START);
fn now() -> i64 {
    CLOCK.load(Ordering::SeqCst)
}

fn row(day: i64, hour: i64, n: i64) -> SightingRow {
    let at = START + day * DAY + hour * HOUR + n;
    let id = u8::try_from((day * 64 + hour * 8 + n) % 251).unwrap_or(0);
    SightingRow {
        ts_ns: at - HOUR,
        sighting_id: SightingId([id; 16]),
        rule_id: Some(format!("rule-{}", n % 5)),
        techniques: vec![format!("T10{}", 50 + n % 7)],
        campaign: None,
        ioc_type: Some(IocType::Ipv4),
        ioc_value: Some(format!("10.0.{day}.{}", hour * 8 + n)),
        reporter_sector: Some("ENERGY".into()),
        target_sector: Some(
            ["ENERGY", "FINANCE", "HEALTH"][usize::try_from(n % 3).unwrap()].into(),
        ),
        target_size: None,
        severity: Some("high".into()),
        confidence: 80,
        observations: 1,
        tlp: Tlp::Green,
        reporter: format!("identity--{}", n % 4),
        digest: Some(Digest([id; 32])),
        received_ns: at,
        seq: 0,
        detail: Some("{}".into()),
    }
}

/// The table, written through a store on `s3`: 30 days, the last one's
/// hours not yet merged. Returns the data directory.
fn write_table(s3: &Arc<FakeS3>) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!("frank-s3-requests-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    CLOCK.store(START, Ordering::SeqCst);
    let s = Sightings::open_in(&dir, Some(s3.store(256 << 20)), Some(90), now).unwrap();
    for day in 0..DAYS {
        for hour in [8, 11, 14, 17] {
            CLOCK.store(START + day * DAY + hour * HOUR, Ordering::SeqCst);
            let rows: Vec<_> = (0..8).map(|n| row(day, hour, n)).collect();
            s.append(&rows).unwrap();
            CLOCK.store(START + day * DAY + (hour + 1) * HOUR + 1, Ordering::SeqCst);
            s.flush().unwrap();
        }
        if day + 1 < DAYS {
            CLOCK.store(START + (day + 1) * DAY + 1, Ordering::SeqCst);
            s.compact().unwrap();
        }
    }
    s.close().unwrap();
    dir
}

/// A server on the table, as a new process opens it: its own store client,
/// so an empty read cache.
fn server(dir: &std::path::Path, s3: &Arc<FakeS3>) -> (axum::Router, Sightings) {
    let sightings = Sightings::open_in(dir, Some(s3.store(256 << 20)), Some(90), now).unwrap();
    let app = router(Arc::new(App {
        data: dir.to_path_buf(),
        sightings: sightings.clone(),
        iocs: Iocs::open(dir).unwrap(),
        geo: frank::geo::Geo::open(dir, now()).unwrap(),
        lists: frank::lists::Lists::open(dir).unwrap(),
        participants: Participants::open(dir).unwrap(),
        registry: Registry::open(dir, &sightings).unwrap(),
        audit: Audit::open(dir).unwrap(),
        sso: None,
        submit_lock: std::sync::Mutex::new(()),
        now,
    }));
    (app, sightings)
}

async fn get(app: &axum::Router, uri: &str) {
    let req = Request::builder()
        .uri(uri)
        .header("authorization", "Bearer p")
        .body(Body::empty())
        .unwrap();
    let status = app.clone().oneshot(req).await.unwrap().status();
    assert_eq!(status, StatusCode::OK, "{uri}");
}

fn delta(a: Counts, b: Counts) -> (u64, u64) {
    (b.gets - a.gets, b.bytes - a.bytes)
}

#[tokio::test]
async fn requests_per_endpoint_cold_and_warm() {
    let s3 = FakeS3::new();
    let dir = write_table(&s3);
    let db = dir.join(FILE);
    parts::add_organisation(&db, "lab", Tier::Partner, "cyber_partner", None, None).unwrap();
    parts::add_user(&db, "lab", "lab", "human", None).unwrap();
    parts::add_token_hash(&db, "lab", &hash("p")).unwrap();
    CLOCK.store(START + (DAYS - 1) * DAY + 20 * HOUR, Ordering::SeqCst);

    let (_, s) = server(&dir, &s3);
    let files = s.files().unwrap();
    let stored: u64 = files.iter().map(|f| f.2).sum();
    s.close().unwrap();
    eprintln!("{} files, {stored} bytes in the bucket", files.len());
    // A GET's time to first byte, scaled down: wall time over it is the
    // number of GETs that ran one after another.
    let latency = std::time::Duration::from_millis(1);
    s3.set_latency(latency);
    eprintln!(
        "{:<28} {:>9} {:>10} {:>9} {:>11} {:>9}",
        "endpoint", "cold GETs", "cold bytes", "in flight", "GETs in row", "warm GETs"
    );

    let mut cold = Vec::new();
    for uri in [
        "/v1/statistics?days=30",
        "/v1/statistics?days=7",
        "/v1/explore?group=rule",
        "/v1/live?window=24h",
        "/v1/sightings?limit=50",
        "/v1/files",
    ] {
        let (app, s) = server(&dir, &s3);
        s3.reset_peak();
        let a = s3.counts();
        let t = std::time::Instant::now();
        get(&app, uri).await;
        let serial = t.elapsed().as_micros() / latency.as_micros();
        let b = s3.counts();
        get(&app, uri).await;
        let c = s3.counts();
        s.close().unwrap();
        let (gets, bytes) = delta(a, b);
        eprintln!(
            "{uri:<28} {gets:>9} {bytes:>10} {:>9} {serial:>11} {:>9}",
            b.max_in_flight,
            delta(b, c).0
        );
        assert_eq!(delta(b, c).0, 0, "{uri}: warm, the cache answers");
        assert!(bytes < stored, "{uri}: read {bytes} of {stored} bytes");
        assert_eq!(
            b.heads, a.heads,
            "{uri}: no HEAD, sizes are in the manifest"
        );
        cold.push(gets);
    }
    assert!(
        cold[1] < cold[0],
        "a 7-day window skips files (#283): {cold:?}"
    );
    assert_eq!(cold[5], 0, "listing the files fetches none");
    let _ = std::fs::remove_dir_all(&dir);
}
