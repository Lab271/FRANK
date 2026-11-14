# ADR-016: Phase 3 in Rust on db-core: striped Parquet sightings, a row table for IoCs, a WASM client

- **Status:** Accepted, revised 2026-10-23 (participants, #159) and 2026-11-10 (target identities are not stored, #256)
- **Date:** 2026-10-22
- **Decision Makers:** Ilja Heitlager
- **Supersedes:** [ADR-001](001-single-code-library.md) (one Python library), [ADR-003](003-four-stage-infrastructure-evolution.md) (stages), [ADR-004](004-repository-pattern-database-abstraction.md) (storage backends), [ADR-006](006-cognito-authentication.md) (Cognito), [ADR-010](010-postgresql-management-api.md) (PostgreSQL for organisations), [ADR-007](007-admin-mvc-architecture.md) (Python admin TUI), [ADR-011](011-stages-vs-environments.md) (stages vs environments)
- **Related:** [ADR-002](002-tiered-access-control.md), [ADR-008](008-forgiving-input-strong-output.md), [ADR-017](017-user-roles-for-identity-administration.md) (user roles: who may manage identities; users still see by their organisation's status)

## Context

Phase 2 delivered a Python/FastAPI service over SQLite, DynamoDB, PostgreSQL and a planned OpenSearch/ScyllaDB stack, and a demo for RVO (May 2026). Its final state is tagged `phase2-final`; the demo branch is tagged `phase2-demo-may13`. The code moved to `legacy/phase2/`, and left the tree on 2026-10-27; the tags keep it.

Phase 3 is the production build. Three things in the Phase 2 outcome drive the redesign:

1. **The workload is columnar.** FRANK answers "how often was this rule, technique or IoC seen, per sector and over time". Sightings are immutable events. That is a scan-and-aggregate workload over an append-only table, not a document index.
2. **Liability and neutrality of the central party** are the main open governance question in the Phase 2 report, and a DPIA is needed for wider rollout. The first version of this ADR answered it by holding no identities at all; the 2026-10-23 revision answers it with known participants, opaque ids in the shared data and a platform that does not judge what it passes on (see *Revision*).
3. **Self-hosting.** Participants must be able to run an installation themselves, on their own machine, in a container, or in an EU cloud.

## Decision

1. **One Rust binary, `frank`,** replaces the Python service. It is the single writer of two stores under one data directory:
   - `sightings/`: a striped (tiered) db-core table. Each closed hour is flushed to `live/` as one Parquet file sorted by `(rule_id, ioc_value)`; closed days merge into `archive/`; retention drops whole days. The files are plain Parquet with hive partitions, so DuckDB and pyarrow read them too. One row per sighting × IoC; a sighting's techniques are a `LIST<UTF8>` column, `techniques`, ranked with `UNNEST(techniques)` and filtered with `list_contains` (0.21). It replaces the comma-separated `technique` string; db-core can neither drop a column nor fill a new one for stored rows, so 0.21 rewrites a table that has the string once at startup, replaying every row at its arrival time so it keeps its hour and day (the old table is kept as `sightings.pre-list/`). Earlier: from 0.15 to 0.18 a second table, `sighting_techniques/`, held them pre-split; in 0.19 and 0.20 they were split from the string at query time (#180).
   - `iocs.db`: a db-core row table (SQLite format), one row per IoC per day with B-tree indexes on the key, the day and the IP address (as 32 hex digits). "Is this IoC known", "when" and "which addresses in this CIDR block" are index seeks, not scans.
2. **Participants are known organisations** (#159; restores the organisation model of [ADR-002](002-tiered-access-control.md) and [ADR-010](010-postgresql-management-api.md)).
   - A participant is an organisation with an opaque id `identity--{uuid4}` and **one status**: observer, contributor, partner or core. Core is the trusted operator circle; there is no other status.
   - Its details (name, type `cyber_partner`/`customer`, sector, region, contact) live only in `participants.db`, a db-core row table next to `iocs.db`, with its users and their tokens.
   - **Users** (people and machine identities) belong to one participant and **inherit its status**; they have no level of their own. **Tokens** belong to users; only their SHA-256 is stored.
   - Contributors and above send; every status consumes according to its level ("give to get", ADR-002).
3. **Sightings are stored under the participant.** Each row's `reporter` is the participant id, set by the server and never taken from the submission; never a user or a token. Counts of distinct reporters are exact over any window. Below the partner status a cell with fewer than 3 distinct reporters is dropped (#148); partners see participant ids (they are in the files), core also resolves them to names. A target's identity (`target.id`) is accepted in a submission and dropped before anything is stored (`Sighting::detail`), so no status sees it; sector, size and region are kept (#256). Which user sent what is recorded in the submission registry, not in Parquet.
   - **FRANK passes on and does not judge.** What a participant includes (victim-side observables, its interpretation such as an observable's role) is its choice and responsibility, under its TLP marking. FRANK normalises; it does not filter by meaning.
4. **TLP is the submitter's disclosure control, next to the tier** (#149). Each stored row carries its TLP level, and every query shows a tier only the levels it may see: CLEAR is public, GREEN observer, AMBER contributor, AMBER+STRICT partner. TLP:RED is refused at submission, because it is meant for named recipients, not for a platform. The `iocs` table keys its rows by TLP as well, so an IoC lookup can't reveal an AMBER+STRICT sighting to a contributor. GREEN is the default, so a public visitor sees only what was explicitly marked CLEAR.
5. **No SQL from callers.** The HTTP API runs fixed, typed queries. Explore (#157) groups by one dimension from a whitelist (rule, IoC, campaign, technique, sector, IoC type, severity) and filters by the others, under the same reporter threshold and TLP rules. Values reaching SQL are normalised IoCs, quoted by doubling quotes.
6. **The browser runs FRANK code as WebAssembly** (`frank-wasm`, `wasm32-unknown-unknown`):
   - the submission preview runs the server's own parsing, so a contributor sees exactly what will be shared before sending it;
   - partners download the Parquet files (`/v1/files`, listed files only) and query them in the browser on db-core's column engine. Counts, sums, minimums and maximums merge across files;
   - the page shows a tab only from the status its calls need (explore observer, live and submit contributor, analyse partner), so the public sees statistics, lookup, about and api. The server still enforces every status; the menu only follows it.
7. **Tokens instead of Cognito:** bearer tokens of users in `participants.db`, managed with `frank participant`, `frank user` and `frank token` (#159; the first version used a `sha256 tier label` tokens file, which is imported once). OIDC can replace tokens later without changing the statuses.
8. **Three deployments, one image and one on-disk layout:** `frank serve` on a machine; `deploy/podman` (compose, data on a host bind mount); `deploy/stackit` (OpenTofu: a VM running the image with podman, data on a separate block volume, Caddy for TLS).

## Consequences

- **Positive:** a single 6 MB binary and a ~1.5 MB WASM module; no database server to operate; the data is open Parquet; the shared table holds opaque participant ids, never names; the same code validates in the browser and on the server.
- **Dependency on db-core.** db-core is an Apache-2.0 project maintained by Ilja Heitlager in a personal capacity (t-rust-db), so SBP depends on an engine it does not own. The output format (Parquet) keeps an exit open: DuckDB reads every table. FRANK pins db-core to an exact commit.
- **db-core gaps found and fixed on the way** (t-rust-db/db-core#707, PR #708): opening Parquet from bytes, batch queries without threads, nanosecond timestamp literals, and literal parsing without a clock.
- **db-core gaps still open:**
  - local filesystem only (object storage: db-core#690), so a cloud deployment is a VM with a block volume, not object storage plus stateless containers;
  - one writer per table, so one server process per data directory;
  - row engine: no `ON CONFLICT`, broken implicit PK/UNIQUE indexes, no index use for `AND` predicates (db-core#694-#696); the `iocs` schema works around all three;
  - the `iocs` projection is updated after the sightings append, not in one transaction (db-core#693). `frank rebuild-iocs` rebuilds it from the sightings.
- **Retention bases differ:** `sightings` drops days by arrival time (the table's partitions), `iocs` by event day. A late submission about an old event stays in `sightings` longer than in `iocs`.
- **Lost from Phase 2:** the TUI/admin GUI, the management API, Cognito user management, and per-organisation contribution accounting (reciprocity, #103). The participant model (#159) brings back organisations, members and per-organisation accounting; the admin interfaces return only as far as Phase 3 needs them.

## Revision 2026-10-23: participants instead of pseudonyms

The first version (items 2, 3 and 7) kept reporters anonymous: no identity columns, and a reporter pseudonym `HMAC-SHA256(window secret, sha256(token))` whose secret rotated every 30 days and was then deleted. In use that turned out wrong for a closed community:

- counts of distinct reporters were an upper bound across windows, and windows are fixed in time, so the default 30-day view nearly always spans two; a reporter counted twice could lift a cell over the k-anonymity threshold;
- one organisation with two tokens counted as two reporters;
- nobody could trace, correct, erase or credit a contribution afterwards.

Participants are known for as long as they take part; their status, not their anonymity, decides what they receive. The trade-off: shared files now carry participant ids, so a leaked partner file shows which rows share a participant (not who it is). The DPIA has to cover the participant table.
