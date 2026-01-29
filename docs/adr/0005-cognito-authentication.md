# ADR-0005: AWS Cognito Authentication Strategy

## Status

Accepted

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
│                     AWS Cognito                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ User Pool                                            │    │
│  │  - username, email, password                         │    │
│  │  - groups: FRANK_OBSERVER, FRANK_CONTRIBUTOR, etc.  │    │
│  │  - custom attributes (future)                        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ JWT Token
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     FRANK Database                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ organisation_members                                 │    │
│  │  - organisation_id (FK to organisations)            │    │
│  │  - username (from Cognito)                          │    │
│  │  - role (member, admin, owner)                      │    │
│  │  - joined_at                                         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Rationale**:
- Cognito handles password hashing, MFA, account lockout
- No credential storage in FRANK reduces security risk
- User attributes (email, groups) always authoritative from Cognito
- Organisation membership is a FRANK concept, stored locally

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

### API Keys Only

Skip user authentication, use API keys for service-to-service auth.

**Rejected**: Doesn't support human users for admin interface. No audit trail per user.

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
