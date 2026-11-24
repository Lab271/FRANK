# ADR-027: The server stays a native binary; no WASI build

- **Status:** Accepted
- **Date:** 2026-11-24
- **Decision Makers:** Ilja Heitlager
- **Related:** [ADR-016](016-phase3-rust-on-db-core.md) (Rust on db-core, `frank-wasm` in the browser), [ADR-018](018-container-is-the-reference-and-test-tiers.md) (the container image is the reference), [ADR-019](019-sightings-in-s3-state-on-a-volume.md) (sightings in S3, state on a volume)

## Context

The question was whether `frank serve` could run as a server-side WebAssembly container (WASI preview 2: crun's WASM handler under podman, wasmtime or Spin) instead of the static musl binary in a `FROM scratch` image.

A build for `wasm32-wasip2` and `wasm32-wasip1` (db-core v0.241.0, tokio 1.54) showed what it would take:

| Part | Builds for WASI |
|---|---|
| `frank-core` | yes |
| db-core `ingest`, `engine-column`, `storage-column-write`, `storage-s3` | yes |
| `ring`, `ureq` with rustls | yes (outbound sockets at runtime not tried) |
| db-core `engine-row` (`iocs.db`, `registry.db`, `participants.db`, lists, geo) | no: its VFS uses `std::os::unix`, positional reads and writes, `fcntl` locks and shared memory |
| tokio `rt-multi-thread`, `signal`, `net` (axum's listener) | no: tokio on wasm offers `sync`, `macros`, `io-util`, `rt` and `time` only |

FRANK also relies on threads: one thread owns each row database (`store/rowdb.rs`), and `serve.rs`, `api.rs` and `sso.rs` use `spawn_blocking`. WASI preview 2 has no threads.

## Decision

1. **The server stays native**: the static musl binary in the `FROM scratch` image, under podman on a VM (ADR-018). There is no `wasm32-wasi*` build of `frank`, and none is checked in CI.
2. **WebAssembly stays in the browser**: `frank-wasm` (`wasm32-unknown-unknown`, ADR-016), where it lets the client check and query files without trusting the server.
3. **If participants ever send their own code** (a query or filter to run on the server), that code runs in a WASM sandbox inside the native server, not the server inside WASM.

## Reasons

- **Scanning Parquet costs more in WASM.** Decompression and column decoding get 128-bit SIMD only (no AVX2, AVX-512 or the host's full NEON), no threads to scan files or row groups in parallel, no `mmap`, every WASI read copied into linear memory, and at most 4 GiB of it on `wasm32`. A query over the sightings would be slower, by an amount not measured here but expected to be a multiple for heavy scans.
- **WASM's strengths do not apply.** Fast cold starts and dense packing help many short-lived or idle tenants; FRANK is one long-running process with a WAL on a local volume and one writer per bucket (ADR-019), so it neither scales out nor idles to zero. Sandboxing helps untrusted code; the server runs FRANK's own. A small, portable artifact FRANK already has in the scratch image.
- **The port is large.** It needs a WASI storage layer for db-core's row engine (or moving those databases elsewhere), a single-threaded server without `spawn_blocking` or per-database threads, a listener from the host (`wasi:http`) or WASI sockets, and new homes for the background work (flush, compaction, audit spool, retention).
- **The runtime is not where FRANK runs.** Debian's podman on the AWS and STACKIT VMs has not been shown to have a WASM handler; the local podman machine (Fedora) has crun with WasmEdge, a different runtime from wasmtime, with weaker preview 2 support.

## Consequences

- Deployments keep launching a VM (or another host) with the native image; nothing changes for AWS, STACKIT or `make up`.
- The question is reopened only by a new need, such as running participants' code on the server (decision 3) or a host that only runs WASM, and with a measurement of a sightings query native against WASM.
