//! The `entry` row table (#192, #193): IoC lists FRANK annotates with,
//! kept apart from `sightings`, which they never change. A `warning` list
//! marks common infrastructure (public DNS, CDNs); a `reference` list says
//! what an outside source lists (abuse.ch). Both are imported from files
//! under `data/lists/`; each import replaces that list's entries.
//!
//! An entry matches an IoC by kind:
//! - `exact`: the IoC's value (addresses normalised as FRANK stores them);
//! - `cidr`: an address in `[lo_hex, hi_hex]`, 32 hex digits as in `iocs.db`;
//! - `hostname`: a domain, URL or e-mail host equal to the value or under it.

use std::collections::BTreeMap;
use std::path::Path;

use db_core::engine::row::RowEngine;
use frank_core::sql_quote;
use serde::Serialize;

use super::rowdb::{exec, int, query, text, transaction, RowDb};

pub const FILE: &str = "lists.db";

// Ranges have their own table, so a range lookup scans ranges only.
const SCHEMA: [&str; 7] = [
    "CREATE TABLE entry (kind TEXT NOT NULL, list TEXT NOT NULL, source TEXT NOT NULL, \
     value TEXT NOT NULL, mtype TEXT NOT NULL, tags TEXT, first_listed INTEGER, \
     imported INTEGER NOT NULL)",
    "CREATE INDEX entry_value ON entry (value)",
    "CREATE INDEX entry_list ON entry (list)",
    "CREATE TABLE cidr_entry (kind TEXT NOT NULL, list TEXT NOT NULL, source TEXT NOT NULL, \
     value TEXT NOT NULL, lo_hex TEXT NOT NULL, hi_hex TEXT NOT NULL, tags TEXT, \
     first_listed INTEGER, imported INTEGER NOT NULL)",
    "CREATE INDEX cidr_entry_lo ON cidr_entry (lo_hex)",
    "CREATE INDEX cidr_entry_list ON cidr_entry (list)",
    "CREATE TABLE list_file (path TEXT NOT NULL, stamp INTEGER NOT NULL, entries INTEGER NOT NULL)",
];

/// One entry of a list.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Entry {
    /// `exact`, `cidr` or `hostname`.
    pub mtype: &'static str,
    pub value: String,
    /// For `cidr`: the first and last address, 32 hex digits.
    pub range: Option<(String, String)>,
    pub tags: Option<String>,
    pub first_listed: Option<i64>,
}

/// What a list says about an IoC.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Listed {
    /// `warning` or `reference`.
    pub kind: String,
    pub list: String,
    pub source: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tags: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub first_listed: Option<i64>,
}

/// A handle to the thread that owns the database.
#[derive(Clone)]
pub struct ListDb {
    db: RowDb,
}

impl ListDb {
    pub fn open(data: &Path) -> Result<ListDb, String> {
        let db = RowDb::open(&data.join(FILE), "lists", |db, fresh| {
            if fresh {
                SCHEMA.iter().try_for_each(|ddl| exec(db, ddl))
            } else {
                Ok(())
            }
        })?;
        Ok(ListDb { db })
    }

    /// Replaces list `list` (of `kind`, from `source`) with `entries`, and
    /// records `path` at `stamp` as imported, in one transaction.
    #[allow(clippy::too_many_arguments)]
    pub fn replace(
        &self,
        kind: &'static str,
        list: String,
        source: String,
        entries: Vec<Entry>,
        path: String,
        stamp: i64,
        now: i64,
    ) -> Result<(), String> {
        self.db.run(move |db| {
            transaction(db, |db| {
                drop_list(db, &list)?;
                exec(db, &format!("DELETE FROM list_file WHERE path = {}", sql_quote(&path)))?;
                for e in &entries {
                    let head = format!(
                        "{}, {}, {}, {}",
                        sql_quote(kind),
                        sql_quote(&list),
                        sql_quote(&source),
                        sql_quote(&e.value)
                    );
                    let tail = format!(
                        "{}, {}, {now}",
                        e.tags.as_deref().map_or("NULL".into(), sql_quote),
                        e.first_listed.map_or("NULL".into(), |t| t.to_string()),
                    );
                    let sql = match &e.range {
                        Some((lo, hi)) => format!(
                            "INSERT INTO cidr_entry (kind, list, source, value, lo_hex, hi_hex, tags, \
                             first_listed, imported) VALUES ({head}, {}, {}, {tail})",
                            sql_quote(lo),
                            sql_quote(hi)
                        ),
                        None => format!(
                            "INSERT INTO entry (kind, list, source, value, mtype, tags, first_listed, \
                             imported) VALUES ({head}, {}, {tail})",
                            sql_quote(e.mtype)
                        ),
                    };
                    exec(db, &sql)?;
                }
                exec(
                    db,
                    &format!(
                        "INSERT INTO list_file (path, stamp, entries) VALUES ({}, {stamp}, {})",
                        sql_quote(&path),
                        entries.len()
                    ),
                )
            })
        })
    }

