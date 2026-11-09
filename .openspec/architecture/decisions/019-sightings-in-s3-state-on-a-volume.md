# ADR-019: Sightings in S3, the rest of the state on a volume

- **Status:** accepted
- **Date:** 2026-11-07
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-016](016-phase3-rust-on-db-core.md), [ADR-018](018-container-is-the-reference-and-test-tiers.md), #220, db-core#1015 (ADR 0044 there)

## Context

The target is an AWS deployment with S3 (#220). FRANK has run on a local filesystem only: `data/sightings/` (Parquet, WAL), three SQLite-format row databases, the audit lines, lists and geo files. Each of them is a different kind of file, and an object store fits only some of them. db-core v0.234 (#1015) can keep a table's manifest and Parquet files in an S3-compatible store; its WAL, writer lock and scratch space stay on the writer's disk.

## Decision

1. **Two modes, one switch.** `FRANK_STORE` (`--store`) unset: everything on the filesystem, as before. Set to `s3://bucket/prefix?endpoint=URL&region=NAME`: the sightings' manifest and Parquet files go to that bucket through db-core's `Table::open_in`. Credentials are the AWS ones (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, the shared credentials file, an ECS task role or the EC2 instance role, the last two fetched again before they expire: db-core 0.237), never part of the URI.
2. **What stays on the volume (EFS on AWS).** The WAL (`data/s3/sightings`, apart from the local table's `data/sightings` so a switch of mode never mixes the two), `iocs.db`, `registry.db`, `participants.db`, `lists/`, the geo files. The row databases are SQLite-format files that need POSIX locks; they are small and mutable, which an object store is bad at.
3. **Audit goes to S3 too.** It is append-only text, one file a day, and S3 cannot append, so in store mode each line is one object, `audit/YYYY-MM-DD/<ns>-<pid>-<n>.jsonl` (zero-padded nanoseconds, so the sorted listing is the order; the process id and a counter keep two writers apart). Reads list the prefix; retention deletes the days' objects. The objects sit under the table's prefix; db-core's recovery only deletes unlisted files in `data/`, `live/`, `archive/` and `staging/`, so it leaves `audit/` alone. One object per line is the simple form; batching is open if the request count ever matters at FRANK's audit rate (tens of lines a day).
4. **One writer.** Garage ignores `If-Match` / `If-None-Match`, so against it db-core uses its local lock only (`SingleWriter`): a second machine on the same bucket is not refused. AWS S3 gets a fenced manifest commit and a lease. FRANK runs one writer either way.
5. **Starting from nothing.** A table in a store is created with the current schema. The rewrites of older local tables rename directories and stay local-only.
6. **Locally: Garage.** `make up-solo` (alias `make up`) is the filesystem mode; `make up-s3` adds a Garage container and sets `FRANK_STORE`, behind the same Caddy and URLs. The two replace each other, so one runs at a time. Garage's S3 API, web endpoint and admin API are published on 127.0.0.1 (3900, 3902, 3903). The web endpoint serves the bucket's objects by key **without credentials**; it is for a laptop only.
7. **TLS to AWS is the application's job.** db-core's `S3Store` speaks `http://` only (its dependency charter excludes a TLS stack). AWS needs a `Transport` over `ureq` and rustls, passed to `S3Store::with_transport`: a `tls` Cargo feature of FRANK (`crates/frank/src/objects.rs`), on in the container image, whose `scratch` base gets the CA bundle copied in; certificates are checked against the platform's store. The build needs a C compiler for ring's assembly (`gcc` in the build stage). t-rust-db/tools took the same route for column-rs (#125), which reads the table directly since 0.45 (`s3://…`, read-only, through the manifest; tools#123). HTTP covers every local and container test; the adapter is tested against a local server and, by hand, against Garage over HTTPS through Caddy (the local CA). A run against AWS S3 itself is still to be done once (#220).

## Consequences

- A laptop, podman and AWS run the same binary and the same layout; only `FRANK_STORE` differs.
- The AWS design needs a volume for the WAL and the row databases next to the bucket; a task replaced without its volume loses the WAL's unflushed hour.
- Garage's single-writer limit makes it a trial store, not a production one.
