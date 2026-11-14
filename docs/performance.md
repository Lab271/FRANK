# Performance: reading sightings from S3

FRANK v0.51 on db-core v0.241.0, with `FRANK_STORE=s3://…`. How the sightings are stored is in [sightings-storage.md](sightings-storage.md); this page is about what a query costs and how that came down. The decisions are in [ADR-019](../.openspec/architecture/decisions/019-sightings-in-s3-state-on-a-volume.md) here and ADR 0045 in [db-core](https://github.com/t-rust-db/db-core).

## In short

With an object store, a query's cost is the **number of requests**, not the bytes: AWS S3 takes 20-100 ms before the first byte of every GET. Between FRANK v0.45 and v0.50 a cold 30-day statistics call went from downloading every file whole, to 1,506 ranged GETs, to 33. After a restart FRANK now fetches those 33 itself before the first caller arrives.

| A cold `/v1/statistics?days=30` over 30 days | GETs | One after another | At AWS latencies |
|---|---:|---:|---|
| db-core v0.240 (FRANK v0.46) | 1,506 | ~560 | 11-56 s, close to the 60 s request timeout |
| db-core v0.241 (FRANK v0.49) | 33 | ~40 | about 1-4 s |
| After the start-up warm-up (FRANK v0.50) | 0 | 0 | as fast as a warm call |

The AWS column is an estimate: the GETs one after another times 20-100 ms. The run against AWS itself is #228.

## The layers, from the bucket up

| Layer | What it does | Since |
|---|---|---|
| **Striping** | One Parquet file per closed hour in `live/`, one per closed day in `archive/`; zstd, row groups of 64k rows, sorted by `rule_id`, `ioc_value` | Phase 3 (ADR-016) |
| **Manifest ranges** | `manifest.json` keeps each file's min and max of `rule_id`, `ioc_value`, `ts` and `received`. A file outside a query's window costs no request at all | v0.46.0 (#283, #284) |
| **WAL and pages** | The open hour is in memory and read from there; the WAL on the volume is only read back on start | db-core |
| **Held files** | A file's footer is fetched and parsed once and kept while the manifest lists the file | db-core v0.240 (#1052) |
| **Ranged reads** | A query fetches the footer and only the column chunks it loads, never the whole file | db-core v0.240 (#1052) |
| **RangeCache** | What was fetched stays in memory, 256 MiB, least recently used out first. Listed files never change, so a cached range is never stale | db-core v0.240 (#1052) |
| **Fewer, wider GETs** | One GET for a footer (the file's last 64 KiB, which takes a smaller file whole); chunks less than 1 MiB apart in one GET; footers 16 at a time, a file's spans 8 at a time, at most 64 GETs per store | db-core v0.241 (db-core#1059), FRANK v0.49.0 (#290) |
| **Warm-up** | On start, after flush and compaction, one query over every listed file fills the cache | v0.50.0 (#291) |

In filesystem mode (no `FRANK_STORE`) the files are memory-mapped and the operating system's page cache does the caching; none of the S3 layers apply.

## What each step bought

**Footers parsed once** (db-core v0.240). Every query used to decode every file's footer again, about 7 ms for a large day file. On a local table of 300 files, a query went from 6.1 to 2.5 ms (db-core [PR #1055](https://github.com/t-rust-db/db-core/pull/1055)).

**Ranged reads** (db-core v0.240, FRANK v0.46). Up to db-core 0.239, every query downloaded every listed file whole, inside the writer's lock, so memory and transfer grew with the table. Now only footers and the needed chunks are fetched, and the same query again sends nothing.

**Time windows skip files** (FRANK v0.46). With `ts` and `received` ranges in the manifest, `/v1/live?window=24h` went from 98 to 40 cold GETs over 30 days.

**Fewer, wider GETs** (db-core v0.241, FRANK v0.49). The same 30-day table, each endpoint called first from a new process:

| Endpoint | Cold GETs, v0.240 → v0.241 | One after another | Warm GETs |
|---|---:|---:|---:|
| `/v1/statistics?days=30` | 1,506 → **33** | ~560 → **~40** | 0 |
| `/v1/statistics?days=7` | 356 → **10** | ~140 → **~10** | 0 |
| `/v1/explore?group=rule` | 666 → **33** | ~450 → **~8** | 0 |
| `/v1/live?window=24h` | 40 → **4** | ~32 → **~5** | 0 |
| `/v1/sightings?limit=50` | 906 → **33** | ~490 → **~7** | 0 |
| `/v1/files` | 0 → 0 | 0 | 0 |

**Warm-up** (FRANK v0.50). The start-up warm-up sends one GET per listed file (33, about 5 one after another, 16 at a time), and then the first statistics, explore and records calls send none. It logs `read cache warmed` with the number of files and the time it took; an error only warns.

## How it is measured

```bash
cargo test --release -p frank --test s3_requests -- --nocapture
```

[`crates/frank/tests/s3_requests.rs`](../crates/frank/tests/s3_requests.rs) writes 30 days of sightings (33 files, 306 KB) into an in-memory bucket that counts requests and adds 1 ms to every GET. Each endpoint runs first in a new process (an empty cache, as after a restart), then again; the last block runs the warm-up and checks that the first calls after it send nothing. "One after another" is the call's wall time over that 1 ms, so the query's own work is in it too.

The test fails when a cold call sends more than one GET per file, when a warm call sends any, when anything is read twice, or when the warm-up does not fill the cache. Last run (v0.51, Sat 2026-11-14):

```
endpoint                     cold GETs cold bytes in flight GETs in row warm GETs
/v1/statistics?days=30              33     306323        16          40         0
/v1/statistics?days=7               10      72822        10          10         0
/v1/explore?group=rule              33     306323        16           8         0
/v1/live?window=24h                  4      11875         4           5         0
/v1/sightings?limit=50              33     306323        16           7         0
/v1/files                            0          0         0           0         0
warm-up                             33     306323        16           5
```

On a running server, the access log (`frank::access`) has each request's latency, and `read cache warmed {files, ms}` the warm-up's.

## What is not measured yet

- **Larger files.** Every test file is under 64 KiB, so each is read whole by its footer GET. Day files larger than that go through the chunk spans, which no FRANK test measures.
- **AWS itself.** All latencies above are 1 ms per GET scaled by 20-100. #228 runs it against AWS.
- **New files are cold once.** db-core puts what it reads in the cache, not what it writes, so the first query after a flush (hourly) or a compaction (daily) fetches the new file. At today's sizes that is about one GET per new file.
- **Files without ranges.** Files written before v0.46.0 have no `ts` or `received` range in the manifest and are read by every time window until retention removes them.
- **Cache size.** The RangeCache is db-core's default, 256 MiB; FRANK does not set it. That holds the whole table at test volume; real volume will tell whether 30 days of sightings still fit.

## Settings

| Setting | Value | Set by |
|---|---|---|
| Read cache | 256 MiB | db-core default (`S3Config::read_cache_bytes`) |
| Gap merged into one GET | 1 MiB | db-core default (`prefetch_gap`) |
| GETs at once per file / per store | 8 / 64 | db-core defaults (`prefetch_per_file`, `max_in_flight`) |
| Footers at once | 16 | db-core |
| Request timeout | 60 s | `FRANK_REQUEST_TIMEOUT` |
| Flush / compaction | every minute / every hour | `serve.rs::maintain` |

None of the db-core values can be set through the `s3://` URI today.
