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
use db_core::engine::Cell;
use frank_core::{sql_blob, sql_quote, Digest, Sighting, SightingId};
use serde::Serialize;
use sha2::{Digest as _, Sha256};

use super::rowdb::{exec, int, query, text, transaction, RowDb};
use super::sightings::{nanos, Sightings};

pub const FILE: &str = "registry.db";
const DAY_NS: i64 = 86_400 * 1_000_000_000;

const SCHEMA: [&str; 3] = [
    "CREATE TABLE registered (k BLOB NOT NULL, participant TEXT NOT NULL, \
     sighting_id BLOB NOT NULL, digest BLOB NOT NULL, \
     received INTEGER NOT NULL, day INTEGER NOT NULL)",
    "CREATE UNIQUE INDEX registered_k ON registered (k)",
    "CREATE INDEX registered_day ON registered (day)",
];

/// What a sender gets back for one sighting.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Receipt {
    pub sighting_id: SightingId,
    /// SHA-256 of the normalised submission.
    pub digest: Digest,
    /// When it was first registered, ns since the epoch.
    pub received: i64,
    /// `created`, or `duplicate` for one registered before.
    pub status: &'static str,
}

/// One registration: participant, sighting id, digest, received (ns).
pub type Registration = (String, SightingId, Digest, i64);

#[derive(Clone)]
pub struct Registry {
    db: RowDb,
}

/// The key of a registration: the id's 16 bytes, then the participant.
fn key(participant: &str, sighting_id: &SightingId) -> String {
    sql_blob(&[&sighting_id.0[..], participant.as_bytes()].concat())
}

/// A blob cell of exactly `N` bytes.
fn bytes<const N: usize>(c: &Cell) -> Option<[u8; N]> {
    match c {
        Cell::Blob(b) => b.as_slice().try_into().ok(),
        _ => None,
    }
}

impl Registry {
    /// Opens `<data>/registry.db` and, when it is new or of an older
    /// schema, builds it from `sightings`.
    pub fn open(data: &Path, sightings: &Sightings) -> Result<Registry, String> {
        let path = data.join(FILE);
        // 0.12's file had a `user` column, and until 0.27 ids and digests
        // were text (#200); the index is derived, so it is dropped and
        // built again.
        if path.exists() {
            let (mut db, _) = super::rowdb::open_engine(&path)?;
            let old = query(&mut db, "SELECT user FROM registered LIMIT 1").is_ok()
                || query(
                    &mut db,
                    "SELECT 1 FROM registered WHERE typeof(sighting_id) = 'text' LIMIT 1",
                )
                .is_ok_and(|r| !r.rows.is_empty());
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
            .filter_map(|row| {
                let id = SightingId(bytes(&row[1])?);
                Some((
                    text(&row[0]),
                    id,
                    Digest(bytes(&row[2])?),
                    nanos(&row[3]).unwrap_or(0),
                ))
            })
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
        ids: Vec<SightingId>,
    ) -> Result<HashMap<SightingId, (Digest, i64)>, String> {
        let participant = participant.to_string();
        self.db.run(move |db| {
            let mut found = HashMap::new();
            // One index seek per id: the row engine plans one indexed
            // predicate (db-core #695), and a batch is at most 100.
            for id in ids {
                let sql = format!(
                    "SELECT digest, received FROM registered WHERE k = {}",
                    key(&participant, &id)
                );
                if let Some(row) = query(db, &sql)?.rows.first() {
                    if let Some(d) = bytes(&row[0]) {
                        found.insert(id, (Digest(d), int(&row[1])));
                    }
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
                    key(participant, id),
                    sql_quote(participant),
                    sql_blob(&id.0),
                    sql_blob(&digest.0),
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
pub fn digest(sighting: &Sighting) -> Digest {
    let mut s = sighting.clone();
    s.sighting_id = None;
    if !s.ts_given {
        s.ts_ns = 0;
    }
    s.sighting_of.techniques.sort();
    let json = serde_json::to_vec(&s).unwrap_or_default();
    Digest(Sha256::digest(&json).into())
}

/// A sighting id derived from a digest, for files without ids: loading
/// the same file twice registers nothing new.
#[must_use]
pub fn derived_id(digest: &Digest) -> SightingId {
    let mut b = [0; 16];
    b.copy_from_slice(&digest.0[..16]);
    b[6] = 0x80 | (b[6] & 0x0f); // UUID version 8: custom
    b[8] = 0x80 | (b[8] & 0x0f); // RFC 4122 variant
    SightingId(b)
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
        assert_eq!(
            Sighting::parse(
                &format!(r#"{{"sighting": {{"sighting_id": "{id}", "sigma_detection": {{"rule_id": "r"}}}}}}"#),
                NOW
            )
            .unwrap()
            .sighting_id,
            Some(id),
            "a derived id is a valid sighting id"
        );
        // Until 0.27 the id was cut from the hex text: the same ids still.
        let mut h = digest(&a).to_string().into_bytes();
        h.truncate(32);
        (h[12], h[16]) = (b'8', b'8');
        let h = String::from_utf8(h).unwrap();
        let old = format!(
            "sighting--{}-{}-{}-{}-{}",
            &h[..8],
            &h[8..12],
            &h[12..16],
            &h[16..20],
            &h[20..]
        );
        assert_eq!(id.to_string(), old);
    }

    #[test]
    fn registrations_are_per_participant_and_expire() {
        let dir = std::env::temp_dir().join(format!("frank-registry-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let s = Sightings::open(&dir, None, || NOW).unwrap();
        let r = Registry::open(&dir, &s).unwrap();
        let (s1, s2, d1) = (SightingId([1; 16]), SightingId([2; 16]), Digest([0xd1; 32]));
        r.register(vec![("org-a".into(), s1, d1, NOW)]).unwrap();
        let found = r.find("org-a", vec![s1, s2]).unwrap();
        assert_eq!(found.get(&s1), Some(&(d1, NOW)));
        assert!(!found.contains_key(&s2));
        assert!(
            r.find("org-b", vec![s1]).unwrap().is_empty(),
            "another participant's ids are its own"
        );
        r.retain_from(NOW / DAY_NS + 1).unwrap();
        assert!(r.find("org-a", vec![s1]).unwrap().is_empty());
        drop(r);

        // A file from 0.27 or before, ids and digests as text (#200): built
        // again from the sightings, here none.
        std::fs::remove_file(dir.join(FILE)).unwrap();
        let (mut db, _) = super::super::rowdb::open_engine(&dir.join(FILE)).unwrap();
        for ddl in [
            "CREATE TABLE registered (k TEXT NOT NULL, participant TEXT NOT NULL, \
             sighting_id TEXT NOT NULL, digest TEXT NOT NULL, \
             received INTEGER NOT NULL, day INTEGER NOT NULL)",
            "INSERT INTO registered VALUES ('org-a|sighting--x', 'org-a', 'sighting--x', 'd', 0, 0)",
        ] {
            exec(&mut db, ddl).unwrap();
        }
        drop(db);
        let r = Registry::open(&dir, &s).unwrap();
        r.register(vec![("org-a".into(), s1, d1, NOW)]).unwrap();
        assert_eq!(
            r.find("org-a", vec![s1]).unwrap().get(&s1),
            Some(&(d1, NOW))
        );
        let rows =
            r.db.run(|db| query(db, "SELECT count(*) FROM registered").map(|q| int(&q.rows[0][0])))
                .unwrap();
        assert_eq!(rows, 1, "the text rows are gone");
        std::fs::remove_dir_all(&dir).ok();
    }
}
