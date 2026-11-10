# ADR-006: AWS Cognito Authentication Strategy

- **Status:** Superseded by [ADR-016](016-phase3-rust-on-db-core.md) (bearer tokens of users in `participants.db`)
- **Date:** 2026-01-29

## Context

FRANK requires user authentication and authorization for its Management API and Admin interfaces. Key requirements:

- **Multi-tenant**: Users belong to organisations with different access levels
- **Role-based access**: FRANK AccessTier (OBSERVER → CONTRIBUTOR → PARTNER → CORE_MEMBER)
- **Local development**: Must work without AWS dependencies
- **Cloud deployment**: Production-ready with AWS services
- **User management**: CRUD operations for users without maintaining a separate user database

Critical decision points:
1. Where to store user credentials and attributes?
2. How to validate authentication tokens?
3. How to map users to organisations?
4. How to enable local development without AWS costs?

## Decision

### User Storage: Cognito Only

**Users exist ONLY in AWS Cognito** - FRANK does not maintain a users table.

```
┌─────────────────────────────────────────────────────────────┐
│                     AWS Cognito (User Pool)                  │
│                                                              │
│  Human Users:                                                │
│    - username: "admin"                                       │
│    - email: "admin@schubergphilis.com"                       │
│    - password: [hashed by Cognito]                           │
│    - groups: ["FRANK_CORE_MEMBER"]                           │
│    - MFA: enabled/disabled                                   │
│                                                              │
│  Service Accounts:                                           │
│    - username: "service-rabobank-ingestion"                  │
│    - email: "service-rabobank@example.com"                   │
│    - password: [auto-generated, hashed by Cognito]           │
│    - groups: ["FRANK_CONTRIBUTOR"]                           │
│                                                              │
│  JWT Tokens (RS256 in AWS, HS256 in Mock)                   │
│  Token Refresh, Logout, MFA                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ JWT Token
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                FRANK Database (PostgreSQL/SQLite)            │
│                                                              │
│  organisations                                               │
│    - organisation_id: identity--{uuid4}                      │
│    - organisation_type: cyber_partner | customer            │
│    - access_level: observer | contributor | partner | core  │
│    - sector, region, metadata                                │
│                                                              │
│  organisation_members                                        │
│    - organisation_id (FK to organisations)                   │
│    - username (from Cognito, includes service-*)             │
│    - role: member | admin | owner                            │
│    - joined_at                                               │
│                                                              │
│  [Optional] refresh_tokens                                   │
│    - token_id, user_id, token_hash                           │
│    - For logout tracking (Cognito can handle this too)       │
└─────────────────────────────────────────────────────────────┘
```

### Database Role: Business Data Only

**What IS stored in FRANK database:**
- ✅ **Organisations**: Business entities (member orgs only, NOT targets)
- ✅ **Organisation Members**: Mapping of Cognito usernames to organisations with roles
- ✅ **Refresh Tokens** (optional): For manual logout tracking

**What is NOT stored in FRANK database:**
- ❌ **Users**: No users table (Cognito only)
- ❌ **Passwords**: Never stored anywhere in FRANK
- ❌ **Email/Attributes**: Always fetched from Cognito
- ❌ **API Keys**: No custom API key system (removed, was never intended per this ADR)
- ❌ **Access Tokens**: Stateless JWT validation via JWKS (no storage)
- ❌ **Target Organisations**: Victim orgs stored in DynamoDB with sightings

**Rationale**:
- **Security**: No credential storage in FRANK eliminates credential breach risk
- **Single Source of Truth**: User data always authoritative from Cognito
- **Simplicity**: No user synchronization needed between systems
- **Cognito Features**: MFA, password reset, account lockout handled by Cognito
- **Organisation Context**: Organisation membership is FRANK business logic, stored locally
- **Service Accounts**: Same as human users, just different naming convention in Cognito

### Dual-Mode Authentication

Support both Mock Cognito (local) and AWS Cognito (cloud) via environment variable:

```python
# Environment variable switches backend
FRANK_AUTH_MODE=local   # Mock Cognito (development)
FRANK_AUTH_MODE=aws     # AWS Cognito (production)
```

### Mock Cognito Service

FastAPI-based Cognito emulator for local development:

