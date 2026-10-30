//! #191: country and ASN of IP addresses from DB-IP Lite, and FRANK working
//! on without them.

mod support;

use frank::geo::Geo;
use frank::store::Sightings;
use frank_core::{IocType, SightingRow, Tlp};
use support::mmdb;

const NOW: i64 = 1_792_670_400_000_000_000;
const MINUTE: i64 = 60 * 1_000_000_000;
/// 2026-10-20, as the databases give it: seconds.
const BUILD: u64 = 1_792_454_400;

fn now() -> i64 {
    NOW
}

struct Dir(std::path::PathBuf);
impl Drop for Dir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
fn dir(name: &str) -> Dir {
    let d = std::env::temp_dir().join(format!("frank-geo-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    Dir(d)
}

/// A test id: `label`'s first 16 bytes, zero-padded.
fn test_id(label: &str) -> frank_core::SightingId {
    let mut b = [0; 16];
    b.iter_mut().zip(label.bytes()).for_each(|(b, c)| *b = c);
    frank_core::SightingId(b)
}

fn row(ip: &str, t: IocType) -> SightingRow {
    SightingRow {
        ts_ns: NOW,
        sighting_id: test_id(ip),
        rule_id: None,
        techniques: Vec::new(),
        campaign: None,
        ioc_type: Some(t),
        ioc_value: Some(ip.into()),
        reporter_sector: None,
        target_sector: None,
        target_size: None,
        severity: None,
        confidence: 50,
        observations: 1,
        tlp: Tlp::Green,
        reporter: "identity--a".into(),
        digest: Some(frank_core::Digest([1; 32])),
        received_ns: NOW,
        seq: 0,
        detail: None,
    }
}

#[test]
fn without_databases_nothing_is_looked_up_and_nothing_fails() {
    let d = dir("missing");
    let g = Geo::open(&d.0, NOW).unwrap();
    assert_eq!(g.status()["status"], "missing");
    assert!(g.lookup("192.0.2.1".parse().unwrap(), NOW).is_none());
    g.fill(&[row("192.0.2.1", IocType::Ipv4)], NOW);
    assert!(g.db().all().unwrap().is_empty(), "not looked up: no row");
}

#[test]
fn addresses_get_country_and_asn_unknown_ones_zz_and_zero() {
    let d = dir("lookup");
    mmdb::dbip(&d.0, BUILD);
    let g = Geo::open(&d.0, NOW).unwrap();
    assert_eq!(
        g.status(),
        serde_json::json!({ "status": "ok", "build": "2026-10-20" })
    );
    let a = g.lookup("192.0.2.77".parse().unwrap(), NOW).unwrap();
    assert_eq!(
        (a.country.as_str(), a.asn, a.as_org.as_deref()),
        ("NL", 64496, Some("Example Net"))
    );
    let b = g.lookup("2001:db8::5".parse().unwrap(), NOW).unwrap();
    assert_eq!((b.country.as_str(), b.asn), ("DE", 64497));
    let c = g.lookup("203.0.113.5".parse().unwrap(), NOW).unwrap();
    assert_eq!(
        (c.country.as_str(), c.asn, c.as_org),
        ("ZZ", 0, None),
        "looked up, nothing found"
    );

    g.fill(
        &[
            row("192.0.2.77", IocType::Ipv4),
            row("evil.example", IocType::Domain),
            row("203.0.113.5", IocType::Ipv4),
        ],
        NOW,
    );
    let all = g.db().all().unwrap();
    assert_eq!(
        all.iter().map(|g| g.ip.as_str()).collect::<Vec<_>>(),
        ["192.0.2.77", "203.0.113.5"]
    );
}

#[test]
fn a_corrupt_database_counts_as_missing() {
    let d = dir("corrupt");
    mmdb::dbip(&d.0, BUILD);
    let f = d.0.join("geoip/dbip-lite/dbip-country-lite.mmdb");
    let bytes = std::fs::read(&f).unwrap();
    std::fs::write(&f, &bytes[..bytes.len() / 3]).unwrap();
    std::fs::remove_file(d.0.join("geoip/dbip-lite/dbip-asn-lite.mmdb")).unwrap();
    let g = Geo::open(&d.0, NOW).unwrap();
    assert_eq!(g.status()["status"], "missing");
    assert!(g.lookup("192.0.2.1".parse().unwrap(), NOW).is_none());
}

#[test]
fn databases_that_appear_later_are_picked_up_within_a_minute() {
    let d = dir("later");
    let g = Geo::open(&d.0, NOW).unwrap();
    mmdb::dbip(&d.0, BUILD);
    g.refresh(NOW + MINUTE / 2);
    assert_eq!(
        g.status()["status"],
        "missing",
        "checked at most once a minute"
    );
    g.refresh(NOW + MINUTE);
    assert_eq!(g.status()["status"], "ok");
}

#[test]
fn backfill_looks_up_every_address_once_per_build() {
    let d = dir("backfill");
    let s = Sightings::open(&d.0, None, now).unwrap();
    s.append(&[
        row("192.0.2.1", IocType::Ipv4),
        row("2001:db8::1", IocType::Ipv6),
        row("evil.example", IocType::Domain),
    ])
    .unwrap();
    let g = Geo::open(&d.0, NOW).unwrap();
    assert_eq!(
        g.backfill(&s, NOW).unwrap(),
        0,
        "no databases: nothing to do"
    );

    mmdb::dbip(&d.0, BUILD);
    g.refresh(NOW + MINUTE);
    assert_eq!(g.backfill(&s, NOW).unwrap(), 2);
    assert_eq!(g.backfill(&s, NOW).unwrap(), 0, "once per build");
    let got = g.answers(vec!["192.0.2.1".into(), "2001:db8::1".into()]);
    assert_eq!(
        (
            got["192.0.2.1"].country.as_str(),
            got["2001:db8::1"].country.as_str()
        ),
        ("NL", "DE")
    );

    // A new build: every address again.
    std::thread::sleep(std::time::Duration::from_millis(1100));
    mmdb::dbip(&d.0, BUILD + 86_400);
    g.refresh(NOW + 2 * MINUTE);
    assert_eq!(g.backfill(&s, NOW).unwrap(), 2);
    s.close().unwrap();
}

#[test]
fn every_record_size_reads() {
    let d = dir("sizes");
    for size in [24, 28, 32] {
        let path = d.0.join(format!("c{size}.mmdb"));
        mmdb::write_with(
            &path,
            "GeoLite2-Country",
            vec![
                ("192.0.2.0/24", mmdb::country("NL")),
                ("2001:db8::/32", mmdb::country("DE")),
            ],
            BUILD,
            size,
        );
        let db = frank::mmdb::Mmdb::open(&path).unwrap();
        let iso = |ip: &str| {
            db.lookup(ip.parse().unwrap()).unwrap().and_then(|v| {
                v.get(&["country", "iso_code"])
                    .and_then(|c| c.as_str().map(str::to_string))
            })
        };
        assert_eq!(iso("192.0.2.200").as_deref(), Some("NL"), "{size}");
        assert_eq!(iso("2001:db8:1::9").as_deref(), Some("DE"), "{size}");
        assert_eq!(iso("198.51.100.1"), None, "{size}");
        assert_eq!(
            (db.build_epoch, db.database_type.as_str()),
            (BUILD, "GeoLite2-Country")
        );
    }
}
