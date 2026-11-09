//! `frank`: the FRANK Phase 3 server and its admin commands.

use std::io::IsTerminal;
use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use clap::{Parser, Subcommand};
use db_core::storage::ingest::IngestError;
use frank::api::{self, App};
use frank::audit::{self, Audit};
use frank::auth::{hash, Role};
use frank::store::participants::{self as parts, FILE as PARTICIPANTS};
use frank::store::registry::{self, Registry};
use frank::store::{Iocs, Participants, Sightings};
use frank_core::{Format, Tier};
use serde_json::json;
use tower_http::services::ServeDir;
use tower_http::set_header::SetResponseHeaderLayer;
use tower_http::trace::TraceLayer;

const DAY_NS: i64 = 86_400 * 1_000_000_000;

#[derive(Parser)]
#[command(
    version,
    about = "FRANK: threat-sighting sharing between known participants"
)]
struct Cli {
    /// Data directory: `sightings/` (Parquet), `iocs.db`.
    #[arg(long, env = "FRANK_DATA", default_value = "./data", global = true)]
    data: PathBuf,
    /// Directory of `participants.db` (organisations, users, tokens): apart
    /// from the data, so wiping the data keeps the participants.
    #[arg(
        long,
        env = "FRANK_PARTICIPANTS",
        default_value = "./participants",
        global = true
    )]
    participants: PathBuf,
    /// Where the sightings' Parquet files live, when not under the data
    /// directory: `s3://bucket/prefix?endpoint=URL&region=NAME` (#220). The
    /// WAL stays in `<data>/s3/sightings`. Credentials come from
    /// `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, or the AWS shared
    /// credentials file.
    #[arg(long, env = "FRANK_STORE", global = true)]
    store: Option<String>,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Run the HTTP server.
    Serve {
        #[arg(long, env = "FRANK_LISTEN", default_value = "127.0.0.1:8080")]
        listen: SocketAddr,
        /// A Phase 3 tokens file (`<sha256> <tier> <label>` lines), imported
        /// once into `participants.db` while that holds no tokens yet.
        #[arg(long, env = "FRANK_TOKENS", default_value = "./tokens")]
        tokens: PathBuf,
        /// Directory with the web UI (index.html, pkg/).
        #[arg(long, env = "FRANK_WEB", default_value = "./web")]
        web: PathBuf,
        /// Closed days kept; older days are dropped whole.
        #[arg(long, env = "FRANK_RETENTION_DAYS", default_value_t = 400)]
        retention_days: u32,
    },
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

