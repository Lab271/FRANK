//! The Explore query model (#157): group the visible sightings by one
//! dimension, filtered by others. Dimensions and filters are a fixed set,
//! so callers pick from a whitelist and never send SQL (ADR-016).

use std::collections::BTreeMap;

use frank_core::{sql_quote, Tier};

/// What a list can be grouped and filtered by.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Dimension {
    Rule,
    Ioc,
    Campaign,
    Technique,
    Sector,
    IocType,
    Severity,
}

impl Dimension {
    pub const ALL: [Dimension; 7] = [
        Dimension::Rule,
        Dimension::Ioc,
        Dimension::Campaign,
        Dimension::Technique,
        Dimension::Sector,
        Dimension::IocType,
        Dimension::Severity,
    ];

    #[must_use]
    pub fn name(self) -> &'static str {
        match self {
            Dimension::Rule => "rule",
            Dimension::Ioc => "ioc",
            Dimension::Campaign => "campaign",
            Dimension::Technique => "technique",
            Dimension::Sector => "sector",
            Dimension::IocType => "ioc_type",
            Dimension::Severity => "severity",
        }
    }

    #[must_use]
    pub fn parse(s: &str) -> Option<Dimension> {
        Dimension::ALL.into_iter().find(|d| d.name() == s)
    }

    /// The `sightings` columns behind the dimension; an IoC is its type and
    /// value together.
    #[must_use]
    pub fn columns(self) -> &'static [&'static str] {
        match self {
            Dimension::Rule => &["rule_id"],
            Dimension::Ioc => &["ioc_type", "ioc_value"],
            Dimension::Campaign => &["campaign"],
            Dimension::Technique => &["technique"],
            Dimension::Sector => &["target_sector"],
            Dimension::IocType => &["ioc_type"],
            Dimension::Severity => &["severity"],
        }
    }

    /// The lowest tier that may group or filter by it, as in
    /// `/v1/statistics`: categories from observer up, what was detected
    /// (rules, techniques, campaigns, IoCs) from contributor up.
    #[must_use]
    pub fn min_tier(self) -> Tier {
        match self {
            Dimension::Sector | Dimension::IocType | Dimension::Severity => Tier::Observer,
            _ => Tier::Contributor,
        }
    }

    /// The SQL condition for one filter value. An IoC filter is
    /// `type:value`; categories are lower case.
    fn condition(self, value: &str) -> Result<String, String> {
        let v = value.trim();
        if v.is_empty() || v.len() > 2048 || v.chars().any(char::is_control) {
            return Err(format!("{}: not a usable filter value", self.name()));
        }
        Ok(match self {
            Dimension::Ioc => {
                let (t, value) = v
                    .split_once(':')
                    .ok_or("ioc: expected type:value, such as ipv4:198.51.100.7")?;
                let t = frank_core::IocType::parse(t).ok_or(format!("ioc: unknown type {t:?}"))?;
                let ioc = frank_core::Ioc::new(t, value).map_err(|e| e.to_string())?;
                format!(
                    "ioc_type = {} AND ioc_value = {}",
                    sql_quote(t.as_str()),
                    sql_quote(&ioc.value)
                )
            }
            Dimension::Sector | Dimension::IocType | Dimension::Severity => {
                format!(
                    "{} = {}",
                    self.columns()[0],
                    sql_quote(&v.to_ascii_lowercase())
                )
            }
            _ => format!("{} = {}", self.columns()[0], sql_quote(v)),
        })
    }
}

/// One Explore request: a grouping, a time window and filters.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Query {
    pub group: Dimension,
    pub days: i64,
    pub filters: Vec<(Dimension, String)>,
}

impl Query {
    /// From query parameters: `group`, `days` (1-3650, default 30) and one
    /// value per dimension name. Anything else is an error.
    pub fn parse(params: &BTreeMap<String, String>) -> Result<Query, String> {
        let mut group = None;
        let mut days = 30;
        let mut filters = Vec::new();
        for (k, v) in params {
            match k.as_str() {
                "group" => {
                    group = Some(Dimension::parse(v).ok_or(format!("unknown group {v:?}"))?);
                }
                "days" => {
                    days = v
                        .parse::<i64>()
                        .ok()
                        .filter(|d| (1..=3650).contains(d))
                        .ok_or("days must be 1-3650")?;
                }
                other => {
                    let d = Dimension::parse(other).ok_or(format!("unknown filter {other:?}"))?;
                    d.condition(v)?;
                    filters.push((d, v.clone()));
                }
            }
        }
        Ok(Query {
            group: group.ok_or("group is required")?,
            days,
            filters,
        })
    }

