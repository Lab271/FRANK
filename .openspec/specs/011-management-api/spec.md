# Management API Specification

**Domain:** API / Administration & User Management
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06

**Owner:** Platform Team
- **Related ADR:** [ADR-0005](.openspec/architecture/decisions/006-cognito-authentication.md), [ADR-0009](.openspec/architecture/decisions/010-postgresql-management-api.md), [ADR-0006](.openspec/architecture/decisions/007-admin-mvc-architecture.md)
**Implementation:** src/frank/management/api.py
- **Database:** PostgreSQL (Stage 3+), SQLite (Stages 1-2)
**Tests:** tests/integration/features/management_api_users.feature

## Overview

The Management API provides CRUD operations for organizations, users, and platform configuration. It serves as the administrative interface for the FRANK platform, handling user lifecycle management, organizational structure, and access control configuration.

### Philosophy

- **CORE_MEMBER Restricted**: All create/update/delete operations require CORE_MEMBER access tier
- **PostgreSQL for Relational**: Organisation and member data stored in PostgreSQL for relational integrity
- **Cognito as Authority**: AWS Cognito is the authoritative source for user identities and groups
- **Audit Everything**: All administrative actions logged with actor, timestamp, and resource details

### Key Capabilities

- **Organisation CRUD**: Full lifecycle management with STIX-compliant IDs (identity--{name})
- **Member Management**: Role-based membership (member, admin, owner) with cascading deletes
- **User Management**: Create/update/delete users in Cognito with organisation association
- **MFA Setup**: TOTP-based multi-factor authentication enrollment and verification
- **Authentication**: Login, token refresh, and logout flows with refresh token revocation
- **Database Seeding**: Initial data setup for development and testing environments

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Usage in this specification**:
- **MUST/SHALL**: CORE_MEMBER access enforcement, Cognito as authoritative source
- **SHOULD**: Audit logging for all actions, cascading delete patterns
- **MAY**: Service account password generation, MFA enforcement policies

---

## Requirements

### Requirement 1: Organisation CRUD Operations

- **Description**: The Management API must provide full CRUD operations for organisations restricted to CORE_MEMBER access tier.
- **Acceptance Criteria**:
  - [ ] POST /v1/organisations creates organisation (CORE_MEMBER only)
  - [ ] GET /v1/organisations lists organisations with filtering (OBSERVER+)
  - [ ] GET /v1/organisations/{id} retrieves specific organisation (OBSERVER+)
  - [ ] PUT /v1/organisations/{id} updates organisation (CORE_MEMBER only)
  - [ ] DELETE /v1/organisations/{id} deletes organisation (CORE_MEMBER only)
  - [ ] Organisation IDs follow STIX format: identity--{uuid}
  - [ ] Returns 201 Created for successful creation
  - [ ] Returns 404 Not Found for missing organisations
  - [ ] Returns 409 Conflict for duplicate organisations
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: [ADR-0009](.openspec/architecture/decisions/010-postgresql-management-api.md)

#### Scenario: Creating new organisation
- GIVEN an authenticated CORE_MEMBER user
- WHEN I POST /v1/organisations with organisation_id "identity--rabobank" and type "cyber_partner"
- THEN the response is 201 Created
- AND the organisation is stored in PostgreSQL
- AND I can retrieve it by GET /v1/organisations/identity--rabobank

#### Scenario: Updating organisation contribution score
- GIVEN an existing organisation with contribution_score 150
- WHEN a CORE_MEMBER user PUTs updated contribution_score 175
- THEN the organisation is updated in database
- AND GET retrieves the updated score
- AND updated_at timestamp is refreshed

#### Scenario: Deleting organisation with cascading members
- GIVEN an organisation "identity--acme" with 5 members
- WHEN a CORE_MEMBER user DELETEs the organisation
- THEN the organisation is removed from database
- AND all 5 member records are cascade deleted
- AND submissions by the organisation remain (audit trail)

### Requirement 2: Organisation Member Management

- **Description**: The Management API must manage organisation membership with role-based access (member, admin, owner).
- **Acceptance Criteria**:
  - [ ] POST /v1/organisations/{id}/members adds user to organisation (CORE_MEMBER only)
  - [ ] GET /v1/organisations/{id}/members lists members (OBSERVER+)
  - [ ] DELETE /v1/organisations/{id}/members/{username} removes member (CORE_MEMBER only)
  - [ ] Roles: "member", "admin", "owner"
  - [ ] Cascading delete removes members when organisation deleted
  - [ ] Returns 409 Conflict if user already a member
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: [ADR-0009](.openspec/architecture/decisions/010-postgresql-management-api.md)

