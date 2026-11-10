# Browser Client Specification

**Domain:** Clients / Web UI and WebAssembly
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-11-10

**Owner:** Platform Team
- **Related ADR:** [ADR-016](../../architecture/decisions/016-phase3-rust-on-db-core.md) (§6, the browser runs FRANK code), [ADR-017](../../architecture/decisions/017-user-roles-for-identity-administration.md) (admin tab)

## Overview

The web UI in `web/` is a static page over the HTTP API. Next to it runs `frank-wasm`, FRANK's own Rust code compiled to `wasm32-unknown-unknown`, for two things the server need not be trusted with:

- **Preview:** a contributor sees the rows a submission would share, computed by the parser the server runs, before anything leaves the browser.
- **Local analysis:** a partner downloads the `sightings` Parquet files and runs SQL over them on db-core's column engine, with no server involved.

### Philosophy

- **Same code, both sides:** the preview is `frank-core`'s parser, not a JavaScript copy of it.
- **Data is text, never markup:** every value from the API or a file reaches the page through `textContent`; IoC values are attacker-controlled.
- **The server decides:** the UI hides what a tier or role cannot use, but every call is checked by the API.

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement 1: Submission preview in the browser [MUST]

`preview(submission, now_ms)` MUST parse a submission (JSON, YAML or a STIX bundle; one or a list) with `frank-core`'s `formats::parse`, using the browser clock for missing times, and return the sighting rows it would add as JSON `{ "rows": [...] }`. The rows MUST be the anonymised rows the server stores: no participant or target identity. A parse error MUST be returned as an error, not as empty rows. The submit tab MUST run the preview before it sends, and MUST NOT send when the preview fails.

**Implementation:** `crates/frank-wasm/src/lib.rs::preview`, `crates/frank-wasm/src/lib.rs::preview_rows`, `web/app.js::doPreview`

#### Scenario: The preview shows the IoC and no identity

- GIVEN the minimal example submission
- WHEN it is previewed
- THEN the rows contain its IP address and no `identity-` value

**Tests:** `crates/frank-wasm/src/lib.rs::preview_shows_no_identity`

#### Scenario: A submission that does not parse is not sent

- GIVEN a submission the parser rejects
- WHEN the user presses send
- THEN the error is shown and no `POST /v1/sightings` is made

**Tests:** (planned: no browser test tier yet, ADR-018)

---

### Requirement 2: Sending from the submit tab [MUST]

