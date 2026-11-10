# Data Model Specification

**Domain:** Core / Data Model
**Version:** 3.0.0
**Status:** Implemented
**Date:** 2026-11-10

**Owner:** Platform Team
- **Related ADR:** [ADR-016](../../architecture/decisions/016-phase3-rust-on-db-core.md), [ADR-008](../../architecture/decisions/008-forgiving-input-strong-output.md), [ADR-009](../../architecture/decisions/009-explicit-error-communication.md), [ADR-002](../../architecture/decisions/002-tiered-access-control.md)
- **Code:** `crates/frank-core` (shared by the server and the browser module)

## Overview

A submission becomes one normalised sighting (`frank/1`), and the sighting becomes the anonymised rows of the shared `sightings` table. `crates/frank-core` does both, in the server and in the browser (`frank-wasm`), so a contributor's preview runs the server's own parsing. This spec replaces the Phase 2 specs 001–004 (submission, observable, sighting, submitter/target).

### Philosophy

- **Forgiving input, strong output** (ADR-008): unknown fields are ignored, Phase 2's shape and STIX names are accepted, a value that could carry free text is dropped; what comes out is normalised and validated.
- **Passes on, does not judge** (ADR-016): every observable is kept with the sender's role and context; nothing is filtered by meaning.
- **No identities in the shared rows**: the target's id is kept for Core only, the sender is set by the server, never taken from the submission.
- **Errors name what is wrong** (ADR-009): `[1] confidence must be 0-100`.

### Key Capabilities

