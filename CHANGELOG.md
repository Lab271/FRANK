# Changelog

All notable changes to FRANK. Format follows [Keep a Changelog](https://keepachangelog.com/), versioning follows [SemVer](https://semver.org/). Phase 2 (Python) releases up to 0.8.0 are tagged in git; its final state is `phase2-final`.

## [Unreleased]

### Added

- `docs/performance.md`: what a query costs against S3, the layers that brought a cold 30-day statistics call from 1,506 GETs to 33 and to none after the warm-up, how it is measured and what is not yet.
- `docs/mcp.md`: connecting an AI assistant to FRANK over MCP, the tools, what each tier sees, and troubleshooting.

## [0.51.3] - 2026-11-14

### Fixed

- SSO sign-in no longer provisions a new user when the store fails during the lookup of the e-mail's user; it refuses the sign-in with the store's error (#312).

### Changed

- `make check-assurance`: the spec box shows the version, and a version that disagrees between `Cargo.toml`, both `Cargo.lock`, the README and the CHANGELOG fails the gate; CI's separate `make version` step is gone.

## [0.51.2] - 2026-11-14

### Changed

- CI: the slow tests run in parallel with the others, and the image build reuses cached layers (#313).
- Internal: the 15 most complex functions are split into named steps with no change in behaviour; no function in `crates/*/src` is over CCN 15, and the CCN baseline is empty (#302).

## [0.51.1] - 2026-11-14

### Changed

- `make check-assurance`: a spec's `**Tests:**` link must name a `#[test]` function, and `make quality` no longer reports lizard's fan-in and fan-out (#298).
- CI runs the workspace tests under `cargo llvm-cov` and gates on 90% of lines covered and on CCN 15, with the functions allowed over it listed in `.openspec/quality-baseline.csv`, which can only shrink (#299, #301).
- The `frank` admin subcommands and `serve` moved out of `main.rs` into `frank::cli` and `frank::serve`; the command line is unchanged (#300).

## [0.51.0] - 2026-11-14

### Added

- Access log (#287): one INFO line per request under `frank::access` with request id, path and query, status, latency, caller and tier. `FRANK_LOG_FORMAT=json` writes one JSON object per line. Tokens, the `Authorization` header, the session cookie, bodies and the SSO callback's query are never logged.

## [0.50.0] - 2026-11-14

### Added

- S3 mode: on start, after flushing and compacting, FRANK warms db-core's read cache with one query over every listed file, so the first caller after a restart sends no cold GETs (#291). Over 30 days that is 33 GETs, one per file, then none for the first statistics, explore and records calls. Logged as `read cache warmed`; errors only warn.

## [0.49.0] - 2026-11-14

### Added

- `deploy/stackit` outputs `data_volume_id`, so a deployment can put a backup schedule on the data volume (test-frank#7).

### Changed

- db-core v0.241.0 (#290): in S3 mode a cold query reads each footer in one GET (a file up to 64 KiB whole), fetches nearby column chunks together, and reads footers and chunks in parallel. Over 30 days, a cold `/v1/statistics?days=30` sends 33 GETs instead of 1,506, about 41 one after another instead of 560; warm calls still send none. `tests/s3_requests.rs` now bounds a cold call at one GET per kept file; ADR-019 and `docs/sightings-storage.md` hold the new numbers.

## [0.48.0] - 2026-11-14

### Added

- `make coverage` (cargo llvm-cov) and `make quality` (lizard: CCN, function and file length, approximate fan-in/out) measure on their own into `target/assurance/`; `make check-assurance` shows both and can gate on `COVERAGE_MIN` and `CCN_MAX` (#293, #294).

## [0.47.0] - 2026-11-14

### Changed

- `deploy/stackit`: the sightings bucket has `prevent_destroy`, like the data volume: a plan that would replace or remove it fails. The README says how to remove it on purpose (`tofu state rm`) and what a rebuilt VM, a lost volume and a lost bucket each keep and lose (#286).

## [0.46.0] - 2026-11-13

### Changed

- db-core v0.240.1 (#282): in S3 mode a query reads each Parquet file's footer once and then only the column chunks it needs, by ranged GET, through a 256 MiB read cache; it used to download every listed file whole on every query, inside the writer's lock. Listing `/v1/files` fetches no file.
- The sightings manifest records each file's `ts` range, so the API's time windows skip the files outside them without reading them, which in S3 mode saves the footer GETs (#283). Files written before keep no range and are always read.
- The manifest records each file's `received` range too, so `/v1/live`'s arrival window skips files: 40 cold GETs instead of 98 over 30 days (#284). `crates/frank/tests/s3_requests.rs` counts the requests each endpoint sends to a store, cold and warm; ADR-019 holds the numbers.
- db-core prints TIMESTAMP results as ISO text since 0.238; FRANK reads `ts` and `received` through `store::sightings::nanos`, which takes either form.

## [0.45.0] - 2026-11-13

### Added

- `deploy/stackit`: the VM fetches the DB-IP Lite GeoIP databases monthly and the IoC lists daily (systemd timers `frank-geoip`, `frank-lists`), first right after boot; `abuse_key` adds URLhaus and ThreatFox (#276).

### Changed

- `make geoip` and `make lists` run `scripts/fetch-geoip.sh` and `scripts/fetch-lists.sh`, the scripts the STACKIT VM runs (#276).

## [0.44.0] - 2026-11-12

### Changed

- Web UI: the eight spec 030 scenarios without tests now run in a browser (Obscura) in `make e2e BROWSER=1`, and in CI before the image is pushed.

### Fixed

- Web UI: the theme button works whatever the load timing; a stale startup sign-in check can no longer drop a signed-in user to public.

## [0.43.0] - 2026-11-12

### Added

- `deploy/stackit` (OpenTofu): SSH is off by default (`admin_cidr` and `ssh_public_key` optional); commands go through the STACKIT Server Agent (#266).
- `deploy/stackit`: `store_bucket` puts the sightings and the audit log in a STACKIT Object Storage bucket (`FRANK_STORE`), with its credential in a 0600 env file (#266).

### Changed

- `deploy/stackit`: `image` has no `:latest` default; pin a commit (#266).

### Fixed

- `deploy/stackit`: the Debian image is picked by name, the x86 "Debian 13" (the filter also matched ARM64); the provider enables beta resources for the image lookup (#266).

## [0.42.0] - 2026-11-12

### Changed

- Spec `013-sso` is `012-sso`, the number kept for OIDC authentication; 013 is disclosure only (#269).
- `make check-assurance` opens with a dashboard: the verdict, implemented and tested as bars, dead links, then a bar per spec in green, yellow or red against the floor. Colour on a terminal or in GitHub Actions; `NO_COLOR` turns it off (#269).

## [0.41.0] - 2026-11-11

### Added

- An MCP server on `POST /mcp` (#263): the Model Context Protocol over Streamable HTTP, with nine read-only tools that answer as their `/v1` routes do for the caller's credentials. Each tool call is audited.

## [0.40.0] - 2026-11-10

### Added

- Sign in with SSO over OpenID Connect (#241, ADR-020): PKCE authorization code flow at `/v1/sso/login`, `/v1/sso/callback`, `/v1/sso/logout`; off unless all five `FRANK_SSO_` settings are given (some but not all: `frank serve` refuses to start). The client secret is read from `FRANK_SSO_CLIENT_SECRET_FILE`, never from the environment, and never logged, audited or returned.
- People are provisioned on first sign-in: a human user with no role in `FRANK_SSO_ORGANISATION`, named by the lower-cased e-mail; an existing human user with the same verified e-mail is linked and keeps its organisation and role. New `sso_subjects` and `sessions` tables in `participants.db`, created on open. Audit lines `user_provisioned`, `sso_login`, `sso_refused`, `sso_logout`.
- The `frank_session` cookie (HttpOnly, SameSite=Lax, Secure on https, 8 h, stored as its SHA-256) names the caller only without an `Authorization` header: bearer tokens work as before and always win. A write with the cookie needs FRANK's own `Origin`. Disabling a user ends its sessions.
- `make up-sso` and `make e2e SSO=1`: a development-only Python OIDC stub (`deploy/podman/sso-stub`) at `http://localhost:9400`, in the frank container's network.
- Web UI: "sign in with SSO" when SSO is on, the signed-in user, "sign out"; a refused sign-in says so.
- Spec 013-sso; `openapi.yaml` documents the `/v1/sso` routes and the cookie scheme. `ureq` is now a regular dependency.

### Changed

- `ureq` is a regular dependency (the identity provider's HTTPS calls); the `tls` feature still only gates the S3 TLS adapter.

## [0.39.0] - 2026-11-10

### Security

- A plain admin in a core organisation could issue a token for that organisation's superadmin, and so act as it, or revoke its tokens. Issuing and revoking a superadmin's token now needs a superadmin, like every other change to one (#242).

### Added

- Every response, the web UI included, carries a Content-Security-Policy, `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. A request not answered within `FRANK_REQUEST_TIMEOUT` (60 s, waiting included) gets 503, and at most `FRANK_MAX_CONCURRENCY` (64) requests run at once. Caddy sets HSTS: a year on STACKIT, a day on `FRANK_HOST` in podman (#244).
- A table-driven test of every admin endpoint for every kind of caller and target (#243). `make fuzz` and a CI job fuzz the submission parsers, and `make audit` runs `cargo deny check` (#245).
- The Phase 3 specs 001 data model, 010 sightings API, 013 disclosure, 014 query API, 020 sightings storage, 021 IoC lookups and 030 browser client (#250). They link 88 requirements to code and 172 of 180 scenarios to tests.
- Added `make assurance` and `make check-assurance` (`scripts/assurance.py`, ADR-021): every spec `**Implementation:**`/`**Tests:**` link and every relative Markdown link in the docs must resolve, and CI runs the gate. Replaces `.openspec/validate.py` and the spec-validation workflow, which never ran.

### Changed

- The theme script is `web/theme.js` instead of inline in `index.html`, so the CSP allows no inline script (#244).
- ADR-016 §3: a target's identity is accepted and not stored, so no status sees it; the ADR said core would (#256).
- `make check-assurance` covers every Rust scenario; the floor is 95% (`ASSURANCE_MIN`), the rest being web UI scenarios marked planned (#254).
- ADRs that Phase 3 replaced are marked superseded (001, 003, 004, 005, 007, 011, 013) or deprecated (012, 014, 015); one status format; cross-links fixed; `decisions/index.md` added.
- `.openspec/README.md`, `docs/glossary.md` and the PR template describe Phase 3.

### Fixed

- `/v1/iocs` below partner leaves out rules reported by fewer than 3 participants and answers `reporters` as null under 3, as Explore and `/v1/rules/{id}` do (#255). `known`, `count` and `days` are unchanged.
- `iocs.db` counts an IoC on the day its sightings arrived, the clock the sightings' retention uses, so a sighting dated before it arrived keeps its IoC as long as its rows (#257). `first_seen` is still the sightings' own time.
- The new-token card reads "shown once" after a `·` instead of a backslash (#258).

### Removed

- `make up-s3` no longer serves the Garage bucket as a website on `:3902`: that endpoint served the Parquet files, reporter ids included, without credentials (#246).
- The Phase 2 specs 001–004, which the data model spec replaces.
- The Phase 2 documents (specs 010, 012, 020–023, 030, 040, the architecture YAML, the design documents under `docs/`); they are at the tag `phase2-final`. Specs 001–004 are marked Outdated until their Phase 3 rewrite (#250).

## [0.38.2] - 2026-11-09

### Fixed

- `make stream` (`scripts/stream_sightings.py`) resends only a sender's own sightings, so the watcher no longer reports false mismatches.

## [0.38.1] - 2026-11-09

### Fixed

- The statistics tab reloads its numbers every time it is opened, not only on the first load and the refresh button.

## [0.38.0] - 2026-11-09

### Added

- Header theme button cycles auto / light / dark; the choice is kept in localStorage (`frank.theme`), auto follows the OS.

## [0.37.0] - 2026-11-09

### Added

- With `FRANK_STORE`, FRANK signs with an ECS task role or the EC2 instance role (IMDSv2) when no keys are in the environment or the shared credentials file, and fetches the role's credentials again before they expire (db-core 0.237, #228).

### Changed

- db-core 0.235.0 to 0.237.0.

## [0.36.0] - 2026-11-09

### Added

- AWS S3 over HTTPS: a `tls` Cargo feature (on in the container image, with the CA bundle copied in) sends db-core's S3 requests through `ureq` and rustls. `deny.toml` and `cargo deny check` in CI (#220).
- `S3=1 make e2e` runs the end-to-end check against a throwaway Garage and checks that the sightings are in the bucket (#220).
- README: "Storage: filesystem or S3", with the copy that switches mode on an existing install; tested both ways (#220).
- With `FRANK_STORE` the audit log lives in the store too: one object per line under `audit/YYYY-MM-DD/<ns>-<pid>-<n>.jsonl`, listed by prefix for reads, whole days dropped with the retention (#220).

## [0.35.0] - 2026-11-08

### Changed

- `make s3-column` reads over HTTPS by default; `TLS=0` reads over http and `URL=s3://…` reads any location; it prints the location first (#220).

## [0.34.0] - 2026-11-08

### Added

- `make up-s3` serves Garage's S3 API over HTTPS at `https://frank.local:9443` (`GARAGE_TLS_PORT`) through Caddy, with the same local CA as FRANK; `make s3-column TLS=1` reads there with column-rs 0.46+ built with `--features s3-tls` (#224).

## [0.33.0] - 2026-11-07

### Added

- The sightings can live in S3: `FRANK_STORE=s3://bucket/prefix?endpoint=…&region=…` (`--store`) keeps the manifest and the Parquet files in a bucket, through db-core 0.234's `storage-s3`; the WAL stays on the local volume in `data/s3/sightings`. Unset, nothing changes. `/v1/files/…` reads through the store, and the log says where the sightings are (the location carries no credentials: the key comes from the AWS environment). The audit lines and the TLS client for AWS follow (#220, [ADR-019](.openspec/architecture/decisions/019-sightings-in-s3-state-on-a-volume.md)).
- `make up-s3`: the podman deployment with a Garage (S3) container holding the sightings, behind the same Caddy and URLs; the S3 API, the bucket's web endpoint and the admin API on 127.0.0.1:3900, :3902 and :3903. `make s3-ls` lists the bucket, `make s3-browse` browses it with `rclone ncdu`, `make s3-read` (`scripts/read-garage.sh`) opens DuckDB on the sightings the manifest lists, `make s3-column` (`scripts/read-garage-column.sh`) opens column-rs 0.45+ on the table directly, through its manifest (t-rust-db/tools#123). `make up-solo` is the filesystem mode, `make up` its alias; `make down`, `make trust` and `make untrust` work for both (#220).

### Changed

- db-core 0.221.0 to 0.235.0.
- `make up` and `make down` now name the compose project with `PROJECT=` when given, and `make up` removes containers of the other mode.

## [0.32.0] - 2026-11-07

### Added

- Admin tab: a superadmin browses the server's data and participants directories (`GET /v1/admin/files`): names, sizes and times, never contents. Each listing is audited (#222).

## [0.31.0] - 2026-11-07

### Added

- Web UI footer shows the FRANK and API versions.

## [0.30.0] - 2026-11-06

### Added

- `make check-mvl-limit` (part of `make lint` and CI): `frank-core` must stay in the qualified Rust subset (no `unsafe`, `dyn`, explicit lifetimes or non-allowlisted macros), checked with `cargo-mvl-limit` from mvl-rust, as in t-rust-db. The `frank` and `frank-wasm` crates are exempt as I/O boundaries (#217).

### Changed

- `frank-core`'s STIX reader owns its object index instead of borrowing it, and the string-field helpers in `model.rs` drop their explicit lifetimes, to fit the subset (#217).

## [0.29.0] - 2026-11-05

### Added

- Every image pushed from `main` is signed (keyless `cosign`) and carries a CycloneDX SBOM and an SLSA build-provenance attestation, by digest. The binary is built with `cargo auditable`, so scanners can read its crates in a scratch image. Verify with the commands in ADR-018, item 9 (#213).

### Changed

- The image is a static musl binary on `FROM scratch`: no third-party runtime base, no libc, CA certificates or tzdata. The build image is pinned by its digest (#211).

### Fixed

- User names may contain `+`, for plus-addressed e-mail (#215).

## [0.28.1] - 2026-11-03

### Fixed

- `GET /v1/sightings` with an IoC filter (`ioc=`, `ioc_type=`) reads one page of matching sighting ids instead of all of them, and fetches their records at most 100 ids per query. The crash itself (a stack overflow from a long `IN` list) was fixed by db-core in 0.28.0; this keeps each page's work bounded as the data grows (#201).

## [0.28.0] - 2026-10-30

### Changed

- **Breaking (partners' files):** in the `sightings` Parquet files, `sighting_id` (16 bytes) and `digest` (32 bytes) are now binary, a `BLOB` in DuckDB, and `digest` is on the `seq = 0` row only. Read them with `lower(hex(digest))`; the `sighting--` form is in the `/v1/files` docs. The API, receipts and STIX are unchanged (#200).
- The table is rewritten once on the first start (backup in `sightings.pre-binary`), and `registry.db` is rebuilt. On the demo data the table is 19% smaller (#200).
- db-core v0.217.2: a long IoC filter on `/v1/sightings` no longer overflows the stack (db-core#901, see #201), and the browser module builds again (db-core#898).

### Fixed

- Analyse tab: a count or sum given a name (`count(*) AS sightings`, as in the default query) now adds up across files instead of showing one row per file.

## [0.27.0] - 2026-10-30

### Added

- **`http://frank.local` redirects to HTTPS**: Caddy in the podman deployment now also listens on port 80 (`FRANK_HTTP_ADDR`) and sends every request with a 307 to `https://frank.local:8443`, keeping the path and query. The API address `http://127.0.0.1:8080` stays as it is.

## [0.26.0] - 2026-10-30

### Added

- **HTTPS locally**: `make up` serves FRANK at `https://frank.local:8443` through Caddy, with a certificate from Caddy's local certificate authority, as on STACKIT. `make trust` (once, with `sudo`) adds that authority to the macOS keychain and `frank.local` to `/etc/hosts`; `make untrust` removes the authority again. Plain HTTP stays on `127.0.0.1:8080`. `FRANK_HOST` changes the name; `FRANK_TLS_ADDR=443` gives `https://frank.local`, reachable from the local network too.

## [0.25.0] - 2026-10-30

### Added

- **Where the addresses are** (#195): the Live tab shows the top 10 countries, with flags, and the top 10 networks of the window's IP addresses, each with its distinct IoCs and reporters. Below partner a country or network needs 3 reporters to be shown. Warning-listed addresses (public DNS, reserved ranges) are left out unless "show warning-listed" is ticked. `GET /v1/live` returns them as `places`.

## [0.24.0] - 2026-10-30

### Added

- **Reserved addresses are marked** (#192): `make lists` adds MISP's warning lists for private (RFC 1918), documentation (RFC 5737, RFC 3849), shared, link-local and multicast ranges. A sensor reporting such an address is greyed out instead of looking like an indicator. The UI says "warning list" for these and for public DNS resolvers.
- **URLhaus and ThreatFox work again** (#193): abuse.ch moved its exports behind an Auth-Key. `make lists` reads it from 1Password (`ABUSE_KEY_REF`) and skips those two lists when there is none. A download that fails now stops `make lists` instead of passing quietly.
- **Demo and stream from abuse.ch data**: with `data/lists`, `make demo` and `make stream` send 15 campaigns built from ThreatFox, URLhaus and Feodo Tracker. They cover about 90 real addresses from about 30 countries, some listed and some on no list. Real addresses come only from abuse.ch.
- **Faster start**: the server listens right away instead of after importing every list.

## [0.23.0] - 2026-10-30

### Added

- **Country and network of IP addresses** (#191): DB-IP Lite country and ASN in the lookup, the IoC pane and the live feed, and for partners as `geo/ip_geo.parquet` next to the sightings files. `make geoip` downloads the databases (no account needed); without them FRANK works as before, and `/health` shows `geoip: missing`.
- **Common infrastructure is marked** (#192): IoCs on a warning list (MISP's public DNS resolvers via `make lists`, or your own files in `data/lists/warning/`) are greyed out and left out of the converging list and Explore's IoC ranking unless `common=include` / "show common infrastructure". Counts are unchanged.
- **Reference lists** (#193): what abuse.ch URLhaus, ThreatFox and Feodo Tracker list about an IoC is shown as context ("listed by … since …"), also in lookups of IoCs FRANK has not seen. Explore by IoC filters on `listed=any|none|<list>`, so "listed nowhere" finds what participants see that no list has yet.

## [0.22.0] - 2026-10-30

### Added

- **Live tab** (#186): the IoCs of the sightings that arrived in the last hour, 6 hours or 24 hours, refreshed every 15 s. Each IoC is marked new or "since <day>", there is a list of IoCs two or more participants report, and there are counters and arrivals per bar. Contributor and up; below partner an IoC needs 3 reporters to be listed, as in Explore.
- `GET /v1/live?window=1h|6h|24h`: the same, for machine clients.

## [0.21.0] - 2026-10-29

### Changed

- **Techniques are a `LIST<UTF8>` column, `techniques`** (db-core 0.201): ranked with `UNNEST(techniques)` and filtered with `list_contains(techniques, …)` instead of `LIKE` on a joined string.
- **Breaking for readers of the Parquet files:** the comma-separated `technique` column is gone; read `techniques` (`VARCHAR[]` in DuckDB, `list<string>` in pyarrow).
- At startup, a table that still has `technique` is rewritten once to the new schema. Every row keeps the hour and day it arrived in, and the old table is kept as `data/sightings.pre-list/` (delete it once checked). The rewrite refuses to start while that directory exists.

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
