//! The `iocs` row table: one row per IoC per day it was seen, in a
//! db-core row (SQLite-format) database with B-tree indexes, so "is this
//! IoC known?" is an index seek instead of a scan of the sightings.
//!
//! The schema keeps to what db-core's row engine plans and enforces today
//! (see db-core #694-#696): a rowid table, single-column keys
//! (`k = type:value`, `kd = k|day`, a UNIQUE index as the upsert target),
//! IP addresses as 32 hex digits, and upsert as SELECT then UPDATE or
//! INSERT.
//!
//! `RowEngine` is single-threaded, so one thread owns it and the rest of
//! the server sends it jobs.

use std::collections::BTreeMap;
use std::path::Path;
use std::sync::mpsc;
use std::thread;

use db_core::engine::row::RowEngine;
use db_core::engine::{Cell, Engine, QueryResult};
use db_core::storage::row::header::DatabaseHeader;
use frank_core::{sql_quote, Ioc, SightingRow, Tlp};
use serde::Serialize;

pub const FILE: &str = "iocs.db";
const DAY_NS: i64 = 86_400 * 1_000_000_000;

const SCHEMA: [&str; 5] = [
    "CREATE TABLE ioc_day (k TEXT NOT NULL, kd TEXT NOT NULL, ioc_type TEXT NOT NULL, \
     value TEXT NOT NULL, day INTEGER NOT NULL, tlp TEXT NOT NULL, ip_hex TEXT, \
     first_ts INTEGER NOT NULL, last_ts INTEGER NOT NULL, n INTEGER NOT NULL)",
    "CREATE INDEX ioc_day_k ON ioc_day (k)",
    "CREATE UNIQUE INDEX ioc_day_kd ON ioc_day (kd)",
    "CREATE INDEX ioc_day_ip ON ioc_day (ip_hex)",
    "CREATE INDEX ioc_day_day ON ioc_day (day)",
];

/// What the `iocs` table knows of one IoC on one day.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct IocDay {
    pub day: String,
    pub first_ts: i64,
    pub last_ts: i64,
    pub count: i64,
}

type Job = Box<dyn FnOnce(&mut RowEngine) + Send>;

/// A handle to the thread that owns the database.
#[derive(Clone)]
pub struct Iocs {
    jobs: mpsc::Sender<Job>,
}

impl Iocs {
    /// Opens `data/iocs.db`, creating it and its schema if needed.
    pub fn open(data: &Path) -> Result<Iocs, String> {
        let path = data.join(FILE);
        let fresh = !path.exists() || std::fs::metadata(&path).map_err(err)?.len() == 0;
        if fresh {
            std::fs::write(&path, DatabaseHeader::new_empty_page1(4096)).map_err(err)?;
        }
        let (ready_tx, ready_rx) = mpsc::channel();
        let (jobs, rx) = mpsc::channel::<Job>();
        thread::Builder::new()
            .name("iocs".into())
            .spawn(move || owner(&path, fresh, &ready_tx, &rx))
            .map_err(err)?;
        ready_rx.recv().map_err(err)??;
        Ok(Iocs { jobs })
    }

