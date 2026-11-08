//! The audit log (#159): who did what, one JSON line per action in
//! `<data>/audit/YYYY-MM-DD.jsonl` (UTC). Append-only: each line is one
//! write to a file opened for appending, so the server and the CLI can
//! both write without a lock. Whole days are dropped with the sightings'
//! retention.
//!
//! With `FRANK_STORE` (#220) the lines go to the object store instead, one
//! object per line under `audit/YYYY-MM-DD/`, since S3 cannot append.
//!
//! It names users, which the shared Parquet files never do, and never a
//! token: a token appears as the first 12 hex digits of its hash.

use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

use db_core::storage::ingest::{Store, TableStore};
use serde_json::{json, Value};
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

pub const DIR: &str = "audit";

/// Where the lines go: a file a day, or, in an object store (#220), one
/// object per line, since S3 cannot append.
#[derive(Debug, Clone)]
enum Backend {
    Dir(PathBuf),
    /// Keys `audit/YYYY-MM-DD/<ns>-<pid>-<n>.jsonl`; the zero-padded
    /// nanoseconds make the sorted listing the order of the lines.
    Store(Store, Arc<AtomicU64>),
}

#[derive(Debug, Clone)]
pub struct Audit {
    backend: Backend,
}

impl Audit {
    /// The log under `<data>/audit`, created if needed.
    pub fn open(data: &Path) -> Result<Audit, String> {
        Audit::open_in(data, None)
    }

    /// [`Audit::open`], or, given a `store` (`FRANK_STORE`), the log in it
    /// under `audit/`.
    pub fn open_in(data: &Path, store: Option<Store>) -> Result<Audit, String> {
        if let Some(store) = store {
            return Ok(Audit {
                backend: Backend::Store(store, Arc::default()),
            });
        }
        let dir = data.join(DIR);
        std::fs::create_dir_all(&dir).map_err(|e| format!("{}: {e}", dir.display()))?;
        Ok(Audit {
            backend: Backend::Dir(dir),
        })
    }

    /// Appends `{"at", "by", "action", ...fields}` at `now_ns`. `by` is
    /// `user@organisation`, or `cli:<os user>` for the command line.
    pub fn record(&self, now_ns: i64, by: &str, action: &str, fields: Value) -> Result<(), String> {
        let at = OffsetDateTime::from_unix_timestamp_nanos(i128::from(now_ns))
            .map_err(|e| e.to_string())?;
        let mut line = json!({
            "at": at.format(&Rfc3339).map_err(|e| e.to_string())?,
            "by": by,
            "action": action,
        });
        if let (Some(line), Value::Object(fields)) = (line.as_object_mut(), fields) {
            line.extend(fields);
        }
        let mut bytes = serde_json::to_vec(&line).map_err(|e| e.to_string())?;
        bytes.push(b'\n');
        match &self.backend {
            Backend::Dir(dir) => {
                let path = dir.join(format!("{}.jsonl", at.date()));
                let mut f = std::fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(&path)
                    .map_err(|e| format!("{}: {e}", path.display()))?;
                f.write_all(&bytes)
                    .and_then(|()| f.sync_data())
                    .map_err(|e| format!("{}: {e}", path.display()))
            }
            Backend::Store(store, n) => {
                let key = format!(
                    "{DIR}/{}/{now_ns:019}-{}-{}.jsonl",
                    at.date(),
                    std::process::id(),
                    n.fetch_add(1, Ordering::Relaxed)
                );
                store.put(&key, &bytes).map_err(|e| format!("{key}: {e}"))
            }
        }
    }

    /// The lines of the days from `from_day` (days since the epoch) on,
    /// oldest first. A line that is not JSON is skipped.
    pub fn read_from(&self, from_day: i64) -> Result<Vec<Value>, String> {
        let mut out = Vec::new();
        match &self.backend {
            Backend::Dir(dir) => {
                let mut days: Vec<(i64, PathBuf)> = std::fs::read_dir(dir)
                    .map_err(|e| e.to_string())?
                    .flatten()
                    .filter_map(|e| Some((day_of(e.file_name().to_str()?)?, e.path())))
                    .filter(|(d, _)| *d >= from_day)
                    .collect();
                days.sort();
                for (_, path) in days {
                    let text = std::fs::read_to_string(&path)
                        .map_err(|e| format!("{}: {e}", path.display()))?;
                    out.extend(text.lines().filter_map(|l| serde_json::from_str(l).ok()));
                }
            }
            Backend::Store(store, _) => {
                for key in keys(store)? {
                    if key_day(&key).is_some_and(|d| d >= from_day) {
                        // Gone since the listing: dropped by retention.
                        let Some(bytes) = store.get(&key).map_err(|e| format!("{key}: {e}"))?
                        else {
                            continue;
                        };
                        out.extend(
                            String::from_utf8_lossy(&bytes)
                                .lines()
                                .filter_map(|l| serde_json::from_str(l).ok()),
                        );
                    }
                }
            }
        }
        Ok(out)
    }

