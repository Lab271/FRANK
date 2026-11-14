# ADR-019: Sightings in S3, the rest of the state on a volume

- **Status:** Accepted
- **Date:** 2026-11-07
- **Decision Makers:** Ilja Heitlager
- **Explained:** [docs/sightings-storage.md](../../../docs/sightings-storage.md) (write and read paths, caching, restart)
- **Related:** [ADR-016](016-phase3-rust-on-db-core.md), [ADR-018](018-container-is-the-reference-and-test-tiers.md), #220, db-core#1015 (ADR 0044 there)

## Context

The target is an AWS deployment with S3 (#220). FRANK has run on a local filesystem only: `data/sightings/` (Parquet, WAL), three SQLite-format row databases, the audit lines, lists and geo files. Each of them is a different kind of file, and an object store fits only some of them. db-core v0.234 (#1015) can keep a table's manifest and Parquet files in an S3-compatible store; its WAL, writer lock and scratch space stay on the writer's disk.

## Decision

1. **Two modes, one switch.** `FRANK_STORE` (`--store`) unset: everything on the filesystem, as before. Set to `s3://bucket/prefix?endpoint=URL&region=NAME`: the sightings' manifest and Parquet files go to that bucket through db-core's `Table::open_in`. Credentials are the AWS ones (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, the shared credentials file, an ECS task role or the EC2 instance role, the last two fetched again before they expire: db-core 0.237), never part of the URI.
2. **What stays on the volume (EFS on AWS).** The WAL (`data/s3/sightings`, apart from the local table's `data/sightings` so a switch of mode never mixes the two), `iocs.db`, `registry.db`, `participants.db`, `lists/`, the geo files. The row databases are SQLite-format files that need POSIX locks; they are small and mutable, which an object store is bad at.
3. **Audit goes to S3 too.** It is append-only text, one file a day, and S3 cannot append, so in store mode each line is one object, `audit/YYYY-MM-DD/<ns>-<pid>-<n>.jsonl` (zero-padded nanoseconds, so the sorted listing is the order; the process id and a counter keep two writers apart). Reads list the prefix; retention deletes the days' objects. The objects sit under the table's prefix; db-core's recovery only deletes unlisted files in `data/`, `live/`, `archive/` and `staging/`, so it leaves `audit/` alone. One object per line is the simple form; batching is open if the request count ever matters at FRANK's audit rate (tens of lines a day).
4. **One writer.** Garage ignores `If-Match` / `If-None-Match`, so against it db-core uses its local lock only (`SingleWriter`): a second machine on the same bucket is not refused. AWS S3 gets a fenced manifest commit and a lease. FRANK runs one writer either way.
5. **Starting from nothing.** A table in a store is created with the current schema. The rewrites of older local tables rename directories and stay local-only.
6. **Locally: Garage.** `make up S3=0` is the filesystem mode; `make up` (S3 is its default) adds a Garage container and sets `FRANK_STORE`, behind the same Caddy and URLs. The two replace each other, so one runs at a time. Garage's S3 API and admin API are published on 127.0.0.1 (3900, 3903). *Revised 2026-11-10 (#246):* the bucket's website endpoint (3902) is gone. It served the Parquet files, reporter ids included, without credentials, past the partner gate on `/v1/files`.
7. **TLS to AWS is the application's job.** db-core's `S3Store` speaks `http://` only (its dependency charter excludes a TLS stack). AWS needs a `Transport` over `ureq` and rustls, passed to `S3Store::with_transport`: a `tls` Cargo feature of FRANK (`crates/frank/src/objects.rs`), on in the container image, whose `scratch` base gets the CA bundle copied in; certificates are checked against the platform's store. The build needs a C compiler for ring's assembly (`gcc` in the build stage). t-rust-db/tools took the same route for column-rs (#125), which reads the table directly since 0.45 (`s3://…`, read-only, through the manifest; tools#123). HTTP covers every local and container test; the adapter is tested against a local server and, by hand, against Garage over HTTPS through Caddy (the local CA). A run against AWS S3 itself is still to be done once (#220).

## Consequences

- A laptop, podman and AWS run the same binary and the same layout; only `FRANK_STORE` differs.
- The AWS design needs a volume for the WAL and the row databases next to the bucket; a task replaced without its volume loses the WAL's unflushed hour.
- Garage's single-writer limit makes it a trial store, not a production one.
- *Revised 2026-11-13 (#282):* up to db-core 0.239.0 every query downloaded every listed Parquet file whole, inside the writer's lock, so each request cost the table's size in transfer and memory, and a partner fetching N files cost about N full downloads. Since db-core 0.240.0 (ADR 0045 there) a query reads a file's footer once and then only the column chunks it loads, by ranged GET, through a read cache (256 MiB, least recently used out first; listed files never change, so a cached range is never stale). Listing the files fetches none. The cache does not survive a restart: the first queries after one fetch every footer again.
- *Measured 2026-11-13 (#284)* with `crates/frank/tests/s3_requests.rs`: 30 days of sightings (33 files, 300 KB) in a counting in-memory bucket that adds 1 ms to every GET, each endpoint first in a new process (empty cache), release build. Each file's manifest records its `ts` and `received` ranges (#283, #284), so time windows skip files without a GET.

  | Endpoint (partner) | Cold GETs | Cold bytes | Peak in flight | GET latencies end to end | Warm GETs |
  |---|---:|---:|---:|---:|---:|
  | `/v1/statistics?days=30` | 1506 | 253 KB | 24 | ~560 | 0 |
  | `/v1/statistics?days=7` | 356 | 60 KB | 24 | ~140 | 0 |
  | `/v1/explore?group=rule` | 666 | 198 KB | 36 | ~450 | 0 |
  | `/v1/live?window=24h` | 40 | 9 KB | 20 | ~32 | 0 |
  | `/v1/sightings?limit=50` | 906 | 216 KB | 12 | ~490 | 0 |
  | `/v1/files` | 0 | 0 | 0 | 0 | 0 |

  The cost is the request count, not the bytes: a GET per footer and per column chunk, with up to one file's GETs in flight at a time. At AWS's 20-100 ms before the first byte, a cold 30-day statistics call takes about 11-56 s, close to `FRANK_REQUEST_TIMEOUT` (60 s); warm, every endpoint sends nothing. **Decision:** keep db-core's 256 MiB read cache, which holds the whole table at today's size, and ask db-core to coalesce adjacent ranges and fetch a file's chunks in parallel (t-rust-db/db-core#1059). The run against AWS itself, for real latencies, is #228.
- *Revised 2026-11-14 (#290):* db-core v0.241.0 (t-rust-db/db-core#1059) reads a footer with one GET of the file's last 64 KiB, which takes a smaller file whole, fetches column chunks less than 1 MiB apart as one span, and runs footers (16 at a time) and spans (8 per file, 64 per store) in parallel. The same test, same table:

  | Endpoint (partner) | Cold GETs | Cold bytes | Peak in flight | GET latencies end to end | Warm GETs |
  |---|---:|---:|---:|---:|---:|
  | `/v1/statistics?days=30` | 33 | 306 KB | 16 | ~41 | 0 |
  | `/v1/statistics?days=7` | 10 | 73 KB | 10 | ~12 | 0 |
  | `/v1/explore?group=rule` | 33 | 306 KB | 16 | ~9 | 0 |
  | `/v1/live?window=24h` | 4 | 12 KB | 4 | ~5 | 0 |
  | `/v1/sightings?limit=50` | 33 | 306 KB | 16 | ~8 | 0 |
  | `/v1/files` | 0 | 0 | 0 | 0 | 0 |

  A cold 30-day statistics call is about 1-4 s at AWS latencies, well inside `FRANK_REQUEST_TIMEOUT`. Every test file is under 64 KiB, so each is read whole in its footer GET (one GET per kept file; more bytes than the chunks alone). The test now asserts that bound; larger day files go through span fetches, which it does not measure (#228). The 256 MiB cache decision stands.
