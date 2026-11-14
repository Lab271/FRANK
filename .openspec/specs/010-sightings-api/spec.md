# Sightings API Specification

**Domain:** API / Sightings
**Version:** 3.2.0
**Status:** Implemented
**Date:** 2026-11-10

**Owner:** Platform Team
- **Related ADR:** [ADR-016](../../architecture/decisions/016-phase3-rust-on-db-core.md), [ADR-002](../../architecture/decisions/002-tiered-access-control.md), [ADR-009](../../architecture/decisions/009-explicit-error-communication.md), [ADR-017](../../architecture/decisions/017-user-roles-for-identity-administration.md)
- **Related specs:** 001 (submission model and `/v1/preview`), 013 (what each status sees), 014 (Explore, live, lists, geo, files), 021 (IoC lookups)

## Overview

The HTTP API through which participants send sightings and read their records back: who a request is, sending a batch, the receipt that makes a resend safe, and listing records. Every route is in `docs/openapi.yaml`.

### Philosophy

- **The sender's id is the registration**: a sighting carries a `sighting_id` the sender chooses. With the participant it identifies the sighting: sending it again is answered with the original receipt, other content under it is refused.
- **Stored under the organisation**: a sighting's `reporter` is the participant's opaque id, set by the server. Which user sent it is in the audit log only.
- **Explicit errors**: every refusal is a status code with `{"error": "..."}` saying what to change (ADR-009).

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement 1: Bearer token authentication [MUST]

A request without an `Authorization` header MUST be the public caller. A `Bearer` token MUST name one user of one participant, and the caller's status MUST be its participant's status. An unknown or revoked token, a token of a disabled user, or a header that is not `Bearer ...` MUST answer 401. A route that needs a higher status than the caller's MUST answer 403. The server MUST compare only the token's SHA-256, and MUST pick up changes to `participants.db` (statuses, revocations) on the next request, without a restart.

**Implementation:** `crates/frank/src/api.rs::require`, `crates/frank/src/store/participants.rs::caller`, `crates/frank/src/auth.rs::hash`

#### Scenario: An unknown token is refused

- GIVEN a token no user holds
- WHEN it posts to `/v1/sightings`
- THEN the response is 401

**Tests:** `crates/frank/tests/api.rs::tiers_gate_the_routes`

#### Scenario: A revoked token stops, the organisation's other users go on

- GIVEN two users of one organisation, each with a token
- WHEN one token is revoked
- THEN `/v1/whoami` with it answers 401, and with the other 200

**Tests:** `crates/frank/tests/api.rs::participants_are_the_reporters`

#### Scenario: A disabled user's token stops until it is enabled

- GIVEN a user with a working token
- WHEN the user is disabled, then enabled
- THEN its token answers 401, then works again

**Tests:** `crates/frank/tests/api.rs::users_are_disabled_then_removed`

#### Scenario: A status change applies on the next request

- GIVEN an observer organisation whose submission is refused with 403
- WHEN its status is set to contributor in `participants.db`
- THEN its next submission is accepted, with the same token and no restart

**Tests:** `crates/frank/tests/api.rs::participants_are_the_reporters`

---

### Requirement 2: Error responses [MUST]

Every error MUST be a JSON body `{"error": "<reason>"}` with the status code that fits: 401 unknown token, 403 status too low, 404 not found, 409 conflict, 415 unsupported content type, 422 a request the caller can correct. An internal failure MUST answer 500 with `internal error` and log the cause, never send it.

**Implementation:** `crates/frank/src/api.rs::into_response`, `crates/frank/src/api.rs::internal`, `crates/frank/src/api.rs::unprocessable`

#### Scenario: A refusal says why

- GIVEN a contributor
- WHEN it sends a sighting marked TLP:RED
- THEN the response is 422 and `error` names TLP:RED

**Tests:** `crates/frank/tests/api.rs::tlp_red_is_refused`

---

### Requirement 3: Health [MUST]

`GET /health` MUST answer without a token with `status: ok`, the server version, and the state of the geo databases and the IoC lists. Missing geo databases or lists MUST NOT make the server unhealthy.

**Implementation:** `crates/frank/src/api.rs::health`

#### Scenario: Health needs no token

- GIVEN no `Authorization` header
- WHEN `GET /health` is called
- THEN the response is 200

**Tests:** `crates/frank/tests/api.rs::tiers_gate_the_routes`

---

### Requirement 4: Who am I [MUST]

`GET /v1/whoami` MUST answer the caller's status (`tier`) and `label` (`user@organisation`, or `public`). For a user it MUST also answer the user, its role (`admin`, `superadmin` or null) and the participant's id, name and status.