    /// Drops the days before `keep_from_day` (days since the epoch).
    pub fn retain_from(&self, keep_from_day: i64) -> Result<(), String> {
        match &self.backend {
            Backend::Dir(dir) => {
                let entries = std::fs::read_dir(dir).map_err(|e| e.to_string())?;
                for entry in entries.flatten() {
                    if entry
                        .file_name()
                        .to_str()
                        .and_then(day_of)
                        .is_some_and(|d| d < keep_from_day)
                    {
                        std::fs::remove_file(entry.path()).map_err(|e| e.to_string())?;
                    }
                }
            }
            Backend::Store(store, _) => {
                for key in keys(store)? {
                    if key_day(&key).is_some_and(|d| d < keep_from_day) {
                        store.delete(&key).map_err(|e| format!("{key}: {e}"))?;
                    }
                }
            }
        }
        Ok(())
    }
}

/// The objects of the log, sorted: oldest first.
fn keys(store: &Store) -> Result<Vec<String>, String> {
    store
        .list(&format!("{DIR}/"))
        .map_err(|e| format!("{DIR}/: {e}"))
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

    #[test]
    fn lines_append_per_day_and_expire() {
        let dir = std::env::temp_dir().join(format!("frank-audit-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let a = Audit::open(&dir).unwrap();
        let t = 1_792_670_400 * 1_000_000_000; // 2026-10-22T12:00:00Z
        a.record(
            t,
            "bob@lab",
            "token_issued",
            json!({"user": "bob", "token": "1a2b3c4d5e6f"}),
        )
        .unwrap();
        a.record(t + 1, "cli:op", "user_added", json!({"user": "eve"}))
            .unwrap();
        a.record(t + DAY, "cli:op", "user_added", json!({"user": "mal"}))
            .unwrap();
        let day = std::fs::read_to_string(dir.join(DIR).join("2026-10-22.jsonl")).unwrap();
        let lines: Vec<Value> = day
            .lines()
            .map(|l| serde_json::from_str(l).unwrap())
            .collect();
        assert_eq!(lines.len(), 2);
        assert_eq!(lines[0]["at"], "2026-10-22T12:00:00Z");
        assert_eq!(lines[0]["by"], "bob@lab");
        assert_eq!(lines[1]["action"], "user_added");
        assert_eq!(a.read_from(t / DAY).unwrap().len(), 3);
        assert_eq!(a.read_from(t / DAY + 1).unwrap()[0]["user"], "mal");
        a.retain_from(t / DAY + 1).unwrap();
        assert!(!dir.join(DIR).join("2026-10-22.jsonl").exists());
        assert!(dir.join(DIR).join("2026-10-23.jsonl").exists());
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn in_a_store_one_object_per_line_ordered_and_expiring() {
        let dir = std::env::temp_dir().join(format!("frank-audit-store-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let store = Store::local(dir.join("bucket"));
        let a = Audit::open_in(&dir, Some(store)).unwrap();
        let b = a.clone();
        let t = 1_792_670_400 * 1_000_000_000;
        // Two writers in the same nanosecond keep both lines.
        a.record(t + DAY, "cli:op", "user_added", json!({"user": "mal"}))
            .unwrap();
        a.record(t, "bob@lab", "token_issued", json!({"user": "bob"}))
            .unwrap();
        b.record(t, "cli:op", "user_added", json!({"user": "eve"}))
            .unwrap();
        let all = a.read_from(t / DAY).unwrap();
        assert_eq!(all.len(), 3);
        assert_eq!(all[0]["user"], "bob");
        assert_eq!(all[1]["user"], "eve");
        assert_eq!(all[2]["user"], "mal");
        assert_eq!(a.read_from(t / DAY + 1).unwrap().len(), 1);
        a.retain_from(t / DAY + 1).unwrap();
        let left = a.read_from(0).unwrap();
        assert_eq!(left.len(), 1);
        assert_eq!(left[0]["user"], "mal");
        std::fs::remove_dir_all(&dir).ok();
    }
}
