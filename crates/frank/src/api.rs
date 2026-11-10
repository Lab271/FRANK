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
//! | `GET  /v1/live`           | contributor |
//! | `GET  /v1/files`, `/v1/files/{*path}` | partner |
//! | `GET  /v1/participants`   | partner (ids and status), core (all details) |
//! | `/v1/admin/…`             | a user with a role ([`crate::admin`]) |

use std::collections::{BTreeMap, HashMap};
use std::net::IpAddr;
use std::path::{Component, Path};
use std::sync::Arc;

use axum::extract::{DefaultBodyLimit, Query, State};
use axum::http::{header, HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use db_core::engine::Cell;
use frank_core::{
    sql_blob, sql_quote, Digest, Format, Ioc, IocType, Sighting, SightingId, Tier, Tlp, MIN_CELL,
};
use serde::Deserialize;
use serde_json::{json, Value};

use crate::audit::Audit;
use crate::auth::Caller;
use crate::explore::{self as ex, Dimension, BY_TECHNIQUE, FIRST_ROW, TECH, TECH_SET};
use crate::live::{self, Window};
use crate::records;
use crate::store::registry::{self, Receipt};
use crate::store::sightings::{scalar, NAME as SIGHTINGS};
use crate::store::{Iocs, Participants, Registry, Sightings};

const DAY_NS: i64 = 86_400 * 1_000_000_000;
/// Most submissions in one POST.
const MAX_BATCH: usize = 100;
/// Most sighting ids in one query's `IN` list (#201): db-core parsed a
/// long literal list recursively and overflowed the stack (db-core#901).
const IDS_PER_QUERY: usize = 100;
const MAX_BODY: usize = 2 * 1024 * 1024;
/// The rows not yet in a file, served as one Parquet file written on request.
pub const OPEN_FILE: &str = "open/current.parquet";
/// The `ip_geo` table (#191), served as one Parquet file written on request.
pub const GEO_FILE: &str = "geo/ip_geo.parquet";
/// Days in a detail pane's trend.
const TREND_DAYS: i64 = 30;

pub struct App {
    /// The data directory, for the admin file listing (#222).
    pub data: std::path::PathBuf,
    pub sightings: Sightings,
    pub iocs: Iocs,
    /// Country and ASN of IP addresses (#191).
    pub geo: crate::geo::Geo,
    /// Warning and reference IoC lists (#192, #193).
    pub lists: crate::lists::Lists,
    pub participants: Participants,
    pub registry: Registry,
    pub audit: Audit,
    /// Sign in with OpenID Connect (#241); `None` when not configured.
    pub sso: Option<crate::sso::Config>,
    /// Makes "is it registered, store it, register it" one step.
    pub submit_lock: std::sync::Mutex<()>,
    /// Wall clock in ns; tests set their own.
    pub now: fn() -> i64,
}

pub type Shared = Arc<App>;

#[derive(Debug)]
pub struct ApiError(pub(crate) StatusCode, pub(crate) String);

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (self.0, Json(json!({ "error": self.1 }))).into_response()
    }
}

pub(crate) fn internal(e: impl std::fmt::Display) -> ApiError {
    tracing::error!("{e}");
    ApiError(StatusCode::INTERNAL_SERVER_ERROR, "internal error".into())
}

pub(crate) fn unprocessable(e: impl std::fmt::Display) -> ApiError {
    ApiError(StatusCode::UNPROCESSABLE_ENTITY, e.to_string())
}

/// The caller the request's bearer token names, at least `tier`.
pub(crate) fn require(app: &App, headers: &HeaderMap, tier: Tier) -> Result<Caller, ApiError> {
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
pub(crate) async fn blocking<T: Send + 'static>(
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
        .route("/v1/sightings", get(list).post(submit))
        .route("/v1/sightings/{id}", get(sighting))
        .route("/v1/summary", get(summary))
        .route("/v1/openapi.json", get(openapi))
        .route("/v1/iocs", get(ioc_lookup))
        .route("/v1/iocs/range", get(ioc_range))
        .route("/v1/explore", get(explore))
        .route("/v1/live", get(live_view))
        .route("/v1/rules/{id}", get(rule_detail))
        .route("/v1/participants", get(participants))
        .route("/v1/files", get(files))
        .route("/v1/files/{*path}", get(file))
        .merge(crate::admin::routes())
        .layer(DefaultBodyLimit::max(MAX_BODY))
        .with_state(app)
}

