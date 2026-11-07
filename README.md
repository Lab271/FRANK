# FRANK

Feedbackinfrastructuur voor cyberRisico Analyse en netwerk Kennisdeling: a neutral platform where known participants (security teams and their organisations) share **sighting statistics** for SIGMA rules and IoCs: how often, where and when a threat was seen. What a participant shares about its customers is its own choice; FRANK passes it on and does not judge it.

## Version: 0.32.0

Phase 3 (production) is a Rust rewrite on [db-core](https://github.com/t-rust-db/db-core); see [ADR-016](.openspec/architecture/decisions/016-phase3-rust-on-db-core.md). Phase 2 (Python/FastAPI) is no longer in the tree: its final state is tagged [`phase2-final`](https://github.com/Lab271/FRANK/tree/phase2-final).

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
- **Admins** (#175, [ADR-017](.openspec/architecture/decisions/017-user-roles-for-identity-administration.md)): a role on a person, apart from the status. An admin manages its own organisation's users and tokens, a superadmin (core only) every organisation, in the web UI's admin tab or under `/v1/admin`.
- **Statuses** (ADR-002): public sees totals; observer sees breakdowns with cells of fewer than 3 distinct reporters suppressed; contributor submits and looks up IoCs; partner downloads the Parquet files and sees reporter ids; core operates and sees who they are.
- **The sender's id is the registration:** each sighting carries a `sighting_id` (UUID) chosen by the sender. Sending it again returns the original receipt; other content under the same id is refused (409).
- **Open data format:** every table is plain Parquet, so DuckDB reads it as well. In `sightings`, `sighting_id` and `digest` are bytes (a `BLOB`; `lower(hex(digest))` is the receipt's digest); the queries are in the OpenAPI description of `/v1/files`.

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
make up                            # builds the image; http://127.0.0.1:8080 (FRANK_PORT) and https://frank.local:8443; same as make up-solo
make trust                         # once: trust its local CA in the macOS keychain, add frank.local to /etc/hosts (sudo)
make down
```

**In podman, the sightings in S3** (#220, [ADR-019](.openspec/architecture/decisions/019-sightings-in-s3-state-on-a-volume.md)): `make up-s3` starts a [Garage](https://garagehq.deuxfleurs.fr) container next to FRANK and sets `FRANK_STORE`, so the manifest and the Parquet files of the sightings are in its bucket (files in `./s3`) and the WAL, `iocs.db` and the other state stay in `./data` and `./participants`. Same Caddy, same URLs, same `make trust` and `make down`; `make up-solo` and `make up-s3` replace each other. The S3 API is at `http://127.0.0.1:3900` (key in `s3/frank.env`; `make s3-ls` lists the bucket, `make s3-browse` browses it with `rclone ncdu`), the bucket as a website, readable without credentials, at `http://frank.web.garage.localhost:3902/<key>`, the admin API at `:3903`. A table is in one place only: switching mode starts the other mode's table. Without podman: `FRANK_STORE=s3://bucket/prefix?endpoint=…&region=…` with `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. The WAL needs a local volume either way, and AWS S3 over HTTPS is not supported yet.

HTTPS comes from Caddy in front of FRANK, as on STACKIT, with a certificate from Caddy's own local CA (`tls internal`). The CA lives in the `caddy-data` volume, so `make trust` holds across `make down` and `make up`; `make untrust` removes it from the keychain again. `FRANK_HOST` changes the name. macOS lets a user bind port 443 only on every interface, so the default is `127.0.0.1:8443`; `FRANK_TLS_ADDR=443` gives `https://frank.local`, reachable from the local network too. `http://frank.local` (port 80, `FRANK_HTTP_ADDR`; on every interface for the same reason) only redirects to the HTTPS address. The plain `http://127.0.0.1:8080` does not redirect: `make stream` and API clients use it. Firefox keeps its own certificate store: set `security.enterprise_roots.enabled` to `true` in `about:config` to use the keychain.

**Participants, users and tokens** live in `participants/participants.db`, apart from the data: wiping `data/` keeps them. Changes apply on the next request, with the server running:

```bash
make participant NAME=acme-mdr STATUS=contributor   # organisation + a user of the same name + token
make user PARTICIPANT=acme-mdr NAME=acme-feed MACHINE=1   # another user (an API client), with a token
make token NAME=acme-feed                           # another token for a user
make participants                                   # organisations, users, token prefixes
target/release/frank participant set-status acme-mdr partner   # all its users, next request
target/release/frank token revoke 1a2b3c4d          # by hash prefix, from `make participants`
target/release/frank user disable acme-feed         # its tokens stop working; `enable` brings them back
target/release/frank user remove acme-feed          # a disabled user only, with its role and tokens
```

**Admins** ([ADR-017](.openspec/architecture/decisions/017-user-roles-for-identity-administration.md)). A role belongs to a person, never to an API client, and decides what the user may manage; the organisation's status still decides what it sees. An **admin** (in a contributor, partner or core organisation) manages its own organisation's users and tokens and reads its audit lines; a **superadmin** (in a core organisation) manages every organisation, its status included. Make the first superadmin on the command line, then manage the rest from the web UI's admin tab:

```bash
make participant NAME=lab271 STATUS=core            # the operator's organisation
make role NAME=lab271 ROLE=superadmin               # its first user becomes superadmin
make user PARTICIPANT=acme-mdr NAME=alice ROLE=admin   # an admin of one organisation, with a token
```

Users are disabled before they are removed. The API refuses to take the last working admin of an organisation or the last working superadmin (by a role change or by disabling), to disable yourself, and to revoke your own last token; the command line can always recover.

An old `./tokens` file is imported once when the server starts on an empty `participants.db`: one organisation per line. Merge the ones that belong together, then delete the file.

**On STACKIT** (OpenTofu, see [`deploy/stackit/`](deploy/stackit/)): a VM runs the same image with podman. Its data sits on a separate block volume that outlives the VM, and Caddy serves TLS.

Participants are managed on the VM through the running container: `sudo podman exec frank frank participant add acme-mdr --status contributor --with-token`.

**Audit log.** `data/audit/YYYY-MM-DD.jsonl` (UTC) has one line per action: every submission and ingest (participant, user, sighting ids, digests, created/duplicate/refused) and every change to participants, users, roles and tokens, from the admin tab or the command line, with who did it (`user@organisation`, or `cli:<os user>`). A token appears only as the first 12 hex digits of its hash, as `frank token list` shows it. Days are dropped with the sightings' retention.

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
| `GET /v1/whoami` | any | status, user, role and participant (id, name) |
| `POST /v1/preview` | any | the rows a submission would share, nothing stored |
| `GET /v1/statistics?days=30` | any | totals; breakdowns from observer up |
| `POST /v1/sightings` | contributor | one submission or an array (max 100), Phase 2 JSON format; each sighting needs a `sighting_id`; answers with receipts (201 new, 200 resend, 409 other content under a registered id) |
| `GET /v1/iocs?type=ipv4&value=…` | contributor | days seen, counts, SIGMA rules |
| `GET /v1/iocs/range?cidr=185.220.0.0/16` | contributor | addresses seen in a block |
| `GET /v1/explore?group=rule&sector=energy&days=30` | observer (rule, IoC, campaign, technique: contributor) | grouped rows with `count`, `reporters`, first/last seen |
| `GET /v1/rules/{id}?days=30` | contributor | one rule's prevalence: trend, sectors, severities, techniques, campaigns, IoCs |
| `GET /v1/files`, `GET /v1/files/{path}` | partner | the table's Parquet files |
| `GET /v1/participants` | partner | ids and status; core: names, type, sector, users |
| `GET, POST /v1/admin/organisations`, `PATCH …/{id}` | admin (own organisation); adding and status: superadmin | organisations |
| `GET, POST /v1/admin/users`, `PATCH, DELETE …/{name}`, `POST …/{name}/disable`, `…/enable` | admin | users, roles; remove a disabled user |
| `GET, POST /v1/admin/tokens`, `DELETE …/{prefix}` | admin | token prefixes; a new token is in its one response |
| `GET /v1/admin/audit?days=7` | admin | audit lines about the organisation; superadmin: all |
| `GET /v1/admin/files?path=data` | superadmin | names, sizes and times of the data and participants directories; no contents |

Send tokens as `Authorization: Bearer <token>`.

Each submission may carry `tlp_level` (default GREEN). Every query shows a tier only the TLP levels it may see: CLEAR is public, GREEN observer, AMBER contributor, AMBER+STRICT partner. TLP:RED is refused.

## Develop

```bash
make test        # cargo test --workspace
make lint        # fmt, clippy (native and wasm32)
```

**Test tiers** ([ADR-018](.openspec/architecture/decisions/018-container-is-the-reference-and-test-tiers.md), #208). `make run` is for developing; the container image is what gets checked, because it is what gets deployed.

```bash
make test-slow                     # Rust tests marked #[ignore = "slow"]: volume, paging
make smoke TOKEN="…"               # read-only checks of http://127.0.0.1:8080 (FRANK_URL=…)
make smoke TLS=1 TOKEN="…"         # the same through Caddy: https://frank.local:8443, its CA, the redirect
make e2e                           # builds the image, runs it on :18080 without Caddy, generates data, checks everything
make e2e E2E_TAG=0.26.0 KEEP=1     # an existing image; keep its data directory
```

`scripts/smoke.py` needs Python 3.9 or later and nothing else (macOS's own `python3` does; `PYTHON=` for another). It asks `/v1/whoami` for each token's status (`TOKEN` takes several, space separated) and checks what that status may and may not read. It never submits unless `--writable` is given, which only `make e2e` does: sightings cannot be deleted. CI runs `test-slow`, and runs `e2e` on the image before pushing it.

**Streaming test** (#177): `scripts/stream_sightings.py` sends synthetic sightings through `POST /v1/sightings` at a steady rate, stamped now, so they pass through every stage of the striped table: the open hour, an hour file in `live/` once the hour closes, a merged day in `archive/` after midnight UTC. With a partner or core token it polls `/v1/statistics` and `/v1/files` and checks that the stored count is the starting count plus what was created at every poll; a share of the sightings is resent and must get its original receipt. Exit code 1 on any mismatch. Run nothing else against the server meanwhile.

```bash
make stream-setup                     # once: register the test tokens in ./participants
make stream RATE=60 DURATION=90m      # cross the top of an hour to see an hour file written
```

The test tokens are checked in as `scripts/stream_tokens.json`: three senders (`stream-test-mdr-1…3`, contributor, three reporters) and a watcher (`stream-test-watch`, partner). `make stream-setup` registers their hashes (`frank token add <user> --hash`) and skips what exists; it works with the server running. **Anyone with the repo has these tokens: run `stream-setup` only on a local FRANK, never on a shared or public one.** Your own tokens go in `FRANK_TOKENS` (comma-separated) and `FRANK_WATCH_TOKEN`. The stream sends no AMBER+STRICT, so a partner watcher sees all of it.

A batch that fails to arrive is sent again, so `make down && make up` in the middle of a run checks that the WAL keeps every accepted sighting.

| Crate | Role |
|---|---|
| `crates/frank-core` | wire model, normalisation, anonymised rows (shared by server and browser) |
| `crates/frank` | server: stores, API, auth, maintenance (flush hourly files, merge days, retention) |
| `crates/frank-wasm` | browser module: preview, Parquet analysis |
| `web/` | static UI |
