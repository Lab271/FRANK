//! Participants (#159, ADR-016): organisations with one status, their
//! users, and the users' tokens, in `<participants>/participants.db`,
//! a directory of its own (with SQLite's journal) apart from the data.
//!
//! The server only reads this file. It keeps the tokens in memory and
//! reloads them when the file changes, so `frank participant`, `frank
//! user` and `frank token` take effect on the next request, with the
//! server running. Writers open the file for one command and close it;
//! db-core uses SQLite's locking and journal, so they never see a half
//! write.
//!
//! The schema keeps to what the row engine enforces today (db-core
//! #694-#696): rowid tables, single-column keys with explicit UNIQUE
//! indexes. The row engine cannot add a column to a table yet, so the
//! users' roles (#175) are a table of their own, created in files that
//! lack it.

use std::collections::{HashMap, HashSet};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::RwLock;
use std::time::SystemTime;

use db_core::engine::row::RowEngine;
use frank_core::{sql_quote, Tier};
use serde::Serialize;

use super::rowdb::{exec, int, open_engine, query, text, transaction};
use crate::auth::{hash, hex, random, uuid4, Caller, Role};

pub const FILE: &str = "participants.db";

const SCHEMA: [&str; 7] = [
    "CREATE TABLE organisations (id TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL, \
     status TEXT NOT NULL, sector TEXT, region TEXT, created INTEGER NOT NULL)",
    "CREATE UNIQUE INDEX organisations_id ON organisations (id)",
    "CREATE UNIQUE INDEX organisations_name ON organisations (name)",
    "CREATE TABLE users (id TEXT NOT NULL, organisation TEXT NOT NULL, name TEXT NOT NULL, \
     kind TEXT NOT NULL, created INTEGER NOT NULL)",
    "CREATE UNIQUE INDEX users_name ON users (name)",
    "CREATE TABLE tokens (hash TEXT NOT NULL, user TEXT NOT NULL, created INTEGER NOT NULL, \
     revoked INTEGER)",
    "CREATE UNIQUE INDEX tokens_hash ON tokens (hash)",
];

/// Users' roles (#175): one row per user that has one. Files written
/// before 0.17 get this table when they are next opened.
const ROLES: [&str; 2] = [
    "CREATE TABLE roles (user TEXT NOT NULL, role TEXT NOT NULL)",
    "CREATE UNIQUE INDEX roles_user ON roles (user)",
];

/// Disabled users (#175): their tokens stop working until they are
/// enabled again; only a disabled user can be removed.
const DISABLED: [&str; 2] = [
    "CREATE TABLE disabled (user TEXT NOT NULL, at INTEGER NOT NULL)",
    "CREATE UNIQUE INDEX disabled_user ON disabled (user)",
];

/// People signed in with SSO (#241, ADR-020): `subject` is the issuer and
/// the ID token's `sub`, one space apart (an issuer is a URL, without
/// spaces), so one column is the key.
const SSO_SUBJECTS: [&str; 2] = [
    "CREATE TABLE sso_subjects (subject TEXT NOT NULL, user TEXT NOT NULL, \
     created INTEGER NOT NULL)",
    "CREATE UNIQUE INDEX sso_subjects_subject ON sso_subjects (subject)",
];

/// SSO sessions (#241, ADR-020): the SHA-256 of the cookie's value, never
/// the value itself.
const SESSIONS: [&str; 2] = [
    "CREATE TABLE sessions (hash TEXT NOT NULL, user TEXT NOT NULL, created INTEGER NOT NULL, \
     expires INTEGER NOT NULL)",
    "CREATE UNIQUE INDEX sessions_hash ON sessions (hash)",
];

/// The tables added after 0.16, each with the table to probe for.
const ADDED: [(&str, &[&str]); 4] = [
    ("roles", &ROLES),
    ("disabled", &DISABLED),
    ("sso_subjects", &SSO_SUBJECTS),
    ("sessions", &SESSIONS),
];

/// How long an SSO session lasts (ADR-020).
pub const SESSION_SECONDS: i64 = 8 * 3600;

/// Organisation types (ADR-010).
pub const KINDS: [&str; 2] = ["cyber_partner", "customer"];
/// User kinds.
pub const USER_KINDS: [&str; 2] = ["human", "machine"];

/// One organisation, as `frank participant list` and core see it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Organisation {
    pub id: String,
    pub name: String,
    pub kind: String,
    pub status: Tier,
    pub sector: Option<String>,
    pub region: Option<String>,
    pub users: Vec<String>,
}

/// One user, as admins see it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct UserInfo {
    pub name: String,
    /// `human` or `machine`.
    pub kind: String,
    pub role: Option<Role>,
    /// Its tokens do not work while it is disabled.
    pub disabled: bool,
    /// The organisation's id and name.
    pub participant: String,
    pub organisation: String,
}

/// One token, without the token itself.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TokenInfo {
    /// The first 12 hex digits of the token's SHA-256.
    pub prefix: String,
    pub user: String,
    /// The organisation's id and name.
    pub participant: String,
    pub organisation: String,
    pub revoked: bool,
}

/// The server's view: token hash → caller, reloaded when the file changes.
pub struct Participants {
    path: PathBuf,
    cache: RwLock<Cache>,
}

#[derive(Default)]
struct Cache {
    stamp: Option<Stamp>,
    by_hash: HashMap<String, Caller>,
    /// Session hash → the caller and when the session ends (Unix s).
    by_session: HashMap<String, (Caller, i64)>,
}

/// What tells a changed file apart: size, modification time and the
/// SQLite header's change counter (bytes 24-27).
type Stamp = (u64, SystemTime, [u8; 4]);

impl Participants {
    /// Opens `<dir>/participants.db`, creating it if needed.
    pub fn open(dir: &Path) -> Result<Participants, String> {
        let path = dir.join(FILE);
        with_db(&path, |_| Ok(()))?;
        let p = Participants {
            path,
            cache: RwLock::new(Cache::default()),
        };
        p.refresh()?;
        Ok(p)
    }

    #[must_use]
    pub fn path(&self) -> &Path {
        &self.path
    }

    /// The caller an `Authorization` header value names: `None` for an
    /// unknown or revoked token, the public tier for no header.
    pub fn caller(&self, authorization: Option<&str>) -> Result<Option<Caller>, String> {
        let Some(value) = authorization else {
            return Ok(Some(Caller::public()));
        };
        let Some(token) = value.strip_prefix("Bearer ") else {
            return Ok(None);
        };
        self.refresh()?;
        let cache = self
            .cache
            .read()
            .map_err(|_| "participants lock poisoned")?;
        Ok(cache.by_hash.get(&hash(token.trim())).cloned())
    }

