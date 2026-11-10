//! The `iocs` row table across transactions and reopen.

use frank::store::Iocs;
use frank_core::{Ioc, IocType, Sighting, Tlp};

const NOW: i64 = 1_792_670_400_000_000_000;

fn rows(ip: &str) -> Vec<frank_core::SightingRow> {
    let json = format!(
        r#"{{"sighting": {{"observables": {{"network": [{{"type": "ipv4", "value": "{ip}"}}]}}}}}}"#
    );
    Sighting::parse(&json, NOW)
        .unwrap()
        .rows(frank_core::SightingId::default())
}

#[test]
fn every_transaction_is_kept() {
    let dir = std::env::temp_dir().join(format!("frank-iocs-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let ip = |v: &str| Ioc::new(IocType::Ipv4, v).unwrap();
    {
        let iocs = Iocs::open(&dir).unwrap();
        for i in 0..5 {
            iocs.record(&rows(&format!("10.0.0.{i}"))).unwrap();
        }
        assert_eq!(iocs.count(&Tlp::SHARED).unwrap(), 5, "same handle");
        for i in 0..5 {
            assert_eq!(
                iocs.lookup(&ip(&format!("10.0.0.{i}")), &Tlp::SHARED)
                    .unwrap()
                    .len(),
                1,
                "10.0.0.{i}"
            );
        }
    }
    let iocs = Iocs::open(&dir).unwrap();
    assert_eq!(iocs.count(&Tlp::SHARED).unwrap(), 5, "after reopen");
    iocs.record(&rows("10.0.0.9")).unwrap();
    assert_eq!(iocs.count(&Tlp::SHARED).unwrap(), 6);
    std::fs::remove_dir_all(&dir).ok();
}

/// A sighting dated 40 days back that arrives today is kept as long as its
/// rows: the IoC's day is the arrival day, the clock the sightings table's
/// retention uses (#257). Days that arrived before the cut are dropped.
#[test]
fn retention_follows_arrival_not_the_sightings_own_time() {
    const DAY: i64 = 86_400_000_000_000;
    let dir = std::env::temp_dir().join(format!("frank-iocs-arrival-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let iocs = Iocs::open(&dir).unwrap();
    let at = |ip: &str, ts: i64, received: i64| {
        let mut r = rows(ip);
        for row in &mut r {
            row.ts_ns = ts;
            row.received_ns = received;
        }
        r
    };
    iocs.record(&at("10.0.1.1", NOW - 40 * DAY, NOW)).unwrap(); // back-dated, arrived today
    iocs.record(&at("10.0.1.2", NOW - 40 * DAY, NOW - 40 * DAY))
        .unwrap(); // arrived 40 days ago
    iocs.retain_from(NOW.div_euclid(DAY) - 30).unwrap();
    let ip = |v: &str| Ioc::new(IocType::Ipv4, v).unwrap();
    let kept = iocs.lookup(&ip("10.0.1.1"), &Tlp::SHARED).unwrap();
    assert_eq!(kept.len(), 1, "a back-dated arrival survives retention");
    assert_eq!(
        kept[0].first_ts,
        NOW - 40 * DAY,
        "first_ts is the sighting's own time"
    );
    assert!(
        iocs.lookup(&ip("10.0.1.2"), &Tlp::SHARED)
            .unwrap()
            .is_empty(),
        "an old arrival is dropped"
    );
    std::fs::remove_dir_all(&dir).ok();
}
