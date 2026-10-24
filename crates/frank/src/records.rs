//! Sighting records for machine clients (#160, D4): the list behind
//! `GET /v1/sightings` and one record by id. A record is the normalised
//! sighting stored on its sighting's `seq = 0` row (`detail`), so only
//! sightings stored since 0.15 are listed.
//!
//! The list is ordered by `(ts, sighting_id)`, oldest first unless
//! `order=desc`, and paged by a cursor that is the last item's pair:
//! `{ts}.{sighting_id}`. It is filtered by Explore's dimensions, so a
//! list matches the Explore view it is opened from.

use std::collections::BTreeMap;

use db_core::engine::Cell;
use frank_core::sql_quote;
use serde_json::{json, Value};
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

use crate::explore::Dimension;

/// Records per page when the request names no `limit`.
pub const DEFAULT_LIMIT: usize = 100;
/// Most records one page may hold.
pub const MAX_LIMIT: usize = 500;
/// The window when the request names no `since`.
const DEFAULT_DAYS: i64 = 30;
const DAY_NS: i64 = 86_400 * 1_000_000_000;

/// The columns [`item`] reads, in order.
pub const COLUMNS: &str = "ts, sighting_id, reporter, received, detail";

/// One `GET /v1/sightings` request.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct List {
    pub since: i64,
    pub until: Option<i64>,
    /// Explore's filters: rule, ioc, campaign, technique, sector,
    /// ioc_type, severity.
    pub filters: Vec<(Dimension, String)>,
    /// Only the caller's own sightings.
    pub mine: bool,
    /// Newest first.
    pub desc: bool,
    /// The cursor: list after this `(ts, sighting_id)`.
    pub after: Option<(i64, String)>,
    pub limit: usize,
}

impl List {
    /// From query parameters: `since` and `until` (RFC 3339; the last 30
    /// days by default), one value per Explore dimension (`rule`, `ioc` as
    /// `type:value`, `campaign`, `technique`, `sector`, `ioc_type`,
    /// `severity`), `mine` (`true` or `false`), `order` (`asc` or `desc`),
    /// `cursor` and `limit` (1-500, default 100). Anything else is an
    /// error.
    pub fn parse(params: &BTreeMap<String, String>, now: i64) -> Result<List, String> {
        let mut q = List {
            since: now - DEFAULT_DAYS * DAY_NS,
            until: None,
            filters: Vec::new(),
            mine: false,
            desc: false,
            after: None,
            limit: DEFAULT_LIMIT,
        };
        for (k, v) in params {
            match k.as_str() {
                "since" => q.since = time(k, v)?,
                "until" => q.until = Some(time(k, v)?),
                "order" => {
                    q.desc = match v.as_str() {
                        "asc" => false,
                        "desc" => true,
                        _ => return Err("order: expected asc or desc".into()),
                    };
                }
                "mine" => {
                    q.mine = match v.as_str() {
                        "true" | "1" => true,
                        "false" | "0" => false,
                        _ => return Err("mine: expected true or false".into()),
                    };
                }
                "cursor" => q.after = Some(cursor(v).ok_or("cursor: not one this API gave")?),
                "limit" => {
                    q.limit = v
                        .parse()
                        .ok()
                        .filter(|n| (1..=MAX_LIMIT).contains(n))
                        .ok_or(format!("limit must be 1-{MAX_LIMIT}"))?;
                }
                other => {
                    let d =
                        Dimension::parse(other).ok_or(format!("unknown parameter {other:?}"))?;
                    d.condition(v, false)?;
                    q.filters.push((d, v.clone()));
                }
            }
        }
        Ok(q)
    }

    fn by_ioc(d: Dimension) -> bool {
        matches!(d, Dimension::Ioc | Dimension::IocType)
    }

    /// The conditions on `sightings` every listed row meets: the window,
    /// the visible TLP levels, the reporter when given, and the filters
    /// (`with_iocs`: also those on IoCs, which hold on one row of a
    /// sighting only).
    fn conditions(&self, visible: &str, reporter: Option<&str>, with_iocs: bool) -> Vec<String> {
        let mut c = vec![format!("ts >= {}", self.since), visible.to_string()];
        if let Some(until) = self.until {
            c.push(format!("ts < {until}"));
        }
        if let Some(r) = reporter {
            c.push(format!("reporter = {}", sql_quote(r)));
        }
        for (d, v) in &self.filters {
            if with_iocs || !Self::by_ioc(*d) {
                // Values were checked when the request was parsed.
                c.extend(d.condition(v, false).ok());
            }
        }
        c
    }

    /// With an `ioc` or `ioc_type` filter, the query for the ids of the
    /// sightings that match: on any of their rows, not only the first.
    #[must_use]
    pub fn ioc_sql(&self, visible: &str, reporter: Option<&str>) -> Option<String> {
        self.filters.iter().any(|(d, _)| Self::by_ioc(*d)).then(|| {
            format!(
                "SELECT DISTINCT sighting_id FROM sightings WHERE {}",
                self.conditions(visible, reporter, true).join(" AND ")
            )
        })
    }

    /// The page query: [`COLUMNS`] of the records after the cursor, one
    /// more than the limit so the caller knows whether a next page
    /// exists. `ids` are those [`List::ioc_sql`] found.
    #[must_use]
    pub fn sql(&self, visible: &str, reporter: Option<&str>, ids: Option<&[String]>) -> String {
        let mut c = self.conditions(visible, reporter, false);
        c.push("seq = 0".into());
        if let Some(ids) = ids {
            let ids: Vec<String> = ids.iter().map(|i| sql_quote(i)).collect();
            c.push(format!("sighting_id IN ({})", ids.join(", ")));
        }
        let (past, dir) = if self.desc { ("<", " DESC") } else { (">", "") };
        if let Some((ts, id)) = &self.after {
            c.push(format!(
                "(ts {past} {ts} OR (ts = {ts} AND sighting_id {past} {}))",
                sql_quote(id)
            ));
        }
        format!(
            "SELECT {COLUMNS} FROM sightings WHERE {} ORDER BY ts{dir}, sighting_id{dir} LIMIT {}",
            c.join(" AND "),
            self.limit + 1
        )
    }
}

