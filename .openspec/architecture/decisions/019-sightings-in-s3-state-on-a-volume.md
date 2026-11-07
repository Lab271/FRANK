# ADR-019: Sightings in S3, the rest of the state on a volume

- **Status:** accepted
- **Date:** 2026-11-07
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-016](016-phase3-rust-on-db-core.md), [ADR-018](018-container-is-the-reference-and-test-tiers.md), #220, db-core#1015 (ADR 0044 there)

## Context

The target is an AWS deployment with S3 (#220). FRANK has run on a local filesystem only: `data/sightings/` (Parquet, WAL), three SQLite-format row databases, the audit lines, lists and geo files. Each of them is a different kind of file, and an object store fits only some of them. db-core v0.234 (#1015) can keep a table's manifest and Parquet files in an S3-compatible store; its WAL, writer lock and scratch space stay on the writer's disk.

## Decision

1. **Two modes, one switch.** `FRANK_STORE` (`--store`) unset: everything on the filesystem, as before. Set to `s3://bucket/prefix?endpoint=URL&region=NAME`: the sightings' manifest and Parquet files go to that bucket through db-core's `Table::open_in`. Credentials are the AWS ones (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or the shared credentials file), never part of the URI.
2. **What stays on the volume (EFS on AWS).** The WAL (`data/s3/sightings`, apart from the local table's `data/sightings` so a switch of mode never mixes the two), `iocs.db`, `registry.db`, `participants.db`, `lists/`, the geo files. The row databases are SQLite-format files that need POSIX locks; they are small and mutable, which an object store is bad at.
3. **Audit goes to S3 too**, in a later change (#220): it is append-only text, one file a day, and S3 cannot append, so it becomes one object per batch.
4. **One writer.** Garage ignores `If-Match` / `If-None-Match`, so against it db-core uses its local lock only (`SingleWriter`): a second machine on the same bucket is not refused. AWS S3 gets a fenced manifest commit and a lease. FRANK runs one writer either way.
5. **Starting from nothing.** A table in a store is created with the current schema. The rewrites of older local tables rename directories and stay local-only.
6. **Locally: Garage.** `make up-solo` (alias `make up`) is the filesystem mode; `make up-s3` adds a Garage container and sets `FRANK_STORE`, behind the same Caddy and URLs. The two replace each other, so one runs at a time. Garage's S3 API, web endpoint and admin API are published on 127.0.0.1 (3900, 3902, 3903). The web endpoint serves the bucket's objects by key **without credentials**; it is for a laptop only.
7. **TLS to AWS is the application's job.** db-core's `S3Store` speaks `http://` only (its dependency charter excludes a TLS stack). AWS needs a `Transport` over `ureq` and rustls, a `tls` Cargo feature of FRANK, in a later change (#220).

## Consequences

- A laptop, podman and AWS run the same binary and the same layout; only `FRANK_STORE` differs.
- The AWS design needs a volume for the WAL and the row databases next to the bucket; a task replaced without its volume loses the WAL's unflushed hour.
- Garage's single-writer limit makes it a trial store, not a production one.