/// Up and its version. The geo databases' state is information only: FRANK is
/// healthy without it (#191).
async fn health(State(app): State<Shared>) -> Json<Value> {
    Json(json!({
        "status": "ok",
        "version": env!("CARGO_PKG_VERSION"),
        "geoip": app.geo.status(),
        "lists": app.lists.status(),
    }))
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
        "role": c.role,
        "participant": { "id": c.participant, "name": c.organisation, "status": c.tier },
    })))
}

/// The sightings of a request body (#160): one, a list or a STIX bundle,
/// in the format its `Content-Type` names; JSON when it names none.
fn submissions(headers: &HeaderMap, body: &str, now: i64) -> Result<Vec<Sighting>, ApiError> {
    let format = match headers.get(header::CONTENT_TYPE) {
        None => Format::Json,
        Some(ct) => ct
            .to_str()
            .ok()
            .and_then(Format::from_content_type)
            .ok_or_else(|| {
                ApiError(
                    StatusCode::UNSUPPORTED_MEDIA_TYPE,
                    "send application/json, application/yaml or application/stix+json".into(),
                )
            })?,
    };
    let subs = frank_core::formats::parse(body, format, now).map_err(unprocessable)?;
    if subs.len() > MAX_BATCH {
        return Err(unprocessable(format!("more than {MAX_BATCH} submissions")));
    }
    Ok(subs)
}

