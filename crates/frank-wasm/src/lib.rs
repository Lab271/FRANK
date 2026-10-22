//! FRANK in the browser (ADR-016), compiled to `wasm32-unknown-unknown`:
//!
//! - [`preview`]: the rows a submission would share, computed locally by the
//!   same code the server runs, before anything leaves the browser;
//! - [`Analyst`]: SQL over the `sightings` Parquet files a partner downloaded,
//!   on db-core's column engine, with no server involved.

use std::collections::BTreeMap;

use db_core::engine::column::BatchEngine;
use db_core::engine::{Cell, Engine, FileStats};
use frank_core::Submission;
use serde_json::{json, Value};
use wasm_bindgen::prelude::*;

const TABLE: &str = "sightings";

/// The sighting rows `submission` (JSON, one or an array) would add, as
/// JSON. `now_ms` is the browser's clock (`Date.now()`).
#[wasm_bindgen]
pub fn preview(submission: &str, now_ms: f64) -> Result<String, JsError> {
    preview_rows(submission, now_ms).map_err(|e| JsError::new(&e))
}

fn preview_rows(submission: &str, now_ms: f64) -> Result<String, String> {
    #[allow(clippy::cast_possible_truncation)]
    let now = (now_ms as i64).saturating_mul(1_000_000);
    let v: Value = serde_json::from_str(submission).map_err(|e| e.to_string())?;
    let items = match v {
        Value::Array(a) => a,
        v => vec![v],
    };
    let mut rows = Vec::new();
    for (i, item) in items.iter().enumerate() {
        let s = Submission::from_value(item, now).map_err(|e| format!("[{i}] {e}"))?;
        rows.extend(s.rows("sighting--preview"));
    }
    Ok(json!({ "rows": rows }).to_string())
}

/// Parquet files of the `sightings` table, held in browser memory.
#[wasm_bindgen]
#[derive(Default)]
pub struct Analyst {
    files: Vec<(String, BatchEngine)>,
}

#[wasm_bindgen]
impl Analyst {
    #[wasm_bindgen(constructor)]
    #[must_use]
    pub fn new() -> Analyst {
        Analyst::default()
    }

    /// Adds one Parquet file; returns its row count.
    pub fn add(&mut self, name: &str, bytes: Vec<u8>) -> Result<f64, JsError> {
        self.add_file(name, bytes).map_err(|e| JsError::new(&e))
    }

    #[must_use]
    pub fn len(&self) -> usize {
        self.files.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.files.is_empty()
    }

    /// Runs `sql` (`... FROM sightings ...`) over every file; see [`run`].
    pub fn query(&mut self, sql: &str) -> Result<String, JsError> {
        run(&mut self.files, sql)
            .map(|v| v.to_string())
            .map_err(|e| JsError::new(&e))
    }
}

impl Analyst {
    fn add_file(&mut self, name: &str, bytes: Vec<u8>) -> Result<f64, String> {
        let engine = BatchEngine::from_bytes(TABLE, bytes).map_err(|e| format!("{name}: {e}"))?;
        let rows = match engine.stats() {
            FileStats::Batch { rows, .. } => rows,
            _ => 0,
        };
        self.files.push((name.to_string(), engine));
        #[allow(clippy::cast_precision_loss)]
        Ok(rows as f64)
    }
}

/// How one result column combines across files.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Merge {
    Key,
    Sum,
    Min,
    Max,
}

fn merge_kind(label: &str) -> Option<Merge> {
    let l = label.to_ascii_uppercase();
    if l.starts_with("COUNT(DISTINCT") || l.starts_with("AVG(") {
        None
    } else if l.starts_with("COUNT(") || l.starts_with("SUM(") {
        Some(Merge::Sum)
    } else if l.starts_with("MIN(") {
        Some(Merge::Min)
    } else if l.starts_with("MAX(") {
        Some(Merge::Max)
    } else {
        Some(Merge::Key)
    }
}

