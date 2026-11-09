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
//!
//! `sighting_id` and `digest` are raw bytes since 0.28 (#200), 16 and 32,
//! where they were text; `digest` is on the `seq = 0` row only. A table
//! stored with text ids is rewritten when it is opened, as the technique
//! string was.

use std::path::Path;
use std::sync::atomic::{AtomicI64, Ordering};

use db_core::engine::{Cell, QueryResult};
use db_core::storage::ingest::{
    Ack, IngestError, Layout, Manifest, PageBody, RecordValue, Store, Table, TableOptions,
    TableStore, TierOptions,
};
use db_core::storage::parquet::writer::{
    ColumnSpec, ColumnType, Compression, ParquetWriter, WriterOptions,
};
use frank_core::{Digest, SightingId, SightingRow};

/// The table's directory name, which is also its name in SQL.
pub const NAME: &str = "sightings";
/// Under the data directory, where a table kept in a store has its WAL.
const LOCAL_WITH_STORE: &str = "s3";
/// The directory of the technique table FRANK wrote until 0.18 (#180).
const OLD_TECHNIQUES: &str = "sighting_techniques";
/// The list column, in place of the `technique` string since 0.21.
const TECHNIQUES: &str = "techniques";
/// Where a table stored with the `technique` string is kept after its
/// rewrite.
const PRE_LIST: &str = "sightings.pre-list";
/// Where a table stored with text ids is kept after its rewrite (#200).
const PRE_BINARY: &str = "sightings.pre-binary";
const SORT_KEY: &[&str] = &["rule_id", "ioc_value"];

