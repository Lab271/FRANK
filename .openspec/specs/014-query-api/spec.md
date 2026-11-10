# Query API Specification

**Domain:** API / Analysis
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-11-10

**Owner:** Platform Team
- **Related ADR:** [ADR-016](../../architecture/decisions/016-phase3-rust-on-db-core.md), [ADR-019](../../architecture/decisions/019-sightings-in-s3-state-on-a-volume.md)
**Implementation:** `crates/frank/src/api.rs::router`
**Tests:** `crates/frank/tests/api.rs`

## Overview

The query API answers "how often was this seen, by how many participants, and since when" over the stored sightings, without callers ever sending SQL. It covers Explore (`/v1/explore`, #157), a rule's prevalence (`/v1/rules/{id}`), the live view of recent arrivals (`/v1/live`, #186), the warning and reference lists that annotate IoCs (#192, #193), the country and network of IP addresses (#191, #195), and the partners' download of the Parquet files (`/v1/files`).

Which TLP levels a caller sees and which cells are dropped below partner are the disclosure rules of spec 013; this spec says where they apply. Submission and authentication are spec 010, IoC lookups spec 021, the sightings table itself spec 020.

### Philosophy

- **A whitelist, not a query language**: callers pick a grouping and filters from a fixed set; values reach SQL normalised and quoted.
- **Sightings, not rows**: a sighting with three IoCs counts once, unless the question is about IoCs.
- **Lists annotate, never judge**: a warning or reference list adds context and can hide common infrastructure from a ranking; it never changes a stored sighting or a count.
- **Enrichment is optional**: without the geo databases or list files everything else works.

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement 1: Explore groups by one whitelisted dimension [MUST]

`GET /v1/explore` MUST take a required `group` and optional filters, each one of `rule`, `ioc`, `campaign`, `technique`, `sector`, `ioc_type`, `severity`, and `days` (1–3650, default 30). An unknown parameter name, a missing group or an out-of-range `days` MUST answer 422. Rows MUST carry `key`, `count`, `reporters`, `first_seen` and `last_seen`, most sightings first, at most 100.

**Implementation:** `crates/frank/src/api.rs::explore`, `crates/frank/src/explore.rs::parse`, `crates/frank/src/explore.rs::sql`, `crates/frank/src/api.rs::grouped`

#### Scenario: Group by rule, filter by sector

- GIVEN sightings of rules r1 and r2 in the energy and water sectors
- WHEN a caller asks `group=sector&rule=r1`, or `group=ioc&sector=ENERGY`
- THEN only r1's sectors, or only the energy sector's IoCs, are returned; filter values are case-normalised

**Tests:** `crates/frank/tests/api.rs::explore_groups_filters_and_suppresses`

#### Scenario: Unknown names are refused

- GIVEN any caller with a sufficient status
- WHEN it omits `group`, groups by `org`, filters by `reporter`, or sends `days=0`
- THEN the answer is 422

**Tests:** `crates/frank/tests/api.rs::explore_enforces_tiers_and_refuses_unknown_names`, `crates/frank/src/explore.rs::parses_and_refuses`

---

### Requirement 2: Each dimension has a minimum status [MUST]

Categories (`sector`, `ioc_type`, `severity`) MUST be available from observer up; what was detected (`rule`, `ioc`, `campaign`, `technique`) from contributor up. A request MUST need the highest status of its group and filters; below it the answer is 403.

**Implementation:** `crates/frank/src/explore.rs::min_tier`, `crates/frank/src/api.rs::require`

#### Scenario: An observer sees categories only

- GIVEN an observer
- WHEN it asks `group=sector`, `group=rule`, or `group=sector&ioc=ipv4:198.51.100.1`
- THEN the first answers 200, the others 403; without a token 403

**Tests:** `crates/frank/tests/api.rs::explore_enforces_tiers_and_refuses_unknown_names`, `crates/frank/src/explore.rs::tier_is_the_highest_dimension`

---

### Requirement 3: No SQL from callers [MUST]

Every filter value MUST be normalised for its dimension (IoCs as `type:value` through the IoC normaliser, categories lower case, techniques upper case) and quoted by doubling single quotes before it reaches SQL. An empty value, one longer than 2048 characters or one with a control character MUST be refused with 422.

**Implementation:** `crates/frank/src/explore.rs::condition`, `crates/frank-core/src/lib.rs::sql_quote`

#### Scenario: A quote cannot end the literal

- GIVEN a rule filter `x' OR '1'='1`
- WHEN the WHERE clause is built
- THEN it reads `rule_id = 'x'' OR ''1''=''1'`, one literal

**Tests:** `crates/frank/src/explore.rs::values_are_quoted_and_normalised`, `crates/frank-core/src/lib.rs::sql_quote_doubles_quotes`

#### Scenario: An IoC filter without a type is refused

- GIVEN the filter `ioc=nope`
- WHEN Explore parses it
- THEN it is an error, answered with 422

**Tests:** `crates/frank/src/explore.rs::parses_and_refuses`

#### Scenario: Control characters and overlong values are refused

- GIVEN a filter value with a control character, or longer than 2048 characters
- WHEN Explore parses it
- THEN the answer is 422

**Tests:** `crates/frank/src/explore.rs::refuses_unusable_filter_values`

---

### Requirement 4: Counts are sightings [MUST]

A sighting is stored as one row per IoC; Explore MUST count its first row (`seq = 0`) unless the group or a filter is `ioc` or `ioc_type`, where each IoC row counts. Techniques MUST be counted from the `techniques` list unnested, and filtered with `list_contains`, wherever the rows are (WAL, hour file, merged day).

**Implementation:** `crates/frank/src/explore.rs::where_clause`, `crates/frank/src/explore.rs::by_technique`

#### Scenario: Three IoCs, one sighting

- GIVEN three participants each sending one sighting of rule r1 with several IoCs
- WHEN a contributor groups by rule
- THEN r1 has count 3 and reporters 3

**Tests:** `crates/frank/tests/api.rs::explore_groups_filters_and_suppresses`

#### Scenario: Techniques in every storage state

- GIVEN sightings with techniques in the WAL, a flushed hour, a merged day and after reopening
- WHEN they are grouped or filtered by technique
- THEN each technique of a sighting counts once, in every state

**Tests:** `crates/frank/tests/techniques_unnest.rs::techniques_are_counted_with_unnest_in_every_state`, `crates/frank/src/explore.rs::techniques_are_unnested`

---

### Requirement 5: Disclosure rules apply to every query [MUST]

Explore, rule detail and the live view MUST read only the TLP levels the caller's status may see, and below partner MUST drop a cell with fewer than 3 distinct reporters (spec 013). The answer MUST state the threshold applied as `min_cell`.

**Implementation:** `crates/frank/src/api.rs::tlp_visible`, `crates/frank/src/api.rs::grouped`

#### Scenario: Small cells below partner

- GIVEN rule r2 sent by one participant
- WHEN a contributor and a partner group by rule
- THEN the contributor sees r1 only; the partner sees r1 and r2

**Tests:** `crates/frank/tests/api.rs::explore_groups_filters_and_suppresses`

#### Scenario: AMBER+STRICT stays with partners

- GIVEN three contributors sending a rule at AMBER+STRICT
- WHEN a contributor and a partner group by rule
- THEN the contributor sees nothing, the partner sees the rule

**Tests:** `crates/frank/tests/api.rs::explore_respects_tlp`

---

### Requirement 6: A rule's prevalence [MUST]

`GET /v1/rules/{id}` (contributor and up, `days` 1–3650, default 30) MUST return the rule's sightings, reporters, first and last time, a per-day trend over at most 90 days with empty days as zero, and its top sectors, severities, techniques, campaigns and IoCs. A rule that would be dropped as a cell MUST answer `{"rule": id, "known": false}`.

**Implementation:** `crates/frank/src/api.rs::rule_detail`, `crates/frank/src/explore.rs::trend`

#### Scenario: Prevalence with a trend

- GIVEN rule r1 seen three times by three participants
- WHEN a contributor asks for r1
- THEN known is true, count and reporters are 3, the 30-day trend sums to 3 and ends today, energy is the top sector

**Tests:** `crates/frank/tests/api.rs::rule_detail_shows_prevalence`, `crates/frank/src/explore.rs::trend_fills_empty_days`

#### Scenario: Unknown below the threshold, refused below contributor

- GIVEN rule r2 with one reporter
- WHEN a contributor, a partner and an observer ask for it
- THEN the contributor gets `known: false`, the partner reporters 1, the observer 403

**Tests:** `crates/frank/tests/api.rs::rule_detail_shows_prevalence`

---

### Requirement 7: The live view [MUST]

`GET /v1/live` (contributor and up) MUST take `window` 1h, 6h or 24h (default 1h; anything else 422) and select by arrival time (`received`), not `ts`. It MUST return the window's sightings, participants, IoCs and new IoCs, arrivals per bar (12 or 24 bars aligned to the clock), a feed of IoCs newest first and a converging list of IoCs with two or more reporters, most reporters first, at most 50 each. Each IoC MUST say when it was first seen before the window (`seen_since`), or null when it is new. Below partner an IoC with fewer than 3 reporters MUST be left out of both lists while the counters stay.

**Implementation:** `crates/frank/src/api.rs::live_view`, `crates/frank/src/live.rs::window_sql`, `crates/frank/src/live.rs::before_sql`, `crates/frank/src/live.rs::mark_seen`, `crates/frank/src/live.rs::buckets`, `crates/frank/src/live.rs::lists`

#### Scenario: New and converging IoCs in a day

- GIVEN an address seen 31 hours ago and, today, three participants reporting it and a new domain, one also reporting another address
- WHEN a partner asks `window=24h`
- THEN 4 sightings, 3 participants, 3 IoCs of which 2 new; the address converges with `seen_since` 31 hours ago; 24 bars

**Tests:** `crates/frank/tests/api.rs::live_shows_recent_iocs_new_and_converging`

#### Scenario: Below partner, single-reporter IoCs are left out

- GIVEN the same window
- WHEN a contributor asks, an observer asks, or a partner asks `window=2h`
- THEN the contributor's feed lacks the single-reporter address with `min_cell` 3 and the counters unchanged; the observer gets 403; `2h` gets 422

**Tests:** `crates/frank/tests/api.rs::live_shows_recent_iocs_new_and_converging`

#### Scenario: Ordering and bars

- GIVEN IoCs with different arrival times and reporter counts
- WHEN the feed, the converging list and the bars are built
- THEN the feed is newest first, converging by reporters, and the last bar holds now

**Tests:** `crates/frank/src/live.rs::feed_is_newest_first_converging_by_reporters`, `crates/frank/src/live.rs::windows_parse_and_bucket`, `crates/frank/src/live.rs::values_are_quoted_and_chunked`

---

### Requirement 8: Where the window's addresses are [SHOULD]

The live view SHOULD rank the countries and networks (ASN) of the window's IP addresses by distinct reporters, then addresses, top 10 each, with the rest together as `other` and addresses without a country as `unknown`. Below partner a place with fewer than 3 reporters MUST go to `other`, and `other` MUST be shown only when it reaches 3 reporters itself. Warning-listed addresses MUST be left out unless `common=include`. Without the geo databases nothing SHALL be ranked, and `geoip` says `missing`.

**Implementation:** `crates/frank/src/api.rs::live_places`, `crates/frank/src/live.rs::places`

#### Scenario: Countries and networks ranked

- GIVEN addresses in NL and DE test ranges and one in neither, reported by three participants
- WHEN a partner asks the live view
- THEN NL and DE rank with their networks, the unlisted address is `unknown`; below partner small places go to `other`

**Tests:** `crates/frank/tests/api.rs::live_ranks_countries_and_networks`, `crates/frank/src/live.rs::places_rank_by_reporters_and_hide_small_cells`

#### Scenario: Without databases

- GIVEN no DB-IP files
- WHEN the live view is asked
- THEN `geoip` is `missing` and the country top list is empty

**Tests:** `crates/frank/tests/api.rs::live_ranks_countries_and_networks`

---

### Requirement 9: Warning and reference lists are imported from files [MUST]

FRANK MUST import list files under `data/lists/warning/` (MISP warninglist JSON, or text with one address, range, domain or URL a line) and `data/lists/reference/` (abuse.ch URLhaus, ThreatFox and Feodo CSV exports, or text), checking the directory at most once a minute. A changed file MUST replace its list, a removed file MUST drop it, and a file that does not parse MUST leave its list as it was. Without files there are no annotations.

**Implementation:** `crates/frank/src/lists.rs::refresh`, `crates/frank/src/lists.rs::misp`, `crates/frank/src/lists.rs::abuse_ch`, `crates/frank/src/store/lists.rs::drop_list`

#### Scenario: Lists follow their files

- GIVEN a list file that is imported, then changed, broken and removed
- WHEN the directory is checked after each change
- THEN the list is replaced, kept as it was, and dropped

**Tests:** `crates/frank/tests/lists.rs::lists_follow_their_files`

#### Scenario: The formats parse

- GIVEN a MISP warninglist, a text list and abuse.ch exports
- WHEN they are parsed
- THEN their entries and source labels are read; an unsupported MISP type or bad JSON is an error

**Tests:** `crates/frank/src/lists.rs::text_and_misp_lists_parse`, `crates/frank/src/lists.rs::abuse_ch_exports_parse`

---

### Requirement 10: IoCs are matched against the lists [MUST]

An IoC MUST match a list entry exactly, an address MUST match a CIDR range holding it, and a domain, a URL's host or an e-mail's domain MUST match a hostname entry equal to it or a parent of it (never the bare top-level domain). Matching MUST NOT fail a caller: on an error nothing is annotated.

**Implementation:** `crates/frank/src/lists.rs::probe`, `crates/frank/src/lists.rs::annotate`, `crates/frank/src/store/lists.rs::matches`

#### Scenario: The host and its parents

- GIVEN a URL, an e-mail address and IP addresses
- WHEN their probes are built
- THEN the URL keeps its exact value and tries its host and parent domains; the e-mail its domain; an address its 32-hex form

**Tests:** `crates/frank/src/lists.rs::probes_try_the_host_and_its_parents`

---

### Requirement 11: Lists annotate, and hide common infrastructure from rankings [MUST]

Explore grouped by IoC and the live view MUST annotate each IoC with what the lists say (`listed`). An IoC on a warning list MUST be marked `common`: kept in the live feed, left out of the converging list and of Explore's IoC rows, unless `common=include`. Explore grouped by IoC MUST accept `listed=any|none|<list>` to keep the IoCs a reference list has, has not, or a named one has; `listed` with another group MUST answer 422. No list SHALL change a count.

**Implementation:** `crates/frank/src/api.rs::explore`, `crates/frank/src/api.rs::live_view`, `crates/frank/src/lists.rs::warned`

#### Scenario: Common infrastructure is marked, not dropped

- GIVEN a public DNS address on a warning list, reported by three participants
- WHEN the live view and Explore by IoC are asked, with and without `common=include`
- THEN it is in the feed marked common, not converging and not in Explore's rows; with `common=include` it is; the sightings count is unchanged

**Tests:** `crates/frank/tests/api.rs::common_infrastructure_is_marked_not_dropped`

#### Scenario: Reference lists as context and a filter

- GIVEN a Feodo and a URLhaus export listing some of the stored IoCs
- WHEN Explore by IoC is asked with `listed=any`, a list name, `none`, and `group=rule&listed=any`
- THEN the listed, named, and unlisted IoCs are returned, each with its list and `first_listed`; the last answers 422

**Tests:** `crates/frank/tests/api.rs::reference_lists_are_context_and_a_filter`

---

### Requirement 12: Country and network of IP addresses [SHOULD]

FRANK SHOULD look up each stored IP address's country and network in DB-IP Lite databases (MaxMind DB format) under `data/geoip/dbip-lite/`, as sightings arrive and by a backfill once per database build, and keep the answers in `ip_geo`. An address found nowhere MUST get country `ZZ` and ASN 0. Missing, unreadable or corrupt databases MUST NOT fail anything: addresses are then not looked up. New or refreshed files MUST be picked up within a minute, without a restart. Reading a database MUST be bounds-checked, so a truncated file is an error, not a panic.

**Implementation:** `crates/frank/src/geo.rs::lookup`, `crates/frank/src/geo.rs::fill`, `crates/frank/src/geo.rs::backfill`, `crates/frank/src/mmdb.rs::lookup`, `crates/frank/src/store/geo.rs::put`

#### Scenario: Addresses get a country and ASN

- GIVEN the test databases
- WHEN addresses inside and outside their ranges are looked up
- THEN known ones get country and ASN, unknown ones `ZZ` and 0

**Tests:** `crates/frank/tests/geo.rs::addresses_get_country_and_asn_unknown_ones_zz_and_zero`, `crates/frank/tests/geo.rs::every_record_size_reads`

#### Scenario: Without, or with broken, databases

- GIVEN no database files, or a corrupt one
- WHEN sightings arrive
- THEN nothing is looked up and nothing fails; a corrupt file counts as missing

**Tests:** `crates/frank/tests/geo.rs::without_databases_nothing_is_looked_up_and_nothing_fails`, `crates/frank/tests/geo.rs::a_corrupt_database_counts_as_missing`, `crates/frank/src/mmdb.rs::truncated_input_is_an_error_not_a_panic`

#### Scenario: Databases appear later

- GIVEN a running FRANK without databases
- WHEN the files appear, or a new build replaces them
- THEN they are used within a minute, and every stored address is looked up once per build

**Tests:** `crates/frank/tests/geo.rs::databases_that_appear_later_are_picked_up_within_a_minute`, `crates/frank/tests/geo.rs::backfill_looks_up_every_address_once_per_build`

---

### Requirement 13: Partners download the listed Parquet files [MUST]

`GET /v1/files` (partner and up) MUST list the sightings table's Parquet files with rows and bytes, the open hour as `open/current.parquet` when it has rows, and `ip_geo` as `geo/ip_geo.parquet` with DB-IP's attribution when it has rows. `GET /v1/files/{path}` MUST serve only those paths, as Parquet: a path with any component other than a plain name (`..`, a root) and any path not listed (the manifest, the WAL) MUST answer 404. Below partner both MUST answer 403.

**Implementation:** `crates/frank/src/api.rs::files`, `crates/frank/src/api.rs::file`, `crates/frank/src/api.rs::geo_parquet`

#### Scenario: Listed files only

- GIVEN a flushed hour
- WHEN a partner lists the files and fetches each, then `manifest.json`, `..%2F..%2Fetc%2Fpasswd` and `wal/0.log`
- THEN each listed file downloads as Parquet; the others answer 404

**Tests:** `crates/frank/tests/api.rs::partners_get_listed_files_only`

#### Scenario: The open hour is a file too

- GIVEN sightings not flushed yet
- WHEN a partner lists and fetches `open/current.parquet`
- THEN it is listed as open with its rows, and the browser engine reads it like an hour file

**Tests:** `crates/frank/tests/api.rs::the_open_hour_is_a_file_too`

#### Scenario: ip_geo with its attribution

- GIVEN looked-up addresses, and then none
- WHEN a partner lists the files and fetches `geo/ip_geo.parquet`
- THEN it is listed with DB-IP's attribution and downloads as Parquet; without rows it is not listed and answers 404

**Tests:** `crates/frank/tests/api.rs::ip_addresses_carry_country_and_asn`

#### Scenario: Below partner

- GIVEN a contributor
- WHEN it lists the files
- THEN the answer is 403

**Tests:** `crates/frank/tests/api.rs::tiers_gate_the_routes`
