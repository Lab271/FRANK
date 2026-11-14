//! `frank`: the FRANK Phase 3 server and its admin commands. The commands
//! live in `frank::cli` and the server in `frank::serve` (#300), where the
//! tests reach them.

use std::io::IsTerminal;

use clap::Parser;
use frank::cli::{self, Cli, Io};
use tracing_subscriber::util::SubscriberInitExt;

fn main() -> Result<(), String> {
    // Colours only on a terminal: a container's log keeps plain text.
    frank::access::subscriber(
        std::env::var("FRANK_LOG_FORMAT").is_ok_and(|f| f == "json"),
        std::io::stdout().is_terminal(),
        tracing_subscriber::EnvFilter::try_from_default_env()
            .unwrap_or_else(|_| "frank=info".into()),
        std::io::stdout,
    )
    .init();
    let (mut out, mut err) = (std::io::stdout(), std::io::stderr());
    cli::run(
        Cli::parse(),
        &mut Io {
            out: &mut out,
            err: &mut err,
        },
    )
}
