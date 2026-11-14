# ADR-023: Coverage and code quality next to spec assurance

- **Status:** Accepted
- **Date:** 2026-11-14
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-021](021-spec-links-checked-in-ci.md), [spec 002](../../specs/002-assurance/spec.md), #293, #294

## Context

`make check-assurance` (ADR-021) proves that every requirement links to code and every scenario to a test that exists. It says nothing about how much of the code the tests run, or how hard the code is to read. Measuring coverage builds the workspace instrumented and runs every test, minutes rather than the second the spec check takes; folding it into `check-assurance` would make that slow, and CI already runs the tests once.

[lizard](https://github.com/terryyin/lizard) (Python, run through `uvx`) reads Rust: per function the cyclomatic complexity (CCN), lines, tokens and parameters. Its `-Eio` extension adds fan-in and fan-out, but matches calls by bare function name across the scan, so every function called `new` or `path` shares the callers of all of them, and any variable of that name counts too. Its nesting-depth extensions return 0 for Rust.

## Decision

1. **Each measurement runs on its own and leaves a file.** `make coverage` runs `cargo llvm-cov --summary-only --json` into `target/assurance/coverage.json`; `make quality` runs lizard (pinned, `-l rust -Eio --csv crates/*/src`) into `target/assurance/lizard.csv`. `target/` is not committed: the numbers belong to a build, not to the tree.
2. **`scripts/assurance.py` reads them** (`scripts/coverage_metrics.py`, `scripts/quality_metrics.py`, standard library only) and shows a coverage box and a code-quality box after the spec box, with how long ago each was measured. A missing file shows `not measured`, not a failure, so `check-assurance` stays fast and works in CI as before.
3. **Gates on request.** `COVERAGE_MIN` (lines, 0.0–1.0) and `CCN_MAX` make `check-assurance` fail below or above them, and when the measurement is missing. Unset, they are shown against display limits (80% lines, CCN 15, 80 lines a function) and never fail.
4. **Fan-in and fan-out are shown as approximate and never gated**, for the name matching above. Tests are not scanned: they would swamp it.

## Consequences

- The dashboard can show numbers from an older tree; the age next to each box says so. Run `make coverage quality` before reading them.
- Without `COVERAGE_MIN` or `CCN_MAX`, nothing stops coverage or complexity from getting worse; setting them, in the Makefile or in CI, is a later decision once the numbers have settled. On 2026-11-14: 90% of lines, 18 functions over CCN 15 (`main.rs::main` 77).
- `crates/frank/src/main.rs` shows 0%: the integration tests call the library, not the binary.
- Evidence: `scripts/coverage_metrics.py`, `scripts/quality_metrics.py` and their tests, `scripts/test_assurance.py::Gates`, `Makefile` targets `coverage`, `quality` and `check-assurance`.
