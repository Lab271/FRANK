//! `frank serve` (#300): the HTTP server and its maintenance loop.

use std::future::Future;
use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use serde_json::json;
use tower_http::services::ServeDir;
use tower_http::set_header::SetResponseHeaderLayer;

use crate::api::{self, App};
use crate::cli::{now_ns, open, Ctx, ServeArgs};
use crate::store::participants as parts;
use crate::store::registry::Registry;
use crate::store::Participants;

const DAY_NS: i64 = 86_400 * 1_000_000_000;

/// Opens everything the server needs and runs it until SIGINT or SIGTERM.
pub fn start(ctx: &Ctx, args: ServeArgs) -> Result<(), String> {
    start_until(ctx, args, shutdown())
}

/// [`start`], until `stop` completes instead of a signal: tests stop it.
pub fn start_until(
    ctx: &Ctx,
    args: ServeArgs,
    stop: impl Future<Output = ()> + Send + 'static,
) -> Result<(), String> {
    let sso = sso_config(ctx, &args)?;
    let limits = limits(&args)?;
    let participants = Participants::open(&ctx.participants)?;
    import_tokens(ctx, &participants, &args.tokens)?;
    let (sightings, iocs) = open(&ctx.data, ctx.store.as_deref(), Some(args.retention_days))?;
    let app = Arc::new(App {
        registry: Registry::open(&ctx.data, &sightings)?,
        geo: crate::geo::Geo::open(&ctx.data, now_ns())?,
        lists: crate::lists::Lists::open(&ctx.data)?,
        data: ctx.data.clone(),
        sightings,
        iocs,
        participants,
        audit: ctx.audit.clone(),
        sso: sso.map(|c| crate::sso::Sso::new(c, Arc::new(crate::sso::Ureq::new()))),
        submit_lock: std::sync::Mutex::new(()),
        now: now_ns,
    });
    tokio::runtime::Runtime::new()
        .map_err(|e| e.to_string())?
        .block_on(serve(
            app,
            args.listen,
            args.web,
            args.retention_days,
            limits,
            stop,
        ))
}

/// Sign in with SSO when all five settings are given; its organisation must exist.
fn sso_config(ctx: &Ctx, args: &ServeArgs) -> Result<Option<crate::sso::Config>, String> {
    let sso = crate::sso::Config::from_settings(crate::sso::Settings {
        issuer: args.sso_issuer.clone(),
        client_id: args.sso_client_id.clone(),
        client_secret_file: args.sso_client_secret_file.clone(),
        redirect_url: args.sso_redirect_url.clone(),
        organisation: args.sso_organisation.clone(),
    })?;
    if let Some(sso) = &sso {
        parts::organisation_id(&ctx.db, &sso.organisation)
            .map_err(|e| format!("FRANK_SSO_ORGANISATION: {e}"))?;
        tracing::info!(
            issuer = %sso.issuer,
            client_id = %sso.client_id,
            organisation = %sso.organisation,
            "sign in with SSO is on"
        );
    }
    Ok(sso)
}

/// `--request-timeout` and `--max-concurrency` (#244).
pub fn limits(args: &ServeArgs) -> Result<api::Limits, String> {
    if args.request_timeout == 0 || args.max_concurrency == 0 {
        return Err("--request-timeout and --max-concurrency must be at least 1".into());
    }
    Ok(api::Limits {
        timeout: Duration::from_secs(args.request_timeout),
        concurrency: args.max_concurrency,
    })
}

