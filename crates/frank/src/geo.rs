//! Country and network (ASN) of IP addresses (#191), from DB-IP's free
//! Lite databases in `data/geoip/dbip-lite/` (`make geoip`), MaxMind DB
//! files with GeoLite2's fields.
//!
//! The databases are assumed to be there, and FRANK keeps working when
//! they are not: missing, unreadable or corrupt files are warned about
//! once and lookups then answer "not looked up". The files are checked
//! for changes at most once a minute, so new or refreshed ones are picked
//! up without a restart.
//!
//! Answers go to the `ip_geo` table ([`GeoDb`]), filled when sightings
//! arrive and by [`Geo::backfill`] when the databases appear or change.

use std::collections::BTreeMap;
use std::net::IpAddr;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::SystemTime;

use crate::mmdb::Mmdb;
use frank_core::observable::ip_hex;
use frank_core::{IocType, SightingRow};
use serde_json::{json, Value};

use crate::store::geo::{GeoDb, IpGeo};
use crate::store::Sightings;

/// Where the databases are, under the data directory.
pub const DIR: &str = "geoip/dbip-lite";
pub const COUNTRY: &str = "dbip-country-lite.mmdb";
pub const ASN: &str = "dbip-asn-lite.mmdb";
/// ISO 3166's code for an unknown country.
pub const UNKNOWN: &str = "ZZ";
/// The attribution DB-IP's licence (CC BY 4.0) asks for.
pub const ATTRIBUTION: &str =
    "IP Geolocation by DB-IP (https://db-ip.com), licensed under CC BY 4.0";
const CHECK_NS: i64 = 60 * 1_000_000_000;
/// Addresses per backfill step.
const STEP: usize = 1000;

struct Loaded {
    country: Option<Mmdb>,
    asn: Option<Mmdb>,
    /// The files' modification times when loaded; `None` for a missing file.
    stamps: [Option<SystemTime>; 2],
    checked: i64,
    /// The build backfilled last, so a backfill runs once per build.
    backfilled: Option<i64>,
}

/// The database readers and the `ip_geo` table.
pub struct Geo {
    dir: PathBuf,
    db: GeoDb,
    loaded: Mutex<Loaded>,
}

impl Geo {
    /// Opens `data/geo.db` and reads the databases under `data/geoip/`.
    pub fn open(data: &Path, now: i64) -> Result<Geo, String> {
        let g = Geo {
            dir: data.join(DIR),
            db: GeoDb::open(data)?,
            loaded: Mutex::new(Loaded {
                country: None,
                asn: None,
                stamps: [None, None],
                checked: i64::MIN,
                backfilled: None,
            }),
        };
        g.refresh(now);
        Ok(g)
    }

    pub fn db(&self) -> &GeoDb {
        &self.db
    }

