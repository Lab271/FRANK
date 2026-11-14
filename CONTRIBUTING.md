# Contributing

Thanks for investing your time in this project!

Contributions are governed by the [License](LICENSE), and
participation by the [Code of Conduct](CODE_OF_CONDUCT.md).

This repository is private and internal to Schuberg Philis.
Treat its contents as SBP confidential.

## Qualified subset

`frank-core` (the pure model) is held to the qualified Rust subset by
`make check-mvl-limit`, which `make lint` and CI run: no `unsafe`, `dyn`,
explicit lifetimes or macros outside the curated allowlist. Install the
checker with
`cargo install --git https://github.com/mvl-lang/mvl-rust rust-limit --bin cargo-mvl-limit`
(CI pins `MVL_RUST_REV` in `.github/workflows/ci.yml`).

The `frank` server crate and `frank-wasm` are exempt: they are I/O
boundaries built on `axum`, `tracing`, `json!` and callbacks. Only
production code is checked: each file is cut at its first `#[cfg(test)]`,
so keep the test module last in the file.

## MC/DC

Every decision of two or more conditions (`a && b`, `a || !b` in an `if`,
`while` or match guard) needs a test per vector, n + 1 for n conditions,
each showing one condition change the outcome on its own
([ADR-025](.openspec/architecture/decisions/025-mcdc-with-tagged-tests.md)).
The tests are named `mcdc__<id>__v<N>_<what>`, with the id from
`tests/mcdc/obligations.json`, in the module's test module (it carries
`#[allow(non_snake_case)]`). `make test-mcdc VERBOSE=1` lists the tests
still missing.

After changing or moving a decision, run `make mcdc-obligations` and
commit the snapshot with the change: CI fails a stale one
(`check-mcdc-fresh`), and a test whose decision changed no longer counts
until it is renamed to the new id. Keep `&&` and `||` out of conditions in
test code; they are scanned too. Install the scanner with
`cargo install --locked --git https://github.com/mvl-lang/mvl-rust --rev 5a5ffd5a8e79298271a65649b3f586ebce2ffb31 rust-mcdc --bin cargo-mvl-mcdc`
(CI pins it as `MVL_MCDC_REV`).

## Fuzzing and dependencies

`make fuzz` runs the `parse` target in `fuzz/` (its own workspace, on
nightly: `cargo install cargo-fuzz`) against `frank_core::formats::parse`,
the parser behind `/v1/submissions` and `/v1/preview`, seeded from
`examples/`. A crash input lands in `fuzz/artifacts/parse/`; turn it into
a unit test in `frank-core` with the fix. `make audit` runs `cargo deny`
with `deny.toml`; an accepted advisory goes in its `ignore` list, with
the reason. CI runs both.