**Implementation:** `crates/frank/src/api.rs::whoami`, `crates/frank/src/auth.rs::label`

#### Scenario: A user sees its organisation

- GIVEN a machine user `mdr-feed` of organisation `mdr`
- WHEN it calls `/v1/whoami`
- THEN the answer names user `mdr-feed`, label `mdr-feed@mdr` and the participant id of `mdr`

**Tests:** `crates/frank/tests/api.rs::participants_are_the_reporters`

#### Scenario: The role is shown

- GIVEN an admin and a user without a role
- WHEN each calls `/v1/whoami`
- THEN `role` is `admin` for the first and null for the second

**Tests:** `crates/frank/tests/api.rs::admins_manage_their_own_organisation_only`

#### Scenario: The public caller

- GIVEN no `Authorization` header
- WHEN `/v1/whoami` is called
- THEN the answer holds `tier: public` and `label: public`, and no user or participant

**Tests:** `crates/frank/tests/api.rs::whoami_without_a_token_is_public`

---

### Requirement 5: Who may send [MUST]

`POST /v1/sightings` MUST require the contributor status or higher. The public caller and observers MUST receive 403.

**Implementation:** `crates/frank/src/api.rs::submit`

#### Scenario: Below contributor is refused

- GIVEN the public caller and an observer
- WHEN each posts a sighting
- THEN both receive 403

**Tests:** `crates/frank/tests/api.rs::tiers_gate_the_routes`

---

### Requirement 6: Request formats [MUST]

A body MUST hold one sighting, a list of sightings or a STIX bundle, in the format its `Content-Type` names: `application/json` (also when no type is given), `application/yaml` or `application/stix+json`. Any other type MUST answer 415. A body that does not parse MUST answer 422. A batch MUST hold at most 100 sightings, and a body MUST be at most 2 MiB; the count is checked once the body has parsed, which the 2 MiB limit bounds. The same sighting in any format MUST be one sighting.

**Implementation:** `crates/frank/src/api.rs::submissions`, `crates/frank-core/src/formats.rs::parse`

#### Scenario: JSON, YAML and STIX are one sighting

- GIVEN the same sighting as JSON, YAML and a STIX bundle
- WHEN each is posted in turn
- THEN the first is `created` and the other two are `duplicate`

**Tests:** `crates/frank/tests/api.rs::json_yaml_and_stix_are_one_sighting`

#### Scenario: Another content type is refused

- GIVEN a sighting
- WHEN it is posted as `text/plain`
- THEN the response is 415

**Tests:** `crates/frank/tests/api.rs::json_yaml_and_stix_are_one_sighting`

#### Scenario: A batch of more than 100 is refused

- GIVEN a list of 101 sightings
- WHEN it is posted
- THEN the response is 422 and nothing is stored

**Tests:** `crates/frank/tests/api.rs::oversized_batches_and_inner_conflicts_are_refused`

---

### Requirement 7: The sender's sighting id [MUST]

Each sighting MUST carry a `sighting_id` chosen by the sender; a sighting without one MUST be refused with 422, naming the field. A batch that holds one id twice MUST store it once when both carry the same content, and MUST be refused with 422 when they differ.

**Implementation:** `crates/frank/src/api.rs::submit`

#### Scenario: No id is refused with the reason

- GIVEN a sighting without `sighting_id`
- WHEN it is posted
- THEN the response is 422 and `error` says `sighting_id is required`

**Tests:** `crates/frank/tests/api.rs::a_resend_is_recognised`

#### Scenario: One id twice in a batch with different content

- GIVEN a batch with two sightings under one id and different observables
- WHEN it is posted
- THEN the response is 422, naming the id as appearing twice, and nothing is stored

**Tests:** `crates/frank/tests/api.rs::oversized_batches_and_inner_conflicts_are_refused`

---

### Requirement 8: Receipts and resends [MUST]

Every accepted sighting MUST get a receipt: its `sighting_id`, the `digest` (SHA-256 of the normalised sighting), `received` (when first registered) and `status` (`created` or `duplicate`). A sighting sent again by the same participant with the same content MUST get its original receipt as `duplicate` and add no rows; the digest MUST NOT depend on key order, spelling of enumerations, evidence or technique order, or a server-filled timestamp. The response MUST be 201 when anything was created, else 200, with the receipts and the number of rows added. Another participant MAY use the same id: it is its own sighting.