    /// The caller an SSO session cookie's value names at `now_s` (Unix
    /// seconds): `None` for an unknown or expired session, or a disabled
    /// user's.
    pub fn session_caller(&self, value: &str, now_s: i64) -> Result<Option<Caller>, String> {
        self.refresh()?;
        let cache = self
            .cache
            .read()
            .map_err(|_| "participants lock poisoned")?;
        Ok(cache
            .by_session
            .get(&hash(value.trim()))
            .filter(|(_, expires)| *expires > now_s)
            .map(|(c, _)| c.clone()))
    }

    /// Active tokens.
    pub fn active_tokens(&self) -> Result<usize, String> {
        self.refresh()?;
        Ok(self
            .cache
            .read()
            .map_err(|_| "participants lock poisoned")?
            .by_hash
            .len())
    }

    /// Reloads the tokens if the file changed since the last load.
    fn refresh(&self) -> Result<(), String> {
        let stamp = stamp(&self.path)?;
        if self
            .cache
            .read()
            .map_err(|_| "participants lock poisoned")?
            .stamp
            == Some(stamp)
        {
            return Ok(());
        }
        let (by_hash, by_session) = with_db(&self.path, load_callers)?;
        let mut cache = self
            .cache
            .write()
            .map_err(|_| "participants lock poisoned")?;
        *cache = Cache {
            stamp: Some(stamp),
            by_hash,
            by_session,
        };
        Ok(())
    }
}

fn stamp(path: &Path) -> Result<Stamp, String> {
    let meta = std::fs::metadata(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut header = [0u8; 28];
    std::fs::File::open(path)
        .and_then(|mut f| f.read_exact(&mut header))
        .map_err(|e| format!("{}: {e}", path.display()))?;
    Ok((
        meta.len(),
        meta.modified().map_err(|e| e.to_string())?,
        [header[24], header[25], header[26], header[27]],
    ))
}

/// Opens the database for one operation, creating the schema in a new
/// file.
fn with_db<T>(
    path: &Path,
    f: impl FnOnce(&mut RowEngine) -> Result<T, String>,
) -> Result<T, String> {
    let (mut db, fresh) = open_engine(path)?;
    if fresh {
        transaction(&mut db, |db| {
            SCHEMA
                .iter()
                .chain(ADDED.iter().flat_map(|(_, ddl)| ddl.iter()))
                .try_for_each(|ddl| exec(db, ddl))
        })?;
    } else {
        for (table, ddl) in ADDED {
            // db-core cannot read sqlite_master, so probe the table itself.
            if let Err(e) = query(&mut db, &format!("SELECT user FROM {table} LIMIT 1")) {
                if !e.contains("no such table") {
                    return Err(e);
                }
                transaction(&mut db, |db| ddl.iter().try_for_each(|d| exec(db, d)))?;
            }
        }
    }
    f(&mut db)
}

/// Token hash → caller, and session hash → (caller, expiry).
type Callers = (HashMap<String, Caller>, HashMap<String, (Caller, i64)>);

fn load_callers(db: &mut RowEngine) -> Result<Callers, String> {
    let dir = Directory::load(db)?;
    let mut by_hash = HashMap::new();
    for r in query(db, "SELECT hash, user FROM tokens WHERE revoked IS NULL")?.rows {
        if let Some(c) = dir.caller(&text(&r[1])) {
            by_hash.insert(text(&r[0]), c);
        }
    }
    let mut by_session = HashMap::new();
    for r in query(db, "SELECT hash, user, expires FROM sessions")?.rows {
        let user_id = text(&r[1]);
        // Only people sign in; a session of a machine user is never valid.
        if dir.users.get(&user_id).is_some_and(|u| u.2 != "human") {
            continue;
        }
        if let Some(c) = dir.caller(&user_id) {
            by_session.insert(text(&r[0]), (c, int(&r[2])));
        }
    }
    Ok((by_hash, by_session))
}

/// What makes a user id a caller, as [`load_callers`] reads it.
struct Directory {
    /// Organisation id → (name, status).
    orgs: HashMap<String, (String, Tier)>,
    /// User id → (organisation id, name, kind).
    users: HashMap<String, (String, String, String)>,
    roles: HashMap<String, Role>,
    disabled: HashSet<String>,
}

impl Directory {
    fn load(db: &mut RowEngine) -> Result<Directory, String> {
        let orgs = query(db, "SELECT id, name, status FROM organisations")?
            .rows
            .iter()
            .filter_map(|r| Some((text(&r[0]), (text(&r[1]), Tier::parse(&text(&r[2]))?))))
            .collect();
        let users = query(db, "SELECT id, organisation, name, kind FROM users")?
            .rows
            .iter()
            .map(|r| (text(&r[0]), (text(&r[1]), text(&r[2]), text(&r[3]))))
            .collect();
        let roles = roles(db)?;
        let disabled = disabled(db)?;
        Ok(Directory {
            orgs,
            users,
            roles,
            disabled,
        })
    }

    /// The working user with id `user_id` as a caller.
    fn caller(&self, user_id: &str) -> Option<Caller> {
        if self.disabled.contains(user_id) {
            return None;
        }
        let (org, user, _) = self.users.get(user_id)?;
        let (name, status) = self.orgs.get(org)?;
        Some(Caller {
            tier: *status,
            participant: org.clone(),
            organisation: name.clone(),
            user: user.clone(),
            role: self.roles.get(user_id).copied(),
        })
    }
}

/// User id → role.
fn roles(db: &mut RowEngine) -> Result<HashMap<String, Role>, String> {
    Ok(query(db, "SELECT user, role FROM roles")?
        .rows
        .iter()
        .filter_map(|r| Some((text(&r[0]), Role::parse(&text(&r[1]))?)))
        .collect())
}

/// The ids of the disabled users.
fn disabled(db: &mut RowEngine) -> Result<HashSet<String>, String> {
    Ok(query(db, "SELECT user FROM disabled")?
        .rows
        .iter()
        .map(|r| text(&r[0]))
        .collect())
}

/// Whether `user`, a `kind` user of an organisation with `status`, may
/// hold `role`: only people do; an admin's organisation is contributor
/// or higher, a superadmin's is core.
fn check_role(user: &str, kind: &str, status: Tier, role: Role) -> Result<(), String> {
    if kind != "human" {
        return Err(format!("{user} is a machine user: only people hold a role"));
    }
    let least = match role {
        Role::Admin => Tier::Contributor,
        Role::Superadmin => Tier::Core,
    };
    if status < least {
        return Err(format!(
            "{role} needs a {least} organisation or higher; {user}'s is {status}"
        ));
    }
    Ok(())
}

// --- administration: one call opens, changes and closes the file ---------

/// A name: 1-64 characters of `[A-Za-z0-9._@-]`, so it is safe in logs,
/// on the command line and in SQL. User names may also hold `+`, for
/// plus-addressed e-mail (#215); they only travel in URL paths, while an
/// organisation's name is also a query value, where `+` reads as a space.
fn check_name(what: &str, name: &str) -> Result<(), String> {
    let extra: &[u8] = if what == "user" { b"._@-+" } else { b"._@-" };
    let ok = !name.is_empty()
        && name.len() <= 64
        && name
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || extra.contains(&b));
    if ok {
        Ok(())
    } else {
        let plus = if what == "user" { ", '+'" } else { "" };
        Err(format!(
            "{what} {name:?}: use 1-64 letters, digits, '.', '_', '@'{plus} or '-'"
        ))
    }
}

