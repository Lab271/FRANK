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

## Fuzzing and dependencies

`make fuzz` runs the `parse` target in `fuzz/` (its own workspace, on
nightly: `cargo install cargo-fuzz`) against `frank_core::formats::parse`,
the parser behind `/v1/submissions` and `/v1/preview`, seeded from
`examples/`. A crash input lands in `fuzz/artifacts/parse/`; turn it into
a unit test in `frank-core` with the fix. `make audit` runs `cargo deny`
with `deny.toml`; an accepted advisory goes in its `ignore` list, with
the reason. CI runs both.