#[derive(Subcommand)]
enum ParticipantCmd {
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
enum UserCmd {
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
enum TokenCmd {
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

fn now_ns() -> i64 {
    let d = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    i64::try_from(d.as_nanos()).unwrap_or(i64::MAX)
}

fn main() -> Result<(), String> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "frank=info,tower_http=info".into()),
        )
        // Colours only on a terminal: a container's log keeps plain text.
        .with_ansi(std::io::stdout().is_terminal())
        .init();
    let cli = Cli::parse();
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
    let store = cli
        .store
        .as_deref()
        .map(frank::objects::open)
        .transpose()
        .map_err(|e| format!("FRANK_STORE: {e}"))?;
    let audit = Audit::open_in(&cli.data, store)?;
    let log = |action: &str, fields: serde_json::Value| {
        audit.record(now_ns(), &audit::cli_user(), action, fields)
    };
    match cli.command {
        Command::Participant(cmd) => participant(&db, cmd, &log),
        Command::User(UserCmd::Add {
            participant,
            name,
            machine,
            role: r,
        }) => {
            let kind = if machine { "machine" } else { "human" };
            let r = r.as_deref().map(role).transpose()?.flatten();
            parts::add_user(&db, &participant, &name, kind, r)?;
            log(
                "user_added",
                json!({ "participant": parts::organisation_id(&db, &participant)?, "user": name, "kind": kind, "role": r }),
            )?;
            eprintln!("added user {name:?} to {participant:?}; create a token with `frank token new {name}`");
            Ok(())
        }
        Command::User(UserCmd::List) => {
            for u in parts::users(&db)? {
                let r = u.role.map_or("", Role::as_str);
                let state = if u.disabled { "disabled" } else { "" };
                println!(
                    "{:<24} {:<8} {:<11} {:<9} {}",
                    u.name, u.kind, r, state, u.organisation
                );
            }
            Ok(())
        }
        Command::User(UserCmd::Disable { name }) => {
            parts::set_disabled(&db, &name, true)?;
            log("user_disabled", json!({ "user": name }))?;
            eprintln!("disabled {name:?}; its tokens stop working on the next request");
            Ok(())
        }
        Command::User(UserCmd::Enable { name }) => {
            parts::set_disabled(&db, &name, false)?;
            log("user_enabled", json!({ "user": name }))?;
            eprintln!("enabled {name:?}");
            Ok(())
        }
        Command::User(UserCmd::Remove { name }) => {
            let tokens = parts::remove_user(&db, &name)?;
            log("user_removed", json!({ "user": name, "tokens": tokens }))?;
            eprintln!("removed {name:?} and {} token(s)", tokens.len());
            Ok(())
        }
        Command::User(UserCmd::SetRole { name, role: r }) => {
            let r = role(&r)?;
            parts::set_role(&db, &name, r)?;
            log("role_set", json!({ "user": name, "role": r }))?;
            eprintln!(
                "{name:?} is {}; from the next request",
                r.map_or("no admin", Role::as_str)
            );
            Ok(())
        }
        Command::Token(TokenCmd::New { user }) => {
            let token = parts::add_token(&db, &user)?;
            log(
                "token_issued",
                json!({ "user": user, "token": &hash(&token)[..12] }),
            )?;
            println!("{token}");
            eprintln!("added a token for {user:?}; it is shown once");
            Ok(())
        }
        Command::Token(TokenCmd::Add { user, hash: h }) => {
            parts::add_token_hash(&db, &user, &h)?;
            let prefix = h.to_ascii_lowercase()[..12].to_string();
            log("token_issued", json!({ "user": user, "token": prefix }))?;
            eprintln!("registered token {prefix}… for {user:?}");
            Ok(())
        }
        Command::Token(TokenCmd::List) => {
            for t in parts::tokens(&db)? {
                let state = if t.revoked { "revoked" } else { "active" };
                println!("{}  {:<8} {}@{}", t.prefix, state, t.user, t.organisation);
            }
            Ok(())
        }
        Command::Token(TokenCmd::Revoke { prefix }) => {
            parts::revoke(&db, &prefix)?;
            log(
                "token_revoked",
                json!({ "token": prefix.to_ascii_lowercase() }),
            )?;
            eprintln!("revoked {prefix}…");
            Ok(())
        }
        Command::Ingest {
            files,
            participant,
            create,
        } => {
            let id = match parts::organisation_id(&db, &participant) {
                Ok(id) => id,
                Err(_) if create => {
                    let id = parts::add_organisation(
                        &db,
                        &participant,
                        Tier::Contributor,
                        "cyber_partner",
                        None,
                        None,
                    )?;
                    log(
                        "participant_added",
                        json!({ "participant": id, "name": participant, "status": Tier::Contributor.as_str() }),
                    )?;
                    id
                }
                Err(e) => return Err(format!("{e} (register it, or pass --create)")),
            };
            ingest(&cli.data, cli.store.as_deref(), &files, &id, &audit)
        }
        Command::Rebuild => {
            let (s, i) = open(&cli.data, cli.store.as_deref(), None)?;
            let n = api::rebuild_iocs(&s, &i)?;
            let r = Registry::open(&cli.data, &s)?.rebuild(&s)?;
            let g = frank::geo::Geo::open(&cli.data, now_ns())?.backfill(&s, now_ns())?;
            s.close().map_err(|e| e.to_string())?;
            eprintln!(
                "rebuilt iocs from {n} sighting rows, the registry with {r} registrations, ip_geo with {g} addresses"
            );
            Ok(())
        }
        Command::Serve {
            listen,
            tokens,
            web,
            retention_days,
        } => {
            let participants = Participants::open(&cli.participants)?;
            if participants.active_tokens()? == 0 && tokens.exists() {
                let created = parts::import_tokens_file(&db, &tokens)?;
                log(
                    "tokens_imported",
                    json!({ "file": tokens.display().to_string(), "organisations": created }),
                )?;
                tracing::warn!(
                    organisations = ?created,
                    "imported {} as one organisation per token; merge the ones that are one \
                     organisation, then delete the file",
                    tokens.display()
                );
            }
            if participants.active_tokens()? == 0 {
                tracing::warn!(
                    "no tokens: only public statistics are available \
                     (`frank participant add NAME --status partner --with-token`)"
                );
            }
            let (sightings, iocs) = open(&cli.data, cli.store.as_deref(), Some(retention_days))?;
            let registry = Registry::open(&cli.data, &sightings)?;
            let geo = frank::geo::Geo::open(&cli.data, now_ns())?;
            let lists = frank::lists::Lists::open(&cli.data)?;
            let app = Arc::new(App {
                data: cli.data.clone(),
                sightings,
                iocs,
                geo,
                lists,
                participants,
                registry,
                audit: audit.clone(),
                submit_lock: std::sync::Mutex::new(()),
                now: now_ns,
            });
            tokio::runtime::Runtime::new()
                .map_err(|e| e.to_string())?
                .block_on(serve(app, listen, web, retention_days))
        }
    }
}

