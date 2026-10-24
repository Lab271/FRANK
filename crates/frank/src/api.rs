//! The HTTP API. Every query is a fixed, typed query over the two stores;
//! no SQL is taken from a caller (ADR-016).
//!
//! | Route                     | Tier        |
//! |---------------------------|-------------|
//! | `GET  /health`            | none        |
//! | `GET  /v1/whoami`         | any         |
//! | `POST /v1/preview`        | any         |
//! | `GET  /v1/statistics`     | any (detail grows with the tier) |
//! | `POST /v1/sightings`      | contributor |
//! | `GET  /v1/iocs`           | contributor |
//! | `GET  /v1/iocs/range`     | contributor |
//! | `GET  /v1/files`, `/v1/files/{*path}` | partner |
//! | `GET  /v1/participants`   | partner (ids and status), core (all details) |

use std::collections::BTreeMap;
use std::net::IpAddr;
use std::path::{Component, Path};
use std::sync::Arc;

use axum::extract::{DefaultBodyLimit, Query, State};
use axum::http::{header, HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use db_core::engine::Cell;
use frank_core::{sql_quote, Ioc, IocType, Sighting, Tier, Tlp, MIN_CELL};
use serde::Deserialize;
use serde_json::{json, Value};

use crate::audit::Audit;
use crate::auth::Caller;
use crate::explore::{self as ex, Dimension, FIRST_ROW};
use crate::store::registry::{self, Receipt};
use crate::store::sightings::{scalar, NAME as SIGHTINGS, TECHNIQUES};
use crate::store::{Iocs, Participants, Registry, Sightings};

const DAY_NS: i64 = 86_400 * 1_000_000_000;
/// Most submissions in one POST.
const MAX_BATCH: usize = 100;
const MAX_BODY: usize = 2 * 1024 * 1024;
/// The rows not yet in a file, served as one Parquet file written on request.
pub const OPEN_FILE: &str = "open/current.parquet";
/// Days in a detail pane's trend.
const TREND_DAYS: i64 = 30;

pub struct App {
    pub sightings: Sightings,
    pub iocs: Iocs,
    pub participants: Participants,
    pub registry: Registry,
    pub audit: Audit,
    /// Makes "is it registered, store it, register it" one step.
    pub submit_lock: std::sync::Mutex<()>,
    /// Wall clock in ns; tests set their own.
    pub now: fn() -> i64,
}

pub type Shared = Arc<App>;

#[derive(Debug)]
pub struct ApiError(StatusCode, String);

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (self.0, Json(json!({ "error": self.1 }))).into_response()
    }
}

fn internal(e: impl std::fmt::Display) -> ApiError {
    tracing::error!("{e}");
    ApiError(StatusCode::INTERNAL_SERVER_ERROR, "internal error".into())
}

fn unprocessable(e: impl std::fmt::Display) -> ApiError {
    ApiError(StatusCode::UNPROCESSABLE_ENTITY, e.to_string())
}

/// The caller the request's bearer token names, at least `tier`.
fn require(app: &App, headers: &HeaderMap, tier: Tier) -> Result<Caller, ApiError> {
    let auth = headers
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok());
    let caller = app
        .participants
        .caller(auth)
        .map_err(internal)?
        .ok_or_else(|| ApiError(StatusCode::UNAUTHORIZED, "unknown token".into()))?;
    if caller.tier < tier {
        return Err(ApiError(
            StatusCode::FORBIDDEN,
            format!("needs the {tier} tier; this token is {}", caller.tier),
        ));
    }
    Ok(caller)
}

/// Runs blocking store work off the async runtime.
async fn blocking<T: Send + 'static>(
    f: impl FnOnce() -> Result<T, ApiError> + Send + 'static,
) -> Result<T, ApiError> {
    tokio::task::spawn_blocking(f).await.map_err(internal)?
}