    /// The tier the request needs: the highest of its dimensions.
    #[must_use]
    pub fn min_tier(&self) -> Tier {
        self.filters
            .iter()
            .map(|(d, _)| d.min_tier())
            .chain([self.group.min_tier()])
            .max()
            .unwrap_or(Tier::Observer)
    }

    /// The WHERE clause: the window, the visible TLP levels, the filters.
    pub fn where_clause(&self, since: i64, visible: &str) -> Result<String, String> {
        let mut parts = vec![format!("ts >= {since}"), visible.to_string()];
        for (d, v) in &self.filters {
            parts.push(d.condition(v)?);
        }
        Ok(parts.join(" AND "))
    }

    /// The grouped query: the group's columns, then rows, distinct
    /// reporters, first and last time.
    pub fn sql(&self, since: i64, visible: &str) -> Result<String, String> {
        let cols = self.group.columns().join(", ");
        Ok(format!(
            "SELECT {cols}, count(*) AS n, count(DISTINCT reporter) AS r, min(ts), max(ts) \
             FROM sightings WHERE {} GROUP BY {cols} ORDER BY n DESC",
            self.where_clause(since, visible)?
        ))
    }
}

/// Per-day counts over `days` days ending today, oldest first, zeros
/// included: `[("2026-10-21", 3), ...]`.
#[must_use]
pub fn trend(ts: &[i64], now: i64, days: i64) -> Vec<(String, i64)> {
    const DAY_NS: i64 = 86_400 * 1_000_000_000;
    let today = now.div_euclid(DAY_NS);
    let first = today - days + 1;
    let mut counts: BTreeMap<i64, i64> = (first..=today).map(|d| (d, 0)).collect();
    for t in ts {
        if let Some(n) = counts.get_mut(&t.div_euclid(DAY_NS)) {
            *n += 1;
        }
    }
    counts
        .into_iter()
        .map(|(d, n)| (crate::store::iocs::day_label(d), n))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn params(kv: &[(&str, &str)]) -> BTreeMap<String, String> {
        kv.iter()
            .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
            .collect()
    }

    #[test]
    fn parses_and_refuses() {
        let q = Query::parse(&params(&[
            ("group", "rule"),
            ("sector", "Energy"),
            ("days", "7"),
        ]))
        .unwrap();
        assert_eq!((q.group, q.days), (Dimension::Rule, 7));
        assert!(
            Query::parse(&params(&[("sector", "energy")])).is_err(),
            "no group"
        );
        assert!(Query::parse(&params(&[("group", "org")])).is_err());
        assert!(Query::parse(&params(&[("group", "rule"), ("reporter", "x")])).is_err());
        assert!(Query::parse(&params(&[("group", "rule"), ("days", "0")])).is_err());
        assert!(Query::parse(&params(&[("group", "rule"), ("ioc", "nope")])).is_err());
    }

    #[test]
    fn tier_is_the_highest_dimension() {
        let q = |kv| Query::parse(&params(kv)).unwrap().min_tier();
        assert_eq!(q(&[("group", "sector")]), Tier::Observer);
        assert_eq!(q(&[("group", "sector"), ("rule", "r1")]), Tier::Contributor);
        assert_eq!(q(&[("group", "ioc")]), Tier::Contributor);
    }

    #[test]
    fn values_are_quoted_and_normalised() {
        let q = Query::parse(&params(&[
            ("group", "ioc"),
            ("rule", "x' OR '1'='1"),
            ("ioc", "IPv4:198.51.100.7"),
            ("severity", "HIGH"),
        ]))
        .unwrap();
        let w = q.where_clause(0, "tlp = 'green'").unwrap();
        assert!(w.contains("rule_id = 'x'' OR ''1''=''1'"), "{w}");
        assert!(
            w.contains("ioc_type = 'ipv4' AND ioc_value = '198.51.100.7'"),
            "{w}"
        );
        assert!(w.contains("severity = 'high'"), "{w}");
        assert!(q
            .sql(0, "tlp = 'green'")
            .unwrap()
            .contains("GROUP BY ioc_type, ioc_value"));
    }

    #[test]
    fn trend_fills_empty_days() {
        let day = 86_400 * 1_000_000_000_i64;
        let now = 20_748 * day + 5;
        let t = trend(&[now, now - day, now - day, 3 * day], now, 3);
        assert_eq!(
            t,
            [
                ("2026-10-20".into(), 0),
                ("2026-10-21".into(), 2),
                ("2026-10-22".into(), 1)
            ]
        );
    }
}
