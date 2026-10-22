//! The `sightings` table: a striped (tiered) db-core table of Parquet
//! files, one row per sighting × IoC (ADR-016). Hour files sorted by
//! `rule_id` go to `live/`, closed days merge into `archive/`, whole days
//! drop out after the retention period.

use std::path::Path;

use db_core::engine::{Cell, QueryResult};
use db_core::storage::ingest::{
    Ack, IngestError, Layout, PageBody, RecordValue, Table, TableOptions, TierOptions,
};
use db_core::storage::parquet::writer::{
    ColumnSpec, ColumnType, Compression, ParquetWriter, WriterOptions,
};
use frank_core::SightingRow;

/// The table's directory name, which is also its name in SQL.
pub const NAME: &str = "sightings";

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
    ]
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
        let options = TableOptions {
            schema: Some(schema()),
            layout: Layout::Tiered(TierOptions {
                sort_key: vec!["rule_id".into(), "ioc_value".into()],
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
        };
        Ok(Sightings {
            table: Table::open(data.join(NAME), options)?,
        })
    }

    /// Appends `rows` and returns once they are on disk (WAL fsync).
    pub fn append(&self, rows: &[SightingRow]) -> Result<(), IngestError> {
        let Some((last, head)) = rows.split_last() else {
            return Ok(());
        };
        for r in head {
            self.table.append_row(record(r), Ack::Memory)?;
        }
        self.table.append_row(record(last), Ack::Durable)?;
        Ok(())
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

/// A single-cell integer answer (`count(*)`), 0 for none.
pub fn scalar(result: &QueryResult) -> i64 {
    match result.rows.first().and_then(|r| r.first()) {
        Some(Cell::Int(n)) => *n,
        _ => 0,
    }
}