/// A Phase 3 tokens file, imported once while `participants.db` holds no
/// tokens; a warning when there are still none.
fn import_tokens(ctx: &Ctx, participants: &Participants, tokens: &Path) -> Result<(), String> {
    if participants.active_tokens()? == 0 && tokens.exists() {
        let created = parts::import_tokens_file(&ctx.db, tokens)?;
        ctx.log(
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
    Ok(())
}

async fn serve(
    app: api::Shared,
    listen: SocketAddr,
    web: PathBuf,
    retention_days: u32,
    limits: api::Limits,
    stop: impl Future<Output = ()> + Send + 'static,
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
        );
    // Outermost, so a 503 from the time limit is logged too (#287).
    let router = api::harden(router, limits).layer(axum::middleware::from_fn(crate::access::log));
    let listener = tokio::net::TcpListener::bind(listen)
        .await
        .map_err(|e| format!("{listen}: {e}"))?;
    tracing::info!(
        "listening on http://{listen}, web UI from {}",
        web.display()
    );
    axum::serve(listener, router)
        .with_graceful_shutdown(stop)
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
            // The first tick comes at once: after flushing and compacting
            // what the downtime left, fill the read cache so the first
            // caller does not pay the cold GETs (#291). Never fatal.
            if n == 1 {
                let started = std::time::Instant::now();
                match app.sightings.warm() {
                    Ok(Some(files)) => {
                        let ms = started.elapsed().as_millis();
                        tracing::info!(files, ms, "read cache warmed");
                    }
                    Ok(None) => {}
                    Err(e) => tracing::warn!("read cache warm-up: {e}"),
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

#[cfg(test)]
#[allow(non_snake_case)] // mcdc__<id>__v<N>_<what> (ADR-025)
mod tests {
    use super::*;
    use crate::cli::{setup, Cli, Command};
    use clap::Parser;
    use frank_core::Tier;

    fn serve_args(extra: &[&str]) -> ServeArgs {
        let cli = Cli::try_parse_from([["frank", "serve"].as_slice(), extra].concat()).unwrap();
        match cli.command {
            Command::Serve(a) => a,
            _ => unreachable!(),
        }
    }

    // `args.request_timeout == 0 || args.max_concurrency == 0`: both at least 1.
    #[test]
    fn mcdc__serve_limits_cb1ba987__v1_both_set_is_accepted() {
        let l = limits(&serve_args(&[
            "--request-timeout",
            "5",
            "--max-concurrency",
            "2",
        ]))
        .unwrap();
        assert_eq!((l.timeout, l.concurrency), (Duration::from_secs(5), 2));
    }

    #[test]
    fn mcdc__serve_limits_cb1ba987__v2_no_timeout_is_refused() {
        assert!(limits(&serve_args(&[
            "--request-timeout",
            "0",
            "--max-concurrency",
            "2"
        ]))
        .is_err());
    }

    #[test]
    fn mcdc__serve_limits_cb1ba987__v3_no_concurrency_is_refused() {
        assert!(limits(&serve_args(&[
            "--request-timeout",
            "5",
            "--max-concurrency",
            "0"
        ]))
        .is_err());
    }

    /// A context in a fresh directory, with `existing` tokens in
    /// `participants.db` and a tokens file of one token if `file`; the
    /// active tokens after [`import_tokens`].
    fn tokens_after_import(label: &str, existing: bool, file: bool) -> usize {
        let dir = std::env::temp_dir().join(format!("frank-serve-{label}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let (data, people) = (dir.join("data"), dir.join("participants"));
        let cli = Cli::try_parse_from([
            "frank",
            "--data",
            data.to_str().unwrap(),
            "--participants",
            people.to_str().unwrap(),
            "rebuild",
        ])
        .unwrap();
        let ctx = setup(&cli).unwrap();
        if existing {
            parts::add_organisation(&ctx.db, "ops", Tier::Core, "cyber_partner", None, None)
                .unwrap();
            parts::add_user(&ctx.db, "ops", "root", "human", None).unwrap();
            parts::add_token(&ctx.db, "root").unwrap();
        }
        let tokens = dir.join("tokens");
        if file {
            std::fs::write(&tokens, format!("{} partner me\n", crate::auth::hash("t1"))).unwrap();
        }
        let participants = Participants::open(&ctx.participants).unwrap();
        import_tokens(&ctx, &participants, &tokens).unwrap();
        let n = participants.active_tokens().unwrap();
        std::fs::remove_dir_all(&dir).ok();
        n
    }

    // `participants.active_tokens()? == 0 && tokens.exists()`: imported once.
    #[test]
    fn mcdc__serve_import_tokens_400d7164__v1_no_tokens_and_a_file_imports_it() {
        assert_eq!(tokens_after_import("v1", false, true), 1);
    }

    #[test]
    fn mcdc__serve_import_tokens_400d7164__v2_tokens_already_skip_the_file() {
        assert_eq!(tokens_after_import("v2", true, true), 1);
    }

    #[test]
    fn mcdc__serve_import_tokens_400d7164__v3_no_file_imports_nothing() {
        assert_eq!(tokens_after_import("v3", false, false), 0);
    }
}