fn check_label(what: &str, v: Option<&str>) -> Result<Option<String>, String> {
    let Some(v) = v
        .map(|v| v.trim().to_ascii_lowercase())
        .filter(|v| !v.is_empty())
    else {
        return Ok(None);
    };
    if v.len() <= 64 && v.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_') {
        Ok(Some(v))
    } else {
        Err(format!("{what} {v:?}: use [a-z0-9_]"))
    }
}

fn opt(v: Option<&String>) -> String {
    v.map_or("NULL".into(), |v| sql_quote(v))
}

fn now_s() -> i64 {
    let d = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default();
    i64::try_from(d.as_secs()).unwrap_or(i64::MAX)
}

/// The organisation `name_or_id` names: `(id, name)`.
fn find_org(db: &mut RowEngine, name_or_id: &str) -> Result<(String, String), String> {
    let q = sql_quote(name_or_id);
    for col in ["name", "id"] {
        let r = query(
            db,
            &format!("SELECT id, name FROM organisations WHERE {col} = {q}"),
        )?;
        if let Some(row) = r.rows.first() {
            return Ok((text(&row[0]), text(&row[1])));
        }
    }
    Err(format!("no participant {name_or_id:?}"))
}

/// The user called `name`: its id.
fn find_user(db: &mut RowEngine, name: &str) -> Result<String, String> {
    let r = query(
        db,
        &format!("SELECT id FROM users WHERE name = {}", sql_quote(name)),
    )?;
    r.rows
        .first()
        .map(|row| text(&row[0]))
        .ok_or_else(|| format!("no user {name:?}"))
}

/// The user called `name`: `(id, organisation id, kind)`.
fn find_user_row(db: &mut RowEngine, name: &str) -> Result<(String, String, String), String> {
    let r = query(
        db,
        &format!(
            "SELECT id, organisation, kind FROM users WHERE name = {}",
            sql_quote(name)
        ),
    )?;
    r.rows
        .first()
        .map(|row| (text(&row[0]), text(&row[1]), text(&row[2])))
        .ok_or_else(|| format!("no user {name:?}"))
}

/// The status of the organisation with id `id`.
fn org_status(db: &mut RowEngine, id: &str) -> Result<Tier, String> {
    let r = query(
        db,
        &format!(
            "SELECT status FROM organisations WHERE id = {}",
            sql_quote(id)
        ),
    )?;
    r.rows
        .first()
        .and_then(|row| Tier::parse(&text(&row[0])))
        .ok_or_else(|| format!("no participant {id:?}"))
}

/// Registers an organisation; returns its id (`identity--{uuid4}`).
pub fn add_organisation(
    path: &Path,
    name: &str,
    status: Tier,
    kind: &str,
    sector: Option<&str>,
    region: Option<&str>,
) -> Result<String, String> {
    check_name("participant", name)?;
    if !KINDS.contains(&kind) {
        return Err(format!("type {kind:?}: one of {}", KINDS.join(", ")));
    }
    let sector = check_label("sector", sector)?;
    let region = check_label("region", region)?;
    let id = format!("identity--{}", uuid4()?);
    with_db(path, |db| {
        if find_org(db, name).is_ok() {
            return Err(format!("participant {name:?} exists"));
        }
        exec(
            db,
            &format!(
                "INSERT INTO organisations (id, name, kind, status, sector, region, created) \
                 VALUES ({}, {}, {}, {}, {}, {}, {})",
                sql_quote(&id),
                sql_quote(name),
                sql_quote(kind),
                sql_quote(status.as_str()),
                opt(sector.as_ref()),
                opt(region.as_ref()),
                now_s()
            ),
        )
    })?;
    Ok(id)
}

/// The id of the organisation `name_or_id` names.
pub fn organisation_id(path: &Path, name_or_id: &str) -> Result<String, String> {
    with_db(path, |db| find_org(db, name_or_id).map(|(id, _)| id))
}

/// Sets an organisation's status; all its users have it from their next
/// request. Refused while one of its users holds a role the new status
/// does not allow (a superadmin outside core, an admin in an observer).
pub fn set_status(path: &Path, name_or_id: &str, status: Tier) -> Result<(), String> {
    with_db(path, |db| {
        let (id, _) = find_org(db, name_or_id)?;
        let roles = roles(db)?;
        let users = query(
            db,
            &format!(
                "SELECT id, name, kind FROM users WHERE organisation = {}",
                sql_quote(&id)
            ),
        )?;
        for r in &users.rows {
            if let Some(role) = roles.get(&text(&r[0])) {
                let name = text(&r[1]);
                check_role(&name, &text(&r[2]), status, *role)
                    .map_err(|e| format!("{e}: change {name}'s role first"))?;
            }
        }
        exec(
            db,
            &format!(
                "UPDATE organisations SET status = {} WHERE id = {}",
                sql_quote(status.as_str()),
                sql_quote(&id)
            ),
        )
    })
}

/// Every organisation, by name, with its users.
pub fn organisations(path: &Path) -> Result<Vec<Organisation>, String> {
    with_db(path, |db| {
        let mut users: HashMap<String, Vec<String>> = HashMap::new();
        for r in query(db, "SELECT organisation, name FROM users")?.rows {
            users.entry(text(&r[0])).or_default().push(text(&r[1]));
        }
        let r = query(
            db,
            "SELECT id, name, kind, status, sector, region FROM organisations",
        )?;
        let mut out: Vec<Organisation> = r
            .rows
            .iter()
            .map(|row| {
                let id = text(&row[0]);
                let mut u = users.remove(&id).unwrap_or_default();
                u.sort();
                Organisation {
                    name: text(&row[1]),
                    kind: text(&row[2]),
                    status: Tier::parse(&text(&row[3])).unwrap_or(Tier::Public),
                    sector: Some(text(&row[4])).filter(|s| !s.is_empty()),
                    region: Some(text(&row[5])).filter(|s| !s.is_empty()),
                    users: u,
                    id,
                }
            })
            .collect();
        out.sort_by(|a, b| a.name.cmp(&b.name));
        Ok(out)
    })
}

