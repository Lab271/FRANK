//! The `frank` command line (#300): the subcommands as functions that write
//! to the streams they are given, so tests can run them. `main.rs` only
//! parses the arguments and calls [`run`]; the server is in [`crate::serve`].

use std::fmt::Display;
use std::io::Write;
use std::net::SocketAddr;
use std::path::{Path, PathBuf};

use clap::{Args, Parser, Subcommand};
use db_core::storage::ingest::IngestError;
use frank_core::{Digest, Format, Sighting, SightingId, Tier};
use serde_json::json;

use crate::api;
use crate::audit::{self, Audit};
use crate::auth::{hash, Role};
use crate::store::participants::{self as parts, FILE as PARTICIPANTS};
use crate::store::registry::{self, Registry};
use crate::store::{Iocs, Sightings};

#[derive(Parser)]
#[command(
    name = "frank",
    version,
    about = "FRANK: threat-sighting sharing between known participants"
)]
pub struct Cli {
    /// Data directory: `sightings/` (Parquet), `iocs.db`.
    #[arg(long, env = "FRANK_DATA", default_value = "./data", global = true)]
    pub data: PathBuf,
    /// Directory of `participants.db` (organisations, users, tokens): apart
    /// from the data, so wiping the data keeps the participants.
    #[arg(
        long,
        env = "FRANK_PARTICIPANTS",
        default_value = "./participants",
        global = true
    )]
    pub participants: PathBuf,
    /// Where the sightings' Parquet files live, when not under the data
    /// directory: `s3://bucket/prefix?endpoint=URL&region=NAME` (#220). The
    /// WAL stays in `<data>/s3/sightings`. Credentials come from
    /// `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, the AWS shared
    /// credentials file, an ECS task role or the EC2 instance role.
    #[arg(long, env = "FRANK_STORE", global = true)]
    pub store: Option<String>,
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand)]
pub enum Command {
    /// Run the HTTP server.
    Serve(ServeArgs),
    /// Organisations: add, list, set their status.
    #[command(subcommand)]
    Participant(ParticipantCmd),
    /// Users of an organisation.
    #[command(subcommand)]
    User(UserCmd),
    /// Users' bearer tokens.
    #[command(subcommand)]
    Token(TokenCmd),
    /// Load sightings with the server stopped: JSON or YAML files (one or a
    /// list each) or STIX 2.1 bundles.
    Ingest {
        files: Vec<PathBuf>,
        /// The participant they are stored under.
        #[arg(long = "as", value_name = "PARTICIPANT")]
        participant: String,
        /// Register the participant as a contributor if it is missing.
        #[arg(long)]
        create: bool,
    },
    /// Rebuild `iocs.db` and `registry.db` from the sightings, with the
    /// server stopped.
    #[command(alias = "rebuild-iocs")]
    Rebuild,
}

#[derive(Args)]
pub struct ServeArgs {
    #[arg(long, env = "FRANK_LISTEN", default_value = "127.0.0.1:8080")]
    pub listen: SocketAddr,
    /// A Phase 3 tokens file (`<sha256> <tier> <label>` lines), imported
    /// once into `participants.db` while that holds no tokens yet.
    #[arg(long, env = "FRANK_TOKENS", default_value = "./tokens")]
    pub tokens: PathBuf,
    /// Directory with the web UI (index.html, pkg/).
    #[arg(long, env = "FRANK_WEB", default_value = "./web")]
    pub web: PathBuf,
    /// Closed days kept; older days are dropped whole.
    #[arg(long, env = "FRANK_RETENTION_DAYS", default_value_t = 400)]
    pub retention_days: u32,
    /// Sign in with OpenID Connect (#241, ADR-020): the issuer, e.g.
    /// `https://<org>.okta.com/oauth2/default`. SSO is off unless all
    /// five `--sso-*` settings are given.
    #[arg(long, env = "FRANK_SSO_ISSUER")]
    pub sso_issuer: Option<String>,
    /// The OIDC client id.
    #[arg(long, env = "FRANK_SSO_CLIENT_ID")]
    pub sso_client_id: Option<String>,
    /// A file holding the OIDC client secret: the secret itself is
    /// never taken from the command line or the environment.
    #[arg(long, env = "FRANK_SSO_CLIENT_SECRET_FILE")]
    pub sso_client_secret_file: Option<PathBuf>,
    /// FRANK's public callback, e.g.
    /// `https://frank.example/v1/sso/callback`.
    #[arg(long, env = "FRANK_SSO_REDIRECT_URL")]
    pub sso_redirect_url: Option<String>,
    /// The organisation users signing in for the first time are
    /// created in, with no role.
    #[arg(long, env = "FRANK_SSO_ORGANISATION")]
    pub sso_organisation: Option<String>,
    /// Seconds a request may take, waiting included; then 503 (#244).
    #[arg(long, env = "FRANK_REQUEST_TIMEOUT", default_value_t = 60)]
    pub request_timeout: u64,
    /// Requests handled at once; the rest wait (#244).
    #[arg(long, env = "FRANK_MAX_CONCURRENCY", default_value_t = 64)]
    pub max_concurrency: usize,
}

