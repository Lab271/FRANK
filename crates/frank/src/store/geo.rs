//! The `ip_geo` row table (#191): the country and network (ASN) of each
//! IP address FRANK has seen, looked up in the GeoLite2 databases. It is
//! a lookup table next to `sightings`, which stays as it is: an address
//! without a row was not looked up yet, a row with country `ZZ` and ASN 0
//! was looked up and found nothing.
//!
//! As in `iocs.db`, keys are single columns (`ip` as the upsert target)
//! and IP addresses are also kept as 32 hex digits for ranges.

use std::collections::BTreeMap;
use std::path::Path;

use db_core::engine::row::RowEngine;
use frank_core::sql_quote;
use serde::Serialize;

use super::rowdb::{exec, int, query, text, transaction, RowDb};

pub const FILE: &str = "geo.db";

const SCHEMA: [&str; 3] = [
    "CREATE TABLE ip_geo (ip TEXT NOT NULL, ip_hex TEXT NOT NULL, country TEXT NOT NULL, \
     asn INTEGER NOT NULL, as_org TEXT, looked_up INTEGER NOT NULL, db_build INTEGER NOT NULL)",
    "CREATE UNIQUE INDEX ip_geo_ip ON ip_geo (ip)",
    "CREATE INDEX ip_geo_hex ON ip_geo (ip_hex)",
];

/// What GeoLite2 says about one address.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct IpGeo {
    pub ip: String,
    #[serde(skip)]
    pub ip_hex: String,
    /// ISO 3166 alpha-2, `ZZ` when unknown.
    pub country: String,
    /// 0 when unknown.
    pub asn: i64,
    pub as_org: Option<String>,
    #[serde(skip)]
    pub looked_up: i64,
    /// The GeoLite2 build it came from, seconds since the epoch.
    #[serde(skip)]
    pub db_build: i64,
}

/// A handle to the thread that owns the database.
#[derive(Clone)]
pub struct GeoDb {
    db: RowDb,
}

impl GeoDb {
    /// Opens `data/geo.db`, creating it and its schema if needed.
    pub fn open(data: &Path) -> Result<GeoDb, String> {
        let db = RowDb::open(&data.join(FILE), "geo", |db, fresh| {
            if fresh {
                SCHEMA.iter().try_for_each(|ddl| exec(db, ddl))
            } else {
                Ok(())
            }
        })?;
        Ok(GeoDb { db })
    }

    /// The rows of `ips` that exist, by address.
    pub fn get(&self, ips: Vec<String>) -> Result<BTreeMap<String, IpGeo>, String> {
        if ips.is_empty() {
            return Ok(BTreeMap::new());
        }
        self.db.run(move |db| {
            let mut out = BTreeMap::new();
            for chunk in ips.chunks(500) {
                let list: Vec<String> = chunk.iter().map(|i| sql_quote(i)).collect();
                let sql = format!("{SELECT} WHERE ip IN ({})", list.join(", "));
                for g in rows(db, &sql)? {
                    out.insert(g.ip.clone(), g);
                }
            }
            Ok(out)
        })
    }

    /// Every row, by address.
    pub fn all(&self) -> Result<Vec<IpGeo>, String> {
        self.db
            .run(|db| rows(db, &format!("{SELECT} ORDER BY ip_hex")))
    }

    /// Each address and the build it was looked up with.
    pub fn builds(&self) -> Result<BTreeMap<String, i64>, String> {
        self.db.run(|db| {
            let r = query(db, "SELECT ip, db_build FROM ip_geo")?;
            Ok(r.rows
                .iter()
                .map(|row| (text(&row[0]), int(&row[1])))
                .collect())
        })
    }

    /// Inserts or replaces `rows`, in one transaction.
    pub fn put(&self, rows: Vec<IpGeo>) -> Result<(), String> {
        if rows.is_empty() {
            return Ok(());
        }
        self.db
            .run(move |db| transaction(db, |db| rows.iter().try_for_each(|g| upsert(db, g))))
    }
}

const SELECT: &str = "SELECT ip, ip_hex, country, asn, as_org, looked_up, db_build FROM ip_geo";

fn rows(db: &mut RowEngine, sql: &str) -> Result<Vec<IpGeo>, String> {
    Ok(query(db, sql)?
        .rows
        .iter()
        .map(|row| IpGeo {
            ip: text(&row[0]),
            ip_hex: text(&row[1]),
            country: text(&row[2]),
            asn: int(&row[3]),
            as_org: Some(text(&row[4])).filter(|o| !o.is_empty()),
            looked_up: int(&row[5]),
            db_build: int(&row[6]),
        })
        .collect())
}

fn upsert(db: &mut RowEngine, g: &IpGeo) -> Result<(), String> {
    let ip = sql_quote(&g.ip);
    let org = g.as_org.as_deref().map_or("NULL".into(), sql_quote);
    let found = query(db, &format!("SELECT ip FROM ip_geo WHERE ip = {ip}"))?;
    let sql = if found.rows.is_empty() {
        format!(
            "INSERT INTO ip_geo (ip, ip_hex, country, asn, as_org, looked_up, db_build) \
             VALUES ({ip}, {}, {}, {}, {org}, {}, {})",
            sql_quote(&g.ip_hex),
            sql_quote(&g.country),
            g.asn,
            g.looked_up,
            g.db_build,
        )
    } else {
        format!(
            "UPDATE ip_geo SET country = {}, asn = {}, as_org = {org}, looked_up = {}, db_build = {} \
             WHERE ip = {ip}",
            sql_quote(&g.country),
            g.asn,
            g.looked_up,
            g.db_build,
        )
    };
    exec(db, &sql)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn geo(ip: &str, country: &str, build: i64) -> IpGeo {
        IpGeo {
            ip: ip.into(),
            ip_hex: frank_core::observable::ip_hex(ip.parse().unwrap()),
            country: country.into(),
            asn: 64496,
            as_org: Some("Example".into()),
            looked_up: 1,
            db_build: build,
        }
    }

    #[test]
    fn put_replaces_and_get_finds() {
        let dir = std::env::temp_dir().join(format!("frank-geo-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let db = GeoDb::open(&dir).unwrap();
        db.put(vec![geo("192.0.2.1", "NL", 1), geo("2001:db8::1", "ZZ", 1)])
            .unwrap();
        db.put(vec![geo("192.0.2.1", "DE", 2)]).unwrap();
        let got = db
            .get(vec!["192.0.2.1".into(), "198.51.100.9".into()])
            .unwrap();
        assert_eq!(got.len(), 1);
        assert_eq!(
            (got["192.0.2.1"].country.as_str(), got["192.0.2.1"].db_build),
            ("DE", 2)
        );
        assert_eq!(db.builds().unwrap().len(), 2);
        assert_eq!(
            db.all().unwrap()[0].ip,
            "192.0.2.1",
            "IPv4 sorts first (mapped)"
        );
        let _ = std::fs::remove_dir_all(&dir);
    }
}
