# Sightings Storage Specification

**Domain:** Storage / Sightings
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-11-10

**Owner:** Platform Team
- **Related ADR:** [ADR-016](../../architecture/decisions/016-phase3-rust-on-db-core.md), [ADR-019](../../architecture/decisions/019-sightings-in-s3-state-on-a-volume.md), [ADR-018](../../architecture/decisions/018-container-is-the-reference-and-test-tiers.md)
**Implementation:** `crates/frank/src/store/sightings.rs`, `crates/frank/src/store/rowdb.rs`, `crates/frank/src/objects.rs`, `crates/frank/src/records.rs`
- **Data:** `data/sightings/` (striped db-core table), or with `FRANK_STORE` the bucket plus `data/s3/sightings/` (WAL)
**Tests:** `crates/frank/tests/sightings_schema.rs`, `crates/frank/tests/techniques_unnest.rs`

## Overview

Sightings are immutable events, stored once in a striped (tiered) db-core table of plain Parquet files with hive partitions, so DuckDB and pyarrow read them too. The server is its single writer. Accepted rows go to a write-ahead log first; each closed hour is written to `live/` as one Parquet file sorted by `(rule_id, ioc_value)`, closed days merge into `archive/`, and retention drops whole days. The smaller state (`iocs.db`, `registry.db`, `participants.db`) lives in db-core row databases in SQLite format.

Who may read which rows (TLP, the reporter threshold) is [spec 013](../013-disclosure/spec.md); the IoC index is [spec 021](../021-ioc-lookups/spec.md); participants are [spec 011](../011-management-api/spec.md).

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement 1: One row per sighting and IoC [MUST]

The `sightings` table MUST hold one row per sighting × IoC (`seq` 0, 1, …), or one row for a sighting without IoCs. Each row MUST carry `ts`, `sighting_id` (16 bytes), `rule_id`, `techniques` (`LIST<UTF8>`), `campaign`, `ioc_type`, `ioc_value`, sectors, `severity`, `confidence`, `observations`, `tlp`, `reporter` and `seq`. The `digest` (32 bytes), `received` and the normalised sighting (`detail`) MUST be on the `seq = 0` row. `reporter` MUST be the participant id, never a user, a token or a name.

**Implementation:** `crates/frank/src/store/sightings.rs::schema`, `crates/frank/src/store/sightings.rs::record`

#### Scenario: A sighting with two IoCs is two rows

- GIVEN two sightings, each with a domain and an IPv4 address
- WHEN a contributor submits them
- THEN the answer reports 4 rows and 2 receipts

**Tests:** `crates/frank/tests/api.rs::submit_then_look_up`

#### Scenario: Rows carry the participant id

- GIVEN two participants that each submit a sighting
- WHEN a partner downloads the files
- THEN the open hour's file has two distinct reporters, and no participant name or token hash appears in it

**Tests:** `crates/frank/tests/api.rs::files_hold_participant_ids_not_names_or_tokens`

---

### Requirement 2: Accepted rows are durable [MUST]

An append MUST return only once its rows are on disk (the WAL fsynced on the last row of the batch). Rows MUST be readable in every state: in the WAL, in an hour file, in a merged day, and after the table is reopened.

**Implementation:** `crates/frank/src/store/sightings.rs::append`, `crates/frank/src/store/sightings.rs::query`

#### Scenario: Rows are counted alike in every state

- GIVEN sightings in the WAL, then in a flushed hour, then in a merged day
- WHEN the table is queried in each state and after reopening
- THEN every query returns the same counts

**Tests:** `crates/frank/tests/techniques_unnest.rs::techniques_are_counted_with_unnest_in_every_state`

#### Scenario: A restart in the middle of a stream loses nothing

- GIVEN sightings appended to the open hour
- WHEN the table is closed without a flush and opened again
- THEN every appended sighting is there, and appending goes on

**Tests:** `crates/frank/tests/restart.rs::a_restart_in_the_middle_of_a_stream_loses_nothing`

---

### Requirement 3: Hour files [MUST]