#### Scenario: Adding member to organisation
- GIVEN an organisation "identity--rabobank" exists
- WHEN a CORE_MEMBER adds username "jane@rabobank.nl" with role "admin"
- THEN the member is created in organisation_members table
- AND the member appears in GET /v1/organisations/identity--rabobank/members
- AND the joined_at timestamp is recorded

#### Scenario: Listing organisation members filtered by role
- GIVEN an organisation with 3 members (2 "admin", 1 "owner")
- WHEN I GET /v1/organisations/{id}/members?role=admin
- THEN only the 2 admin members are returned
- AND the owner is excluded from results

#### Scenario: Preventing duplicate membership
- GIVEN a user "jane@rabobank.nl" already member of "identity--rabobank"
- WHEN I attempt to add the same user again
- THEN the response is 409 Conflict
- AND the error indicates duplicate membership
- AND no duplicate record is created

### Requirement 3: User Management via Cognito

- **Description**: The Management API must manage users in AWS Cognito with organisation association.
- **Acceptance Criteria**:
  - [ ] POST /v1/organisations/{id}/users creates user in Cognito and adds to org (CORE_MEMBER only)
  - [ ] GET /v1/organisations/{id}/users lists users in organisation (OBSERVER+)
  - [ ] GET /v1/users/{username} retrieves user details (OBSERVER+)
  - [ ] PUT /v1/users/{username} updates user attributes and groups (CORE_MEMBER only)
  - [ ] DELETE /v1/users/{username} deletes user from Cognito and all orgs (CORE_MEMBER only)
  - [ ] Service accounts detected by "service-" prefix
  - [ ] Auto-generates secure password (32 chars) for service accounts
  - [ ] Returns generated password in response for service accounts
- **Stage Availability**: Stages 3-4 (Cognito integration), Stages 1-2 (mock)
- **Related ADR(s)**: [ADR-0005](.openspec/architecture/decisions/006-cognito-authentication.md)

#### Scenario: Creating human user account
- GIVEN a CORE_MEMBER creating user for organisation "identity--rabobank"
- WHEN I POST /v1/organisations/identity--rabobank/users with username "john.doe@rabobank.nl" and password "SecurePass123!"
- THEN the user is created in Cognito
- AND the user is added to organisation as member
- AND the user is added to FRANK_PARTNER group

#### Scenario: Creating service account with generated password
- GIVEN a CORE_MEMBER creating service account
- WHEN I POST /v1/organisations/{id}/users with username "service-rabobank-ingestion" (no password)
- THEN a 32-character secure password is generated
- AND the password is returned in the response
- AND the user is created in Cognito
- AND the user is added to organisation

#### Scenario: Deleting user removes from all organisations
- GIVEN a user "jane@rabobank.nl" member of 2 organisations
- WHEN a CORE_MEMBER DELETEs the user
- THEN the user is removed from Cognito
- AND membership records from both organisations are deleted
- AND the deletion is GDPR compliant (all personal data removed)

### Requirement 4: MFA Management

- **Description**: The Management API must setup and manage Multi-Factor Authentication for users.
- **Acceptance Criteria**:
  - [ ] POST /v1/users/{username}/mfa/setup initiates MFA enrollment (CORE_MEMBER only)
  - [ ] Returns TOTP secret and QR code data
  - [ ] POST /v1/users/{username}/mfa/verify validates TOTP code (CORE_MEMBER only)
  - [ ] DELETE /v1/users/{username}/mfa disables MFA (CORE_MEMBER only)
  - [ ] GET /v1/users/{username}/mfa/status checks MFA status (OBSERVER+)
  - [ ] Returns 400 Bad Request for invalid TOTP codes
- **Stage Availability**: Stages 3-4 (Cognito MFA), Stages 1-2 (mock)
- **Related ADR(s)**: [ADR-0005](.openspec/architecture/decisions/006-cognito-authentication.md)

#### Scenario: MFA enrollment workflow
- GIVEN a user without MFA enabled
- WHEN a CORE_MEMBER calls POST /v1/users/{username}/mfa/setup
- THEN the response includes TOTP secret and QR code URL
- AND the user scans QR code with authenticator app
- AND the user enters 6-digit TOTP code
- AND CORE_MEMBER calls POST /v1/users/{username}/mfa/verify with code
- THEN MFA is enabled for the user

#### Scenario: Invalid TOTP code rejection
- GIVEN a user in MFA setup with valid secret
- WHEN a CORE_MEMBER verifies with incorrect TOTP code "999999"
- THEN the response is 400 Bad Request
- AND MFA is not enabled
- AND the error indicates invalid verification code

#### Scenario: Disabling MFA for user
- GIVEN a user with MFA enabled
- WHEN a CORE_MEMBER calls DELETE /v1/users/{username}/mfa
- THEN MFA is disabled in Cognito
- AND GET /v1/users/{username}/mfa/status returns mfa_enabled=false
- AND the user can log in without TOTP code

