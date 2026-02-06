# Specification: Management API

## Metadata

| Attribute | Value |
|-----------|-------|
| **Spec ID** | SPEC-API-002 |
| **Status** | IMPLEMENTED |
| **Version** | 0.2.0 |
| **Component** | src/frank/management/api.py |
| **Database** | PostgreSQL (Stage 3+), SQLite (Stages 1-2) |
| **Related ADRs** | ADR-0005 (Cognito Auth), ADR-0009 (PostgreSQL), ADR-0006 (Admin MVC) |
| **Related Specs** | [Authentication](authentication.spec.md), [PostgreSQL Storage](../storage/postgresql.spec.md) |
| **Test Files** | tests/integration/test_management_api.py |

---

## Purpose

The Management API provides CRUD operations for organizations, users, and platform configuration. It serves as the administrative interface for the FRANK platform, handling user lifecycle management, organizational structure, and access control configuration.

**Key Responsibilities**:
- Organisation CRUD (create, read, update, delete)
- Organisation member management
- User management via Cognito
- MFA setup and management
- Authentication (login, token refresh, logout)
- Database seeding for initial setup

---

## Functional Requirements

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

## Non-Functional Requirements

### NFR1: Performance
- CRUD endpoints: < 200ms response time (p95)
- User list endpoint: < 500ms (Cognito API calls)
- Authentication: < 300ms (Cognito proxy)

### NFR2: Security
- All endpoints except /health and /v1/auth/login require authentication
- CORE_MEMBER access required for all create/update/delete operations
- Passwords never returned in API responses (except generated service account passwords)
- Refresh tokens hashed with SHA-256 before storage
- MFA secrets stored only in Cognito

### NFR3: Reliability
- Graceful degradation if Cognito unavailable (503 Service Unavailable)
- Database transaction rollback on errors
- Cascading deletes maintain referential integrity
- Audit logging for all administrative actions

### NFR4: Compliance
- GDPR: User deletion removes all personal data
- Audit trail: All actions logged with actor, timestamp, resource
- Password policy: 12+ chars, uppercase, lowercase, numbers, special chars (enforced by Cognito)

---

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

**Related Spec**: [Authentication Patterns](authentication.spec.md)

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

## Test Coverage

### Integration Tests
**File**: tests/integration/test_management_api.py

**Scenarios**:
- [ ] Organisation CRUD lifecycle
- [ ] Organisation member management
- [ ] User creation (human and service accounts)
- [ ] User list, get, update, delete
- [ ] MFA setup, verify, disable, status
- [ ] Authentication (login, refresh, logout)
- [ ] Database seeding
- [ ] Access control (OBSERVER, CORE_MEMBER)

**Coverage Target**: ≥85%

---

## Related Documentation

- **ADR-0005**: Cognito Authentication Strategy
- **ADR-0009**: PostgreSQL for Management API
- **ADR-0006**: Admin MVC Architecture
- **Spec**: [Authentication Patterns](authentication.spec.md)
- **Spec**: [PostgreSQL Storage](../storage/postgresql.spec.md)
- **Implementation**: src/frank/management/api.py

---

**Document Version**: 1.0
**Last Updated**: 2026-02-06
**Status**: Approved for implementation
