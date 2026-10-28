//! #180 spike: techniques counted on `sightings` with
//! `UNNEST(string_split(technique, ','))` (db-core 0.192) give what the
//! `sighting_techniques` table gives, wherever the rows are: in the WAL, in
//! a flushed hour file, in a merged day, after reopening.

use std::sync::atomic::{AtomicI64, Ordering};

use db_core::engine::{Cell, QueryResult};
use frank::store::Sightings;
use frank_core::{IocType, SightingRow, Tlp};

/// 2026-10-22 12:00 UTC.
const T0: i64 = 1_792_670_400_000_000_000;
const HOUR: i64 = 3_600 * 1_000_000_000;
const DAY: i64 = 24 * HOUR;

static CLOCK: AtomicI64 = AtomicI64::new(T0);
fn now() -> i64 {
    CLOCK.load(Ordering::SeqCst)
}

/// The rows of one sighting: one per IoC (`seq` 0, 1, ...), or one without.
fn sighting(
    id: &str,
    ts: i64,
    techniques: Option<&str>,
    iocs: &[(IocType, &str)],
    reporter: &str,
    tlp: Tlp,
) -> Vec<SightingRow> {
    let row = |seq: u32, ioc: Option<&(IocType, &str)>| SightingRow {
        ts_ns: ts,
        sighting_id: id.into(),
        rule_id: Some("sigma-rule-x".into()),
        technique: techniques.map(Into::into),
        campaign: Some("c1".into()),
        ioc_type: ioc.map(|(t, _)| *t),
        ioc_value: ioc.map(|(_, v)| (*v).into()),
        reporter_sector: None,
        target_sector: Some("energy".into()),
        target_size: None,
        severity: Some("high".into()),
        confidence: 80,
        observations: 1,
        tlp,
        reporter: reporter.into(),
        digest: format!("d-{id}"),
        received_ns: ts,
        seq,
        detail: (seq == 0).then(|| "{}".into()),
    };
    if iocs.is_empty() {
        return vec![row(0, None)];
    }
    iocs.iter()
        .enumerate()
        .map(|(i, ioc)| row(u32::try_from(i).unwrap(), Some(ioc)))
        .collect()
}

fn rows(r: &QueryResult) -> Vec<String> {
    r.rows
        .iter()
        .map(|row| {
            row.iter()
                .map(|c| match c {
                    Cell::Text(t) => t.clone(),
                    Cell::Int(n) => n.to_string(),
                    Cell::Null => "NULL".into(),
                    other => format!("{other:?}"),
                })
                .collect::<Vec<_>>()
                .join(" ")
        })
        .collect()
}

/// Today's query on `sighting_techniques` (one row per sighting × technique).
const OLD: &str =
    "SELECT technique, count(*) AS n, count(DISTINCT reporter) AS r, min(ts), max(ts) \
     FROM sighting_techniques WHERE ts >= 0 AND tlp IN ('clear', 'green', 'amber') \
     GROUP BY technique ORDER BY technique";

/// The same on `sightings`: every row of a sighting carries its techniques,
/// so sightings are counted distinct.
const NEW: &str = "SELECT tech, count(DISTINCT sighting_id) AS n, count(DISTINCT reporter) AS r, min(ts), max(ts) \
     FROM sightings, UNNEST(string_split(technique, ',')) AS t(tech) \
     WHERE ts >= 0 AND tlp IN ('clear', 'green', 'amber') AND tech <> '' \
     GROUP BY tech ORDER BY tech";

/// What the old table cannot answer (#180): techniques of the sightings
/// that carry an IPv4.
const BY_IOC_TYPE: &str = "SELECT tech, count(DISTINCT sighting_id) AS n \
     FROM sightings, UNNEST(string_split(technique, ',')) AS t(tech) \
     WHERE ioc_type = 'ipv4' AND tech <> '' GROUP BY tech ORDER BY tech";

/// A filter on the unnested value (Explore's technique filter).
const ONE_TECHNIQUE: &str = "SELECT count(DISTINCT sighting_id), count(DISTINCT reporter) \
     FROM sightings, UNNEST(string_split(technique, ',')) AS t(tech) WHERE tech = 'T1105'";

fn check(s: &Sightings, stage: &str, expected: &[&str]) {
    let old = rows(&s.query_techniques(OLD).unwrap());
    let new = rows(&s.query(NEW).unwrap_or_else(|e| panic!("{stage}: {e}")));
    assert_eq!(new, expected, "{stage}: UNNEST on sightings");
    assert_eq!(old, new, "{stage}: sighting_techniques and UNNEST disagree");
}

#[test]
fn unnest_counts_techniques_like_the_techniques_table() {
    let dir = std::env::temp_dir().join(format!("frank-unnest-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let ip = |v| (IocType::Ipv4, v);
    let dom = |v| (IocType::Domain, v);

    // Hour 1: four sightings, one with two IoCs, one without techniques,
    // one AMBER+STRICT (not visible to the queries above).
    CLOCK.store(T0, Ordering::SeqCst);
    let s = Sightings::open(&dir, None, now).unwrap();
    let mut batch = Vec::new();
    batch.extend(sighting(
        "s1",
        T0,
        Some("T1059.001,T1105"),
        &[ip("198.51.100.1"), dom("evil.example")],
        "r1",
        Tlp::Green,
    ));
    batch.extend(sighting(
        "s2",
        T0 + 1,
        Some("T1105"),
        &[dom("evil.example")],
        "r2",
        Tlp::Clear,
    ));
    batch.extend(sighting(
        "s3",
        T0 + 2,
        None,
        &[ip("198.51.100.2")],
        "r1",
        Tlp::Green,
    ));
    batch.extend(sighting(
        "s4",
        T0 + 3,
        Some("T1059.001"),
        &[],
        "r3",
        Tlp::AmberStrict,
    ));
    s.append(&batch).unwrap();
    let hour1 = [
        "T1059.001 1 1 1792670400000000000 1792670400000000000",
        "T1105 2 2 1792670400000000000 1792670400000000001",
    ];
    check(&s, "all in the WAL", &hour1);

    // Hour 2: hour 1 is closed and flushed to a file; one more sighting in
    // the WAL.
    CLOCK.store(T0 + 2 * HOUR, Ordering::SeqCst);
    assert!(s.flush().unwrap() > 0, "hour 1 written");
    s.append(&sighting(
        "s5",
        T0 + 2 * HOUR,
        Some("T1105,T1566.002"),
        &[ip("203.0.113.9")],
        "r3",
        Tlp::Amber,
    ))
    .unwrap();
    let hour2 = [
        "T1059.001 1 1 1792670400000000000 1792670400000000000",
        "T1105 3 3 1792670400000000000 1792677600000000000",
        "T1566.002 1 1 1792677600000000000 1792677600000000000",
    ];
    check(&s, "hour file + WAL", &hour2);

    // Two days on: both hours flushed and the day merged into archive/.
    CLOCK.store(T0 + 2 * DAY, Ordering::SeqCst);
    s.flush().unwrap();
    assert!(s.compact().unwrap() > 0, "day merged");
    check(&s, "merged day", &hour2);

    assert_eq!(
        rows(&s.query(BY_IOC_TYPE).unwrap()),
        ["T1059.001 1", "T1105 2", "T1566.002 1"]
    );
    assert_eq!(rows(&s.query(ONE_TECHNIQUE).unwrap()), ["3 3"]);
    s.close().unwrap();

    // Reopened: everything read back from files.
    let s = Sightings::open(&dir, None, now).unwrap();
    check(&s, "reopened", &hour2);
    s.close().unwrap();
    std::fs::remove_dir_all(&dir).ok();
}
