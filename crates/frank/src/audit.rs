//! The audit log (#159): who did what, one row per state-changing action,
//! in the striped db-core table `audit` (ADR-024, #309): hour files in
//! `live/`, closed days merged into `archive/`, whole days dropped after
//! `FRANK_AUDIT_RETENTION_DAYS`, apart from the sightings' retention. It
//! is under the data directory, or with `FRANK_STORE` (#220) under
//! `<store>/audit` with its WAL in `<data>/s3/audit`.
//!
//! A table has one writer, the server while it runs. A command run next
//! to it (`frank user add` through `podman exec`) finds the table locked
//! and appends its lines to `<data>/audit.spool` instead; the server moves
//! them into the table on its next tick. With the server stopped, the
//! command writes the table itself.
//!
//! The JSONL days of FRANK 0.55 and before (`<data>/audit/*.jsonl`, or
//! `audit/YYYY-MM-DD/` objects in the store) are imported once, then kept
//! aside in `audit.jsonl/`.
//!
//! It names users, which the shared Parquet files never do, and never a
//! token: a token appears as the first 12 hex digits of its hash.

use std::fs::{File, OpenOptions};
use std::io::Write;
use std::os::unix::fs::MetadataExt;
use std::path::{Path, PathBuf};

use db_core::engine::Cell;
use db_core::storage::ingest::{
    Ack, IngestError, Layout, RecordValue, Store, Table, TableOptions, TableStore, TierOptions,
    WalError,
};
use db_core::storage::parquet::writer::{ColumnSpec, ColumnType, Compression, WriterOptions};
use frank_core::sql_quote;
use serde_json::{json, Map, Value};
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

/// The table's directory and its name in SQL.
pub const NAME: &str = "audit";
/// Where a command appends while the server holds the table.
pub const SPOOL: &str = "audit.spool";
/// The spool while the server moves it into the table.
const DRAINING: &str = "audit.spool.draining";
/// Where the JSONL days are kept once imported.
pub const OLD: &str = "audit.jsonl";
/// In [`OLD`]: the import is done.
const IMPORTED: &str = "IMPORTED";
/// Under the data directory, where a table kept in a store has its WAL.
const LOCAL_WITH_STORE: &str = "s3";
/// The fields with a column of their own; the rest go in `fields`.
const PROMOTED: [&str; 3] = ["participant", "user", "token"];

fn schema() -> Vec<ColumnSpec> {
    let text = |name| ColumnSpec::new(name, ColumnType::Utf8, true);
    vec![
        ColumnSpec::new("at", ColumnType::TimestampNanos, false),
        ColumnSpec::new("by", ColumnType::Utf8, false),
        ColumnSpec::new("action", ColumnType::Utf8, false),
        text("participant"),
        text("user"),
        text("token"),
        // The other fields as one JSON object; NULL when there are none.
        text("fields"),
    ]
}