pub fn router(app: Shared) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/v1/whoami", get(whoami))
        .route("/v1/preview", post(preview))
        .route("/v1/statistics", get(statistics))
        .route("/v1/sightings", post(submit))
        .route("/v1/iocs", get(ioc_lookup))
        .route("/v1/iocs/range", get(ioc_range))
        .route("/v1/explore", get(explore))
        .route("/v1/rules/{id}", get(rule_detail))
        .route("/v1/participants", get(participants))
        .route("/v1/files", get(files))
        .route("/v1/files/{*path}", get(file))
        .layer(DefaultBodyLimit::max(MAX_BODY))
        .with_state(app)
}

async fn health() -> Json<Value> {
    Json(json!({ "status": "ok", "version": env!("CARGO_PKG_VERSION") }))
}

async fn whoami(State(app): State<Shared>, headers: HeaderMap) -> Result<Json<Value>, ApiError> {
    let c = require(&app, &headers, Tier::Public)?;
    if c.user.is_empty() {
        return Ok(Json(json!({ "tier": c.tier, "label": c.label() })));
    }
    Ok(Json(json!({
        "tier": c.tier,
        "label": c.label(),
        "user": c.user,
        "participant": { "id": c.participant, "name": c.organisation, "status": c.tier },
    })))
}

/// One submission or an array of them.
fn submissions(body: &Value, now: i64) -> Result<Vec<Sighting>, ApiError> {
    let items: Vec<&Value> = match body {
        Value::Array(a) if a.len() > MAX_BATCH => {
            return Err(unprocessable(format!("more than {MAX_BATCH} submissions")))
        }
        Value::Array(a) => a.iter().collect(),
        v => vec![v],
    };
    items
        .into_iter()
        .enumerate()
        .map(|(i, v)| Sighting::from_value(v, now).map_err(|e| unprocessable(format!("[{i}] {e}"))))
        .collect()
}

