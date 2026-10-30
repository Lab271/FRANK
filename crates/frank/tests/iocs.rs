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