/// The rows a submission would add, without storing anything: what leaves
/// the contributor, shown before it leaves.
async fn preview(
    State(app): State<Shared>,
    headers: HeaderMap,
    body: String,
) -> Result<Json<Value>, ApiError> {
    require(&app, &headers, Tier::Public)?;
    let subs = submissions(&headers, &body, (app.now)())?;
    let rows: Vec<_> = subs
        .iter()
        .flat_map(|s| s.rows(s.sighting_id.unwrap_or_default()))
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
    body: String,
) -> Result<Response, ApiError> {
    let caller = require(&app, &headers, Tier::Contributor)?;
    let subs = submissions(&headers, &body, (app.now)())?;
    let mut items: Vec<(SightingId, Digest, Sighting)> = Vec::with_capacity(subs.len());
    for (i, s) in subs.into_iter().enumerate() {
        let id = s.sighting_id.ok_or_else(|| {
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
        let ids = items.iter().map(|(id, _, _)| *id).collect();
        let known = app.registry.find(&caller2.participant, ids).map_err(internal)?;
        let conflicts: Vec<String> = items
            .iter()
            .filter(|(id, d, _)| known.get(id).is_some_and(|(k, _)| k != d))
            .map(|(id, _, _)| id.to_string())
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
            rows.extend(s.rows(id).into_iter().map(|mut r| {
                r.reporter.clone_from(&caller2.participant);
                r.digest = (r.seq == 0).then_some(digest);
                r.received_ns = now;
                r
            }));
            fresh.push((caller2.participant.clone(), id, digest, now));
            receipts.push(Receipt { sighting_id: id, digest, received: now, status: "created" });
        }
        if !fresh.is_empty() {
            // Rows first: they hold the registration. Both indexes can be
            // rebuilt from them (`frank rebuild`).
            app.sightings.append(&rows).map_err(internal)?;
            app.iocs.record(&rows).map_err(internal)?;
            app.registry.register(fresh).map_err(internal)?;
            app.geo.fill(&rows, now);
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
/// all rows for the IoC type, techniques unnested (#180). Unless
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
    let (column, from, rows) = match column {
        "technique" => (
            TECH,
            BY_TECHNIQUE,
            format!(" AND {FIRST_ROW} AND {TECH_SET}"),
        ),
        "ioc_type" => (column, SIGHTINGS, String::new()),
        _ => (column, SIGHTINGS, format!(" AND {FIRST_ROW}")),
    };
    let sql = format!(
        "SELECT {column}, count(*) AS n, count(DISTINCT reporter) AS r FROM {from} WHERE ts >= {since} AND {visible}{rows} GROUP BY {column} ORDER BY n DESC"
    );
    let r = s.query(&sql).map_err(internal)?;
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
struct LiveQuery {
    window: Option<String>,
    common: Option<String>,
}

/// `common=include|exclude` (#192): whether IoCs a warning list marks as
/// common infrastructure stay in the converging list and Explore's IoC
/// ranking. Excluded by default; they are marked, never dropped, elsewhere.
fn include_common(v: Option<&str>) -> Result<bool, ApiError> {
    match v {
        None | Some("exclude") => Ok(false),
        Some("include") => Ok(true),
        Some(_) => Err(unprocessable("common: expected include or exclude")),
    }
}

/// IoCs per list in the live view.
const LIVE_LIMIT: usize = 50;
/// Countries and networks in the live view's top lists (#195).
const PLACES_LIMIT: usize = 10;

/// What arrived in the window (#186): counters, arrivals per bar, and the
/// window's IoCs as a feed (newest first) and as the converging list (two
/// or more reporters). Below partner an IoC with fewer than [`MIN_CELL`]
/// reporters is left out of both lists, as Explore leaves out small cells.
/// `places` ranks the countries and networks of the window's IP addresses
/// (#195) under the same threshold; warning-listed addresses (public DNS,
/// reserved ranges) are left out of it unless `common=include`.
async fn live_view(
    State(app): State<Shared>,
    headers: HeaderMap,
    Query(q): Query<LiveQuery>,
) -> Result<Json<Value>, ApiError> {
    let caller = require(&app, &headers, Tier::Contributor)?;
    let window = Window::parse(q.window.as_deref().unwrap_or("1h"))
        .ok_or_else(|| unprocessable("window: expected 1h, 6h or 24h"))?;
    let common = include_common(q.common.as_deref())?;
    let now = (app.now)();
    let since = now - window.ns();
    let visible = tlp_visible(caller.tier);
    let exact = caller.tier >= Tier::Partner;
    blocking(move || {
        let s = &app.sightings;
        let v = visible.as_str();
        let rows = |sql: &str| s.query(sql).map(|r| r.rows).map_err(internal);
        let mut iocs = live::iocs(&rows(&live::window_sql(since, v))?);
        let mut before = Vec::new();
        for values in live::chunks(&iocs) {
            before.extend(rows(&live::before_sql(since, v, &values))?);
        }
        live::mark_seen(&mut iocs, &before);
        let arrivals: Vec<i64> = rows(&live::arrivals_sql(since, v))?
            .iter()
            .filter_map(|r| match r.first() {
                Some(Cell::Int(t)) => Some(*t),
                _ => None,
            })
            .collect();
        let participants = s
            .query(&live::reporters_sql(since, v))
            .map(|r| scalar(&r))
            .map_err(internal)?;
        let new = iocs.iter().filter(|i| i.seen_since.is_none()).count();
        let total = iocs.len();
        if !exact {
            iocs.retain(|i| i.reporters >= MIN_CELL);
        }
        if !common {
            // Converging candidates marked as common infrastructure stay in
            // the feed, marked, but do not converge.
            let candidates: Vec<(String, String)> = iocs
                .iter()
                .filter(|i| i.reporters >= 2)
                .map(|i| (i.ioc_type.clone(), i.value.clone()))
                .collect();
            let warned: std::collections::BTreeSet<(String, String)> = candidates
                .iter()
                .zip(app.lists.annotate(&candidates))
                .filter(|(_, l)| crate::lists::warned(l))
                .map(|(k, _)| k.clone())
                .collect();
            for i in &mut iocs {
                if warned.contains(&(i.ioc_type.clone(), i.value.clone())) {
                    i.common = true;
                }
            }
        }
        let places = live_places(&app, &rows(&live::addresses_sql(since, v))?, common, exact);
        let (mut feed, mut converging) = live::lists(&iocs, LIVE_LIMIT);
        let shown: Vec<(String, String)> = feed
            .iter()
            .chain(&converging)
            .map(|i| (i.ioc_type.clone(), i.value.clone()))
            .collect();
        for (i, l) in feed
            .iter_mut()
            .chain(converging.iter_mut())
            .zip(app.lists.annotate(&shown))
        {
            i.listed = l;
        }
        let ips: Vec<String> = feed
            .iter()
            .chain(&converging)
            .filter(|i| matches!(i.ioc_type.as_str(), "ipv4" | "ipv6"))
            .map(|i| i.value.clone())
            .collect();
        let geo = app.geo.answers(ips);
        for i in feed.iter_mut().chain(converging.iter_mut()) {
            i.geo = geo.get(&i.value).cloned();
        }
        Ok(Json(json!({
            "window": window.label(),
            "since": since,
            "now": now,
            "min_cell": if exact { 1 } else { MIN_CELL },
            "sightings": arrivals.len(),
            "participants": participants,
            "iocs": total,
            "new_iocs": new,
            "bucket_ns": window.bucket_ns(),
            "buckets": live::buckets(&arrivals, window, now)
                .into_iter()
                .map(|(t, n)| json!({ "t": t, "sightings": n }))
                .collect::<Vec<_>>(),
            "feed": feed,
            "converging": converging,
            "geoip": app.geo.status()["status"],
            "places": places,
        })))
    })
    .await
}

/// The countries and networks of the window's addresses (#195), from the
/// rows of [`live::addresses_sql`].
fn live_places(app: &App, rows: &[Vec<Cell>], common: bool, exact: bool) -> live::Places {
    let mut pairs = live::addresses(rows);
    let mut ips: Vec<String> = pairs.iter().map(|(ip, _)| ip.clone()).collect();
    ips.sort_unstable();
    ips.dedup();
    if !common {
        let keys: Vec<(String, String)> = ips
            .iter()
            .map(|ip| {
                let t = if ip.contains(':') { "ipv6" } else { "ipv4" };
                (t.to_string(), ip.clone())
            })
            .collect();
        let warned: std::collections::BTreeSet<&str> = ips
            .iter()
            .zip(app.lists.annotate(&keys))
            .filter(|(_, l)| crate::lists::warned(l))
            .map(|(ip, _)| ip.as_str())
            .collect();
        pairs.retain(|(ip, _)| !warned.contains(ip.as_str()));
    }
    let min = if exact { 1 } else { MIN_CELL };
    live::places(&pairs, &app.geo.answers(ips), min, PLACES_LIMIT)
}

#[derive(Deserialize)]
struct IocQuery {
    #[serde(rename = "type")]
    ioc_type: String,
    value: String,
    /// Limit the panels to one day, `YYYY-MM-DD` (#182).
    day: Option<String>,
}

/// `YYYY-MM-DD` as `[start, end)` in nanoseconds.
fn day_bounds(day: &str) -> Option<(i64, i64)> {
    let d = time::Date::parse(
        day,
        time::macros::format_description!("[year]-[month]-[day]"),
    )
    .ok()?;
    let start = d.midnight().assume_utc().unix_timestamp() * 1_000_000_000;
    Some((start, start + DAY_NS))
}

/// The lookup's panels (#182): the IoC's sightings since `since` (and before
/// `until`), grouped the way the rule page groups them, under the same
/// reporter threshold and TLP rules as Explore.
fn ioc_panels(
    s: &Sightings,
    ioc: &Ioc,
    since: i64,
    until: Option<i64>,
    tier: Tier,
) -> Result<Value, ApiError> {
    let visible = match until {
        Some(u) => format!("{} AND ts < {u}", tlp_visible(tier)),
        None => tlp_visible(tier),
    };
    let exact = tier >= Tier::Partner;
    let list = |group, n| {
        let q = ex::Query {
            group,
            days: 0,
            filters: vec![(Dimension::Ioc, ioc.key())],
        };
        grouped(s, &q, since, &visible, exact, n)
    };
    Ok(json!({
        "since": since,
        "until": until,
        "rules": list(Dimension::Rule, 15)?,
        "sectors": list(Dimension::Sector, 20)?,
        "severities": list(Dimension::Severity, 10)?,
        "techniques": list(Dimension::Technique, 15)?,
        "campaigns": list(Dimension::Campaign, 10)?,
    }))
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
    let window = match q.day.as_deref() {
        Some(d) => Some(
            day_bounds(d)
                .ok_or_else(|| unprocessable(format!("day: expected YYYY-MM-DD, got {d:?}")))?,
        ),
        None => None,
    };
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
        let panels = match (window, days.first()) {
            (Some((from, to)), _) => ioc_panels(&app.sightings, &ioc, from, Some(to), caller.tier)?,
            (None, Some(d)) => ioc_panels(&app.sightings, &ioc, d.first_ts, None, caller.tier)?,
            (None, None) => Value::Null,
        };
        let geo = ioc
            .ip_hex()
            .and_then(|_| app.geo.answers(vec![ioc.value.clone()]).remove(&ioc.value));
        let listed = app
            .lists
            .annotate(&[(ioc.ioc_type.as_str().to_string(), ioc.value.clone())])
            .pop()
            .unwrap_or_default();
        Ok(Json(json!({
            "ioc": ioc,
            "geo": geo,
            "listed": listed,
            "known": !days.is_empty(),
            "count": days.iter().map(|d| d.count).sum::<i64>(),
            "reporters": reporters,
            "first_seen": days.first().map(|d| d.first_ts),
            "last_seen": days.iter().map(|d| d.last_ts).max(),
            "days": days,
            "rules": rules,
            "trend": trend,
            "panels": panels,
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
    let r = s.query(&sql).map_err(internal)?;
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
    Query(mut params): Query<BTreeMap<String, String>>,
) -> Result<Json<Value>, ApiError> {
    let common = include_common(params.remove("common").as_deref())?;
    // `listed=any|none|<list>` (#193): IoCs a reference list has, has not,
    // or a given one has; with group=ioc.
    let listed_by = params.remove("listed");
    let q = ex::Query::parse(&params).map_err(unprocessable)?;
    if listed_by.is_some() && q.group != Dimension::Ioc {
        return Err(unprocessable("listed: only with group=ioc"));
    }
    if listed_by
        .as_deref()
        .is_some_and(|l| l.is_empty() || l.len() > 200)
    {
        return Err(unprocessable("listed: any, none or a list name"));
    }
    let caller = require(&app, &headers, q.min_tier())?;
    let since = (app.now)() - q.days * DAY_NS;
    let visible = tlp_visible(caller.tier);
    let exact = caller.tier >= Tier::Partner;
    blocking(move || {
        let by_ioc = q.group == Dimension::Ioc;
        let mut rows = grouped(
            &app.sightings,
            &q,
            since,
            &visible,
            exact,
            if by_ioc { 200 } else { 100 },
        )?;
        if by_ioc {
            // What the lists say about each IoC (#192, #193); common
            // infrastructure is left out unless asked for.
            let keys: Vec<(String, String)> = rows
                .iter()
                .filter_map(|r| r["key"].as_str()?.split_once(':'))
                .map(|(t, v)| (t.to_string(), v.to_string()))
                .collect();
            let listed = app.lists.annotate(&keys);
            let mut keep = Vec::with_capacity(rows.len());
            for (r, l) in rows.iter_mut().zip(listed) {
                let refs: Vec<&str> = l
                    .iter()
                    .filter(|x| x.kind == "reference")
                    .map(|x| x.list.as_str())
                    .collect();
                keep.push(match listed_by.as_deref() {
                    None => true,
                    Some("any") => !refs.is_empty(),
                    Some("none") => refs.is_empty(),
                    Some(name) => refs.contains(&name),
                });
                r["common"] = json!(crate::lists::warned(&l));
                r["listed"] = json!(l);
            }
            let mut keep = keep.into_iter();
            rows.retain(|_| keep.next().unwrap_or(false));
            rows.retain(|r| common || r["common"] != true);
            rows.truncate(100);
        }
        Ok(Json(json!({
            "group": q.group.name(),
            "days": q.days,
            "filters": q.filters.iter().map(|(d, v)| (d.name(), v)).collect::<BTreeMap<_, _>>(),
            "min_cell": if exact { 1 } else { MIN_CELL },
            "listed": listed_by,
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
pub(crate) fn cidr_bounds(cidr: &str) -> Option<(String, String)> {
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
        let geo = app.geo.db().all().map_err(internal)?.len();
        let ip_geo = (geo > 0).then(|| {
            json!({ "table": "ip_geo", "path": GEO_FILE, "rows": geo, "attribution": crate::geo::ATTRIBUTION })
        });
        Ok(Json(
            json!({ "table": crate::store::sightings::NAME, "files": files, "ip_geo": ip_geo }),
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
        if path == GEO_FILE {
            // Served when listed: when `ip_geo` has rows.
            let rows = app.geo.db().all().map_err(internal)?;
            if rows.is_empty() {
                return Err(ApiError(StatusCode::NOT_FOUND, "no such file".into()));
            }
            let bytes = geo_parquet(&rows).map_err(internal)?;
            return Ok((
                [
                    (header::CONTENT_TYPE, "application/vnd.apache.parquet"),
                    (header::CACHE_CONTROL, "no-store"),
                ],
                bytes,
            )
                .into_response());
        }
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
        let bytes = app.sightings.read_file(&path).map_err(internal)?;
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

/// `ip_geo` as one Parquet file, DB-IP's attribution in its metadata.
fn geo_parquet(rows: &[crate::store::geo::IpGeo]) -> Result<Vec<u8>, String> {
    use db_core::storage::parquet::schema::ColumnValues as V;
    use db_core::storage::parquet::writer::{
        ColumnSpec, ColumnType, Compression, ParquetWriter, WriterOptions,
    };
    let text = |name| ColumnSpec::new(name, ColumnType::Utf8, false);
    let schema = vec![
        text("ip"),
        text("country"),
        ColumnSpec::new("asn", ColumnType::Int64, false),
        ColumnSpec::new("as_org", ColumnType::Utf8, true),
        ColumnSpec::new("looked_up", ColumnType::TimestampNanos, false),
    ];
    let mut w = ParquetWriter::new(
        Vec::new(),
        schema,
        WriterOptions {
            compression: Compression::Zstd,
            key_value_metadata: vec![("attribution".into(), crate::geo::ATTRIBUTION.into())],
            ..WriterOptions::default()
        },
    )
    .map_err(|e| e.to_string())?;
    if !rows.is_empty() {
        w.write_columns(vec![
            V::Utf8(rows.iter().map(|g| Some(g.ip.clone())).collect()),
            V::Utf8(rows.iter().map(|g| Some(g.country.clone())).collect()),
            V::Int64(rows.iter().map(|g| Some(g.asn)).collect()),
            V::Utf8(rows.iter().map(|g| g.as_org.clone()).collect()),
            V::TimestampNanos(rows.iter().map(|g| Some(g.looked_up)).collect()),
        ])
        .map_err(|e| e.to_string())?;
    }
    w.finish()
        .map(|(bytes, _)| bytes)
        .map_err(|e| e.to_string())
}

/// The API description (`docs/openapi.yaml`), as JSON.
async fn openapi() -> Result<Json<Value>, ApiError> {
    frank_core::yaml::to_json(include_str!("../../../docs/openapi.yaml"))
        .map(Json)
        .map_err(internal)
}

/// `GET /v1/sightings` (#160): the records of the visible sightings, in
/// time order, a page at a time. Partners and core list all; a
/// contributor lists its own (`mine=true`).
async fn list(
    State(app): State<Shared>,
    headers: HeaderMap,
    Query(params): Query<BTreeMap<String, String>>,
) -> Result<Json<Value>, ApiError> {
    let caller = require(&app, &headers, Tier::Contributor)?;
    let q = records::List::parse(&params, (app.now)()).map_err(unprocessable)?;
    if caller.tier < Tier::Partner && !q.mine {
        return Err(ApiError(
            StatusCode::FORBIDDEN,
            "below partner, a participant lists its own sightings: mine=true".into(),
        ));
    }
    let reporter = q.mine.then(|| caller.participant.clone());
    let visible = tlp_visible(caller.tier);
    blocking(move || {
        let s = &app.sightings;
        let r = reporter.as_deref();
        let Some(ids_sql) = q.ioc_sql(&visible, r) else {
            let rows = s.query(&q.sql(&visible, r, None)).map_err(internal)?.rows;
            let more = rows.len() > q.limit;
            let mut items: Vec<(String, Value)> = rows
                .iter()
                .take(q.limit)
                .filter_map(|row| records::item(row))
                .collect();
            let next = if more {
                items.last().map(|(c, _)| c.clone())
            } else {
                None
            };
            let items: Vec<Value> = items.drain(..).map(|(_, v)| v).collect();
            return Ok(Json(json!({ "sightings": items, "next_cursor": next })));
        };
        // An IoC filter (#201): one page of ids, then their records in
        // chunks, so no query holds more than `IDS_PER_QUERY` literals.
        let mut page: Vec<(i64, SightingId)> = s
            .query(&ids_sql)
            .map_err(internal)?
            .rows
            .into_iter()
            .filter_map(|row| match (row.first(), row.get(1)) {
                (Some(Cell::Int(ts)), Some(Cell::Blob(id))) => {
                    Some((*ts, SightingId(id.as_slice().try_into().ok()?)))
                }
                _ => None,
            })
            .collect();
        let more = page.len() > q.limit;
        page.truncate(q.limit);
        let mut found: HashMap<String, Vec<Value>> = HashMap::new();
        let ids: Vec<SightingId> = page.iter().map(|(_, id)| *id).collect();
        for chunk in ids.chunks(IDS_PER_QUERY) {
            for row in s
                .query(&q.sql(&visible, r, Some(chunk)))
                .map_err(internal)?
                .rows
            {
                if let Some((cursor, v)) = records::item(&row) {
                    found.entry(cursor).or_default().push(v);
                }
            }
        }
        let cursors: Vec<String> = page.iter().map(|(ts, id)| format!("{ts}.{id}")).collect();
        let items: Vec<Value> = cursors
            .iter()
            .flat_map(|c| found.remove(c).unwrap_or_default())
            .collect();
        let next = if more { cursors.last().cloned() } else { None };
        Ok(Json(json!({ "sightings": items, "next_cursor": next })))
    })
    .await
}

/// `GET /v1/sightings/{id}` (#160): one record. Below partner only the
/// caller's own; anything else is not found.
async fn sighting(
    State(app): State<Shared>,
    headers: HeaderMap,
    axum::extract::Path(id): axum::extract::Path<String>,
) -> Result<Json<Value>, ApiError> {
    let caller = require(&app, &headers, Tier::Contributor)?;
    let id = SightingId::parse(&id).map_err(unprocessable)?;
    let mut filter = format!(
        "sighting_id = {} AND seq = 0 AND {}",
        sql_blob(&id.0),
        tlp_visible(caller.tier)
    );
    if caller.tier < Tier::Partner {
        filter.push_str(&format!(
            " AND reporter = {}",
            sql_quote(&caller.participant)
        ));
    }
    blocking(move || {
        let r = app
            .sightings
            .query(&format!(
                "SELECT {} FROM sightings WHERE {filter}",
                records::COLUMNS
            ))
            .map_err(internal)?;
        let items: Vec<Value> = r
            .rows
            .iter()
            .filter_map(|row| records::item(row).map(|(_, v)| v))
            .collect();
        // Two participants may have chosen the same id: the caller's own first.
        items
            .iter()
            .find(|v| v["reporter"] == caller.participant.as_str())
            .or(items.first())
            .cloned()
            .map(Json)
            .ok_or_else(|| ApiError(StatusCode::NOT_FOUND, format!("no sighting {id}")))
    })
    .await
}

/// `GET /v1/summary?days=30` (#160): what the caller's participant sent in
/// the window, and the sightings it can see from everyone.
async fn summary(
    State(app): State<Shared>,
    headers: HeaderMap,
    Query(q): Query<StatsQuery>,
) -> Result<Json<Value>, ApiError> {
    let caller = require(&app, &headers, Tier::Contributor)?;
    let days = q.days.unwrap_or(30);
    if !(1..=3650).contains(&days) {
        return Err(unprocessable("days must be 1-3650"));
    }
    let since = (app.now)() - days * DAY_NS;
    let visible = tlp_visible(caller.tier);
    blocking(move || {
        let s = &app.sightings;
        let own = format!(
            "reporter = {} AND ts >= {since}",
            sql_quote(&caller.participant)
        );
        let r = s
            .query(&format!(
                "SELECT count(*), sum(observations), max(received) FROM sightings WHERE {own} AND {FIRST_ROW}"
            ))
            .map_err(internal)?;
        let row = r.rows.first();
        let int = |i: usize| match row.map(|r| &r[i]) {
            Some(Cell::Int(n)) => Some(*n),
            _ => None,
        };
        let iocs = s
            .query(&format!(
                "SELECT count(*) FROM sightings WHERE {own} AND ioc_type IS NOT NULL"
            ))
            .map(|r| scalar(&r))
            .map_err(internal)?;
        let network = s
            .query(&format!(
                "SELECT count(*) FROM sightings WHERE ts >= {since} AND {visible} AND {FIRST_ROW}"
            ))
            .map(|r| scalar(&r))
            .map_err(internal)?;
        Ok(Json(json!({
            "participant": caller.participant,
            "days": days,
            "sightings": int(0).unwrap_or(0),
            "observations": int(1).unwrap_or(0),
            "iocs": iocs,
            "last_received": int(2).map_or(Value::Null, records::rfc3339),
            "network": { "sightings": network },
        })))
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
            sighting_id: SightingId::default(),
            rule_id: None,
            techniques: Vec::new(),
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
            digest: None,
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