/// Runs `sql` on each file. When every aggregate in the result combines
/// exactly across files (`count`, `sum`, `min`, `max`, unaliased), the
/// per-file answers are merged by the other columns into one answer;
/// otherwise the rows are returned per file with a `file` column.
fn run(files: &mut [(String, BatchEngine)], sql: &str) -> Result<Value, String> {
    let mut columns: Vec<String> = Vec::new();
    let mut per_file: Vec<(String, Vec<Vec<Cell>>)> = Vec::new();
    for (name, engine) in files.iter_mut() {
        let r = engine.run_query(sql).map_err(|e| e.to_string())?;
        columns = r.columns;
        per_file.push((name.clone(), r.rows));
    }
    let kinds: Option<Vec<Merge>> = columns.iter().map(|c| merge_kind(c)).collect();
    let mergeable = kinds
        .as_ref()
        .is_some_and(|k| k.iter().any(|m| *m != Merge::Key));
    if let (true, Some(kinds)) = (mergeable && per_file.len() > 1, kinds) {
        let mut groups: BTreeMap<String, Vec<Cell>> = BTreeMap::new();
        for (_, rows) in per_file {
            for row in rows {
                let key: Vec<String> = row
                    .iter()
                    .zip(&kinds)
                    .filter(|(_, k)| **k == Merge::Key)
                    .map(|(c, _)| c.to_string())
                    .collect();
                let key = serde_json::to_string(&key).unwrap_or_default();
                match groups.get_mut(&key) {
                    None => {
                        groups.insert(key, row);
                    }
                    Some(acc) => {
                        for ((a, c), k) in acc.iter_mut().zip(row).zip(&kinds) {
                            *a = combine(a, c, *k);
                        }
                    }
                }
            }
        }
        let rows: Vec<Value> = groups
            .into_values()
            .map(|r| Value::Array(r.iter().map(cell).collect()))
            .collect();
        return Ok(json!({ "merged": true, "columns": columns, "rows": rows }));
    }
    let mut out_cols = vec!["file".to_string()];
    out_cols.extend(columns);
    let rows: Vec<Value> = per_file
        .into_iter()
        .flat_map(|(name, rows)| {
            rows.into_iter().map(move |r| {
                let mut v = vec![json!(name)];
                v.extend(r.iter().map(cell));
                Value::Array(v)
            })
        })
        .collect();
    Ok(json!({ "merged": false, "columns": out_cols, "rows": rows }))
}

fn combine(a: &Cell, b: Cell, kind: Merge) -> Cell {
    match (a, &b, kind) {
        (_, _, Merge::Key) => a.clone(),
        (Cell::Null, _, _) => b,
        (_, Cell::Null, _) => a.clone(),
        (Cell::Int(x), Cell::Int(y), Merge::Sum) => Cell::Int(x + y),
        (Cell::Real(x), Cell::Real(y), Merge::Sum) => Cell::Real(x + y),
        (x, y, Merge::Min) if lt(y, x) => b,
        (x, y, Merge::Max) if lt(x, y) => b,
        _ => a.clone(),
    }
}

fn lt(a: &Cell, b: &Cell) -> bool {
    match (a, b) {
        (Cell::Int(x), Cell::Int(y)) => x < y,
        (Cell::Real(x), Cell::Real(y)) => x < y,
        (Cell::Text(x), Cell::Text(y)) => x < y,
        _ => false,
    }
}

