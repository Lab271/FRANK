# FRANK

Feedbackinfrastructuur voor cyberRisico Analyse en netwerk Kennisdeling: a neutral platform where security teams share **sighting statistics** for SIGMA rules and IoCs (how often, where and when a threat was seen) without sharing who they or their customers are.

## Version: 0.10.0

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
                       └──────────────► HTTP API (tiered) ◄───────────────┘
                                             │
                          web UI + frank-wasm (preview, SQL over Parquet in the browser)
```

- **Anonymised by schema:** a sighting row has no column for an organisation, so none can be stored.
- **Tiers** (ADR-002): public sees totals; observer sees breakdowns with cells under 3 suppressed; contributor submits and looks up IoCs; partner downloads the Parquet files; core operates.
- **Open data format:** every table is plain Parquet, so DuckDB reads it as well.

## Run it

Needs Rust (stable), the `wasm32-unknown-unknown` target and `wasm-bindgen-cli` 0.2.129 (`make check` says what is missing).

**On this machine:**

```bash
make build                         # server + web/pkg
make token TIER=partner LABEL=me   # prints a token once; stores its hash in ./tokens
make demo                          # optional: 60 synthetic sightings from the last 7 days
make run                           # http://127.0.0.1:8080, data in ./data
```

**In podman** (data stays on the host under `deploy/podman/data`; tokens are the same `./tokens` file `make run` uses):

```bash
make token TIER=partner LABEL=me   # skip if you already have one
make up                            # builds the image; http://127.0.0.1:8080 (FRANK_PORT to change)
make down
```

**On STACKIT** (OpenTofu, see [`deploy/stackit/`](deploy/stackit/)): a VM runs the same image with podman. Its data sits on a separate block volume that outlives the VM, and Caddy serves TLS.

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
| `GET /v1/whoami` | any | the token's tier |
| `POST /v1/preview` | any | the rows a submission would share, nothing stored |
| `GET /v1/statistics?days=30` | any | totals; breakdowns from observer up |
| `POST /v1/sightings` | contributor | one submission or an array (max 100), Phase 2 JSON format |
| `GET /v1/iocs?type=ipv4&value=…` | contributor | days seen, counts, SIGMA rules |
| `GET /v1/iocs/range?cidr=185.220.0.0/16` | contributor | addresses seen in a block |
| `GET /v1/files`, `GET /v1/files/{path}` | partner | the table's Parquet files |

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
