# IoC Lookups Specification

**Domain:** Storage / API: IoC index
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-11-10

**Owner:** Platform Team
- **Related ADR:** [ADR-016](../../architecture/decisions/016-phase3-rust-on-db-core.md), [ADR-019](../../architecture/decisions/019-sightings-in-s3-state-on-a-volume.md)
**Implementation:** `crates/frank/src/store/iocs.rs`, `crates/frank/src/api.rs::ioc_lookup`, `crates/frank/src/api.rs::ioc_range`
- **Database:** `data/iocs.db` (db-core row table, SQLite format; on the volume also with `FRANK_STORE`)
**Tests:** `crates/frank/tests/iocs.rs`, `crates/frank/tests/api.rs`

## Overview

"Is this IoC known, when, and which addresses in this block were seen?" are index seeks on `iocs.db`, not scans of the sightings table ([spec 020](../020-sightings-storage/spec.md)). The table holds one row per IoC per day per TLP level, kept with every submission and rebuildable from the sightings. A lookup then reads the details (rules, reporters, trend, panels) from the sightings, from the first day the index knows.

Which TLP levels and statuses see what is [spec 013](../013-disclosure/spec.md).

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement 1: One row per IoC, day and TLP [MUST]

`iocs.db` MUST hold table `ioc_day` with one row per normalised IoC (`k = type:value`), day the sightings arrived (`received`, else their timestamp), and TLP level: first and last timestamp of the sightings themselves and the sum of `observations`. Rows of one submission MUST be counted in one transaction, upserting on the unique key `k|day|tlp`. Each TLP level MUST be counted separately, so a lookup can leave out the levels a caller may not see.

**Implementation:** `crates/frank/src/store/iocs.rs::record`, `crates/frank/src/store/iocs.rs::upsert`

#### Scenario: Two sightings of one IoC are one day

- GIVEN two sightings on 2026-10-22 that both carry `evil.example`
- WHEN a contributor looks up `EVIL.example`
- THEN it is known, with count 2 on day 2026-10-22

**Tests:** `crates/frank/tests/api.rs::submit_then_look_up`

#### Scenario: Levels are counted apart

- GIVEN `evil.example` in four sightings, one each at CLEAR, GREEN, AMBER and AMBER+STRICT
- WHEN a contributor looks it up
- THEN the count is 3: the AMBER+STRICT sighting is left out

**Tests:** `crates/frank/tests/api.rs::each_tier_sees_its_tlp_levels`

---

### Requirement 2: Indexed keys and addresses [MUST]

The table MUST have B-tree indexes on `k`, on `kd` (unique), on `day` and on `ip_hex`. An IP address MUST be stored in `ip_hex` as 32 hex digits, IPv4 mapped into IPv6, so a CIDR block is one `BETWEEN` range. Other IoC types MUST have no `ip_hex`.

**Implementation:** `crates/frank/src/store/iocs.rs::open`, `crates/frank-core/src/observable.rs::ip_hex`

#### Scenario: Addresses sort as numbers

- GIVEN IPv4 addresses 10.0.0.1, 10.0.0.2 and 10.0.1.0, and a domain
- WHEN they are converted to `ip_hex`
- THEN 10.0.0.1 is `00000000000000000000ffff0a000001`, the order is numeric, and the domain has none

**Tests:** `crates/frank-core/src/observable.rs::ip_hex_orders_addresses`

---

### Requirement 3: Kept with every submission, rebuildable [MUST]

