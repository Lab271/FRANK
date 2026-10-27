//! Identity administration (#175, ADR-017). A user's role decides what it
//! may manage; its organisation's status still decides what it may see.
//! An admin manages the users and tokens of its own organisation, a
//! superadmin every organisation. To an admin, another organisation's
//! objects answer 404, as if they did not exist.
//!
//! | Route                                 | Role       |
//! |---------------------------------------|------------|
//! | `GET    /v1/admin/organisations`      | admin (its own), superadmin (all) |
//! | `POST   /v1/admin/organisations`      | superadmin |
//! | `PATCH  /v1/admin/organisations/{id}` | superadmin |
//! | `GET    /v1/admin/users`              | admin      |
//! | `POST   /v1/admin/users`              | admin      |
//! | `PATCH  /v1/admin/users/{name}`       | admin (superadmin to grant or take superadmin) |
//! | `GET    /v1/admin/tokens`             | admin      |
//! | `POST   /v1/admin/tokens`             | admin      |
//! | `DELETE /v1/admin/tokens/{prefix}`    | admin      |
//! | `GET    /v1/admin/audit`              | admin      |
//!
//! Every change writes an audit line naming `user@organisation`; a token
//! appears there only as its hash prefix. Three changes are refused:
//! taking the role of an organisation's last admin, demoting the last
//! superadmin, and revoking the caller's own last token.

use std::sync::Mutex;

