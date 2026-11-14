# ADR-024: Three log streams — web, app, audit

- **Status:** Accepted
- **Date:** 2026-11-14
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-019](019-sightings-in-s3-state-on-a-volume.md) (point 3 superseded), [ADR-016](016-phase3-rust-on-db-core.md), #287, #306, #307, #308, #309

## Context

FRANK records three different things, for different readers and lifetimes:

- **What reached the edge.** Caddy terminates TLS in front of FRANK. Only Caddy sees the client's address, the TLS version, the user agent, and the requests that never reach FRANK (a 502 while it restarts, the port-80 redirect). FRANK sees every request from 127.0.0.1 and does not trust `X-Forwarded-For` (#244).
- **What FRANK did with a request.** Only FRANK knows the caller (`user@organisation`, tier) once it has resolved the token or session. Since #287 it writes one `frank::access` line per request, apart from its application lines (`frank`).
- **Who changed what.** The audit log (`crate::audit`, #159) holds one record per state-changing action: submissions, participants, users, roles, tokens, sign-ins. It is the accountability record.

ADR-019 point 3 put the audit in S3 as one object per line, for "tens of lines a day". Every submission (`submit`, `submit_refused`) and every MCP tool call (`mcp_call`) now writes one, so a feed of one submission a minute makes about 1,440 objects a day. The admin tab lists and GETs every object of its window (7 days by default, 31 at most) on each view: about 10,000 GETs for the default view. Retention is the sightings' (`FRANK_RETENTION_DAYS`), so shortening it for the data also shortens the accountability record.

#287 decided that the access log names the user in clear and keeps the query string: `user + /v1/iocs?value=…` says which organisation investigates which indicator, so the stream is kept 30 days and read only by FRANK admins.

## Decision

| Stream | Holds | Where | Retention | Readers |
|---|---|---|---|---|
| Web (Caddy) | client IP, TLS, user agent, bytes, status, the response's `X-Request-Id`; requests FRANK never sees | Caddy's access log, JSON, to stdout / journald | 30 days | FRANK admins |
| App (`frank`, `frank::access`, `mvl_manifest`) | application lines; one line per request with caller, tier, path and query (#287); at server start, the runtime manifest: version, toolchain, build provenance, every package (#315) | stdout / journald, `FRANK_LOG_FORMAT=json` | 30 days | FRANK admins |
| Audit | one record per state-changing action | a striped db-core table (`audit`) in the data directory or `FRANK_STORE` | its own, `FRANK_AUDIT_RETENTION_DAYS`, default 400 days | admins in the admin tab (their scope), superadmins all |

1. **Web and app stay two streams, joined by the request id.** Neither alone answers both "from where" and "who". FRANK returns a ULID as `X-Request-Id`; Caddy's JSON access log carries the response headers, so the id is on both lines with no extra configuration (#307). Caddy keeps `log_credentials` off, so `Authorization`, `Cookie` and `Set-Cookie` are redacted in its lines.
2. **Web and app are regular log streams.** They go to stdout as JSON, the host's journal keeps them 30 days (#308), and each deployment ships them to its own log store (STACKIT Logs, CloudWatch Logs). They are operational: short-lived, read by time range and request id, never queried across months. A column store would add nothing.
3. **The audit is a striped db-core table** (#309), like the sightings: hour files in `live/`, closed days merged in `archive/`, whole days dropped after its own retention. A view of 31 days reads about 31 files instead of one object per line, and the admin tab becomes a query (column-rs, DuckDB, `make s3-column`). Its schema: `at`, `by`, `action`, the promoted `participant` and `user`, and the remaining fields as one JSON string column, sorted by `at`. A token appears only as the first 12 hex digits of its hash, as now. This supersedes ADR-019 point 3.
4. **The CLI writes audit lines through a spool.** A db-core table has one writer (its WAL and writer lease), and the server holds it while it runs. The CLI (`frank user add`, `frank token`, `frank ingest`, through `podman exec`) appends its lines to a spool file in the data directory; the server moves them into the table on its next tick. With the server stopped, the CLI writes the table itself. The CLI keeps working whether the server runs or not, and needs no credential of its own.
5. **An audit line may wait up to an hour in the WAL.** Until its hour is flushed, a line is in the WAL on the volume, not in the bucket. Losing the volume loses up to that hour, as it does for the sightings and for `participants.db`, which the audit describes. The record stays as durable as the data it accounts for; a separate path to make the audit more durable than that would add a second write path for little gain.
6. **Reads are in the access log, not the audit.** `mcp_call` records a read (a tool call over `POST /mcp`), as `GET /v1/iocs` is a read that is not audited. It leaves the audit, and the `frank::access` line gets a `tool` field with the MCP tool's name (#309). `files_listed` stays: it is an admin looking at the data directory, which is accountability rather than use.
7. **Identities in clear, bounded instead of hidden** (#287). The access and web streams name the user and keep the query, for 30 days and for FRANK admins only. Pseudonyms (`HMAC-SHA256(FRANK_LOG_KEY, value)`, written by FRANK so the journal never holds clear identities) become the design when more people than FRANK admins read the logs, the logs go to a shared or third-party SIEM, they are needed longer than about 30 days, or partners ask. The audit keeps real identities in either case.

## Consequences

- One request can be followed from the edge to the caller with one id; a support ticket can quote it.
- Two places define the 30 days: the host's journal (#308) and each deployment's log store. A deployment that ships the streams sets the store's retention to match.
- The audit table brings db-core's WAL, flush and compaction to the audit, and one more table to rebuild or move between a filesystem and a store; the existing JSONL days (files and `audit/YYYY-MM-DD/` objects) are imported once (#309).
- Compaction rewrites audit files, so the process that writes the record can rewrite it. Bucket versioning (README) keeps earlier versions; S3 Object Lock is the stronger option if the audit has to be tamper-evident.
- Until #309 lands, the audit stays as ADR-019 point 3 describes, and `mcp_call` stays in it.
- The runtime manifest (#315, mvl-manifest) logs one record per package since mvl-manifest 0.12.1, about 160 lines of at most about 1 KB at each start. Long lines are still possible in the app stream, and a log path that cuts them breaks the JSON: podman's journald driver stores a line in 8 KiB partial entries, so the STACKIT unit uses `--log-driver passthrough` (#308).
