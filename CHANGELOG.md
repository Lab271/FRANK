# Changelog

All notable changes to FRANK. Format follows [Keep a Changelog](https://keepachangelog.com/), versioning follows [SemVer](https://semver.org/). Phase 2 (Python) releases up to 0.8.0 are tagged in git; its final state is `phase2-final`.

## [Unreleased]

## [0.20.0] - 2026-10-28

### Added
- IoC lookup details in the side pane: per-day and per-rule views, with sectors, severities, techniques and campaigns (#182).
- `GET /v1/iocs` returns `panels` (same reporter threshold and TLP rules as Explore) and takes `day=YYYY-MM-DD` (#182).

## [0.19.0] - 2026-10-28

### Changed
- **Techniques are counted on `sightings`** (#180) with `UNNEST(string_split(technique, ','))`, db-core v0.198.0 (from v0.173.0). Statistics, Explore and rule pages give the same counts as before.
- Explore `group=technique` takes an `ioc` or `ioc_type` filter (was 422).

### Removed
- `data/sighting_techniques/` is no longer written or read. A directory from 0.15–0.18 is reported at startup and can be deleted.

## [0.18.0] - 2026-10-27

### Added

- `scripts/stream_sightings.py` and `make stream` (#177): stream synthetic sightings through the API and check the striped table at every stage (open hour, hour file, merged day): stored = sent, resends keep their receipt, a restart mid-run loses nothing.
- `make stream-setup` and `frank token add <user> --hash`: register the checked-in test tokens (`scripts/stream_tokens.json`, local only) so the stream test runs without setup of its own.

## [0.17.0] - 2026-10-27

### Added

- **Admins** (#175, ADR-017): a role on a user, apart from its organisation's status. An **admin** (in a contributor, partner or core organisation) manages its own organisation's users and tokens; a **superadmin** (core only) manages every organisation, its status included. Only people hold a role, never an API client. Roles are a `roles` table in `participants.db`, created in older files when they are opened (db-core cannot add a column to a table yet).
- `/v1/admin/…`: organisations (list; add and set status: superadmin), users (list, add, set role, disable, enable, remove), tokens (list prefixes, issue, revoke) and the audit log (`?days=`, up to 31). To an admin another organisation's objects are 404. A new token is in its one response only (`Cache-Control: no-store`). Every change writes an audit line naming `user@organisation`.
- **Users are disabled before they are removed.** A disabled user's tokens stop working without being revoked, and enabling it brings them back; no token can be issued to it. Removing a disabled user deletes it with its role and tokens; its sightings stay under the organisation, and its name can be used again.
- Guards in the API: an organisation's last working admin and the platform's last working superadmin keep their role and cannot be disabled; you cannot disable yourself or revoke your own last token; only a superadmin changes a superadmin. A status change that would leave a user with a role the status does not allow is refused, from the CLI as well.
- Web UI **admin tab**, shown to users with a role: users with role, state and actions (new token, disable, enable, remove), tokens with revoke, and the audit window; superadmins also pick the organisation, set its status and add organisations. The status pill shows the role.
- CLI: `frank user add … --role admin|superadmin`, `frank user set-role`, `frank user list`, `frank user disable|enable|remove`; `make role NAME=… ROLE=…`, `make user … ROLE=…`. `make participants` lists the users too.
- `GET /v1/whoami` returns the user's `role`.

### Changed

- The API tab marks admin routes with the role they need (`x-role` in `api/openapi.yaml`) and shows `curl` examples with the request body.
- The server writes `participants.db` as well as reading it; the CLI keeps working beside it.

## [0.16.0] - 2026-10-24

### Added

- YAML and STIX 2.1 input (#160, D3): `POST /v1/sightings` and `/v1/preview` read the format the `Content-Type` names (`application/json`, `application/yaml`, `application/stix+json`); an unknown one is 415. A STIX bundle maps each `sighting` with its SIGMA `indicator` and the SCOs of its `observed-data`; identities and relationships are ignored. YAML aliases are refused.
- `frank ingest` and the browser preview take JSON, YAML and STIX bundles, told apart by the content.
- Sighting records for machine clients (#160, D4): `GET /v1/sightings` (`since`, `until`, `rule`, `ioc`, `mine`, `cursor`, `limit`) lists normalised records oldest first with a cursor; `GET /v1/sightings/{id}` returns one. Partners and core list all; contributors their own (`mine=true`). Only sightings stored since 0.15 have records.
- `GET /v1/summary`: what the caller's participant sent in the window, and the sightings it can see from everyone.
- `GET /v1/openapi.json`, from the hand-written `api/openapi.yaml` with each operation's lowest status (`x-min-status`); a test fails when a route is missing from it.
- Web UI `about` and `api` tabs (#160, D5): the "FRANK does not judge" principle, what each status may do, statuses × TLP, and an example message with each field marked by the lowest status that sees it; the endpoints from `/v1/openapi.json` with their lowest status and `curl` examples, and the three input formats.
- The submit tab takes YAML and STIX as well as JSON.
- Explore reaches single sightings: a rule or IoC pane lists its sightings newest first (partners all, contributors their own), carrying Explore's filters and window; a sighting opens as its record in YAML, with links back to its rule, IoCs and techniques. `GET /v1/sightings` takes Explore's filters (`campaign`, `technique`, `sector`, `ioc_type`, `severity`) and `order=desc`. Explore counts are labelled sightings.
- A sighting record shows as YAML or JSON, coloured by value type, with a copy button; what is copied can be submitted again as-is.

## [0.15.0] - 2026-10-24

### Added

- **Sightings stored at the right grain** (#160, D2): `sightings` gains `seq` (the IoC's position in its sighting) and `detail` (the normalised sighting as `frank/1` JSON, on the `seq = 0` row, without the target's id since partners download these files). `technique` holds all techniques, comma-separated. db-core adds the two columns to an existing table; its rows read NULL there.
- `data/sighting_techniques/`: one row per sighting × technique, for ranking techniques. Not served in `/v1/files`.

### Fixed

- **Counts are per sighting, not per sighting × IoC.** `observations` in `/v1/statistics` no longer multiplies by the number of IoCs; rules, sectors, severities and campaigns in statistics, Explore and rule pages count sightings. Techniques count every technique of a sighting, not the first. Grouped by IoC type, a sighting counts once per IoC of the type. Rows stored before this release still count as they did: reload the data (`make demo` into an empty `./data`) for exact numbers.

### Changed

- Explore refuses `group=technique` with an `ioc` or `ioc_type` filter (422): techniques are counted in their own table and db-core's table query cannot join.

## [0.14.1] - 2026-10-24

### Fixed

- Logs are plain text when not written to a terminal (no ANSI colour codes in container logs), and the hourly maintenance logs `compacted` only when it merged files.

## [0.14.0] - 2026-10-24

### Added

- **The normalised sighting** (#160, D1): `frank_core::Sighting` (`frank/1`) replaces `Submission` and is built by `SightingBuilder` from Phase 2's format or `frank/1` (`"format": "frank/1"`, what a `Sighting` serialises to). It keeps what was dropped before: all ATT&CK techniques, every observable with the sender's `role` and its other fields (port, protocol, file name, ...) as context, the SIGMA rule's title and level, the description, first and last seen, the target's region and id. Nothing is filtered on `role` (ADR-016). Storage is unchanged until D2: one row per sighting × IoC with the first technique.

### Changed

- **Digests are taken over the normalised sighting.** A sighting registered by 0.13 and resent unchanged now gets 409 instead of its receipt: its digest covered fewer fields.
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
