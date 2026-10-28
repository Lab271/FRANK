//! The `sightings` table: a striped (tiered) db-core table of Parquet
//! files, one row per sighting × IoC (ADR-016). Hour files sorted by
//! `rule_id` go to `live/`, closed days merge into `archive/`, whole days
//! drop out after the retention period.
//!
//! Techniques are ranked on this table too, with
//! `UNNEST(string_split(technique, ','))` (#180). Until 0.18 a second
//! table, `sighting_techniques/`, held one row per sighting × technique;
//! it is no longer written or read.

use std::path::Path;

use db_core::engine::{Cell, QueryResult};
use db_core::storage::ingest::{
    Ack, IngestError, Layout, Manifest, PageBody, RecordValue, Table, TableOptions, TierOptions,
};
use db_core::storage::parquet::writer::{
    ColumnSpec, ColumnType, Compression, ParquetWriter, WriterOptions,
};
use frank_core::SightingRow;

/// The table's directory name, which is also its name in SQL.
pub const NAME: &str = "sightings";
/// The directory of the technique table FRANK wrote until 0.18 (#180).
const OLD_TECHNIQUES: &str = "sighting_techniques";

fn schema() -> Vec<ColumnSpec> {
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
        // The registration (#159); NULL in rows stored before 0.13.
        text("digest"),
        ColumnSpec::new("received", ColumnType::TimestampNanos, true),
        // The grain (#160); NULL in rows stored before 0.15.
        ColumnSpec::new("seq", ColumnType::Int64, true),
        text("detail"),
    ]
}

fn record(r: &SightingRow) -> Vec<RecordValue> {
    let opt = |v: &Option<String>| v.clone().map_or(RecordValue::Null, RecordValue::Str);
    vec![
        RecordValue::Int(r.ts_ns),
        RecordValue::Str(r.sighting_id.clone()),
        opt(&r.rule_id),
        opt(&r.technique),
        opt(&r.campaign),
        r.ioc_type
            .map_or(RecordValue::Null, |t| RecordValue::Str(t.as_str().into())),
        opt(&r.ioc_value),
        opt(&r.reporter_sector),
        opt(&r.target_sector),
        opt(&r.target_size),
        opt(&r.severity),
        RecordValue::Int(i64::from(r.confidence)),
        RecordValue::Int(i64::from(r.observations)),
        RecordValue::Str(r.tlp.as_str().into()),
        RecordValue::Str(r.reporter.clone()),
        if r.digest.is_empty() {
            RecordValue::Null
        } else {
            RecordValue::Str(r.digest.clone())
        },
        if r.received_ns == 0 {
            RecordValue::Null
        } else {
            RecordValue::Int(r.received_ns)
        },
        RecordValue::Int(i64::from(r.seq)),
        opt(&r.detail),
    ]
}

fn options(
    schema: Vec<ColumnSpec>,
    sort_key: &[&str],
    retention_days: Option<u32>,
    clock: fn() -> i64,
) -> TableOptions {
    TableOptions {
        schema: Some(schema),
        layout: Layout::Tiered(TierOptions {
            sort_key: sort_key.iter().map(|k| (*k).to_string()).collect(),
            row_group_max_rows: 64 * 1024,
            retention_days,
            ..TierOptions::default()
        }),
        parquet: WriterOptions {
            compression: Compression::Zstd,
            ..WriterOptions::default()
        },
        clock,
        ..TableOptions::default()
    }
}

/// The shared table handle; cheap to clone, safe to share across threads.
#[derive(Clone)]
pub struct Sightings {
    table: Table,
}

