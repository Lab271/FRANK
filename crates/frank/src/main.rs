//! `frank`: the FRANK Phase 3 server and its admin commands.

use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use clap::{Parser, Subcommand};
use frank::api::{self, App};
use frank::auth::{add_token, Tokens};
use frank::store::{Iocs, Sightings};
use frank_core::{Submission, Tier};
use tower_http::services::ServeDir;
use tower_http::trace::TraceLayer;

const DAY_NS: i64 = 86_400 * 1_000_000_000;

#[derive(Parser)]
#[command(version, about = "FRANK: anonymised threat-sighting sharing")]
struct Cli {
    /// Data directory: `sightings/` (Parquet) and `iocs.db`.
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
        /// Tokens file (`<sha256> <tier> <label>` per line).
        #[arg(long, env = "FRANK_TOKENS", default_value = "./tokens")]
        tokens: PathBuf,
        /// Directory with the web UI (index.html, pkg/).
        #[arg(long, env = "FRANK_WEB", default_value = "./web")]
        web: PathBuf,
        /// Closed days kept; older days are dropped whole.
        #[arg(long, env = "FRANK_RETENTION_DAYS", default_value_t = 400)]
        retention_days: u32,
    },
    /// Create a token for a tier; prints it once.
    Token {
        tier: String,
        label: String,
        #[arg(long, env = "FRANK_TOKENS", default_value = "./tokens")]
        tokens: PathBuf,
    },
    /// Load submissions (JSON files, each one or an array) with the server stopped.
    Ingest { files: Vec<PathBuf> },
    /// Rebuild `iocs.db` from the sightings, with the server stopped.
    RebuildIocs,
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
    match cli.command {
        Command::Token {
            tier,
            label,
            tokens,
        } => {
            let tier =
                Tier::parse(&tier).ok_or("tier: public, observer, contributor, partner or core")?;
            println!("{}", add_token(&tokens, tier, &label)?);
            eprintln!("added a {tier} token for {label:?} to {}", tokens.display());
            Ok(())
        }
        Command::Ingest { files } => ingest(&cli.data, &files),
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
            let tokens = Tokens::load(&tokens)?;
            if tokens.is_empty() {
                tracing::warn!(
                    "no tokens: only public statistics are available (create one with `frank token`)"
                );
            }
            let (sightings, iocs) = open(&cli.data, Some(retention_days))?;
            let app = Arc::new(App {
                sightings,
                iocs,
                tokens,
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

fn ingest(data: &Path, files: &[PathBuf]) -> Result<(), String> {
    let (s, i) = open(data, None)?;
    let mut total = 0;
    for f in files {
        let text = std::fs::read_to_string(f).map_err(|e| format!("{}: {e}", f.display()))?;
        let v: serde_json::Value =
            serde_json::from_str(&text).map_err(|e| format!("{}: {e}", f.display()))?;
        let items = match v {
            serde_json::Value::Array(a) => a,
            v => vec![v],
        };
        let mut rows = Vec::new();
        for item in &items {
            let sub = Submission::from_value(item, now_ns())
                .map_err(|e| format!("{}: {e}", f.display()))?;
            rows.extend(sub.rows(&api::new_sighting_id()?));
        }
        s.append(&rows).map_err(|e| e.to_string())?;
        i.record(&rows)?;
        total += items.len();
    }
    s.flush().map_err(|e| e.to_string())?;
    s.close().map_err(|e| e.to_string())?;
    eprintln!("ingested {total} submissions");
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
        .fallback_service(ServeDir::new(&web))
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
