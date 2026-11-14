//! `frank`: the FRANK Phase 3 server and its admin commands. The commands
//! live in `frank::cli` and the server in `frank::serve` (#300), where the
//! tests reach them.

use std::io::IsTerminal;

use clap::Parser;
use frank::cli::{self, Cli, Io};

fn main() -> Result<(), String> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "frank=info,tower_http=info".into()),
        )
        // Colours only on a terminal: a container's log keeps plain text.
        .with_ansi(std::io::stdout().is_terminal())
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