fn open(
    data: &Path,
    location: Option<&str>,
    retention_days: Option<u32>,
) -> Result<(Sightings, Iocs), String> {
    std::fs::create_dir_all(data).map_err(|e| format!("{}: {e}", data.display()))?;
    let store = location
        .map(frank::objects::open)
        .transpose()
        .map_err(|e| format!("FRANK_STORE: {e}"))?;
    let sightings =
        Sightings::open_in(data, store, retention_days, now_ns).map_err(|e| match e {
            // 0.13 added `digest` and `received`; `Sightings::open` refuses a
            // table without them.
            IngestError::SchemaMismatch => format!(
                "{}: written by FRANK 0.12 or older (no digest column, pseudonymous \
             reporters): move it aside and reload the sightings",
                data.join(frank::store::sightings::NAME).display()
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

fn participant(
    db: &Path,
    cmd: ParticipantCmd,
    log: &dyn Fn(&str, serde_json::Value) -> Result<(), String>,
) -> Result<(), String> {
    match cmd {
        ParticipantCmd::Add {
            name,
            status: st,
            kind,
            sector,
            region,
            with_token,
        } => {
            let st = status(&st)?;
            let id = parts::add_organisation(
                db,
                &name,
                st,
                &kind,
                sector.as_deref(),
                region.as_deref(),
            )?;
            log(
                "participant_added",
                json!({ "participant": id, "name": name, "status": st.as_str(), "type": kind }),
            )?;
            eprintln!("registered {name:?} ({st}) as {id}");
            if with_token {
                parts::add_user(db, &name, &name, "human", None)?;
                log(
                    "user_added",
                    json!({ "participant": id, "user": name, "kind": "human" }),
                )?;
                let token = parts::add_token(db, &name)?;
                log(
                    "token_issued",
                    json!({ "user": name, "token": &hash(&token)[..12] }),
                )?;
                println!("{token}");
                eprintln!("added user {name:?} and a token for it; the token is shown once");
            }
            Ok(())
        }
        ParticipantCmd::List => {
            for o in parts::organisations(db)? {
                println!(
                    "{:<24} {:<11} {:<13} {}  users: {}",
                    o.name,
                    o.status.as_str(),
                    o.kind,
                    o.id,
                    o.users.join(", ")
                );
            }
            Ok(())
        }
        ParticipantCmd::SetStatus { name, status: st } => {
            let st = status(&st)?;
            parts::set_status(db, &name, st)?;
            log(
                "status_set",
                json!({ "participant": parts::organisation_id(db, &name)?, "status": st.as_str() }),
            )?;
            eprintln!("{name:?} is now {st}");
            Ok(())
        }
    }
}

/// Loads files with the server stopped, stored under `reporter` (a
/// participant id) and registered like a POST from user `ingest`: a
/// sighting without an id gets one derived from its content, so loading a
/// file twice adds nothing. A file with a conflicting sighting is refused
/// whole.
fn ingest(
    data: &Path,
    store: Option<&str>,
    files: &[PathBuf],
    reporter: &str,
    audit: &Audit,
) -> Result<(), String> {
    let (s, i) = open(data, store, None)?;
    let reg = Registry::open(data, &s)?;
    let (mut created, mut duplicates) = (0, 0);
    for f in files {
        let text = std::fs::read_to_string(f).map_err(|e| format!("{}: {e}", f.display()))?;
        let sightings = frank_core::formats::parse(&text, Format::sniff(&text), now_ns())
            .map_err(|e| format!("{}: {e}", f.display()))?;
        let mut subs = Vec::with_capacity(sightings.len());
        for sub in sightings {
            let digest = registry::digest(&sub);
            let id = sub
                .sighting_id
                .unwrap_or_else(|| registry::derived_id(&digest));
            subs.push((id, digest, sub));
        }
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
        created += fresh.len();
        if !fresh.is_empty() {
            s.append(&rows).map_err(|e| e.to_string())?;
            i.record(&rows)?;
            reg.register(fresh)?;
        }
        audit.record(
            now,
            &audit::cli_user(),
            "ingest",
            json!({ "participant": reporter, "file": f.display().to_string(), "receipts": seen }),
        )?;
    }
    s.flush().map_err(|e| e.to_string())?;
    s.close().map_err(|e| e.to_string())?;
    eprintln!("ingested {created} sightings ({duplicates} already registered)");
    Ok(())
}

async fn serve(
    app: api::Shared,
    listen: SocketAddr,
    web: PathBuf,
    retention_days: u32,
) -> Result<(), String> {
    let maintenance = tokio::spawn(maintain(app.clone(), retention_days));
    let router = api::router(app.clone())
        // The UI and its WASM module change with every build: browsers
        // revalidate them (Last-Modified) instead of reusing a stale copy.
        .fallback_service(
            axum::Router::new()
                .fallback_service(ServeDir::new(&web))
                .layer(SetResponseHeaderLayer::if_not_present(
                    axum::http::header::CACHE_CONTROL,
                    axum::http::HeaderValue::from_static("no-cache"),
                )),
        )
        .layer(TraceLayer::new_for_http());
    let listener = tokio::net::TcpListener::bind(listen)
        .await
        .map_err(|e| format!("{listen}: {e}"))?;
    tracing::info!(
        "listening on http://{listen}, web UI from {}",
        web.display()
    );
    axum::serve(listener, router)
        .with_graceful_shutdown(shutdown())
        .await
        .map_err(|e| e.to_string())?;
    maintenance.abort();
    let s = app.sightings.clone();
    tokio::task::spawn_blocking(move || {
        let _ = s.flush();
        s.close()
    })
    .await
    .map_err(|e| e.to_string())?
    .map_err(|e| e.to_string())?;
    tracing::info!("stopped");
    Ok(())
}

/// Flushes closed hours every minute; merges closed days and applies
/// retention to both stores every hour.
async fn maintain(app: api::Shared, retention_days: u32) {
    let mut tick = tokio::time::interval(Duration::from_secs(60));
    let mut n: u64 = 0;
    loop {
        tick.tick().await;
        n += 1;
        let app = app.clone();
        let result = tokio::task::spawn_blocking(move || -> Result<(), String> {
            // DB-IP databases picked up when it appears or changes (#191); its
            // errors never stop the rest of the maintenance.
            app.geo.refresh(now_ns());
            app.lists.refresh(now_ns());
            if let Err(e) = app.geo.backfill(&app.sightings, now_ns()) {
                tracing::warn!("ip_geo backfill: {e}");
            }
            let flushed = app.sightings.flush().map_err(|e| e.to_string())?;
            if flushed > 0 {
                tracing::info!(files = flushed, "flushed closed hours");
            }
            if n % 60 == 1 {
                let merged = app.sightings.compact().map_err(|e| e.to_string())?;
                let keep_from = now_ns().div_euclid(DAY_NS) - i64::from(retention_days);
                app.iocs.retain_from(keep_from)?;
                app.registry.retain_from(keep_from)?;
                app.audit.retain_from(keep_from)?;
                if merged > 0 {
                    tracing::info!(files = merged, keep_from_day = keep_from, "compacted");
                }
            }
            Ok(())
        })
        .await;
        match result {
            Ok(Ok(())) => {}
            Ok(Err(e)) => tracing::error!("maintenance: {e}"),
            Err(e) => tracing::error!("maintenance task: {e}"),
        }
    }
}

async fn shutdown() {
    let ctrl_c = async {
        let _ = tokio::signal::ctrl_c().await;
    };
    #[cfg(unix)]
    let term = async {
        if let Ok(mut s) = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        {
            s.recv().await;
        }
    };
    #[cfg(not(unix))]
    let term = std::future::pending::<()>();
    tokio::select! { () = ctrl_c => {}, () = term => {} }
}