use axum::extract::{Path as UrlPath, Query, State};
use axum::http::{header, HeaderMap, HeaderValue, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{delete, get, patch};
use axum::{Json, Router};
use frank_core::Tier;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::api::{blocking, internal, require, unprocessable, ApiError, App, Shared};
use crate::auth::{hash, Caller, Role};
use crate::store::participants::{self as parts, UserInfo};

const DAY_NS: i64 = 86_400 * 1_000_000_000;
/// Most audit days in one request, and most lines returned.
const MAX_AUDIT_DAYS: i64 = 31;
const MAX_AUDIT_LINES: usize = 1000;

/// Makes "check the guards, then write" one step for the server's own
/// writes. The CLI writes past it; it is the operator's tool.
static WRITE: Mutex<()> = Mutex::new(());

pub fn routes() -> Router<Shared> {
    Router::new()
        .route(
            "/v1/admin/organisations",
            get(organisations).post(add_organisation),
        )
        .route("/v1/admin/organisations/{id}", patch(set_status))
        .route("/v1/admin/users", get(users).post(add_user))
        .route("/v1/admin/users/{name}", patch(set_role))
        .route("/v1/admin/tokens", get(tokens).post(add_token))
        .route("/v1/admin/tokens/{prefix}", delete(revoke))
        .route("/v1/admin/audit", get(audit))
}

fn forbidden(msg: &str) -> ApiError {
    ApiError(StatusCode::FORBIDDEN, msg.into())
}

fn not_found(what: &str) -> ApiError {
    ApiError(StatusCode::NOT_FOUND, format!("no {what}"))
}

fn conflict(msg: String) -> ApiError {
    ApiError(StatusCode::CONFLICT, msg)
}

/// The caller, if it holds a role.
fn admin(app: &App, headers: &HeaderMap) -> Result<Caller, ApiError> {
    let c = require(app, headers, Tier::Public)?;
    if c.role.is_none() {
        return Err(forbidden("needs the admin role"));
    }
    Ok(c)
}

fn superadmin(app: &App, headers: &HeaderMap) -> Result<Caller, ApiError> {
    let c = admin(app, headers)?;
    if c.role != Some(Role::Superadmin) {
        return Err(forbidden("needs the superadmin role"));
    }
    Ok(c)
}

/// Whether `c` may manage organisation `participant`.
fn manages(c: &Caller, participant: &str) -> bool {
    c.role == Some(Role::Superadmin) || c.participant == participant
}

fn record(app: &App, c: &Caller, action: &str, fields: Value) -> Result<(), ApiError> {
    app.audit
        .record((app.now)(), &c.label(), action, fields)
        .map_err(internal)
}

fn created(body: Value) -> Response {
    (StatusCode::CREATED, Json(body)).into_response()
}

/// The users `c` manages, all of them for a superadmin.
fn managed_users(app: &App, c: &Caller) -> Result<Vec<UserInfo>, ApiError> {
    Ok(parts::users(app.participants.path())
        .map_err(internal)?
        .into_iter()
        .filter(|u| manages(c, &u.participant))
        .collect())
}

/// The user called `name`, if `c` manages it.
fn managed_user(app: &App, c: &Caller, name: &str) -> Result<UserInfo, ApiError> {
    managed_users(app, c)?
        .into_iter()
        .find(|u| u.name == name)
        .ok_or_else(|| not_found(&format!("user {name:?}")))
}

#[derive(Deserialize)]
struct Scope {
    /// An organisation's id; without it, all the caller manages.
    participant: Option<String>,
}

impl Scope {
    fn admits(&self, participant: &str) -> bool {
        self.participant.as_deref().is_none_or(|p| p == participant)
    }
}

// --- organisations ------------------------------------------------------

async fn organisations(
    State(app): State<Shared>,
    headers: HeaderMap,
) -> Result<Json<Value>, ApiError> {
    let c = admin(&app, &headers)?;
    blocking(move || {
        let list: Vec<_> = parts::organisations(app.participants.path())
            .map_err(internal)?
            .into_iter()
            .filter(|o| manages(&c, &o.id))
            .collect();
        Ok(Json(json!({ "organisations": list })))
    })
    .await
}

#[derive(Deserialize)]
struct NewOrganisation {
    name: String,
    status: String,
    #[serde(rename = "type", default = "cyber_partner")]
    kind: String,
    sector: Option<String>,
    region: Option<String>,
}

fn cyber_partner() -> String {
    "cyber_partner".into()
}

fn tier(s: &str) -> Result<Tier, ApiError> {
    Tier::parse(s)
        .filter(|t| *t > Tier::Public)
        .ok_or_else(|| unprocessable("status: observer, contributor, partner or core"))
}

async fn add_organisation(
    State(app): State<Shared>,
    headers: HeaderMap,
    Json(o): Json<NewOrganisation>,
) -> Result<Response, ApiError> {
    let c = superadmin(&app, &headers)?;
    let status = tier(&o.status)?;
    blocking(move || {
        let _w = WRITE.lock().map_err(internal)?;
        let id = parts::add_organisation(
            app.participants.path(),
            &o.name,
            status,
            &o.kind,
            o.sector.as_deref(),
            o.region.as_deref(),
        )
        .map_err(unprocessable)?;
        record(
            &app,
            &c,
            "participant_added",
            json!({ "participant": id, "name": o.name, "status": status.as_str(), "type": o.kind }),
        )?;
        Ok(created(
            json!({ "id": id, "name": o.name, "status": status }),
        ))
    })
    .await
}

#[derive(Deserialize)]
struct StatusChange {
    status: String,
}

async fn set_status(
    State(app): State<Shared>,
    headers: HeaderMap,
    UrlPath(id): UrlPath<String>,
    Json(change): Json<StatusChange>,
) -> Result<Json<Value>, ApiError> {
    let c = superadmin(&app, &headers)?;
    let status = tier(&change.status)?;
    blocking(move || {
        let _w = WRITE.lock().map_err(internal)?;
        let path = app.participants.path();
        if !parts::organisations(path)
            .map_err(internal)?
            .iter()
            .any(|o| o.id == id)
        {
            return Err(not_found("participant"));
        }
        parts::set_status(path, &id, status).map_err(conflict)?;
        record(
            &app,
            &c,
            "status_set",
            json!({ "participant": id, "status": status.as_str() }),
        )?;
        Ok(Json(json!({ "id": id, "status": status })))
    })
    .await
}

// --- users --------------------------------------------------------------

async fn users(
    State(app): State<Shared>,
    headers: HeaderMap,
    Query(scope): Query<Scope>,
) -> Result<Json<Value>, ApiError> {
    let c = admin(&app, &headers)?;
    blocking(move || {
        let list: Vec<_> = managed_users(&app, &c)?
            .into_iter()
            .filter(|u| scope.admits(&u.participant))
            .collect();
        Ok(Json(json!({ "users": list })))
    })
    .await
}

#[derive(Deserialize)]
struct NewUser {
    /// The organisation's id; an admin's own when missing.
    participant: Option<String>,
    name: String,
    #[serde(default = "human")]
    kind: String,
    role: Option<String>,
}

fn human() -> String {
    "human".into()
}

/// A role from a request: `null` or `"none"` is none.
fn role(s: Option<&str>) -> Result<Option<Role>, ApiError> {
    match s {
        None => Ok(None),
        Some(s) if s.eq_ignore_ascii_case("none") => Ok(None),
        Some(s) => Role::parse(s)
            .map(Some)
            .ok_or_else(|| unprocessable("role: admin, superadmin or none")),
    }
}

async fn add_user(
    State(app): State<Shared>,
    headers: HeaderMap,
    Json(u): Json<NewUser>,
) -> Result<Response, ApiError> {
    let c = admin(&app, &headers)?;
    let r = role(u.role.as_deref())?;
    if r == Some(Role::Superadmin) && c.role != Some(Role::Superadmin) {
        return Err(forbidden("only a superadmin makes a superadmin"));
    }
    blocking(move || {
        let _w = WRITE.lock().map_err(internal)?;
        let participant = u.participant.unwrap_or_else(|| c.participant.clone());
        let path = app.participants.path();
        if !manages(&c, &participant)
            || !parts::organisations(path)
                .map_err(internal)?
                .iter()
                .any(|o| o.id == participant)
        {
            return Err(not_found("participant"));
        }
        parts::add_user(path, &participant, &u.name, &u.kind, r).map_err(unprocessable)?;
        record(
            &app,
            &c,
            "user_added",
            json!({ "participant": participant, "user": u.name, "kind": u.kind, "role": r }),
        )?;
        Ok(created(
            json!({ "name": u.name, "kind": u.kind, "role": r, "participant": participant }),
        ))
    })
    .await
}

#[derive(Deserialize)]
struct RoleChange {
    role: Option<String>,
}

async fn set_role(
    State(app): State<Shared>,
    headers: HeaderMap,
    UrlPath(name): UrlPath<String>,
    Json(change): Json<RoleChange>,
) -> Result<Json<Value>, ApiError> {
    let c = admin(&app, &headers)?;
    let new = role(change.role.as_deref())?;
    blocking(move || {
        let _w = WRITE.lock().map_err(internal)?;
        let user = managed_user(&app, &c, &name)?;
        let superadmin = Some(Role::Superadmin);
        if (new == superadmin || user.role == superadmin) && c.role != superadmin {
            return Err(forbidden("only a superadmin grants or takes superadmin"));
        }
        let all = parts::users(app.participants.path()).map_err(internal)?;
        if user.role.is_some()
            && new.is_none()
            && all
                .iter()
                .filter(|u| u.participant == user.participant && u.role.is_some())
                .count()
                == 1
        {
            return Err(conflict(format!(
                "{name} is {}'s last admin: make another one first",
                user.organisation
            )));
        }
        if user.role == superadmin
            && new != superadmin
            && all.iter().filter(|u| u.role == superadmin).count() == 1
        {
            return Err(conflict(format!(
                "{name} is the last superadmin: make another one first"
            )));
        }
        parts::set_role(app.participants.path(), &name, new).map_err(unprocessable)?;
        record(&app, &c, "role_set", json!({ "user": name, "role": new }))?;
        Ok(Json(json!({ "name": name, "role": new })))
    })
    .await
}

// --- tokens -------------------------------------------------------------

async fn tokens(
    State(app): State<Shared>,
    headers: HeaderMap,
    Query(scope): Query<Scope>,
) -> Result<Json<Value>, ApiError> {
    let c = admin(&app, &headers)?;
    blocking(move || {
        let list: Vec<_> = parts::tokens(app.participants.path())
            .map_err(internal)?
            .into_iter()
            .filter(|t| manages(&c, &t.participant) && scope.admits(&t.participant))
            .collect();
        Ok(Json(json!({ "tokens": list })))
    })
    .await
}

#[derive(Deserialize)]
struct NewToken {
    user: String,
}

/// The new token is in this one response and nowhere else.
async fn add_token(
    State(app): State<Shared>,
    headers: HeaderMap,
    Json(t): Json<NewToken>,
) -> Result<Response, ApiError> {
    let c = admin(&app, &headers)?;
    blocking(move || {
        let _w = WRITE.lock().map_err(internal)?;
        let user = managed_user(&app, &c, &t.user)?;
        let token = parts::add_token(app.participants.path(), &user.name).map_err(internal)?;
        let prefix = hash(&token)[..12].to_string();
        record(
            &app,
            &c,
            "token_issued",
            json!({ "user": user.name, "token": prefix }),
        )?;
        let mut resp = created(json!({ "token": token, "prefix": prefix, "user": user.name }));
        resp.headers_mut()
            .insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
        Ok(resp)
    })
    .await
}

async fn revoke(
    State(app): State<Shared>,
    headers: HeaderMap,
    UrlPath(prefix): UrlPath<String>,
) -> Result<Json<Value>, ApiError> {
    let c = admin(&app, &headers)?;
    let prefix = prefix.to_ascii_lowercase();
    if prefix.len() < 8 || !prefix.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(unprocessable(
            "give at least 8 hex digits of the token's hash",
        ));
    }
    blocking(move || {
        let _w = WRITE.lock().map_err(internal)?;
        let path = app.participants.path();
        let active: Vec<_> = parts::tokens(path)
            .map_err(internal)?
            .into_iter()
            .filter(|t| !t.revoked)
            .collect();
        let matches: Vec<_> = active
            .iter()
            .filter(|t| t.prefix.starts_with(&prefix) && manages(&c, &t.participant))
            .collect();
        let t = match matches.as_slice() {
            [one] => *one,
            [] => return Err(not_found(&format!("active token {prefix}…"))),
            _ => return Err(unprocessable(format!("{prefix}… matches several tokens"))),
        };
        if t.user == c.user && active.iter().filter(|a| a.user == c.user).count() == 1 {
            return Err(conflict(
                "this is your last token: issue another first".into(),
            ));
        }
        parts::revoke(path, &t.prefix).map_err(unprocessable)?;
        record(
            &app,
            &c,
            "token_revoked",
            json!({ "user": t.user, "token": t.prefix }),
        )?;
        Ok(Json(json!({ "revoked": t.prefix, "user": t.user })))
    })
    .await
}