fn options(retention_days: Option<u32>, clock: fn() -> i64) -> TableOptions {
    TableOptions {
        schema: Some(schema()),
        layout: Layout::Tiered(TierOptions {
            sort_key: vec!["at".to_string()],
            retention_days,
            // A window of days skips the files outside it without a read.
            stat_columns: vec!["at".to_string()],
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

/// Which lines an admin sees (#159): about its organisation, its users or
/// its tokens, or done by one of its users. `None` is all of them.
#[derive(Debug, Default)]
pub struct Scope {
    pub participant: String,
    pub users: Vec<String>,
    pub tokens: Vec<String>,
    /// `user@organisation` of its users.
    pub by: Vec<String>,
}

impl Scope {
    /// The scope as a SQL condition.
    fn condition(&self) -> String {
        let list = |vs: &[String]| vs.iter().map(|v| sql_quote(v)).collect::<Vec<_>>();
        // Every column name quoted: `by`, `user` and `action` are keywords.
        let mut any = vec![format!(
            "\"participant\" = {}",
            sql_quote(&self.participant)
        )];
        for (column, values) in [
            ("\"user\"", &self.users),
            ("\"token\"", &self.tokens),
            ("\"by\"", &self.by),
        ] {
            if !values.is_empty() {
                any.push(format!("{column} IN ({})", list(values).join(", ")));
            }
        }
        format!("({})", any.join(" OR "))
    }
}

#[derive(Debug, Clone)]
enum Backend {
    Table(Table),
    /// The server holds the table: lines go to the spool file.
    Spool(PathBuf),
}

#[derive(Debug, Clone)]
pub struct Audit {
    backend: Backend,
    data: PathBuf,
}

impl Audit {
    /// The table under `<data>/audit`, created if needed.
    pub fn open(data: &Path) -> Result<Audit, String> {
        Audit::open_in(data, None, None)
    }

    /// [`Audit::open`], or, given `location` (`FRANK_STORE`), the table
    /// under `<location>/audit`; days older than `retention_days` drop out
    /// at compaction. A table another process holds gives the spool.
    pub fn open_in(
        data: &Path,
        location: Option<&str>,
        retention_days: Option<u32>,
    ) -> Result<Audit, String> {
        Audit::open_with(data, location, retention_days, crate::cli::now_ns)
    }

    /// [`Audit::open_in`] with the table's `clock` (ns since the epoch),
    /// which decides the hour and day a row is in, and so its retention.
    fn open_with(
        data: &Path,
        location: Option<&str>,
        retention_days: Option<u32>,
        clock: fn() -> i64,
    ) -> Result<Audit, String> {
        std::fs::create_dir_all(data).map_err(|e| format!("{}: {e}", data.display()))?;
        let opened = match location {
            None => {
                set_aside_local(data)?;
                Table::open(data.join(NAME), options(retention_days, clock))
            }
            Some(location) => {
                let local = data.join(LOCAL_WITH_STORE).join(NAME);
                std::fs::create_dir_all(&local).map_err(|e| e.to_string())?;
                let store = crate::objects::open(&sub_location(location, NAME))
                    .map_err(|e| format!("FRANK_STORE: {e}"))?;
                Table::open_in(local, store, options(retention_days, clock))
            }
        };
        let table = match opened {
            Ok(t) => t,
            Err(IngestError::Wal(WalError::Locked)) => {
                return Ok(Audit {
                    backend: Backend::Spool(data.join(SPOOL)),
                    data: data.to_path_buf(),
                })
            }
            Err(e) => return Err(format!("audit: {e}")),
        };
        let audit = Audit {
            backend: Backend::Table(table),
            data: data.to_path_buf(),
        };
        match location {
            None => audit.import_local()?,
            Some(location) => {
                let root =
                    crate::objects::open(location).map_err(|e| format!("FRANK_STORE: {e}"))?;
                audit.import_store(&root)?;
            }
        }
        Ok(audit)
    }

    /// Whether another process holds the table and lines go to the spool.
    #[must_use]
    pub fn is_spool(&self) -> bool {
        matches!(self.backend, Backend::Spool(_))
    }

    /// Records `{"at", "by", "action", ...fields}` at `now_ns`. `by` is
    /// `user@organisation`, or `cli:<os user>` for the command line.
    pub fn record(&self, now_ns: i64, by: &str, action: &str, fields: Value) -> Result<(), String> {
        let mut line = json!({ "at": rfc3339(now_ns)?, "by": by, "action": action });
        if let (Some(line), Value::Object(fields)) = (line.as_object_mut(), fields) {
            line.extend(fields);
        }
        match &self.backend {
            Backend::Table(table) => append(table, vec![row(&line)?]),
            Backend::Spool(path) => spool(path, &line),
        }
    }

    /// The lines from `from_ns` on that `scope` lets through, newest first,
    /// at most `limit`.
    pub fn query(
        &self,
        from_ns: i64,
        scope: Option<&Scope>,
        limit: usize,
    ) -> Result<Vec<Value>, String> {
        let scope = scope.map_or(String::new(), |s| format!(" AND {}", s.condition()));
        // Oldest first, then reversed: lines of the same nanosecond stay in
        // the order they were written, newest first, as the JSONL gave.
        let mut lines =
            self.select(&format!("WHERE \"at\" >= {from_ns}{scope} ORDER BY \"at\""))?;
        lines.reverse();
        lines.truncate(limit);
        Ok(lines)
    }

    /// The lines of the days from `from_day` (days since the epoch) on,
    /// oldest first.
    pub fn read_from(&self, from_day: i64) -> Result<Vec<Value>, String> {
        let from = from_day.saturating_mul(86_400_000_000_000);
        self.select(&format!("WHERE \"at\" >= {from} ORDER BY \"at\""))
    }

    fn select(&self, rest: &str) -> Result<Vec<Value>, String> {
        let Backend::Table(table) = &self.backend else {
            return Err("the audit table is held by the server".into());
        };
        let r = table
            .query(&format!(
                "SELECT \"at\", \"by\", \"action\", \"participant\", \"user\", \"token\", \"fields\" FROM {NAME} {rest}"
            ))
            .map_err(|e| format!("audit: {e}"))?;
        r.rows.iter().map(|cells| line(cells)).collect()
    }

    /// Moves the spool into the table: the lines commands wrote while the
    /// server ran. The number of lines moved.
    pub fn drain_spool(&self) -> Result<usize, String> {
        let Backend::Table(table) = &self.backend else {
            return Ok(0);
        };
        let draining = self.data.join(DRAINING);
        // A drain cut short left its file: finish it first.
        if !draining.exists() {
            match std::fs::rename(self.data.join(SPOOL), &draining) {
                Ok(()) => {}
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(0),
                Err(e) => return Err(format!("{SPOOL}: {e}")),
            }
        }
        let file = File::open(&draining).map_err(|e| format!("{DRAINING}: {e}"))?;
        // Waits for a command still writing to it (see `spool`).
        file.lock().map_err(|e| format!("{DRAINING}: {e}"))?;
        let text = std::fs::read_to_string(&draining).map_err(|e| format!("{DRAINING}: {e}"))?;
        let rows = lines_to_rows(&text)?;
        let n = rows.len();
        if n > 0 {
            append(table, rows)?;
        }
        std::fs::remove_file(&draining).map_err(|e| format!("{DRAINING}: {e}"))?;
        Ok(n)
    }

    /// Writes closed hours to `live/`.
    pub fn flush(&self) -> Result<usize, String> {
        match &self.backend {
            Backend::Table(t) => Ok(t.flush().map_err(|e| e.to_string())?.len()),
            Backend::Spool(_) => Ok(0),
        }
    }

    /// Merges closed days into `archive/` and drops the days past the
    /// retention.
    pub fn compact(&self) -> Result<usize, String> {
        match &self.backend {
            Backend::Table(t) => Ok(t.compact().map_err(|e| e.to_string())?.len()),
            Backend::Spool(_) => Ok(0),
        }
    }

    pub fn close(&self) -> Result<(), String> {
        match &self.backend {
            Backend::Table(t) => t.close().map_err(|e| e.to_string()),
            Backend::Spool(_) => Ok(()),
        }
    }

    // --- the JSONL days of 0.55 and before ----------------------------

    /// Appends `lines` (oldest first) past the first `skip`: rows an
    /// import cut short already wrote, in the same order.
    fn import(&self, lines: &str, skip: usize) -> Result<usize, String> {
        let Backend::Table(table) = &self.backend else {
            return Ok(0);
        };
        let rows: Vec<_> = lines_to_rows(lines)?.into_iter().skip(skip).collect();
        let n = rows.len();
        if n > 0 {
            append(table, rows)?;
        }
        Ok(n)
    }

    /// The rows in the table: before an import, those an earlier one cut
    /// short wrote.
    fn count(&self) -> Result<usize, String> {
        let Backend::Table(table) = &self.backend else {
            return Ok(0);
        };
        let r = table
            .query(&format!("SELECT count(*) FROM {NAME}"))
            .map_err(|e| e.to_string())?;
        Ok(usize::try_from(crate::store::sightings::scalar(&r)).unwrap_or(0))
    }

    /// Imports `<data>/audit.jsonl/*.jsonl` (set aside by
    /// [`set_aside_local`]) unless done.
    fn import_local(&self) -> Result<(), String> {
        let old = self.data.join(OLD);
        if old.join(IMPORTED).exists() {
            return Ok(());
        }
        // Nothing set aside: a table from the start.
        if !old.is_dir() {
            return Ok(());
        }
        self.import_days(&old)
    }

    fn import_days(&self, old: &Path) -> Result<(), String> {
        let mut days: Vec<(i64, PathBuf)> = std::fs::read_dir(old)
            .map_err(|e| format!("{}: {e}", old.display()))?
            .flatten()
            .filter_map(|e| Some((day_of(e.file_name().to_str()?)?, e.path())))
            .collect();
        days.sort();
        let mut text = String::new();
        for (_, path) in days {
            text +=
                &std::fs::read_to_string(&path).map_err(|e| format!("{}: {e}", path.display()))?;
        }
        let n = self.import(&text, self.count()?)?;
        std::fs::write(old.join(IMPORTED), b"").map_err(|e| format!("{}: {e}", old.display()))?;
        tracing::info!(
            lines = n,
            "audit: the JSONL days are imported into the table; {} can be deleted once checked",
            old.display()
        );
        Ok(())
    }

    /// Imports the `audit/YYYY-MM-DD/` objects of `root` unless done: moved
    /// to `audit.jsonl/` first, then imported, then marked.
    fn import_store(&self, root: &Store) -> Result<(), String> {
        let marker = format!("{OLD}/{IMPORTED}");
        if root
            .get(&marker)
            .map_err(|e| store_err(&marker, e))?
            .is_some()
        {
            return Ok(());
        }
        move_day_objects(root)?;
        let n = self.import(&store_text(root)?, self.count()?)?;
        root.put(&marker, b"").map_err(|e| store_err(&marker, e))?;
        if n > 0 {
            tracing::info!(
                lines = n,
                "audit: the day objects are imported into the table, kept in {OLD}/"
            );
        }
        Ok(())
    }
}

fn store_err(key: &str, e: std::io::Error) -> String {
    format!("{key}: {e}")
}

/// Moves the `audit/YYYY-MM-DD/` objects of `root` to `audit.jsonl/`. Only
/// the day objects: the table's own files are under the same prefix, in
/// `live/`, `archive/` and the manifest.
fn move_day_objects(root: &Store) -> Result<(), String> {
    let prefix = format!("{NAME}/");
    for key in root.list(&prefix).map_err(|e| store_err(&prefix, e))? {
        if key_day(&key).is_none() {
            continue;
        }
        let Some(bytes) = root.get(&key).map_err(|e| store_err(&key, e))? else {
            continue;
        };
        let to = format!("{OLD}/{}", &key[prefix.len()..]);
        root.put(&to, &bytes).map_err(|e| store_err(&to, e))?;
        root.delete(&key).map_err(|e| store_err(&key, e))?;
    }
    Ok(())
}

/// The text of every object kept in `audit.jsonl/` in `root`, in key order.
fn store_text(root: &Store) -> Result<String, String> {
    let moved = format!("{OLD}/");
    let mut text = String::new();
    for key in root.list(&moved).map_err(|e| store_err(&moved, e))? {
        if let Some(bytes) = root.get(&key).map_err(|e| store_err(&key, e))? {
            text += &String::from_utf8_lossy(&bytes);
        }
    }
    Ok(text)
}

/// `<data>/audit` of 0.55 and before, a directory of JSONL days, renamed
/// to `<data>/audit.jsonl` so the table can take its name.
fn set_aside_local(data: &Path) -> Result<(), String> {
    let dir = data.join(NAME);
    let jsonl = std::fs::read_dir(&dir).is_ok_and(|mut es| {
        es.any(|e| e.is_ok_and(|e| day_of(&e.file_name().to_string_lossy()).is_some()))
    });
    if !jsonl {
        return Ok(());
    }
    let old = data.join(OLD);
    if old.exists() {
        return Err(format!(
            "{} holds JSONL days, but {} exists: move one of them away",
            dir.display(),
            old.display()
        ));
    }
    std::fs::rename(&dir, &old).map_err(|e| format!("{}: {e}", dir.display()))
}

/// `location` with `name` appended to its path: `s3://b/p?x` gives
/// `s3://b/p/name?x`, a directory its subdirectory.
#[must_use]
pub fn sub_location(location: &str, name: &str) -> String {
    match location.split_once('?') {
        Some((path, query)) => format!("{}/{name}?{query}", path.trim_end_matches('/')),
        None => format!("{}/{name}", location.trim_end_matches('/')),
    }
}

/// Appends `line` to the spool. A drain renames the spool and then takes
/// its lock, so a line written to a renamed file is still read; one that
/// lost the race to a drain (the file it opened is gone) is written again
/// to a new spool.
fn spool(path: &Path, line: &Value) -> Result<(), String> {
    let mut bytes = serde_json::to_vec(line).map_err(|e| e.to_string())?;
    bytes.push(b'\n');
    let err = |e: std::io::Error| format!("{}: {e}", path.display());
    loop {
        let mut f = OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .map_err(err)?;
        f.lock().map_err(err)?;
        let ino = f.metadata().map_err(err)?.ino();
        // Still the spool, or renamed to the draining file the server reads
        // only once this lock is released: either way it is read.
        let at = |p: &Path| std::fs::metadata(p).map(|m| m.ino()).ok();
        if ![at(path), at(&path.with_file_name(DRAINING))].contains(&Some(ino)) {
            continue;
        }
        f.write_all(&bytes)
            .and_then(|()| f.sync_data())
            .map_err(err)?;
        return Ok(());
    }
}

/// The table row of an audit line.
fn row(line: &Value) -> Result<Vec<RecordValue>, String> {
    let s = |k: &str| line[k].as_str().map(str::to_string);
    let at = s("at").ok_or("audit line without `at`")?;
    let at = OffsetDateTime::parse(&at, &Rfc3339).map_err(|e| format!("at {at}: {e}"))?;
    let at = i64::try_from(at.unix_timestamp_nanos()).map_err(|e| e.to_string())?;
    let text = |v: Option<String>| v.map_or(RecordValue::Null, RecordValue::Str);
    let mut rest = Map::new();
    if let Some(fields) = line.as_object() {
        for (k, v) in fields {
            // A promoted field that is no string stays in `fields`.
            let own_column = match k.as_str() {
                "at" | "by" | "action" => true,
                k if PROMOTED.contains(&k) => v.is_string(),
                _ => false,
            };
            if !own_column {
                rest.insert(k.clone(), v.clone());
            }
        }
    }
    Ok(vec![
        RecordValue::Int(at),
        RecordValue::Str(s("by").unwrap_or_default()),
        RecordValue::Str(s("action").unwrap_or_default()),
        text(s("participant")),
        text(s("user")),
        text(s("token")),
        if rest.is_empty() {
            RecordValue::Null
        } else {
            RecordValue::Str(Value::Object(rest).to_string())
        },
    ])
}

/// The audit line of a row, as the JSONL line was.
fn line(cells: &[Cell]) -> Result<Value, String> {
    let text = |i: usize| match cells.get(i) {
        Some(Cell::Text(t)) => Some(t.clone()),
        _ => None,
    };
    let at = cells
        .first()
        .and_then(crate::store::sightings::nanos)
        .ok_or("audit row without `at`")?;
    let mut out = Map::new();
    out.insert("at".into(), Value::String(rfc3339(at)?));
    out.insert("by".into(), Value::String(text(1).unwrap_or_default()));
    out.insert("action".into(), Value::String(text(2).unwrap_or_default()));
    for (i, k) in PROMOTED.iter().enumerate() {
        if let Some(v) = text(3 + i) {
            out.insert((*k).into(), Value::String(v));
        }
    }
    if let Some(Value::Object(rest)) = text(6).and_then(|f| serde_json::from_str(&f).ok()) {
        out.extend(rest);
    }
    Ok(Value::Object(out))
}

/// The rows of JSONL `text`; a line that is not JSON is skipped.
fn lines_to_rows(text: &str) -> Result<Vec<Vec<RecordValue>>, String> {
    text.lines()
        .filter_map(|l| serde_json::from_str::<Value>(l).ok())
        .map(|l| row(&l))
        .collect()
}

/// Appends `rows`, durable once the last one is.
fn append(table: &Table, rows: Vec<Vec<RecordValue>>) -> Result<(), String> {
    let n = rows.len();
    for (i, r) in rows.into_iter().enumerate() {
        let ack = if i + 1 == n {
            Ack::Durable
        } else {
            Ack::Memory
        };
        table
            .append_row(r, ack)
            .map_err(|e| format!("audit: {e}"))?;
    }
    Ok(())
}

fn rfc3339(ns: i64) -> Result<String, String> {
    OffsetDateTime::from_unix_timestamp_nanos(i128::from(ns))
        .map_err(|e| e.to_string())?
        .format(&Rfc3339)
        .map_err(|e| e.to_string())
}

/// The day (since the epoch) of `YYYY-MM-DD`.
fn parse_day(d: &str) -> Option<i64> {
    let day =
        time::Date::parse(d, time::macros::format_description!("[year]-[month]-[day]")).ok()?;
    Some(
        day.midnight()
            .assume_utc()
            .unix_timestamp()
            .div_euclid(86_400),
    )
}

/// The day a `YYYY-MM-DD.jsonl` file holds.
fn day_of(name: &str) -> Option<i64> {
    parse_day(name.strip_suffix(".jsonl")?)
}

/// The day an `audit/YYYY-MM-DD/<line>.jsonl` object holds.
fn key_day(key: &str) -> Option<i64> {
    parse_day(key.strip_prefix("audit/")?.split('/').next()?)
}

/// `cli:<os user>`, who runs a command.
#[must_use]
pub fn cli_user() -> String {
    format!(
        "cli:{}",
        std::env::var("USER")
            .or_else(|_| std::env::var("LOGNAME"))
            .unwrap_or_else(|_| "unknown".into())
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    const DAY: i64 = 86_400 * 1_000_000_000;
    /// 2026-10-22T12:00:00Z.
    const T: i64 = 1_792_670_400 * 1_000_000_000;

    fn dir(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("frank-audit-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        d
    }

    #[test]
    fn lines_are_rows_and_read_back_as_lines() {
        let d = dir("rows");
        let a = Audit::open(&d).unwrap();
        a.record(
            T,
            "bob@lab",
            "token_issued",
            json!({"user": "bob", "token": "1a2b3c4d5e6f"}),
        )
        .unwrap();
        a.record(
            T + 1,
            "cli:op",
            "ingest",
            json!({"participant": "p1", "receipts": [1, 2]}),
        )
        .unwrap();
        a.record(T + DAY, "cli:op", "user_added", json!({"user": "mal"}))
            .unwrap();
        let all = a.read_from(T / DAY).unwrap();
        assert_eq!(all.len(), 3);
        assert_eq!(
            all[0],
            json!({"at": "2026-10-22T12:00:00Z", "by": "bob@lab", "action": "token_issued",
                   "user": "bob", "token": "1a2b3c4d5e6f"})
        );
        assert_eq!(all[1]["receipts"], json!([1, 2]));
        assert_eq!(all[1]["participant"], "p1");
        assert_eq!(a.read_from(T / DAY + 1).unwrap()[0]["user"], "mal");
        // Newest first, limited.
        let newest = a.query(0, None, 2).unwrap();
        assert_eq!(newest.len(), 2);
        assert_eq!(newest[0]["user"], "mal");
        a.close().unwrap();
        std::fs::remove_dir_all(&d).ok();
    }

    #[test]
    fn a_scope_lets_through_its_organisation_users_tokens_and_doers() {
        let d = dir("scope");
        let a = Audit::open(&d).unwrap();
        a.record(T, "x@o", "a", json!({"participant": "p1"}))
            .unwrap();
        a.record(T, "x@o", "b", json!({"user": "amy"})).unwrap();
        a.record(T, "x@o", "c", json!({"token": "aaaaaaaaaaaa"}))
            .unwrap();
        a.record(T, "amy@lab", "d", json!({})).unwrap();
        a.record(
            T,
            "x@o",
            "e",
            json!({"participant": "p2", "user": "o'neil"}),
        )
        .unwrap();
        let scope = Scope {
            participant: "p1".into(),
            users: vec!["amy".into()],
            tokens: vec!["aaaaaaaaaaaa".into()],
            by: vec!["amy@lab".into()],
        };
        let mut seen: Vec<String> = a
            .query(0, Some(&scope), 100)
            .unwrap()
            .iter()
            .map(|l| l["action"].as_str().unwrap().to_string())
            .collect();
        seen.sort();
        assert_eq!(seen, ["a", "b", "c", "d"]);
        // Quotes are quoted; no list is an empty `IN ()`.
        let only = Scope {
            participant: "o'x".into(),
            ..Scope::default()
        };
        assert!(a.query(0, Some(&only), 100).unwrap().is_empty());
        a.close().unwrap();
        std::fs::remove_dir_all(&d).ok();
    }

    #[test]
    fn a_second_opener_spools_and_the_holder_drains_it() {
        let d = dir("spool");
        let server = Audit::open(&d).unwrap();
        let cli = Audit::open(&d).unwrap();
        assert!(cli.is_spool());
        cli.record(T, "cli:op", "user_added", json!({"user": "eve"}))
            .unwrap();
        cli.record(T + 1, "cli:op", "user_added", json!({"user": "mal"}))
            .unwrap();
        assert!(cli.read_from(0).is_err());
        assert!(server.read_from(0).unwrap().is_empty());
        assert_eq!(server.drain_spool().unwrap(), 2);
        assert!(!d.join(SPOOL).exists());
        assert_eq!(server.drain_spool().unwrap(), 0);
        let users: Vec<_> = server
            .read_from(0)
            .unwrap()
            .iter()
            .map(|l| l["user"].clone())
            .collect();
        assert_eq!(users, [json!("eve"), json!("mal")]);
        // A drain cut short is finished by the next one.
        cli.record(T + 2, "cli:op", "user_added", json!({"user": "bob"}))
            .unwrap();
        std::fs::rename(d.join(SPOOL), d.join(DRAINING)).unwrap();
        cli.record(T + 3, "cli:op", "user_added", json!({"user": "ann"}))
            .unwrap();
        assert_eq!(server.drain_spool().unwrap(), 1);
        assert_eq!(server.drain_spool().unwrap(), 1);
        assert_eq!(server.read_from(0).unwrap().len(), 4);
        server.close().unwrap();
        drop(server);
        // With the server gone, a command writes the table itself.
        let cli = Audit::open(&d).unwrap();
        assert!(!cli.is_spool());
        std::fs::remove_dir_all(&d).ok();
    }

    static CLOCK: std::sync::atomic::AtomicI64 = std::sync::atomic::AtomicI64::new(T);
    fn clock() -> i64 {
        CLOCK.load(std::sync::atomic::Ordering::SeqCst)
    }

    #[test]
    fn retention_drops_whole_days_at_compaction() {
        use std::sync::atomic::Ordering::SeqCst;
        let d = dir("retention");
        let a = Audit::open_with(&d, None, Some(2), clock).unwrap();
        a.record(T, "x@o", "old", json!({})).unwrap();
        CLOCK.store(T + 3 * DAY, SeqCst);
        a.record(T + 3 * DAY, "x@o", "new", json!({})).unwrap();
        CLOCK.store(T + 4 * DAY, SeqCst);
        a.flush().unwrap();
        a.compact().unwrap();
        let left: Vec<_> = a
            .read_from(0)
            .unwrap()
            .iter()
            .map(|l| l["action"].clone())
            .collect();
        assert_eq!(left, [json!("new")]);
        std::fs::remove_dir_all(&d).ok();
    }

    fn jsonl_days(old: &Path) {
        std::fs::create_dir_all(old).unwrap();
        std::fs::write(
            old.join("2026-10-22.jsonl"),
            "{\"at\":\"2026-10-22T12:00:00Z\",\"by\":\"bob@lab\",\"action\":\"token_issued\",\"user\":\"bob\",\"token\":\"1a2b3c4d5e6f\"}\nnot json\n",
        )
        .unwrap();
        std::fs::write(
            old.join("2026-10-23.jsonl"),
            "{\"at\":\"2026-10-23T08:00:00Z\",\"by\":\"cli:op\",\"action\":\"user_added\",\"user\":\"mal\"}\n",
        )
        .unwrap();
    }

    #[test]
    fn jsonl_files_are_imported_once_and_kept_aside() {
        let d = dir("import-files");
        jsonl_days(&d.join(NAME));
        let a = Audit::open(&d).unwrap();
        let all = a.read_from(0).unwrap();
        assert_eq!(all.len(), 2);
        assert_eq!(all[0]["token"], "1a2b3c4d5e6f");
        assert_eq!(all[1]["user"], "mal");
        assert!(d.join(OLD).join("2026-10-22.jsonl").exists());
        assert!(d.join(OLD).join(IMPORTED).exists());
        a.close().unwrap();
        drop(a);
        // Opened again: not imported twice.
        let a = Audit::open(&d).unwrap();
        assert_eq!(a.read_from(0).unwrap().len(), 2);
        a.close().unwrap();
        drop(a);
        // An import cut short (no marker) goes on where it stopped.
        std::fs::remove_file(d.join(OLD).join(IMPORTED)).unwrap();
        let a = Audit::open(&d).unwrap();
        assert_eq!(a.read_from(0).unwrap().len(), 2);
        std::fs::remove_dir_all(&d).ok();
    }

    #[test]
    fn day_objects_in_a_store_are_imported_once_and_moved_aside() {
        let d = dir("import-store");
        let bucket = d.join("bucket");
        let root = Store::local(&bucket);
        root.put("audit/2026-10-22/0000000000000000001-1-0.jsonl",
            b"{\"at\":\"2026-10-22T12:00:00Z\",\"by\":\"bob@lab\",\"action\":\"token_issued\",\"user\":\"bob\"}\n")
            .unwrap();
        root.put("audit/2026-10-23/0000000000000000002-1-0.jsonl",
            b"{\"at\":\"2026-10-23T08:00:00Z\",\"by\":\"cli:op\",\"action\":\"user_added\",\"user\":\"mal\"}\n")
            .unwrap();
        let location = bucket.to_str().unwrap().to_string();
        let a = Audit::open_in(&d.join("data"), Some(&location), None).unwrap();
        let all = a.read_from(0).unwrap();
        assert_eq!(all.len(), 2);
        assert_eq!(all[0]["user"], "bob");
        let keys = root.list("").unwrap();
        assert!(keys
            .iter()
            .any(|k| k == "audit.jsonl/2026-10-22/0000000000000000001-1-0.jsonl"));
        assert!(!keys.iter().any(|k| key_day(k).is_some()), "{keys:?}");
        // The WAL on this volume; the files, once flushed, in the store.
        assert!(d.join("data").join("s3").join(NAME).exists());
        a.record(T, "x@o", "a", json!({})).unwrap();
        a.close().unwrap();
        drop(a);
        let a = Audit::open_in(&d.join("data"), Some(&location), None).unwrap();
        assert_eq!(a.read_from(0).unwrap().len(), 3);
        std::fs::remove_dir_all(&d).ok();
    }

    #[test]
    fn sub_location_appends_before_the_query() {
        assert_eq!(
            sub_location("s3://b/sightings?endpoint=http://x&region=r", "audit"),
            "s3://b/sightings/audit?endpoint=http://x&region=r"
        );
        assert_eq!(sub_location("/var/bucket/", "audit"), "/var/bucket/audit");
    }
}