/// Adds a user (`human` or `machine`) to an organisation, with a role
/// or none.
pub fn add_user(
    path: &Path,
    organisation: &str,
    name: &str,
    kind: &str,
    role: Option<Role>,
) -> Result<(), String> {
    check_name("user", name)?;
    if !USER_KINDS.contains(&kind) {
        return Err(format!("user kind {kind:?}: human or machine"));
    }
    with_db(path, |db| {
        let (org, _) = find_org(db, organisation)?;
        if find_user(db, name).is_ok() {
            return Err(format!("user {name:?} exists"));
        }
        if let Some(role) = role {
            check_role(name, kind, org_status(db, &org)?, role)?;
        }
        let id = uuid4()?;
        transaction(db, |db| {
            exec(
                db,
                &format!(
                    "INSERT INTO users (id, organisation, name, kind, created) VALUES ({}, {}, {}, {}, {})",
                    sql_quote(&id),
                    sql_quote(&org),
                    sql_quote(name),
                    sql_quote(kind),
                    now_s()
                ),
            )?;
            match role {
                Some(role) => insert_role(db, &id, role),
                None => Ok(()),
            }
        })
    })
}

fn insert_role(db: &mut RowEngine, user_id: &str, role: Role) -> Result<(), String> {
    exec(
        db,
        &format!(
            "INSERT INTO roles (user, role) VALUES ({}, {})",
            sql_quote(user_id),
            sql_quote(role.as_str())
        ),
    )
}

/// Gives `user` a role, or takes it away with `None`.
pub fn set_role(path: &Path, user: &str, role: Option<Role>) -> Result<(), String> {
    with_db(path, |db| {
        let (id, org, kind) = find_user_row(db, user)?;
        if let Some(role) = role {
            check_role(user, &kind, org_status(db, &org)?, role)?;
        }
        transaction(db, |db| {
            exec(
                db,
                &format!("DELETE FROM roles WHERE user = {}", sql_quote(&id)),
            )?;
            match role {
                Some(role) => insert_role(db, &id, role),
                None => Ok(()),
            }
        })
    })
}

/// Every user, by organisation and name.
pub fn users(path: &Path) -> Result<Vec<UserInfo>, String> {
    with_db(path, |db| {
        let orgs: HashMap<String, String> = query(db, "SELECT id, name FROM organisations")?
            .rows
            .iter()
            .map(|r| (text(&r[0]), text(&r[1])))
            .collect();
        let roles = roles(db)?;
        let disabled = disabled(db)?;
        let mut out: Vec<UserInfo> = query(db, "SELECT id, organisation, name, kind FROM users")?
            .rows
            .iter()
            .map(|r| {
                let participant = text(&r[1]);
                UserInfo {
                    name: text(&r[2]),
                    kind: text(&r[3]),
                    role: roles.get(&text(&r[0])).copied(),
                    disabled: disabled.contains(&text(&r[0])),
                    organisation: orgs.get(&participant).cloned().unwrap_or_default(),
                    participant,
                }
            })
            .collect();
        out.sort_by(|a, b| (&a.organisation, &a.name).cmp(&(&b.organisation, &b.name)));
        Ok(out)
    })
}

/// Disables `user` (its tokens stop working, none are revoked) or
/// enables it again.
pub fn set_disabled(path: &Path, user: &str, disable: bool) -> Result<(), String> {
    with_db(path, |db| {
        let id = find_user(db, user)?;
        let q = sql_quote(&id);
        transaction(db, |db| {
            exec(db, &format!("DELETE FROM disabled WHERE user = {q}"))?;
            if disable {
                exec(
                    db,
                    &format!("INSERT INTO disabled (user, at) VALUES ({q}, {})", now_s()),
                )?;
            }
            Ok(())
        })
    })
}

/// Removes a disabled user with its role, tokens, SSO link and sessions;
/// returns the
/// prefixes of the tokens removed. Its sightings stay: they are stored
/// under the organisation, never under a user.
pub fn remove_user(path: &Path, user: &str) -> Result<Vec<String>, String> {
    with_db(path, |db| {
        let id = find_user(db, user)?;
        if !disabled(db)?.contains(&id) {
            return Err(format!("{user} is not disabled: disable it first"));
        }
        let q = sql_quote(&id);
        let prefixes = query(db, &format!("SELECT hash FROM tokens WHERE user = {q}"))?
            .rows
            .iter()
            .map(|r| text(&r[0])[..12].to_string())
            .collect();
        transaction(db, |db| {
            for table in ["tokens", "roles", "disabled", "sso_subjects", "sessions"] {
                exec(db, &format!("DELETE FROM {table} WHERE user = {q}"))?;
            }
            exec(db, &format!("DELETE FROM users WHERE id = {q}"))
        })?;
        Ok(prefixes)
    })
}

// --- SSO (#241, ADR-020) ---------------------------------------------------

/// A person as the identity provider vouches for them, from a checked ID
/// token.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Identity {
    pub issuer: String,
    /// The ID token's `sub`.
    pub subject: String,
    pub email: Option<String>,
    pub email_verified: bool,
}

/// How a sign-in found its user.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SignedIn {
    /// The identity was linked to the user before.
    Known,
    /// An existing human user with the identity's verified e-mail.
    Linked,
    /// A new human user, created in the default organisation, no role.
    Provisioned,
}

impl SignedIn {
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            SignedIn::Known => "known",
            SignedIn::Linked => "linked",
            SignedIn::Provisioned => "provisioned",
        }
    }
}

/// The user an identity signs in as (ADR-020, decision 5), creating it in
/// `organisation` on first sign-in. The outer error is a failure of the
/// store; the inner one a refusal, with the reason for the audit line.
pub fn sign_in(
    path: &Path,
    id: &Identity,
    organisation: &str,
) -> Result<Result<(String, SignedIn), String>, String> {
    if id.issuer.contains(' ') || id.subject.is_empty() {
        return Ok(Err("malformed issuer or subject".into()));
    }
    let key = format!("{} {}", id.issuer, id.subject);
    with_db(path, |db| {
        let disabled = disabled(db)?;
        let linked = query(
            db,
            &format!(
                "SELECT user FROM sso_subjects WHERE subject = {}",
                sql_quote(&key)
            ),
        )?;
        if let Some(row) = linked.rows.first() {
            return sign_in_known(db, &text(&row[0]), &disabled);
        }
        let Some(name) = id.email.as_deref().map(|e| e.trim().to_ascii_lowercase()) else {
            return Ok(Err("the ID token has no email claim".into()));
        };
        if check_name("user", &name).is_err() {
            return Ok(Err(format!("{name:?} is not a valid user name")));
        }
        if let Ok((user_id, _, kind)) = find_user_row(db, &name) {
            let user = (name, user_id, kind);
            return link_existing(db, &key, user, id.email_verified, &disabled);
        }
        provision(db, &key, name, organisation)
    })
}

