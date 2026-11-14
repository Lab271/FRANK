# ADR-025: MC/DC with tagged tests, as in db-core

- **Status:** Accepted
- **Date:** 2026-11-14
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-023](023-coverage-and-code-quality-next-to-spec-assurance.md), [spec 002](../../specs/002-assurance/spec.md), #317

## Context

Line coverage (ADR-023, 90% in CI) says a line ran, not that each condition of a decision mattered. FRANK's decisions of two or more conditions are mostly access rules: who may add a superadmin (`admin.rs`), which cells are suppressed below partner (`api.rs`), which tokens and labels are refused (`store/participants.rs`), which identity provider answers are accepted (`sso.rs`). A test that passes with one condition removed would not notice it gone.

rustc's own MC/DC instrumentation is nightly-only. db-core measures MC/DC on stable with `cargo-mvl-mcdc` (mvl-rust's `rust-mcdc`): a `syn` scan lists every decision as an obligation, and tests named `mcdc__<id>__v<N>_<what>` cover its vectors (n conditions need n + 1). On 2026-11-14 FRANK had 534 decisions: 158 exhaustive matches (the compiler covers them), 328 of one condition (branch coverage, which llvm-cov already counts) and 48 of two or more, with 148 vectors.

## Decision

1. **db-core's setup, unchanged in kind.** `make mcdc-obligations` writes `tests/mcdc/obligations.json` from all of `crates/*/src`, no file left out, and it is committed; `make check-mcdc-fresh` fails when it differs from a fresh scan. The id is `<module>_<fn>_<hash of the decision>`, so moving a decision changes only the snapshot's line; changing it changes the id.
2. **Decisions of two or more conditions are the gate.** `make test-mcdc` runs `cargo-mvl-mcdc harvest`, narrowed by a cargo shim to the `mcdc__` tests of the workspace with `frank/tls`, writes `target/assurance/mcdc.json`, and fails while one of them lacks a passing test for a vector. Decisions of one condition are left to llvm-cov; exhaustive matches to the compiler. CI runs it on every push.
3. **The tests are ordinary tests.** They sit in the module's test module (`#[allow(non_snake_case)]` there, for the double underscores), run under `make test` and count toward line coverage. A test's own loops and `if`s are scanned too, so test code keeps `&&` and `||` out of conditions.
4. **Bookkeeping under a plain `cargo test`.** `crates/frank/tests/mcdc_discharge.rs` fails when a tagged test names an id the snapshot lacks (the decision changed and the test no longer counts) and when two files share an id (both `lib.rs` have the slug `lib`). It reads the snapshot, so it needs no tool installed.
5. **Shown next to coverage and quality.** `check-assurance` shows a MC/DC box from `mcdc.json` (`not measured` without it) and fails below `MCDC_MIN` when that is set.
6. **The scanner is pinned.** The snapshot depends on the scanner's id scheme, so CI installs `cargo-mvl-mcdc` at db-core's mvl-rust revision (`MVL_MCDC_REV`), and the Makefile prints the same install line.

## Consequences

- A change to a decision of two or more conditions needs its vectors, and a change to any decision a new snapshot (`make mcdc-obligations`), in the same PR. CONTRIBUTING says how.
- `test-mcdc` builds the tests once more outside llvm-cov in CI: about a minute.
- The tagged tests prove each condition can change the outcome, not that the outcome is right; they assert what the decision controls, as any test.
- `objects.rs`'s fake S3 server read until the headers and the body had arrived; it now waits only for the body, which comes last, so a test helper no longer adds a decision of its own.