fn schema() -> Vec<ColumnSpec> {
    let text = |name| ColumnSpec::new(name, ColumnType::Utf8, true);
    vec![
        ColumnSpec::new("ts", ColumnType::TimestampNanos, false),
        // Bytes since 0.28 (#200); `open` rewrites a table with text.
        ColumnSpec::new("sighting_id", ColumnType::Binary, false),
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
        // The registration (#159), on the `seq = 0` row; NULL in rows
        // stored before 0.13.
        ColumnSpec::new("digest", ColumnType::Binary, true),
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
        RecordValue::Bytes(r.sighting_id.0.to_vec()),
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
        r.digest
            .map_or(RecordValue::Null, |d| RecordValue::Bytes(d.0.to_vec())),
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

/// Whether a table stored with `stored` needs [`rewrite`]: it has the
/// `technique` string (0.20 and before) or text ids (0.27 and before).
fn outdated(stored: &[ColumnSpec]) -> bool {
    stored.iter().any(|c| {
        c.name == "technique" || (c.name == "sighting_id" && c.column_type == ColumnType::Utf8)
    })
}

/// A stored id or digest as bytes: text (0.27 and before, #200) or bytes.
fn id_bytes(cell: &Cell, digest: bool) -> Option<Vec<u8>> {
    match cell {
        Cell::Blob(b) => Some(b.clone()),
        Cell::Text(t) if digest => Digest::parse(t).map(|d| d.0.to_vec()),
        Cell::Text(t) => SightingId::parse(t).ok().map(|id| id.0.to_vec()),
        _ => None,
    }
}

/// Rewrites the table under `data`, stored with `stored`, into the current
/// schema: the list filled from the `technique` string, ids and digests
/// from text to bytes, the digest on the `seq = 0` row only. db-core can
/// neither drop or retype a column nor fill a new one for rows already
/// written, so the rows are copied. Each is appended at its
/// `received` time (`ts` before 0.13), so it stays in the hour and day it
/// arrived in. The new table is built next to the old one and swapped in
/// only when every row is there; the old one is kept as [`PRE_LIST`] or
/// [`PRE_BINARY`].
fn rewrite(
    data: &Path,
    stored: &[ColumnSpec],
    retention_days: Option<u32>,
    clock: fn() -> i64,
) -> Result<(), IngestError> {
    let corrupt = |why: String| IngestError::Corrupt(why);
    let dir = data.join(NAME);
    let had_string = stored.iter().any(|c| c.name == "technique");
    let backup = data.join(if had_string { PRE_LIST } else { PRE_BINARY });
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
    let first = |row: &[Cell]| int(row, at("seq")).unwrap_or(0) == 0;
    let mut rows: Vec<(i64, Vec<RecordValue>)> = Vec::with_capacity(all.rows.len());
    for row in &all.rows {
        let values = schema()
            .iter()
            .map(|c| {
                if c.name == TECHNIQUES && technique.is_some() {
                    return Ok(techniques(match technique.map(|i| &row[i]) {
                        Some(Cell::Text(t)) => Some(t.as_str()),
                        _ => None,
                    }));
                }
                // A stored list (0.21 on) reads back as JSON text.
                if c.column_type == ColumnType::ListUtf8 {
                    return match at(&c.name).map(|i| &row[i]) {
                        Some(Cell::Text(t)) => serde_json::from_str::<Vec<Option<String>>>(t)
                            .map(RecordValue::List)
                            .map_err(|e| corrupt(format!("{}: {e}: {t}", c.name))),
                        _ => Ok(RecordValue::Null),
                    };
                }
                let cell = at(&c.name).map(|i| &row[i]);
                if c.name == "digest" && !first(row) {
                    return Ok(RecordValue::Null);
                }
                if let Some(v @ (Cell::Text(_) | Cell::Blob(_))) =
                    cell.filter(|_| c.column_type == ColumnType::Binary)
                {
                    return id_bytes(v, c.name == "digest")
                        .map(RecordValue::Bytes)
                        .ok_or_else(|| corrupt(format!("{}: not an id or digest: {v:?}", c.name)));
                }
                Ok(match cell {
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
        "{} rewritten to the 0.28 schema ({n} rows); the old table is in {} and can be deleted once checked",
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
    /// Where the manifest and the Parquet files live when that is not the
    /// table directory (S3, `FRANK_STORE`); `None` for the local table.
    store: Option<Store>,
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
        Sightings::open_in(data, None, retention_days, clock)
    }

    /// [`Sightings::open`] with the manifest and the Parquet files kept in
    /// `store` when given (an `s3://` location, #220). The WAL, the writer
    /// lock and scratch space stay on this machine, in `data/s3/sightings`
    /// (apart from the local table's `data/sightings`, so a switch between
    /// the two never mixes them; the directory is named `sightings` for the
    /// table's name in SQL). A
    /// table in a store starts from the current schema: the rewrites of
    /// older local tables below rename directories, which a store cannot.
    pub fn open_in(
        data: &Path,
        store: Option<Store>,
        retention_days: Option<u32>,
        clock: fn() -> i64,
    ) -> Result<Sightings, IngestError> {
        if let Some(store) = store {
            let local = data.join(LOCAL_WITH_STORE).join(NAME);
            std::fs::create_dir_all(&local)?;
            let sightings = options(schema(), SORT_KEY, retention_days, clock);
            return Ok(Sightings {
                table: Table::open_in(local, store.clone(), sightings)?,
                store: Some(store),
            });
        }
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
        if let Some(s) = stored.as_ref().filter(|s| outdated(s)) {
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
            store: None,
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

    /// The table directory: for a table in a store, only its WAL.
    pub fn dir(&self) -> &Path {
        self.table.dir()
    }

    /// One file the table lists, by its path relative to the table.
    pub fn read_file(&self, path: &str) -> Result<Vec<u8>, String> {
        match &self.store {
            Some(store) => store
                .get(path)
                .map_err(|e| format!("{path}: {e}"))?
                .ok_or_else(|| format!("{path}: not in the store")),
            None => std::fs::read(self.dir().join(path)).map_err(|e| format!("{path}: {e}")),
        }
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

    fn row(n: u8, arrived: i64, techniques: &[&str], seq: u32) -> SightingRow {
        SightingRow {
            ts_ns: arrived - HOUR,
            sighting_id: SightingId([n; 16]),
            rule_id: Some("r1".into()),
            techniques: techniques.iter().map(|t| (*t).to_string()).collect(),
            campaign: None,
            ioc_type: None,
            ioc_value: Some(format!("s{n}-{seq}")),
            reporter_sector: None,
            target_sector: None,
            target_size: None,
            severity: None,
            confidence: 50,
            observations: 1,
            tlp: Tlp::Green,
            reporter: "identity--a".into(),
            digest: (seq == 0).then_some(Digest([n; 32])),
            received_ns: arrived,
            seq,
            detail: None,
        }
    }

    /// The schema as 0.27 stored it: ids and digests as text (#200).
    fn text_schema() -> Vec<ColumnSpec> {
        let mut s = schema();
        s[1] = ColumnSpec::new("sighting_id", ColumnType::Utf8, false);
        s[15] = ColumnSpec::new("digest", ColumnType::Utf8, true);
        s
    }

    /// `r` as 0.27 stored it: ids and digests as text, the digest on
    /// every row of a sighting.
    fn text_record(r: &SightingRow) -> Vec<RecordValue> {
        let mut v = record(r);
        v[1] = RecordValue::Str(r.sighting_id.to_string());
        v[15] = RecordValue::Str(Digest([r.sighting_id.0[0]; 32]).to_string());
        v
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

    static STORE_CLOCK: AtomicI64 = AtomicI64::new(T0);
    fn store_now() -> i64 {
        STORE_CLOCK.load(Ordering::SeqCst)
    }

    #[test]
    fn a_table_in_a_store_keeps_its_files_there_and_its_wal_apart() {
        let data = std::env::temp_dir().join(format!("frank-store-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&data);
        let bucket = data.join("bucket");
        let open = || {
            let store = Store::at(bucket.to_str().unwrap()).unwrap();
            Sightings::open_in(&data, Some(store), None, store_now).unwrap()
        };

        STORE_CLOCK.store(T0, Ordering::SeqCst);
        let s = open();
        s.append(&[row(1, T0, &[], 0), row(2, T0, &[], 0)]).unwrap();
        STORE_CLOCK.store(T0 + 2 * HOUR, Ordering::SeqCst);
        assert_eq!(s.flush().unwrap(), 1);

        let files = s.files().unwrap();
        assert_eq!(files.len(), 1);
        let path = &files[0].0;
        assert!(path.starts_with("live/"), "{path}");
        assert!(bucket.join(path).is_file(), "the file is in the store");
        assert!(bucket.join("manifest.json").is_file(), "so is the manifest");
        let local = data.join(LOCAL_WITH_STORE).join(NAME);
        assert!(local.join("wal").is_dir(), "the WAL is local");
        assert!(!local.join("live").exists(), "no Parquet beside it");
        assert!(
            !data.join(NAME).exists(),
            "the local table's directory is untouched"
        );

        let bytes = s.read_file(path).unwrap();
        assert_eq!(&bytes[..4], b"PAR1");
        assert!(s.read_file("live/none.parquet").is_err());
        assert_eq!(
            scalar(&s.query("SELECT count(*) FROM sightings").unwrap()),
            2
        );
        s.close().unwrap();

        // A new process, with no WAL left to replay, reads it from the store.
        let s = open();
        assert_eq!(
            scalar(&s.query("SELECT count(*) FROM sightings").unwrap()),
            2
        );
        s.close().unwrap();
        let _ = std::fs::remove_dir_all(&data);
    }

    /// The documented way to switch mode (README, "Switching mode"): a local
    /// table's directory copied to the bucket, its `wal/` to the store mode's
    /// WAL directory, is the table in the store, and the other way round.
    #[test]
    fn a_local_table_copied_to_a_store_is_the_same_table() {
        fn copy(from: &Path, to: &Path) {
            for e in std::fs::read_dir(from).unwrap().flatten() {
                let (src, dst) = (e.path(), to.join(e.file_name()));
                if matches!(e.file_name().to_str(), Some("tmp" | "lock" | "LOCK")) {
                    continue;
                }
                if src.is_dir() {
                    std::fs::create_dir_all(&dst).unwrap();
                    copy(&src, &dst);
                } else {
                    std::fs::copy(&src, &dst).unwrap();
                }
            }
        }
        let data = std::env::temp_dir().join(format!("frank-switch-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&data);
        let count = |s: &Sightings| scalar(&s.query("SELECT count(*) FROM sightings").unwrap());

        // Local mode: two sightings, the server stopped (closed).
        STORE_CLOCK.store(T0, Ordering::SeqCst);
        let local = Sightings::open(&data, None, store_now).unwrap();
        local
            .append(&[row(1, T0, &[], 0), row(2, T0, &[], 0)])
            .unwrap();
        local.close().unwrap();

        // Switch to a store: copy `data/sightings` (no WAL) to the bucket.
        let bucket = data.join("bucket");
        let wal = data.join(LOCAL_WITH_STORE).join(NAME);
        std::fs::create_dir_all(&bucket).unwrap();
        std::fs::create_dir_all(&wal).unwrap();
        copy(&data.join(NAME), &bucket);
        // The WAL is not an object: it goes beside the other state, with the
        // open hour that is not in Parquet yet.
        std::fs::rename(bucket.join("wal"), wal.join("wal")).unwrap();
        let store = Store::at(bucket.to_str().unwrap()).unwrap();
        let s = Sightings::open_in(&data, Some(store), None, store_now).unwrap();
        assert_eq!(count(&s), 2, "what the local table held is in the store");
        s.append(&[row(3, T0, &[], 0)]).unwrap();
        s.close().unwrap();

        // And back: the bucket and the WAL over a fresh local directory.
        let back = data.join("back");
        std::fs::create_dir_all(back.join(NAME)).unwrap();
        copy(&bucket, &back.join(NAME));
        std::fs::remove_dir_all(back.join(NAME).join("wal")).ok();
        std::fs::create_dir_all(back.join(NAME).join("wal")).unwrap();
        copy(&wal.join("wal"), &back.join(NAME).join("wal"));
        let s = Sightings::open(&back, None, store_now).unwrap();
        assert_eq!(count(&s), 3, "the sighting written in the store came along");
        s.close().unwrap();
        let _ = std::fs::remove_dir_all(&data);
    }

    /// Retention removes the objects themselves from the store (#220).
    #[test]
    fn retention_deletes_the_objects_in_the_store() {
        let data = std::env::temp_dir().join(format!("frank-store-ret-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&data);
        let bucket = data.join("bucket");
        let store = Store::at(bucket.to_str().unwrap()).unwrap();
        STORE_CLOCK.store(T0, Ordering::SeqCst);
        let s = Sightings::open_in(&data, Some(store), Some(2), store_now).unwrap();
        s.append(&[row(1, T0, &[], 0)]).unwrap();
        STORE_CLOCK.store(T0 + 2 * HOUR, Ordering::SeqCst);
        s.flush().unwrap();
        STORE_CLOCK.store(T0 + DAY, Ordering::SeqCst);
        s.compact().unwrap();
        let files = s.files().unwrap();
        assert_eq!(files.len(), 1);
        let kept = files[0].0.clone();
        assert!(bucket.join(&kept).is_file(), "{kept}");

        // Past the retention the day drops out of the manifest; the object
        // goes once db-core's delete grace (10 minutes, for readers still on
        // the old manifest) has passed.
        STORE_CLOCK.store(T0 + 5 * DAY, Ordering::SeqCst);
        s.compact().unwrap();
        assert!(s.files().unwrap().is_empty());
        STORE_CLOCK.store(T0 + 5 * DAY + HOUR, Ordering::SeqCst);
        s.compact().unwrap();
        assert!(!bucket.join(&kept).exists(), "{kept} still in the store");
        s.close().unwrap();
        let _ = std::fs::remove_dir_all(&data);
    }

    #[test]
    fn a_table_with_the_string_is_rewritten_in_its_partitions() {
        let data = std::env::temp_dir().join(format!("frank-list-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&data);
        std::fs::create_dir_all(&data).unwrap();

        // A 0.20 table: the `technique` string in place of the list, rows
        // over two days and three hours, flushed and compacted.
        let mut old = text_schema();
        old[3] = ColumnSpec::new("technique", ColumnType::Utf8, true);
        let t = Table::open(data.join(NAME), options(old, SORT_KEY, None, now)).unwrap();
        let rows = [
            (row(1, T0, &[], 0), Some("T1059,T1071.001")),
            (row(1, T0, &[], 1), Some("T1059,T1071.001")),
            (row(2, T0 + 2 * HOUR, &[], 0), Some("T1059")),
            (row(3, T0 + DAY, &[], 0), None),
            (row(4, T0 + DAY + HOUR, &[], 0), Some("")),
        ];
        for (r, technique) in &rows {
            CLOCK.store(r.received_ns, Ordering::SeqCst);
            let mut v = text_record(r);
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
        s.append(&[row(5, now(), &["T1059"], 0)]).unwrap();
        s.close().unwrap();
        let s = Sightings::open(&data, None, now).unwrap();
        assert_eq!(
            counts(&s, "sightings, UNNEST(techniques) AS t(tech)"),
            ["T1059 3", "T1071.001 1"]
        );
        s.close().unwrap();
        let _ = std::fs::remove_dir_all(&data);
    }

    /// Its own clock: tests run in parallel.
    static BIN_CLOCK: AtomicI64 = AtomicI64::new(T0);
    fn bin_now() -> i64 {
        BIN_CLOCK.load(Ordering::SeqCst)
    }

    #[test]
    fn a_table_with_text_ids_is_rewritten_to_bytes() {
        let data = std::env::temp_dir().join(format!("frank-binary-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&data);
        std::fs::create_dir_all(&data).unwrap();

        // A 0.27 table: ids and digests as text, the digest on every row,
        // over two hours.
        let t = Table::open(
            data.join(NAME),
            options(text_schema(), SORT_KEY, None, bin_now),
        )
        .unwrap();
        let rows = [
            row(1, T0, &["T1059"], 0),
            row(1, T0, &["T1059"], 1),
            row(2, T0 + HOUR, &[], 0),
        ];
        for r in &rows {
            BIN_CLOCK.store(r.received_ns, Ordering::SeqCst);
            t.append_row(text_record(r), Ack::Durable).unwrap();
        }
        BIN_CLOCK.store(T0 + 3 * HOUR, Ordering::SeqCst);
        t.flush().unwrap();
        t.compact().unwrap();
        let before = partitions(&t);
        t.close().unwrap();

        let s = Sightings::open(&data, None, bin_now).unwrap();
        assert!(data.join(PRE_BINARY).exists());
        assert!(!data.join(PRE_LIST).exists());
        let got = s
            .query("SELECT sighting_id, digest, seq FROM sightings ORDER BY ioc_value")
            .unwrap();
        let blob = |n: u8, len: usize| Cell::Blob(vec![n; len]);
        assert_eq!(
            got.rows,
            [
                vec![blob(1, 16), blob(1, 32), Cell::Int(0)],
                vec![blob(1, 16), Cell::Null, Cell::Int(1)],
                vec![blob(2, 16), blob(2, 32), Cell::Int(0)],
            ],
            "the same ids as bytes, the digest on the first row only"
        );
        let one = s
            .query(&format!(
                "SELECT count(*) FROM sightings WHERE sighting_id = {}",
                frank_core::sql_blob(&[1; 16])
            ))
            .unwrap();
        assert_eq!(scalar(&one), 2);
        assert_eq!(partitions(&s.table), before, "rows stay in their hours");
        assert_eq!(
            counts(&s, "sightings, UNNEST(techniques) AS t(tech)"),
            ["T1059 1"],
            "the list is kept"
        );

        // New rows go in as bytes; a second open does not rewrite again.
        BIN_CLOCK.store(T0 + 4 * HOUR, Ordering::SeqCst);
        s.append(&[row(3, bin_now(), &[], 0)]).unwrap();
        s.close().unwrap();
        std::fs::remove_dir_all(data.join(PRE_BINARY)).unwrap();
        let s = Sightings::open(&data, None, bin_now).unwrap();
        assert!(!data.join(PRE_BINARY).exists());
        let all = s
            .query("SELECT count(DISTINCT sighting_id) FROM sightings")
            .unwrap();
        assert_eq!(scalar(&all), 3);
        s.close().unwrap();
        let _ = std::fs::remove_dir_all(&data);
    }

    #[test]
    fn a_text_id_that_is_no_uuid_stops_the_rewrite() {
        let data = std::env::temp_dir().join(format!("frank-badid-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&data);
        std::fs::create_dir_all(&data).unwrap();
        let t = Table::open(data.join(NAME), options(text_schema(), SORT_KEY, None, now)).unwrap();
        let mut v = text_record(&row(1, T0, &[], 0));
        v[1] = RecordValue::Str("s1".into());
        t.append_row(v, Ack::Durable).unwrap();
        t.close().unwrap();

        let e = Sightings::open(&data, None, now).err().unwrap();
        assert!(e.to_string().contains("sighting_id"), "{e}");
        assert!(
            !data.join(PRE_BINARY).exists(),
            "the table is left as it was"
        );
        let _ = std::fs::remove_dir_all(&data);
    }
}
