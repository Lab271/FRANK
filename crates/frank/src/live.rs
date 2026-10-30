//! The live view (#186): the IoCs of the sightings that arrived in the
//! last hour, six hours or day, by `received` (when FRANK stored them),
//! not `ts` (when they were seen). Each IoC says whether FRANK had it
//! before the window, and which IoCs several participants report.
//!
//! Recent rows are in the WAL and the open hour's file, so the window
//! query reads little. "Seen before" is one `IN (...)` query over the rest
//! of the table for the window's IoCs only.

use std::collections::{BTreeMap, BTreeSet};

use db_core::engine::Cell;
use frank_core::sql_quote;
use serde::Serialize;

use crate::explore::FIRST_ROW;
use crate::geo::UNKNOWN;
use crate::store::geo::IpGeo;

const MINUTE_NS: i64 = 60 * 1_000_000_000;
/// IoCs per `IN (...)` query.
const CHUNK: usize = 1000;

/// How far back the view looks.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Window {
    Hour,
    SixHours,
    Day,
}

impl Window {
    #[must_use]
    pub fn parse(s: &str) -> Option<Window> {
        match s {
            "1h" => Some(Window::Hour),
            "6h" => Some(Window::SixHours),
            "24h" => Some(Window::Day),
            _ => None,
        }
    }

    #[must_use]
    pub fn label(self) -> &'static str {
        match self {
            Window::Hour => "1h",
            Window::SixHours => "6h",
            Window::Day => "24h",
        }
    }

    #[must_use]
    pub fn ns(self) -> i64 {
        match self {
            Window::Hour => 60 * MINUTE_NS,
            Window::SixHours => 6 * 60 * MINUTE_NS,
            Window::Day => 24 * 60 * MINUTE_NS,
        }
    }

    /// The width of one bar of the arrivals chart: 12 or 24 bars.
    #[must_use]
    pub fn bucket_ns(self) -> i64 {
        match self {
            Window::Hour => 5 * MINUTE_NS,
            Window::SixHours => 30 * MINUTE_NS,
            Window::Day => 60 * MINUTE_NS,
        }
    }
}

/// One IoC of the window.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct LiveIoc {
    pub ioc_type: String,
    pub value: String,
    /// One rule it was sighted under in the window (the greatest id).
    pub rule_id: Option<String>,
    /// When the latest sighting with it arrived.
    pub last_received: i64,
    pub sightings: i64,
    pub reporters: i64,
    /// The earliest `ts` of a visible sighting with it that arrived before
    /// the window; `None` makes it new.
    pub seen_since: Option<i64>,
    /// Country and ASN of an IP address, when looked up (#191).
    pub geo: Option<crate::store::geo::IpGeo>,
    /// What the warning and reference lists say about it (#192, #193).
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub listed: Vec<crate::store::lists::Listed>,
    /// Marked as common infrastructure: shown, never converging (#192).
    pub common: bool,
}

/// The window's IoCs: per IoC, the latest arrival, the sightings and
/// reporters, and a rule. A sighting holds an IoC once, so its rows count
/// sightings.
#[must_use]
pub fn window_sql(since: i64, visible: &str) -> String {
    format!(
        "SELECT ioc_type, ioc_value, max(received) AS latest, count(*) AS n, \
         count(DISTINCT reporter) AS r, max(rule_id) AS rule \
         FROM sightings WHERE received >= {since} AND {visible} AND ioc_value IS NOT NULL \
         GROUP BY ioc_type, ioc_value"
    )
}

/// For `values`, the earliest `ts` of a visible row that arrived before
/// the window. Rows stored before 0.13 have no `received` and count as
/// before.
#[must_use]
pub fn before_sql(since: i64, visible: &str, values: &[&str]) -> String {
    let values: Vec<String> = values.iter().map(|v| sql_quote(v)).collect();
    format!(
        "SELECT ioc_type, ioc_value, min(ts) FROM sightings \
         WHERE (received < {since} OR received IS NULL) AND {visible} \
         AND ioc_value IN ({}) GROUP BY ioc_type, ioc_value",
        values.join(", ")
    )
}

/// The arrival time of each sighting in the window.
#[must_use]
pub fn arrivals_sql(since: i64, visible: &str) -> String {
    format!(
        "SELECT received FROM sightings WHERE received >= {since} AND {visible} AND {FIRST_ROW}"
    )
}

/// The participants that sent a sighting in the window.
#[must_use]
pub fn reporters_sql(since: i64, visible: &str) -> String {
    format!(
        "SELECT count(DISTINCT reporter) FROM sightings WHERE received >= {since} AND {visible}"
    )
}

