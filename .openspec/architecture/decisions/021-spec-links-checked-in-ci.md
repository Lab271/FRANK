# ADR-021: Spec links are checked in CI

- **Status:** Accepted
- **Date:** 2026-11-10
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-016](016-phase3-rust-on-db-core.md), [ADR-018](018-container-is-the-reference-and-test-tiers.md), #247, #248, #249, #250

## Context

When Phase 3 replaced the Python service (ADR-016), the specs and ADRs did not follow. A review on 2026-11-10 found 196 of 300 internal links in `.openspec/`, `docs/` and the README dead: specs marked Implemented pointed at `src/frank/*.py`, ADRs linked each other under an old 4-digit numbering, and ADRs that ADR-016 superseded still read Accepted. Nothing noticed: `.openspec/validate.py` checked headers only, and its workflow watched `openspec/**/*.spec.md`, a path that does not exist, so it never ran. Only spec 011 linked to the Rust code, one requirement at a time, and all its links resolved.

## Decision

1. **Specs link per requirement and per scenario.** A requirement carries `**Implementation:**` before its first scenario, a scenario carries `**Tests:**`. A link is `path` or `path::symbol`, backtick-quoted; for a `.rs` file the symbol must be a `fn` in it. `(planned)` marks work not done and is not counted. The format is in [.openspec/README.md](../../README.md); spec 011 is the model.
2. **`scripts/assurance.py` checks every link** (Python 3, standard library only, like `scripts/smoke.py`): spec links against the tree, and every relative Markdown link in `.openspec/`, `docs/`, `README.md` and `CONTRIBUTING.md`. It scores per spec how many requirements are implemented and how many scenarios are tested; a dead link subtracts a tested scenario, because a stale link is a false claim of coverage.
3. **`make check-assurance` is a CI job** and fails on any dead link or when tested scenarios fall below `ASSURANCE_MIN` (0 to start; raised as #250 adds specs). `make assurance` is the dashboard, `V=1` per requirement. It replaces `.openspec/validate.py` and `spec-validation.yml`.
4. **A spec whose status starts with `Outdated` is skipped**, so a spec awaiting its rewrite (001–004, #250) does not block the gate while it still says what it says.
5. **Phase 2 documents leave the tree** rather than going to an archive folder: the tag `phase2-final` keeps them, and an archive would be one more place for the checker to skip and readers to trip over (#248).

## Consequences

- Renaming a function or test that a spec names fails CI until the spec follows. That is the intent.
- The checker proves that a link resolves, not that the test checks what the scenario says; that stays a review question.
- Superseded ADRs keep their text as history, but their Markdown links must resolve, so links to removed code became plain text (#249).
- Evidence: `scripts/assurance.py`, `scripts/test_assurance.py`, `Makefile` targets `assurance` and `check-assurance`, the `specs` job in `.github/workflows/ci.yml`.