    fn lock(&self) -> std::sync::MutexGuard<'_, Loaded> {
        self.loaded
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }

    /// Reloads the databases when a file appeared, changed or went away,
    /// checking at most once a minute.
    pub fn refresh(&self, now: i64) {
        let mut l = self.lock();
        if now.saturating_sub(l.checked) < CHECK_NS {
            return;
        }
        let first = l.checked == i64::MIN;
        l.checked = now;
        let stamp = |name| {
            std::fs::metadata(self.dir.join(name))
                .and_then(|m| m.modified())
                .ok()
        };
        let stamps = [stamp(COUNTRY), stamp(ASN)];
        if !first && stamps == l.stamps {
            return;
        }
        l.stamps = stamps;
        l.country = self.read(COUNTRY);
        l.asn = self.read(ASN);
        match build(&l) {
            Some(b) => tracing::info!(build = %day(b), "DB-IP databases loaded from {}", self.dir.display()),
            None => tracing::warn!(
                "no DB-IP databases in {}: run `make geoip`; IP addresses are not looked up meanwhile",
                self.dir.display()
            ),
        }
    }

    /// One database, or `None` (warned) when it is missing or unusable.
    fn read(&self, name: &str) -> Option<Mmdb> {
        let path = self.dir.join(name);
        if !path.exists() {
            return None;
        }
        match Mmdb::open(&path) {
            Ok(r) => Some(r),
            Err(e) => {
                tracing::warn!("{} is unusable, ignored: {e}", path.display());
                None
            }
        }
    }

    /// The answer for `ip` with the databases loaded now, or `None` when
    /// none is: then the address is not looked up.
    pub fn lookup(&self, ip: IpAddr, now: i64) -> Option<IpGeo> {
        let l = self.lock();
        let b = build(&l)?;
        // A record that cannot be read counts as no record.
        let record = |db: &Option<Mmdb>| db.as_ref().and_then(|r| r.lookup(ip).ok().flatten());
        let country = record(&l.country).and_then(|c| {
            [["country", "iso_code"], ["registered_country", "iso_code"]]
                .iter()
                .find_map(|path| c.get(path).and_then(|v| v.as_str()).map(str::to_string))
        });
        let asn = record(&l.asn);
        let field = |k: &str| asn.as_ref().and_then(|a| a.get(&[k]).cloned());
        Some(IpGeo {
            ip: ip.to_string(),
            ip_hex: ip_hex(ip),
            country: country.unwrap_or_else(|| UNKNOWN.into()),
            asn: field("autonomous_system_number")
                .and_then(|n| n.as_u64())
                .and_then(|n| i64::try_from(n).ok())
                .unwrap_or(0),
            as_org: field("autonomous_system_organization")
                .and_then(|o| o.as_str().map(str::to_string)),
            looked_up: now,
            db_build: b,
        })
    }

    /// Looks up the addresses of `rows` that `ip_geo` does not have yet.
    /// Never fails a caller: an error is logged and the addresses are
    /// left for the backfill.
    pub fn fill(&self, rows: &[SightingRow], now: i64) {
        let ips: Vec<String> = rows
            .iter()
            .filter(|r| matches!(r.ioc_type, Some(IocType::Ipv4 | IocType::Ipv6)))
            .filter_map(|r| r.ioc_value.clone())
            .collect();
        if ips.is_empty() || build(&self.lock()).is_none() {
            return;
        }
        let result = self.db.get(ips.clone()).and_then(|known| {
            let new: Vec<IpGeo> = ips
                .iter()
                .filter(|ip| !known.contains_key(*ip))
                .filter_map(|ip| self.lookup(ip.parse().ok()?, now))
                .collect();
            self.db.put(new)
        });
        if let Err(e) = result {
            tracing::warn!("ip_geo: {e}");
        }
    }

    /// Looks up every address in `sightings` that `ip_geo` lacks or holds
    /// from another build, once per build. Returns how many it wrote.
    pub fn backfill(&self, sightings: &Sightings, now: i64) -> Result<usize, String> {
        let Some(b) = build(&self.lock()) else {
            return Ok(0);
        };
        if self.lock().backfilled == Some(b) {
            return Ok(0);
        }
        let seen = sightings.query(
            "SELECT DISTINCT ioc_value FROM sightings WHERE ioc_type = 'ipv4' OR ioc_type = 'ipv6'",
        )?;
        let have = self.db.builds()?;
        let todo: Vec<IpAddr> = seen
            .rows
            .iter()
            .filter_map(|row| match row.first() {
                Some(db_core::engine::Cell::Text(v)) => Some(v.clone()),
                _ => None,
            })
            .filter(|ip| have.get(ip) != Some(&b))
            .filter_map(|ip| ip.parse().ok())
            .collect();
        for step in todo.chunks(STEP) {
            self.db
                .put(step.iter().filter_map(|ip| self.lookup(*ip, now)).collect())?;
        }
        self.lock().backfilled = Some(b);
        if !todo.is_empty() {
            tracing::info!(addresses = todo.len(), build = %day(b), "ip_geo backfilled");
        }
        Ok(todo.len())
    }

    /// The answers `ip_geo` holds for `ips`.
    pub fn answers(&self, ips: Vec<String>) -> BTreeMap<String, IpGeo> {
        self.db.get(ips).unwrap_or_else(|e| {
            tracing::warn!("ip_geo: {e}");
            BTreeMap::new()
        })
    }

    /// For `/health`: `ok` with the build day, or `missing`.
    pub fn status(&self) -> Value {
        match build(&self.lock()) {
            Some(b) => json!({ "status": "ok", "build": day(b) }),
            None => json!({ "status": "missing" }),
        }
    }
}

