# Specification: Authentication Patterns

## Metadata

| Attribute | Value |
|-----------|-------|
| **Spec ID** | SPEC-API-003 |
| **Status** | IMPLEMENTED |
| **Version** | 0.2.0 |
| **Component** | src/frank/auth/ |
| **Related ADRs** | ADR-0005 (Cognito Authentication Strategy) |
| **Related Specs** | [Sightings API](sightings-api.spec.md), [Management API](management-api.spec.md) |
| **Test Files** | tests/unit/auth/, tests/spikes/014_cognito/ |

---

## Purpose

Define the unified authentication and authorization patterns used across all FRANK APIs. This specification documents the **single authentication system** approach where AWS Cognito manages all authentication for both human users and service accounts.

**Key Principle**: ONE authentication system (AWS Cognito) for EVERYTHING - no custom API tokens, no local credential storage, no token management complexity.

---

## Functional Requirements

### FR1: JWT Token Generation
**Requirement**: Generate signed JWT tokens with user claims and group membership.

**Acceptance Criteria**:
- Access tokens expire in 1 hour
- Refresh tokens expire in 30 days
- Tokens include: username, groups, organisation_id, exp, iat, jti
- Tokens signed with RS256 (AWS) or HS256 (local development)
- JTI (JWT ID) included for refresh token tracking

### FR2: JWT Token Validation
**Requirement**: Validate JWT tokens using JWKS public key endpoint (stateless).

**Acceptance Criteria**:
- Fetch public keys from Cognito JWKS endpoint
- Cache JWKS keys for 24 hours
- Verify token signature using RS256 public key
- Verify token expiration (exp claim)
- Verify issuer (iss claim matches Cognito User Pool)
- Extract claims: username, groups, organisation_id
- Returns 401 Unauthorized for invalid tokens
- NO database queries during validation (stateless)

### FR3: Access Tier Mapping
**Requirement**: Map Cognito groups to FRANK AccessTier enum.

**Acceptance Criteria**:
- FRANK_OBSERVER → AccessTier.OBSERVER
- FRANK_CONTRIBUTOR → AccessTier.CONTRIBUTOR
- FRANK_PARTNER → AccessTier.PARTNER
- FRANK_CORE_MEMBER → AccessTier.CORE_MEMBER
- Default to AccessTier.PUBLIC for users with no groups
- Return highest tier if user has multiple groups
- Hierarchy: CORE_MEMBER > PARTNER > CONTRIBUTOR > OBSERVER > PUBLIC

### FR4: Token Refresh Flow
**Requirement**: Exchange refresh token for new access token without re-authentication.

**Acceptance Criteria**:
- Validate refresh token signature and expiration
- Check refresh token exists in database (not revoked)
- Verify stored hash matches provided token
- Fetch fresh user groups from Cognito
- Generate new access token with updated groups
- Return new access token (refresh token remains valid)
- Returns 401 Unauthorized if token revoked or invalid

### FR5: Logout and Token Revocation
**Requirement**: Revoke refresh tokens on logout to prevent reuse.

**Acceptance Criteria**:
- Revoke all user's refresh tokens in database
- Access tokens remain valid until expiry (stateless design)
- Client must discard both access and refresh tokens
- Logged action includes username and timestamp
- Returns 204 No Content on success

### FR6: Service Account Authentication
**Requirement**: Authenticate service accounts using username/password like human users.

**Acceptance Criteria**:
- Service accounts are Cognito users with "service-" prefix
- Authenticate via POST /auth/login (same as humans)
- Receive JWT tokens (same flow)
- Service account groups map to AccessTier (same as humans)
- No API keys, no custom token formats

---

## Non-Functional Requirements

### NFR1: Performance
- Token validation: < 2ms (JWKS cached)
- Token generation: < 10ms
- JWKS fetch: < 100ms (happens once per 24 hours)
- No database queries during token validation

### NFR2: Security
- Tokens signed with RS256 (production) or HS256 (local dev)
- Refresh tokens hashed with SHA-256 before database storage
- JWKS public keys fetched over HTTPS
- Token expiration strictly enforced
- No password storage in FRANK (Cognito only)
- No credential leakage in logs or error messages

### NFR3: Scalability
- Stateless validation enables horizontal scaling
- JWKS caching reduces Cognito API calls
- No shared session state between API instances
- Refresh token database queries minimal (only on /auth/refresh)

### NFR4: Reliability
- Graceful fallback to Mock Cognito in local development
- Invalid tokens return 401 with clear error messages
- Token expiration checked before every API call
- JWKS key rotation handled automatically

---

## Authentication Flows

### Flow 1: Human User Login (Web GUI)

