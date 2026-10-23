//! Participants (#159, ADR-016): organisations with one status, their
//! users, and the users' tokens, in `<data>/participants.db`.
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
//! indexes.

use std::collections::HashMap;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::RwLock;
use std::time::SystemTime;

use db_core::engine::row::RowEngine;
use frank_core::{sql_quote, Tier};
use serde::Serialize;

use super::rowdb::{exec, int, open_engine, query, text, transaction};
use crate::auth::{hash, hex, random, uuid4, Caller};

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

/// One token, without the token itself.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TokenInfo {
    /// The first 12 hex digits of the token's SHA-256.
    pub prefix: String,
    pub user: String,
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
}

/// What tells a changed file apart: size, modification time and the
/// SQLite header's change counter (bytes 24-27).
type Stamp = (u64, SystemTime, [u8; 4]);

impl Participants {
    /// Opens `<data>/participants.db`, creating it if needed.
    pub fn open(data: &Path) -> Result<Participants, String> {
        let path = data.join(FILE);
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
        let by_hash = with_db(&self.path, load_callers)?;
        let mut cache = self
            .cache
            .write()
            .map_err(|_| "participants lock poisoned")?;
        *cache = Cache {
            stamp: Some(stamp),
            by_hash,
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
            SCHEMA.iter().try_for_each(|ddl| exec(db, ddl))
        })?;
    }
    f(&mut db)
}

fn load_callers(db: &mut RowEngine) -> Result<HashMap<String, Caller>, String> {
    let orgs: HashMap<String, (String, Tier)> =
        query(db, "SELECT id, name, status FROM organisations")?
            .rows
            .iter()
            .filter_map(|r| Some((text(&r[0]), (text(&r[1]), Tier::parse(&text(&r[2]))?))))
            .collect();
    let users: HashMap<String, (String, String)> =
        query(db, "SELECT id, organisation, name FROM users")?
            .rows
            .iter()
            .map(|r| (text(&r[0]), (text(&r[1]), text(&r[2]))))
            .collect();
    let mut by_hash = HashMap::new();
    for r in query(db, "SELECT hash, user FROM tokens WHERE revoked IS NULL")?.rows {
        let Some((org, user)) = users.get(&text(&r[1])) else {
            continue;
        };
        let Some((name, status)) = orgs.get(org) else {
            continue;
        };
        by_hash.insert(
            text(&r[0]),
            Caller {
                tier: *status,
                participant: org.clone(),
                organisation: name.clone(),
                user: user.clone(),
            },
        );
    }
    Ok(by_hash)
}

// --- administration: one call opens, changes and closes the file ---------

/// A name: 1-64 characters of `[A-Za-z0-9._@-]`, so it is safe in logs,
/// on the command line and in SQL.
fn check_name(what: &str, name: &str) -> Result<(), String> {
    let ok = !name.is_empty()
        && name.len() <= 64
        && name
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"._@-".contains(&b));
    if ok {
        Ok(())
    } else {
        Err(format!(
            "{what} {name:?}: use 1-64 letters, digits, '.', '_', '@' or '-'"
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
/// request.
pub fn set_status(path: &Path, name_or_id: &str, status: Tier) -> Result<(), String> {
    with_db(path, |db| {
        let (id, _) = find_org(db, name_or_id)?;
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

/// Adds a user (`human` or `machine`) to an organisation.
pub fn add_user(path: &Path, organisation: &str, name: &str, kind: &str) -> Result<(), String> {
    check_name("user", name)?;
    if !USER_KINDS.contains(&kind) {
        return Err(format!("user kind {kind:?}: human or machine"));
    }
    with_db(path, |db| {
        let (org, _) = find_org(db, organisation)?;
        if find_user(db, name).is_ok() {
            return Err(format!("user {name:?} exists"));
        }
        exec(
            db,
            &format!(
                "INSERT INTO users (id, organisation, name, kind, created) VALUES ({}, {}, {}, {}, {})",
                sql_quote(&uuid4()?),
                sql_quote(&org),
                sql_quote(name),
                sql_quote(kind),
                now_s()
            ),
        )
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
        let user = find_user(db, user)?;
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
        add_user(path, &name, &name, "human")?;
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
        add_user(&path, "acme-mdr", "alice", "human").unwrap();
        add_user(&path, "acme-mdr", "acme-feed", "machine").unwrap();
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
        add_user(&path, "lab", "bob", "human").unwrap();
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
        add_user(&path, "lab", "u1", "human").unwrap();
        assert!(
            add_user(&path, "lab", "u1", "human").is_err(),
            "user names are unique"
        );
        assert!(add_user(&path, "nope", "u2", "human").is_err());
        assert!(add_user(&path, "lab", "u3", "robot").is_err());
        let orgs = organisations(&path).unwrap();
        assert_eq!(orgs.len(), 1);
        assert_eq!(orgs[0].users, ["u1"]);
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
}