**Implementation:** `crates/frank/src/api.rs::submit`, `crates/frank/src/store/registry.rs::digest`, `crates/frank/src/store/registry.rs::find`, `crates/frank/src/store/registry.rs::register`

#### Scenario: A batch is created

- GIVEN a contributor
- WHEN it posts two sightings with two observables each
- THEN the response is 201 with two receipts and 4 rows

**Tests:** `crates/frank/tests/api.rs::submit_then_look_up`

#### Scenario: A resend gets the original receipt

- GIVEN a stored sighting
- WHEN it is sent again with keys reordered and the severity in capitals
- THEN the response is 200, its receipt is `duplicate` with the original digest and `received`, and no rows are added

**Tests:** `crates/frank/tests/api.rs::a_resend_is_recognised`

#### Scenario: The digest ignores form, not content

- GIVEN one sighting written in two ways, and one with other content
- WHEN their digests are taken
- THEN the first two are equal and the third differs

**Tests:** `crates/frank/src/store/registry.rs::the_digest_ignores_form_not_content`

#### Scenario: Another organisation may use the same id

- GIVEN a sighting registered by organisation A
- WHEN organisation B sends it under the same id
- THEN B's sighting is `created`

**Tests:** `crates/frank/tests/api.rs::a_resend_is_recognised`

---

### Requirement 9: Conflicts [MUST]

Other content under an id the participant registered before MUST be refused with 409, naming the ids, and nothing of the batch MUST be stored. The refusal MUST be audited as `submit_refused`.

**Implementation:** `crates/frank/src/api.rs::submit`

#### Scenario: A changed sighting refuses the whole batch

- GIVEN a registered sighting
- WHEN a batch holds a new sighting and the registered one with another severity
- THEN the response is 409, the new sighting is not stored, and an audit line `submit_refused` names the conflicting id

**Tests:** `crates/frank/tests/api.rs::a_resend_is_recognised`

---

### Requirement 10: TLP:RED is refused [MUST]

A sighting marked TLP:RED MUST be refused with 422: RED is meant for named recipients, not a platform. Nothing of it MUST be stored.

**Implementation:** `crates/frank-core/src/model.rs::build`

#### Scenario: RED is refused

- GIVEN a contributor
- WHEN it sends a sighting with `tlp_level: TLP:RED`
- THEN the response is 422

**Tests:** `crates/frank/tests/api.rs::tlp_red_is_refused`

---

### Requirement 11: The reporter is the organisation [MUST]

Each stored row's `reporter` MUST be the sending participant's id, set by the server and never taken from the submission. It MUST NOT be a user or a token: two users of one organisation are one reporter.

**Implementation:** `crates/frank/src/api.rs::submit`

#### Scenario: Two users, one reporter

- GIVEN a person and a machine user of one organisation
- WHEN each sends a sighting
- THEN the sightings hold one distinct reporter: the organisation's id

**Tests:** `crates/frank/tests/api.rs::participants_are_the_reporters`

#### Scenario: No user name in the rows

- GIVEN user `mdr` sends sightings
- WHEN the sightings are queried for `reporter = 'mdr'`
- THEN none is found

**Tests:** `crates/frank/tests/api.rs::a_resend_is_recognised`

---

### Requirement 12: Storing a batch [MUST]

Submissions MUST be stored one batch at a time: checking the registrations, storing the rows and registering them MUST be one step. The rows MUST be appended to the sightings first, then the IoC table and the registration index. The registration index MUST be derivable from the sightings alone: on a new or old-schema `registry.db` it MUST be rebuilt from them, and its entries MUST expire with the sightings' retention, by arrival day.

**Implementation:** `crates/frank/src/api.rs::submit`, `crates/frank/src/store/registry.rs::open`, `crates/frank/src/store/registry.rs::rebuild`, `crates/frank/src/store/registry.rs::retain_from`

#### Scenario: A rebuilt index gives the same receipt

- GIVEN a stored sighting
- WHEN the registration index is rebuilt from the sightings and the sighting is sent again
- THEN the receipt equals the one before the rebuild

**Tests:** `crates/frank/tests/api.rs::a_resend_is_recognised`

#### Scenario: Registrations are per participant and expire

- GIVEN registrations of two participants on different days
- WHEN one participant looks an id up, and retention drops the older day
- THEN only its own registration is found, and the dropped day's is gone

**Tests:** `crates/frank/src/store/registry.rs::registrations_are_per_participant_and_expire`

---

### Requirement 13: Submissions are audited [MUST]

