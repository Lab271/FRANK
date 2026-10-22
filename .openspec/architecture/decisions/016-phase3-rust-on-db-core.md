# ADR-016: Phase 3 in Rust on db-core: striped Parquet sightings, a row table for IoCs, a WASM client

- **Status:** accepted
- **Date:** 2026-10-22
- **Decision Makers:** Ilja Heitlager
- **Supersedes:** [ADR-003](003-four-stage-infrastructure-evolution.md) (stages), [ADR-004](004-repository-pattern-database-abstraction.md) (storage backends), [ADR-006](006-cognito-authentication.md) (Cognito)
- **Related:** [ADR-002](002-tiered-access-control.md), [ADR-008](008-forgiving-input-strong-output.md)

## Context

Phase 2 delivered a Python/FastAPI service over SQLite, DynamoDB, PostgreSQL and a planned OpenSearch/ScyllaDB stack, and a demo for RVO (May 2026). Its final state is tagged `phase2-final`; the demo branch is tagged `phase2-demo-may13`. The code moved to `legacy/phase2/`.

Phase 3 is the production build. Three things in the Phase 2 outcome drive the redesign:

1. **The workload is columnar.** FRANK answers "how often was this rule, technique or IoC seen, per sector and over time". Sightings are immutable events. That is a scan-and-aggregate workload over an append-only table, not a document index.
2. **Liability and neutrality of the central party** are the main open governance question in the Phase 2 report, and a DPIA is needed for wider rollout. The less identifying data the platform can hold, the smaller both problems get.
3. **Self-hosting.** Participants must be able to run an installation themselves, on their own machine, in a container, or in an EU cloud.

## Decision

1. **One Rust binary, `frank`,** replaces the Python service. It is the single writer of two stores under one data directory:
   - `sightings/`: a striped (tiered) db-core table. Each closed hour is flushed to `live/` as one Parquet file sorted by `(rule_id, ioc_value)`; closed days merge into `archive/`; retention drops whole days. The files are plain Parquet with hive partitions, so DuckDB and pyarrow read them too.
   - `iocs.db`: a db-core row table (SQLite format), one row per IoC per day with B-tree indexes on the key, the day and the IP address (as 32 hex digits). "Is this IoC known", "when" and "which addresses in this CIDR block" are index seeks, not scans.
2. **Anonymisation by schema.** A submission is reduced to sighting rows (`frank-core::SightingRow`) that have no column for an organisation's identity. Submitter and target identities are dropped at parsing time; sector and size are kept as `[a-z0-9_]` labels only. Public and observer statistics suppress cells under `MIN_CELL` (3).
3. **No SQL from callers.** The HTTP API runs fixed, typed queries. Values reaching SQL are normalised IoCs, quoted by doubling quotes.
4. **The browser runs FRANK code as WebAssembly** (`frank-wasm`, `wasm32-unknown-unknown`):
   - the submission preview runs the server's own parsing, so a contributor sees exactly what will be shared before sending it;
   - partners download the Parquet files (`/v1/files`, listed files only) and query them in the browser on db-core's column engine. Counts, sums, minimums and maximums merge across files.
5. **Tokens instead of Cognito:** a tokens file of `sha256(token) tier label` lines, managed with `frank token`. OIDC can replace it later without changing the tiers.
6. **Three deployments, one image and one on-disk layout:** `frank serve` on a machine; `deploy/podman` (compose, data on a host bind mount); `deploy/stackit` (OpenTofu: a VM running the image with podman, data on a separate block volume, Caddy for TLS).

## Consequences

- **Positive:** a single 6 MB binary and a ~1.5 MB WASM module; no database server to operate; the data is open Parquet; the shared table cannot hold organisation identities; the same code validates in the browser and on the server.
- **Dependency on db-core.** db-core is an Apache-2.0 project maintained by Ilja Heitlager in a personal capacity (t-rust-db), so SBP depends on an engine it does not own. The output format (Parquet) keeps an exit open: DuckDB reads every table. FRANK pins db-core to an exact commit.
- **db-core gaps found and fixed on the way** (t-rust-db/db-core#707, PR #708): opening Parquet from bytes, batch queries without threads, nanosecond timestamp literals, and literal parsing without a clock.
- **db-core gaps still open:**
  - local filesystem only (object storage: db-core#690), so a cloud deployment is a VM with a block volume, not object storage plus stateless containers;
  - one writer per table, so one server process per data directory;
  - row engine: no `ON CONFLICT`, broken implicit PK/UNIQUE indexes, no index use for `AND` predicates (db-core#694-#696); the `iocs` schema works around all three;
  - the `iocs` projection is updated after the sightings append, not in one transaction (db-core#693). `frank rebuild-iocs` rebuilds it from the sightings.
- **Retention bases differ:** `sightings` drops days by arrival time (the table's partitions), `iocs` by event day. A late submission about an old event stays in `sightings` longer than in `iocs`.
- **Lost from Phase 2:** the TUI/admin GUI, the management API, Cognito user management, and per-organisation contribution accounting (reciprocity, #103). These return only as far as Phase 3 needs them, designed against the no-identity schema.
