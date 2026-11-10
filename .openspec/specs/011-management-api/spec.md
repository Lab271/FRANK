# Management API Specification

**Domain:** API / Identity Administration
**Version:** 2.0.0
**Status:** Implemented
**Date:** 2026-11-07

**Owner:** Platform Team
- **Related ADR:** [ADR-017](../../architecture/decisions/017-user-roles-for-identity-administration.md), [ADR-002](../../architecture/decisions/002-tiered-access-control.md)
**Implementation:** `crates/frank/src/admin.rs::routes`
- **Database:** `participants.db` (SQLite, in the `--participants` directory)
**Tests:** `crates/frank/tests/api.rs`

## Overview

The management API lets organisations and their users be administered over HTTP under `/v1/admin/`. It replaces the Python-era Cognito management API; no external identity provider is involved. Participants, users and bearer tokens live in `participants.db`.

### Philosophy

- **Roles, not tiers**: a user's role (`admin`, `superadmin`) decides what it may administer; the organisation's status decides what it may see.
- **Scoped by organisation**: an admin manages its own organisation only; a superadmin manages every organisation.
- **Every change is audited**: each change writes an audit line naming `user@organisation`. Tokens appear only as a 12-hex-digit hash prefix.

### Key Capabilities

- **Organisations**: list, create and set the status of an organisation.
- **Users**: list, add, change role, disable, enable and remove.
- **Tokens**: list, issue and revoke bearer tokens.
- **Audit**: read the audit lines of a time window.
- **Files**: list the server's state directories (superadmin only).

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement 1: Access by role [MUST]

Every `/v1/admin/` route MUST require a caller that holds a role. A caller without a role MUST receive 403. An admin MUST NOT act on another organisation's objects; such an object MUST answer 404.

**Implementation:** `crates/frank/src/admin.rs::admin`, `crates/frank/src/admin.rs::manages`

#### Scenario: A plain user is refused

- GIVEN a user with no role
- WHEN it calls `GET /v1/admin/users`
- THEN the response is 403

**Tests:** `crates/frank/tests/api.rs::admins_manage_their_own_organisation_only`

#### Scenario: An admin is scoped to its own organisation

- GIVEN an admin of organisation A and an organisation B
- WHEN the admin lists organisations or changes a user of B
- THEN B is not listed, and the change answers 404

**Tests:** `crates/frank/tests/api.rs::admins_manage_their_own_organisation_only`

---

### Requirement 2: Organisations [MUST]

A superadmin MUST be able to create an organisation and set its status (`observer`, `contributor`, `partner`, `core`). An admin MUST see its own organisation only.

**Implementation:** `crates/frank/src/admin.rs::organisations`, `crates/frank/src/admin.rs::add_organisation`, `crates/frank/src/admin.rs::set_status`

#### Scenario: Only a superadmin creates or re-statuses an organisation

- GIVEN an admin and a superadmin
- WHEN the admin posts a new organisation or patches a status
- THEN the admin is refused with 403; the superadmin succeeds

**Tests:** `crates/frank/tests/api.rs::superadmins_and_the_guards`

---

### Requirement 3: Users and roles [MUST]

An admin MUST be able to add, disable, enable and remove users of its own organisation. Only a superadmin MUST be able to grant or take the superadmin role. A user MUST be removed only when it is disabled. A disabled user's tokens MUST stop working.

**Implementation:** `crates/frank/src/admin.rs::add_user`, `crates/frank/src/admin.rs::set_role`, `crates/frank/src/admin.rs::disable`, `crates/frank/src/admin.rs::enable`, `crates/frank/src/admin.rs::remove_user`

#### Scenario: Removing a user needs it disabled first

- GIVEN an active user
- WHEN it is removed
- THEN the removal is refused; once disabled it is removed with its tokens, and its name is free again

**Tests:** `crates/frank/tests/api.rs::users_are_disabled_then_removed`

---

### Requirement 4: Last-admin guards [MUST]

The platform MUST keep at least one working superadmin, and each organisation MUST keep at least one working admin. A user MUST NOT disable itself, and MUST NOT revoke its own last token.

**Implementation:** `crates/frank/src/admin.rs::keeps_admins`, `crates/frank/src/admin.rs::disable`, `crates/frank/src/admin.rs::revoke`

#### Scenario: The last admin cannot be disabled

- GIVEN an organisation with one working admin
- WHEN a superadmin disables it
- THEN the response is 409

**Tests:** `crates/frank/tests/api.rs::users_are_disabled_then_removed`

---

### Requirement 5: Tokens [MUST]

Issuing a token MUST return the plain token once, with `Cache-Control: no-store`. The server MUST store only the token's hash. Listing tokens MUST show a prefix, never the token.

**Implementation:** `crates/frank/src/admin.rs::tokens`, `crates/frank/src/admin.rs::add_token`, `crates/frank/src/admin.rs::revoke`

#### Scenario: An issued token authenticates

- GIVEN an admin issues a token for a user
- WHEN the token is used as a bearer token
- THEN `GET /v1/whoami` names that user

**Tests:** `crates/frank/tests/api.rs::admins_manage_their_own_organisation_only`

---

### Requirement 6: Audit [MUST]

Every change MUST write an audit line. An admin MUST see only the audit lines about its organisation; a superadmin MUST see all of them. Tokens MUST appear only as a prefix.

**Implementation:** `crates/frank/src/admin.rs::record`, `crates/frank/src/admin.rs::audit`

#### Scenario: The audit never holds a plain token

- GIVEN tokens issued and revoked through the API
- WHEN the audit log is read from disk
- THEN no token appears in plain

**Tests:** `crates/frank/tests/api.rs::admins_manage_their_own_organisation_only`

---

### Requirement 7: File listing [MUST]

A superadmin MUST be able to list one directory at a time under the `data` and `participants` roots. The listing MUST show names, kinds, sizes and times, never file contents. A path MUST NOT leave its root: `..`, absolute paths and symlinks pointing outside a root MUST be refused. Each listing MUST write a `files_listed` audit line.

**Implementation:** `crates/frank/src/admin.rs::files`, `crates/frank/src/admin.rs::resolve`

#### Scenario: Paths are confined to the roots

- GIVEN a superadmin
- WHEN it lists `data/../x`, `/etc`, or a symlink to `/`
- THEN the request is refused, and a listing of `data/audit` succeeds

**Tests:** `crates/frank/tests/api.rs::superadmins_list_files_inside_the_roots_only`

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 2025-01-20 | 0.1 | Platform Team | Initial management API (Python) |
| 2026-02-06 | 1.0 | SDD Migration | Formalized as specification (Cognito era) |
| 2026-11-07 | 2.0.0 | Platform Team | Rewritten for the Rust admin API (#222); Cognito and PostgreSQL removed |