Every minute the server MUST write each closed hour to `live/date=…/hour=…/` as one Parquet file (zstd, sorted by `rule_id`, `ioc_value`), whose `ts` and `received` ranges the manifest MUST record so a `ts` or `received` window skips the files outside it without reading them (#283, #284). On shutdown it MUST flush before closing. Rows of the open hour MUST still be readable as one Parquet file written on request.

**Implementation:** `crates/frank/src/store/sightings.rs::flush`, `crates/frank/src/store/sightings.rs::options`, `crates/frank/src/store/sightings.rs::open_rows_parquet`, `crates/frank/src/serve.rs::maintain`

#### Scenario: A closed hour becomes one file

- GIVEN a submission in hour H
- WHEN an hour later the table is flushed
- THEN one file under `live/` is listed

**Tests:** `crates/frank/tests/api.rs::partners_get_listed_files_only`

#### Scenario: The open hour is a file too

- GIVEN rows not yet flushed
- WHEN a partner asks for `open/current.parquet`
- THEN it gets a Parquet file with those rows

**Tests:** `crates/frank/tests/api.rs::the_open_hour_is_a_file_too`

#### Scenario: A ts window skips the files outside it

- GIVEN three hour files with `ts` an hour apart
- WHEN a query asks for `ts` from the last hour's on, or after every row
- THEN it opens one file, or none, and counts the same rows as before

**Tests:** `crates/frank/src/store/sightings.rs::a_ts_window_skips_the_files_outside_it`

---

### Requirement 4: Day merge and retention [MUST]

Every hour the server MUST merge closed days into `archive/date=…/` and drop whole days older than `FRANK_RETENTION_DAYS` (default 400). The same cut MUST be applied to `iocs.db`, the registry and the audit log. Retention is by arrival day.

**Implementation:** `crates/frank/src/store/sightings.rs::compact`, `crates/frank/src/serve.rs::maintain`

#### Scenario: Days merge and expire

- GIVEN a table with a retention of 2 days and a flushed hour
- WHEN a day passes and the table is compacted, then 5 days pass
- THEN the day is one archive file, and later it leaves the manifest

**Tests:** `crates/frank/src/store/sightings.rs::retention_deletes_the_objects_in_the_store`

#### Scenario: Audit days expire with the sightings

- GIVEN audit lines on two days
- WHEN retention keeps the second day only
- THEN the first day's file is gone and the second's stays

**Tests:** `crates/frank/src/audit.rs::lines_append_per_day_and_expire`

---

### Requirement 5: Techniques as a list [MUST]

A sighting's ATT&CK techniques MUST be stored as the `techniques` list column, so they are ranked with `UNNEST(techniques)` and filtered with `list_contains`, with the same counts a per-technique table gave (#180).

**Implementation:** `crates/frank/src/store/sightings.rs::schema`, `crates/frank/src/store/sightings.rs::techniques`

#### Scenario: Techniques are counted with UNNEST

- GIVEN sightings with zero, one and two techniques
- WHEN techniques are ranked, overall and for IPv4 sightings, and filtered by one technique
- THEN the counts match the old per-technique table's

**Tests:** `crates/frank/tests/techniques_unnest.rs::techniques_are_counted_with_unnest_in_every_state`

---

### Requirement 6: Older tables are rewritten once [MUST]

On open, a local table stored with the comma-separated `technique` string (0.20 and before) or with text ids and digests (0.27 and before) MUST be rewritten into the current schema: each row appended at its own arrival time so it keeps its hour and day, the digest on the `seq = 0` row only. The new table MUST be swapped in only when every row was copied; the old one MUST be kept as `sightings.pre-list/` or `sightings.pre-binary/`. The rewrite MUST refuse to start if that backup already exists, and MUST stop with the table unchanged when a text id is not a UUID. A table without `digest` (0.12 and before) MUST be refused, not evolved.

**Implementation:** `crates/frank/src/store/sightings.rs::open_in`, `crates/frank/src/store/sightings.rs::outdated`, `crates/frank/src/store/sightings.rs::rewrite`, `crates/frank/src/store/sightings.rs::id_bytes`

#### Scenario: The technique string becomes a list in place

- GIVEN a 0.20 table over two days, flushed and compacted
- WHEN it is opened
- THEN its rows are in the same partitions with the list filled, `sightings.pre-list/` holds the old table, and a second open does not rewrite again

**Tests:** `crates/frank/src/store/sightings.rs::a_table_with_the_string_is_rewritten_in_its_partitions`

#### Scenario: Text ids become bytes

- GIVEN a 0.27 table with text ids and a digest on every row
- WHEN it is opened
- THEN the ids and digests are bytes, rows stay in their hours, and `sightings.pre-binary/` holds the old table

**Tests:** `crates/frank/src/store/sightings.rs::a_table_with_text_ids_is_rewritten_to_bytes`

#### Scenario: A bad id stops the rewrite

- GIVEN a table with a text id that is not a UUID
- WHEN it is opened
- THEN the open fails naming `sighting_id`, and no backup is made

**Tests:** `crates/frank/src/store/sightings.rs::a_text_id_that_is_no_uuid_stops_the_rewrite`

#### Scenario: A 0.12 table is refused; a 0.14 table gains columns

- GIVEN a table without `digest`, and one with text `digest` and `received` but no `seq` or `detail`
- WHEN each is opened
- THEN the first is refused; the second opens with NULL `seq` and `detail`, and its id and digest as bytes

**Tests:** `crates/frank/tests/sightings_schema.rs::a_0_12_table_is_refused`, `crates/frank/tests/sightings_schema.rs::a_0_14_table_gains_the_grain_columns`

---

### Requirement 7: Sightings in an object store [MUST]

With `FRANK_STORE=s3://bucket/prefix?endpoint=…&region=…` the table's manifest and Parquet files MUST be kept in the store, while its WAL, writer lock and scratch space MUST stay on the local volume in `data/s3/sightings/`, apart from the local table's `data/sightings/`. Credentials MUST come from the AWS chain, never from the URI. An `https://` endpoint MUST go through the TLS transport (`--features tls`, built into the image); without it the store MUST be refused with a message saying why. Retention MUST delete the objects themselves, after db-core's delete grace. A query MUST read the store's files by range (footers, then the column chunks it loads) through db-core's read cache, and listing the files MUST fetch none (#282). On start, after flushing and compacting, the server MUST warm the read cache by touching every listed file once, off the request path; a failure MUST only be logged (#291).

**Implementation:** `crates/frank/src/objects.rs::open`, `crates/frank/src/store/sightings.rs::open_in`, `crates/frank/src/store/sightings.rs::read_file`, `crates/frank/src/store/sightings.rs::nanos`, `crates/frank/src/store/sightings.rs::warm`, `crates/frank/src/serve.rs::maintain`

#### Scenario: Files in the store, the WAL apart

- GIVEN a table opened in a store
- WHEN a closed hour is flushed and a new process opens the table
- THEN the hour file and `manifest.json` are in the store, the WAL is local with no Parquet beside it, and the new process reads both rows

**Tests:** `crates/frank/src/store/sightings.rs::a_table_in_a_store_keeps_its_files_there_and_its_wal_apart`

#### Scenario: Queries read by range, once

- GIVEN three closed hours flushed to a store
- WHEN the files are listed, a query runs, and the same query runs again
- THEN the listing fetches no file, the query reads fewer bytes than the files hold and sends no HEAD, and the second run sends no request

**Tests:** `crates/frank/src/store/sightings.rs::a_query_in_a_store_reads_by_range_and_once`, `crates/frank/src/store/sightings.rs::nanos_reads_an_integer_or_the_iso_text_db_core_prints`

#### Scenario: Every endpoint is answered from the cache when warm

- GIVEN 30 days of sightings in a store, and a server started on it with an empty cache
- WHEN a partner calls statistics (30 and 7 days), explore, live, the records list and the file list, each twice
- THEN the second call of each sends no request, no call sends a HEAD or reads as many bytes as the files hold, a 7-day window sends fewer requests than a 30-day one, and the file list fetches nothing

**Tests:** `crates/frank/tests/s3_requests.rs::requests_per_endpoint_cold_and_warm`

#### Scenario: The first caller after a start sends nothing

- GIVEN 30 days of sightings in a store, and a new process with an empty cache
- WHEN the warm-up runs, then statistics, explore and the records list are called
- THEN the warm-up sends one GET per listed file, the calls after it send none, and on the filesystem the warm-up does nothing

**Tests:** `crates/frank/tests/s3_requests.rs::requests_per_endpoint_cold_and_warm`, `crates/frank/tests/s3_requests.rs::warm_is_a_no_op_on_the_filesystem`

#### Scenario: Retention deletes objects

- GIVEN a merged day in the store
- WHEN the day passes retention and the delete grace passes
- THEN the object is removed from the store

**Tests:** `crates/frank/src/store/sightings.rs::retention_deletes_the_objects_in_the_store`

#### Scenario: HTTPS requests reach the endpoint

- GIVEN the TLS transport
- WHEN db-core sends a request
- THEN its method, target and body are sent and the response mapped back

**Tests:** `crates/frank/src/objects.rs::sends_the_request_and_maps_the_response`, `crates/frank/src/objects.rs::talks_https_to_an_endpoint`

---

### Requirement 8: Switching between filesystem and store [SHOULD]

A local table copied to the bucket, with its `wal/` moved to the store mode's WAL directory, SHOULD open as the same table in the store, and the other way round. A table in a store MUST start from the current schema: the rewrites of Requirement 6 apply to local tables only.

**Implementation:** `crates/frank/src/store/sightings.rs::open_in`

#### Scenario: A copied table is the same table

- GIVEN a local table with two sightings
- WHEN its directory is copied to a bucket and opened in store mode, a third sighting added, and copied back
- THEN store mode reads 2 rows, and the local table afterwards reads 3

**Tests:** `crates/frank/src/store/sightings.rs::a_local_table_copied_to_a_store_is_the_same_table`

---

### Requirement 9: The audit log in the store [MUST]

With `FRANK_STORE` the audit log MUST go to the store as one object per line under `audit/YYYY-MM-DD/`, since S3 cannot append, and MUST read back in order. Two writers in the same nanosecond MUST both keep their line.

**Implementation:** `crates/frank/src/audit.rs::open_in`, `crates/frank/src/audit.rs::record`, `crates/frank/src/audit.rs::read_from`

#### Scenario: One object per line, ordered and expiring

- GIVEN two audit handles on one store
- WHEN both record lines in the same nanosecond and on the next day
- THEN every line is read back in order, and retention drops the first day

**Tests:** `crates/frank/src/audit.rs::in_a_store_one_object_per_line_ordered_and_expiring`

---

### Requirement 10: Row databases [MUST]

`iocs.db`, `registry.db` and `participants.db` MUST be db-core row databases in SQLite format, each owned by one thread that the server sends jobs to, so `sqlite3` can open them too. A schema MUST be created for a new file and checked for an existing one. Every committed transaction MUST survive a reopen.

**Implementation:** `crates/frank/src/store/rowdb.rs::open`, `crates/frank/src/store/rowdb.rs::run`, `crates/frank/src/store/rowdb.rs::transaction`

#### Scenario: Transactions survive a reopen

- GIVEN five IoCs recorded in five transactions
- WHEN the database is closed and opened again
- THEN all five are there, and a sixth adds to them

**Tests:** `crates/frank/tests/iocs.rs::every_transaction_is_kept`

---

### Requirement 11: Records from the first row [MUST]

A sighting's record (the list behind `GET /v1/sightings` and one record by id) MUST be read from its `seq = 0` row's `detail`, so sightings stored before 0.15 are not listed. The list MUST be ordered by `(ts, sighting_id)` and paged by a cursor of the last item's pair; with an IoC filter it MUST page the ids first, then read their records.

**Implementation:** `crates/frank/src/records.rs::parse`, `crates/frank/src/records.rs::sql`, `crates/frank/src/records.rs::ioc_sql`, `crates/frank/src/records.rs::item`

#### Scenario: Pages follow the cursor, one record a sighting

- GIVEN a cursor and a rule filter with a quote in it
- WHEN the list's SQL is built
- THEN it selects `seq = 0` rows after the cursor, quotes the value, and asks one row more than the page

**Tests:** `crates/frank/src/records.rs::pages_after_the_cursor_one_record_a_sighting`, `crates/frank/src/records.rs::an_ioc_filter_pages_in_the_ids_query`

The listing over HTTP, including paging through thousands of IoC matches, is spec 010, Requirement 14.

---

## Known gaps

- The hourly maintenance loop itself (`main.rs::maintain`) is not under test; its parts are.