    /// Runs `f` on the database thread and waits for its answer.
    fn run<T: Send + 'static>(
        &self,
        f: impl FnOnce(&mut RowEngine) -> Result<T, String> + Send + 'static,
    ) -> Result<T, String> {
        let (tx, rx) = mpsc::channel();
        self.jobs
            .send(Box::new(move |db| {
                let _ = tx.send(f(db));
            }))
            .map_err(|_| "iocs thread stopped".to_string())?;
        rx.recv().map_err(|_| "iocs thread stopped".to_string())?
    }

    /// Counts `rows` into their IoCs' days, in one transaction. Each TLP
    /// level counts separately, so a lookup shows a tier only what it may
    /// see (#149).
    pub fn record(&self, rows: &[SightingRow]) -> Result<(), String> {
        // (key, day, tlp) -> (ioc, first, last, count): one upsert each.
        type Key = (String, i64, Tlp);
        let mut agg: BTreeMap<Key, (Ioc, i64, i64, i64)> = BTreeMap::new();
        for r in rows {
            let (Some(t), Some(v)) = (r.ioc_type, r.ioc_value.clone()) else {
                continue;
            };
            let ioc = Ioc {
                ioc_type: t,
                value: v,
            };
            let e = agg
                .entry((ioc.key(), r.ts_ns.div_euclid(DAY_NS), r.tlp))
                .or_insert((ioc, r.ts_ns, r.ts_ns, 0));
            e.1 = e.1.min(r.ts_ns);
            e.2 = e.2.max(r.ts_ns);
            e.3 += i64::from(r.observations);
        }
        if agg.is_empty() {
            return Ok(());
        }
        self.run(move |db| {
            exec(db, "BEGIN")?;
            let result = (|| {
                for (key, value) in &agg {
                    upsert(db, key, value)?;
                }
                Ok(())
            })();
            match result {
                Ok(()) => exec(db, "COMMIT"),
                Err(e) => {
                    let _ = exec(db, "ROLLBACK");
                    Err(e)
                }
            }
        })
    }

    /// Every retained day `ioc` was seen on at the `visible` TLP levels,
    /// oldest first. The key is an index seek; TLP is filtered here, as
    /// the row engine plans one indexed predicate (db-core #695).
    pub fn lookup(&self, ioc: &Ioc, visible: &[Tlp]) -> Result<Vec<IocDay>, String> {
        let sql = format!(
            "SELECT day, first_ts, last_ts, n, tlp FROM ioc_day WHERE k = {}",
            sql_quote(&ioc.key())
        );
        let visible = levels(visible);
        self.run(move |db| {
            let r = query(db, &sql)?;
            let mut days: BTreeMap<i64, IocDay> = BTreeMap::new();
            for row in r.rows.iter().filter(|row| shown(&row[4], &visible)) {
                let day = int(&row[0]);
                let d = days.entry(day).or_insert_with(|| IocDay {
                    day: day_label(day),
                    first_ts: i64::MAX,
                    last_ts: i64::MIN,
                    count: 0,
                });
                d.first_ts = d.first_ts.min(int(&row[1]));
                d.last_ts = d.last_ts.max(int(&row[2]));
                d.count += int(&row[3]);
            }
            Ok(days.into_values().collect())
        })
    }

    /// IP addresses seen in `[lo, hi]` (32-hex-digit form), with counts.
    pub fn ip_range(
        &self,
        lo: &str,
        hi: &str,
        visible: &[Tlp],
        limit: usize,
    ) -> Result<Vec<(String, i64)>, String> {
        let sql = format!(
            "SELECT value, n, tlp FROM ioc_day WHERE ip_hex BETWEEN {} AND {}",
            sql_quote(lo),
            sql_quote(hi)
        );
        let visible = levels(visible);
        self.run(move |db| {
            let r = query(db, &sql)?;
            let mut by_value: BTreeMap<String, i64> = BTreeMap::new();
            for row in r.rows.iter().filter(|row| shown(&row[2], &visible)) {
                if let Cell::Text(v) = &row[0] {
                    *by_value.entry(v.clone()).or_default() += int(&row[1]);
                }
            }
            Ok(by_value.into_iter().take(limit).collect())
        })
    }

    /// Distinct IoCs over the retained days, at the `visible` TLP levels.
    pub fn count(&self, visible: &[Tlp]) -> Result<i64, String> {
        let visible = levels(visible);
        self.run(move |db| {
            let r = query(db, "SELECT k, tlp FROM ioc_day")?;
            let keys: std::collections::BTreeSet<String> = r
                .rows
                .iter()
                .filter(|row| shown(&row[1], &visible))
                .map(|row| row[0].to_string())
                .collect();
            Ok(i64::try_from(keys.len()).unwrap_or(i64::MAX))
        })
    }

    /// Drops the days before `keep_from_day` (days since the epoch), as
    /// the sightings table's retention drops them.
    pub fn retain_from(&self, keep_from_day: i64) -> Result<(), String> {
        self.run(move |db| {
            exec(
                db,
                &format!("DELETE FROM ioc_day WHERE day < {keep_from_day}"),
            )
        })
    }

    /// Empties the table, for a rebuild from `sightings`.
    pub fn clear(&self) -> Result<(), String> {
        self.run(|db| exec(db, "DELETE FROM ioc_day"))
    }
}

