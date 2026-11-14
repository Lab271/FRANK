# FRANK

Feedbackinfrastructuur voor cyberRisico Analyse en netwerk Kennisdeling: a neutral platform where known participants (security teams and their organisations) share **sighting statistics** for SIGMA rules and IoCs: how often, where and when a threat was seen. What a participant shares about its customers is its own choice; FRANK passes it on and does not judge it.

## Version: 0.54.0

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
- **Open data format:** every table is plain Parquet, so DuckDB reads it as well. In `sightings`, `sighting_id` and `digest` are bytes (a `BLOB`; `lower(hex(digest))` is the receipt's digest); the queries are in the OpenAPI description of `/v1/files`. In the browser, `frank-wasm` runs a query over each downloaded file and merges `count`, `sum`, `min` and `max` across them; `avg` and `count(DISTINCT …)` cannot be merged that way, so such a query answers per file, and the UI says so.

## Run it

Needs Rust (stable), the `wasm32-unknown-unknown` target and `wasm-bindgen-cli` 0.2.129 (`make check` says what is missing).

**On this machine:**

```bash
make build                                # server + web/pkg
make participant NAME=me STATUS=partner   # registers an organisation, prints a token once
make demo                                 # optional: 60 synthetic sightings, one participant per MDR
make run                                  # http://127.0.0.1:8080, data in ./data, participants in ./participants
```

**In podman** (the same `./data` and `./participants` as `make run`, so participants and tokens are shared; run one of the two at a time):

```bash
make up                            # builds the image; http://127.0.0.1:8080 (FRANK_PORT) and https://frank.local:8443, the sightings in S3, sign-in with SSO
make up S3=0 SSO=0                 # either left out: the sightings in ./data (as make run), tokens only
make trust                         # once: trust its local CA in the macOS keychain, add frank.local to /etc/hosts (sudo)
make down                          # stops it, whatever S3 and SSO were
```

**In podman, the sightings in S3** (#220, [ADR-019](.openspec/architecture/decisions/019-sightings-in-s3-state-on-a-volume.md)): `make up` starts a [Garage](https://garagehq.deuxfleurs.fr) container next to FRANK and sets `FRANK_STORE`, so the manifest and the Parquet files of the sightings are in its bucket (files in `./s3`) and the WAL, `iocs.db` and the other state stay in `./data` and `./participants`; `make up S3=0` keeps the sightings in `./data` instead. Same Caddy, same URLs, same `make trust` and `make down` either way. The S3 API is at `http://127.0.0.1:3900` (key in `s3/frank.env`; `make s3-ls` lists the bucket, `make s3-browse` browses it with `rclone ncdu`, `make s3-read` opens DuckDB on the sightings, `make s3-column` opens column-rs on it, read through the manifest), over HTTPS through Caddy at `https://frank.local:9443` (`GARAGE_TLS_PORT`, the same local CA as FRANK's; `make s3-column` reads there by default with column-rs 0.46+ built with `--features s3-tls`, `TLS=0` reads the http port instead, `URL=s3://bucket/prefix?endpoint=…&region=…` any other location), the admin API at `:3903`. Garage has no website endpoint: it would serve the Parquet files, reporter ids included, without credentials (#246). A table is in one place only: switching mode starts the other mode's table. Without podman: `FRANK_STORE=s3://bucket/prefix?endpoint=…&region=…` with `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. The WAL needs a local volume either way.

**Storage: filesystem or S3** (#220, [ADR-019](.openspec/architecture/decisions/019-sightings-in-s3-state-on-a-volume.md)). How a sighting is written, read, cached and replayed after a restart, with diagrams: [docs/sightings-storage.md](docs/sightings-storage.md). What a query costs against S3, and how that came down: [docs/performance.md](docs/performance.md). `FRANK_STORE` unset keeps everything on the filesystem. Set to `s3://bucket/prefix?endpoint=…&region=…` it moves the sightings' manifest and Parquet files **and the audit log** (one object per line, `audit/YYYY-MM-DD/<ns>-<pid>-<n>.jsonl`, listed by prefix, so it reads back in order) to the bucket; retention deletes the objects of days past it, db-core's 10-minute delete grace after the manifest drops them. Everything else stays on the volume (EFS on AWS): the WAL (`data/s3/sightings`), `iocs.db`, `registry.db`, `participants.db`, `lists/`, the geo files. Credentials come from the AWS chain (environment, shared credentials file, an ECS task role, the EC2 instance role through IMDSv2; a role's are fetched again before they expire), never from the URI.

- **AWS S3 over HTTPS.** Leave `endpoint` out (or give an `https://` one) and FRANK sends the requests itself through `ureq` and rustls (`ring`, the system's certificate store), a `tls` Cargo feature that is on in the container image (`cargo build --features tls`; off, an `https://` endpoint is refused). Garage and other `http://` endpoints need nothing. `deny.toml` holds the licence allow-list, `cargo deny check` runs in CI, and the image's SBOM lists the TLS crates with the rest.
- **One writer.** Garage ignores `If-Match` / `If-None-Match`, so against it only FRANK's local lock protects the table and a second FRANK on the same bucket is **not** refused. AWS S3 gets a fenced manifest commit and a lease. Run one FRANK per bucket and prefix either way.
- **Switching mode on an existing install** (stop FRANK first; a table is in one place only, so this is a copy, not a setting). Filesystem to S3:

  ```bash
  aws s3 sync data/sightings s3://BUCKET/sightings --exclude 'wal/*' --exclude 'tmp/*'
  mkdir -p data/s3/sightings && cp -R data/sightings/wal data/s3/sightings/wal   # the open hour, not yet in Parquet
  for f in data/audit/*.jsonl; do d=$(basename "$f" .jsonl)
    aws s3 cp "$f" "s3://BUCKET/sightings/audit/$d/0000000000000000000-migrated.jsonl"; done
  ```

  then start with `FRANK_STORE=s3://BUCKET/sightings?…` (use `--endpoint-url` with `aws` for Garage). Back to the filesystem, the other way round: `aws s3 sync s3://BUCKET/sightings data/sightings --exclude 'audit/*'`, `rm -rf data/sightings/wal && cp -R data/s3/sightings/wal data/sightings/wal`, and each `audit/<day>/` objects' lines appended in name order to `data/audit/<day>.jsonl`. Unflushed rows are in the WAL, so keep it with the table; `a_local_table_copied_to_a_store_is_the_same_table` in `store/sightings.rs` runs both directions.

HTTPS comes from Caddy in front of FRANK, as on STACKIT, with a certificate from Caddy's own local CA (`tls internal`). The CA lives in the `caddy-data` volume, so `make trust` holds across `make down` and `make up`; `make untrust` removes it from the keychain again. `FRANK_HOST` changes the name. macOS lets a user bind port 443 only on every interface, so the default is `127.0.0.1:8443`; `FRANK_TLS_ADDR=443` gives `https://frank.local`, reachable from the local network too. `http://frank.local` (port 80, `FRANK_HTTP_ADDR`; on every interface for the same reason) only redirects to the HTTPS address. The plain `http://127.0.0.1:8080` does not redirect: `make stream` and API clients use it. Firefox keeps its own certificate store: set `security.enterprise_roots.enabled` to `true` in `about:config` to use the keychain.

**Limits and headers** (#244). FRANK itself, in every deployment, sends a Content-Security-Policy (scripts, styles and data from FRANK only, plus the WASM preview; no inline script, no framing), `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer` on every response. It handles at most `FRANK_MAX_CONCURRENCY` (64) requests at once; the rest wait. A request that takes longer than `FRANK_REQUEST_TIMEOUT` (60 s), waiting included, gets 503 (a query already running finishes in the background). Caddy adds HSTS: a year on STACKIT, a day on `frank.local` (so a browser lets go of it soon after `make untrust`), none on `localhost`. There is no per-client rate limit yet: behind Caddy, FRANK would have to trust `X-Forwarded-For` to tell clients apart.

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

**Sign in with SSO** (#241, [ADR-020](.openspec/architecture/decisions/020-sso-with-openid-connect.md)). People can sign in to the web UI with OpenID Connect (Okta, or any OIDC provider) instead of pasting a token. It is **off unless all five settings are given**; with some but not all, `frank serve` refuses to start and names the missing ones. Without them FRANK behaves exactly as before.

| Setting | What |
|---|---|
| `FRANK_SSO_ISSUER` | The issuer, e.g. `https://<org>.okta.com/oauth2/default`; discovery is read from `<issuer>/.well-known/openid-configuration` at the first sign-in |
| `FRANK_SSO_CLIENT_ID` | The OIDC application's client id |
| `FRANK_SSO_CLIENT_SECRET_FILE` | **A file** holding the client secret: the only secret SSO adds. Never an environment variable (it would show in `podman inspect`), never in git; FRANK never logs, audits or returns it |
| `FRANK_SSO_REDIRECT_URL` | FRANK's public callback, `https://<host>/v1/sso/callback`, registered as the sign-in redirect URI in the provider |
| `FRANK_SSO_ORGANISATION` | The organisation (must exist) that people signing in for the first time are created in |

The issuer and the redirect URL must be `https://`; only `localhost` may be `http://` (the local stub). The application is a confidential web client with the authorization code flow and PKCE (S256), client authentication `client_secret_basic`, scopes `openid email profile`.

- **Users are provisioned on first sign-in.** The ID token's `email`, in lower case, is the user name. A new person becomes a **human user with no role** in `FRANK_SSO_ORGANISATION`; that organisation's status decides what they see, and roles are still given by an admin (SSO never grants one). An existing human user with the same e-mail is linked when the provider says the e-mail is verified, and keeps its organisation and role: make yourself superadmin on the command line, then sign in with SSO. Machine users never sign in; a disabled user is refused.
- **Bearer tokens are unchanged.** A session is an HttpOnly `frank_session` cookie (eight hours, `SameSite=Lax`, `Secure` on https; only its SHA-256 is stored, in `participants.db`). It names the caller only when a request has no `Authorization` header, so API clients, `make stream` and the token box in the web UI work as before, and a token always wins. A `POST`, `PUT`, `PATCH` or `DELETE` that carries the cookie needs FRANK's own `Origin` (cross-site request forgery). Disabling a user ends its sessions as it stops its tokens.
- **Audit lines:** `sso_login`, `user_provisioned`, `sso_refused` (with the reason; the browser only sees `/?sso=refused`) and `sso_logout`.
- **Not (yet):** SCIM. A person removed in the provider keeps their FRANK user until an admin disables it; their session ends within eight hours. Signing out of FRANK leaves the provider's own session as it is.

**Locally, against a stub** (#238, development only): `make up` (unless `SSO=0`) runs a small Python stand-in for Okta's OIDC endpoints ([`deploy/podman/sso-stub/`](deploy/podman/sso-stub/)), at `http://localhost:9400/oauth2/default` (`SSO_STUB_PORT`). It shares the frank container's network, so that one address works for the browser and for FRANK. It signs in **anyone who picks a name** from `users.json`, with a signing key made at every start: never deploy it. `make up` makes the client secret once in `./sso/client-secret` (git-ignored, never printed) and registers the organisation `sso-users` (contributor; `FRANK_SSO_ORGANISATION`) for new users. It also registers `sbp`, the main company (core), with the users `admin@sbp.example` (admin) and `superadmin@sbp.example` (superadmin), without tokens: the stub's "Ada Admin" and "Sam Superadmin" are linked to them on sign-in and keep those roles. Open `https://frank.local:8443` (after `make trust`) and press "sign in with SSO". Its tests: `cd deploy/podman/sso-stub && uv run --group dev pytest`.

**In production** the Okta application and its secret are set up outside this repository (GitLab `Labs/deployments/test-frank`); the secret is mounted as a file, as here.

**On STACKIT** (OpenTofu, see [`deploy/stackit/`](deploy/stackit/)): a VM runs the same image, pinned by commit, with podman. Its data sits on a separate block volume that outlives the VM, and Caddy serves TLS. Options:

- `store_bucket`: the sightings and the audit log go to that Object Storage bucket (`FRANK_STORE`, ADR-019); the WAL and the SQLite files stay on the volume. OpenTofu makes the bucket and a credential for it. The credential's keys reach the VM through its user data, which anyone who can read the project's servers can see. Turn on versioning once, as on AWS, with the credential's keys: `aws s3api put-bucket-versioning --endpoint-url https://object.storage.eu01.onstackit.cloud --bucket <bucket> --versioning-configuration Status=Enabled` (the provider has no resource for it), and let old versions expire with `put-bucket-lifecycle-configuration` (`NoncurrentVersionExpiration`; STACKIT refuses an `AbortIncompleteMultipartUpload` rule). The writer lease leaves an old version every few seconds. Like the volume, the bucket is protected (`prevent_destroy`, #286): a plan that would replace it (another name) or remove it (`store_bucket` emptied) fails. To drop it on purpose, take it out of the state first, `tofu state rm 'stackit_objectstorage_bucket.frank[0]'` (from a deployment that uses the directory as a module: `'module.<name>.stackit_objectstorage_bucket.frank[0]'`), apply, and delete the bucket in STACKIT yourself; the volume the same way, `stackit_volume.data`.
- `abuse_key`: the abuse.ch Auth-Key for the URLhaus and ThreatFox lists. The VM fetches the GeoIP databases monthly and the IoC lists daily (#276), first right after boot, with the same scripts as `make geoip` and `make lists` (`scripts/fetch-geoip.sh`, `scripts/fetch-lists.sh`; systemd timers `frank-geoip` and `frank-lists`). Without the key the other lists are still fetched. It reaches the VM through its user data, like the bucket's keys; it is kept in `/etc/frank/lists.env` (0600). A failed download keeps the previous files; `journalctl -u frank-geoip -u frank-lists` shows the runs.
- `sso_issuer`, `sso_client_id`, `sso_client_secret`, `sso_organisation`: sign in with SSO (ADR-020), all four or none (the plan refuses a partial set). The redirect URL is `https://<domain>/v1/sso/callback`; register it in the identity provider. The settings go to `/etc/frank/sso.env`, the secret to `/etc/frank/sso-client-secret` (0600, FRANK's uid), mounted into the container as the file `FRANK_SSO_CLIENT_SECRET_FILE` names; like the bucket's keys it travels in the user data. Create `sso_organisation` first (`frank participant add …` through `stackit server command create`), and your own human user with its e-mail if it should keep a role: FRANK refuses to start while the organisation is missing. Changing these replaces the VM; the data volume stays.
- `admin_cidr` and `ssh_public_key`: SSH from that range. Empty (the default) opens no port 22: the VM runs the STACKIT Server Agent, and commands go through `stackit server command create … --template-name RunShellScript`. The project needs the run-command service (`cloud.stackit.run-command`) enabled first, through the service-enablement API or the portal.

**Logs on STACKIT** (#308, [ADR-024](.openspec/architecture/decisions/024-log-streams.md)). FRANK runs with `FRANK_LOG_FORMAT=json` and `--log-driver passthrough`, Caddy logs its access lines to stdout, so both are in the VM's journal: `journalctl -t frank -o cat` and `journalctl -u caddy -o cat`. Not the journald log driver: it stores a line in 8 KiB partial entries, which breaks the JSON of the runtime manifest's packages line, and an attached `podman run` logs each line twice; passthrough hands the container's stdout to the unit, and journald keeps each line whole up to `LineMax` (1M here). A drop-in, `/etc/systemd/journald.conf.d/frank.conf`, makes the journal persistent and keeps it **30 days** (`MaxRetentionSec=30day`), for every unit on the VM, with lines up to 1 MiB (`LineMax=1M`). Shipping the lines to STACKIT Logs is the deployment's own work (test-frank#8).

Participants are managed on the VM through the running container: `sudo podman exec frank frank participant add acme-mdr --status contributor --with-token`, over SSH or as a server command (`tofu output create_token` prints one).

**Audit log.** `data/audit/YYYY-MM-DD.jsonl` (UTC) has one line per action: every submission and ingest (participant, user, sighting ids, digests, created/duplicate/refused) and every change to participants, users, roles and tokens, from the admin tab or the command line, with who did it (`user@organisation`, or `cli:<os user>`). A token appears only as the first 12 hex digits of its hash, as `frank token list` shows it. Days are dropped with the sightings' retention. With `FRANK_STORE` the lines are objects in the bucket instead (see Storage above).

**Logs** (#287). FRANK writes two log targets to stdout. `frank` holds the application's lines (startup, flushes, an `accepted` submission, errors). `frank::access` holds one INFO line per request: `request_id`, `method`, `uri` (path **with** its query string), `status`, `latency_ms`, `caller` (`user@organisation`, `public`, or `unknown` when no token or session was resolved, as on a 401) and `tier`. The request id is a ULID, returned as `X-Request-Id` and carried on the application's lines for that request, so FRANK's lines, Caddy's and a support ticket can be joined. **Caddy writes the web stream** (#307, [ADR-024](.openspec/architecture/decisions/024-log-streams.md)): one JSON line per request to stdout, with the client address, TLS, user agent, status and the response headers, `X-Request-Id` among them, and the requests that never reach FRANK; `Authorization` and cookies are `REDACTED` (`log_credentials` stays off). `make log-check` sends one request through Caddy in `make up` with a made-up token and cookie and checks both lines carry the same id and neither secret. Never logged: the `Authorization` header, the session cookie, a token, a request or response body, and the query of `/v1/sso/callback` (its one-time code). **At start, `frank serve` logs its runtime manifest** under a third target, `mvl_manifest` (#315, [mvl-manifest](https://github.com/mvl-lang/mvl-rust/tree/main/crates/mvl-manifest)): the version, the toolchain, the build provenance (`source_digest`, `lockfile_digest`), every package in the binary and in its build with source and checksum, the runtime environment, and a WARN per assurance gap. In the image the VCS fields are empty (`.git` is not in the build context); `source_digest` and `lockfile_digest` identify the source, and `path_or_git_dependency` is expected (db-core and mvl-manifest come from git). Each package is its own record, so a start logs about 160 `mvl_manifest` lines, none longer than about 1 KB. `RUST_LOG` chooses what is written (default `frank=info,mvl_manifest=info`, which includes the access log and the manifest; `frank::access=off` or `mvl_manifest=off` drops one). `FRANK_LOG_FORMAT=json` writes one JSON object per line with `target` and the fields at the top level, so a log agent can send `frank::access` and `frank` to separate streams; plain text is the default. The access log names the actual user (decision in #287): it says which organisation looks up which indicator, so keep it **30 days** and readable only by FRANK admins. The privacy notice should say: requests are logged with user and query for 30 days, for security and operations.

**Backups.** `iocs.db` and `registry.db` are indexes rebuilt from the sightings (`frank rebuild`, server stopped); `participants.db` cannot be rebuilt. On STACKIT a nightly timer copies it with `sqlite3 .backup` (safe while FRANK runs) to `/srv/frank/backup/<date>/` and keeps two weeks. That copy sits on the same volume: take volume snapshots or copy `/srv/frank/backup` off the VM for a backup that survives losing the volume. What each loss costs on STACKIT: a rebuilt VM keeps everything (the volume is re-attached and the WAL replays); a lost volume costs the WAL's unflushed hour and `participants.db` unless it was copied off the volume (the indexes are rebuilt from the sightings), and without a bucket the sightings and the audit log too; a lost bucket costs every sighting and the audit log, which versioning does not bring back. Elsewhere: `sqlite3 participants/participants.db ".backup /somewhere/participants.db"`.

```bash
cd deploy/stackit
export STACKIT_SERVICE_ACCOUNT_KEY_PATH=…
tofu init && tofu apply -var project_id=… -var domain=frank.example.nl \
  -var image=ghcr.io/lab271/frank:<sha> -var store_bucket=frank-example-sightings
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
| `GET /v1/sso` | none | whether sign-in with SSO is on |
| `GET /v1/sso/login`, `GET /v1/sso/callback` | none | the OIDC sign-in (browser redirects); 404 when SSO is off |
| `POST /v1/sso/logout` | the session | ends the session; needs FRANK's own `Origin` |
| `POST /mcp` | any; each tool as its route | the MCP server (see below) |

Send tokens as `Authorization: Bearer <token>`. With SSO on, a request without that header is named by its `frank_session` cookie, if any.

**MCP** (#263, [spec 015](.openspec/specs/015-mcp/spec.md); for users: [docs/mcp.md](docs/mcp.md)). `POST /mcp` speaks the Model Context Protocol (Streamable HTTP, stateless: JSON answers, no SSE stream), so Claude Code and other MCP clients can query FRANK. Its read-only tools `whoami`, `statistics`, `summary`, `lookup_ioc`, `ioc_range`, `explore`, `rule_detail`, `list_sightings` and `get_sighting` each call the `/v1` route of that name with the request's own token, so they see exactly what that token sees on `/v1`; a status too low for a tool is a tool error the model can read. Every tool call is an `mcp_call` audit line. To add it to Claude Code, against `make up` (after `make trust`), with the token in an environment variable from 1Password rather than pasted:

```bash
export FRANK_TOKEN=$(op read 'op://<vault>/<item>/token')
claude mcp add --transport http frank https://frank.local:8443/mcp \
  --header "Authorization: Bearer ${FRANK_TOKEN}"
claude mcp list            # frank: … ✓ Connected
```

The token's user decides the status the tools answer with: a machine user in an observer or contributor organisation is a sensible one for an assistant. Over SSH, forward the port (`ssh -L 8443:127.0.0.1:8443 host`) and use the same command. A Claude.ai connector, signed in through Okta, is #264.

Each submission may carry `tlp_level` (default GREEN). Every query shows a tier only the TLP levels it may see: CLEAR is public, GREEN observer, AMBER contributor, AMBER+STRICT partner. TLP:RED is refused.

## Develop

```bash
make test        # cargo test --workspace
make lint        # fmt, clippy (native and wasm32)
make check-assurance   # spec links and scores; the coverage and quality boxes; the checker's tests first
make coverage    # test coverage (cargo llvm-cov) into target/assurance/, read by check-assurance
make quality     # code quality (lizard: CCN, function and file length)
```

`check-assurance` shows a coverage box and a code-quality box once `make coverage` and `make quality` have written their files, and says `not measured` until then. `COVERAGE_MIN=0.85` or `CCN_MAX=15` make them gates; with `CCN_MAX`, the functions in `.openspec/quality-baseline.csv` may stay over it at most at their recorded CCN, and the list may only shrink (`make quality-baseline` rewrites it). See [spec 002](.openspec/specs/002-assurance/spec.md) and [ADR-023](.openspec/architecture/decisions/023-coverage-and-code-quality-next-to-spec-assurance.md).

**Test tiers** ([ADR-018](.openspec/architecture/decisions/018-container-is-the-reference-and-test-tiers.md), #208). `make run` is for developing; the container image is what gets checked, because it is what gets deployed.

```bash
make test-slow                     # Rust tests marked #[ignore = "slow"]: volume, paging
make smoke TOKEN="…"               # read-only checks of http://127.0.0.1:8080 (FRANK_URL=…)
make smoke TLS=1 TOKEN="…"         # the same through Caddy: https://frank.local:8443, its CA, the redirect
make e2e                           # builds the image, runs it on :18080 without Caddy, generates data, checks everything
make e2e E2E_TAG=0.26.0 KEEP=1     # an existing image; keep its data directory
make e2e SSO=1                     # also sign in through the OIDC stub (scripts/sso_check.py: PKCE, cookies, CSRF, logout)
make fuzz                          # fuzz the submission parsers for FUZZ_TIME=60 s (nightly, cargo-fuzz)
make audit                         # cargo-deny: RustSec advisories, licences, sources (deny.toml)
```

`scripts/smoke.py` needs Python 3.9 or later and nothing else (macOS's own `python3` does; `PYTHON=` for another). It asks `/v1/whoami` for each token's status (`TOKEN` takes several, space separated) and checks what that status may and may not read. It never submits unless `--writable` is given, which only `make e2e` does: sightings cannot be deleted. CI runs the tests under `make coverage` and fails below 90% of lines covered (`COVERAGE_MIN`), runs `make quality` and fails on a function over CCN 15 that the baseline does not allow (`CCN_MAX`), `test-slow`, `audit` and a short `fuzz`, and runs `e2e` on the image before pushing it.

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