    /// The imported files: path → stamp.
    pub fn files(&self) -> Result<BTreeMap<String, i64>, String> {
        self.db.run(|db| {
            Ok(query(db, "SELECT path, stamp FROM list_file")?
                .rows
                .iter()
                .map(|r| (text(&r[0]), int(&r[1])))
                .collect())
        })
    }

    /// Drops `list` and the record of `path`, for a file that went away.
    pub fn remove(&self, list: String, path: String) -> Result<(), String> {
        self.db.run(move |db| {
            transaction(db, |db| {
                drop_list(db, &list)?;
                exec(
                    db,
                    &format!("DELETE FROM list_file WHERE path = {}", sql_quote(&path)),
                )
            })
        })
    }

    /// The entries matching each probe, by probe index. A probe is the
    /// values to try exactly, the host names to try (the host and each
    /// parent domain), and an address as 32 hex digits.
    pub fn matches(&self, probes: Vec<Probe>) -> Result<Vec<Vec<Listed>>, String> {
        self.db.run(move |db| {
            probes
                .iter()
                .map(|p| {
                    // One index seek per value; ranges from their own table.
                    let mut out = Vec::new();
                    for (mtype, values) in [("exact", &p.exact), ("hostname", &p.hosts)] {
                        for v in values {
                            let cond = format!(
                                "value = {} AND mtype = {}",
                                sql_quote(v),
                                sql_quote(mtype)
                            );
                            out.extend(listed(db, "entry", &cond)?);
                        }
                    }
                    if let Some(h) = &p.ip_hex {
                        let h = sql_quote(h);
                        let cond = format!("lo_hex <= {h} AND hi_hex >= {h}");
                        out.extend(listed(db, "cidr_entry", &cond)?);
                    }
                    out.sort_by(|a, b| (&a.kind, &a.list).cmp(&(&b.kind, &b.list)));
                    out.dedup_by(|a, b| a.kind == b.kind && a.list == b.list);
                    Ok(out)
                })
                .collect()
        })
    }

    /// Entries per list, for `/health`.
    pub fn counts(&self) -> Result<Vec<(String, String, i64)>, String> {
        self.db.run(|db| {
            let mut counts: BTreeMap<(String, String), i64> = BTreeMap::new();
            for table in ["entry", "cidr_entry"] {
                let sql = format!("SELECT kind, list, count(*) FROM {table} GROUP BY kind, list");
                for r in query(db, &sql)?.rows {
                    *counts.entry((text(&r[0]), text(&r[1]))).or_default() += int(&r[2]);
                }
            }
            Ok(counts.into_iter().map(|((k, l), n)| (k, l, n)).collect())
        })
    }
}

/// What to look up for one IoC; see [`ListDb::matches`].
#[derive(Clone, Debug, Default)]
pub struct Probe {
    pub exact: Vec<String>,
    pub hosts: Vec<String>,
    pub ip_hex: Option<String>,
}

fn drop_list(db: &mut RowEngine, list: &str) -> Result<(), String> {
    exec(
        db,
        &format!("DELETE FROM entry WHERE list = {}", sql_quote(list)),
    )?;
    exec(
        db,
        &format!("DELETE FROM cidr_entry WHERE list = {}", sql_quote(list)),
    )
}

fn listed(db: &mut RowEngine, table: &str, cond: &str) -> Result<Vec<Listed>, String> {
    let sql =
        format!("SELECT kind, list, source, tags, first_listed FROM {table} WHERE {cond} LIMIT 20");
    Ok(query(db, &sql)?
        .rows
        .iter()
        .map(|r| Listed {
            kind: text(&r[0]),
            list: text(&r[1]),
            source: text(&r[2]),
            tags: Some(text(&r[3])).filter(|t| !t.is_empty()),
            first_listed: match r[4] {
                db_core::engine::Cell::Int(t) => Some(t),
                _ => None,
            },
        })
        .collect())
}
