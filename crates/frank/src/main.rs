//! `frank`: the FRANK Phase 3 server and its admin commands.

use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use clap::{Parser, Subcommand};
use frank::api::{self, App};
use frank::store::participants::{self as parts, FILE as PARTICIPANTS};
use frank::store::registry::{self, Registry};
use frank::store::{Iocs, Participants, Sightings};
use frank_core::{Submission, Tier};
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
    /// Data directory: `sightings/` (Parquet), `iocs.db`, `participants.db`.
    #[arg(long, env = "FRANK_DATA", default_value = "./data", global = true)]
    data: PathBuf,
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
    /// Load submissions (JSON files, each one or an array) with the server stopped.
    Ingest {
        files: Vec<PathBuf>,
        /// The participant they are stored under.
        #[arg(long = "as", value_name = "PARTICIPANT")]
        participant: String,
        /// Register the participant as a contributor if it is missing.
        #[arg(long)]
        create: bool,
    },
    /// Rebuild `iocs.db` from the sightings, with the server stopped.
    RebuildIocs,
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
    },
}

#[derive(Subcommand)]
enum TokenCmd {
    /// Create a token for a user; prints it once.
    New { user: String },
    /// List the tokens (hash prefixes, never the tokens).
    List,
    /// Revoke the token whose hash starts with PREFIX (see `list`).
    Revoke { prefix: String },
}

fn status(s: &str) -> Result<Tier, String> {
    Tier::parse(s).ok_or_else(|| "status: observer, contributor, partner or core".to_string())
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
        .init();
    let cli = Cli::parse();
    std::fs::create_dir_all(&cli.data).map_err(|e| format!("{}: {e}", cli.data.display()))?;
    let db = cli.data.join(PARTICIPANTS);
    match cli.command {
        Command::Participant(cmd) => participant(&db, cmd),
        Command::User(UserCmd::Add {
            participant,
            name,
            machine,
        }) => {
            parts::add_user(
                &db,
                &participant,
                &name,
                if machine { "machine" } else { "human" },
            )?;
            eprintln!("added user {name:?} to {participant:?}; create a token with `frank token new {name}`");
            Ok(())
        }
        Command::Token(TokenCmd::New { user }) => {
            println!("{}", parts::add_token(&db, &user)?);
            eprintln!("added a token for {user:?}; it is shown once");
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
                Err(_) if create => parts::add_organisation(
                    &db,
                    &participant,
                    Tier::Contributor,
                    "cyber_partner",
                    None,
                    None,
                )?,
                Err(e) => return Err(format!("{e} (register it, or pass --create)")),
            };
            ingest(&cli.data, &files, &id)
        }
        Command::RebuildIocs => {
            let (s, i) = open(&cli.data, None)?;
            let n = api::rebuild_iocs(&s, &i)?;
            s.close().map_err(|e| e.to_string())?;
            eprintln!("rebuilt iocs from {n} sighting rows");
            Ok(())
        }
        Command::Serve {
            listen,
            tokens,
            web,
            retention_days,
        } => {
            let participants = Participants::open(&cli.data)?;
            if participants.active_tokens()? == 0 && tokens.exists() {
                let created = parts::import_tokens_file(&db, &tokens)?;
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
            let (sightings, iocs) = open(&cli.data, Some(retention_days))?;
            let app = Arc::new(App {
                sightings,
                iocs,
                participants,
                registry: Registry::open(&cli.data)?,
                submit_lock: std::sync::Mutex::new(()),
                now: now_ns,
            });
            tokio::runtime::Runtime::new()
                .map_err(|e| e.to_string())?
                .block_on(serve(app, listen, web, retention_days))
        }
    }
}

fn open(data: &Path, retention_days: Option<u32>) -> Result<(Sightings, Iocs), String> {
    std::fs::create_dir_all(data).map_err(|e| format!("{}: {e}", data.display()))?;
    let sightings =
        Sightings::open(data, retention_days, now_ns).map_err(|e| format!("sightings: {e}"))?;
    let iocs = Iocs::open(data).map_err(|e| format!("iocs: {e}"))?;
    Ok((sightings, iocs))
}

fn participant(db: &Path, cmd: ParticipantCmd) -> Result<(), String> {
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
            eprintln!("registered {name:?} ({st}) as {id}");
            if with_token {
                parts::add_user(db, &name, &name, "human")?;
                println!("{}", parts::add_token(db, &name)?);
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
fn ingest(data: &Path, files: &[PathBuf], reporter: &str) -> Result<(), String> {
    let (s, i) = open(data, None)?;
    let reg = Registry::open(data)?;
    let (mut created, mut duplicates) = (0, 0);
    for f in files {
        let text = std::fs::read_to_string(f).map_err(|e| format!("{}: {e}", f.display()))?;
        let v: serde_json::Value =
            serde_json::from_str(&text).map_err(|e| format!("{}: {e}", f.display()))?;
        let items = match v {
            serde_json::Value::Array(a) => a,
            v => vec![v],
        };
        let mut subs = Vec::with_capacity(items.len());
        for item in &items {
            let sub = Submission::from_value(item, now_ns())
                .map_err(|e| format!("{}: {e}", f.display()))?;
            let digest = registry::digest(&sub);
            let id = sub
                .sighting_id
                .clone()
                .unwrap_or_else(|| registry::derived_id(&digest));
            subs.push((id, digest, sub));
        }
        let known = reg.find(reporter, subs.iter().map(|(id, _, _)| id.clone()).collect())?;
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
        let mut fresh = Vec::new();
        for (id, digest, sub) in subs {
            if known.contains_key(&id) || fresh.iter().any(|(f, _)| *f == id) {
                duplicates += 1;
                continue;
            }
            rows.extend(sub.rows(&id).into_iter().map(|mut r| {
                r.reporter = reporter.to_string();
                r
            }));
            fresh.push((id, digest));
        }
        created += fresh.len();
        if !fresh.is_empty() {
            s.append(&rows).map_err(|e| e.to_string())?;
            i.record(&rows)?;
            reg.register(reporter, "ingest", fresh, now_ns())?;
        }
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
            let flushed = app.sightings.flush().map_err(|e| e.to_string())?;
            if flushed > 0 {
                tracing::info!(files = flushed, "flushed closed hours");
            }
            if n % 60 == 1 {
                let merged = app.sightings.compact().map_err(|e| e.to_string())?;
                let keep_from = now_ns().div_euclid(DAY_NS) - i64::from(retention_days);
                app.iocs.retain_from(keep_from)?;
                app.registry.retain_from(keep_from)?;
                tracing::info!(files = merged, keep_from_day = keep_from, "compacted");
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
