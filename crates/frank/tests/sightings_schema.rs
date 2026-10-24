//! The `sightings` table's schema across FRANK versions.

use db_core::storage::ingest::{
    Ack, IngestError, Layout, RecordValue, Table, TableOptions, TierOptions,
};
use db_core::storage::parquet::writer::{ColumnSpec, ColumnType};
use frank::store::sightings::NAME;
use frank::store::Sightings;

const NOW: i64 = 1_792_670_400_000_000_000;

fn now() -> i64 {
    NOW
}

/// The `sightings` columns of FRANK 0.12: no `digest` or `received`.
fn schema_0_12() -> Vec<ColumnSpec> {
    let text = |name| ColumnSpec::new(name, ColumnType::Utf8, true);
    vec![
        ColumnSpec::new("ts", ColumnType::TimestampNanos, false),
        ColumnSpec::new("sighting_id", ColumnType::Utf8, false),
        text("rule_id"),
        text("technique"),
        text("campaign"),
        text("ioc_type"),
        text("ioc_value"),
        text("reporter_sector"),
        text("target_sector"),
        text("target_size"),
        text("severity"),
        ColumnSpec::new("confidence", ColumnType::Int64, false),
        ColumnSpec::new("observations", ColumnType::Int64, false),
        ColumnSpec::new("tlp", ColumnType::Utf8, false),
        ColumnSpec::new("reporter", ColumnType::Utf8, false),
    ]
}

/// A temporary data directory holding a `sightings` table of `schema`
/// with one row of `extra` trailing values.
fn old_table(name: &str, schema: Vec<ColumnSpec>, extra: Vec<RecordValue>) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!("frank-schema-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    {
        let table = Table::open(
            dir.join(NAME),
            TableOptions {
                schema: Some(schema),
                layout: Layout::Tiered(TierOptions {
                    sort_key: vec!["rule_id".into(), "ioc_value".into()],
                    ..TierOptions::default()
                }),
                clock: now,
                ..TableOptions::default()
            },
        )
        .unwrap();
        let mut row = vec![RecordValue::Int(NOW), RecordValue::Str("s".into())];
        row.extend((0..9).map(|_| RecordValue::Null));
        row.extend([
            RecordValue::Int(50),
            RecordValue::Int(1),
            RecordValue::Str("TLP:GREEN".into()),
            RecordValue::Str("pseudonym".into()),
        ]);
        row.extend(extra);
        table.append_row(row, Ack::Durable).unwrap();
        table.close().unwrap();
    }
    dir
}

/// A table as FRANK 0.12 wrote it: no `digest` or `received` column and
/// pseudonymous reporters. Opening it must fail, not evolve it.
#[test]
fn a_0_12_table_is_refused() {
    let dir = old_table("0.12", schema_0_12(), vec![]);
    assert!(matches!(
        Sightings::open(&dir, None, now),
        Err(IngestError::SchemaMismatch)
    ));
}

/// A table as FRANK 0.13 and 0.14 wrote it gains `seq` and `detail`
/// (#160); its rows read NULL there and still count.
#[test]
fn a_0_14_table_gains_the_grain_columns() {
    let mut schema = schema_0_12();
    schema.push(ColumnSpec::new("digest", ColumnType::Utf8, true));
    schema.push(ColumnSpec::new(
        "received",
        ColumnType::TimestampNanos,
        true,
    ));
    let dir = old_table(
        "0.14",
        schema,
        vec![RecordValue::Str("d".into()), RecordValue::Int(NOW)],
    );
    let s = Sightings::open(&dir, None, now).unwrap();
    let r = s
        .query("SELECT count(*) FROM sightings WHERE (seq = 0 OR seq IS NULL) AND detail IS NULL")
        .unwrap();
    assert_eq!(frank::store::sightings::scalar(&r), 1);
    s.close().unwrap();
    std::fs::remove_dir_all(&dir).ok();
}
