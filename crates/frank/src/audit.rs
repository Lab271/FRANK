//! The audit log (#159): who did what, one JSON line per action in
//! `<data>/audit/YYYY-MM-DD.jsonl` (UTC). Append-only: each line is one
//! write to a file opened for appending, so the server and the CLI can
//! both write without a lock. Whole days are dropped with the sightings'
//! retention.
//!
//! It names users, which the shared Parquet files never do, and never a
//! token: a token appears as the first 12 hex digits of its hash.

use std::io::Write;
use std::path::{Path, PathBuf};

use serde_json::{json, Value};
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

pub const DIR: &str = "audit";

#[derive(Debug, Clone)]
pub struct Audit {
    dir: PathBuf,
}

impl Audit {
    /// The log under `<data>/audit`, created if needed.
    pub fn open(data: &Path) -> Result<Audit, String> {
        let dir = data.join(DIR);
        std::fs::create_dir_all(&dir).map_err(|e| format!("{}: {e}", dir.display()))?;
        Ok(Audit { dir })
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
        let path = self.dir.join(format!("{}.jsonl", at.date()));
        let mut f = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .map_err(|e| format!("{}: {e}", path.display()))?;
        f.write_all(&bytes)
            .and_then(|()| f.sync_data())
            .map_err(|e| format!("{}: {e}", path.display()))
    }

    /// Drops the days before `keep_from_day` (days since the epoch).
    pub fn retain_from(&self, keep_from_day: i64) -> Result<(), String> {
        let entries = std::fs::read_dir(&self.dir).map_err(|e| e.to_string())?;
        for entry in entries.flatten() {
            let name = entry.file_name();
            let Some(day) = name
                .to_str()
                .and_then(|n| n.strip_suffix(".jsonl"))
                .and_then(|d| {
                    time::Date::parse(d, time::macros::format_description!("[year]-[month]-[day]"))
                        .ok()
                })
            else {
                continue;
            };
            if day
                .midnight()
                .assume_utc()
                .unix_timestamp()
                .div_euclid(86_400)
                < keep_from_day
            {
                std::fs::remove_file(entry.path()).map_err(|e| e.to_string())?;
            }
        }
        Ok(())
    }
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
        a.retain_from(t / DAY + 1).unwrap();
        assert!(!dir.join(DIR).join("2026-10-22.jsonl").exists());
        assert!(dir.join(DIR).join("2026-10-23.jsonl").exists());
        std::fs::remove_dir_all(&dir).ok();
    }
}