/// What [`sign_in`] comes to: a store failure, or a refusal or the user.
type SignInResult = Result<Result<(String, SignedIn), String>, String>;

/// An identity linked before signs in as its user, while that is a
/// working human.
fn sign_in_known(db: &mut RowEngine, user_id: &str, disabled: &HashSet<String>) -> SignInResult {
    let r = query(
        db,
        &format!(
            "SELECT name, kind FROM users WHERE id = {}",
            sql_quote(user_id)
        ),
    )?;
    let Some(u) = r.rows.first() else {
        return Ok(Err("the linked user no longer exists".into()));
    };
    let name = text(&u[0]);
    if text(&u[1]) != "human" {
        return Ok(Err(format!("{name} is a machine user")));
    }
    if disabled.contains(user_id) {
        return Ok(Err(format!("{name} is disabled")));
    }
    Ok(Ok((name, SignedIn::Known)))
}

/// Links the identity (`key`) to the existing user `(name, id, kind)`: a
/// working human, by a verified e-mail, not linked to another identity.
fn link_existing(
    db: &mut RowEngine,
    key: &str,
    (name, user_id, kind): (String, String, String),
    email_verified: bool,
    disabled: &HashSet<String>,
) -> SignInResult {
    if kind != "human" {
        return Ok(Err(format!("{name} is a machine user")));
    }
    if !email_verified {
        return Ok(Err(format!(
            "{name} exists and the identity's e-mail is not verified"
        )));
    }
    if disabled.contains(&user_id) {
        return Ok(Err(format!("{name} is disabled")));
    }
    let other = query(
        db,
        &format!(
            "SELECT subject FROM sso_subjects WHERE user = {}",
            sql_quote(&user_id)
        ),
    )?;
    if !other.rows.is_empty() {
        return Ok(Err(format!("{name} is linked to another identity")));
    }
    link_subject(db, key, &user_id)?;
    Ok(Ok((name, SignedIn::Linked)))
}

/// Creates the human user `name` in `organisation`, without a role, linked
/// to the identity (`key`), in one transaction.
fn provision(db: &mut RowEngine, key: &str, name: String, organisation: &str) -> SignInResult {
    let (org, _) = find_org(db, organisation)?;
    let user_id = uuid4()?;
    transaction(db, |db| {
        exec(
            db,
            &format!(
                "INSERT INTO users (id, organisation, name, kind, created) VALUES ({}, {}, {}, 'human', {})",
                sql_quote(&user_id),
                sql_quote(&org),
                sql_quote(&name),
                now_s()
            ),
        )?;
        link_subject(db, key, &user_id)
    })?;
    Ok(Ok((name, SignedIn::Provisioned)))
}

/// Links the identity `key` (issuer and subject) to the user `user_id`.
fn link_subject(db: &mut RowEngine, key: &str, user_id: &str) -> Result<(), String> {
    exec(
        db,
        &format!(
            "INSERT INTO sso_subjects (subject, user, created) VALUES ({}, {}, {})",
            sql_quote(key),
            sql_quote(user_id),
            now_s()
        ),
    )
}

/// Starts an SSO session for the human user `user` and returns the value
/// for its cookie; only the value's SHA-256 is stored. Drops expired
/// sessions on the way.
pub fn add_session(path: &Path, user: &str) -> Result<String, String> {
    let value = hex(&random::<32>()?);
    with_db(path, |db| {
        let (user_id, _, kind) = find_user_row(db, user)?;
        if kind != "human" {
            return Err(format!("{user} is a machine user: only people sign in"));
        }
        if disabled(db)?.contains(&user_id) {
            return Err(format!("{user} is disabled"));
        }
        let now = now_s();
        transaction(db, |db| {
            exec(db, &format!("DELETE FROM sessions WHERE expires <= {now}"))?;
            exec(
                db,
                &format!(
                    "INSERT INTO sessions (hash, user, created, expires) VALUES ({}, {}, {now}, {})",
                    sql_quote(&hash(&value)),
                    sql_quote(&user_id),
                    now + SESSION_SECONDS
                ),
            )
        })
    })?;
    Ok(value)
}

/// Ends the session a cookie's value names; returns whether there was one.
pub fn end_session(path: &Path, value: &str) -> Result<bool, String> {
    let q = sql_quote(&hash(value.trim()));
    with_db(path, |db| {
        let found = !query(db, &format!("SELECT user FROM sessions WHERE hash = {q}"))?
            .rows
            .is_empty();
        if found {
            exec(db, &format!("DELETE FROM sessions WHERE hash = {q}"))?;
        }
        Ok(found)
    })
}

/// Creates a token for `user` and returns it; only its hash is stored.
pub fn add_token(path: &Path, user: &str) -> Result<String, String> {
    let token = format!("frank_{}", hex(&random::<24>()?));
    add_token_hash(path, user, &hash(&token))?;
    Ok(token)
}

/// Stores a token's SHA-256 (64 hex digits) for `user`.
pub fn add_token_hash(path: &Path, user: &str, token_hash: &str) -> Result<(), String> {
    let token_hash = token_hash.to_ascii_lowercase();
    if token_hash.len() != 64 || !token_hash.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("not a SHA-256 hex digest".into());
    }
    with_db(path, |db| {
        let name = user;
        let user = find_user(db, user)?;
        if disabled(db)?.contains(&user) {
            return Err(format!("{name} is disabled: enable it first"));
        }
        exec(
            db,
            &format!(
                "INSERT INTO tokens (hash, user, created, revoked) VALUES ({}, {}, {}, NULL)",
                sql_quote(&token_hash),
                sql_quote(&user),
                now_s()
            ),
        )
    })
}

