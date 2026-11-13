//! #180: techniques counted on `sightings` with `UNNEST(techniques)`, a
//! `LIST<UTF8>` column since 0.21, and filtered with `list_contains`,
//! wherever the rows are: in the WAL, in a flushed hour file, in a merged
//! day, after reopening. Until 0.18 a `sighting_techniques` table gave
//! these counts; the expected values are what it gave on the same rows.

use std::sync::atomic::{AtomicI64, Ordering};

use db_core::engine::{Cell, QueryResult};
use frank::explore::{Dimension, BY_TECHNIQUE, FIRST_ROW, TECH_SET};
use frank::store::sightings::nanos;
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
/// A test id: `label`'s first 16 bytes, zero-padded.
fn test_id(label: &str) -> frank_core::SightingId {
    let mut b = [0; 16];
    b.iter_mut().zip(label.bytes()).for_each(|(b, c)| *b = c);
    frank_core::SightingId(b)
}

fn sighting(
    id: &str,
    ts: i64,
    techniques: &[&str],
    iocs: &[(IocType, &str)],
    reporter: &str,
    tlp: Tlp,
) -> Vec<SightingRow> {
    let row = |seq: u32, ioc: Option<&(IocType, &str)>| SightingRow {
        ts_ns: ts,
        sighting_id: test_id(id),
        rule_id: Some("sigma-rule-x".into()),
        techniques: techniques.iter().map(|t| (*t).to_string()).collect(),
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
        digest: (seq == 0).then_some(frank_core::Digest([1; 32])),
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
                    // `min(ts)`, `max(ts)` print as ISO text (db-core #1046).
                    Cell::Text(t) => nanos(c).map_or_else(|| t.clone(), |n| n.to_string()),
                    Cell::Int(n) => n.to_string(),
                    Cell::Null => "NULL".into(),
                    other => format!("{other:?}"),
                })
                .collect::<Vec<_>>()
                .join(" ")
        })
        .collect()
}

/// The form the server uses without an IoC filter: the first row of each
/// sighting, `count(*)` (exact because a sighting holds a technique once).
fn first_row() -> String {
    format!(
        "SELECT tech, count(*) AS n, count(DISTINCT reporter) AS r, min(ts), max(ts) \
         FROM {BY_TECHNIQUE} WHERE ts >= 0 AND tlp IN ('clear', 'green', 'amber') \
         AND {FIRST_ROW} AND {TECH_SET} GROUP BY tech ORDER BY tech"
    )
}

/// Over every row of a sighting (the form with an IoC filter), sightings
/// counted distinct.
fn all_rows() -> String {
    format!(
        "SELECT tech, count(DISTINCT sighting_id) AS n, count(DISTINCT reporter) AS r, min(ts), max(ts) \
         FROM {BY_TECHNIQUE} WHERE ts >= 0 AND tlp IN ('clear', 'green', 'amber') AND {TECH_SET} \
         GROUP BY tech ORDER BY tech"
    )
}

/// What the old table cannot answer (#180): techniques of the sightings
/// that carry an IPv4.
fn by_ioc_type() -> String {
    format!(
        "SELECT tech, count(DISTINCT sighting_id) AS n \
         FROM {BY_TECHNIQUE} WHERE ioc_type = 'ipv4' AND {TECH_SET} GROUP BY tech ORDER BY tech"
    )
}

/// Explore's technique filter, on the unnested value and on the list.
fn one_technique(unnested: bool) -> String {
    let from = if unnested { BY_TECHNIQUE } else { "sightings" };
    let cond = Dimension::Technique.condition("t1105", unnested).unwrap();
    format!("SELECT count(DISTINCT sighting_id), count(DISTINCT reporter) FROM {from} WHERE {cond}")
}

fn check(s: &Sightings, stage: &str, expected: &[&str]) {
    let first = rows(
        &s.query(&first_row())
            .unwrap_or_else(|e| panic!("{stage}: {e}")),
    );
    let all = rows(
        &s.query(&all_rows())
            .unwrap_or_else(|e| panic!("{stage}: {e}")),
    );
    assert_eq!(first, expected, "{stage}: first row, count(*)");
    assert_eq!(all, expected, "{stage}: all rows, count(DISTINCT)");
}

#[test]
fn techniques_are_counted_with_unnest_in_every_state() {
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
        &["T1059.001", "T1105"],
        &[ip("198.51.100.1"), dom("evil.example")],
        "r1",
        Tlp::Green,
    ));
    batch.extend(sighting(
        "s2",
        T0 + 1,
        &["T1105"],
        &[dom("evil.example")],
        "r2",
        Tlp::Clear,
    ));
    batch.extend(sighting(
        "s3",
        T0 + 2,
        &[],
        &[ip("198.51.100.2")],
        "r1",
        Tlp::Green,
    ));
    batch.extend(sighting(
        "s4",
        T0 + 3,
        &["T1059.001"],
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
        &["T1105", "T1566.002"],
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
        rows(&s.query(&by_ioc_type()).unwrap()),
        ["T1059.001 1", "T1105 2", "T1566.002 1"]
    );
    for unnested in [true, false] {
        assert_eq!(
            rows(&s.query(&one_technique(unnested)).unwrap()),
            ["3 3"],
            "unnested: {unnested}"
        );
    }
    s.close().unwrap();

    // Reopened: everything read back from files.
    let s = Sightings::open(&dir, None, now).unwrap();
    check(&s, "reopened", &hour2);
    s.close().unwrap();
    std::fs::remove_dir_all(&dir).ok();
}