```
┌──────────┐           ┌─────────────┐           ┌──────────┐
│ Web GUI  │           │  Mgmt API   │           │ Cognito  │
└────┬─────┘           └──────┬──────┘           └────┬─────┘
     │                        │                       │
     │ 1. POST /v1/auth/login │                       │
     ├───────────────────────▶│                       │
     │    {username, password}│                       │
     │                        │                       │
     │                        │ 2. InitiateAuth       │
     │                        ├──────────────────────▶│
     │                        │                       │
     │                        │ 3. Return tokens      │
     │                        │◀──────────────────────┤
     │                        │                       │
     │ 4. Return tokens       │                       │
     │◀───────────────────────┤                       │
     │                        │                       │
     │ 5. Store in memory     │                       │
     │    (NOT localStorage)  │                       │
```

**Key Points**:
- Web GUI calls Management API (no direct Cognito access)
- Management API proxies to Cognito for authentication
- Tokens stored in memory only (cleared on page refresh)
- Refresh token in HttpOnly cookie for security

---

### Flow 2: Service Account Authentication

```
┌──────────┐           ┌─────────────┐           ┌──────────┐
│ Service  │           │ Sightings   │           │ Cognito  │
│ (script) │           │    API      │           │          │
└────┬─────┘           └──────┬──────┘           └────┬─────┘
     │                        │                       │
     │ 1. POST /auth/login    │                       │
     ├───────────────────────▶│                       │
     │    {service-user, pw}  │                       │
     │                        │                       │
     │                        │ 2. InitiateAuth       │
     │                        ├──────────────────────▶│
     │                        │                       │
     │                        │ 3. Return JWT         │
     │                        │◀──────────────────────┤
     │                        │                       │
     │ 4. Return JWT          │                       │
     │◀───────────────────────┤                       │
     │                        │                       │
     │ 5. Cache token         │                       │
     │    (until expiry)      │                       │
```

**Service Account Example**:
```python
import requests

# Authenticate (same as human user)
response = requests.post(
    "https://api.frank-platform.eu/auth/login",
    json={
        "username": "service-rabobank-ingestion",
        "password": os.environ["FRANK_SERVICE_PASSWORD"]
    }
)

tokens = response.json()
access_token = tokens["access_token"]

# Use token for API calls
response = requests.post(
    "https://sightings.frank-platform.eu/submit",
    headers={"Authorization": f"Bearer {access_token}"},
    json=submission_data
)
```

---

### Flow 3: API Request with JWT Validation

```
┌──────────┐           ┌─────────────┐           ┌──────────┐
│  Client  │           │     API     │           │ Cognito  │
│          │           │             │           │  JWKS    │
└────┬─────┘           └──────┬──────┘           └────┬─────┘
     │                        │                       │
     │ 1. GET /observables    │                       │
     ├───────────────────────▶│                       │
     │    Authorization:      │                       │
     │    Bearer <JWT>        │                       │
     │                        │                       │
     │                        │ 2. Fetch JWKS keys    │
     │                        ├──────────────────────▶│
     │                        │    (cached 24h)       │
     │                        │                       │
     │                        │ 3. Public keys        │
     │                        │◀──────────────────────┤
     │                        │                       │
     │                        │ 4. Verify signature   │
     │                        │    Verify expiration  │
     │                        │    Extract claims     │
     │                        │                       │
     │                        │ 5. Map groups to      │
     │                        │    AccessTier         │
     │                        │                       │
     │                        │ 6. Query database     │
     │                        │    (if authorized)    │
     │                        │                       │
     │ 7. 200 OK              │                       │
     │◀───────────────────────┤                       │
     │    [filtered results]  │                       │
```

**Code Example**:
```python
from frank.auth import get_current_user

@app.get("/observables")
async def query_observables(
    user: TokenPayload = Depends(get_current_user)
):
    # user.username: Cognito username
    # user.access_tier: AccessTier enum
    # user.organisation_id: Organisation STIX ID
    # user.groups: List of Cognito groups

    # Access tier filtering applied automatically
    results = db.query_observables(
        access_level=user.access_tier
    )
    return results
```

---

### Flow 4: Token Refresh

```
┌──────────┐           ┌─────────────┐           ┌──────────┐
│  Client  │           │     API     │           │ Database │
└────┬─────┘           └──────┬──────┘           └────┬─────┘
     │                        │                       │
     │ 1. POST /auth/refresh  │                       │
     ├───────────────────────▶│                       │
     │    {refresh_token}     │                       │
     │                        │                       │
     │                        │ 2. Validate token     │
     │                        │    signature + exp    │
     │                        │                       │
     │                        │ 3. Check not revoked  │
     │                        ├──────────────────────▶│
     │                        │                       │
     │                        │ 4. Token valid        │
     │                        │◀──────────────────────┤
     │                        │                       │
     │                        │ 5. Generate new       │
     │                        │    access token       │
     │                        │                       │
     │ 6. New access token    │                       │
     │◀───────────────────────┤                       │
```