/// Every token, by organisation and user.
pub fn tokens(path: &Path) -> Result<Vec<TokenInfo>, String> {
    with_db(path, |db| {
        let orgs: HashMap<String, String> = query(db, "SELECT id, name FROM organisations")?
            .rows
            .iter()
            .map(|r| (text(&r[0]), text(&r[1])))
            .collect();
        let users: HashMap<String, (String, String)> =
            query(db, "SELECT id, name, organisation FROM users")?
                .rows
                .iter()
                .map(|r| (text(&r[0]), (text(&r[1]), text(&r[2]))))
                .collect();
        let mut out: Vec<TokenInfo> = query(db, "SELECT hash, user, revoked FROM tokens")?
            .rows
            .iter()
            .map(|r| {
                let (user, org) = users.get(&text(&r[1])).cloned().unwrap_or_default();
                TokenInfo {
                    prefix: text(&r[0])[..12].to_string(),
                    user,
                    organisation: orgs.get(&org).cloned().unwrap_or_default(),
                    participant: org,
                    revoked: int(&r[2]) != 0,
                }
            })
            .collect();
        out.sort_by(|a, b| (&a.organisation, &a.user).cmp(&(&b.organisation, &b.user)));
        Ok(out)
    })
}

/// Revokes the one token whose hash starts with `prefix` (at least 8 hex
/// digits, as `frank token list` shows them).
pub fn revoke(path: &Path, prefix: &str) -> Result<(), String> {
    let prefix = prefix.to_ascii_lowercase();
    if prefix.len() < 8 || !prefix.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("give at least 8 hex digits of the token's hash (frank token list)".into());
    }
    with_db(path, |db| {
        let all = query(db, "SELECT hash FROM tokens WHERE revoked IS NULL")?;
        let matches: Vec<String> = all
            .rows
            .iter()
            .map(|r| text(&r[0]))
            .filter(|h| h.starts_with(&prefix))
            .collect();
        match matches.as_slice() {
            [one] => exec(
                db,
                &format!(
                    "UPDATE tokens SET revoked = {} WHERE hash = {}",
                    now_s(),
                    sql_quote(one)
                ),
            ),
            [] => Err(format!("no active token {prefix}…")),
            _ => Err(format!(
                "{prefix}… matches several tokens: give more digits"
            )),
        }
    })
}