Each `POST /v1/sightings` that passes authentication and parsing MUST write one audit line: `submit` with the participant and the receipts, or `submit_refused` with the conflicting ids, by `user@organisation`. The audit log, not the sightings, records which user sent what. A request refused before that (no or an unknown token, a malformed `Authorization` header, a body that does not parse or is not a valid batch) MUST NOT be audited: it names no user, or changes nothing. Lines MUST be appended per UTC day and MUST be dropped by whole days with the sightings' retention.

**Implementation:** `crates/frank/src/api.rs::submit`, `crates/frank/src/audit.rs::record`, `crates/frank/src/audit.rs::retain_from`

#### Scenario: One line per POST, naming the user

- GIVEN three posts by one user, one by another organisation's user, and one refused post
- WHEN the audit log is read
- THEN it holds four `submit` lines and one `submit_refused`, each naming its `user@organisation`

**Tests:** `crates/frank/tests/api.rs::a_resend_is_recognised`

#### Scenario: Lines append per day and expire

- GIVEN audit lines on several days
- WHEN retention keeps from a later day
- THEN the earlier days' lines are gone

**Tests:** `crates/frank/src/audit.rs::lines_append_per_day_and_expire`

---

### Requirement 14: Listing sightings [MUST]

`GET /v1/sightings` MUST require the contributor status. Partners and core MUST list every visible sighting; below partner a caller MUST list its own only, with `mine=true`, and MUST receive 403 without it. The list MUST be in `(ts, sighting_id)` order (`order=desc` reverses it), paged by `limit` (1–500, default 100) and the `next_cursor` of the previous page, over the last 30 days unless `since`/`until` say otherwise, filterable by Explore's dimensions. An unknown parameter MUST answer 422. Paging MUST return every sighting exactly once, also when an IoC filter matches thousands.

**Implementation:** `crates/frank/src/api.rs::list`, `crates/frank/src/records.rs::parse`, `crates/frank/src/records.rs::sql`, `crates/frank/src/records.rs::ioc_sql`

#### Scenario: Records are listed by status

- GIVEN four sightings from two contributors
- WHEN a partner lists, pages and filters them, and a contributor lists with and without `mine=true`
- THEN the partner pages through all four, each once; the contributor gets 403 without `mine=true` and its own three with it; an unknown parameter is 422

**Tests:** `crates/frank/tests/api.rs::records_are_listed_by_status`

#### Scenario: An IoC filter pages through thousands

- GIVEN thousands of sightings sharing one IoC
- WHEN they are listed by that IoC, forwards and backwards
- THEN every sighting is listed exactly once, in order

**Tests:** `crates/frank/tests/api.rs::an_ioc_filter_pages_through_thousands`

---

### Requirement 15: One sighting [MUST]

`GET /v1/sightings/{id}` MUST require the contributor status and answer the sighting's record. Below partner only the caller's own sighting MUST be found; another's MUST answer 404. An id that does not parse MUST answer 422. When two participants chose the same id, the caller's own MUST come first.

**Implementation:** `crates/frank/src/api.rs::sighting`, `crates/frank/src/records.rs::item`

#### Scenario: Only its own below partner

- GIVEN a contributor's sighting and another contributor's
- WHEN the contributor and a partner fetch each by id
- THEN the contributor gets its own and 404 for the other; the partner gets both; `not-an-id` is 422

**Tests:** `crates/frank/tests/api.rs::records_are_listed_by_status`

---

### Requirement 16: The API description [MUST]

`GET /v1/openapi.json` MUST answer, without a token, the OpenAPI document `docs/openapi.yaml` as JSON. Every route of the router MUST be in it, each with the lowest status it needs (`x-min-status`).

**Implementation:** `crates/frank/src/api.rs::openapi`, `crates/frank/src/api.rs::router`

#### Scenario: Every route is documented

- GIVEN the routes in `api.rs` and `admin.rs`
- WHEN `/v1/openapi.json` is fetched
- THEN each route and method is in it with `x-min-status`

**Tests:** `crates/frank/tests/api.rs::every_route_is_in_the_openapi_document`

---

### Requirement 17: Security headers and limits [MUST]