```
┌─────────────────────────────────────────────────────────────┐
│              docker-compose.local.yml                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐       ┌─────────────────────┐              │
│  │ Mock Cognito│◀─────▶│   Management API    │              │
│  │  :8100      │       │   :8001             │              │
│  └─────────────┘       └──────────┬──────────┘              │
│                                   │                          │
│                        ┌──────────▼──────────┐              │
│                        │  SQLite (volume)    │              │
│                        └─────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

**Pre-seeded test users:**

| Username | Password | Group | AccessTier |
|----------|----------|-------|------------|
| admin | admin123 | FRANK_CORE_MEMBER | CORE_MEMBER |
| partner | partner123 | FRANK_PARTNER | PARTNER |
| contributor | contrib123 | FRANK_CONTRIBUTOR | CONTRIBUTOR |
| observer | observer123 | FRANK_OBSERVER | OBSERVER |

### JWT Token Validation

Two validation strategies based on environment:

| Feature | Mock Cognito | AWS Cognito |
|---------|--------------|-------------|
| Algorithm | HS256 (shared secret) | RS256 (public key) |
| Validation | Direct JWT decode | JWKS endpoint |
| Token Source | Local mock service | AWS Cognito |
| Network | Local only | Internet required |

```python
# Auth module configuration
AuthConfig.configure(
    environment="mock",           # or "aws"
    validation_strategy="local_only",  # or "cognito_fallback"
    mock_cognito_url="http://localhost:8100",
    jwt_secret="local-dev-secret",
)
```

### Service Accounts

Service accounts are Cognito users with special naming convention:

**Naming:** `service-{organisation}-{purpose}`

**Examples:**
- `service-rabobank-ingestion` - Rabobank's data ingestion service
- `service-ing-threat-feed` - ING's threat feed automation
- `service-sunit-scanner` - S-Unit's automated scanning

**Authentication Flow:**
1. Service authenticates with Cognito using username/password
2. Cognito returns JWT access token (same as human users)
3. Service uses JWT token for all API calls
4. APIs validate JWT via JWKS endpoint (stateless)

**Password Management:**
- Passwords auto-generated during service account creation (32+ chars, secure)
- Stored only in Cognito (hashed)
- Rotated via Management API (generates new password)

**No Custom API Keys:**
Service accounts do NOT use custom API keys. They use Cognito JWT tokens exactly like human users. This eliminates the need for custom token management, key rotation, and key storage.

### Cognito Groups → AccessTier Mapping

Cognito groups map directly to FRANK AccessTier:

```python
GROUP_TO_TIER = {
    "FRANK_OBSERVER": AccessTier.OBSERVER,
    "FRANK_CONTRIBUTOR": AccessTier.CONTRIBUTOR,
    "FRANK_PARTNER": AccessTier.PARTNER,
    "FRANK_CORE_MEMBER": AccessTier.CORE_MEMBER,
}

def get_access_tier_from_groups(groups: List[str]) -> AccessTier:
    """Return highest tier from user's groups."""
    # Hierarchy: CORE_MEMBER > PARTNER > CONTRIBUTOR > OBSERVER
```

**Applies to both:**
- Human users: Access tier based on their Cognito groups
- Service accounts: Access tier based on their Cognito groups (same mechanism)

### Auth Module Structure

Extracted to reusable `src/frank/auth/`:

```
src/frank/auth/
├── __init__.py       # Public API exports
├── config.py         # AuthConfig singleton
├── jwt.py            # Local JWT validation
├── cognito.py        # AWS Cognito integration
└── dependencies.py   # FastAPI dependencies
```

**FastAPI Integration:**

```python
from frank.auth import get_current_user, require_access_tier
from frank.core.enum import AccessTier

@app.get("/organisations")
async def list_orgs(user: TokenPayload = Depends(get_current_user)):
    # Any authenticated user
    pass

@app.post("/organisations")
async def create_org(user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER))):
    # Only CORE_MEMBER can create organisations
    pass
