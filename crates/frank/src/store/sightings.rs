//! The `sightings` table: a striped (tiered) db-core table of Parquet
//! files, one row per sighting × IoC (ADR-016). Hour files sorted by
//! `rule_id` go to `live/`, closed days merge into `archive/`, whole days
//! drop out after the retention period.
//!
//! Techniques are ranked on this table too, with `UNNEST(techniques)`, a
//! `LIST<UTF8>` column (0.21). Until 0.18 a second table,
//! `sighting_techniques/`, held one row per sighting × technique; from
//! 0.19 to 0.20 they were split at query time from a comma-separated
//! `technique` string (#180), which the list replaces.

use std::path::Path;
use std::sync::atomic::{AtomicI64, Ordering};

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
/// The list column, in place of the `technique` string since 0.21.
const TECHNIQUES: &str = "techniques";
/// Where a table stored with the `technique` string is kept after its
/// rewrite.
const PRE_LIST: &str = "sightings.pre-list";
const SORT_KEY: &[&str] = &["rule_id", "ioc_value"];

fn schema() -> Vec<ColumnSpec> {
    let text = |name| ColumnSpec::new(name, ColumnType::Utf8, true);
    vec![
        ColumnSpec::new("ts", ColumnType::TimestampNanos, false),
        ColumnSpec::new("sighting_id", ColumnType::Utf8, false),
        text("rule_id"),
        // A list since 0.21; `open` rewrites a table with the string.
        ColumnSpec::new(TECHNIQUES, ColumnType::ListUtf8, true),
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

/// The comma-separated `technique` string as a list, empty parts left out.
fn techniques(technique: Option<&str>) -> RecordValue {
    technique.map_or(RecordValue::Null, |t| {
        RecordValue::List(
            t.split(',')
                .filter(|s| !s.is_empty())
                .map(|s| Some(s.to_string()))
                .collect(),
        )
    })
}

fn record(r: &SightingRow) -> Vec<RecordValue> {
    let opt = |v: &Option<String>| v.clone().map_or(RecordValue::Null, RecordValue::Str);
    vec![
        RecordValue::Int(r.ts_ns),
        RecordValue::Str(r.sighting_id.clone()),
        opt(&r.rule_id),
        if r.techniques.is_empty() {
            RecordValue::Null
        } else {
            RecordValue::List(r.techniques.iter().cloned().map(Some).collect())
        },
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

/// The clock a rewrite appends by: each row's arrival time in turn.
static REPLAY: AtomicI64 = AtomicI64::new(0);
fn replay_clock() -> i64 {
    REPLAY.load(Ordering::SeqCst)
}

/// Rewrites the table under `data`, stored with `stored` (the `technique`
/// string), into the current schema, the list filled from the string.
/// db-core can neither drop a column nor fill a new one for rows already
/// written, so the rows are copied. Each is appended at its
/// `received` time (`ts` before 0.13), so it stays in the hour and day it
/// arrived in. The new table is built next to the old one and swapped in
/// only when every row is there; the old one is kept as [`PRE_LIST`].
fn rewrite(
    data: &Path,
    stored: &[ColumnSpec],
    retention_days: Option<u32>,
    clock: fn() -> i64,
) -> Result<(), IngestError> {
    let corrupt = |why: String| IngestError::Corrupt(why);
    let dir = data.join(NAME);
    let backup = data.join(PRE_LIST);
    // Named so the table is still `sightings` in SQL.
    let work = data.join(format!("{NAME}.rewrite"));
    if backup.exists() {
        return Err(corrupt(format!(
            "{} needs a rewrite, but {} exists: move it away first",
            dir.display(),
            backup.display()
        )));
    }
    if work.exists() {
        std::fs::remove_dir_all(&work)?;
    }

    let old = Table::open(
        &dir,
        options(stored.to_vec(), SORT_KEY, retention_days, clock),
    )?;
    let all = old
        .query(&format!("SELECT * FROM {NAME}"))
        .map_err(|e| corrupt(e.to_string()))?;
    old.close()?;

    let at = |name: &str| stored.iter().position(|c| c.name == name);
    let int = |row: &[Cell], i: Option<usize>| match i.map(|i| &row[i]) {
        Some(Cell::Int(n)) => Some(*n),
        _ => None,
    };
    let (technique, received, ts) = (at("technique"), at("received"), at("ts"));
    let mut rows: Vec<(i64, Vec<RecordValue>)> = Vec::with_capacity(all.rows.len());
    for row in &all.rows {
        let values = schema()
            .iter()
            .map(|c| {
                if c.name == TECHNIQUES {
                    return Ok(techniques(match technique.map(|i| &row[i]) {
                        Some(Cell::Text(t)) => Some(t.as_str()),
                        _ => None,
                    }));
                }
                Ok(match at(&c.name).map(|i| &row[i]) {
                    None | Some(Cell::Null) => RecordValue::Null,
                    Some(Cell::Int(n)) => RecordValue::Int(*n),
                    Some(Cell::Text(t)) => RecordValue::Str(t.clone()),
                    Some(other) => {
                        return Err(corrupt(format!("{}: unexpected value {other:?}", c.name)))
                    }
                })
            })
            .collect::<Result<Vec<_>, _>>()?;
        let arrived = int(row, received).or(int(row, ts)).unwrap_or(0);
        rows.push((arrived, values));
    }
    rows.sort_by_key(|(arrived, _)| *arrived);

    let n = rows.len();
    REPLAY.store(rows.first().map_or_else(clock, |r| r.0), Ordering::SeqCst);
    let new = Table::open(
        work.join(NAME),
        options(schema(), SORT_KEY, retention_days, replay_clock),
    )?;
    for (i, (arrived, values)) in rows.into_iter().enumerate() {
        REPLAY.store(arrived, Ordering::SeqCst);
        let ack = if i + 1 == n {
            Ack::Durable
        } else {
            Ack::Memory
        };
        new.append_row(values, ack)?;
    }
    REPLAY.store(clock(), Ordering::SeqCst);
    new.flush()?;
    let copied = new
        .query(&format!("SELECT count(*) FROM {NAME}"))
        .map(|r| scalar(&r))
        .map_err(|e| corrupt(e.to_string()))?;
    if usize::try_from(copied).ok() != Some(n) {
        new.close()?;
        return Err(corrupt(format!(
            "rewrite copied {copied} of {n} rows; {} is unchanged",
            dir.display()
        )));
    }
    new.compact()?;
    new.close()?;

    std::fs::rename(&dir, &backup)?;
    std::fs::rename(work.join(NAME), &dir)?;
    std::fs::remove_dir(&work)?;
    tracing::info!(
        "{} rewritten with a {TECHNIQUES} list ({n} rows); the old table is in {} and can be deleted once checked",
        dir.display(),
        backup.display()
    );
    Ok(())
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
        let has = |s: &[ColumnSpec], name: &str| s.iter().any(|c| c.name == name);
        if stored.as_ref().is_some_and(|s| !has(s, "digest")) {
            return Err(IngestError::SchemaMismatch);
        }
        if let Some(s) = stored.as_ref().filter(|s| has(s, "technique")) {
            rewrite(data, s, retention_days, clock)?;
        }
        if data.join(OLD_TECHNIQUES).exists() {
            tracing::info!(
                "{} is no longer used (#180) and can be deleted",
                data.join(OLD_TECHNIQUES).display()
            );
        }
        let sightings = options(schema(), SORT_KEY, retention_days, clock);
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

#[cfg(test)]
mod tests {
    use super::*;
    use frank_core::Tlp;

    /// 2026-10-22 12:00 UTC.
    const T0: i64 = 1_792_670_400_000_000_000;
    const HOUR: i64 = 3_600 * 1_000_000_000;
    const DAY: i64 = 24 * HOUR;

    static CLOCK: AtomicI64 = AtomicI64::new(T0);
    fn now() -> i64 {
        CLOCK.load(Ordering::SeqCst)
    }

    fn row(id: &str, arrived: i64, techniques: &[&str], seq: u32) -> SightingRow {
        SightingRow {
            ts_ns: arrived - HOUR,
            sighting_id: id.into(),
            rule_id: Some("r1".into()),
            techniques: techniques.iter().map(|t| (*t).to_string()).collect(),
            campaign: None,
            ioc_type: None,
            ioc_value: Some(format!("{id}-{seq}")),
            reporter_sector: None,
            target_sector: None,
            target_size: None,
            severity: None,
            confidence: 50,
            observations: 1,
            tlp: Tlp::Green,
            reporter: "identity--a".into(),
            digest: format!("d-{id}"),
            received_ns: arrived,
            seq,
            detail: None,
        }
    }

    /// The partition directories of the listed files, sorted.
    fn partitions(t: &Table) -> Vec<String> {
        let mut p: Vec<String> = t
            .snapshot()
            .unwrap()
            .manifest()
            .files
            .iter()
            .map(|f| f.path.rsplit_once('/').map_or("", |(d, _)| d).to_string())
            .collect();
        p.sort();
        p.dedup();
        p
    }

    fn counts(s: &Sightings, from: &str) -> Vec<String> {
        let r = s
            .query(&format!(
                "SELECT tech, count(*) AS n FROM {from} WHERE seq = 0 AND tech <> '' GROUP BY tech ORDER BY tech"
            ))
            .unwrap();
        r.rows
            .iter()
            .map(|row| match (&row[0], &row[1]) {
                (Cell::Text(t), Cell::Int(n)) => format!("{t} {n}"),
                other => format!("{other:?}"),
            })
            .collect()
    }

    #[test]
    fn a_table_with_the_string_is_rewritten_in_its_partitions() {
        let data = std::env::temp_dir().join(format!("frank-list-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&data);
        std::fs::create_dir_all(&data).unwrap();

        // A 0.20 table: the `technique` string in place of the list, rows
        // over two days and three hours, flushed and compacted.
        let mut old = schema();
        old[3] = ColumnSpec::new("technique", ColumnType::Utf8, true);
        let t = Table::open(data.join(NAME), options(old, SORT_KEY, None, now)).unwrap();
        let rows = [
            (row("s1", T0, &[], 0), Some("T1059,T1071.001")),
            (row("s1", T0, &[], 1), Some("T1059,T1071.001")),
            (row("s2", T0 + 2 * HOUR, &[], 0), Some("T1059")),
            (row("s3", T0 + DAY, &[], 0), None),
            (row("s4", T0 + DAY + HOUR, &[], 0), Some("")),
        ];
        for (r, technique) in &rows {
            CLOCK.store(r.received_ns, Ordering::SeqCst);
            let mut v = record(r);
            v[3] = technique.map_or(RecordValue::Null, |t| RecordValue::Str(t.into()));
            t.append_row(v, Ack::Durable).unwrap();
        }
        CLOCK.store(T0 + DAY + 3 * HOUR, Ordering::SeqCst);
        t.flush().unwrap();
        t.compact().unwrap();
        let before = partitions(&t);
        assert!(
            before.iter().any(|p| p.starts_with("archive/")),
            "{before:?}"
        );
        assert!(before.iter().any(|p| p.starts_with("live/")), "{before:?}");
        t.close().unwrap();

        let s = Sightings::open(&data, None, now).unwrap();
        assert!(data.join(PRE_LIST).exists());
        assert!(!data.join(format!("{NAME}.rewrite")).exists());
        let all = s.query("SELECT count(*) FROM sightings").unwrap();
        assert_eq!(scalar(&all), 5);
        let expected = ["T1059 2", "T1071.001 1"];
        assert_eq!(
            counts(&s, "sightings, UNNEST(techniques) AS t(tech)"),
            expected
        );
        let has = s
            .query("SELECT count(*) FROM sightings WHERE list_contains(techniques, 'T1071.001')")
            .unwrap();
        assert_eq!(scalar(&has), 2, "both rows of s1");
        assert!(
            s.query("SELECT technique FROM sightings").is_err(),
            "the string is gone"
        );
        assert_eq!(
            partitions(&s.table),
            before,
            "rows stay in the hour and day they arrived in"
        );

        // New rows carry the list; a second open does not rewrite again.
        CLOCK.store(T0 + DAY + 4 * HOUR, Ordering::SeqCst);
        s.append(&[row("s5", now(), &["T1059"], 0)]).unwrap();
        s.close().unwrap();
        let s = Sightings::open(&data, None, now).unwrap();
        assert_eq!(
            counts(&s, "sightings, UNNEST(techniques) AS t(tech)"),
            ["T1059 3", "T1071.001 1"]
        );
        s.close().unwrap();
        let _ = std::fs::remove_dir_all(&data);
    }
}