/// The rows of [`window_sql`].
#[must_use]
pub fn iocs(rows: &[Vec<Cell>]) -> Vec<LiveIoc> {
    rows.iter()
        .filter_map(|row| match row.as_slice() {
            [Cell::Text(t), Cell::Text(v), Cell::Int(last), Cell::Int(n), Cell::Int(r), rule] => {
                Some(LiveIoc {
                    ioc_type: t.clone(),
                    value: v.clone(),
                    rule_id: match rule {
                        Cell::Text(r) => Some(r.clone()),
                        _ => None,
                    },
                    last_received: *last,
                    sightings: *n,
                    reporters: *r,
                    seen_since: None,
                    geo: None,
                    listed: Vec::new(),
                    common: false,
                })
            }
            _ => None,
        })
        .collect()
}

/// The `IN (...)` lists for [`before_sql`], [`CHUNK`] values each.
#[must_use]
pub fn chunks(iocs: &[LiveIoc]) -> Vec<Vec<&str>> {
    let mut values: Vec<&str> = iocs.iter().map(|i| i.value.as_str()).collect();
    values.sort_unstable();
    values.dedup();
    values.chunks(CHUNK).map(<[&str]>::to_vec).collect()
}

/// Sets `seen_since` from the rows of [`before_sql`].
pub fn mark_seen(iocs: &mut [LiveIoc], rows: &[Vec<Cell>]) {
    let seen: BTreeMap<(&str, &str), i64> = rows
        .iter()
        .filter_map(|row| match row.as_slice() {
            [Cell::Text(t), Cell::Text(v), Cell::Int(ts)] => Some(((t.as_str(), v.as_str()), *ts)),
            _ => None,
        })
        .collect();
    for i in iocs.iter_mut() {
        i.seen_since = seen.get(&(i.ioc_type.as_str(), i.value.as_str())).copied();
    }
}

/// Arrivals per bar, oldest first: `(bar start, sightings)`, bars aligned
/// to the clock and the last one holding `now`.
#[must_use]
pub fn buckets(times: &[i64], window: Window, now: i64) -> Vec<(i64, i64)> {
    let width = window.bucket_ns();
    let n = window.ns() / width;
    let last = now.div_euclid(width) * width;
    let first = last - (n - 1) * width;
    let mut counts = vec![0; usize::try_from(n).unwrap_or(0)];
    for t in times {
        if *t >= first {
            if let Ok(i) = usize::try_from((t - first) / width) {
                if let Some(c) = counts.get_mut(i) {
                    *c += 1;
                }
            }
        }
    }
    counts
        .into_iter()
        .enumerate()
        .map(|(i, c)| (first + i64::try_from(i).unwrap_or(0) * width, c))
        .collect()
}

/// The feed (newest first) and the converging list (two or more
/// reporters, most reporters first), `limit` each.
#[must_use]
pub fn lists(iocs: &[LiveIoc], limit: usize) -> (Vec<LiveIoc>, Vec<LiveIoc>) {
    let mut feed = iocs.to_vec();
    feed.sort_by(|a, b| {
        b.last_received
            .cmp(&a.last_received)
            .then_with(|| a.value.cmp(&b.value))
    });
    feed.truncate(limit);
    let mut converging: Vec<LiveIoc> = iocs
        .iter()
        .filter(|i| i.reporters >= 2 && !i.common)
        .cloned()
        .collect();
    converging.sort_by(|a, b| {
        b.reporters
            .cmp(&a.reporters)
            .then(b.sightings.cmp(&a.sightings))
            .then(b.last_received.cmp(&a.last_received))
    });
    converging.truncate(limit);
    (feed, converging)
}

/// The window's IP addresses with each reporter that sent one (#195):
/// one row per address and reporter.
#[must_use]
pub fn addresses_sql(since: i64, visible: &str) -> String {
    format!(
        "SELECT ioc_value, reporter, count(*) FROM sightings \
         WHERE received >= {since} AND {visible} AND ioc_type IN ('ipv4', 'ipv6') \
         GROUP BY ioc_value, reporter"
    )
}

/// The rows of [`addresses_sql`]: `(address, reporter)`.
#[must_use]
pub fn addresses(rows: &[Vec<Cell>]) -> Vec<(String, String)> {
    rows.iter()
        .filter_map(|row| match row.as_slice() {
            [Cell::Text(ip), Cell::Text(r), ..] => Some((ip.clone(), r.clone())),
            _ => None,
        })
        .collect()
}

/// Distinct IoCs and reporters of a place (#195).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize)]
pub struct Tally {
    pub iocs: i64,
    pub reporters: i64,
}