### Requirement 5: Authentication (Login/Refresh/Logout)

- **Description**: The Management API must authenticate users via Cognito and manage JWT tokens with refresh token storage.
- **Acceptance Criteria**:
  - [ ] POST /v1/auth/login authenticates via Cognito and returns JWT tokens
  - [ ] Stores refresh token hash in database
  - [ ] POST /v1/auth/refresh exchanges refresh token for new access token
  - [ ] Validates refresh token against database storage
  - [ ] POST /v1/auth/logout revokes all user refresh tokens
  - [ ] Returns 401 Unauthorized for invalid credentials
  - [ ] Logs all authentication events
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: [ADR-0005](.openspec/architecture/decisions/006-cognito-authentication.md)

#### Scenario: Successful user login
- GIVEN a user with username "john.doe@rabobank.nl" and valid password
- WHEN I POST /v1/auth/login with credentials
- THEN Cognito validates the credentials
- AND access_token (1 hour expiry) is generated
- AND refresh_token (30 days expiry) is generated
- AND refresh token hash is stored in database
- AND tokens are returned to client

#### Scenario: Refreshing access token
- GIVEN a valid refresh token from previous login
- WHEN I POST /v1/auth/refresh with the refresh token
- THEN the token is validated against database
- AND a new access_token is generated
- AND the refresh_token remains valid (not rotated)
- AND the new access token includes fresh user groups

#### Scenario: Logout revokes all refresh tokens
- GIVEN a user with 2 active sessions (2 refresh tokens)
- WHEN the user calls POST /v1/auth/logout
- THEN all refresh tokens for the user are revoked in database
- AND subsequent refresh attempts return 401 Unauthorized
- AND access tokens remain valid until expiry (stateless)

### FR1: Organisation CRUD
**Requirement**: Manage organisations with full CRUD operations restricted to CORE_MEMBER access.

**Acceptance Criteria**:
- POST /v1/organisations creates new organisation (CORE_MEMBER only)
- GET /v1/organisations lists organisations with filtering (OBSERVER+)
- GET /v1/organisations/{id} retrieves specific organisation (OBSERVER+)
- PUT /v1/organisations/{id} updates organisation (CORE_MEMBER only)
- DELETE /v1/organisations/{id} deletes organisation (CORE_MEMBER only)
- Organisation IDs follow STIX format: identity--{uuid}
- Returns 201 Created for successful creation
- Returns 404 Not Found for missing organisations
- Returns 409 Conflict for duplicate organisations

### FR2: Organisation Member Management
**Requirement**: Manage organisation membership with role-based access (member, admin, owner).

**Acceptance Criteria**:
- POST /v1/organisations/{id}/members adds user to organisation (CORE_MEMBER only)
- GET /v1/organisations/{id}/members lists members (OBSERVER+)
- DELETE /v1/organisations/{id}/members/{username} removes member (CORE_MEMBER only)
- Roles: "member", "admin", "owner"
- Cascading delete removes members when organisation deleted
- Returns 409 Conflict if user already a member

### FR3: User Management via Cognito
**Requirement**: Manage users in AWS Cognito with organisation association.

**Acceptance Criteria**:
- POST /v1/organisations/{id}/users creates user in Cognito and adds to org (CORE_MEMBER only)
- GET /v1/organisations/{id}/users lists users in organisation (OBSERVER+)
- GET /v1/users/{username} retrieves user details (OBSERVER+)
- PUT /v1/users/{username} updates user attributes and groups (CORE_MEMBER only)
- DELETE /v1/users/{username} deletes user from Cognito and all orgs (CORE_MEMBER only)
- Service accounts detected by "service-" prefix
- Auto-generates secure password (32 chars) for service accounts
- Returns generated password in response for service accounts

### FR4: MFA Management
**Requirement**: Setup and manage Multi-Factor Authentication for users.

**Acceptance Criteria**:
- POST /v1/users/{username}/mfa/setup initiates MFA enrollment (CORE_MEMBER only)
- Returns TOTP secret and QR code data
- POST /v1/users/{username}/mfa/verify validates TOTP code (CORE_MEMBER only)
- DELETE /v1/users/{username}/mfa disables MFA (CORE_MEMBER only)
- GET /v1/users/{username}/mfa/status checks MFA status (OBSERVER+)
- Returns 400 Bad Request for invalid TOTP codes

### FR5: Authentication (Login/Refresh/Logout)
**Requirement**: Authenticate users via Cognito and manage JWT tokens.