#[derive(Subcommand)]
pub enum ParticipantCmd {
    /// Register an organisation.
    Add {
        name: String,
        /// observer, contributor, partner or core.
        #[arg(long)]
        status: String,
        /// cyber_partner or customer.
        #[arg(long = "type", default_value = "cyber_partner")]
        kind: String,
        #[arg(long)]
        sector: Option<String>,
        #[arg(long)]
        region: Option<String>,
        /// Also add a user of the same name and print a token for it.
        #[arg(long)]
        with_token: bool,
    },
    /// List the organisations, their status and users.
    List,
    /// Change an organisation's status; its users have it on their next request.
    SetStatus { name: String, status: String },
}

#[derive(Subcommand)]
pub enum UserCmd {
    /// Add a user to an organisation.
    Add {
        participant: String,
        name: String,
        /// A machine identity (an API client) rather than a person.
        #[arg(long)]
        machine: bool,
        /// admin (its own organisation's users and tokens) or superadmin
        /// (every organisation; core only). People only.
        #[arg(long)]
        role: Option<String>,
    },
    /// List the users, their kind and role.
    List,
    /// Give a user a role: admin, superadmin, or none to take it away.
    SetRole { name: String, role: String },
    /// Disable a user: its tokens stop working until it is enabled.
    Disable { name: String },
    /// Enable a disabled user again.
    Enable { name: String },
    /// Remove a disabled user with its role and tokens.
    Remove { name: String },
}

#[derive(Subcommand)]
pub enum TokenCmd {
    /// Create a token for a user; prints it once.
    New { user: String },
    /// Register a token made elsewhere by its SHA-256 (64 hex digits);
    /// FRANK never sees the token itself.
    Add {
        user: String,
        #[arg(long)]
        hash: String,
    },
    /// List the tokens (hash prefixes, never the tokens).
    List,
    /// Revoke the token whose hash starts with PREFIX (see `list`).
    Revoke { prefix: String },
}

/// What every subcommand works on, from the global options.
pub struct Ctx {
    pub data: PathBuf,
    pub participants: PathBuf,
    /// `<participants>/participants.db`.
    pub db: PathBuf,
    pub store: Option<String>,
    pub audit: Audit,
}

impl Ctx {
    /// An audit line by the operating-system user running the command.
    pub fn log(&self, action: &str, fields: serde_json::Value) -> Result<(), String> {
        self.audit
            .record(now_ns(), &audit::cli_user(), action, fields)
    }
}

/// The streams a command writes to: results on `out`, notes on `err`.
pub struct Io<'a> {
    pub out: &'a mut dyn Write,
    pub err: &'a mut dyn Write,
}

impl Io<'_> {
    fn out(&mut self, line: impl Display) -> Result<(), String> {
        writeln!(self.out, "{line}").map_err(|e| e.to_string())
    }

    fn err(&mut self, line: impl Display) -> Result<(), String> {
        writeln!(self.err, "{line}").map_err(|e| e.to_string())
    }
}

pub fn now_ns() -> i64 {
    let d = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    i64::try_from(d.as_nanos()).unwrap_or(i64::MAX)
}

