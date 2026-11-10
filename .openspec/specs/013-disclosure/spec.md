# Disclosure Specification

**Domain:** API / Disclosure
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-11-10

**Owner:** Platform Team
- **Related ADR:** [ADR-002](../../architecture/decisions/002-tiered-access-control.md), [ADR-016](../../architecture/decisions/016-phase3-rust-on-db-core.md), [ADR-017](../../architecture/decisions/017-user-roles-for-identity-administration.md)

## Overview

Who sees what. A caller's status (`public`, `observer`, `contributor`, `partner`, `core`) decides which routes it may call, which TLP levels it sees, whether small cells are suppressed and whether participant ids and names are shown. The rules hold for every query the server runs; the endpoints whose main job is disclosure, `/v1/statistics`, `/v1/summary` and `/v1/participants`, are specified here, the others (Explore, live, lists, files) in their own specs.

### Philosophy

- **Give to get** (ADR-002): the status a participant holds decides how much it sees; contributors and above send.
- **The submitter marks, the server enforces** (#149): every row keeps its TLP level, and every query adds the levels the caller may see.
- **k-anonymity counts reporters, not rows** (#148): below partner, a cell that fewer than 3 distinct participants reported is left out.
- **Participants, not users** (ADR-016): the reporter of a row is the participant's opaque id, never a user, a token or a name.

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement 1: Ordered statuses gate the routes [MUST]

The statuses MUST be ordered `public < observer < contributor < partner < core`; `core_member` MUST be read as `core`. Each route names the lowest status it serves, and a caller below it MUST receive 403 naming the status needed. A caller without a token is `public`.

**Implementation:** `crates/frank-core/src/tier.rs::parse`, `crates/frank/src/api.rs::require`

#### Scenario: The statuses are ordered

- GIVEN the five statuses
- WHEN they are compared
- THEN public is lowest and core highest, and `CORE_MEMBER` parses as core

**Tests:** `crates/frank-core/src/tier.rs::tiers_are_ordered`

#### Scenario: A lower status is refused

- GIVEN an observer token
- WHEN it submits a sighting or a contributor lists files
- THEN the response is 403

**Tests:** `crates/frank/tests/api.rs::tiers_gate_the_routes`

---

### Requirement 2: TLP levels per status [MUST]

Each status MUST see the TLP levels at or below it: CLEAR from public, GREEN from observer, AMBER from contributor, AMBER+STRICT from partner. TLP:RED MUST NOT be stored: a submission marked RED is refused. Every query on the sightings MUST add the caller's visible levels as a condition.

**Implementation:** `crates/frank-core/src/tlp.rs::min_tier`, `crates/frank-core/src/tlp.rs::visible_to`, `crates/frank/src/api.rs::tlp_visible`

#### Scenario: Each status sees its levels

- GIVEN one sighting at each of CLEAR, GREEN, AMBER and AMBER+STRICT
- WHEN each status asks `/v1/statistics`
- THEN public counts one, observer two, contributor three, partner four

**Tests:** `crates/frank-core/src/tlp.rs::each_tier_sees_its_levels`, `crates/frank/tests/api.rs::each_tier_sees_its_tlp_levels`

#### Scenario: TLP:RED is refused

- GIVEN a sighting marked TLP:RED
- WHEN a contributor submits it
- THEN it is refused and nothing is stored

**Tests:** `crates/frank/tests/api.rs::tlp_red_is_refused`

#### Scenario: Explore applies the levels

- GIVEN sightings at several TLP levels
- WHEN a contributor groups them in Explore
- THEN AMBER+STRICT rows are not counted

**Tests:** `crates/frank/tests/api.rs::explore_respects_tlp`

---

### Requirement 3: TLP holds for the IoC table [MUST]

The IoC table keys its rows by TLP level, and IoC lookups and range queries MUST pass the caller's visible levels, so a lookup MUST NOT reveal that an IoC was seen at a level the caller cannot see.

**Implementation:** `crates/frank/src/api.rs::ioc_lookup`, `crates/frank/src/api.rs::ioc_range`

#### Scenario: An AMBER+STRICT IoC is unknown to a contributor

- GIVEN an IoC sent only at AMBER+STRICT
- WHEN a contributor and a partner look it up
- THEN the contributor gets `known: false`, the partner `known: true`

**Tests:** `crates/frank/tests/api.rs::each_tier_sees_its_tlp_levels`

---

### Requirement 4: Small cells suppressed below partner [MUST]

Below partner, an aggregate cell (a sector, type, severity, rule, technique, campaign, IoC, country or network) with fewer than 3 distinct reporters MUST be left out. Reporters are counted, not rows: one participant's many sightings are one reporter. Partners and core MUST see exact cells. Answers MUST say which minimum applied (`min_cell`: 3, or 1 for partner and core). An IoC lookup (`/v1/iocs`) MUST answer whether the IoC is known, its count and days to a contributor, but leave out rules with fewer than 3 reporters and answer `reporters` as null below 3 (#255).

**Implementation:** `crates/frank/src/api.rs::breakdown`, `crates/frank/src/api.rs::grouped`, `crates/frank/src/api.rs::live_view`, `crates/frank/src/api.rs::live_places`, `crates/frank/src/api.rs::ioc_lookup`

#### Scenario: One reporter's cell is dropped

- GIVEN energy reported by three participants and water by one participant three times
- WHEN an observer or contributor asks `/v1/statistics`
- THEN energy is shown and water is not; a partner sees both

**Tests:** `crates/frank/tests/api.rs::small_cells_are_suppressed_below_partner`

#### Scenario: Explore suppresses the same way

- GIVEN rule r1 reported by three participants and r2 by one
- WHEN a contributor and a partner group by rule
- THEN the contributor sees r1 only, the partner r1 and r2

**Tests:** `crates/frank/tests/api.rs::explore_groups_filters_and_suppresses`

#### Scenario: The live view leaves out a single reporter's IoC

- GIVEN an IoC only one participant reported in the window
- WHEN a contributor opens `/v1/live`
- THEN that IoC is not listed, the totals still count it, and `min_cell` is 3

**Tests:** `crates/frank/tests/api.rs::live_shows_recent_iocs_new_and_converging`

#### Scenario: An IoC lookup hides a small rule and reporter count

- GIVEN one IoC sent by two participants under rule r1
- WHEN a contributor and a partner look it up, and then a third participant sends it
- THEN the contributor first sees it known with its count but `reporters` null and no rules, the partner sees 2 reporters and r1; after the third, the contributor sees 3 and r1

**Tests:** `crates/frank/tests/api.rs::lookups_count_reporters`

---

### Requirement 5: The reporter is the participant [MUST]

Each stored row's reporter MUST be the sending participant's opaque id, set by the server and never taken from the submission. Two users of one organisation MUST count as one reporter. No organisation id, name or token from the submission MUST reach a stored row or a preview.

**Implementation:** `crates/frank/src/api.rs::submit`, `crates/frank-core/src/model.rs::rows`

#### Scenario: Two users are one reporter

- GIVEN two users of one participant who each send a sighting
- WHEN the rows are read
- THEN both carry the participant's id

**Tests:** `crates/frank/tests/api.rs::participants_are_the_reporters`

#### Scenario: Nothing identifying is stored

- GIVEN a submission naming the submitter's and the target's organisation ids
- WHEN it is stored or previewed
- THEN no `identity--` value appears in the rows or the preview

**Tests:** `crates/frank/tests/api.rs::nothing_identifying_is_stored`, `crates/frank-core/src/model.rs::rows_carry_no_organisation_identity`

---

### Requirement 6: No target identity in the shared data [MUST]

The target's identity (`target.id`) MUST NOT be stored: the record kept with a sighting (`detail`) leaves it out, because partners download the table's files whole, and the rows never have it, so no status, core included, sees it (ADR-016 §3, revised for #256). The target's sector, size and region MAY be kept.

**Implementation:** `crates/frank-core/src/model.rs::detail`

#### Scenario: The detail has the sector, not the identity

- GIVEN a sighting whose target names an organisation id and a sector
- WHEN its rows are built
- THEN the detail's target holds the sector only

**Tests:** `crates/frank-core/src/model.rs::rows_are_one_per_ioc_with_the_detail_on_the_first`

---

### Requirement 7: Participant ids from partner, names for core [MUST]

Aggregates MUST NOT show participant ids or names to any status. From partner up, records and downloaded files carry participant ids. `/v1/participants` MUST answer 403 below partner, list id and status for a partner, and the full details (name, type, sector, region, contact) for core.

**Implementation:** `crates/frank/src/api.rs::participants`

#### Scenario: Aggregates name nobody

- GIVEN sightings from known participants
- WHEN a contributor or partner asks statistics, Explore, a rule or an IoC
- THEN no answer holds a participant id or name

**Tests:** `crates/frank/tests/api.rs::reporters_are_shown_by_status`

#### Scenario: The participant list by status

- GIVEN registered participants
- WHEN a contributor, a partner and core ask `/v1/participants`
- THEN the contributor gets 403, the partner ids and statuses, core the names too

**Tests:** `crates/frank/tests/api.rs::reporters_are_shown_by_status`

#### Scenario: Files hold ids, not names or tokens

- GIVEN stored sightings
- WHEN a partner downloads the open hour's Parquet file
- THEN its reporter column holds participant ids, and no name or token appears

**Tests:** `crates/frank/tests/api.rs::files_hold_participant_ids_not_names_or_tokens`

---

### Requirement 8: Statistics by status [MUST]

`/v1/statistics?days=N` (1–3650, default 30; otherwise 422) MUST answer every status with the totals at its visible levels: sightings, observations and IoCs. From observer up it MUST add breakdowns by IoC type, severity and target sector; from contributor up the top rules, techniques and campaigns. Breakdowns follow Requirement 4.

**Implementation:** `crates/frank/src/api.rs::statistics`, `crates/frank/src/api.rs::breakdown`

#### Scenario: Public sees totals only

- GIVEN stored sightings
- WHEN a caller without a token asks `/v1/statistics`
- THEN it gets totals and no breakdown

**Tests:** `crates/frank/tests/api.rs::small_cells_are_suppressed_below_partner`

#### Scenario: Observers get categories, contributors detections

- GIVEN stored sightings
- WHEN an observer and a contributor ask `/v1/statistics`
- THEN the observer gets sector, type and severity breakdowns but no top rules; the contributor gets the top rules too

**Tests:** `crates/frank/tests/api.rs::small_cells_are_suppressed_below_partner`

#### Scenario: A window out of range is refused

- GIVEN `days=0`
- WHEN any caller asks `/v1/statistics`
- THEN the response is 422

**Tests:** `crates/frank/tests/api.rs::small_cells_are_suppressed_below_partner`

---

### Requirement 9: Explore dimensions need a status [MUST]

Grouping or filtering by sector, IoC type or severity MUST need observer; by rule, technique, campaign or IoC contributor. A query needs the highest status of its dimensions.

**Implementation:** `crates/frank/src/explore.rs::min_tier`

#### Scenario: The highest dimension decides

- GIVEN a query grouping by sector and filtering by rule
- WHEN its status is computed
- THEN it needs contributor

**Tests:** `crates/frank/src/explore.rs::tier_is_the_highest_dimension`

#### Scenario: An observer cannot group by rule

- GIVEN an observer token
- WHEN it asks `/v1/explore?group=rule`
- THEN the response is 403

**Tests:** `crates/frank/tests/api.rs::explore_enforces_tiers_and_refuses_unknown_names`

---

### Requirement 10: Records by status [MUST]

Below partner, a participant MUST see only the records it sent: listing `/v1/sightings` MUST need `mine=true` (otherwise 403), and `/v1/sightings/{id}` of another participant's sighting MUST answer 404. From partner up, every record at the visible TLP levels is listed. Records never carry the target's identity (Requirement 6).

**Implementation:** `crates/frank/src/api.rs::list`, `crates/frank/src/api.rs::sighting`

#### Scenario: A contributor lists its own

- GIVEN sightings from two contributors
- WHEN one of them lists `/v1/sightings` without and with `mine=true`
- THEN the first is 403, the second lists its own sightings only

**Tests:** `crates/frank/tests/api.rs::records_are_listed_by_status`

#### Scenario: Another's record is not found

- GIVEN a sighting sent by another participant
- WHEN a contributor asks for it by id
- THEN the response is 404

**Tests:** `crates/frank/tests/api.rs::records_are_listed_by_status`

---

### Requirement 11: The participant's own summary [MUST]

`/v1/summary?days=N` MUST need contributor and answer what the caller's participant sent in the window (sightings, observations, IoC rows, the last time one was received), and how many sightings in the window it may see from everyone, at its visible TLP levels.

**Implementation:** `crates/frank/src/api.rs::summary`

#### Scenario: Own counts and the network

- GIVEN three sightings from the caller's participant and one from another
- WHEN the caller asks `/v1/summary`
- THEN it gets its own three, their IoCs, and four sightings in the network

**Tests:** `crates/frank/tests/api.rs::records_are_listed_by_status`