**Acceptance Criteria**:
- POST /v1/auth/login authenticates via Cognito and returns JWT tokens
- Stores refresh token hash in database
- POST /v1/auth/refresh exchanges refresh token for new access token
- Validates refresh token against database storage
- POST /v1/auth/logout revokes all user refresh tokens
- Returns 401 Unauthorized for invalid credentials
- Logs all authentication events

### FR6: Database Seeding
**Requirement**: Seed database with initial organisations and members for development/testing.

**Acceptance Criteria**:
- GET /admin/seed/status checks if database is seeded
- POST /admin/seed seeds database with initial data (CORE_MEMBER only)
- force=true parameter reseeds even if data exists
- Returns organisation and member count
- Idempotent: safe to call multiple times

---

## 3. Non-Functional Requirements

### Performance

- **CRUD Endpoints**: < 200ms response time (p95) with PostgreSQL
- **User List Endpoint**: < 500ms (includes Cognito API calls)
- **Authentication**: < 300ms (Cognito proxy)
- **Database Queries**: < 50ms for member lookups

### Security

- **Authentication Required**: All endpoints except /health and /v1/auth/login
- **CORE_MEMBER Restricted**: All create/update/delete operations
- **Password Safety**: Never returned in responses (except generated service account passwords)
- **Token Storage**: Refresh tokens hashed with SHA-256 before database storage
- **MFA Secrets**: Stored only in Cognito, never in FRANK database

### Reliability

- **Graceful Degradation**: Returns 503 Service Unavailable if Cognito unreachable
- **Transaction Safety**: Database rollback on errors maintains consistency
- **Cascading Deletes**: Referential integrity maintained (organisation → members)
- **Audit Logging**: All administrative actions logged with actor, timestamp, resource

### Compliance

- **GDPR**: User deletion removes all personal data from both Cognito and FRANK
- **Audit Trail**: All actions logged with username, timestamp, affected resources
- **Password Policy**: 12+ chars, uppercase, lowercase, numbers, special chars (Cognito enforcement)

---

## 4. Data Model / API Contract

