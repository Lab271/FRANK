# FRANK

Feedbackinfrastructuur voor cyberRisico Analyse en netwerk Kennisdeling: a neutral platform where known participants (security teams and their organisations) share **sighting statistics** for SIGMA rules and IoCs: how often, where and when a threat was seen. What a participant shares about its customers is its own choice; FRANK passes it on and does not judge it.

## Version: 0.15.0

Phase 3 (production) is a Rust rewrite on [db-core](https://github.com/t-rust-db/db-core); see [ADR-016](.openspec/architecture/decisions/016-phase3-rust-on-db-core.md). Phase 2 (Python/FastAPI) is in [`legacy/phase2/`](legacy/phase2/), and its final state is tagged `phase2-final`.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## How it works

```
 submission (JSON) ──► frank-core: parse, normalise, drop identities ──► sighting rows
                                                                          │
                       ┌──────────────────────────────────────────────────┤
                       ▼                                                  ▼
   data/sightings/   striped Parquet table              data/iocs.db   row table
   live/date=…/hour=…/*.parquet  (hour files)           one row per IoC per day,
   archive/date=…/*.parquet      (merged days)          indexed on IoC, day, IP
                       │                                                  │
                       └──────────────► HTTP API (by status) ◄────────────┘
                                             ▲
                   participants/participants.db: organisations, users, tokens
                   data/registry.db: resend index (rebuilt from the sightings)
                   data/audit/: who did what, one JSON line per action
                                             │
                          web UI + frank-wasm (preview, SQL over Parquet in the browser)
```

- **Known participants** (#159): a participant is an organisation with one status; its users (people and API clients) inherit that status, and sightings are stored under the organisation's opaque id (`identity--{uuid}`), never under a user.
- **Statuses** (ADR-002): public sees totals; observer sees breakdowns with cells of fewer than 3 distinct reporters suppressed; contributor submits and looks up IoCs; partner downloads the Parquet files and sees reporter ids; core operates and sees who they are.
- **The sender's id is the registration:** each sighting carries a `sighting_id` (UUID) chosen by the sender. Sending it again returns the original receipt; other content under the same id is refused (409).
- **Open data format:** every table is plain Parquet, so DuckDB reads it as well.

## Run it

Needs Rust (stable), the `wasm32-unknown-unknown` target and `wasm-bindgen-cli` 0.2.129 (`make check` says what is missing).

**On this machine:**

```bash
make build                                # server + web/pkg
make participant NAME=me STATUS=partner   # registers an organisation, prints a token once
make demo                                 # optional: 60 synthetic sightings, one participant per MDR
make run                                  # http://127.0.0.1:8080, data in ./data, participants in ./participants
```

**In podman** (the same `./data` and `./participants` as `make run`, so participants, tokens and sightings are shared; run one of the two at a time):

```bash
make up                            # builds the image; http://127.0.0.1:8080 (FRANK_PORT to change)
make down
```

**Participants, users and tokens** live in `participants/participants.db`, apart from the data: wiping `data/` keeps them. Changes apply on the next request, with the server running:

```bash
make participant NAME=acme-mdr STATUS=contributor   # organisation + a user of the same name + token
make user PARTICIPANT=acme-mdr NAME=acme-feed MACHINE=1   # another user (an API client), with a token
make token NAME=acme-feed                           # another token for a user
make participants                                   # organisations, users, token prefixes
target/release/frank participant set-status acme-mdr partner   # all its users, next request
target/release/frank token revoke 1a2b3c4d          # by hash prefix, from `make participants`
```

An old `./tokens` file is imported once when the server starts on an empty `participants.db`: one organisation per line. Merge the ones that belong together, then delete the file.

**On STACKIT** (OpenTofu, see [`deploy/stackit/`](deploy/stackit/)): a VM runs the same image with podman. Its data sits on a separate block volume that outlives the VM, and Caddy serves TLS.

Participants are managed on the VM through the running container: `sudo podman exec frank frank participant add acme-mdr --status contributor --with-token`.

**Audit log.** `data/audit/YYYY-MM-DD.jsonl` (UTC) has one line per action: every submission and ingest (participant, user, sighting ids, digests, created/duplicate/refused) and every change to participants, users and tokens, with who did it (`user@organisation`, or `cli:<os user>`). A token appears only as the first 12 hex digits of its hash, as `frank token list` shows it. Days are dropped with the sightings' retention.

**Backups.** `iocs.db` and `registry.db` are indexes rebuilt from the sightings (`frank rebuild`, server stopped); `participants.db` cannot be rebuilt. On STACKIT a nightly timer copies it with `sqlite3 .backup` (safe while FRANK runs) to `/srv/frank/backup/<date>/` and keeps two weeks. That copy sits on the same volume: take volume snapshots or copy `/srv/frank/backup` off the VM for a backup that survives losing the volume. Elsewhere: `sqlite3 participants/participants.db ".backup /somewhere/participants.db"`.

```bash
cd deploy/stackit
export STACKIT_SERVICE_ACCOUNT_KEY_PATH=…
tofu init && tofu apply -var project_id=… -var domain=frank.example.nl \
  -var ssh_public_key="$(cat ~/.ssh/id_ed25519.pub)" -var admin_cidr=203.0.113.4/32
```

## API

| Route | Tier | What |
|---|---|---|
| `GET /health` | none | liveness |
| `GET /v1/whoami` | any | status, user and participant (id, name) |
| `POST /v1/preview` | any | the rows a submission would share, nothing stored |
| `GET /v1/statistics?days=30` | any | totals; breakdowns from observer up |
| `POST /v1/sightings` | contributor | one submission or an array (max 100), Phase 2 JSON format; each sighting needs a `sighting_id`; answers with receipts (201 new, 200 resend, 409 other content under a registered id) |
| `GET /v1/iocs?type=ipv4&value=…` | contributor | days seen, counts, SIGMA rules |
| `GET /v1/iocs/range?cidr=185.220.0.0/16` | contributor | addresses seen in a block |
| `GET /v1/explore?group=rule&sector=energy&days=30` | observer (rule, IoC, campaign, technique: contributor) | grouped rows with `count`, `reporters`, first/last seen |
| `GET /v1/rules/{id}?days=30` | contributor | one rule's prevalence: trend, sectors, severities, techniques, campaigns, IoCs |
| `GET /v1/files`, `GET /v1/files/{path}` | partner | the table's Parquet files |
| `GET /v1/participants` | partner | ids and status; core: names, type, sector, users |

Send tokens as `Authorization: Bearer <token>`.

Each submission may carry `tlp_level` (default GREEN). Every query shows a tier only the TLP levels it may see: CLEAR is public, GREEN observer, AMBER contributor, AMBER+STRICT partner. TLP:RED is refused.

## Develop

```bash
make test        # cargo test --workspace
make lint        # fmt, clippy (native and wasm32)
```

| Crate | Role |
|---|---|
| `crates/frank-core` | wire model, normalisation, anonymised rows (shared by server and browser) |
| `crates/frank` | server: stores, API, auth, maintenance (flush hourly files, merge days, retention) |
| `crates/frank-wasm` | browser module: preview, Parquet analysis |
| `web/` | static UI |