**Implementation**: `src/frank/management/api.py:881`

---

### Flow 5: Logout

```
┌──────────┐           ┌─────────────┐           ┌──────────┐
│  Client  │           │     API     │           │ Database │
└────┬─────┘           └──────┬──────┘           └────┬─────┘
     │                        │                       │
     │ 1. POST /auth/logout   │                       │
     ├───────────────────────▶│                       │
     │    {access_token}      │                       │
     │                        │                       │
     │                        │ 2. Revoke all user's  │
     │                        │    refresh tokens     │
     │                        ├──────────────────────▶│
     │                        │                       │
     │                        │ 3. Tokens revoked     │
     │                        │◀──────────────────────┤
     │                        │                       │
     │ 4. 204 No Content      │                       │
     │◀───────────────────────┤                       │
     │                        │                       │
     │ 5. Discard tokens      │                       │
     │    from memory         │                       │
```

**Implementation**: `src/frank/management/api.py:950`

---

## JWT Token Structure

### Access Token

```json
{
  "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "username": "john.doe@rabobank.nl",
  "groups": ["FRANK_PARTNER"],
  "organisation_id": "identity--rabobank",
  "iss": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_XXXXX",
  "exp": 1706784000,
  "iat": 1706780400,
  "jti": "uuid",
  "token_use": "access"
}
```

**Claims**:
- `sub`: Cognito user ID (UUID)
- `username`: User's username (email or service account name)
- `groups`: List of Cognito groups (e.g., ["FRANK_PARTNER"])
- `organisation_id`: Organisation STIX ID (custom attribute)
- `iss`: Issuer (Cognito User Pool URL)
- `exp`: Expiration timestamp (Unix epoch)
- `iat`: Issued at timestamp (Unix epoch)
- `jti`: JWT ID (unique identifier for this token)
- `token_use`: Token type ("access")

**Lifetime**: 1 hour (3600 seconds)

---

### Refresh Token

```json
{
  "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "username": "john.doe@rabobank.nl",
  "iss": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_XXXXX",
  "exp": 1709376400,
  "iat": 1706780400,
  "jti": "uuid",
  "token_use": "refresh"
}
```

**Claims**:
- Minimal claims (no groups or organisation_id)
- Used only for generating new access tokens
- Must be validated against database storage
- Hash stored in database (SHA-256)

**Lifetime**: 30 days (2,592,000 seconds)

---

## Access Tier Mapping

### Group to Tier Mapping

```python
# src/frank/auth/config.py

GROUP_TO_TIER = {
    "FRANK_OBSERVER": AccessTier.OBSERVER,
    "FRANK_CONTRIBUTOR": AccessTier.CONTRIBUTOR,
    "FRANK_PARTNER": AccessTier.PARTNER,
    "FRANK_CORE_MEMBER": AccessTier.CORE_MEMBER,
}

def map_groups_to_tier(groups: List[str]) -> AccessTier:
    """
    Return highest tier from user's Cognito groups.

    Hierarchy: CORE_MEMBER > PARTNER > CONTRIBUTOR > OBSERVER > PUBLIC
    """
    tiers = [GROUP_TO_TIER[g] for g in groups if g in GROUP_TO_TIER]

    if not tiers:
        return AccessTier.PUBLIC  # Default for no groups

    # Return highest tier
    tier_priority = [
        AccessTier.CORE_MEMBER,
        AccessTier.PARTNER,
        AccessTier.CONTRIBUTOR,
        AccessTier.OBSERVER,
        AccessTier.PUBLIC,
    ]

    for tier in tier_priority:
        if tier in tiers:
            return tier

    return AccessTier.PUBLIC
```

### Tier Capabilities

| AccessTier | Can Submit | Can Query | Can Admin |
|------------|-----------|-----------|-----------|
| PUBLIC | ❌ | Statistics only | ❌ |
| OBSERVER | ❌ | Masked observables | ❌ |
| CONTRIBUTOR | ✅ | Full observables | ❌ |
| PARTNER | ✅ | Full submissions | ❌ |
| CORE_MEMBER | ✅ | Everything + audit logs | ✅ |

---

## Token Storage and Security

### What FRANK Stores