// --- audit --------------------------------------------------------------

#[derive(Deserialize)]
struct Window {
    days: Option<i64>,
}

/// The audit lines of the last `days` (7, at most 31), newest first. An
/// admin sees the lines about its organisation: its id, its users, its
/// tokens, or done by one of its users.
async fn audit(
    State(app): State<Shared>,
    headers: HeaderMap,
    Query(w): Query<Window>,
) -> Result<Json<Value>, ApiError> {
    let c = admin(&app, &headers)?;
    let days = w.days.unwrap_or(7).clamp(1, MAX_AUDIT_DAYS);
    blocking(move || {
        let from_day = (app.now)().div_euclid(DAY_NS) - (days - 1);
        let lines = app.audit.read_from(from_day).map_err(internal)?;
        let mut lines: Vec<Value> = if c.role == Some(Role::Superadmin) {
            lines
        } else {
            let users: Vec<String> = managed_users(&app, &c)?
                .into_iter()
                .map(|u| u.name)
                .collect();
            let tokens: Vec<String> = parts::tokens(app.participants.path())
                .map_err(internal)?
                .into_iter()
                .filter(|t| t.participant == c.participant)
                .map(|t| t.prefix)
                .collect();
            let by: Vec<String> = users
                .iter()
                .map(|u| format!("{u}@{}", c.organisation))
                .collect();
            lines
                .into_iter()
                .filter(|l| {
                    let s = |k: &str| l[k].as_str().unwrap_or("");
                    s("participant") == c.participant
                        || users.iter().any(|u| u == s("user"))
                        || tokens
                            .iter()
                            .any(|t| !s("token").is_empty() && t.starts_with(s("token")))
                        || by.iter().any(|b| b == s("by"))
                })
                .collect()
        };
        lines.reverse();
        lines.truncate(MAX_AUDIT_LINES);
        Ok(Json(json!({ "days": days, "lines": lines })))
    })
    .await
}