/// The rows a submission would add, without storing anything: what leaves
/// the contributor, shown before it leaves.
async fn preview(
    State(app): State<Shared>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Json<Value>, ApiError> {
    require(&app, &headers, Tier::Public)?;
    let subs = submissions(&body, (app.now)())?;
    let rows: Vec<_> = subs
        .iter()
        .flat_map(|s| s.rows("sighting--preview"))
        .collect();
    Ok(Json(json!({ "rows": rows })))
}

/// Stores a batch of submissions from one sender. Each carries the
/// sender's `sighting_id`; with the participant it is the registration
/// (#159). A sighting sent again with the same content gets its original
/// receipt; other content under a registered id is a conflict (409) and
/// nothing of the batch is stored. 201 when anything was new, else 200.
async fn submit(
    State(app): State<Shared>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Result<Response, ApiError> {
    let caller = require(&app, &headers, Tier::Contributor)?;
    let subs = submissions(&body, (app.now)())?;
    let mut items: Vec<(String, String, Sighting)> = Vec::with_capacity(subs.len());
    for (i, s) in subs.into_iter().enumerate() {
        let id = s.sighting_id.clone().ok_or_else(|| {
            unprocessable(format!(
                "[{i}] sighting.sighting_id is required: a UUID the sender chooses, so a resend is recognised"
            ))
        })?;
        let digest = registry::digest(&s);
        match items.iter().find(|(other, _, _)| *other == id) {
            Some((_, d, _)) if *d == digest => {}
            Some(_) => {
                return Err(unprocessable(format!(
                    "[{i}] {id} appears twice in the batch with different content"
                )))
            }
            None => items.push((id, digest, s)),
        }
    }
    let app2 = app.clone();
    let caller2 = caller.clone();
    let (receipts, rows) = blocking(move || {
        let app = app2;
        let _one_at_a_time = app.submit_lock.lock().map_err(internal)?;
        let ids = items.iter().map(|(id, _, _)| id.clone()).collect();
        let known = app.registry.find(&caller2.participant, ids).map_err(internal)?;
        let conflicts: Vec<&str> = items
            .iter()
            .filter(|(id, d, _)| known.get(id).is_some_and(|(k, _)| k != d))
            .map(|(id, _, _)| id.as_str())
            .collect();
        if !conflicts.is_empty() {
            app.audit
                .record(
                    (app.now)(),
                    &caller2.label(),
                    "submit_refused",
                    json!({ "participant": caller2.participant, "conflicts": conflicts }),
                )
                .map_err(internal)?;
            return Err(ApiError(
                StatusCode::CONFLICT,
                format!(
                    "already registered with other content: {}; nothing was stored (corrections: #161)",
                    conflicts.join(", ")
                ),
            ));
        }
        let now = (app.now)();
        let mut rows = Vec::new();
        let mut fresh = Vec::new();
        let mut receipts = Vec::with_capacity(items.len());
        for (id, digest, s) in items {
            if let Some((_, received)) = known.get(&id) {
                receipts.push(Receipt { sighting_id: id, digest, received: *received, status: "duplicate" });
                continue;
            }
            // Sightings are stored under the organisation, never the user,
            // and carry their registration.
            rows.extend(s.rows(&id).into_iter().map(|mut r| {
                r.reporter.clone_from(&caller2.participant);
                r.digest.clone_from(&digest);
                r.received_ns = now;
                r
            }));
            fresh.push((caller2.participant.clone(), id.clone(), digest.clone(), now));
            receipts.push(Receipt { sighting_id: id, digest, received: now, status: "created" });
        }
        if !fresh.is_empty() {
            // Rows first: they hold the registration. Both indexes can be
            // rebuilt from them (`frank rebuild`).
            app.sightings.append(&rows).map_err(internal)?;
            app.iocs.record(&rows).map_err(internal)?;
            app.registry.register(fresh).map_err(internal)?;
        }
        app.audit
            .record(
                now,
                &caller2.label(),
                "submit",
                json!({ "participant": caller2.participant, "receipts": receipts }),
            )
            .map_err(internal)?;
        Ok((receipts, rows.len()))
    })
    .await?;
    let created = receipts.iter().filter(|r| r.status == "created").count();
    tracing::info!(caller = %caller.label(), created, duplicates = receipts.len() - created, rows, "accepted");
    let status = if created > 0 {
        StatusCode::CREATED
    } else {
        StatusCode::OK
    };
    Ok((status, Json(json!({ "receipts": receipts, "rows": rows }))).into_response())
}

#[derive(Deserialize)]
struct StatsQuery {
    days: Option<i64>,
}

/// The SQL condition for the TLP levels `tier` may see (#149).
fn tlp_visible(tier: Tier) -> String {
    let levels: Vec<String> = Tlp::visible_to(tier)
        .into_iter()
        .map(|t| sql_quote(t.as_str()))
        .collect();
    format!("tlp IN ({})", levels.join(", "))
}

/// `(key, sightings, reporters)` per value of `column` over the rows
/// `visible` selects, counted as [`ex::Query::sql`] does: `seq = 0` rows,
/// all rows for the IoC type, `sighting_techniques` for techniques. Unless
/// `exact`, a cell with fewer than [`MIN_CELL`] distinct reporters is
/// dropped: k-anonymity counts reporters, not rows (#148).
fn breakdown(
    s: &Sightings,
    column: &str,
    visible: &str,
    since: i64,
    limit: usize,
    exact: bool,
) -> Result<Vec<Value>, ApiError> {
    let (table, rows) = match column {
        "technique" => (TECHNIQUES, String::new()),
        "ioc_type" => (SIGHTINGS, String::new()),
        _ => (SIGHTINGS, format!(" AND {FIRST_ROW}")),
    };
    let sql = format!(
        "SELECT {column}, count(*) AS n, count(DISTINCT reporter) AS r FROM {table} WHERE ts >= {since} AND {visible}{rows} GROUP BY {column} ORDER BY n DESC"
    );
    let r = if column == "technique" {
        s.query_techniques(&sql)
    } else {
        s.query(&sql)
    }
    .map_err(internal)?;
    Ok(r.rows
        .iter()
        .filter_map(|row| match (&row[0], &row[1], &row[2]) {
            (Cell::Text(k), Cell::Int(n), Cell::Int(r)) if exact || *r >= MIN_CELL => {
                Some(json!({ "key": k, "count": n, "reporters": r }))
            }
            _ => None,
        })
        .take(limit)
        .collect())
}

async fn statistics(
    State(app): State<Shared>,
    headers: HeaderMap,
    Query(q): Query<StatsQuery>,
) -> Result<Json<Value>, ApiError> {
    let caller = require(&app, &headers, Tier::Public)?;
    let days = q.days.unwrap_or(30);
    if !(1..=3650).contains(&days) {
        return Err(unprocessable("days must be 1-3650"));
    }
    let since = (app.now)() - days * DAY_NS;
    let visible = tlp_visible(caller.tier);
    blocking(move || {
        let s = &app.sightings;
        let v = visible.as_str();
        let q = |sql: &str| s.query(sql).map(|r| scalar(&r)).map_err(internal);
        let mut out = json!({
            "tier": caller.tier,
            "days": days,
            "sightings": q(&format!("SELECT count(DISTINCT sighting_id) FROM sightings WHERE ts >= {since} AND {v}"))?,
            "observations": q(&format!("SELECT sum(observations) FROM sightings WHERE ts >= {since} AND {v} AND {FIRST_ROW}"))?,
            "iocs": app.iocs.count(&Tlp::visible_to(caller.tier)).map_err(internal)?,
        });
        let exact = caller.tier >= Tier::Partner;
        if caller.tier >= Tier::Observer {
            out["min_cell"] = json!(if exact { 1 } else { MIN_CELL });
            out["by_ioc_type"] = json!(breakdown(s, "ioc_type", v, since, 20, exact)?);
            out["by_severity"] = json!(breakdown(s, "severity", v, since, 10, exact)?);
            out["by_target_sector"] = json!(breakdown(s, "target_sector", v, since, 30, exact)?);
        }
        if caller.tier >= Tier::Contributor {
            out["top_rules"] = json!(breakdown(s, "rule_id", v, since, 25, exact)?);
            out["top_techniques"] = json!(breakdown(s, "technique", v, since, 25, exact)?);
            out["top_campaigns"] = json!(breakdown(s, "campaign", v, since, 25, exact)?);
        }
        Ok(Json(out))
    })
    .await
}

#[derive(Deserialize)]
struct IocQuery {
    #[serde(rename = "type")]
    ioc_type: String,
    value: String,
}

async fn ioc_lookup(
    State(app): State<Shared>,
    headers: HeaderMap,
    Query(q): Query<IocQuery>,
) -> Result<Json<Value>, ApiError> {
    let caller = require(&app, &headers, Tier::Contributor)?;
    let t = IocType::parse(&q.ioc_type)
        .ok_or_else(|| unprocessable(format!("unknown IoC type {:?}", q.ioc_type)))?;
    let ioc = Ioc::new(t, &q.value).map_err(unprocessable)?;
    blocking(move || {
        let days = app
            .iocs
            .lookup(&ioc, &Tlp::visible_to(caller.tier))
            .map_err(internal)?;
        let now = (app.now)();
        let (rules, reporters, trend) = if days.is_empty() {
            (Vec::new(), 0, ex::trend(&[], now, TREND_DAYS))
        } else {
            let filter = format!(
                "ioc_value = {} AND ts >= {} AND {}",
                sql_quote(&ioc.value),
                days[0].first_ts,
                tlp_visible(caller.tier),
            );
            let r = app
                .sightings
                .query(&format!(
                    "SELECT rule_id, count(*) AS n FROM sightings WHERE {filter} GROUP BY rule_id ORDER BY n DESC"
                ))
                .map_err(internal)?;
            let rules = r
                .rows
                .iter()
                .filter_map(|row| match (&row[0], &row[1]) {
                    (Cell::Text(k), Cell::Int(n)) => Some(json!({ "rule_id": k, "count": n })),
                    _ => None,
                })
                .collect();
            let reporters = app
                .sightings
                .query(&format!(
                    "SELECT count(DISTINCT reporter) FROM sightings WHERE {filter}"
                ))
                .map(|r| scalar(&r))
                .map_err(internal)?;
            let ts = times(&app.sightings, &filter)?;
            (rules, reporters, ex::trend(&ts, now, TREND_DAYS))
        };
        Ok(Json(json!({
            "ioc": ioc,
            "known": !days.is_empty(),
            "count": days.iter().map(|d| d.count).sum::<i64>(),
            "reporters": reporters,
            "first_seen": days.first().map(|d| d.first_ts),
            "last_seen": days.iter().map(|d| d.last_ts).max(),
            "days": days,
            "rules": rules,
            "trend": trend,
        })))
    })
    .await
}

/// The `ts` of every row `filter` selects, for a trend.
fn times(s: &Sightings, filter: &str) -> Result<Vec<i64>, ApiError> {
    let r = s
        .query(&format!("SELECT ts FROM sightings WHERE {filter}"))
        .map_err(internal)?;
    Ok(r.rows
        .iter()
        .filter_map(|row| match row.first() {
            Some(Cell::Int(t)) => Some(*t),
            _ => None,
        })
        .collect())
}

/// The rows of an Explore query: `{key, count, reporters, first_seen,
/// last_seen}`, at most `limit`. Below partner (`exact` false) a group
/// with fewer than [`MIN_CELL`] distinct reporters is dropped (#148).
fn grouped(
    s: &Sightings,
    q: &ex::Query,
    since: i64,
    visible: &str,
    exact: bool,
    limit: usize,
) -> Result<Vec<Value>, ApiError> {
    let sql = q.sql(since, visible).map_err(unprocessable)?;
    let r = if q.on_techniques() {
        s.query_techniques(&sql)
    } else {
        s.query(&sql)
    }
    .map_err(internal)?;
    let k = q.group.columns().len();
    Ok(r.rows
        .iter()
        .filter_map(|row| {
            let key: Option<Vec<&str>> = row[..k]
                .iter()
                .map(|c| match c {
                    Cell::Text(t) => Some(t.as_str()),
                    _ => None,
                })
                .collect();
            match (key, &row[k], &row[k + 1], &row[k + 2], &row[k + 3]) {
                (Some(key), Cell::Int(n), Cell::Int(r), Cell::Int(first), Cell::Int(last))
                    if exact || *r >= MIN_CELL =>
                {
                    Some(json!({
                        "key": key.join(":"),
                        "count": n,
                        "reporters": r,
                        "first_seen": first,
                        "last_seen": last,
                    }))
                }
                _ => None,
            }
        })
        .take(limit)
        .collect())
}

/// `GET /v1/explore?group=rule&sector=energy&days=30` (#157).
async fn explore(
    State(app): State<Shared>,
    headers: HeaderMap,
    Query(params): Query<BTreeMap<String, String>>,
) -> Result<Json<Value>, ApiError> {
    let q = ex::Query::parse(&params).map_err(unprocessable)?;
    let caller = require(&app, &headers, q.min_tier())?;
    let since = (app.now)() - q.days * DAY_NS;
    let visible = tlp_visible(caller.tier);
    let exact = caller.tier >= Tier::Partner;
    blocking(move || {
        let rows = grouped(&app.sightings, &q, since, &visible, exact, 100)?;
        Ok(Json(json!({
            "group": q.group.name(),
            "days": q.days,
            "filters": q.filters.iter().map(|(d, v)| (d.name(), v)).collect::<BTreeMap<_, _>>(),
            "min_cell": if exact { 1 } else { MIN_CELL },
            "rows": rows,
        })))
    })
    .await
}

/// `GET /v1/rules/{id}?days=30`: one rule's prevalence (#157). A rule seen
/// by fewer than [`MIN_CELL`] reporters is reported as unknown below
/// partner, as it would be in a list.
async fn rule_detail(
    State(app): State<Shared>,
    headers: HeaderMap,
    axum::extract::Path(id): axum::extract::Path<String>,
    Query(q): Query<StatsQuery>,
) -> Result<Json<Value>, ApiError> {
    let caller = require(&app, &headers, Tier::Contributor)?;
    let days = q.days.unwrap_or(TREND_DAYS);
    if !(1..=3650).contains(&days) {
        return Err(unprocessable("days must be 1-3650"));
    }
    let now = (app.now)();
    let since = now - days * DAY_NS;
    let visible = tlp_visible(caller.tier);
    let exact = caller.tier >= Tier::Partner;
    let by = move |group| ex::Query {
        group,
        days,
        filters: vec![(Dimension::Rule, id.clone())],
    };
    blocking(move || {
        let s = &app.sightings;
        let total = grouped(s, &by(Dimension::Rule), since, &visible, exact, 1)?;
        let Some(total) = total.into_iter().next() else {
            return Ok(Json(
                json!({ "rule": by(Dimension::Rule).filters[0].1, "known": false }),
            ));
        };
        let base = by(Dimension::Rule);
        let filter = format!(
            "{} AND {FIRST_ROW}",
            base.where_clause(since, &visible).map_err(unprocessable)?
        );
        let list = |d, n| grouped(s, &by(d), since, &visible, exact, n);
        Ok(Json(json!({
            "rule": total["key"],
            "known": true,
            "days": days,
            "count": total["count"],
            "reporters": total["reporters"],
            "first_seen": total["first_seen"],
            "last_seen": total["last_seen"],
            "trend": ex::trend(&times(s, &filter)?, now, days.min(90)),
            "sectors": list(Dimension::Sector, 20)?,
            "severities": list(Dimension::Severity, 10)?,
            "techniques": list(Dimension::Technique, 10)?,
            "campaigns": list(Dimension::Campaign, 10)?,
            "iocs": list(Dimension::Ioc, 15)?,
        })))
    })
    .await
}

#[derive(Deserialize)]
struct RangeQuery {
    cidr: String,
}

/// The first and last address of a CIDR block, as 32 hex digits.
fn cidr_bounds(cidr: &str) -> Option<(String, String)> {
    let (addr, len) = cidr.trim().split_once('/')?;
    let ip: IpAddr = addr.parse().ok()?;
    let len: u32 = len.parse().ok()?;
    let (base, bits) = match ip {
        IpAddr::V4(v4) => (u128::from(v4.to_ipv6_mapped()), 32),
        IpAddr::V6(v6) => (u128::from(v6), 128),
    };
    if len > bits {
        return None;
    }
    let host = bits - len;
    let mask = if host == 128 {
        u128::MAX
    } else {
        (1u128 << host) - 1
    };
    let lo = base & !mask;
    Some((format!("{lo:032x}"), format!("{:032x}", lo | mask)))
}

async fn ioc_range(
    State(app): State<Shared>,
    headers: HeaderMap,
    Query(q): Query<RangeQuery>,
) -> Result<Json<Value>, ApiError> {
    let caller = require(&app, &headers, Tier::Contributor)?;
    let (lo, hi) = cidr_bounds(&q.cidr)
        .ok_or_else(|| unprocessable("expected a CIDR block such as 185.220.0.0/16"))?;
    blocking(move || {
        let hits = app
            .iocs
            .ip_range(&lo, &hi, &Tlp::visible_to(caller.tier), 1000)
            .map_err(internal)?;
        let hits: Vec<Value> = hits
            .into_iter()
            .map(|(v, n)| json!({ "value": v, "count": n }))
            .collect();
        Ok(Json(json!({ "cidr": q.cidr, "addresses": hits })))
    })
    .await
}

/// The participants (#159). A partner sees the ids that appear in the
/// sighting files and each one's status; core also sees who they are.
async fn participants(
    State(app): State<Shared>,
    headers: HeaderMap,
) -> Result<Json<Value>, ApiError> {
    let caller = require(&app, &headers, Tier::Partner)?;
    blocking(move || {
        let orgs =
            crate::store::participants::organisations(app.participants.path()).map_err(internal)?;
        let list: Vec<Value> = orgs
            .into_iter()
            .map(|o| {
                if caller.tier >= Tier::Core {
                    json!(o)
                } else {
                    json!({ "id": o.id, "status": o.status })
                }
            })
            .collect();
        Ok(Json(json!({ "participants": list })))
    })
    .await
}

async fn files(State(app): State<Shared>, headers: HeaderMap) -> Result<Json<Value>, ApiError> {
    require(&app, &headers, Tier::Partner)?;
    blocking(move || {
        let files = app.sightings.files().map_err(internal)?;
        let mut files: Vec<Value> = files
            .into_iter()
            .map(|(path, rows, bytes)| json!({ "path": path, "rows": rows, "bytes": bytes }))
            .collect();
        let open = app.sightings.open_rows().map_err(internal)?;
        if open > 0 {
            files.push(json!({ "path": OPEN_FILE, "rows": open, "bytes": null, "open": true }));
        }
        Ok(Json(
            json!({ "table": crate::store::sightings::NAME, "files": files }),
        ))
    })
    .await
}

/// One Parquet file the table lists. Only listed paths are served, so
/// the WAL, the manifest and anything outside the table stay private.
async fn file(
    State(app): State<Shared>,
    headers: HeaderMap,
    axum::extract::Path(path): axum::extract::Path<String>,
) -> Result<Response, ApiError> {
    require(&app, &headers, Tier::Partner)?;
    let safe = Path::new(&path)
        .components()
        .all(|c| matches!(c, Component::Normal(_)));
    if !safe {
        return Err(ApiError(StatusCode::NOT_FOUND, "no such file".into()));
    }
    blocking(move || {
        if path == OPEN_FILE {
            let bytes = app.sightings.open_rows_parquet().map_err(internal)?;
            return Ok((
                [
                    (header::CONTENT_TYPE, "application/vnd.apache.parquet"),
                    (header::CACHE_CONTROL, "no-store"),
                ],
                bytes,
            )
                .into_response());
        }
        let listed = app
            .sightings
            .files()
            .map_err(internal)?
            .iter()
            .any(|(p, _, _)| *p == path);
        if !listed {
            return Err(ApiError(StatusCode::NOT_FOUND, "no such file".into()));
        }
        let bytes = std::fs::read(app.sightings.dir().join(&path)).map_err(internal)?;
        Ok((
            [
                (header::CONTENT_TYPE, "application/vnd.apache.parquet"),
                (header::CACHE_CONTROL, "private, max-age=3600, immutable"),
            ],
            bytes,
        )
            .into_response())
    })
    .await
}

/// Per-day counts, for the rebuild: (day, ioc) totals over all sightings.
pub fn rebuild_iocs(sightings: &Sightings, iocs: &Iocs) -> Result<usize, String> {
    let r = sightings.query(
        "SELECT ts, ioc_type, ioc_value, observations, tlp FROM sightings WHERE ioc_type IS NOT NULL",
    )?;
    let mut rows = Vec::with_capacity(r.rows.len());
    let mut types: BTreeMap<String, IocType> = BTreeMap::new();
    for row in &r.rows {
        let (Cell::Int(ts), Cell::Text(t), Cell::Text(v), Cell::Int(n), Cell::Text(tlp)) =
            (&row[0], &row[1], &row[2], &row[3], &row[4])
        else {
            continue;
        };
        let Ok(tlp) = Tlp::parse(tlp) else {
            continue;
        };
        let Some(t) = types.get(t).copied().or_else(|| IocType::parse(t)) else {
            continue;
        };
        types.insert(t.as_str().to_string(), t);
        rows.push(frank_core::SightingRow {
            ts_ns: *ts,
            sighting_id: String::new(),
            rule_id: None,
            technique: None,
            campaign: None,
            ioc_type: Some(t),
            ioc_value: Some(v.clone()),
            reporter_sector: None,
            target_sector: None,
            target_size: None,
            severity: None,
            confidence: 0,
            observations: u32::try_from(*n).unwrap_or(1),
            tlp,
            reporter: String::new(),
            digest: String::new(),
            received_ns: 0,
            seq: 0,
            detail: None,
        });
    }
    iocs.clear()?;
    iocs.record(&rows)?;
    Ok(rows.len())
}

#[cfg(test)]
mod tests {
    use super::*;
    use frank_core::observable::ip_hex;

    #[test]
    fn cidr_bounds_cover_the_block() {
        let (lo, hi) = cidr_bounds("185.220.0.0/16").unwrap();
        let h = |s: &str| ip_hex(s.parse().unwrap());
        assert!(lo <= h("185.220.0.0") && h("185.220.255.255") <= hi);
        assert!(h("185.221.0.0") > hi);
        assert!(cidr_bounds("10.0.0.0/33").is_none());
        assert!(cidr_bounds("::/0").is_some());
    }
}
