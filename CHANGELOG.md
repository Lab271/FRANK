# Changelog

All notable changes to FRANK. Format follows [Keep a Changelog](https://keepachangelog.com/), versioning follows [SemVer](https://semver.org/). Phase 2 (Python) releases up to 0.8.0 are tagged in git; its final state is `phase2-final`.

## [Unreleased]

### Changed

- db-core pinned to release v0.173.0 instead of a branch head. It carries the browser fixes, set-probe `IN` lists (a 100-id resend check over 2M rows: about 1 s to 21 ms, db-core #737) and nullable columns appended to an existing table (db-core #740).

### Fixed

- A `sightings/` table written by 0.12 is still refused at startup. db-core #740 would add the `digest` and `received` columns to it and keep the old pseudonymous reporters; `Sightings::open` now checks the stored schema first.

## [0.13.0] - 2026-10-24

### Added

- **Participants** (#159): organisations with one status (observer, contributor, partner, core) and an opaque id `identity--{uuid}`; users (people and API clients) belong to one organisation and inherit its status; tokens belong to users. All in `participants/participants.db` (`--participants`, `FRANK_PARTICIPANTS`), a SQLite-format row table apart from the data directory, so wiping `data/` keeps them. Changes apply on the next request, with the server running.
- CLI: `frank participant add|list|set-status`, `frank user add`, `frank token new|list|revoke`; `frank ingest --as <participant> [--create]`. Make targets `participant`, `participants`, `user`, `token`.
- **The sender's `sighting_id` is the registration** (#159). `POST /v1/sightings` requires it (a UUID; `sighting--` and Phase 2's `sighting-` forms accepted) and answers with receipts: a resend with the same content gets its original receipt (200), other content under a registered id is 409 and nothing of the batch is stored. The registration is stored with the sighting: new `digest` and `received` columns in the Parquet; `data/registry.db` is an index over them for a fast resend check, rebuilt from the sightings when missing (P9a on #159: a scan of the Parquet per POST costs seconds, db-core #737). Which user sent what is not in either. `frank ingest` derives an id from the content when a file has none, so loading a file twice adds nothing.
- `GET /v1/participants`: ids and status for partners; names, type, sector and users for core. `GET /v1/whoami` returns the user and participant.
- STACKIT: a nightly timer copies `participants.db` with `sqlite3 .backup` and keeps two weeks.
- `frank rebuild` (was `rebuild-iocs`, still accepted) rebuilds `iocs.db` and `registry.db`.
- **Audit log** (#159): `data/audit/YYYY-MM-DD.jsonl`, one line per submission, ingest and change to participants, users and tokens, naming who did it; tokens only as a hash prefix. Written by the server and the CLI; dropped with the retention.

### Changed

- **Sightings are stored under the organisation** (#159, ADR-016 revised): the `reporter` column holds the participant id. Counts of distinct reporters are exact over any window; two users of one organisation are one reporter.
- `make run` and `make up` share `./data` and `./participants`; run one of the two at a time. Podman's old `deploy/podman/data` is no longer used.
- A `./tokens` file is imported once into an empty `participants.db`, one organisation per line.
- The web UI writes a new `sighting_id` into the form before sending, and shows the receipts.

### Removed

- The rotating HMAC reporter pseudonyms (#148): `data/secrets/` is no longer used. A `sightings/` table written by 0.12.0 (old pseudonyms, no `digest` column) is refused at startup: move it aside and reload (`make demo` into an empty `./data`).

### Fixed

- Web UI: filter chips use the text colour.

## [0.12.0] - 2026-10-23

### Added

- **Explore** (#157): one list grouped by a dimension (rule, IoC, campaign, technique, sector, IoC type, severity) and filtered by others, from a fixed whitelist (`GET /v1/explore`). Tier per dimension as in `/v1/statistics`; groups under 3 reporters are hidden below partner; TLP applies.
- **Detail pane**: `GET /v1/rules/{id}` gives one rule's trend, sectors, severities, techniques, campaigns and IoCs; `GET /v1/iocs` gains a 30-day trend. The web UI opens them in a sliding pane; panes link to each other and dashboard bars link into Explore. The view lives in the URL hash, so it can be bookmarked.

### Changed

- `make up` recreates the container, so a rebuilt image is always the one running.

## [0.11.1] - 2026-10-22

### Fixed

- **k-anonymity counts distinct reporters, not rows** (#148). One contributor sending three sightings used to clear the threshold of 3 alone. Each row now carries a reporter pseudonym (HMAC-SHA256 of the token's hash under a secret that rotates every 30 days and is deleted when its window ends). Statistics below partner drop cells with fewer than 3 distinct reporters; breakdowns and IoC lookups report `reporters` next to `count`.

### Changed

- `frank ingest` counts each input file as one reporter; `make demo` writes one file per synthetic MDR.
- The `sightings` table has a `reporter` column: data from 0.11.0 has to be reloaded.

## [0.11.0] - 2026-10-22

### Added

- **TLP per submission, enforced per tier** (#149). A submission may carry `tlp_level` (default GREEN; `TLP:` prefix, AMBER+ and WHITE spellings accepted). Each tier sees only the levels it may: CLEAR is public, GREEN observer, AMBER contributor, AMBER+STRICT partner. TLP:RED is refused (422). This applies to statistics, IoC lookup and its rules, CIDR ranges and the IoC count. The `iocs` table is keyed per level, so a lookup can't reveal an AMBER+STRICT sighting to a contributor.
- The browser preview shows each row's TLP; `make demo` mixes the levels.

### Changed

- GREEN is no longer public: a public visitor sees only sightings marked CLEAR.
- db-core 0.167 (from the head of t-rust-db/db-core#708), which brings `IN (list)` to the column engine.
- An `iocs.db` from before this release is refused at startup; delete it and run `frank rebuild-iocs`.

## [0.10.0] - 2026-10-22

Phase 3: FRANK rebuilt in Rust on db-core (ADR-016). The Phase 2 Python service moved to `legacy/phase2/`.

### Added

- `frank` server, one binary (`serve`, `token`, `ingest`, `rebuild-iocs`):
  - sightings in a striped db-core Parquet table (hour files sorted by rule and IoC, closed days merged, retention by whole day);
  - IoCs in a db-core row table, one row per IoC per day, indexed on key, day and IP (CIDR lookups);
  - tiered HTTP API: statistics (cells under 3 suppressed below partner), IoC lookup, CIDR range, Parquet file download for partners, including the open hour (`open/current.parquet`);
  - hashed bearer tokens instead of Cognito.
- Anonymisation by schema: a sighting row has no column for an organisation's identity.
- Browser module (`frank-wasm`): a preview of exactly the rows a submission shares, and SQL over the downloaded Parquet files on db-core's column engine.
- Web UI on the Lab271 design system.
- Deployments: `make run`; podman compose with data on a host bind mount and tokens shared with `make run`; OpenTofu for STACKIT (VM, persistent data volume, Caddy TLS).
- `make demo`: 60 synthetic sightings from the last 7 days (documentation addresses only).
- CI: fmt, clippy (native and wasm32), tests, container image.

### Changed

- Blank observable values are skipped instead of refusing the submission (ADR-008).
- UI files are served with `Cache-Control: no-cache`, so a rebuilt WASM module is picked up.

### Removed

- The Phase 2 Python service, Cognito auth, the admin TUI and web GUI, and the management API (kept in `legacy/phase2/`).