/// The newest build of the loaded databases, seconds since the epoch.
fn build(l: &Loaded) -> Option<i64> {
    [&l.country, &l.asn]
        .into_iter()
        .flatten()
        .filter_map(|r| i64::try_from(r.build_epoch).ok())
        .max()
}

fn day(epoch_s: i64) -> String {
    crate::store::iocs::day_label(epoch_s.div_euclid(86_400))
}

/// The tests' MaxMind DB writer, shared with the integration tests.
#[cfg(test)]
#[allow(dead_code)]
#[path = "../tests/support/mmdb.rs"]
mod test_mmdb;

#[cfg(test)]
#[allow(non_snake_case)] // mcdc__<id>__v<N>_<what> (ADR-025)
mod tests {
    use super::*;
    use frank_core::{SightingBuilder, SightingId};

    const NOW: i64 = 1_792_670_400_000_000_000;
    const BUILD: u64 = 1_792_454_400;

    struct Dir(PathBuf);
    impl Drop for Dir {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }
    fn dir(name: &str) -> Dir {
        let d = std::env::temp_dir().join(format!("frank-geo-unit-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        Dir(d)
    }

    fn rows(t: IocType, v: &str) -> Vec<SightingRow> {
        let mut b = SightingBuilder::new();
        b.observable(t, v, None, &serde_json::Map::new());
        b.build(NOW).unwrap().rows(SightingId([1; 16]))
    }

    /// Opened without databases, which then appear; checked last at `checked`.
    fn appeared(name: &str, checked: i64) -> (Dir, Geo) {
        let d = dir(name);
        let g = Geo::open(&d.0, NOW).unwrap();
        test_mmdb::dbip(&d.0, BUILD);
        g.lock().checked = checked;
        (d, g)
    }

    fn stamps(g: &Geo) -> [Option<SystemTime>; 2] {
        [COUNTRY, ASN].map(|f| {
            std::fs::metadata(g.dir.join(f))
                .and_then(|m| m.modified())
                .ok()
        })
    }

    // refresh: `!first && stamps == l.stamps`
    #[test]
    fn mcdc__geo_refresh_01ee018e__v1_unchanged_files_are_not_reread() {
        let (_d, g) = appeared("refresh-same", NOW);
        g.lock().stamps = stamps(&g);
        g.refresh(NOW + CHECK_NS);
        assert_eq!(g.status()["status"], "missing");
    }

    #[test]
    fn mcdc__geo_refresh_01ee018e__v2_first_check_reads_anyway() {
        let (_d, g) = appeared("refresh-first", i64::MIN);
        g.lock().stamps = stamps(&g);
        g.refresh(NOW + CHECK_NS);
        assert_eq!(g.status()["status"], "ok");
    }

    #[test]
    fn mcdc__geo_refresh_01ee018e__v3_changed_files_are_reread() {
        let (_d, g) = appeared("refresh-changed", NOW);
        g.refresh(NOW + CHECK_NS);
        assert_eq!(g.status()["status"], "ok");
    }

    // fill: `ips.is_empty() || build(&self.lock()).is_none()`
    #[test]
    fn mcdc__geo_fill_8fcf4e98__v1_addresses_with_databases_are_looked_up() {
        let d = dir("fill-ip");
        test_mmdb::dbip(&d.0, BUILD);
        let g = Geo::open(&d.0, NOW).unwrap();
        g.fill(&rows(IocType::Ipv4, "192.0.2.77"), NOW);
        let all = g.db().all().unwrap();
        assert_eq!(
            all.iter().map(|a| a.ip.as_str()).collect::<Vec<_>>(),
            ["192.0.2.77"]
        );
    }

    #[test]
    fn mcdc__geo_fill_8fcf4e98__v2_no_addresses_writes_nothing() {
        let d = dir("fill-none");
        test_mmdb::dbip(&d.0, BUILD);
        let g = Geo::open(&d.0, NOW).unwrap();
        g.fill(&rows(IocType::Domain, "evil.example"), NOW);
        assert!(g.db().all().unwrap().is_empty());
    }

    #[test]
    fn mcdc__geo_fill_8fcf4e98__v3_no_databases_writes_nothing() {
        let d = dir("fill-nodb");
        let g = Geo::open(&d.0, NOW).unwrap();
        g.fill(&rows(IocType::Ipv4, "192.0.2.77"), NOW);
        assert!(g.db().all().unwrap().is_empty());
    }
}