/// One country of the top list.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Country {
    /// ISO 3166 alpha-2.
    pub country: String,
    #[serde(flatten)]
    pub tally: Tally,
}

/// One network (autonomous system) of the top list.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Network {
    pub asn: i64,
    pub as_org: Option<String>,
    #[serde(flatten)]
    pub tally: Tally,
}

/// A top list, and what is not in it taken together.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Ranked<T> {
    pub top: Vec<T>,
    /// The places below the top, or below the reporter threshold; `None`
    /// when there are none, or too few reporters to show them.
    pub other: Option<Tally>,
}

/// Where the window's addresses are (#195).
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Places {
    pub countries: Ranked<Country>,
    pub networks: Ranked<Network>,
    /// Addresses without a country: reserved (private, documentation) or
    /// not in the database.
    pub unknown: Option<Tally>,
}

type Sets<'a> = (BTreeSet<&'a str>, BTreeSet<&'a str>);

fn tally(s: &Sets) -> Tally {
    let n = |set: &BTreeSet<&str>| i64::try_from(set.len()).unwrap_or(i64::MAX);
    Tally {
        iocs: n(&s.0),
        reporters: n(&s.1),
    }
}

/// Groups `(key, address, reporter)` by key: the `limit` keys with the most
/// reporters (then addresses) that have at least `min` reporters, and the
/// rest together when that has `min` reporters too.
fn rank<'a, K: Ord>(
    items: impl Iterator<Item = (K, &'a str, &'a str)>,
    min: i64,
    limit: usize,
) -> (Vec<(K, Tally)>, Option<Tally>) {
    let mut by: BTreeMap<K, Sets<'a>> = BTreeMap::new();
    for (k, ip, r) in items {
        let e = by.entry(k).or_default();
        e.0.insert(ip);
        e.1.insert(r);
    }
    let mut ranked: Vec<(K, Tally, Sets<'a>)> =
        by.into_iter().map(|(k, s)| (k, tally(&s), s)).collect();
    ranked.sort_by(|(ka, a, _), (kb, b, _)| {
        (b.reporters, b.iocs)
            .cmp(&(a.reporters, a.iocs))
            .then_with(|| ka.cmp(kb))
    });
    let mut top = Vec::new();
    let mut rest = Sets::default();
    for (k, t, s) in ranked {
        if top.len() < limit && t.reporters >= min {
            top.push((k, t));
        } else {
            rest.0.extend(s.0);
            rest.1.extend(s.1);
        }
    }
    let other = tally(&rest);
    (
        top,
        (other.iocs > 0 && other.reporters >= min).then_some(other),
    )
}

/// The top `limit` countries and networks of `pairs` (address, reporter),
/// by `geo`. Addresses not looked up are left out; those without a
/// country count as unknown, and those without a network are left out of
/// the networks. Every place needs `min` reporters to be shown.
#[must_use]
pub fn places(
    pairs: &[(String, String)],
    geo: &BTreeMap<String, IpGeo>,
    min: i64,
    limit: usize,
) -> Places {
    let found = || {
        pairs
            .iter()
            .filter_map(|(ip, r)| geo.get(ip).map(|g| (g, ip.as_str(), r.as_str())))
    };
    let (countries, other) = rank(
        found()
            .filter(|(g, ..)| g.country != UNKNOWN)
            .map(|(g, ip, r)| (g.country.as_str(), ip, r)),
        min,
        limit,
    );
    let (networks, other_networks) = rank(
        found()
            .filter(|(g, ..)| g.asn != 0)
            .map(|(g, ip, r)| (g.asn, ip, r)),
        min,
        limit,
    );
    let org = |asn: i64| {
        geo.values()
            .find(|g| g.asn == asn)
            .and_then(|g| g.as_org.clone())
    };
    let (_, unknown) = rank(
        found()
            .filter(|(g, ..)| g.country == UNKNOWN)
            .map(|(_, ip, r)| ((), ip, r)),
        min,
        0,
    );
    Places {
        countries: Ranked {
            top: countries
                .into_iter()
                .map(|(c, tally)| Country {
                    country: c.to_string(),
                    tally,
                })
                .collect(),
            other,
        },
        networks: Ranked {
            top: networks
                .into_iter()
                .map(|(asn, tally)| Network {
                    asn,
                    as_org: org(asn),
                    tally,
                })
                .collect(),
            other: other_networks,
        },
        unknown,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const NOW: i64 = 1_792_670_400_000_000_000;

    fn ioc(value: &str, last: i64, n: i64, r: i64) -> LiveIoc {
        LiveIoc {
            ioc_type: "ipv4".into(),
            value: value.into(),
            rule_id: None,
            last_received: last,
            sightings: n,
            reporters: r,
            seen_since: None,
            geo: None,
            listed: Vec::new(),
            common: false,
        }
    }

    #[test]
    fn windows_parse_and_bucket() {
        assert_eq!(Window::parse("6h"), Some(Window::SixHours));
        assert_eq!(Window::parse("2h"), None);
        let b = buckets(
            &[NOW, NOW - 1, NOW - 59 * MINUTE_NS, NOW - 61 * MINUTE_NS],
            Window::Hour,
            NOW,
        );
        assert_eq!(b.len(), 12);
        assert_eq!(b[11], (NOW, 1), "the bar holding now");
        assert_eq!(b[10].1, 1);
        assert_eq!(b[0].1, 0, "59 minutes back is before the first bar");
        assert_eq!(b.iter().map(|(_, n)| n).sum::<i64>(), 2);
        assert_eq!(buckets(&[], Window::Day, NOW).len(), 24);
    }

    #[test]
    fn values_are_quoted_and_chunked() {
        let sql = before_sql(5, "x", &["a'b"]);
        assert!(sql.contains("IN ('a''b')"), "{sql}");
        let many: Vec<LiveIoc> = (0..2500).map(|i| ioc(&i.to_string(), 0, 1, 1)).collect();
        assert_eq!(
            chunks(&many).iter().map(Vec::len).collect::<Vec<_>>(),
            [1000, 1000, 500]
        );
    }

    #[test]
    fn feed_is_newest_first_converging_by_reporters() {
        let all = [ioc("a", 1, 1, 1), ioc("b", 3, 5, 2), ioc("c", 2, 1, 3)];
        let (feed, converging) = lists(&all, 2);
        assert_eq!(
            feed.iter().map(|i| i.value.as_str()).collect::<Vec<_>>(),
            ["b", "c"]
        );
        assert_eq!(
            converging
                .iter()
                .map(|i| i.value.as_str())
                .collect::<Vec<_>>(),
            ["c", "b"]
        );
    }

    fn geo(ip: &str, country: &str, asn: i64, org: Option<&str>) -> (String, IpGeo) {
        let g = IpGeo {
            ip: ip.into(),
            ip_hex: String::new(),
            country: country.into(),
            asn,
            as_org: org.map(str::to_string),
            looked_up: 0,
            db_build: 0,
        };
        (ip.into(), g)
    }

    #[test]
    fn places_rank_by_reporters_and_hide_small_cells() {
        let geo: BTreeMap<String, IpGeo> = [
            geo("192.0.2.1", "NL", 64496, Some("Example Net")),
            geo("192.0.2.2", "NL", 64496, Some("Example Net")),
            geo("198.51.100.1", "DE", 64497, None),
            geo("198.51.100.2", "DE", 64497, None),
            geo("198.51.100.3", "DE", 64497, None),
            geo("203.0.113.1", "ZZ", 0, None),
        ]
        .into_iter()
        .collect();
        let pairs: Vec<(String, String)> = [
            ("192.0.2.1", "a"),
            ("192.0.2.1", "b"),
            ("192.0.2.2", "c"),
            ("198.51.100.1", "a"),
            ("198.51.100.2", "a"),
            ("198.51.100.3", "b"),
            ("203.0.113.1", "a"),
            ("2001:db8::1", "c"),
        ]
        .iter()
        .map(|(i, r)| (i.to_string(), r.to_string()))
        .collect();
        let t = |iocs, reporters| Tally { iocs, reporters };

        // Partner and up: every place, by reporters, then addresses.
        let p = places(&pairs, &geo, 1, 10);
        let c: Vec<(&str, Tally)> = p
            .countries
            .top
            .iter()
            .map(|c| (c.country.as_str(), c.tally))
            .collect();
        assert_eq!(c, [("NL", t(2, 3)), ("DE", t(3, 2))]);
        assert_eq!(p.countries.other, None);
        assert_eq!(
            (p.networks.top[0].asn, p.networks.top[0].as_org.as_deref()),
            (64496, Some("Example Net"))
        );
        assert_eq!(p.unknown, Some(t(1, 1)), "ZZ, not a country");

        // Below partner: DE has two reporters, so it is not shown, and
        // neither is the rest, which is DE alone.
        let p = places(&pairs, &geo, 3, 10);
        assert_eq!(p.countries.top.len(), 1);
        assert_eq!((p.countries.other, p.unknown), (None, None));

        // Beyond the top: taken together.
        let p = places(&pairs, &geo, 1, 1);
        assert_eq!(p.countries.other, Some(t(3, 2)));
    }
}
