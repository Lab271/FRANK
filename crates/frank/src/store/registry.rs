//! The registration index (#159): which participant registered which
//! sighting id with what content. The sender's `(participant,
//! sighting_id)` is the registration: sending the same sighting again is
//! answered with the original receipt, sending other content under a
//! registered id is refused (corrections: #161).
//!
//! The registration itself lives in the sightings (`reporter`,
//! `sighting_id`, `digest`, `received`); this table only makes the check
//! one index seek per id, where a scan of the Parquet costs seconds (P9a
//! on #159). It is rebuilt from the sightings ([`rebuild`]), and rows are
//! dropped with the sightings' retention (by arrival day). Which user
//! sent what is in neither: that is the audit log's.

use std::collections::HashMap;
use std::path::Path;

use db_core::engine::row::RowEngine;
use frank_core::{sql_quote, Sighting};
use serde::Serialize;
use sha2::{Digest, Sha256};

use super::rowdb::{exec, int, query, text, transaction, RowDb};
use super::sightings::Sightings;
use crate::auth::hex;

pub const FILE: &str = "registry.db";
const DAY_NS: i64 = 86_400 * 1_000_000_000;

const SCHEMA: [&str; 3] = [
    "CREATE TABLE registered (k TEXT NOT NULL, participant TEXT NOT NULL, \
     sighting_id TEXT NOT NULL, digest TEXT NOT NULL, \
     received INTEGER NOT NULL, day INTEGER NOT NULL)",
    "CREATE UNIQUE INDEX registered_k ON registered (k)",
    "CREATE INDEX registered_day ON registered (day)",
];

/// What a sender gets back for one sighting.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Receipt {
    pub sighting_id: String,
    /// SHA-256 of the normalised submission.
    pub digest: String,
    /// When it was first registered, ns since the epoch.
    pub received: i64,
    /// `created`, or `duplicate` for one registered before.
    pub status: &'static str,
}

/// One registration: participant, sighting id, digest, received (ns).
pub type Registration = (String, String, String, i64);

#[derive(Clone)]
pub struct Registry {
    db: RowDb,
}

/// The key of a registration.
fn key(participant: &str, sighting_id: &str) -> String {
    format!("{participant}|{sighting_id}")
}

impl Registry {
    /// Opens `<data>/registry.db` and, when it is new or of an older
    /// schema, builds it from `sightings`.
    pub fn open(data: &Path, sightings: &Sightings) -> Result<Registry, String> {
        let path = data.join(FILE);
        // 0.12's file had a `user` column; the index is derived, so it is
        // dropped and built again.
        if path.exists() {
            let (mut db, _) = super::rowdb::open_engine(&path)?;
            let old = query(&mut db, "SELECT user FROM registered LIMIT 1").is_ok();
            drop(db);
            if old {
                for f in [
                    FILE.to_string(),
                    format!("{FILE}-journal"),
                    format!("{FILE}-wal"),
                ] {
                    let _ = std::fs::remove_file(data.join(f));
                }
            }
        }
        let (tx, rx) = std::sync::mpsc::channel();
        let db = RowDb::open(&path, "registry", move |db, fresh| {
            let _ = tx.send(fresh);
            if fresh {
                SCHEMA.iter().try_for_each(|ddl| exec(db, ddl))
            } else {
                Ok(())
            }
        })?;
        let registry = Registry { db };
        if rx.recv().unwrap_or(false) {
            let n = registry.rebuild(sightings)?;
            if n > 0 {
                tracing::info!(registrations = n, "built registry.db from the sightings");
            }
        }
        Ok(registry)
    }

    /// Replaces the index with the registrations in `sightings`; their
    /// number. Rows stored before the `digest` column are left out.
    pub fn rebuild(&self, sightings: &Sightings) -> Result<usize, String> {
        let r = sightings.query(
            "SELECT reporter, sighting_id, digest, min(received) FROM sightings \
             WHERE digest IS NOT NULL GROUP BY reporter, sighting_id, digest",
        )?;
        let entries: Vec<Registration> = r
            .rows
            .iter()
            .map(|row| (text(&row[0]), text(&row[1]), text(&row[2]), int(&row[3])))
            .collect();
        let n = entries.len();
        self.db.run(move |db| {
            transaction(db, |db| {
                exec(db, "DELETE FROM registered")?;
                insert(db, &entries)
            })
        })?;
        Ok(n)
    }

    /// The registered `(digest, received)` of each of `ids` the
    /// participant registered before.
    pub fn find(
        &self,
        participant: &str,
        ids: Vec<String>,
    ) -> Result<HashMap<String, (String, i64)>, String> {
        let participant = participant.to_string();
        self.db.run(move |db| {
            let mut found = HashMap::new();
            // One index seek per id: the row engine plans one indexed
            // predicate (db-core #695), and a batch is at most 100.
            for id in ids {
                let sql = format!(
                    "SELECT digest, received FROM registered WHERE k = {}",
                    sql_quote(&key(&participant, &id))
                );
                if let Some(row) = query(db, &sql)?.rows.first() {
                    found.insert(id, (text(&row[0]), int(&row[1])));
                }
            }
            Ok(found)
        })
    }

    /// Adds registrations, in one transaction.
    pub fn register(&self, entries: Vec<Registration>) -> Result<(), String> {
        self.db
            .run(move |db| transaction(db, |db| insert(db, &entries)))
    }