fn owner(
    path: &Path,
    fresh: bool,
    ready: &mpsc::Sender<Result<(), String>>,
    jobs: &mpsc::Receiver<Job>,
) {
    let mut db = match RowEngine::open(path).map_err(err) {
        Ok(db) => db,
        Err(e) => {
            let _ = ready.send(Err(e));
            return;
        }
    };
    if fresh {
        for ddl in SCHEMA {
            if let Err(e) = exec(&mut db, ddl) {
                let _ = ready.send(Err(e));
                return;
            }
        }
    } else if query(&mut db, "SELECT tlp FROM ioc_day LIMIT 1").is_err() {
        let _ = ready.send(Err(format!(
            "{} predates TLP (#149): delete it and run `frank rebuild-iocs`",
            path.display()
        )));
        return;
    }
    let _ = ready.send(Ok(()));
    while let Ok(job) = jobs.recv() {
        job(&mut db);
    }
}

fn upsert(
    db: &mut RowEngine,
    (k, day, tlp): &(String, i64, Tlp),
    (ioc, first, last, n): &(Ioc, i64, i64, i64),
) -> Result<(), String> {
    let (day, tlp, first, last, n) = (*day, *tlp, *first, *last, *n);
    let kd = sql_quote(&format!("{k}|{day}|{tlp}"));
    let found = query(
        db,
        &format!("SELECT first_ts, last_ts, n FROM ioc_day WHERE kd = {kd}"),
    )?;
    if let Some(row) = found.rows.first() {
        let sql = format!(
            "UPDATE ioc_day SET first_ts = {}, last_ts = {}, n = {} WHERE kd = {kd}",
            first.min(int(&row[0])),
            last.max(int(&row[1])),
            n + int(&row[2]),
        );
        exec(db, &sql)
    } else {
        let ip = ioc.ip_hex().map_or("NULL".to_string(), |h| sql_quote(&h));
        let sql = format!(
            "INSERT INTO ioc_day (k, kd, ioc_type, value, day, tlp, ip_hex, first_ts, last_ts, n) \
             VALUES ({}, {kd}, {}, {}, {day}, {}, {ip}, {first}, {last}, {n})",
            sql_quote(k),
            sql_quote(ioc.ioc_type.as_str()),
            sql_quote(&ioc.value),
            sql_quote(tlp.as_str()),
        );
        exec(db, &sql)
    }
}

fn query(db: &mut RowEngine, sql: &str) -> Result<QueryResult, String> {
    db.run_query(sql).map_err(|e| format!("{e}: {sql}"))
}

fn exec(db: &mut RowEngine, sql: &str) -> Result<(), String> {
    query(db, sql).map(|_| ())
}

/// The `visible` levels as stored text.
fn levels(visible: &[Tlp]) -> Vec<&'static str> {
    visible.iter().map(|t| t.as_str()).collect()
}

/// Whether a stored `tlp` cell is one of `visible`.
fn shown(tlp: &Cell, visible: &[&str]) -> bool {
    matches!(tlp, Cell::Text(t) if visible.contains(&t.as_str()))
}

fn int(c: &Cell) -> i64 {
    match c {
        Cell::Int(n) => *n,
        _ => 0,
    }
}

/// Days since the epoch as `YYYY-MM-DD`.
pub fn day_label(day: i64) -> String {
    time::OffsetDateTime::from_unix_timestamp(day * 86_400)
        .map(|t| t.date().to_string())
        .unwrap_or_default()
}

fn err(e: impl std::fmt::Display) -> String {
    e.to_string()
}