Before sending, the submit tab MUST give every sighting without a `sighting_id` a new UUID in the form itself, so that sending the same form again is a resend (#159). It MUST send JSON (also a STIX bundle) as `application/json` and anything else as `application/yaml`, and MUST report how many sightings were created, how many were already registered, and their ids.

**Implementation:** `web/app.js::nameSightings`, `web/app.js::contentType`

#### Scenario: Sending the same form twice is a resend

- GIVEN a JSON submission without a `sighting_id`
- WHEN it is sent twice
- THEN the first send fills in an id and stores it; the second reports it as already registered

**Tests:** (planned: no browser test tier yet, ADR-018)

---

### Requirement 3: Local analysis of Parquet files [MUST]

An `Analyst` MUST hold the downloaded `sightings` Parquet files in browser memory, one column engine per file, and report each file's row count when it is added. A file that is not valid Parquet MUST be refused with an error naming it. `query(sql)` MUST run the SQL on every file. The analyse tab MUST download the files listed by `GET /v1/files` (partner and above) with the user's token.

**Implementation:** `crates/frank-wasm/src/lib.rs::new`, `crates/frank-wasm/src/lib.rs::add_file`, `crates/frank-wasm/src/lib.rs::query`, `crates/frank-wasm/src/lib.rs::run`

#### Scenario: Files load and count their rows

- GIVEN two Parquet files of 3 and 2 rows, and a file of three random bytes
- WHEN they are added
- THEN the first reports 3 rows, and the random bytes are refused

**Tests:** `crates/frank-wasm/src/lib.rs::merges_exact_aggregates_across_files`, `crates/frank-wasm/src/lib.rs::distinct_counts_stay_per_file`

#### Scenario: Filters on timestamps take ISO literals

- GIVEN a file with rows an hour apart from 2026-10-22 00:00 UTC
- WHEN `count(*)` is queried with `ts >= '2026-10-22T01:00:00Z'`
- THEN the count covers the later rows only

**Tests:** `crates/frank-wasm/src/lib.rs::filters_on_time_literals`

---

### Requirement 4: Merging results across files [MUST]

When more than one file is loaded and every aggregate in the result combines exactly (`count`, `sum`, one-argument `min` and `max`), the per-file results MUST be merged into one answer, grouped by the other columns, and marked `merged: true`. An aggregate MUST be recognised by its expression, so `count(*) AS sightings` still sums. When any result column cannot combine exactly (`avg`, `total`, `group_concat`, `count(DISTINCT ...)`, a window function), the rows MUST be returned per file with a leading `file` column and `merged: false`. Scalar functions, including two-argument `max(a, b)`, MUST be treated as grouping keys. Null MUST NOT override a value.

**Implementation:** `crates/frank-wasm/src/lib.rs::run`, `crates/frank-wasm/src/lib.rs::merge_kinds`, `crates/frank-wasm/src/lib.rs::call_kind`, `crates/frank-wasm/src/lib.rs::merge_kind`, `crates/frank-wasm/src/lib.rs::combine`

#### Scenario: Counts, sums and maxima merge

- GIVEN two files with IoC types `ipv4, ipv4, domain` and `ipv4, url`
- WHEN `ioc_type, count(*), sum(observations), max(observations)` is grouped by type
- THEN one merged answer has `ipv4` counted 3 times

**Tests:** `crates/frank-wasm/src/lib.rs::merges_exact_aggregates_across_files`

#### Scenario: Aliased aggregates merge, inexact ones stay per file

- GIVEN the same two files
- WHEN the analyse tab's default query (aliased `count(*)` and `sum`) runs, and then an `avg` and a `count(DISTINCT ...)`
- THEN the first is merged, the other two are returned per file

**Tests:** `crates/frank-wasm/src/lib.rs::aliased_aggregates_merge_by_their_expression`, `crates/frank-wasm/src/lib.rs::distinct_counts_stay_per_file`

#### Scenario: Partial aggregates combine by kind

- GIVEN partial results 2 and 3, and a null
- WHEN they combine as sum, min and max
- THEN they give 5, 2 and 3, and a null yields the other value

**Tests:** `crates/frank-wasm/src/lib.rs::combines_partial_aggregates`, `crates/frank-wasm/src/lib.rs::merge_kinds_by_label`

---

### Requirement 5: Bytes shown in hex [MUST]

Byte columns (`sighting_id`, `digest`, #200) MUST be shown as lowercase hex, and MUST order by their bytes when merged as a minimum or maximum.

**Implementation:** `crates/frank-wasm/src/lib.rs::cell`, `crates/frank-wasm/src/lib.rs::lt`

#### Scenario: A blob reads as hex

- GIVEN the bytes `0f ab`
- WHEN they are rendered
- THEN they read `0fab`, and the minimum of `02` and `01` is `01`

**Tests:** `crates/frank-wasm/src/lib.rs::blobs_show_in_hex_and_order_by_bytes`

---

### Requirement 6: Token and tier in the page [MUST]

The page MUST send the token as `Authorization: Bearer <token>` on every API call, and MUST accept a pasted `Bearer <token>` as the bare token. The token MUST be kept in `sessionStorage` (`frank-token`), so it ends with the browser tab. After a token is set, the page MUST ask `GET /v1/whoami` for the tier and role, show them, and fall back to `public` when the token is rejected. Explore dimensions above the tier MUST be disabled.

**Implementation:** `web/app.js::api`, `web/app.js::whoami`

#### Scenario: A rejected token falls back to public

- GIVEN a token the server refuses
- WHEN it is entered
- THEN the page shows `rejected: <reason>` and behaves as the public tier

**Tests:** (planned: no browser test tier yet, ADR-018)

---

### Requirement 7: Tabs follow the URL and the tier [SHOULD]

The URL hash SHOULD hold the view's state (`#explore?group=rule&sector=energy&pane=rule:r1`), so a view can be linked and reloaded; an unknown tab SHOULD open the statistics. The admin tab MUST be hidden and unreachable without a role. The live view MUST ask for a contributor token or higher, refresh every 15 s, and stop polling when it is paused, left, or the browser tab is hidden.

**Implementation:** `web/app.js::route`, `web/app.js::showTab`, `web/app.js::loadLive`, `web/app.js::stopLive`

#### Scenario: The admin tab needs a role

- GIVEN a user without a role
- WHEN it opens `#admin`
- THEN the statistics tab is shown instead

**Tests:** (planned: no browser test tier yet, ADR-018)

#### Scenario: The live view stops when not seen

- GIVEN a contributor on the live tab
- WHEN the browser tab is hidden
- THEN polling stops, and resumes when it is shown again

**Tests:** (planned: no browser test tier yet, ADR-018)

---

### Requirement 8: Admin tab [MUST]

For a user with a role (ADR-017) the admin tab MUST list the organisations it manages, their users, tokens and audit lines, and MUST offer the changes of spec 011 through `/v1/admin/`. Controls for a superadmin only (status, new organisation, superadmin role, file listing) MUST be hidden from an admin. A new token MUST be shown once, with a copy button.

**Implementation:** `web/app.js::loadAdmin`, `web/app.js::tokenCard`, `web/app.js::loadFiles`

#### Scenario: An admin does not see superadmin controls

- GIVEN an admin, not a superadmin
- WHEN it opens the admin tab
- THEN the status control, the new-organisation form, the superadmin role and the file listing are hidden

**Tests:** (planned: no browser test tier yet, ADR-018)

---

### Requirement 9: Values are rendered as text [MUST]

Every value from the API, a Parquet file or the submission MUST be written to the page as text (`textContent` or text nodes), never parsed as HTML.

**Implementation:** `web/app.js::el`, `web/app.js::table`

#### Scenario: An IoC that looks like markup stays text

- GIVEN a sighting whose URL IoC contains `<script>`
- WHEN it is shown in a table or the side pane
- THEN the characters appear as written and nothing runs

**Tests:** (planned: no browser test tier yet, ADR-018)

---

### Requirement 10: Colour theme [SHOULD]

A header button SHOULD cycle the theme through auto, light and dark, keep the choice in `localStorage` (`frank.theme`), and in auto follow the operating system's setting as it changes. Storage that is blocked SHOULD leave the theme on auto.

**Implementation:** `web/theme.js::frank.theme`

#### Scenario: The choice survives a reload

- GIVEN the theme set to dark
- WHEN the page is reloaded
- THEN it opens dark; on auto it follows the OS

**Tests:** (planned: no browser test tier yet, ADR-018)

