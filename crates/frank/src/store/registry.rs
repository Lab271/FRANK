//! The submission registry (#159): which participant registered which
//! sighting id, through which user, with what content. The sender's
//! `(participant, sighting_id)` is the registration: sending the same
//! sighting again is answered with the original receipt, sending other
//! content under a registered id is refused (corrections: #161).
//!
//! Which user sent what lives here, never in the shared Parquet files.
//! Rows are dropped with the sightings' retention (by arrival day).

use std::collections::HashMap;
use std::path::Path;

use frank_core::{sql_quote, Submission};
use serde::Serialize;
use sha2::{Digest, Sha256};

use super::rowdb::{exec, int, query, text, transaction, RowDb};
use crate::auth::hex;

pub const FILE: &str = "registry.db";
const DAY_NS: i64 = 86_400 * 1_000_000_000;

const SCHEMA: [&str; 3] = [
    "CREATE TABLE registered (k TEXT NOT NULL, participant TEXT NOT NULL, \
     sighting_id TEXT NOT NULL, user TEXT NOT NULL, digest TEXT NOT NULL, \
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

#[derive(Clone)]
pub struct Registry {
    db: RowDb,
}

/// The key of a registration.
fn key(participant: &str, sighting_id: &str) -> String {
    format!("{participant}|{sighting_id}")
}

impl Registry {
    /// Opens `<data>/registry.db`, creating it if needed.
    pub fn open(data: &Path) -> Result<Registry, String> {
        let db = RowDb::open(&data.join(FILE), "registry", |db, fresh| {
            if fresh {
                SCHEMA.iter().try_for_each(|ddl| exec(db, ddl))
            } else {
                Ok(())
            }
        })?;
        Ok(Registry { db })
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

    /// Registers `(sighting_id, digest)` pairs for a participant's user,
    /// in one transaction.
    pub fn register(
        &self,
        participant: &str,
        user: &str,
        entries: Vec<(String, String)>,
        received: i64,
    ) -> Result<(), String> {
        let (participant, user) = (participant.to_string(), user.to_string());
        self.db.run(move |db| {
            transaction(db, |db| {
                entries.iter().try_for_each(|(id, digest)| {
                    exec(
                        db,
                        &format!(
                            "INSERT INTO registered (k, participant, sighting_id, user, digest, received, day) \
                             VALUES ({}, {}, {}, {}, {}, {received}, {})",
                            sql_quote(&key(&participant, id)),
                            sql_quote(&participant),
                            sql_quote(id),
                            sql_quote(&user),
                            sql_quote(digest),
                            received.div_euclid(DAY_NS)
                        ),
                    )
                })
            })
        })
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

/// SHA-256 of what a submission says, independent of how it was written:
/// key order, spacing, IoC and technique order, and a timestamp the server
/// filled in do not change it. The id is left out: it is the key.
#[must_use]
pub fn digest(sub: &Submission) -> String {
    let mut s = sub.clone();
    s.sighting_id = None;
    if !s.ts_given {
        s.ts_ns = 0;
    }
    s.iocs.sort_by_key(frank_core::Ioc::key);
    s.techniques.sort();
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

    fn sub(json: &str) -> Submission {
        Submission::parse(json, NOW).unwrap()
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
        let later = Submission::parse(
            r#"{"sighting": {"sigma_detection": {"rule_id": "r2"}}}"#,
            NOW + 1,
        )
        .unwrap();
        assert_eq!(
            digest(&c),
            digest(&later),
            "the server's clock is not content"
        );
        let id = derived_id(&digest(&a));
        assert_eq!(id.len(), "sighting--".len() + 36);
        assert!(Submission::parse(
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
        let r = Registry::open(&dir).unwrap();
        r.register("org-a", "alice", vec![("s1".into(), "d1".into())], NOW)
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