- **Formats**: JSON (Phase 2's shape or `frank/1`), YAML, STIX 2.1 bundles; one sighting, a list, or a bundle per body.
- **Observables**: nine IoC types, normalised per type.
- **TLP**: the sender's disclosure level per sighting; RED refused.
- **Registration**: the sender's `sighting_id` and a SHA-256 digest of the content.
- **Rows**: one per sighting × IoC, the normalised sighting on the first.
- **Preview**: the rows a submission would add, without storing it.

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement 1: Formats by Content-Type [MUST]

A request body MUST be read in the format its `Content-Type` names: `application/json`, `application/yaml` (also `application/x-yaml`, `text/yaml`, `text/x-yaml`) or `application/stix+json`; parameters are ignored. Without a `Content-Type` the server MUST read JSON; any other type MUST answer 415. Where nothing names the format (the browser, `frank load`), text starting with `{` or `[` is JSON, else YAML. A STIX bundle MUST be read as STIX whichever format named it. The same sighting in the three formats MUST be the same normalised record.

**Implementation:** `crates/frank-core/src/formats.rs::from_content_type`, `crates/frank-core/src/formats.rs::sniff`, `crates/frank-core/src/formats.rs::parse`, `crates/frank/src/api.rs::submissions`

#### Scenario: The Content-Type picks the format

- GIVEN `application/json; charset=utf-8`, `Application/YAML` and `application/stix+json;version=2.1`
- WHEN the format is looked up
- THEN they name JSON, YAML and STIX; `text/plain` names none

**Tests:** `crates/frank-core/src/formats.rs::content_types_name_formats`

#### Scenario: An unsupported Content-Type is 415

- GIVEN a valid JSON sighting
- WHEN it is posted as `text/plain`
- THEN the response is 415

**Tests:** `crates/frank/tests/api.rs::json_yaml_and_stix_are_one_sighting`

#### Scenario: One sighting in three formats is one record

- GIVEN the same sighting as JSON, YAML and a STIX bundle (`examples/formats/`)
- WHEN each is parsed, and the bundle also as plain JSON
- THEN all four give the same normalised sighting

**Tests:** `crates/frank-core/src/formats.rs::the_same_sighting_in_three_formats_is_one_record`

---

### Requirement 2: Batches [MUST]

A JSON or YAML body MUST hold one sighting or a list of them; a STIX bundle holds one per `sighting` object. Sightings MUST be returned in body order. An error MUST name the sighting it is about by its index (`[1] ...`). The API MUST refuse more than 100 sightings in one body with 422.

**Implementation:** `crates/frank-core/src/formats.rs::parse`, `crates/frank-core/src/formats.rs::at`, `crates/frank/src/api.rs::submissions`

#### Scenario: An error names the sighting

- GIVEN a list of two sightings, the second with `confidence: 101`
- WHEN it is parsed
- THEN the error is Invalid and starts with `[1] `

**Tests:** `crates/frank-core/src/formats.rs::errors_name_the_sighting`

#### Scenario: More than 100 sightings are refused

- GIVEN a list of 101 sightings
- WHEN it is posted to `/v1/sightings` or `/v1/preview`
- THEN the response is 422 and nothing is stored

**Tests:** `crates/frank/tests/api.rs::oversized_batches_and_inner_conflicts_are_refused`

---

### Requirement 3: Phase 2 shape and frank/1 [MUST]

A JSON or YAML sighting MUST be read as `frank/1` when its `format` is `"frank/1"`, as Phase 2's submission (`submitter`, `hit_target`, `sighting` with `sigma_detection`, `threat_context`, `observables`, optional `metadata`) when it has no `format`, and refused as Malformed for any other `format`. Both MAY be wrapped in `{"submission": ...}`. `organization_` and `organisation_` spellings MUST both be read. `frank/1` is what a normalised sighting serialises to, and MUST read back to the same sighting. An observable of an unknown type MUST be skipped in Phase 2's shape, which existing Phase 2 senders produce (ADR-008), and refused in `frank/1`, which FRANK itself writes and which must read back exactly (ADR-009).

**Implementation:** `crates/frank-core/src/model.rs::from_json`, `crates/frank-core/src/model.rs::phase2`, `crates/frank-core/src/model.rs::phase2_observable`, `crates/frank-core/src/model.rs::frank1`, `crates/frank-core/src/model.rs::common`

#### Scenario: Phase 2's minimal example parses

- GIVEN Phase 2's minimal submission
- WHEN it is parsed
- THEN confidence, timestamp and the two IoCs (an IPv4 address and a domain) are read

**Tests:** `crates/frank-core/src/model.rs::parses_the_phase2_minimal_example`

#### Scenario: Rules, sectors, files and email are read

- GIVEN a Phase 2 submission with a SIGMA rule (level in its embedded YAML), sectors, a campaign, techniques, a `files` entry with a hash and an `email` entry with sender and sender IP
- WHEN it is parsed
- THEN the rule id, title and level, sectors, campaign and techniques are set, the hash, address and IP are observables, and the entries' other fields are their context

**Tests:** `crates/frank-core/src/model.rs::reads_rules_sectors_files_and_email`

#### Scenario: frank/1 reads back what it writes

- GIVEN a parsed Phase 2 submission
- WHEN it is serialised as `frank/1` and parsed again
- THEN the sighting and its serialisation are unchanged

**Tests:** `crates/frank-core/src/model.rs::frank1_reads_back_what_it_writes`

#### Scenario: An unknown format is refused

- GIVEN `{"format": "frank/2"}`, or `frank/1` evidence of an unknown type
- WHEN it is parsed
- THEN the first is Malformed naming `frank/2`, the second Invalid

**Tests:** `crates/frank-core/src/model.rs::an_unknown_format_is_refused`

---

### Requirement 4: YAML is bounded [MUST]

YAML MUST be read as one YAML 1.2 document into JSON: plain scalars resolve as the core schema (null, booleans, numbers), quoted, block and tagged scalars are strings. Aliases MUST be refused, so a small document cannot expand into a large one; nesting MUST NOT exceed 64 levels; a mapping key MUST be a scalar.

**Implementation:** `crates/frank-core/src/yaml.rs::to_json`, `crates/frank-core/src/yaml.rs::scalar`

#### Scenario: A document is read as JSON

- GIVEN YAML with numbers, a list of quoted and plain strings, a mapping, a block scalar and an RFC 3339 time
- WHEN it is read
- THEN the JSON has numbers, strings, booleans and null where YAML 1.2 puts them, and the time stays a string

**Tests:** `crates/frank-core/src/yaml.rs::reads_a_document_as_json`

#### Scenario: Aliases and deep nesting are refused

- GIVEN a YAML alias bomb, 65 nested lists, a complex key, or an empty document
- WHEN it is read
- THEN each is Malformed; 10 nested lists are read; the API answers 422

**Tests:** `crates/frank-core/src/yaml.rs::refuses_aliases_and_deep_nesting`, `crates/frank/tests/api.rs::json_yaml_and_stix_are_one_sighting`

---

### Requirement 5: STIX bundles [MUST]

Each `sighting` object of a STIX 2.1 bundle MUST be one sighting: its `first_seen`, `last_seen`, `count`, `confidence`, `description`, the SIGMA `indicator` it is a sighting of (`pattern_type: sigma`) and the SCOs of its `observed-data`. The TLP MUST come from the first TLP marking among its `object_marking_refs` (a marking definition in the bundle by name, or a well-known TLP 2.0 or 1.0 id; WHITE is CLEAR). Identities, relationships and other objects MUST be ignored, so a bundle never names the reporter or the target. A bundle without `objects` or without a `sighting` MUST be refused as Malformed.

**Implementation:** `crates/frank-core/src/stix.rs::is_bundle`, `crates/frank-core/src/stix.rs::sightings`, `crates/frank-core/src/stix.rs::sighting`, `crates/frank-core/src/stix.rs::tlp`, `crates/frank-core/src/stix.rs::sigma`, `crates/frank-core/src/stix.rs::observable`

#### Scenario: A bundle holds several sightings and ignores the rest

- GIVEN a bundle with two `sighting` objects, an `identity` named in `where_sighted_refs`, and a relationship
- WHEN it is parsed
- THEN there are two sightings, and the identity's name is nowhere in them

**Tests:** `crates/frank-core/src/formats.rs::a_bundle_holds_several_sightings_and_ignores_the_rest`

#### Scenario: A TLP marking sets the level

- GIVEN the example bundle marked with TLP 2.0 AMBER's well-known id
- WHEN it is parsed
- THEN the sighting's TLP is AMBER

**Tests:** `crates/frank-core/src/formats.rs::the_same_sighting_in_three_formats_is_one_record`

#### Scenario: A bundle without sightings is refused

- GIVEN `{"type": "bundle", "objects": []}`, or a plain sighting sent as `application/stix+json`
- WHEN it is parsed
- THEN it is Malformed

**Tests:** `crates/frank-core/src/formats.rs::errors_name_the_sighting`

---

### Requirement 6: Observables [MUST]

An observable MUST be one of nine types: `ipv4`, `ipv6`, `domain`, `url`, `email`, `certificate`, `file_hash`, `registry_key`, `mutex`; the STIX names (`ipv4-addr`, `domain-name`, `x509-certificate`, ...) and `hash`, `md5`, `sha1`, `sha256` MUST be read too, in any case. A value MUST be trimmed and normalised for its type: IP addresses in canonical form, hashes as lower-case hex of 32, 40, 64 or 128 digits, URLs as sent, every other type in lower case. An empty value, one over 2048 characters, one with a control character, or a malformed address or hash MUST be refused. Each IoC has a lookup key `type:value`, and an IP address a 32-hex-digit form (IPv4 mapped into IPv6) so ranges compare as text.

**Implementation:** `crates/frank-core/src/observable.rs::parse`, `crates/frank-core/src/observable.rs::new`, `crates/frank-core/src/observable.rs::key`, `crates/frank-core/src/observable.rs::ip_hex`

#### Scenario: Values are normalised per type

- GIVEN `  EXAMPLE.com `, ` https://Evil.com/Path `, `2001:DB8:0:0::1`, an upper-case MD5 and `Global\MalwareMutex`
- WHEN each is normalised for its type
- THEN they are `example.com`, `https://Evil.com/Path`, `2001:db8::1`, the lower-case hash and `global\malwaremutex`

**Tests:** `crates/frank-core/src/observable.rs::normalises_per_type`

#### Scenario: Malformed values are refused

- GIVEN `999.1.1.1` as IPv4, `xyz` as a hash, a blank domain, a domain with a line break, a URL of 2049 characters
- WHEN each is normalised
- THEN each is refused

**Tests:** `crates/frank-core/src/observable.rs::refuses_malformed_values`

#### Scenario: STIX type names are read

- GIVEN `domain-name`, `SHA256` and `executable`
- WHEN the type is parsed
- THEN they are `domain`, `file_hash` and none; every type reads back from its own name

**Tests:** `crates/frank-core/src/observable.rs::parses_stix_names`

#### Scenario: IP addresses compare as text

- GIVEN `10.0.0.1`, `10.0.0.2` and `10.0.1.0`
- WHEN their hex forms are taken
- THEN `10.0.0.1` is `00000000000000000000ffff0a000001` and the order of the strings is the order of the addresses; a domain has none

**Tests:** `crates/frank-core/src/observable.rs::ip_hex_orders_addresses`

---

### Requirement 7: Forgiving input [SHOULD]

A value that cannot be used but does no harm SHOULD be dropped rather than refused (ADR-008):

- an observable with a blank value or no known type (a form left empty);
- a sector, size, region, role or context key that is not a label (`[a-z0-9_]`, at most 64 characters), so it cannot carry free text;
- a context value other than a short string, number or boolean, and context past 32 fields;
- a severity other than info, low, medium, high, critical; a SIGMA level other than informational, low, medium, high, critical;
- a technique that is not an ATT&CK id (`T1234` or `T1234.001`), a repeated one, and any past 16.

A confidence MAY be sent as a 0.0–1.0 score; it MUST be scaled to 0–100. Without one it is 69 (Phase 2's default).

**Implementation:** `crates/frank-core/src/model.rs::label`, `crates/frank-core/src/model.rs::clean_text`, `crates/frank-core/src/model.rs::context_value`, `crates/frank-core/src/model.rs::severity`, `crates/frank-core/src/model.rs::technique`, `crates/frank-core/src/model.rs::confidence`, `crates/frank-core/src/model.rs::filled`

#### Scenario: Blank observables are skipped

- GIVEN observables with empty and blank values, an unknown type, and an empty hash
- WHEN the sighting is parsed
- THEN only the one usable observable remains; with none left and no rule id, it is refused

**Tests:** `crates/frank-core/src/model.rs::blank_observables_are_skipped`

#### Scenario: A label that could carry free text is dropped

- GIVEN a submitter sector `ACME Corp, Utrecht`
- WHEN the sighting is parsed
- THEN it has no reporter sector

**Tests:** `crates/frank-core/src/model.rs::labels_that_could_carry_free_text_are_dropped`

#### Scenario: A score is scaled to percent

- GIVEN `confidence: 0.85`
- WHEN the sighting is parsed
- THEN its confidence is 85

**Tests:** `crates/frank-core/src/model.rs::a_score_is_scaled_to_percent`

#### Scenario: Techniques are validated, kept once and in order

- GIVEN techniques `T1195.001 `, `bogus`, `T1071.001` and `t1195.001`
- WHEN the sighting is parsed
- THEN its techniques are `T1195.001`, `T1071.001`

**Tests:** `crates/frank-core/src/model.rs::reads_rules_sectors_files_and_email`, `crates/frank-core/src/model.rs::the_builder_validates_its_setters`

---

### Requirement 8: Strict output [MUST]

A sighting MUST be refused (Invalid, 422 at the API) for: a confidence outside 0–100 (or a score outside 0.0–1.0), an `observation_count` that is not a whole number of at least 1, a time that is not RFC 3339, `first_seen` after `last_seen`, a time more than 5 minutes ahead of the server's clock, a `sighting_id` that is not a string or UUID, a malformed observable, more than 1000 observables, and neither an observable nor a SIGMA `rule_id`. When several are wrong, the first error found MUST be returned.

**Implementation:** `crates/frank-core/src/model.rs::build`, `crates/frank-core/src/model.rs::count`, `crates/frank-core/src/model.rs::time_field`, `crates/frank-core/src/model.rs::present`, `crates/frank/src/api.rs::unprocessable`

#### Scenario: What Phase 2 refused is refused

- GIVEN a non-object, a submission without `sighting`, an empty sighting, a rule without an id, and in turn each invalid field above
- WHEN each is parsed
- THEN the first two are Malformed, the rest Invalid

**Tests:** `crates/frank-core/src/model.rs::refuses_what_phase2_refused`

#### Scenario: The first error wins

- GIVEN a builder with confidence 101 and count 0
- WHEN it is built
- THEN the error names confidence

**Tests:** `crates/frank-core/src/model.rs::the_builder_validates_its_setters`

#### Scenario: Bad submissions are 422

- GIVEN an empty sighting, a body without `sighting`, or a confidence of 1.5
- WHEN it is posted to `/v1/sightings`
- THEN the response is 422 with an `error` string

**Tests:** `crates/frank/tests/api.rs::bad_submissions_are_422`

#### Scenario: Too many observables are refused

- GIVEN a sighting with 1001 distinct observables
- WHEN it is parsed
- THEN it is Invalid: more than 1000 observables

**Tests:** `crates/frank-core/src/model.rs::refuses_more_than_max_iocs_observables`

---

### Requirement 9: When it was observed [MUST]

A sighting MUST be dated by its own `timestamp`, else its last seen time, else its first seen time, else (Phase 2) the submission's `metadata.timestamp`, else the server's clock. Whether the time came from the sender MUST be recorded, so a server-filled time does not change the digest (Requirement 11).

**Implementation:** `crates/frank-core/src/model.rs::build`, `crates/frank-core/src/model.rs::phase2`

#### Scenario: The last observed time dates it

- GIVEN a Phase 2 sighting with first and last observed times and no timestamp
- WHEN it is parsed
- THEN it is dated by the last observed time and keeps the first as first seen

**Tests:** `crates/frank-core/src/model.rs::reads_rules_sectors_files_and_email`

#### Scenario: An undated sighting gets the server's clock

- GIVEN a sighting with a rule id and no time
- WHEN it is parsed
- THEN it is dated now, marked as not given by the sender, with count 1 and confidence 69

**Tests:** `crates/frank-core/src/model.rs::a_rule_without_observables_is_one_row`, `crates/frank-core/src/model.rs::the_builder_validates_its_setters`

---

### Requirement 10: TLP [MUST]

Each sighting MUST carry the sender's TLP 2.0 level, read from `tlp_level` or `tlp` on the sighting, else the submission, else (Phase 2) its `metadata`; GREEN when none is given. `TLP:AMBER`, `amber`, `AMBER+STRICT`, `AMBER+` and `WHITE` (as CLEAR) MUST be read in any case; an unknown level MUST be refused. TLP:RED MUST be refused (422): it is meant for named recipients, not for a platform. Every row of the sighting carries its level.

**Implementation:** `crates/frank-core/src/tlp.rs::parse`, `crates/frank-core/src/model.rs::tlp_level`, `crates/frank-core/src/model.rs::build`

#### Scenario: GREEN by default, the sighting's own level first

- GIVEN a submission without a level, one with `TLP:AMBER`, one with `amber+strict` in its metadata, and one with `amber` on the submission and `clear` on the sighting
- WHEN each is parsed
- THEN they are GREEN, AMBER, AMBER+STRICT and CLEAR, and every row carries the level

**Tests:** `crates/frank-core/src/model.rs::tlp_defaults_to_green_and_red_is_refused`, `crates/frank-core/src/tlp.rs::parses_tlp_spellings`

#### Scenario: TLP:RED is refused

- GIVEN a sighting marked `TLP:RED`
- WHEN it is posted to `/v1/sightings`
- THEN the response is 422 naming TLP:RED, and `purple` is refused as unknown

**Tests:** `crates/frank/tests/api.rs::tlp_red_is_refused`, `crates/frank-core/src/model.rs::tlp_defaults_to_green_and_red_is_refused`

---

### Requirement 11: Sighting id and digest [MUST]

The sender's `sighting_id` MUST be a UUID, bare, as `sighting--{uuid}` or as Phase 2's `sighting-{uuid}`, in any case; it MUST be stored as its 16 bytes and written as `sighting--{uuid}` in lower case. The digest MUST be the SHA-256 of the normalised sighting without its id, with a server-filled time left out and techniques in sorted order, so key order, spacing, case, and the order and repeats of evidence do not change it. Written in lower-case hex, stored as 32 bytes. With the participant, id and digest are the registration (spec 010). Because the digest sorts techniques, a resend that differs only in their order is a duplicate, and the rows keep the order of the first send.

**Implementation:** `crates/frank-core/src/model.rs::sighting_id`, `crates/frank-core/src/model.rs::parse`, `crates/frank/src/store/registry.rs::digest`, `crates/frank-core/src/model.rs::build`

#### Scenario: The sender names the sighting

- GIVEN the same UUID in upper case, with `sighting--` and with `sighting-`
- WHEN each is parsed
- THEN all give the same id, written `sighting--0f8fad5b-...`; `not-a-uuid`, `sight_789` and a UUID a digit short are refused; a digest reads back from its hex

**Tests:** `crates/frank-core/src/model.rs::the_sender_names_the_sighting`

#### Scenario: Evidence order is not content

- GIVEN two sightings with the same observables in another order, case and with a repeat
- WHEN both are parsed
- THEN they are equal

**Tests:** `crates/frank-core/src/model.rs::evidence_order_is_not_content`

#### Scenario: One sighting in three formats is one registration

- GIVEN the example sighting as JSON, YAML and STIX
- WHEN each is posted in turn
- THEN the first is created and the other two are duplicates of it

**Tests:** `crates/frank/tests/api.rs::json_yaml_and_stix_are_one_sighting`

---

### Requirement 12: Rows [MUST]

A sighting MUST add one row per distinct IoC to `sightings` (`seq` 0, 1, ...), or one row without an IoC when it carries none. Every row MUST repeat the sighting's time, id, rule id, techniques (a list), campaign, sectors, target size, severity, confidence, observation count and TLP; the `seq = 0` row MUST also carry the normalised sighting as JSON (`detail`), without the target's id. An observable's role and context MUST be kept in the detail and MUST NOT split or filter rows. No row MUST carry an organisation's identity: not the sender's, not the target's.

**Implementation:** `crates/frank-core/src/model.rs::rows`, `crates/frank-core/src/model.rs::detail`, `crates/frank-core/src/model.rs::iocs`

#### Scenario: One row per IoC, the detail on the first

- GIVEN a sighting with three IoCs, two techniques and a target id
- WHEN its rows are made
- THEN there are rows `seq` 0, 1, 2, each with both techniques; only row 0 has the detail, which reads back and has the target's sector but not its id

**Tests:** `crates/frank-core/src/model.rs::rows_are_one_per_ioc_with_the_detail_on_the_first`

#### Scenario: A rule without observables is one row

- GIVEN a sighting with a rule id only
- WHEN its rows are made
- THEN there is one row without an IoC

**Tests:** `crates/frank-core/src/model.rs::a_rule_without_observables_is_one_row`

#### Scenario: Role and context never filter

- GIVEN one IP address as `C2_server` (with port, protocol and a nested object) and as `victim`, and a domain as `benign`
- WHEN the sighting is parsed
- THEN there are three observables over two IoCs and two rows; the C2 role keeps port and protocol, the nested object is dropped, the benign one is kept

**Tests:** `crates/frank-core/src/model.rs::role_and_context_are_kept_and_never_filter`

#### Scenario: Nothing identifying is stored

- GIVEN a submission naming the submitter's and the target's organisation ids
- WHEN its rows are made, it is stored, or it is previewed
- THEN the target id is kept on the sighting for Core, and neither id appears in the rows, the stored table or the preview

**Tests:** `crates/frank-core/src/model.rs::rows_carry_no_organisation_identity`, `crates/frank/tests/api.rs::nothing_identifying_is_stored`

---

### Requirement 13: The server sets the reporter [MUST]

The row's `reporter` MUST be the sending participant's id, set by the server from the caller's token, never taken from the submission and never a user. The server MUST also set `received_ns` on every row and the digest on the `seq = 0` row.

**Implementation:** `crates/frank/src/api.rs::submit`

#### Scenario: Two users of one organisation are one reporter

- GIVEN two users of one participant, each sending a sighting
- WHEN the stored rows are counted by reporter
- THEN there is one distinct reporter, the participant's id

**Tests:** `crates/frank/tests/api.rs::participants_are_the_reporters`

---

### Requirement 14: Preview [MUST]

`POST /v1/preview` MUST parse a body exactly as `POST /v1/sightings` does (same formats, limits and errors) and answer with the rows it would add, without storing or registering anything. Any caller MAY use it, a public one too. The browser module MUST run the same parsing locally (spec 030).

**Implementation:** `crates/frank/src/api.rs::preview`, `crates/frank/src/api.rs::submissions`

#### Scenario: The preview shows the rows, without identities

- GIVEN a sighting with two IoCs naming organisation ids
- WHEN it is posted to `/v1/preview` without a token
- THEN the answer holds two rows and no organisation id

**Tests:** `crates/frank/tests/api.rs::nothing_identifying_is_stored`

#### Scenario: A preview stores nothing

- GIVEN an empty table
- WHEN a sighting is previewed
- THEN the table and the registry are still empty, and sending it afterwards is `created`, not a duplicate

**Tests:** `crates/frank/tests/api.rs::a_preview_stores_nothing`