/// One record from a row of [`COLUMNS`], with its cursor: the sighting id,
/// the participant that sent it, when the server stored it and the
/// normalised sighting. `None` for a row without a record.
#[must_use]
pub fn item(row: &[Cell]) -> Option<(String, Value)> {
    let (Cell::Int(ts), Cell::Text(id), Cell::Text(reporter), Cell::Text(detail)) =
        (&row[0], &row[1], &row[2], &row[4])
    else {
        return None;
    };
    let received = match &row[3] {
        Cell::Int(ns) => rfc3339(*ns),
        _ => Value::Null,
    };
    let record: Value = serde_json::from_str(detail).ok()?;
    Some((
        format!("{ts}.{id}"),
        json!({ "sighting_id": id, "reporter": reporter, "received": received, "record": record }),
    ))
}

/// The time `ns` as RFC 3339, or null.
#[must_use]
pub fn rfc3339(ns: i64) -> Value {
    OffsetDateTime::from_unix_timestamp_nanos(i128::from(ns))
        .ok()
        .and_then(|t| t.format(&Rfc3339).ok())
        .map_or(Value::Null, Value::String)
}

fn time(key: &str, v: &str) -> Result<i64, String> {
    OffsetDateTime::parse(v, &Rfc3339)
        .ok()
        .and_then(|t| i64::try_from(t.unix_timestamp_nanos()).ok())
        .ok_or(format!(
            "{key}: expected an RFC 3339 time, such as 2026-10-22T00:00:00Z"
        ))
}

/// A cursor `{ts}.{sighting_id}` this API gave.
fn cursor(v: &str) -> Option<(i64, String)> {
    let (ts, id) = v.split_once('.')?;
    let id = frank_core::model::sighting_id(id).ok()?;
    Some((ts.parse().ok()?, id))
}

#[cfg(test)]
mod tests {
    use super::*;

    const NOW: i64 = 1_792_670_400_000_000_000;
    const ID: &str = "sighting--0f8fad5b-d9cb-469f-a165-70867728950e";

    fn params(kv: &[(&str, &str)]) -> BTreeMap<String, String> {
        kv.iter()
            .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
            .collect()
    }

    #[test]
    fn parses_and_refuses() {
        let q = List::parse(
            &params(&[
                ("since", "2026-10-01T00:00:00Z"),
                ("ioc", "IPv4:198.51.100.7"),
                ("mine", "true"),
                ("limit", "10"),
                ("cursor", &format!("5.{ID}")),
            ]),
            NOW,
        )
        .unwrap();
        assert_eq!(q.since, 1_790_812_800_000_000_000);
        assert_eq!(
            q.filters,
            [(Dimension::Ioc, "IPv4:198.51.100.7".to_string())]
        );
        assert!(q.mine);
        assert_eq!((q.limit, q.after), (10, Some((5, ID.to_string()))));
        let bad = |kv: &[(&str, &str)]| List::parse(&params(kv), NOW).is_err();
        assert!(bad(&[("limit", "0")]));
        assert!(bad(&[("limit", "501")]));
        assert!(bad(&[("since", "yesterday")]));
        assert!(bad(&[("cursor", "5.x' OR '1'='1")]));
        assert!(bad(&[("reporter", "x")]));
        assert!(bad(&[("mine", "yes")]));
        assert!(bad(&[("order", "up")]));
        assert!(bad(&[("ioc", "ipv4:1.2.3")]));
    }

    #[test]
    fn filters_split_by_where_they_hold() {
        let q = List::parse(
            &params(&[
                ("sector", "Energy"),
                ("ioc_type", "ipv4"),
                ("technique", "t1059"),
                ("order", "desc"),
            ]),
            NOW,
        )
        .unwrap();
        let ids = q.ioc_sql("x", None).unwrap();
        assert!(
            ids.contains("ioc_type = 'ipv4'") && ids.contains("target_sector = 'energy'"),
            "{ids}"
        );
        let page = q.sql("x", None, Some(&["s".into()]));
        assert!(!page.contains("ioc_type"), "IoCs are on any row: {page}");
        assert!(
            page.contains("target_sector = 'energy'") && page.contains("technique LIKE"),
            "{page}"
        );
        assert!(
            page.contains("ORDER BY ts DESC, sighting_id DESC"),
            "{page}"
        );
    }

    #[test]
    fn pages_after_the_cursor_one_record_a_sighting() {
        let q = List::parse(
            &params(&[("rule", "x' OR '1'='1"), ("cursor", &format!("5.{ID}"))]),
            NOW,
        )
        .unwrap();
        let sql = q.sql("tlp = 'green'", Some("identity--a"), None);
        assert!(sql.contains("rule_id = 'x'' OR ''1''=''1'"), "{sql}");
        assert!(sql.contains("seq = 0"), "{sql}");
        assert!(sql.contains("reporter = 'identity--a'"), "{sql}");
        assert!(sql.contains(&format!("(ts > 5 OR (ts = 5 AND sighting_id > '{ID}'))")));
        assert!(sql.ends_with("ORDER BY ts, sighting_id LIMIT 101"), "{sql}");
        assert!(q.ioc_sql("x", None).is_none());
    }
}