Every response, the web UI's included, MUST carry a Content-Security-Policy that allows only FRANK's own origin (with `'wasm-unsafe-eval'` for the WASM module, no inline script, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. The server MUST handle at most `FRANK_MAX_CONCURRENCY` requests at once, across all routes; a request that is not answered within `FRANK_REQUEST_TIMEOUT`, waiting included, MUST get 503. HSTS is Caddy's to set (#244).

**Implementation:** `crates/frank/src/api.rs::harden`

#### Scenario: Every response carries the headers

- GIVEN the hardened router
- WHEN an answer, a refusal and an unknown route are requested
- THEN each response carries the CSP, nosniff and the referrer policy

**Tests:** `crates/frank/tests/api.rs::every_response_carries_the_security_headers`

#### Scenario: A slow request times out

- GIVEN a time limit shorter than a request takes
- WHEN the request is made
- THEN the answer is 503, with the headers

**Tests:** `crates/frank/tests/api.rs::a_slow_request_times_out_with_503`

#### Scenario: The limit is one for all routes

- GIVEN one slot and a request in progress on one route
- WHEN a request is made to another route
- THEN it waits for the slot, and past the time limit gets 503

**Tests:** `crates/frank/tests/api.rs::requests_wait_for_a_slot`

---

### Requirement 18: The access log [MUST]

FRANK MUST write one INFO line per request under the target `frank::access`, apart from its application lines (`frank`), with `request_id`, `method`, `uri` (path and query string), `status`, `latency_ms`, `caller` (`user@organisation`, `public`, or `unknown` when no token or session was resolved) and `tier`. The request id MUST be a ULID, returned as `X-Request-Id`. A line MUST NOT contain the `Authorization` header, the session cookie, a token, a request or response body, or the query of the SSO callback. With `FRANK_LOG_FORMAT=json` each line MUST be one JSON object with `target`; plain text is the default (#287).

**Implementation:** `crates/frank/src/access.rs::log`

#### Scenario: A request is one line with its query and caller

- GIVEN a partner's token
- WHEN a GET with a query string is made
- THEN exactly one `frank::access` line has the request id of `X-Request-Id`, the method, path and query, status 200, latency and `lab@lab` with its tier

**Tests:** `crates/frank/tests/api.rs::a_request_is_one_access_line_with_query_and_caller`

#### Scenario: Refused requests are logged

- GIVEN an unknown token and an observer's token
- WHEN each requests a partner route
- THEN the lines say 401 with `caller=unknown` and 403 with `caller=obs@obs`

**Tests:** `crates/frank/tests/api.rs::refused_requests_are_logged_with_their_status`

#### Scenario: Secrets are never logged

- GIVEN requests with a known token, a session cookie, a body and an SSO callback code
- WHEN they are logged
- THEN no line contains the token, `Bearer`, the cookie, the body or the code

**Tests:** `crates/frank/tests/api.rs::no_token_cookie_or_body_is_logged`

#### Scenario: JSON lines

- GIVEN `FRANK_LOG_FORMAT=json`
- WHEN a request is made
- THEN each line is a JSON object, and the access line has `target` `frank::access` and its fields at the top level

**Tests:** `crates/frank/tests/api.rs::json_format_is_one_object_per_line_with_target`

---

### Requirement 19: The runtime manifest at start [MUST]

`frank serve` MUST log its runtime manifest (mvl-manifest, embedded by `build.rs`) once when it starts, before anything else, under the target `mvl_manifest`: app version, toolchain, build provenance (`source_digest`, `lockfile_digest`, VCS where the build had it), the runtime and build packages with their sources and checksums, the runtime environment, and one WARN per condition that weakens assurance. The records MUST go through FRANK's log format (`FRANK_LOG_FORMAT=json` included), never straight to stderr; with `mvl_manifest` filtered out, nothing is logged. The other commands MUST NOT log it (#315).

**Implementation:** `crates/frank/src/serve.rs::log_manifest`

#### Scenario: The manifest is JSON lines under its own target

- GIVEN `FRANK_LOG_FORMAT=json` and `mvl_manifest=info`
- WHEN the manifest is logged
- THEN every line is a JSON object with `target` `mvl_manifest`, the first is the runtime manifest with this version, and the build provenance and runtime packages follow

**Tests:** `crates/frank/tests/api.rs::the_manifest_is_json_lines_under_its_own_target`

#### Scenario: Filtered out, nothing is logged

- GIVEN `mvl_manifest=off`
- WHEN the manifest would be logged
- THEN nothing is written

**Tests:** `crates/frank/tests/api.rs::mvl_manifest_off_logs_nothing`

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 2026-02-06 | 1.0 | SDD Migration | Phase 2 sightings API (FastAPI, Cognito), removed in #248 |
| 2026-11-10 | 3.0.0 | Platform Team | Rewritten for the Rust API (#250) |
| 2026-11-14 | 3.1.0 | Platform Team | Requirement 18: the access log (#287) |
| 2026-11-14 | 3.2.0 | Platform Team | Requirement 19: the runtime manifest at start (#315) |
