//! The access log (#287): one line per request under the target
//! `frank::access`, apart from the application's own lines (`frank`).
//!
//! A line has the request id, method, path with its query string, status,
//! latency and the caller (`user@organisation`, `public`, or `unknown` when
//! no token or session was resolved) with its tier. Never logged: the
//! `Authorization` header, the session cookie, a token, a body, or the query
//! of the SSO callback (its one-time code).

use std::cell::RefCell;
use std::time::Instant;

use axum::extract::Request;
use axum::http::HeaderValue;
use axum::middleware::Next;
use axum::response::Response;
use frank_core::Tier;
use tracing::Instrument;
use tracing_subscriber::fmt::MakeWriter;
use tracing_subscriber::EnvFilter;

use crate::auth::Caller;

/// The response header that carries the request id.
pub const REQUEST_ID: &str = "x-request-id";

tokio::task_local! {
    /// The caller `api::require` resolved for the request in progress.
    static CALLER: RefCell<Option<(String, Tier)>>;
}

/// Notes the caller for the access line; outside a request, nothing.
pub(crate) fn record(caller: &Caller) {
    let _ = CALLER.try_with(|c| *c.borrow_mut() = Some((caller.label(), caller.tier)));
}

/// The middleware: a request id (also returned as `X-Request-Id` and on the
/// span of the application's lines), then one `frank::access` line.
pub async fn log(req: Request, next: Next) -> Response {
    let start = Instant::now();
    let id = ulid();
    let method = req.method().clone();
    let uri = match req.uri().path() {
        "/v1/sso/callback" => req.uri().path().to_string(),
        _ => req.uri().to_string(),
    };
    let span = tracing::info_span!(target: "frank", "request", request_id = %id);
    let (mut res, caller) = CALLER
        .scope(RefCell::new(None), async {
            let res = next.run(req).instrument(span).await;
            (res, CALLER.with(RefCell::take))
        })
        .await;
    let (caller, tier) = caller.map_or(("unknown".to_string(), "-".to_string()), |(c, t)| {
        (c, t.to_string())
    });
    tracing::info!(
        target: "frank::access",
        request_id = %id,
        method = %method,
        uri = %uri,
        status = res.status().as_u16(),
        latency_ms = u64::try_from(start.elapsed().as_millis()).unwrap_or(u64::MAX),
        caller = %caller,
        tier = %tier,
    );
    if let Ok(v) = HeaderValue::from_str(&id) {
        res.headers_mut().insert(REQUEST_ID, v);
    }
    res
}

/// A ULID: 48 bits of milliseconds and 80 random bits, Crockford base32,
/// so ids sort by time.
#[must_use]
pub fn ulid() -> String {
    const ALPHABET: &[u8; 32] = b"0123456789ABCDEFGHJKMNPQRSTVWXYZ";
    let ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        & ((1 << 48) - 1);
    let mut r = [0u8; 16];
    r[6..].copy_from_slice(&crate::auth::random::<10>().unwrap_or_default());
    let v = (ms << 80) | u128::from_be_bytes(r);
    (0..26)
        .map(|i| char::from(ALPHABET[((v >> (125 - 5 * i)) & 31) as usize]))
        .collect()
}

/// The log subscriber: plain text, or with `json` one JSON object per line
/// with `target` and the fields at the top level (`FRANK_LOG_FORMAT=json`).
pub fn subscriber<W>(
    json: bool,
    ansi: bool,
    filter: EnvFilter,
    writer: W,
) -> Box<dyn tracing::Subscriber + Send + Sync>
where
    W: for<'a> MakeWriter<'a> + Send + Sync + 'static,
{
    let fmt = tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_writer(writer);
    if json {
        Box::new(fmt.json().flatten_event(true).finish())
    } else {
        Box::new(fmt.with_ansi(ansi).finish())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ulids_are_26_crockford_characters_and_differ() {
        let (a, b) = (ulid(), ulid());
        assert_eq!(a.len(), 26);
        assert!(a
            .bytes()
            .all(|c| c.is_ascii_digit() || c.is_ascii_uppercase()));
        assert!(!a.contains(['I', 'L', 'O', 'U']));
        assert_ne!(a, b);
    }
}