fn status(s: &str) -> Result<Tier, String> {
    Tier::parse(s).ok_or_else(|| "status: observer, contributor, partner or core".to_string())
}

/// `none` is no role.
fn role(s: &str) -> Result<Option<Role>, String> {
    if s.eq_ignore_ascii_case("none") {
        return Ok(None);
    }
    Role::parse(s)
        .map(Some)
        .ok_or_else(|| "role: admin, superadmin or none".to_string())
}

/// Runs a parsed command line.
pub fn run(cli: Cli, io: &mut Io) -> Result<(), String> {
    let ctx = setup(&cli)?;
    match cli.command {
        Command::Serve(args) => crate::serve::start(&ctx, args),
        Command::Participant(cmd) => participant(&ctx, cmd, io),
        Command::User(cmd) => user(&ctx, cmd, io),
        Command::Token(cmd) => token(&ctx, cmd, io),
        Command::Ingest {
            files,
            participant,
            create,
        } => ingest_as(&ctx, &files, &participant, create, io),
        Command::Rebuild => rebuild(&ctx, io),
    }
}

/// The directories, `participants.db` where it belongs, the store and the
/// audit log.
pub fn setup(cli: &Cli) -> Result<Ctx, String> {
    for dir in [&cli.data, &cli.participants] {
        std::fs::create_dir_all(dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    }
    let db = cli.participants.join(PARTICIPANTS);
    let old = cli.data.join(PARTICIPANTS);
    if old.exists() && !db.exists() {
        return Err(format!(
            "{} moved out of the data directory: mv {}* {}/",
            old.display(),
            old.display(),
            cli.participants.display()
        ));
    }
    let store = open_store(cli.store.as_deref())?;
    Ok(Ctx {
        audit: Audit::open_in(&cli.data, store)?,
        data: cli.data.clone(),
        participants: cli.participants.clone(),
        db,
        store: cli.store.clone(),
    })
}

fn open_store(location: Option<&str>) -> Result<Option<db_core::storage::ingest::Store>, String> {
    location
        .map(crate::objects::open)
        .transpose()
        .map_err(|e| format!("FRANK_STORE: {e}"))
}

/// The sightings and `iocs.db`, with the sightings in `location` when given.
pub fn open(
    data: &Path,
    location: Option<&str>,
    retention_days: Option<u32>,
) -> Result<(Sightings, Iocs), String> {
    std::fs::create_dir_all(data).map_err(|e| format!("{}: {e}", data.display()))?;
    let store = open_store(location)?;
    let sightings =
        Sightings::open_in(data, store, retention_days, now_ns).map_err(|e| match e {
            // 0.13 added `digest` and `received`; `Sightings::open` refuses a
            // table without them.
            IngestError::SchemaMismatch => format!(
                "{}: written by FRANK 0.12 or older (no digest column, pseudonymous \
             reporters): move it aside and reload the sightings",
                data.join(crate::store::sightings::NAME).display()
            ),
            e => format!("sightings: {e}"),
        })?;
    if let Some(location) = location {
        // No credentials in it: the key comes from the AWS environment, and
        // db-core refuses options it does not know.
        tracing::info!(
            store = location,
            wal = %sightings.dir().display(),
            "sightings in an object store; the WAL, iocs.db and the rest stay on this volume"
        );
    }
    let iocs = Iocs::open(data).map_err(|e| format!("iocs: {e}"))?;
    Ok((sightings, iocs))
}

// Organisations.

fn participant(ctx: &Ctx, cmd: ParticipantCmd, io: &mut Io) -> Result<(), String> {
    match cmd {
        ParticipantCmd::Add {
            name,
            status: st,
            kind,
            sector,
            region,
            with_token,
        } => {
            let id = participant_add(
                ctx,
                &name,
                &st,
                &kind,
                sector.as_deref(),
                region.as_deref(),
                io,
            )?;
            if with_token {
                first_user_with_token(ctx, &id, &name, io)?;
            }
            Ok(())
        }
        ParticipantCmd::List => participant_list(ctx, io),
        ParticipantCmd::SetStatus { name, status: st } => {
            participant_set_status(ctx, &name, &st, io)
        }
    }
}

fn participant_add(
    ctx: &Ctx,
    name: &str,
    st: &str,
    kind: &str,
    sector: Option<&str>,
    region: Option<&str>,
    io: &mut Io,
) -> Result<String, String> {
    let st = status(st)?;
    let id = parts::add_organisation(&ctx.db, name, st, kind, sector, region)?;
    ctx.log(
        "participant_added",
        json!({ "participant": id, "name": name, "status": st.as_str(), "type": kind }),
    )?;
    io.err(format!("registered {name:?} ({st}) as {id}"))?;
    Ok(id)
}

/// `participant add --with-token`: a user of the organisation's name, and a
/// token for it.
fn first_user_with_token(ctx: &Ctx, id: &str, name: &str, io: &mut Io) -> Result<(), String> {
    parts::add_user(&ctx.db, name, name, "human", None)?;
    ctx.log(
        "user_added",
        json!({ "participant": id, "user": name, "kind": "human" }),
    )?;
    let token = parts::add_token(&ctx.db, name)?;
    ctx.log(
        "token_issued",
        json!({ "user": name, "token": &hash(&token)[..12] }),
    )?;
    io.out(&token)?;
    io.err(format!(
        "added user {name:?} and a token for it; the token is shown once"
    ))
}

fn participant_list(ctx: &Ctx, io: &mut Io) -> Result<(), String> {
    for o in parts::organisations(&ctx.db)? {
        io.out(format!(
            "{:<24} {:<11} {:<13} {}  users: {}",
            o.name,
            o.status.as_str(),
            o.kind,
            o.id,
            o.users.join(", ")
        ))?;
    }
    Ok(())
}

fn participant_set_status(ctx: &Ctx, name: &str, st: &str, io: &mut Io) -> Result<(), String> {
    let st = status(st)?;
    parts::set_status(&ctx.db, name, st)?;
    ctx.log(
        "status_set",
        json!({ "participant": parts::organisation_id(&ctx.db, name)?, "status": st.as_str() }),
    )?;
    io.err(format!("{name:?} is now {st}"))
}

// Users.

fn user(ctx: &Ctx, cmd: UserCmd, io: &mut Io) -> Result<(), String> {
    match cmd {
        UserCmd::Add {
            participant,
            name,
            machine,
            role: r,
        } => user_add(ctx, &participant, &name, machine, r.as_deref(), io),
        UserCmd::List => user_list(ctx, io),
        UserCmd::Disable { name } => user_set_disabled(ctx, &name, true, io),
        UserCmd::Enable { name } => user_set_disabled(ctx, &name, false, io),
        UserCmd::Remove { name } => user_remove(ctx, &name, io),
        UserCmd::SetRole { name, role: r } => user_set_role(ctx, &name, &r, io),
    }
}

fn user_add(
    ctx: &Ctx,
    participant: &str,
    name: &str,
    machine: bool,
    r: Option<&str>,
    io: &mut Io,
) -> Result<(), String> {
    let kind = if machine { "machine" } else { "human" };
    let r = r.map(role).transpose()?.flatten();
    parts::add_user(&ctx.db, participant, name, kind, r)?;
    ctx.log(
        "user_added",
        json!({ "participant": parts::organisation_id(&ctx.db, participant)?, "user": name, "kind": kind, "role": r }),
    )?;
    io.err(format!(
        "added user {name:?} to {participant:?}; create a token with `frank token new {name}`"
    ))
}

fn user_list(ctx: &Ctx, io: &mut Io) -> Result<(), String> {
    for u in parts::users(&ctx.db)? {
        let r = u.role.map_or("", Role::as_str);
        let state = if u.disabled { "disabled" } else { "" };
        io.out(format!(
            "{:<24} {:<8} {:<11} {:<9} {}",
            u.name, u.kind, r, state, u.organisation
        ))?;
    }
    Ok(())
}

fn user_set_disabled(ctx: &Ctx, name: &str, disabled: bool, io: &mut Io) -> Result<(), String> {
    parts::set_disabled(&ctx.db, name, disabled)?;
    if disabled {
        ctx.log("user_disabled", json!({ "user": name }))?;
        io.err(format!(
            "disabled {name:?}; its tokens stop working on the next request"
        ))
    } else {
        ctx.log("user_enabled", json!({ "user": name }))?;
        io.err(format!("enabled {name:?}"))
    }
}

fn user_remove(ctx: &Ctx, name: &str, io: &mut Io) -> Result<(), String> {
    let tokens = parts::remove_user(&ctx.db, name)?;
    ctx.log("user_removed", json!({ "user": name, "tokens": tokens }))?;
    io.err(format!("removed {name:?} and {} token(s)", tokens.len()))
}

fn user_set_role(ctx: &Ctx, name: &str, r: &str, io: &mut Io) -> Result<(), String> {
    let r = role(r)?;
    parts::set_role(&ctx.db, name, r)?;
    ctx.log("role_set", json!({ "user": name, "role": r }))?;
    io.err(format!(
        "{name:?} is {}; from the next request",
        r.map_or("no admin", Role::as_str)
    ))
}

// Tokens.

fn token(ctx: &Ctx, cmd: TokenCmd, io: &mut Io) -> Result<(), String> {
    match cmd {
        TokenCmd::New { user } => token_new(ctx, &user, io),
        TokenCmd::Add { user, hash: h } => token_add(ctx, &user, &h, io),
        TokenCmd::List => token_list(ctx, io),
        TokenCmd::Revoke { prefix } => token_revoke(ctx, &prefix, io),
    }
}

fn token_new(ctx: &Ctx, user: &str, io: &mut Io) -> Result<(), String> {
    let token = parts::add_token(&ctx.db, user)?;
    ctx.log(
        "token_issued",
        json!({ "user": user, "token": &hash(&token)[..12] }),
    )?;
    io.out(&token)?;
    io.err(format!("added a token for {user:?}; it is shown once"))
}

fn token_add(ctx: &Ctx, user: &str, h: &str, io: &mut Io) -> Result<(), String> {
    parts::add_token_hash(&ctx.db, user, h)?;
    let prefix = h.to_ascii_lowercase()[..12].to_string();
    ctx.log("token_issued", json!({ "user": user, "token": prefix }))?;
    io.err(format!("registered token {prefix}… for {user:?}"))
}

fn token_list(ctx: &Ctx, io: &mut Io) -> Result<(), String> {
    for t in parts::tokens(&ctx.db)? {
        let state = if t.revoked { "revoked" } else { "active" };
        io.out(format!(
            "{}  {:<8} {}@{}",
            t.prefix, state, t.user, t.organisation
        ))?;
    }
    Ok(())
}

fn token_revoke(ctx: &Ctx, prefix: &str, io: &mut Io) -> Result<(), String> {
    parts::revoke(&ctx.db, prefix)?;
    ctx.log(
        "token_revoked",
        json!({ "token": prefix.to_ascii_lowercase() }),
    )?;
    io.err(format!("revoked {prefix}…"))
}

// Sightings, with the server stopped.

/// `ingest --as PARTICIPANT [--create]`: the participant's id, registering it
/// as a contributor first with `--create`.
fn ingest_as(
    ctx: &Ctx,
    files: &[PathBuf],
    participant: &str,
    create: bool,
    io: &mut Io,
) -> Result<(), String> {
    let id = match parts::organisation_id(&ctx.db, participant) {
        Ok(id) => id,
        Err(_) if create => {
            let id = parts::add_organisation(
                &ctx.db,
                participant,
                Tier::Contributor,
                "cyber_partner",
                None,
                None,
            )?;
            ctx.log(
                "participant_added",
                json!({ "participant": id, "name": participant, "status": Tier::Contributor.as_str() }),
            )?;
            id
        }
        Err(e) => return Err(format!("{e} (register it, or pass --create)")),
    };
    ingest(ctx, files, &id, io)
}

/// Loads files with the server stopped, stored under `reporter` (a
/// participant id) and registered like a POST from user `ingest`: a
/// sighting without an id gets one derived from its content, so loading a
/// file twice adds nothing. A file with a conflicting sighting is refused
/// whole.
fn ingest(ctx: &Ctx, files: &[PathBuf], reporter: &str, io: &mut Io) -> Result<(), String> {
    let (s, i) = open(&ctx.data, ctx.store.as_deref(), None)?;
    let reg = Registry::open(&ctx.data, &s)?;
    let (mut created, mut duplicates) = (0, 0);
    for f in files {
        let (c, d) = ingest_file(ctx, &s, &i, &reg, f, reporter)?;
        created += c;
        duplicates += d;
    }
    s.flush().map_err(|e| e.to_string())?;
    s.close().map_err(|e| e.to_string())?;
    io.err(format!(
        "ingested {created} sightings ({duplicates} already registered)"
    ))
}

/// One file's sightings with their ids and digests.
type Keyed = Vec<(SightingId, Digest, Sighting)>;

fn read_file(f: &Path) -> Result<Keyed, String> {
    let text = std::fs::read_to_string(f).map_err(|e| format!("{}: {e}", f.display()))?;
    let sightings = frank_core::formats::parse(&text, Format::sniff(&text), now_ns())
        .map_err(|e| format!("{}: {e}", f.display()))?;
    Ok(sightings
        .into_iter()
        .map(|sub| {
            let digest = registry::digest(&sub);
            let id = sub
                .sighting_id
                .unwrap_or_else(|| registry::derived_id(&digest));
            (id, digest, sub)
        })
        .collect())
}

/// One file: (created, duplicates).
fn ingest_file(
    ctx: &Ctx,
    s: &Sightings,
    i: &Iocs,
    reg: &Registry,
    f: &Path,
    reporter: &str,
) -> Result<(usize, usize), String> {
    let subs = read_file(f)?;
    let known = reg.find(reporter, subs.iter().map(|(id, _, _)| *id).collect())?;
    if let Some((id, _, _)) = subs
        .iter()
        .find(|(id, d, _)| known.get(id).is_some_and(|(k, _)| k != d))
    {
        return Err(format!(
            "{}: {id} is registered with other content",
            f.display()
        ));
    }
    let mut rows = Vec::new();
    let mut fresh: Vec<registry::Registration> = Vec::new();
    let mut seen = Vec::new();
    let mut duplicates = 0;
    let now = now_ns();
    for (id, digest, sub) in subs {
        if known.contains_key(&id) || fresh.iter().any(|f| f.1 == id) {
            duplicates += 1;
            seen.push(json!({ "sighting_id": id, "digest": digest, "status": "duplicate" }));
            continue;
        }
        seen.push(json!({ "sighting_id": id, "digest": digest, "status": "created" }));
        rows.extend(sub.rows(id).into_iter().map(|mut r| {
            r.reporter = reporter.to_string();
            r.digest = (r.seq == 0).then_some(digest);
            r.received_ns = now;
            r
        }));
        fresh.push((reporter.to_string(), id, digest, now));
    }
    let created = fresh.len();
    if !fresh.is_empty() {
        s.append(&rows).map_err(|e| e.to_string())?;
        i.record(&rows)?;
        reg.register(fresh)?;
    }
    ctx.audit.record(
        now,
        &audit::cli_user(),
        "ingest",
        json!({ "participant": reporter, "file": f.display().to_string(), "receipts": seen }),
    )?;
    Ok((created, duplicates))
}

/// `rebuild`: `iocs.db`, the registry and `ip_geo` from the sightings.
fn rebuild(ctx: &Ctx, io: &mut Io) -> Result<(), String> {
    let (s, i) = open(&ctx.data, ctx.store.as_deref(), None)?;
    let n = api::rebuild_iocs(&s, &i)?;
    let r = Registry::open(&ctx.data, &s)?.rebuild(&s)?;
    let g = crate::geo::Geo::open(&ctx.data, now_ns())?.backfill(&s, now_ns())?;
    s.close().map_err(|e| e.to_string())?;
    io.err(format!(
        "rebuilt iocs from {n} sighting rows, the registry with {r} registrations, ip_geo with {g} addresses"
    ))
}