impl Sightings {
    /// Opens (or creates) the table under `data`, keeping `retention_days`
    /// closed days in `archive/`. `clock` (ns since the epoch) decides
    /// which hours and days are closed.
    pub fn open(
        data: &Path,
        retention_days: Option<u32>,
        clock: fn() -> i64,
    ) -> Result<Sightings, IngestError> {
        // db-core adds trailing nullable columns to a stored schema (#740),
        // which would take a 0.12 table (no `digest`, pseudonymous
        // reporters) as it is. Refuse it instead.
        let stored = Manifest::read(&data.join(NAME))
            .map_err(|e| IngestError::Corrupt(e.to_string()))?
            .and_then(|m| m.schema);
        if stored.is_some_and(|s| !s.iter().any(|c| c.name == "digest")) {
            return Err(IngestError::SchemaMismatch);
        }
        if data.join(OLD_TECHNIQUES).exists() {
            tracing::info!(
                "{} is no longer used (#180) and can be deleted",
                data.join(OLD_TECHNIQUES).display()
            );
        }
        let sightings = options(schema(), &["rule_id", "ioc_value"], retention_days, clock);
        Ok(Sightings {
            table: Table::open(data.join(NAME), sightings)?,
        })
    }

    /// Appends `rows` and returns once they are on disk (WAL fsync).
    pub fn append(&self, rows: &[SightingRow]) -> Result<(), IngestError> {
        append(&self.table, rows.iter().map(record).collect())
    }

    /// Runs one `SELECT` over everything appended so far (Parquet files,
    /// sealed pages and the WAL head).
    pub fn query(&self, sql: &str) -> Result<QueryResult, String> {
        self.table.query(sql).map_err(|e| e.to_string())
    }

    /// Writes closed hours to `live/`.
    pub fn flush(&self) -> Result<usize, IngestError> {
        Ok(self.table.flush()?.len())
    }

    /// Merges closed days into `archive/` and applies retention.
    pub fn compact(&self) -> Result<usize, IngestError> {
        Ok(self.table.compact()?.len())
    }

    /// The Parquet files the table lists now: path relative to the table
    /// directory, rows, bytes.
    pub fn files(&self) -> Result<Vec<(String, u64, u64)>, IngestError> {
        let snap = self.table.snapshot()?;
        Ok(snap
            .manifest()
            .files
            .iter()
            .map(|f| (f.path.clone(), f.rows, f.bytes))
            .collect())
    }

    /// Rows not yet in a file: the open hour, plus any closed hour the
    /// next flush has not written yet.
    pub fn open_rows(&self) -> Result<u64, IngestError> {
        let snap = self.table.snapshot()?;
        Ok(snap.pages().iter().map(|p| p.len() as u64).sum())
    }

    /// The rows not yet in a file as one Parquet file, written now from the
    /// table's in-memory pages. An hour file is only written once the hour
    /// closes (db-core ADR 0028); this lets readers see the open hour too.
    pub fn open_rows_parquet(&self) -> Result<Vec<u8>, String> {
        let snap = self.table.snapshot().map_err(|e| e.to_string())?;
        let mut w = ParquetWriter::new(
            Vec::new(),
            schema(),
            WriterOptions {
                compression: Compression::Zstd,
                ..WriterOptions::default()
            },
        )
        .map_err(|e| e.to_string())?;
        for page in snap.pages() {
            if let PageBody::Rows(rows) = &page.body {
                if !rows.is_empty() {
                    w.write_columns(rows.columns().to_vec())
                        .map_err(|e| e.to_string())?;
                }
            }
        }
        w.finish()
            .map(|(bytes, _)| bytes)
            .map_err(|e| e.to_string())
    }

    /// The table directory.
    pub fn dir(&self) -> &Path {
        self.table.dir()
    }

    pub fn close(&self) -> Result<(), IngestError> {
        self.table.close()
    }
}

/// Appends `records`, durable once the last one is.
fn append(table: &Table, records: Vec<Vec<RecordValue>>) -> Result<(), IngestError> {
    let n = records.len();
    for (i, r) in records.into_iter().enumerate() {
        let ack = if i + 1 == n {
            Ack::Durable
        } else {
            Ack::Memory
        };
        table.append_row(r, ack)?;
    }
    Ok(())
}

/// A single-cell integer answer (`count(*)`), 0 for none.
pub fn scalar(result: &QueryResult) -> i64 {
    match result.rows.first().and_then(|r| r.first()) {
        Some(Cell::Int(n)) => *n,
        _ => 0,
    }
}