```sql
-- refresh_tokens table (PostgreSQL/SQLite)
CREATE TABLE refresh_tokens (
    token_id TEXT PRIMARY KEY,           -- JWT jti claim
    user_id TEXT NOT NULL,                -- Username
    token_hash TEXT NOT NULL,             -- SHA-256 hash of token
    expires_at TEXT NOT NULL,             -- ISO 8601 timestamp
    revoked BOOLEAN DEFAULT FALSE,        -- Revocation flag
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Security Properties**:
- Tokens hashed with SHA-256 before storage (one-way)
- Original token never stored
- Revoked flag enables logout without waiting for expiry
- Expired tokens automatically cleaned up

---

### What FRANK Does NOT Store

```
❌ Passwords or password hashes
❌ MFA secrets
❌ API keys or API key hashes
❌ Access tokens (stateless validation)
❌ User credentials of any kind
❌ JWKS private keys (Cognito only)
```

**Rationale**: Database breach cannot compromise user credentials

---

## Mock Cognito (Local Development)

### Purpose

Enable local development without AWS account or internet connectivity.

### Implementation

**File**: `tests/spikes/014_cognito/mock_cognito.py`

**Features**:
- 100% AWS Cognito API compatible
- Pre-seeded with test users and service accounts
- HS256 token signing (simpler than RS256 for development)
- No external dependencies
- Runs in Docker: `http://localhost:8100`

### Mock vs Real Cognito

| Feature | Mock Cognito | AWS Cognito |
|---------|-------------|-------------|
| Token Signing | HS256 (shared secret) | RS256 (public key) |
| JWKS Endpoint | ✅ | ✅ |
| User Management | ✅ | ✅ |
| MFA | ✅ (simulated) | ✅ (real TOTP) |
| Password Policy | ✅ | ✅ |
| Group Management | ✅ | ✅ |
| Deployment | Docker container | AWS service |
| Cost | Free | AWS charges |

### Security Note

**CRITICAL**: Mock Cognito ONLY for local development
- Environment variable: `FRANK_AUTH_MODE=local` (explicit)
- Production MUST use `FRANK_AUTH_MODE=aws`
- CI/CD pipelines verify auth mode configuration
- Mock Cognito not deployed to cloud environments

---

## FastAPI Dependency Injection

### get_current_user (Any Authenticated User)

```python
from frank.auth import get_current_user

@app.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: str,
    user: TokenPayload = Depends(get_current_user)
):
    # Requires valid JWT token
    # Any access tier permitted
    # Access filtering applied by repository layer
    submission = db.get_submission_by_id(
        submission_id,
        access_level=user.access_tier
    )
    return submission
```

---

### require_access_tier (Minimum Tier Required)

```python
from frank.auth import require_access_tier
from frank.core.enum import AccessTier

@app.post("/organisations")
async def create_organisation(
    org_data: OrganisationCreate,
    user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER))
):
    # Requires CORE_MEMBER access tier
    # Returns 403 Forbidden if insufficient tier
    result = db.create_organisation(org_data.model_dump())
    return result
```

---

## Error Handling

### Authentication Errors

**401 Unauthorized**:
```json
{
  "detail": "Invalid or expired token",
  "status_code": 401
}
```

**Causes**:
- Missing Authorization header
- Invalid JWT signature
- Expired access token
- Token from different Cognito User Pool

---

**403 Forbidden**:
```json
{
  "detail": "Insufficient access tier: requires CORE_MEMBER",
  "status_code": 403
}
```

**Causes**:
- User authenticated but lacks required access tier
- OBSERVER trying to call CORE_MEMBER endpoint

---

## Test Coverage

### Unit Tests
**Directory**: tests/unit/auth/

**Files**:
- test_tokens.py: Token generation and validation
- test_dependencies.py: get_current_user, require_access_tier
- test_config.py: Group to tier mapping

**Scenarios**:
- [ ] Token generation with valid claims
- [ ] Token validation with JWKS
- [ ] Expired token rejection
- [ ] Invalid signature rejection
- [ ] Group to tier mapping (all tiers)
- [ ] Multiple groups (highest tier wins)
- [ ] No groups (PUBLIC tier)
- [ ] get_current_user with valid token
- [ ] require_access_tier with sufficient/insufficient tier

---

### Integration Tests (Spike 014)
**Directory**: tests/spikes/014_cognito/

**Scenarios**:
- [x] Mock Cognito authentication flow
- [x] JWT token validation against JWKS
- [x] Service account authentication
- [x] Token refresh flow
- [x] Logout and token revocation
- [x] HS256 vs RS256 token signing
- [x] Access tier mapping from groups

---

## Related Documentation

- **ADR-0005**: Cognito Authentication Strategy
- **ADR-0003**: Tiered Access Control Model
- **Spike 014**: Cognito Integration (tests/spikes/014_cognito/)
- **Implementation**: src/frank/auth/
- **Sightings API**: [Sightings API Spec](sightings-api.spec.md)
- **Management API**: [Management API Spec](management-api.spec.md)

---

**Document Version**: 1.0
**Last Updated**: 2026-02-06
**Status**: Approved for implementation