```

## Consequences

### Positive

- **No Password Storage**: FRANK never handles user credentials
- **Standard OAuth2**: JWT tokens work with any OAuth2 client
- **Local Development**: Full auth flow without AWS costs
- **Parity**: Mock behaves identically to AWS for testing
- **Testable**: Auth module injectable for unit tests
- **Scalable**: Cognito handles millions of users

### Negative

- **AWS Dependency**: Production requires AWS Cognito
- **Mock Limitations**: Some Cognito features not emulated
- **Network Required**: AWS validation needs internet
- **Two Codepaths**: Mock vs AWS may diverge

### Tradeoffs

**Security vs Simplicity**: Using Cognito adds complexity but eliminates credential storage risk.

**AWS Lock-in vs Features**: Cognito provides MFA, account recovery, federation - would be expensive to build.

**Mock Fidelity vs Development Speed**: Mock is "good enough" for development, not perfect emulation.

## Alternatives Considered

### Self-Hosted Identity Provider (Keycloak)

Run Keycloak for both development and production.

**Rejected**: Additional infrastructure to maintain. Cognito is managed service with better AWS integration.

### Store Users in FRANK Database

Maintain users table with hashed passwords.

**Rejected**: Security responsibility for credentials. No benefit over Cognito. Duplicates user management.

### Custom API Keys

Use custom API keys (separate from Cognito) for service-to-service authentication.

**Rejected**: This alternative was explicitly rejected for multiple reasons:

1. **Doesn't support human users**: API keys alone can't handle Web GUI/TUI authentication
2. **No audit trail**: API keys don't identify individual users, only services
3. **Dual authentication systems**: Would require maintaining both Cognito (humans) and custom keys (services)
4. **Token management complexity**: Key generation, hashing, storage, rotation, revocation
5. **Security risk**: Another credential store to secure and audit
6. **No MFA**: API keys can't enforce multi-factor authentication

**Why Cognito for services too:**
Service accounts as Cognito users provide:
- ✅ Single authentication system for everything
- ✅ Same JWT token format (standard OAuth2)
- ✅ Stateless validation via JWKS
- ✅ No custom token management needed
- ✅ Same access tier enforcement
- ✅ Audit trail (username in JWT claims)

**Implementation Note:**
If custom API keys appear in any part of FRANK, they represent architectural drift from this ADR and should be removed. All authentication must flow through Cognito.

### Firebase Auth

Use Google's Firebase Authentication.

**Rejected**: Different cloud provider. FRANK is AWS-native. Would require Google Cloud account.

## Validation

Validated through Spike 014 (Cognito):

1. **Mock Cognito**: Local authentication working with Docker
2. **JWT Validation**: HS256 (mock) and RS256 (AWS) both working
3. **Role-based Access**: All 4 access tiers enforced correctly
4. **FastAPI Integration**: Dependencies work in endpoints
5. **Token Refresh**: Refresh token flow implemented

Test evidence:
- `tests/spikes/014_cognito/` - Spike implementation
- `tests/unit/auth/` - Auth module unit tests
- `tests/unit/management/test_api.py` - API endpoint auth tests

## Related ADRs

- ADR-0003: Tiered Access Control Model - AccessTier definitions
- ADR-0006: Admin MVC Architecture - Uses auth services

## Implementation Notes

Key files:
- `src/frank/auth/` - Reusable auth module
- `src/frank/management/api.py` - Management API using auth
- `tests/spikes/014_cognito/mock_cognito.py` - Mock implementation

Environment variables:
```bash
FRANK_AUTH_MODE=local|aws
FRANK_COGNITO_REGION=eu-central-1
FRANK_COGNITO_USER_POOL_ID=eu-central-1_xxxxx
FRANK_COGNITO_CLIENT_ID=xxxxxxxxxxxxx
FRANK_JWT_SECRET=local-dev-secret  # Mock only
```

Future considerations:
- Custom Cognito attributes for organisation affiliation
- Cognito triggers for user lifecycle events
- Multi-factor authentication enforcement
- Federation with external identity providers (Azure AD, Okta)

---

## Update Log

### 2026-01-31: Architecture Cleanup and Validation

**Issue Identified:**
During implementation, custom API keys were added to the Management API, contradicting this ADR's explicit rejection of custom API keys. This created architectural drift.

**Actions Taken:**
1. Removed custom API key system (PR #74)
   - Deleted `api_keys` table from PostgreSQL
   - Removed API key management endpoints
   - Removed API key generation and validation code

2. Implemented service accounts as Cognito users
   - Naming convention: `service-{org}-{purpose}`
   - Auto-generated passwords
   - Same JWT authentication as human users

3. Updated documentation
   - Issue #54 updated to remove API key references
   - Created `docs/glossary.md` defining all concepts
   - Created `docs/architecture-alignment-analysis.md` validating consistency

**Current State:**
Architecture now fully compliant with this ADR:
- ✅ Cognito only for all authentication
- ✅ No custom API keys
- ✅ Service accounts = Cognito users
- ✅ Stateless JWT validation
- ✅ Database stores only business data (organisations, members)

**Lesson:**
New features must validate against existing ADRs. If requirements change, either update the ADR explicitly or create a new ADR that supersedes it. Implementing features that contradict ADRs leads to architectural drift and wasted effort.