fn cell(c: &Cell) -> Value {
    match c {
        Cell::Null => Value::Null,
        Cell::Int(n) => json!(n),
        Cell::Real(x) => json!(x),
        Cell::Bool(b) => json!(b),
        Cell::Text(s) => json!(s),
        other => json!(other.to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn merge_kinds() {
        assert_eq!(merge_kind("COUNT(*)"), Some(Merge::Sum));
        assert_eq!(merge_kind("SUM(observations)"), Some(Merge::Sum));
        assert_eq!(merge_kind("ioc_type"), Some(Merge::Key));
        assert_eq!(merge_kind("COUNT(DISTINCT sighting_id)"), None);
        assert_eq!(merge_kind("AVG(confidence)"), None);
    }

    #[test]
    fn combines_partial_aggregates() {
        assert_eq!(
            combine(&Cell::Int(2), Cell::Int(3), Merge::Sum),
            Cell::Int(5)
        );
        assert_eq!(
            combine(&Cell::Int(2), Cell::Int(3), Merge::Min),
            Cell::Int(2)
        );
        assert_eq!(
            combine(&Cell::Int(2), Cell::Int(3), Merge::Max),
            Cell::Int(3)
        );
        assert_eq!(combine(&Cell::Null, Cell::Int(3), Merge::Max), Cell::Int(3));
    }

    #[test]
    fn preview_shows_no_identity() {
        let out = preview_rows(include_str!("../../../examples/minimal.json"), 1.8e12).unwrap();
        assert!(out.contains("185.220.102.45"));
        assert!(!out.contains("identity-"));
    }

    /// A small `sightings`-shaped Parquet file: one row per IoC type.
    fn file(types: &[&str]) -> Vec<u8> {
        use db_core::storage::parquet::writer::{
            ColumnSpec, ColumnType, ColumnValues, ParquetWriter, WriterOptions,
        };
        let schema = vec![
            ColumnSpec::new("ts", ColumnType::TimestampNanos, false),
            ColumnSpec::new("ioc_type", ColumnType::Utf8, true),
            ColumnSpec::new("observations", ColumnType::Int64, false),
        ];
        let mut w = ParquetWriter::new(Vec::new(), schema, WriterOptions::default()).unwrap();
        // 2026-10-22 00:00 UTC plus one hour per row.
        let hour = 3_600_000_000_000_i64;
        w.write_columns(vec![
            ColumnValues::TimestampNanos(
                (0..types.len())
                    .map(|i| Some(1_792_627_200_000_000_000 + hour * i as i64))
                    .collect(),
            ),
            ColumnValues::Utf8(types.iter().map(|t| Some((*t).to_string())).collect()),
            ColumnValues::Int64(types.iter().map(|_| Some(2)).collect()),
        ])
        .unwrap();
        w.finish().unwrap().0
    }

    #[test]
    fn merges_exact_aggregates_across_files() {
        let mut a = Analyst::new();
        assert_eq!(
            a.add_file("a", file(&["ipv4", "ipv4", "domain"])).unwrap(),
            3.0
        );
        a.add_file("b", file(&["ipv4", "url"])).unwrap();
        let r = run(
            &mut a.files,
            "SELECT ioc_type, count(*), sum(observations), max(observations) FROM sightings GROUP BY ioc_type",
        )
        .unwrap();
        assert_eq!(r["merged"], true);
        assert_eq!(
            r["rows"],
            json!([["domain", 1, 2, 2], ["ipv4", 3, 6, 2], ["url", 1, 2, 2]])
        );
    }

    #[test]
    fn filters_on_time_literals() {
        let mut a = Analyst::new();
        a.add_file("a", file(&["ipv4", "ipv4", "domain"])).unwrap();
        let r = run(
            &mut a.files,
            "SELECT count(*) FROM sightings WHERE ts >= '2026-10-22T01:00:00Z'",
        )
        .unwrap();
        assert_eq!(r["rows"], json!([["a", 2]]));
    }

    #[test]
    fn distinct_counts_stay_per_file() {
        let mut a = Analyst::new();
        a.add_file("a", file(&["ipv4"])).unwrap();
        a.add_file("b", file(&["ipv4"])).unwrap();
        let r = run(
            &mut a.files,
            "SELECT count(DISTINCT ioc_type) FROM sightings",
        )
        .unwrap();
        assert_eq!(r["merged"], false);
        assert_eq!(r["rows"], json!([["a", 1], ["b", 1]]));
        assert!(a.add_file("bad", vec![1, 2, 3]).is_err());
    }
}
