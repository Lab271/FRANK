//! Accepted sightings survive a restart before their hour is flushed
//! (spec 020): the WAL holds them.

use frank::store::sightings::scalar;
use frank::store::Sightings;
use frank_core::{Sighting, SightingId};

const NOW: i64 = 1_792_670_400_000_000_000;

fn now() -> i64 {
    NOW
}

fn rows(ip: &str) -> Vec<frank_core::SightingRow> {
    let json = format!(
        r#"{{"sighting": {{"observables": {{"network": [{{"type": "ipv4", "value": "{ip}"}}]}}}}}}"#
    );
    let mut rows = Sighting::parse(&json, NOW)
        .unwrap()
        .rows(SightingId::default());
    for r in &mut rows {
        r.reporter = "identity--test".into();
        r.received_ns = NOW;
    }
    rows
}

#[test]
fn a_restart_in_the_middle_of_a_stream_loses_nothing() {
    let dir = std::env::temp_dir().join(format!("frank-restart-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let count = |s: &Sightings| scalar(&s.query("SELECT count(*) FROM sightings").unwrap());
    {
        let s = Sightings::open(&dir, None, now).unwrap();
        for i in 0..3 {
            s.append(&rows(&format!("10.9.0.{i}"))).unwrap();
        }
        assert_eq!(count(&s), 3);
        // Dropped without a flush: the hour is still open.
    }
    let s = Sightings::open(&dir, None, now).unwrap();
    assert_eq!(count(&s), 3, "the WAL brings back every accepted row");
    s.append(&rows("10.9.0.9")).unwrap();
    assert_eq!(count(&s), 4, "and the stream goes on");
    std::fs::remove_dir_all(&dir).ok();
}