A submission MUST record its new rows in `iocs.db` right after appending them to the sightings table. `frank rebuild` (alias `rebuild-iocs`), with the server stopped, MUST empty `iocs.db` and count it again from the sightings, giving the same answers. An `iocs.db` from before TLP (#149) MUST be refused with a message to delete it and rebuild.

**Implementation:** `crates/frank/src/api.rs::submit`, `crates/frank/src/api.rs::rebuild_iocs`, `crates/frank/src/store/iocs.rs::clear`, `crates/frank/src/store/iocs.rs::open`

#### Scenario: A rebuild gives the same answer

- GIVEN two sightings of 1.2.3.4
- WHEN `iocs.db` is rebuilt from the sightings
- THEN a lookup returns the same days, with count 2

**Tests:** `crates/frank/tests/api.rs::iocs_rebuild_from_sightings`

#### Scenario: Every transaction is kept

- GIVEN five IoCs recorded in five transactions
- WHEN the database is reopened
- THEN five distinct IoCs are counted, and a sixth adds one

**Tests:** `crates/frank/tests/iocs.rs::every_transaction_is_kept`

---

### Requirement 4: Look up one IoC [MUST]

`GET /v1/iocs?type=…&value=…[&day=YYYY-MM-DD]` MUST require contributor status or above. The value MUST be normalised for its type before the seek; an unknown type, a value invalid for its type or a malformed `day` MUST answer 422. The answer MUST say whether the IoC is `known`, with its total `count`, distinct `reporters`, `first_seen` (the least first timestamp of its days), `last_seen`, the `days`, its `rules` ranked by count, a `trend`, Explore-style `panels` (limited to `day` when given), and, where they apply, its country and network (`geo`) and list matches (`listed`).

**Implementation:** `crates/frank/src/api.rs::ioc_lookup`, `crates/frank/src/store/iocs.rs::lookup`

#### Scenario: Observers may not look up

- GIVEN an observer token
- WHEN it calls `/v1/iocs`
- THEN the response is 403

**Tests:** `crates/frank/tests/api.rs::tiers_gate_the_routes`

#### Scenario: Known, unknown and invalid

- GIVEN stored sightings of `evil.example` with rule r1
- WHEN a contributor looks up `EVIL.example`, an unseen 10.0.0.1, and the IPv4 value `nope`
- THEN the first is known with rule r1 counted twice, the second is not known, and the third answers 422

**Tests:** `crates/frank/tests/api.rs::submit_then_look_up`

#### Scenario: Reporters are counted distinct

- GIVEN one IoC sent three times by two participants
- WHEN a partner looks it up
- THEN count is 3 and reporters is 2; below partner `reporters` and the rules follow spec 013 Requirement 4

**Tests:** `crates/frank/tests/api.rs::lookups_count_reporters`

#### Scenario: Panels for one day

- GIVEN sightings of one IoC on 2026-10-22
- WHEN a partner looks it up with `day=2026-10-22`, with `day=2026-10-23`, and with `day=22-10-2026`
- THEN the first has panels, the second has none, and the third answers 422

**Tests:** `crates/frank/tests/api.rs::lookup_panels_follow_explore_rules`

---

### Requirement 5: Addresses in a CIDR block [MUST]

`GET /v1/iocs/range?cidr=…` MUST require contributor status or above. An IPv4 or IPv6 block MUST be turned into its first and last address in `ip_hex` form; anything else MUST answer 422. The answer MUST list at most 1,000 addresses seen in the block at the caller's visible TLP levels, each with its count.

**Implementation:** `crates/frank/src/api.rs::ioc_range`, `crates/frank/src/api.rs::cidr_bounds`, `crates/frank/src/store/iocs.rs::ip_range`

#### Scenario: Two addresses in a /24

- GIVEN sightings of 185.220.102.45 and 185.220.102.46
- WHEN a contributor asks for `185.220.102.0/24`
- THEN two addresses are listed

**Tests:** `crates/frank/tests/api.rs::submit_then_look_up`

#### Scenario: Only visible levels are listed

- GIVEN addresses in 10.9.0.0/24 at several TLP levels
- WHEN a contributor asks for the block
- THEN the AMBER+STRICT address is left out

**Tests:** `crates/frank/tests/api.rs::each_tier_sees_its_tlp_levels`

#### Scenario: A malformed block is refused

- GIVEN `cidr=10.0.0.0/33`
- WHEN a contributor asks for it
- THEN the response is 422

**Tests:** `crates/frank/tests/api.rs::a_malformed_block_is_refused`

---

### Requirement 6: Retention [MUST]

Every hour, with the sightings' compaction, `iocs.db` MUST drop the days before the retention cut (`FRANK_RETENTION_DAYS`). Its days are arrival days, the clock the sightings table's retention uses, so an IoC is kept exactly as long as the rows it was counted from, also when a sighting is dated before it arrived (#257).

**Implementation:** `crates/frank/src/store/iocs.rs::retain_from`, `crates/frank/src/serve.rs::maintain`

#### Scenario: Old days are dropped

- GIVEN an IoC that arrived 40 days ago and one dated 40 days back that arrived today, with 30 days' retention
- WHEN retention runs
- THEN the first is no longer returned by a lookup; the second is, with its own first time

**Tests:** `crates/frank/tests/iocs.rs::retention_follows_arrival_not_the_sightings_own_time`
