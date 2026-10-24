//! A db-core row database (SQLite format) owned by one thread.
//!
//! `RowEngine` is single-threaded (`Rc` inside), so one thread owns it
//! and the rest of the server sends it jobs. The file uses SQLite's own
//! locking and journal, so `sqlite3` and other processes can open it too.

use std::path::Path;
use std::sync::mpsc;
use std::thread;

use db_core::engine::row::RowEngine;
use db_core::engine::{Cell, Engine, QueryResult};
use db_core::storage::row::header::DatabaseHeader;

type Job = Box<dyn FnOnce(&mut RowEngine) + Send>;

/// A handle to the thread that owns one database file.
#[derive(Clone)]
pub struct RowDb {
    jobs: mpsc::Sender<Job>,
    name: &'static str,
}

impl RowDb {
    /// Opens `path` on a thread named `name`, creating the file if needed.
    /// `init` runs first, with `true` for a new file (create the schema)
    /// or `false` for an existing one (check it).
    pub fn open(
        path: &Path,
        name: &'static str,
        init: impl FnOnce(&mut RowEngine, bool) -> Result<(), String> + Send + 'static,
    ) -> Result<RowDb, String> {
        let path = path.to_path_buf();
        let (ready_tx, ready_rx) = mpsc::channel();
        let (jobs, rx) = mpsc::channel::<Job>();
        thread::Builder::new()
            .name(name.into())
            .spawn(move || {
                let mut db = match open_engine(&path).and_then(|(mut db, fresh)| {
                    init(&mut db, fresh)?;
                    Ok(db)
                }) {
                    Ok(db) => db,
                    Err(e) => {
                        let _ = ready_tx.send(Err(e));
                        return;
                    }
                };
                let _ = ready_tx.send(Ok(()));
                while let Ok(job) = rx.recv() {
                    job(&mut db);
                }
            })
            .map_err(err)?;
        ready_rx.recv().map_err(err)??;
        Ok(RowDb { jobs, name })
    }

    /// Runs `f` on the database thread and waits for its answer.
    pub fn run<T: Send + 'static>(
        &self,
        f: impl FnOnce(&mut RowEngine) -> Result<T, String> + Send + 'static,
    ) -> Result<T, String> {
        let (tx, rx) = mpsc::channel();
        let stopped = || format!("{} thread stopped", self.name);
        self.jobs
            .send(Box::new(move |db| {
                let _ = tx.send(f(db));
            }))
            .map_err(|_| stopped())?;
        rx.recv().map_err(|_| stopped())?
    }
}

/// Opens `path` as a row database, creating an empty one if it is missing
/// or empty; `true` when it was created.
pub fn open_engine(path: &Path) -> Result<(RowEngine, bool), String> {
    let fresh = !path.exists() || std::fs::metadata(path).map_err(err)?.len() == 0;
    if fresh {
        std::fs::write(path, DatabaseHeader::new_empty_page1(4096)).map_err(err)?;
    }
    let db = RowEngine::open(path).map_err(|e| format!("{}: {e}", path.display()))?;
    Ok((db, fresh))
}

/// `f` inside BEGIN/COMMIT, rolled back on an error.
pub fn transaction<T>(
    db: &mut RowEngine,
    f: impl FnOnce(&mut RowEngine) -> Result<T, String>,
) -> Result<T, String> {
    exec(db, "BEGIN")?;
    match f(db) {
        Ok(v) => exec(db, "COMMIT").map(|()| v),
        Err(e) => {
            let _ = exec(db, "ROLLBACK");
            Err(e)
        }
    }
}

pub fn query(db: &mut RowEngine, sql: &str) -> Result<QueryResult, String> {
    db.run_query(sql).map_err(|e| format!("{e}: {sql}"))
}

pub fn exec(db: &mut RowEngine, sql: &str) -> Result<(), String> {
    query(db, sql).map(|_| ())
}

pub fn int(c: &Cell) -> i64 {
    match c {
        Cell::Int(n) => *n,
        _ => 0,
    }
}

/// A text cell, or empty.
pub fn text(c: &Cell) -> String {
    match c {
        Cell::Text(t) => t.clone(),
        _ => String::new(),
    }
}

pub fn err(e: impl std::fmt::Display) -> String {
    e.to_string()
}