    /// Drops registrations that arrived before `keep_from_day`, as the
    /// sightings' retention drops their rows.
    pub fn retain_from(&self, keep_from_day: i64) -> Result<(), String> {
        self.db.run(move |db| {
            exec(
                db,
                &format!("DELETE FROM registered WHERE day < {keep_from_day}"),
            )
        })
    }
}

fn insert(db: &mut RowEngine, entries: &[Registration]) -> Result<(), String> {
    entries
        .iter()
        .try_for_each(|(participant, id, digest, received)| {
            exec(
                db,
                &format!(
                    "INSERT INTO registered (k, participant, sighting_id, digest, received, day) \
                 VALUES ({}, {}, {}, {}, {received}, {})",
                    sql_quote(&key(participant, id)),
                    sql_quote(participant),
                    sql_quote(id),
                    sql_quote(digest),
                    received.div_euclid(DAY_NS)
                ),
            )
        })
}

/// SHA-256 of what a sighting says, independent of how it was written:
/// key order, spacing, evidence and technique order, and a timestamp the
/// server filled in do not change it (the evidence is in canonical order
/// already). The id is left out: it is the key.
#[must_use]
pub fn digest(sighting: &Sighting) -> String {
    let mut s = sighting.clone();
    s.sighting_id = None;
    if !s.ts_given {
        s.ts_ns = 0;
    }
    s.sighting_of.techniques.sort();
    let json = serde_json::to_vec(&s).unwrap_or_default();
    hex(&Sha256::digest(&json))
}

/// A sighting id derived from a digest, for files without ids: loading
/// the same file twice registers nothing new.
#[must_use]
pub fn derived_id(digest: &str) -> String {
    let mut h: Vec<u8> = digest.bytes().take(32).collect();
    h[12] = b'8'; // UUID version 8: custom
    h[16] = b'8'; // RFC 4122 variant
    let h = String::from_utf8(h).unwrap_or_default();
    format!(
        "sighting--{}-{}-{}-{}-{}",
        &h[..8],
        &h[8..12],
        &h[12..16],
        &h[16..20],
        &h[20..]
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    const NOW: i64 = 1_792_670_400_000_000_000;

    fn sub(json: &str) -> Sighting {
        Sighting::parse(json, NOW).unwrap()
    }

    #[test]
    fn the_digest_ignores_form_not_content() {
        let a = sub(
            r#"{"sighting": {"sighting_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
                "sigma_detection": {"rule_id": "r"},
                "observables": {"network": [{"type": "ipv4", "value": "198.51.100.1"}, {"type": "domain", "value": "a.example"}]}}}"#,
        );
        let b = sub(
            r#"{"sighting": {"observables": {"network": [{"value": "A.example", "type": "domain"}, {"type": "ipv4", "value": "198.51.100.1"}]},
                "sigma_detection": {"rule_id": "r"}}}"#,
        );
        assert_eq!(
            digest(&a),
            digest(&b),
            "order, case, id and a filled-in time"
        );
        let c = sub(r#"{"sighting": {"sigma_detection": {"rule_id": "r2"}}}"#);
        assert_ne!(digest(&a), digest(&c));
        let later = Sighting::parse(
            r#"{"sighting": {"sigma_detection": {"rule_id": "r2"}}}"#,
            NOW + 1,
        )
        .unwrap();
        assert_eq!(
            digest(&c),
            digest(&later),
            "the server's clock is not content"
        );
        let record = serde_json::to_value(&a).unwrap();
        assert_ne!(
            digest(&a),
            digest(&Sighting::from_value(&record, NOW).unwrap()),
            "a's time was filled in; its frank/1 form gives one"
        );
        let dated = sub(
            r#"{"sighting": {"timestamp": "2026-10-20T08:00:00Z", "sigma_detection": {"rule_id": "r"}}}"#,
        );
        let record = serde_json::to_value(&dated).unwrap();
        assert_eq!(
            digest(&dated),
            digest(&Sighting::from_value(&record, NOW).unwrap()),
            "Phase 2's format and frank/1 are the same content"
        );
        let id = derived_id(&digest(&a));
        assert_eq!(id.len(), "sighting--".len() + 36);
        assert!(Sighting::parse(
            &format!(r#"{{"sighting": {{"sighting_id": "{id}", "sigma_detection": {{"rule_id": "r"}}}}}}"#),
            NOW
        )
        .is_ok(), "a derived id is a valid sighting id");
    }

    #[test]
    fn registrations_are_per_participant_and_expire() {
        let dir = std::env::temp_dir().join(format!("frank-registry-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let s = Sightings::open(&dir, None, || NOW).unwrap();
        let r = Registry::open(&dir, &s).unwrap();
        r.register(vec![("org-a".into(), "s1".into(), "d1".into(), NOW)])
            .unwrap();
        let found = r.find("org-a", vec!["s1".into(), "s2".into()]).unwrap();
        assert_eq!(found.get("s1"), Some(&("d1".to_string(), NOW)));
        assert!(!found.contains_key("s2"));
        assert!(
            r.find("org-b", vec!["s1".into()]).unwrap().is_empty(),
            "another participant's ids are its own"
        );
        r.retain_from(NOW / DAY_NS + 1).unwrap();
        assert!(r.find("org-a", vec!["s1".into()]).unwrap().is_empty());
        std::fs::remove_dir_all(&dir).ok();
    }
}
