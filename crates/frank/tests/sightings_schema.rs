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

/// A table as FRANK 0.12 wrote it: no `digest` or `received` column and
/// pseudonymous reporters. Opening it under 0.13 must fail, not evolve it.
#[test]
fn a_0_12_table_is_refused() {
    let dir = std::env::temp_dir().join(format!("frank-schema-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let text = |name| ColumnSpec::new(name, ColumnType::Utf8, true);
    let schema = vec![
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
    ];
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
        table.append_row(row, Ack::Durable).unwrap();
        table.close().unwrap();
    }
    assert!(matches!(
        Sightings::open(&dir, None, now),
        Err(IngestError::SchemaMismatch)
    ));
}