/// Imports a Phase 3 tokens file (`<sha256> <tier> <label>` lines): each
/// line becomes its own organisation and user, named after the label
/// (`token-<hash>` without one), with the line's tier as status. Returns
/// the organisations created. Merge organisations that are one afterwards.
pub fn import_tokens_file(path: &Path, file: &Path) -> Result<Vec<String>, String> {
    let text = std::fs::read_to_string(file).map_err(|e| format!("{}: {e}", file.display()))?;
    let mut created = Vec::new();
    for (n, line) in text.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let mut parts = line.splitn(3, char::is_whitespace);
        let (Some(h), Some(tier)) = (parts.next(), parts.next()) else {
            return Err(format!(
                "{}:{}: expected `<sha256> <tier> [label]`",
                file.display(),
                n + 1
            ));
        };
        let tier = Tier::parse(tier)
            .ok_or_else(|| format!("{}:{}: unknown tier {tier:?}", file.display(), n + 1))?;
        let label: String = parts
            .next()
            .unwrap_or("")
            .trim()
            .chars()
            .map(|c| {
                if c.is_ascii_alphanumeric() || "._@-".contains(c) {
                    c
                } else {
                    '-'
                }
            })
            .take(48)
            .collect();
        let base = if label.is_empty() {
            format!("token-{}", &h[..h.len().min(8)])
        } else {
            label
        };
        let existing: Vec<String> = organisations(path)?.into_iter().map(|o| o.name).collect();
        let mut name = base.clone();
        let mut i = 2;
        while existing.contains(&name) {
            name = format!("{base}-{i}");
            i += 1;
        }
        add_organisation(path, &name, tier, "cyber_partner", None, None)?;
        add_user(path, &name, &name, "human", None)?;
        add_token_hash(path, &name, h)?;
        created.push(name);
    }
    Ok(created)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp(name: &str) -> PathBuf {
        let dir =
            std::env::temp_dir().join(format!("frank-participants-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn users_inherit_their_organisation_status() {
        let dir = temp("inherit");
        let path = dir.join(FILE);
        let server = Participants::open(&dir).unwrap();
        let id = add_organisation(
            &path,
            "acme-mdr",
            Tier::Contributor,
            "cyber_partner",
            Some("Energy"),
            None,
        )
        .unwrap();
        assert!(id.starts_with("identity--") && id.len() == 46, "{id}");
        add_user(&path, "acme-mdr", "alice", "human", None).unwrap();
        add_user(&path, "acme-mdr", "acme-feed", "machine", None).unwrap();
        let a = add_token(&path, "alice").unwrap();
        let b = add_token(&path, "acme-feed").unwrap();

        // Written by another handle, seen by the running server.
        let ca = server
            .caller(Some(&format!("Bearer {a}")))
            .unwrap()
            .unwrap();
        let cb = server
            .caller(Some(&format!("Bearer {b}")))
            .unwrap()
            .unwrap();
        assert_eq!((ca.tier, cb.tier), (Tier::Contributor, Tier::Contributor));
        assert_eq!(ca.participant, id);
        assert_eq!(ca.participant, cb.participant, "one organisation");
        assert_eq!((ca.user.as_str(), cb.user.as_str()), ("alice", "acme-feed"));

        set_status(&path, "acme-mdr", Tier::Partner).unwrap();
        for t in [&a, &b] {
            let c = server
                .caller(Some(&format!("Bearer {t}")))
                .unwrap()
                .unwrap();
            assert_eq!(c.tier, Tier::Partner, "a status change reaches every user");
        }
        assert_eq!(server.caller(None).unwrap().unwrap().tier, Tier::Public);
        assert_eq!(server.caller(Some("Bearer nope")).unwrap(), None);
        assert_eq!(server.caller(Some(&a)).unwrap(), None, "not a bearer token");
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn revoking_one_token_leaves_the_others() {
        let dir = temp("revoke");
        let path = dir.join(FILE);
        let server = Participants::open(&dir).unwrap();
        add_organisation(&path, "lab", Tier::Partner, "cyber_partner", None, None).unwrap();
        add_user(&path, "lab", "bob", "human", None).unwrap();
        let a = add_token(&path, "bob").unwrap();
        let b = add_token(&path, "bob").unwrap();
        assert!(
            !std::fs::read(&path)
                .unwrap()
                .windows(a.len())
                .any(|w| w == a.as_bytes()),
            "only hashes are stored"
        );
        revoke(&path, &hash(&a)[..10]).unwrap();
        assert_eq!(server.caller(Some(&format!("Bearer {a}"))).unwrap(), None);
        assert!(server
            .caller(Some(&format!("Bearer {b}")))
            .unwrap()
            .is_some());
        assert!(revoke(&path, "abc").is_err(), "too short");
        let list = tokens(&path).unwrap();
        assert_eq!(list.iter().filter(|t| t.revoked).count(), 1);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn refuses_bad_names_and_duplicates() {
        let dir = temp("names");
        let path = dir.join(FILE);
        add_organisation(&path, "lab", Tier::Partner, "cyber_partner", None, None).unwrap();
        assert!(
            add_organisation(&path, "lab", Tier::Observer, "cyber_partner", None, None).is_err()
        );
        assert!(add_organisation(
            &path,
            "x'; DROP",
            Tier::Observer,
            "cyber_partner",
            None,
            None
        )
        .is_err());
        assert!(add_organisation(&path, "y", Tier::Observer, "bank", None, None).is_err());
        add_user(&path, "lab", "u1", "human", None).unwrap();
        assert!(
            add_user(&path, "lab", "u1", "human", None).is_err(),
            "user names are unique"
        );
        assert!(add_user(&path, "nope", "u2", "human", None).is_err());
        assert!(add_user(&path, "lab", "u3", "robot", None).is_err());
        add_user(&path, "lab", "u4+mdr@example.com", "machine", None).unwrap();
        assert!(add_user(&path, "lab", "u5 x", "human", None).is_err());
        assert!(
            add_organisation(&path, "a+b", Tier::Observer, "cyber_partner", None, None).is_err(),
            "organisation names keep the old rule"
        );
        let orgs = organisations(&path).unwrap();
        assert_eq!(orgs.len(), 1);
        assert_eq!(orgs[0].users, ["u1", "u4+mdr@example.com"]);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn disable_then_remove() {
        let dir = temp("disable");
        let path = dir.join(FILE);
        let server = Participants::open(&dir).unwrap();
        add_organisation(&path, "mdr", Tier::Contributor, "cyber_partner", None, None).unwrap();
        add_user(&path, "mdr", "amy", "human", Some(Role::Admin)).unwrap();
        let t = add_token(&path, "amy").unwrap();
        let bearer = format!("Bearer {t}");

        assert!(remove_user(&path, "amy").is_err(), "disable first");
        set_disabled(&path, "amy", true).unwrap();
        assert_eq!(server.caller(Some(&bearer)).unwrap(), None, "tokens stop");
        assert!(add_token(&path, "amy").is_err(), "no tokens while disabled");
        assert!(users(&path).unwrap()[0].disabled);
        set_disabled(&path, "amy", false).unwrap();
        assert!(
            server.caller(Some(&bearer)).unwrap().is_some(),
            "and work again"
        );

        set_disabled(&path, "amy", true).unwrap();
        let removed = remove_user(&path, "amy").unwrap();
        assert_eq!(removed, [hash(&t)[..12].to_string()]);
        assert!(users(&path).unwrap().is_empty());
        assert!(tokens(&path).unwrap().is_empty());
        // The name is free again, without the old role.
        add_user(&path, "mdr", "amy", "human", None).unwrap();
        assert_eq!(users(&path).unwrap()[0].role, None);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn roles_follow_the_rules() {
        let dir = temp("roles");
        let path = dir.join(FILE);
        let server = Participants::open(&dir).unwrap();
        add_organisation(&path, "ops", Tier::Core, "cyber_partner", None, None).unwrap();
        add_organisation(&path, "mdr", Tier::Contributor, "cyber_partner", None, None).unwrap();
        add_organisation(&path, "obs", Tier::Observer, "customer", None, None).unwrap();
        add_user(&path, "ops", "root", "human", Some(Role::Superadmin)).unwrap();
        add_user(&path, "mdr", "amy", "human", Some(Role::Admin)).unwrap();
        add_user(&path, "mdr", "feed", "machine", None).unwrap();
        add_user(&path, "obs", "olga", "human", None).unwrap();

        // Only people; admin from contributor up; superadmin in core only.
        assert!(set_role(&path, "feed", Some(Role::Admin)).is_err());
        assert!(add_user(&path, "mdr", "bot", "machine", Some(Role::Admin)).is_err());
        assert!(organisations(&path).unwrap()[0]
            .users
            .iter()
            .all(|u| u != "bot"));
        assert!(set_role(&path, "olga", Some(Role::Admin)).is_err());
        assert!(set_role(&path, "amy", Some(Role::Superadmin)).is_err());

        // The running server sees roles on the next request.
        let t = add_token(&path, "amy").unwrap();
        let bearer = format!("Bearer {t}");
        assert_eq!(
            server.caller(Some(&bearer)).unwrap().unwrap().role,
            Some(Role::Admin)
        );
        set_role(&path, "amy", None).unwrap();
        assert_eq!(server.caller(Some(&bearer)).unwrap().unwrap().role, None);
        set_role(&path, "amy", Some(Role::Admin)).unwrap();
        set_role(&path, "amy", Some(Role::Admin)).unwrap();

        // A status change may not strand a role.
        assert!(set_status(&path, "mdr", Tier::Observer).is_err());
        assert!(set_status(&path, "ops", Tier::Partner).is_err());
        set_status(&path, "mdr", Tier::Partner).unwrap();

        let users = users(&path).unwrap();
        let roles: Vec<(&str, Option<Role>)> =
            users.iter().map(|u| (u.name.as_str(), u.role)).collect();
        assert_eq!(
            roles,
            [
                ("amy", Some(Role::Admin)),
                ("feed", None),
                ("olga", None),
                ("root", Some(Role::Superadmin))
            ]
        );
        assert_eq!(users[0].organisation, "mdr");
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_file_without_roles_gets_the_table() {
        let dir = temp("upgrade");
        let path = dir.join(FILE);
        {
            // As 0.13-0.16 wrote it.
            let (mut db, _) = open_engine(&path).unwrap();
            transaction(&mut db, |db| {
                SCHEMA.iter().try_for_each(|ddl| exec(db, ddl))
            })
            .unwrap();
        }
        add_organisation(&path, "ops", Tier::Core, "cyber_partner", None, None).unwrap();
        add_user(&path, "ops", "root", "human", None).unwrap();
        let t = add_token(&path, "root").unwrap();
        set_role(&path, "root", Some(Role::Superadmin)).unwrap();
        let server = Participants::open(&dir).unwrap();
        let c = server
            .caller(Some(&format!("Bearer {t}")))
            .unwrap()
            .unwrap();
        assert_eq!(c.role, Some(Role::Superadmin));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn imports_a_tokens_file() {
        let dir = temp("import");
        let path = dir.join(FILE);
        let file = dir.join("tokens");
        std::fs::write(
            &file,
            format!(
                "# old\n{} partner me\n{} contributor list\n{} partner me\n{} observer\n",
                hash("t1"),
                hash("t2"),
                hash("t3"),
                hash("t4")
            ),
        )
        .unwrap();
        let created = import_tokens_file(&path, &file).unwrap();
        assert_eq!(created.len(), 4);
        assert!(created.contains(&"me-2".to_string()), "{created:?}");
        let server = Participants::open(&dir).unwrap();
        assert_eq!(
            server.caller(Some("Bearer t2")).unwrap().unwrap().tier,
            Tier::Contributor
        );
        assert_eq!(server.active_tokens().unwrap(), 4);
        std::fs::remove_dir_all(&dir).ok();
    }

    fn identity(sub: &str, email: &str, verified: bool) -> Identity {
        Identity {
            issuer: "https://sso.example".into(),
            subject: sub.into(),
            email: Some(email.into()),
            email_verified: verified,
        }
    }

    fn sso_setup(name: &str) -> (PathBuf, PathBuf) {
        let dir = temp(name);
        let path = dir.join(FILE);
        add_organisation(&path, "lab", Tier::Partner, "cyber_partner", None, None).unwrap();
        add_organisation(&path, "core", Tier::Core, "cyber_partner", None, None).unwrap();
        (dir, path)
    }

    #[test]
    fn first_sign_in_provisions_a_human_without_a_role() {
        let (dir, path) = sso_setup("sso-provision");
        let id = identity("00u1", "Alice@Lab271.dev", false);
        let (name, how) = sign_in(&path, &id, "lab").unwrap().unwrap();
        assert_eq!(
            (name.as_str(), how),
            ("alice@lab271.dev", SignedIn::Provisioned)
        );
        let u = users(&path).unwrap();
        assert_eq!(u.len(), 1);
        assert_eq!(
            (u[0].kind.as_str(), u[0].role, u[0].organisation.as_str()),
            ("human", None, "lab")
        );
        // The second sign-in finds the same user, even with a new e-mail.
        let id = identity("00u1", "alice.new@lab271.dev", false);
        let (name, how) = sign_in(&path, &id, "lab").unwrap().unwrap();
        assert_eq!((name.as_str(), how), ("alice@lab271.dev", SignedIn::Known));
        assert_eq!(users(&path).unwrap().len(), 1);
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn a_verified_email_links_an_existing_human_and_keeps_its_role() {
        let (dir, path) = sso_setup("sso-link");
        add_user(
            &path,
            "core",
            "ops@lab271.dev",
            "human",
            Some(Role::Superadmin),
        )
        .unwrap();
        let e = sign_in(&path, &identity("00u2", "ops@lab271.dev", false), "lab")
            .unwrap()
            .unwrap_err();
        assert!(e.contains("not verified"), "{e}");
        let (name, how) = sign_in(&path, &identity("00u2", "ops@lab271.dev", true), "lab")
            .unwrap()
            .unwrap();
        assert_eq!((name.as_str(), how), ("ops@lab271.dev", SignedIn::Linked));
        let u = users(&path).unwrap();
        assert_eq!(
            (u[0].role, u[0].organisation.as_str()),
            (Some(Role::Superadmin), "core")
        );
        // Another identity with the same e-mail cannot take the user over.
        let e = sign_in(&path, &identity("00u3", "ops@lab271.dev", true), "lab")
            .unwrap()
            .unwrap_err();
        assert!(e.contains("another identity"), "{e}");
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn machines_disabled_users_and_bad_names_are_refused() {
        let (dir, path) = sso_setup("sso-refuse");
        add_user(&path, "lab", "feed@lab271.dev", "machine", None).unwrap();
        let e = sign_in(&path, &identity("m", "feed@lab271.dev", true), "lab")
            .unwrap()
            .unwrap_err();
        assert!(e.contains("machine"), "{e}");
        sign_in(&path, &identity("b", "bob@lab271.dev", true), "lab")
            .unwrap()
            .unwrap();
        set_disabled(&path, "bob@lab271.dev", true).unwrap();
        let e = sign_in(&path, &identity("b", "bob@lab271.dev", true), "lab")
            .unwrap()
            .unwrap_err();
        assert!(e.contains("disabled"), "{e}");
        let e = sign_in(&path, &identity("x", "not an e-mail", true), "lab")
            .unwrap()
            .unwrap_err();
        assert!(e.contains("not a valid user name"), "{e}");
        let mut no_email = identity("y", "", true);
        no_email.email = None;
        let e = sign_in(&path, &no_email, "lab").unwrap().unwrap_err();
        assert!(e.contains("no email"), "{e}");
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn sessions_name_their_user_until_they_end() {
        let (dir, path) = sso_setup("sso-session");
        let server = Participants::open(&dir).unwrap();
        sign_in(&path, &identity("c", "carol@lab271.dev", true), "lab")
            .unwrap()
            .unwrap();
        let value = add_session(&path, "carol@lab271.dev").unwrap();
        assert_eq!(value.len(), 64);
        let now = now_s();
        let c = server.session_caller(&value, now).unwrap().unwrap();
        assert_eq!(
            (c.user.as_str(), c.tier),
            ("carol@lab271.dev", Tier::Partner)
        );
        // Not a bearer token, and expired after SESSION_SECONDS.
        assert_eq!(
            server.caller(Some(&format!("Bearer {value}"))).unwrap(),
            None
        );
        assert_eq!(
            server
                .session_caller(&value, now + SESSION_SECONDS + 1)
                .unwrap(),
            None
        );
        assert_eq!(server.session_caller("nope", now).unwrap(), None);
        // Disabling stops it; enabling brings it back, as with tokens.
        set_disabled(&path, "carol@lab271.dev", true).unwrap();
        assert_eq!(server.session_caller(&value, now).unwrap(), None);
        assert!(add_session(&path, "carol@lab271.dev").is_err());
        set_disabled(&path, "carol@lab271.dev", false).unwrap();
        assert!(server.session_caller(&value, now).unwrap().is_some());
        assert!(end_session(&path, &value).unwrap());
        assert!(!end_session(&path, &value).unwrap());
        assert_eq!(server.session_caller(&value, now).unwrap(), None);
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn machine_users_get_no_session_and_removal_clears_sso_rows() {
        let (dir, path) = sso_setup("sso-remove");
        add_user(&path, "lab", "feed", "machine", None).unwrap();
        assert!(add_session(&path, "feed").is_err());
        sign_in(&path, &identity("d", "dan@lab271.dev", true), "lab")
            .unwrap()
            .unwrap();
        add_session(&path, "dan@lab271.dev").unwrap();
        set_disabled(&path, "dan@lab271.dev", true).unwrap();
        remove_user(&path, "dan@lab271.dev").unwrap();
        // Signing in again provisions a fresh user: the old link is gone.
        let (_, how) = sign_in(&path, &identity("d", "dan@lab271.dev", true), "lab")
            .unwrap()
            .unwrap();
        assert_eq!(how, SignedIn::Provisioned);
        let _ = std::fs::remove_dir_all(dir);
    }
}