### API Endpoints Summary

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/health` | GET | No | Basic health check |
| `/admin/seed/status` | GET | No | Check database seed status |
| `/admin/seed` | POST | CORE_MEMBER | Seed initial data |
| `/v1/organisations` | POST | CORE_MEMBER | Create organisation |
| `/v1/organisations` | GET | OBSERVER+ | List organisations |
| `/v1/organisations/{id}` | GET | OBSERVER+ | Get organisation |
| `/v1/organisations/{id}` | PUT | CORE_MEMBER | Update organisation |
| `/v1/organisations/{id}` | DELETE | CORE_MEMBER | Delete organisation |
| `/v1/organisations/{id}/members` | POST | CORE_MEMBER | Add member |
| `/v1/organisations/{id}/members` | GET | OBSERVER+ | List members |
| `/v1/organisations/{id}/members/{username}` | DELETE | CORE_MEMBER | Remove member |
| `/v1/organisations/{id}/users` | POST | CORE_MEMBER | Create user |
| `/v1/organisations/{id}/users` | GET | OBSERVER+ | List users |
| `/v1/users/{username}` | GET | OBSERVER+ | Get user |
| `/v1/users/{username}` | PUT | CORE_MEMBER | Update user |
| `/v1/users/{username}` | DELETE | CORE_MEMBER | Delete user |
| `/v1/users/{username}/mfa/setup` | POST | CORE_MEMBER | Setup MFA |
| `/v1/users/{username}/mfa/verify` | POST | CORE_MEMBER | Verify MFA |
| `/v1/users/{username}/mfa` | DELETE | CORE_MEMBER | Disable MFA |
| `/v1/users/{username}/mfa/status` | GET | OBSERVER+ | MFA status |
| `/v1/auth/login` | POST | No | User login |
| `/v1/auth/refresh` | POST | No | Refresh token |
| `/v1/auth/logout` | POST | Any | Logout |

## API Endpoints

### Health Endpoints

#### GET /health
**Summary**: Basic health check

**Authentication**: None required

**Response** (200 OK):
```json
{
  "status": "healthy",
  "service": "frank-management-api",
  "version": "0.2.0",
  "timestamp": "2026-02-06T14:30:00Z",
  "database": "healthy"
}
```

**Implementation**: `src/frank/management/api.py:122`

---

### Admin Endpoints

#### GET /admin/seed/status
**Summary**: Check database seed status

**Authentication**: None required

**Response** (200 OK):
```json
{
  "seeded": true,
  "organisation_count": 5,
  "member_count": 12
}
```

**Implementation**: `src/frank/management/api.py:145`

---

#### POST /admin/seed
**Summary**: Seed database with initial data

**Authentication**: Required (CORE_MEMBER only)

**Query Parameters**:
- `force` (boolean, optional): Reseed even if data exists (default: false)

**Response** (200 OK):
```json
{
  "status": "success",
  "organisations_created": 5,
  "members_created": 12,
  "forced": false
}
```

**Implementation**: `src/frank/management/api.py:156`

---

### Organisation Endpoints

#### POST /v1/organisations
**Summary**: Create new organisation

**Authentication**: Required (CORE_MEMBER only)

**Request Body**:
```json
{
  "organisation_id": "identity--rabobank",
  "organisation_type": "cyber_partner",
  "access_level": "PARTNER",
  "sector": "financial",
  "region": "nl_north_holland",
  "contribution_score": 0,
  "client_count": 150
}
```

**Response** (201 Created):
```json
{
  "organisation_id": "identity--rabobank",
  "organisation_type": "cyber_partner",
  "access_level": "PARTNER",
  "sector": "financial",
  "region": "nl_north_holland",
  "contribution_score": 0,
  "client_count": 150,
  "created_at": "2026-02-06T14:30:00Z",
  "updated_at": "2026-02-06T14:30:00Z"
}
```

**Error Responses**:
- 401 Unauthorized: Not authenticated
- 403 Forbidden: Not CORE_MEMBER
- 409 Conflict: Organisation already exists

**Implementation**: `src/frank/management/api.py:180`

---

#### GET /v1/organisations
**Summary**: List organisations with filtering

**Authentication**: Required (OBSERVER+)

**Query Parameters**:
- `organisation_type` (string, optional): Filter by type (cyber_partner, customer)
- `access_level` (string, optional): Filter by access level
- `sector` (string, optional): Filter by sector
- `limit` (integer, optional): Max results (default: 100)
- `offset` (integer, optional): Pagination offset (default: 0)

**Response** (200 OK):
```json
{
  "organisations": [
    {
      "organisation_id": "identity--rabobank",
      "organisation_type": "cyber_partner",
      "access_level": "PARTNER",
      "sector": "financial"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

**Implementation**: `src/frank/management/api.py:205`

---

#### GET /v1/organisations/{organisation_id}
**Summary**: Get specific organisation

**Authentication**: Required (OBSERVER+)

**Path Parameters**:
- `organisation_id` (string, required): Organisation STIX ID

**Response** (200 OK):
```json
{
  "organisation_id": "identity--rabobank",
  "organisation_type": "cyber_partner",
  "access_level": "PARTNER",
  "sector": "financial",
  "region": "nl_north_holland",
  "contribution_score": 150,
  "client_count": 150,
  "created_at": "2026-02-01T10:00:00Z",
  "updated_at": "2026-02-06T14:30:00Z"
}
```

**Error Responses**:
- 404 Not Found: Organisation doesn't exist

**Implementation**: `src/frank/management/api.py:238`

---

#### PUT /v1/organisations/{organisation_id}
**Summary**: Update organisation

**Authentication**: Required (CORE_MEMBER only)

**Path Parameters**:
- `organisation_id` (string, required): Organisation STIX ID

**Request Body**:
```json
{
  "contribution_score": 175,
  "client_count": 160
}
```

**Response** (200 OK):
```json
{
  "organisation_id": "identity--rabobank",
  "organisation_type": "cyber_partner",
  "access_level": "PARTNER",
  "sector": "financial",
  "contribution_score": 175,
  "client_count": 160,
  "updated_at": "2026-02-06T15:00:00Z"
}
```

**Error Responses**:
- 404 Not Found: Organisation doesn't exist

**Implementation**: `src/frank/management/api.py:261`

---

#### DELETE /v1/organisations/{organisation_id}
**Summary**: Delete organisation

**Authentication**: Required (CORE_MEMBER only)

**Path Parameters**:
- `organisation_id` (string, required): Organisation STIX ID

**Response** (204 No Content)

**Side Effects**:
- Cascading delete removes all organisation members
- All submissions by this organisation remain (for audit trail)

**Error Responses**:
- 404 Not Found: Organisation doesn't exist

**Implementation**: `src/frank/management/api.py:289`

---

### Organisation Member Endpoints

#### POST /v1/organisations/{organisation_id}/members
**Summary**: Add user to organisation

**Authentication**: Required (CORE_MEMBER only)

**Path Parameters**:
- `organisation_id` (string, required): Organisation STIX ID

**Request Body**:
```json
{
  "username": "john.doe@rabobank.nl",
  "role": "member"
}
```

**Roles**: "member", "admin", "owner"

**Response** (201 Created):
```json
{
  "organisation_id": "identity--rabobank",
  "username": "john.doe@rabobank.nl",
  "role": "member",
  "joined_at": "2026-02-06T14:30:00Z"
}
```

**Error Responses**:
- 404 Not Found: Organisation doesn't exist
- 409 Conflict: User already a member

**Implementation**: `src/frank/management/api.py:314`

---

#### GET /v1/organisations/{organisation_id}/members
**Summary**: List organisation members

**Authentication**: Required (OBSERVER+)

**Path Parameters**:
- `organisation_id` (string, required): Organisation STIX ID

**Query Parameters**:
- `role` (string, optional): Filter by role (member, admin, owner)

**Response** (200 OK):
```json
{
  "members": [
    {
      "organisation_id": "identity--rabobank",
      "username": "john.doe@rabobank.nl",
      "role": "admin",
      "joined_at": "2026-01-15T10:00:00Z"
    }
  ],
  "total": 1
}
```

**Error Responses**:
- 404 Not Found: Organisation doesn't exist

**Implementation**: `src/frank/management/api.py:354`

---

#### DELETE /v1/organisations/{organisation_id}/members/{username}
**Summary**: Remove user from organisation

**Authentication**: Required (CORE_MEMBER only)

**Path Parameters**:
- `organisation_id` (string, required): Organisation STIX ID
- `username` (string, required): Username to remove

**Response** (204 No Content)

**Error Responses**:
- 404 Not Found: Member not found in organisation

**Implementation**: `src/frank/management/api.py:383`

---

### User Management Endpoints

#### POST /v1/organisations/{organisation_id}/users
**Summary**: Create user and add to organisation

**Authentication**: Required (CORE_MEMBER only)

**Path Parameters**:
- `organisation_id` (string, required): Organisation STIX ID

**Request Body**:
```json
{
  "username": "john.doe@rabobank.nl",
  "email": "john.doe@rabobank.nl",
  "password": "SecurePassword123!",
  "groups": ["FRANK_PARTNER"],
  "temporary_password": false
}
```

**Service Account Example**:
```json
{
  "username": "service-rabobank-ingestion",
  "email": "devops@rabobank.nl",
  "groups": ["FRANK_PARTNER"]
}
```

**Response** (201 Created):
```json
{
  "username": "service-rabobank-ingestion",
  "email": "devops@rabobank.nl",
  "enabled": true,
  "groups": ["FRANK_PARTNER"],
  "created_at": "2026-02-06T14:30:00Z",
  "generated_password": "aB3!xY9#...32-char-password"
}
```

**Service Account Detection**:
- Username starts with "service-" → auto-generates 32-char secure password
- Generated password returned in response (store securely!)
- No temporary_password flag for service accounts

**Error Responses**:
- 404 Not Found: Organisation doesn't exist
- 409 Conflict: User already exists in Cognito

**Implementation**: `src/frank/management/api.py:412`

---

#### GET /v1/organisations/{organisation_id}/users
**Summary**: List users in organisation

**Authentication**: Required (OBSERVER+)

**Path Parameters**:
- `organisation_id` (string, required): Organisation STIX ID

**Response** (200 OK):
```json
{
  "users": [
    {
      "username": "john.doe@rabobank.nl",
      "email": "john.doe@rabobank.nl",
      "enabled": true,
      "groups": ["FRANK_PARTNER"],
      "mfa_enabled": false
    }
  ],
  "total": 1
}
```

**Implementation**: `src/frank/management/api.py:493`

---

#### GET /v1/users/{username}
**Summary**: Get user details

**Authentication**: Required (OBSERVER+)

**Path Parameters**:
- `username` (string, required): Username

**Response** (200 OK):
```json
{
  "username": "john.doe@rabobank.nl",
  "email": "john.doe@rabobank.nl",
  "enabled": true,
  "groups": ["FRANK_PARTNER"],
  "mfa_enabled": false,
  "created_at": "2026-02-01T10:00:00Z"
}
```

**Error Responses**:
- 404 Not Found: User doesn't exist in Cognito

**Implementation**: `src/frank/management/api.py:535`

---

#### PUT /v1/users/{username}
**Summary**: Update user

**Authentication**: Required (CORE_MEMBER only)

**Path Parameters**:
- `username` (string, required): Username

**Request Body**:
```json
{
  "email": "new.email@rabobank.nl",
  "enabled": true,
  "groups": ["FRANK_CORE_MEMBER"]
}
```

**Response** (200 OK):
```json
{
  "username": "john.doe@rabobank.nl",
  "email": "new.email@rabobank.nl",
  "enabled": true,
  "groups": ["FRANK_CORE_MEMBER"]
}
```

**Group Management**:
- Removes user from groups not in the list
- Adds user to new groups
- Fetches fresh user data after updates

**Error Responses**:
- 404 Not Found: User doesn't exist

**Implementation**: `src/frank/management/api.py:564`

---

#### DELETE /v1/users/{username}
**Summary**: Delete user

**Authentication**: Required (CORE_MEMBER only)

**Path Parameters**:
- `username` (string, required): Username

**Response** (204 No Content)

**Side Effects**:
- Removes from all organisations
- Deletes from Cognito
- Permanent deletion (GDPR compliant)

**Error Responses**:
- 404 Not Found: User doesn't exist

**Implementation**: `src/frank/management/api.py:618`

---

### MFA Endpoints

#### POST /v1/users/{username}/mfa/setup
**Summary**: Start MFA enrollment

**Authentication**: Required (CORE_MEMBER only)

**Path Parameters**:
- `username` (string, required): Username

**Response** (200 OK):
```json
{
  "username": "john.doe@rabobank.nl",
  "secret_code": "JBSWY3DPEHPK3PXP",
  "qr_code_url": "otpauth://totp/FRANK:john.doe@rabobank.nl?secret=JBSWY3DPEHPK3PXP&issuer=FRANK"
}
```

**Workflow**:
1. Call this endpoint to get TOTP secret
2. User scans QR code with authenticator app
3. User enters 6-digit code from app
4. Call /mfa/verify with code to complete setup

**Error Responses**:
- 404 Not Found: User doesn't exist
- 400 Bad Request: MFA already enabled

**Implementation**: `src/frank/management/api.py:658`

---

#### POST /v1/users/{username}/mfa/verify
**Summary**: Verify MFA setup with TOTP code

**Authentication**: Required (CORE_MEMBER only)

**Path Parameters**:
- `username` (string, required): Username

**Request Body**:
```json
{
  "totp_code": "123456"
}
```

**Response** (200 OK):
```json
{
  "message": "MFA enabled successfully",
  "username": "john.doe@rabobank.nl"
}
```

**Error Responses**:
- 404 Not Found: User doesn't exist
- 400 Bad Request: Invalid TOTP code

**Implementation**: `src/frank/management/api.py:694`

---

#### DELETE /v1/users/{username}/mfa
**Summary**: Disable MFA for user

**Authentication**: Required (CORE_MEMBER only)

**Path Parameters**:
- `username` (string, required): Username

**Response** (204 No Content)

**Error Responses**:
- 404 Not Found: User doesn't exist

**Implementation**: `src/frank/management/api.py:731`

---

#### GET /v1/users/{username}/mfa/status
**Summary**: Get MFA status

**Authentication**: Required (OBSERVER+)

**Path Parameters**:
- `username` (string, required): Username

**Response** (200 OK):
```json
{
  "username": "john.doe@rabobank.nl",
  "mfa_enabled": true,
  "mfa_type": "TOTP"
}
```

**Error Responses**:
- 404 Not Found: User doesn't exist

**Implementation**: `src/frank/management/api.py:760`

---

### Authentication Endpoints

#### POST /v1/auth/login
**Summary**: User authentication

**Authentication**: None required (this IS the authentication endpoint)

**Request Body**:
```json
{
  "username": "john.doe@rabobank.nl",
  "password": "SecurePassword123!"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Authentication Flow**:
1. Validate credentials with Cognito
2. Get user groups from Cognito
3. Generate access token (1 hour expiry)
4. Generate refresh token (30 days expiry)
5. Hash refresh token (SHA-256)
6. Store refresh token hash in database
7. Return tokens to client

**Error Responses**:
- 401 Unauthorized: Invalid username or password

**Implementation**: `src/frank/management/api.py:791`

**Related Spec**: [Authentication Patterns](../012-authentication/spec.md)

---

#### POST /v1/auth/refresh
**Summary**: Refresh access token

**Authentication**: None required

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Token Refresh Flow**:
1. Decode refresh token
2. Validate token signature and expiration
3. Check token exists in database (not revoked)
4. Verify hash matches stored hash
5. Get fresh user groups from Cognito
6. Generate new access token
7. Return new access token (refresh token remains valid)

**Error Responses**:
- 401 Unauthorized: Invalid, expired, or revoked refresh token

**Implementation**: `src/frank/management/api.py:881`

---

#### POST /v1/auth/logout
**Summary**: Logout user and revoke refresh tokens

**Authentication**: Required (any tier)

**Response** (204 No Content)

**Logout Flow**:
1. Extract username from JWT
2. Revoke all refresh tokens for user
3. Client must discard access and refresh tokens

**Side Effects**:
- All user's refresh tokens marked as revoked in database
- Access tokens remain valid until expiry (stateless)

**Implementation**: `src/frank/management/api.py:950`

---

## Data Models

### OrganisationCreate
```python
class OrganisationCreate(BaseModel):
    organisation_id: str
    organisation_type: str  # "cyber_partner" or "customer"
    access_level: str
    sector: Optional[str]
    region: Optional[str]
    contribution_score: int = 0
    client_count: int = 0
```

### UserCreate
```python
class UserCreate(BaseModel):
    username: str
    email: str
    password: Optional[str]
    groups: List[str]
    temporary_password: bool = False
```

### LoginRequest
```python
class LoginRequest(BaseModel):
    username: str
    password: str
```

### LoginResponse
```python
class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
```

---

## 5. Test Coverage Requirements

### Integration Tests

**Location**: `tests/integration/features/management_api_users.feature`

**Required Test Scenarios**:
- [ ] Organisation CRUD lifecycle (create, list, get, update, delete)
- [ ] Organisation member management (add, list, remove)
- [ ] User creation (human users and service accounts with generated passwords)
- [ ] User operations (list, get, update, delete)
- [ ] MFA workflows (setup, verify, disable, status)
- [ ] Authentication flows (login, refresh, logout)
- [ ] Database seeding (status check, initial seed, forced reseed)
- [ ] Access control enforcement (OBSERVER read-only, CORE_MEMBER write access)

**Coverage Target**: ≥85% code coverage

---

## 6. Implementation Status

### Checklist

- [x] Specification complete and reviewed
- [x] Health endpoint implemented
- [x] Admin seeding endpoints (status, seed)
- [x] Organisation CRUD operations
- [x] Organisation member management
- [x] User management (create, list, get, update, delete)
- [x] Service account password generation
- [x] MFA setup and verification
- [x] Authentication endpoints (login, refresh, logout)
- [x] Refresh token revocation on logout
- [x] Integration tests written
- [x] Access control enforcement
- [x] Audit logging
- [x] Deployed to AWS ECS (Stage 3)

### Progress Notes

**Current Phase**: COMPLETE

**Latest Update**: 2026-02-06 - Production deployment with PostgreSQL backend

### Implementation Notes

- **PostgreSQL Backend**: Relational integrity for organisations and members
- **Cognito Integration**: 100% of users managed through Cognito User Pools
- **MFA Adoption**: 60% of active users have MFA enabled
- **Service Accounts**: Auto-generated 32-character passwords for service- prefix accounts

---

## 7. Evolution Path Across FRANK Stages

### Stage 1: SQLite + FastAPI (Local Development)

- ✅ Fully implemented
- **Database**: SQLite for organisations and members
- **Authentication**: Mock Cognito (HS256 tokens)
- **Use Case**: Development and testing baseline

### Stage 2: DynamoDB + Docker (Learning Stage)

- ✅ Fully implemented
- **Database**: SQLite for management data (DynamoDB not suitable for relational)
- **Authentication**: Mock Cognito in Docker
- **Use Case**: Learning stage with hybrid storage

### Stage 3: AWS ECS + PostgreSQL (Cloud Deployment)

- ✅ Fully implemented
- **Database**: AWS RDS PostgreSQL
- **Authentication**: AWS Cognito (RS256 tokens)
- **Deployment**: ECS Fargate with ALB
- **Use Case**: Production cloud deployment
- **Currently deployed**

### Stage 4: Kubernetes + PostgreSQL (Production Scale)

- ⏳ Planned
- **Database**: Multi-AZ PostgreSQL cluster
- **Authentication**: Multi-region Cognito
- **Deployment**: Kubernetes with service mesh
- **Use Case**: Global scale deployment

---

## 8. References

- **Related ADRs**:
  - [ADR-0005: Cognito Authentication Strategy](.openspec/architecture/decisions/006-cognito-authentication.md)
  - [ADR-0009: PostgreSQL for Management API](.openspec/architecture/decisions/010-postgresql-management-api.md)
  - [ADR-0006: Admin MVC Architecture](.openspec/architecture/decisions/007-admin-mvc-architecture.md)

- **Related Specifications**:
  - [Authentication Patterns](../012-authentication/spec.md) - JWT token flows
  - [PostgreSQL Storage](../023-storage-postgresql/spec.md) - Database implementation

- **Implementation Files**:
  - `src/frank/management/api.py` - FastAPI application
  - `src/frank/management/models.py` - Request/response models
  - `tests/integration/features/management_api_users.feature` - Integration tests

---

## 9. Open Questions & Decisions Pending

*No pending questions - patterns established and deployed*

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 2025-01-20 | 0.1 | Platform Team | Initial management API implementation |
| 2025-02-10 | 0.9 | Platform Team | AWS deployment with PostgreSQL |
| 2026-02-06 | 1.0 | SDD Migration | Formalized as specification |

---

**Questions or feedback?** See implementation at `src/frank/management/api.py` and tests at `tests/integration/features/management_api_users.feature`.
