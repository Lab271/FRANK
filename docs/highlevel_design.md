# FRANK High-Level Design

**Document Status:** Draft
**Version:** 2.0
**Date:** 2026-01-31
**Author:** FRANK Architecture Team

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Component Descriptions](#component-descriptions)
4. [Authentication & Authorization](#authentication--authorization)
5. [Data Models](#data-models)
6. [Authentication Flows](#authentication-flows)
7. [Security Considerations](#security-considerations)
8. [Related ADRs](#related-adr-references)

---

## Executive Summary

FRANK (Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling) is a threat intelligence platform that demonstrates structured evolutionary architecture through clear separation of concerns. The platform uses a **dual-API architecture** where the Management API handles user and organization administration while the Sightings API handles high-volume threat intelligence data.

**Key Architecture Principle**: ONE authentication system (AWS Cognito) for EVERYTHING - no custom API tokens, no local credential storage, no token management complexity.

### Core Design Philosophy

1. **Single Authentication Provider**: AWS Cognito manages ALL authentication (humans and services)
2. **Stateless JWT Validation**: All APIs validate tokens using JWKS endpoint (no local state)
3. **Service Accounts = Cognito Users**: Service authentication uses Cognito users with service-prefixed names
4. **Minimal Database Schema**: PostgreSQL stores only business data (organisations, members) - no auth tables
5. **Cognito for Everything**: Token refresh, logout, user management all proxy to Cognito

### Architecture Simplification

**Traditional Approach (Complex)**:
```
❌ Custom API keys + JWT tokens
❌ api_keys table with hashing
❌ refresh_tokens table for revocation
❌ Token refresh logic in application
❌ Logout revocation lists
❌ Key rotation management
❌ Two authentication systems
```

**FRANK Approach (Simple)**:
```
✅ Cognito JWT tokens for everything
✅ organisations + organisation_members tables only
✅ Stateless JWKS validation
✅ Cognito handles refresh + logout
✅ No credential storage
✅ No key management
✅ One authentication system
```

---

## System Architecture

### High-Level Component Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         FRANK Platform Architecture                        │
└────────────────────────────────────────────────────────────────────────────┘

         Human Users                                      Service Accounts
    (Web GUI / TUI / CLI)                              (Ingestion Services)
                │                                                  │
                │                                                  │
                ▼                                                  │
    ┌────────────────────┐                                        │
    │   Web GUI          │                                        │
    │   (FastAPI/React)  │                                        │
    │                    │                                        │
    │  • User Management │                                        │
    │  • Org Admin       │                                        │
    │  • Dashboards      │                                        │
    │  • Reports         │                                        │
    └────────┬───────────┘                                        │
             │                                                    │
             │ HTTP/REST API                                      │
             │                                                    │
             ▼                                                    │
    ┌────────────────────┐                                        │
    │  Management API    │                                        │
    │   (FastAPI)        │                                        │
    │                    │                                        │
    │  • User CRUD       │                                        │
    │  • Organisation    │                                        │
    │    Management      │                                        │
    │  • Member Roles    │                                        │
    │  • Auth Proxy      │◀────────┐                              │
    └────────┬───────────┘         │                              │
             │                     │                              │
             ▼                     │                              │
    ┌────────────────────┐         │                              │
    │   PostgreSQL       │         │                              │
    │   (AWS RDS)        │         │                              │
    │                    │         │                              │
    │  • organisations   │         │                              │
    │  • members         │         │                              │
    └────────────────────┘         │                              │
                                   │                              │
                                   │  Auth operations             │
                                   │  (login, MFA, etc)           │
                                   │                              │
                                   ▼                              │
                      ┌─────────────────────────┐                 │
                      │    AWS Cognito          │◀────────────────┘
                      │  (ONE Auth System)      │  Direct auth
                      │                         │  (services only)
                      │  • User Pool            │
                      │  • JWT Tokens           │
                      │  • Groups (Tiers)       │
                      │  • Service Accounts     │
                      │  • Token Refresh        │
                      │  • Logout & MFA         │
                      └────────┬────────────────┘
                               │
                               │ JWT validation (JWKS)
                               │
                               ▼
                    ┌────────────────────┐
                    │   Sightings API    │
                    │   (FastAPI)        │
                    │                    │
                    │  • Submit          │
                    │  • Query           │
                    │  • Statistics      │
                    │  • Aggregations    │
                    └────────┬───────────┘
                             │
                             ▼
                    ┌────────────────────┐
                    │   DynamoDB         │
                    │                    │
                    │  • submissions     │
                    │  • observables     │
                    │  • sightings       │
                    │  • statistics      │
                    │  • target orgs     │
                    └────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Local Development Environment                              │
│  • Mock Cognito (port 8100)                                 │
│  • PostgreSQL (port 5432)                                   │
│  • SQLite fallback (Stage 1)                                │
└─────────────────────────────────────────────────────────────┘
```

**Key Architecture Points:**
- **Web GUI connects ONLY to Management API** (not directly to Cognito)
- **Management API proxies auth** to Cognito (login, MFA, user management)
- **Service accounts authenticate directly** with Cognito, then use Sightings API
- **Sightings API validates JWT** directly with Cognito JWKS endpoint (stateless)

### Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Request Flow                                   │
└─────────────────────────────────────────────────────────────────────────────┘

1. Human User Login (Web GUI)
   ┌──────────┐  POST /login     ┌─────────────┐  InitiateAuth   ┌──────────┐
   │ Web GUI  │ ───────────────▶ │ Mgmt API    │ ──────────────▶ │ Cognito  │
   │          │ ◀─────────────── │             │ ◀────────────── │          │
   └──────────┘  JWT Token       └─────────────┘  JWT + Refresh  └──────────┘

2. Service Authentication (Ingestion)
   ┌──────────┐  POST /login     ┌─────────────┐  InitiateAuth   ┌──────────┐
   │ Service  │ ───────────────▶ │ Sightings   │ ──────────────▶ │ Cognito  │
   │ (script) │ ◀─────────────── │    API      │ ◀────────────── │          │
   └──────────┘  JWT Token       └─────────────┘  JWT Token      └──────────┘

   Service credentials: username="service-rabobank-ingestion", password=[secret]

3. API Request with JWT (Management API)
   ┌──────────┐  GET /orgs       ┌─────────────┐  Validate JWT   ┌──────────┐
   │  Client  │ ───────────────▶ │ Mgmt API    │ ──────────────▶ │ JWKS     │
   │          │   Authorization: │             │ ◀────────────── │ Endpoint │
   │          │   Bearer <JWT>   │             │  Valid/Invalid  └──────────┘
   │          │                  │             │
   │          │ ◀─────────────── │             │ ───▶ PostgreSQL Query
   └──────────┘  Response        └─────────────┘ ◀─── organisations

4. API Request with JWT (Sightings API)
   ┌──────────┐  POST /submit    ┌─────────────┐  Validate JWT   ┌──────────┐
   │  Client  │ ───────────────▶ │ Sightings   │ ──────────────▶ │ JWKS     │
   │          │   Authorization: │    API      │ ◀────────────── │ Endpoint │
   │          │   Bearer <JWT>   │             │  Valid/Invalid  └──────────┘
   │          │                  │             │
   │          │ ◀─────────────── │             │ ───▶ DynamoDB Write
   └──────────┘  Response        └─────────────┘ ◀─── submission_id

5. Token Refresh (Stateless Proxy)
   ┌──────────┐  POST /refresh   ┌─────────────┐  RefreshToken   ┌──────────┐
   │  Client  │ ───────────────▶ │   API       │ ──────────────▶ │ Cognito  │
   │          │   refresh_token  │             │ ◀────────────── │          │
   │          │ ◀─────────────── │             │  New JWT        └──────────┘
   └──────────┘  New JWT Token   └─────────────┘

6. Logout (Stateless Proxy)
   ┌──────────┐  POST /logout    ┌─────────────┐  GlobalSignOut  ┌──────────┐
   │  Client  │ ───────────────▶ │   API       │ ──────────────▶ │ Cognito  │
   │          │   access_token   │             │ ◀────────────── │          │
   │          │ ◀─────────────── │             │  Success        └──────────┘
   └──────────┘  200 OK          └─────────────┘
```

---

## Component Descriptions

### 1. AWS Cognito (Authentication Hub)

**Purpose**: Single source of truth for ALL authentication in FRANK platform.

**Responsibilities**:
- Store user credentials (passwords, MFA secrets)
- Authenticate users and services
- Issue JWT access tokens and refresh tokens
- Manage user groups (FRANK_OBSERVER, FRANK_CONTRIBUTOR, etc.)
- Handle token refresh and logout
- Provide JWKS endpoint for token validation

**Configuration**:
```yaml
User Pool: frank-platform-users
Region: eu-central-1

User Attributes:
  - email (required, verified)
  - given_name
  - family_name
  - custom:organisation_id (links to PostgreSQL)

Groups (mapped to AccessTier):
  - FRANK_OBSERVER         → AccessTier.OBSERVER
  - FRANK_CONTRIBUTOR      → AccessTier.CONTRIBUTOR
  - FRANK_PARTNER          → AccessTier.PARTNER
  - FRANK_CORE_MEMBER      → AccessTier.CORE_MEMBER

Password Policy:
  - Minimum 12 characters
  - Uppercase + lowercase + numbers + special chars
  - MFA: Optional for OBSERVER/CONTRIBUTOR, Required for PARTNER/CORE_MEMBER

Token Validity:
  - Access Token: 1 hour
  - Refresh Token: 30 days
  - ID Token: 1 hour
```

**Service Accounts**:
Service accounts are regular Cognito users with naming convention: `service-{org}-{purpose}`

Examples:
- `service-rabobank-ingestion` - Rabobank automated threat feed ingestion
- `service-kpn-siem-export` - KPN SIEM export service
- `service-monitor-healthcheck` - Platform health monitoring

**Why This Works**:
- Cognito doesn't distinguish between human and service users
- Services authenticate with username/password like humans
- Same JWT token flow, same validation, same access control
- No custom API key management needed

**Mock Cognito (Local Development)**:
- FastAPI service implementing Cognito authentication API
- Pre-seeded with test users and service accounts
- 100% AWS Cognito API compatible
- Runs in Docker: `http://localhost:8100`

### 2. Management API (User & Organization Administration)

**Purpose**: CRUD operations for users, organisations, and platform configuration.

**Technology Stack**:
- Framework: FastAPI (Python 3.13)
- Database: PostgreSQL 16 (AWS RDS)
- Authentication: JWT validation via Cognito JWKS
- Deployment: ECS Fargate (AWS)

**API Endpoints**:

```python
# Authentication (proxy to Cognito)
POST   /auth/login           # Username/password → JWT
POST   /auth/refresh         # Refresh token → new JWT
POST   /auth/logout          # Revoke tokens
POST   /auth/change-password # Change password

# User Management (CORE_MEMBER only)
GET    /users                # List all users
POST   /users                # Create user in Cognito
GET    /users/{username}     # Get user details
PUT    /users/{username}     # Update user
DELETE /users/{username}     # Delete user
POST   /users/{username}/reset-password  # Admin password reset

# Organisation Management
GET    /organisations        # List organisations
POST   /organisations        # Create organisation (CORE_MEMBER)
GET    /organisations/{id}   # Get organisation
PUT    /organisations/{id}   # Update organisation
DELETE /organisations/{id}   # Delete organisation (CORE_MEMBER)

# Organisation Members
GET    /organisations/{id}/members           # List members
POST   /organisations/{id}/members           # Add member (admin/owner)
DELETE /organisations/{id}/members/{username} # Remove member
PUT    /organisations/{id}/members/{username} # Update member role

# Health & Monitoring
GET    /health               # Basic health check
GET    /health/deep          # Database connectivity check
```

**Access Control**:
```python
from frank.auth import get_current_user, require_access_tier
from frank.core.enum import AccessTier

@app.get("/organisations")
async def list_organisations(
    user: TokenPayload = Depends(get_current_user)
):
    # Any authenticated user can list their organisations
    pass

@app.post("/organisations")
async def create_organisation(
    org_data: dict,
    user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER))
):
    # Only CORE_MEMBER can create organisations
    pass
```

**Database Schema** (PostgreSQL):
```sql
-- Organisations (business entities)
CREATE TABLE organisations (
    organisation_id TEXT PRIMARY KEY,
    organisation_type TEXT CHECK (organisation_type IN ('cyber_partner', 'customer')),
    access_level TEXT,
    sector TEXT,
    region TEXT,
    contribution_score INTEGER DEFAULT 0,
    client_count INTEGER DEFAULT 0,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Organisation Members (user-to-org relationships)
CREATE TABLE organisation_members (
    id SERIAL PRIMARY KEY,
    organisation_id TEXT REFERENCES organisations(organisation_id) ON DELETE CASCADE,
    username TEXT NOT NULL,  -- References Cognito user
    role TEXT CHECK (role IN ('member', 'admin', 'owner')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organisation_id, username)
);

CREATE INDEX idx_members_org ON organisation_members(organisation_id);
CREATE INDEX idx_members_username ON organisation_members(username);
```

**Note**: NO `api_keys` table, NO `refresh_tokens` table, NO `users` table. All authentication data lives in Cognito.

### 3. Sightings API (Threat Intelligence Data)

**Purpose**: High-volume submission and query of threat intelligence sightings.

**Technology Stack**:
- Framework: FastAPI (Python 3.13)
- Database: DynamoDB (AWS)
- Authentication: JWT validation via Cognito JWKS
- Deployment: ECS Fargate (AWS) with auto-scaling

**API Endpoints**:

```python
# Authentication (same as Management API)
POST   /auth/login           # Service account login
POST   /auth/refresh         # Token refresh

# Submission
POST   /submit               # Submit threat sighting
GET    /submissions/{id}     # Get submission details

# Query
GET    /observables          # Query observables (filtered by access tier)
GET    /statistics           # Platform statistics
GET    /search               # Search submissions

# Health & Monitoring
GET    /health               # Basic health check
GET    /health/deep          # DynamoDB connectivity check
```

**Access Filtering** (Built into Repository Layer):
```python
from frank.storage.base import BaseFRANKDatabase

class SightingsAPI:
    def __init__(self, db: BaseFRANKDatabase):
        self.db = db

    async def get_submission(self, submission_id: str, user: TokenPayload):
        # Access tier from JWT token groups
        access_tier = user.access_tier

        # Repository layer filters submission based on access tier
        submission = await self.db.get_submission_by_id(
            submission_id=submission_id,
            access_level=access_tier
        )
        return submission
```

**DynamoDB Schema**:
```
Table: frank-submissions
Partition Key: submission_id (String)
Sort Key: timestamp (Number)

Attributes:
  - submission_id: STIX ID (e.g., "submission--uuid")
  - timestamp: Unix timestamp (milliseconds)
  - submitter_id: Organisation ID
  - submitter_access_level: AccessTier (PUBLIC/OBSERVER/CONTRIBUTOR/PARTNER/CORE_MEMBER)
  - observables: List of Observable objects
  - hit_targets: List of affected organisations
  - confidence_score: Float (0.0-1.0)
  - severity_level: INFORMATIONAL/LOW/MEDIUM/HIGH/CRITICAL
  - tlp_level: WHITE/GREEN/AMBER/RED
  - metadata: JSON

GSI-1: submitter_id (PK) + timestamp (SK) - Query by submitter
GSI-2: observable_value (PK) + timestamp (SK) - Query by observable
```

### 4. Web GUI (User Interface)

**Purpose**: Browser-based interface for threat intelligence management.

**Technology Stack**:
- Frontend: React + TypeScript
- Backend: FastAPI (serves React SPA)
- State Management: React Query
- UI Components: Material-UI or Tailwind CSS

**Features**:
- User authentication (login/logout)
- Organisation dashboard
- Submission viewer with access-filtered data
- User management (admin features)
- Statistics and visualizations

**Authentication Flow**:
1. User enters credentials in login form
2. Frontend calls `POST /auth/login` on Management API
3. Management API proxies to Cognito
4. Frontend receives JWT + refresh token
5. Frontend stores tokens in memory (NOT localStorage)
6. All API calls include `Authorization: Bearer <JWT>` header
7. Frontend auto-refreshes token before expiry

**Security Practices**:
- JWT stored in memory only (cleared on page refresh)
- Refresh token in HttpOnly cookie
- CSRF protection enabled
- Content Security Policy headers
- No sensitive data in client-side storage

### 5. TUI (Terminal User Interface)

**Purpose**: Command-line interface for power users and automation.

**Technology Stack**:
- Framework: Rich (Python) or Textual
- Authentication: Same JWT flow as Web GUI
- Configuration: `~/.frank/credentials` (encrypted)

**Commands**:
```bash
frank login               # Authenticate with Cognito
frank logout              # Revoke tokens

frank orgs list           # List organisations
frank orgs show <id>      # Show organisation details

frank submit <file>       # Submit threat intelligence
frank query <observable>  # Query by observable

frank users list          # List users (admin)
frank users create        # Create user (admin)
```

---

## Authentication & Authorization

### ONE Authentication System: AWS Cognito for Everything

**Key Principle**: FRANK does NOT manage authentication. All authentication operations are delegated to AWS Cognito.

```
┌─────────────────────────────────────────────────────────────────┐
│           What Cognito Handles (AWS manages this)               │
├─────────────────────────────────────────────────────────────────┤
│  ✅ Password storage (hashed, salted)                           │
│  ✅ Password validation                                         │
│  ✅ MFA (TOTP, SMS)                                             │
│  ✅ Account lockout after failed attempts                       │
│  ✅ JWT token issuance                                          │
│  ✅ JWT token signing (RS256)                                   │
│  ✅ Token refresh                                               │
│  ✅ Token revocation (logout)                                   │
│  ✅ User CRUD operations                                        │
│  ✅ Group membership                                            │
│  ✅ JWKS public key rotation                                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│           What FRANK Handles (Application logic)                │
├─────────────────────────────────────────────────────────────────┤
│  ✅ JWT token validation (JWKS endpoint)                        │
│  ✅ Extract access tier from JWT groups                         │
│  ✅ Enforce access tier permissions                             │
│  ✅ Organisation membership (PostgreSQL)                        │
│  ✅ Organisation-level roles (member/admin/owner)               │
│  ✅ Business logic authorization                                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│           What FRANK Does NOT Store                             │
├─────────────────────────────────────────────────────────────────┤
│  ❌ Passwords or password hashes                                │
│  ❌ MFA secrets                                                 │
│  ❌ API keys or API key hashes                                  │
│  ❌ Refresh tokens or refresh token hashes                      │
│  ❌ User credentials of any kind                                │
│  ❌ Authentication state                                        │
│  ❌ Token revocation lists                                      │
└─────────────────────────────────────────────────────────────────┘
```

### JWT Token Structure

**Access Token** (validated by FRANK APIs):
```json
{
  "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "cognito:username": "john.doe@rabobank.nl",
  "cognito:groups": ["FRANK_PARTNER"],
  "email": "john.doe@rabobank.nl",
  "email_verified": true,
  "custom:organisation_id": "identity--rabobank",
  "iss": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_XXXXX",
  "exp": 1706784000,
  "iat": 1706780400,
  "token_use": "access"
}
```

**FRANK Extracts**:
- `cognito:username` → User identity
- `cognito:groups` → AccessTier mapping (FRANK_PARTNER → AccessTier.PARTNER)
- `custom:organisation_id` → Organisation affiliation
- `exp` → Token expiration validation

### Stateless JWT Validation

**No Database Lookups for Token Validation**:

```python
from frank.auth import validate_jwt_token

async def get_current_user(
    authorization: str = Header(...)
) -> TokenPayload:
    """
    Validate JWT token using Cognito JWKS endpoint.

    NO DATABASE ACCESS - Completely stateless.
    """
    # Extract token from "Bearer <token>"
    token = authorization.replace("Bearer ", "")

    # Validate signature using JWKS public key
    # Verify expiration, issuer, audience
    # Extract claims (username, groups, organisation_id)
    payload = await validate_jwt_token(token)

    # Map Cognito groups to AccessTier
    access_tier = map_groups_to_tier(payload.groups)

    return TokenPayload(
        username=payload.username,
        access_tier=access_tier,
        organisation_id=payload.organisation_id
    )
```

**JWKS Validation Process**:
1. Extract JWT from `Authorization: Bearer <token>` header
2. Fetch JWKS public keys from Cognito endpoint (cached)
3. Verify JWT signature using RS256 public key
4. Verify expiration (`exp` claim)
5. Verify issuer (`iss` claim matches Cognito User Pool)
6. Extract claims (username, groups, organisation_id)
7. Return validated token payload

**Performance**:
- JWKS keys cached for 24 hours
- Token validation takes ~1-2ms
- No database queries
- Horizontally scalable

### Access Tier Mapping

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

### Service Accounts (Cognito Users)

**Concept**: Service accounts are regular Cognito users with specific naming convention.

**Naming Convention**: `service-{organisation}-{purpose}`

**Examples**:

```yaml
# Rabobank Automated Ingestion
Username: service-rabobank-ingestion
Password: [generated-secret-32-chars]
Groups: [FRANK_PARTNER]
Custom Attributes:
  organisation_id: identity--rabobank

# KPN SIEM Export
Username: service-kpn-siem-export
Password: [generated-secret-32-chars]
Groups: [FRANK_PARTNER]
Custom Attributes:
  organisation_id: identity--kpn

# Platform Health Monitor
Username: service-monitor-healthcheck
Password: [generated-secret-32-chars]
Groups: [FRANK_OBSERVER]
Custom Attributes:
  organisation_id: identity--frank-platform
```

**Service Account Authentication**:

```python
# Service script authenticates like a human user
import requests

def authenticate_service():
    response = requests.post(
        "https://api.frank-platform.eu/auth/login",
        json={
            "username": "service-rabobank-ingestion",
            "password": os.environ["FRANK_SERVICE_PASSWORD"]
        }
    )

    tokens = response.json()
    return tokens["access_token"], tokens["refresh_token"]

# Use token for API calls
access_token, refresh_token = authenticate_service()

response = requests.post(
    "https://sightings.frank-platform.eu/submit",
    headers={"Authorization": f"Bearer {access_token}"},
    json=submission_data
)
```

**Service Account Management**:

```bash
# Create service account (Admin operation)
frank users create \
  --username service-rabobank-ingestion \
  --password [auto-generated] \
  --groups FRANK_PARTNER \
  --organisation identity--rabobank

# List service accounts
frank users list --filter "service-*"

# Rotate service account password
frank users reset-password service-rabobank-ingestion

# Disable service account
frank users disable service-rabobank-ingestion
```

**Security**:
- Service passwords are 32+ character random strings
- Passwords stored in secrets manager (AWS Secrets Manager)
- Regular password rotation (90 days)
- Audit logging of service account usage
- Service accounts cannot use MFA (password-only authentication)

---

## Data Models

### PostgreSQL Schema (Management API)

**organisations table**:
```sql
CREATE TABLE organisations (
    organisation_id TEXT PRIMARY KEY,           -- STIX identity ID
    organisation_type TEXT NOT NULL,            -- 'cyber_partner' or 'customer'
    access_level TEXT,                          -- Default AccessTier for members
    sector TEXT,                                -- Industry sector
    region TEXT,                                -- Geographic region
    contribution_score INTEGER DEFAULT 0,       -- Gamification score
    client_count INTEGER DEFAULT 0,             -- Number of clients served
    metadata_json TEXT,                         -- Additional metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**organisation_members table**:
```sql
CREATE TABLE organisation_members (
    id SERIAL PRIMARY KEY,
    organisation_id TEXT NOT NULL REFERENCES organisations(organisation_id) ON DELETE CASCADE,
    username TEXT NOT NULL,                      -- Cognito username
    role TEXT NOT NULL CHECK (role IN ('member', 'admin', 'owner')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organisation_id, username)
);

CREATE INDEX idx_members_org ON organisation_members(organisation_id);
CREATE INDEX idx_members_username ON organisation_members(username);
```

**Member Roles**:
- `member`: Read-only access to organisation data
- `admin`: Can add/remove members, edit organisation details
- `owner`: Full control, can delete organisation

### DynamoDB Schema (Sightings API)

**Table: frank-submissions**

```yaml
Partition Key: submission_id (String)
Sort Key: timestamp (Number)

Attributes:
  submission_id: String              # STIX ID: "submission--uuid"
  timestamp: Number                  # Unix timestamp (ms)
  submitter_id: String               # Organisation ID
  submitter_access_level: String     # OBSERVER/CONTRIBUTOR/PARTNER/CORE_MEMBER
  confidence_score: Number           # 0.0 - 1.0
  severity_level: String             # INFORMATIONAL/LOW/MEDIUM/HIGH/CRITICAL
  tlp_level: String                  # WHITE/GREEN/AMBER/RED
  observables: List                  # List of Observable objects
  hit_targets: List                  # List of affected organisations
  threat_context: Map                # Campaign, threat actor, TTPs
  metadata: Map                      # Additional fields

Global Secondary Indexes:
  GSI-1: submitter_id (PK) + timestamp (SK)      # Query by submitter
  GSI-2: observable_value (PK) + timestamp (SK)  # Query by observable
  GSI-3: sector (PK) + timestamp (SK)            # Query by sector

TTL Attribute: expires_at (Number)   # Auto-delete old submissions
```

### Pydantic Models (Shared Library)

**Observable** (src/frank/core/models.py):
```python
from pydantic import BaseModel, Field
from frank.core.enum import ObservableType

class Observable(BaseModel):
    id: Optional[str] = None                # Auto-generated STIX ID
    observable_type: ObservableType         # IPV4, DOMAIN, URL, HASH, etc.
    value: str                              # Observable value
    role: Optional[str] = None              # C2, exfiltration, etc.
    port: Optional[int] = None
    protocol: Optional[str] = None
    first_seen: Optional[datetime] = None
    connection_count: Optional[int] = None

    @classmethod
    def create_ipv4(cls, value: str, role: str = None, port: int = None):
        return cls(observable_type=ObservableType.IPV4, value=value, role=role, port=port)
```

**Submission** (src/frank/core/models.py):
```python
class Submission(BaseModel):
    submission_id: Optional[str] = None     # Auto-generated
    timestamp: datetime
    submitter: Submitter                    # Organisation details
    sighting: Sighting                      # Observation details

    @classmethod
    def create_minimal(cls, organisation_id: str, observables: List[Observable]):
        """Factory method for basic submission"""
        return cls(
            timestamp=datetime.now(timezone.utc),
            submitter=Submitter(
                organisation_id=organisation_id,
                access_level=AccessTier.CONTRIBUTOR
            ),
            sighting=Sighting(
                observables=Observables(network=[o for o in observables if o.observable_type in [ObservableType.IPV4, ObservableType.DOMAIN]]),
                confidence_score=0.5
            )
        )
```

---

## Authentication Flows

### 1. Human User Login (Web GUI)

```
┌──────────┐           ┌─────────────┐           ┌──────────┐
│ Web GUI  │           │  Mgmt API   │           │ Cognito  │
└────┬─────┘           └──────┬──────┘           └────┬─────┘
     │                        │                       │
     │ 1. Enter credentials   │                       │
     │                        │                       │
     │ 2. POST /auth/login    │                       │
     ├───────────────────────▶│                       │
     │    {username, password}│                       │
     │                        │                       │
     │                        │ 3. InitiateAuth       │
     │                        ├──────────────────────▶│
     │                        │    {username, pw}     │
     │                        │                       │
     │                        │                       │ 4. Validate
     │                        │                       │    credentials
     │                        │                       │
     │                        │ 5. Return tokens      │
     │                        │◀──────────────────────┤
     │                        │    {access, refresh}  │
     │                        │                       │
     │ 6. Return tokens       │                       │
     │◀───────────────────────┤                       │
     │    {access, refresh}   │                       │
     │                        │                       │
     │ 7. Store in memory     │                       │
     │    (NOT localStorage)  │                       │
     │                        │                       │
```

**Code Example**:
```python
# Management API: POST /auth/login
from frank.auth.cognito import CognitoClient

@app.post("/auth/login")
async def login(credentials: LoginRequest):
    cognito = CognitoClient()

    # Proxy to Cognito - no local validation
    tokens = await cognito.initiate_auth(
        username=credentials.username,
        password=credentials.password
    )

    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_in": tokens.expires_in
    }
```

**Frontend Code**:
```typescript
// React: Login component
async function handleLogin(username: string, password: string) {
  const response = await fetch('https://api.frank-platform.eu/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });

  const tokens = await response.json();

  // Store in memory (React state)
  setAccessToken(tokens.access_token);
  setRefreshToken(tokens.refresh_token);

  // DO NOT store in localStorage (security risk)
}
```

### 2. Service Account Authentication

```
┌──────────┐           ┌─────────────┐           ┌──────────┐
│ Service  │           │ Sightings   │           │ Cognito  │
│ (script) │           │    API      │           │          │
└────┬─────┘           └──────┬──────┘           └────┬─────┘
     │                        │                       │
     │ 1. Load credentials    │                       │
     │    from env/secrets    │                       │
     │                        │                       │
     │ 2. POST /auth/login    │                       │
     ├───────────────────────▶│                       │
     │    {service-user, pw}  │                       │
     │                        │                       │
     │                        │ 3. InitiateAuth       │
     │                        ├──────────────────────▶│
     │                        │                       │
     │                        │ 4. Return JWT         │
     │                        │◀──────────────────────┤
     │                        │                       │
     │ 5. Return JWT          │                       │
     │◀───────────────────────┤                       │
     │                        │                       │
     │ 6. Cache token         │                       │
     │    (until expiry)      │                       │
     │                        │                       │
     │ 7. POST /submit        │                       │
     ├───────────────────────▶│                       │
     │    Authorization:      │ 8. Validate JWT       │
     │    Bearer <JWT>        ├──────────────────────▶│
     │                        │    (JWKS)             │
     │                        │                       │
     │                        │ 9. Valid              │
     │                        │◀──────────────────────┤
     │                        │                       │
     │                        │ 10. Process submission│
     │                        │     (DynamoDB write)  │
     │                        │                       │
     │ 11. 201 Created        │                       │
     │◀───────────────────────┤                       │
     │                        │                       │
```

**Service Script Example**:
```python
#!/usr/bin/env python3
"""Rabobank Threat Feed Ingestion Service"""

import os
import requests
from datetime import datetime, timedelta

class FRANKClient:
    def __init__(self):
        self.base_url = "https://sightings.frank-platform.eu"
        self.username = "service-rabobank-ingestion"
        self.password = os.environ["FRANK_SERVICE_PASSWORD"]
        self.access_token = None
        self.token_expiry = None

    def authenticate(self):
        """Authenticate with Cognito via FRANK API"""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={
                "username": self.username,
                "password": self.password
            }
        )
        response.raise_for_status()

        tokens = response.json()
        self.access_token = tokens["access_token"]
        self.token_expiry = datetime.now() + timedelta(seconds=tokens["expires_in"])

    def ensure_authenticated(self):
        """Ensure token is valid, refresh if needed"""
        if not self.access_token or datetime.now() >= self.token_expiry:
            self.authenticate()

    def submit_sighting(self, observables: list):
        """Submit threat intelligence sighting"""
        self.ensure_authenticated()

        response = requests.post(
            f"{self.base_url}/submit",
            headers={"Authorization": f"Bearer {self.access_token}"},
            json={
                "timestamp": datetime.now().isoformat(),
                "observables": observables,
                "confidence_score": 0.8
            }
        )
        response.raise_for_status()
        return response.json()

# Usage
client = FRANKClient()
client.submit_sighting([
    {"type": "ipv4", "value": "192.0.2.1", "role": "C2"},
    {"type": "domain", "value": "malicious.example.com"}
])
```

### 3. API Request with JWT Validation

```
┌──────────┐           ┌─────────────┐           ┌──────────┐
│  Client  │           │     API     │           │ Cognito  │
│          │           │             │           │  JWKS    │
└────┬─────┘           └──────┬──────┘           └────┬─────┘
     │                        │                       │
     │ 1. GET /organisations  │                       │
     ├───────────────────────▶│                       │
     │    Authorization:      │                       │
     │    Bearer <JWT>        │                       │
     │                        │                       │
     │                        │ 2. Extract JWT        │
     │                        │                       │
     │                        │ 3. Fetch JWKS keys    │
     │                        ├──────────────────────▶│
     │                        │    (cached 24h)       │
     │                        │                       │
     │                        │ 4. Public keys        │
     │                        │◀──────────────────────┤
     │                        │                       │
     │                        │ 5. Verify signature   │
     │                        │    Verify expiration  │
     │                        │    Extract claims     │
     │                        │                       │
     │                        │ 6. Map groups to      │
     │                        │    AccessTier         │
     │                        │                       │
     │                        │ 7. Query PostgreSQL   │
     │                        │    (if authorized)    │
     │                        │                       │
     │ 8. 200 OK              │                       │
     │◀───────────────────────┤                       │
     │    [organisations]     │                       │
     │                        │                       │
```

**Code Example**:
```python
# src/frank/auth/dependencies.py

from fastapi import Depends, Header, HTTPException
from frank.auth.jwt import validate_jwt_token
from frank.auth.config import map_groups_to_tier

async def get_current_user(
    authorization: str = Header(...)
) -> TokenPayload:
    """
    Stateless JWT validation using Cognito JWKS.

    NO database queries - completely stateless.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.replace("Bearer ", "")

    try:
        # Validate JWT signature using JWKS public key
        payload = await validate_jwt_token(token)

        # Map Cognito groups to FRANK AccessTier
        access_tier = map_groups_to_tier(payload.groups)

        return TokenPayload(
            sub=payload.sub,
            username=payload.username,
            email=payload.email,
            groups=payload.groups,
            access_tier=access_tier,
            organisation_id=payload.custom_organisation_id
        )

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# Use in endpoint
@app.get("/organisations")
async def list_organisations(
    user: TokenPayload = Depends(get_current_user),
    db: BaseFRANKDatabase = Depends(get_database)
):
    # user.access_tier is already validated
    # user.organisation_id links to PostgreSQL

    orgs = db.list_organisations_for_user(user.username)
    return orgs
```

### 4. Token Refresh (Stateless Proxy to Cognito)

```
┌──────────┐           ┌─────────────┐           ┌──────────┐
│  Client  │           │     API     │           │ Cognito  │
└────┬─────┘           └──────┬──────┘           └────┬─────┘
     │                        │                       │
     │ 1. POST /auth/refresh  │                       │
     ├───────────────────────▶│                       │
     │    {refresh_token}     │                       │
     │                        │                       │
     │                        │ 2. RefreshToken       │
     │                        ├──────────────────────▶│
     │                        │    {refresh_token}    │
     │                        │                       │
     │                        │                       │ 3. Validate
     │                        │                       │    refresh token
     │                        │                       │
     │                        │ 4. New access token   │
     │                        │◀──────────────────────┤
     │                        │                       │
     │ 5. New access token    │                       │
     │◀───────────────────────┤                       │
     │                        │                       │
```

**Key Point**: FRANK does NOT store refresh tokens. Token refresh is a stateless proxy to Cognito.

**Code Example**:
```python
# POST /auth/refresh
@app.post("/auth/refresh")
async def refresh_token(request: RefreshRequest):
    cognito = CognitoClient()

    # Stateless proxy to Cognito
    # NO database queries, NO token storage
    new_tokens = await cognito.refresh_token(
        refresh_token=request.refresh_token
    )

    return {
        "access_token": new_tokens.access_token,
        "expires_in": new_tokens.expires_in
    }
```

### 5. Logout (Stateless Proxy to Cognito)

```
┌──────────┐           ┌─────────────┐           ┌──────────┐
│  Client  │           │     API     │           │ Cognito  │
└────┬─────┘           └──────┬──────┘           └────┬─────┘
     │                        │                       │
     │ 1. POST /auth/logout   │                       │
     ├───────────────────────▶│                       │
     │    {access_token}      │                       │
     │                        │                       │
     │                        │ 2. GlobalSignOut      │
     │                        ├──────────────────────▶│
     │                        │    {access_token}     │
     │                        │                       │
     │                        │                       │ 3. Revoke all
     │                        │                       │    user tokens
     │                        │                       │
     │                        │ 4. Success            │
     │                        │◀──────────────────────┤
     │                        │                       │
     │ 5. 200 OK              │                       │
     │◀───────────────────────┤                       │
     │                        │                       │
     │ 6. Clear tokens        │                       │
     │    from memory         │                       │
     │                        │                       │
```

**Key Point**: FRANK does NOT maintain a token revocation list. Logout proxies to Cognito's GlobalSignOut.

**Code Example**:
```python
# POST /auth/logout
@app.post("/auth/logout")
async def logout(
    user: TokenPayload = Depends(get_current_user)
):
    cognito = CognitoClient()

    # Stateless proxy to Cognito
    # Cognito revokes ALL tokens for this user
    await cognito.global_sign_out(access_token=user.raw_token)

    return {"message": "Logged out successfully"}
```

---

## Security Considerations

### 1. No Credential Storage

**Threat Mitigated**: Database breach does not expose user credentials.

**Implementation**:
- PostgreSQL has NO `users` table
- PostgreSQL has NO `api_keys` table with password hashes
- PostgreSQL has NO `refresh_tokens` table
- All credentials exist ONLY in AWS Cognito (AWS-managed security)

**Benefit**: Even if PostgreSQL is compromised, attackers cannot authenticate as users.

### 2. Stateless JWT Validation

**Threat Mitigated**: Reduces attack surface, eliminates session storage vulnerabilities.

**Implementation**:
- JWT validation uses public key cryptography (RS256)
- Public keys fetched from Cognito JWKS endpoint
- Keys cached for 24 hours
- No database queries for token validation
- No session storage

**Benefit**: Horizontally scalable, no shared session state, resistant to session hijacking.

### 3. Service Accounts (Not Custom API Keys)

**Threat Mitigated**: Eliminates custom key management complexity and vulnerabilities.

**Implementation**:
- Service accounts are Cognito users (same security as human users)
- Same JWT token flow as human authentication
- Cognito password policy enforced (32+ char random strings)
- Regular password rotation through Cognito
- Audit logs in Cognito CloudTrail

**Benefit**: Unified authentication system, no custom key management code, AWS security best practices.

### 4. Token Expiry and Refresh

**Threat Mitigated**: Limits impact of stolen tokens.

**Configuration**:
- Access token: 1 hour expiry
- Refresh token: 30 days expiry
- Automatic refresh before expiry in client SDKs

**Implementation**:
```python
class TokenManager:
    def ensure_valid_token(self):
        if datetime.now() >= self.token_expiry - timedelta(minutes=5):
            # Refresh 5 minutes before expiry
            self.refresh_token()
```

### 5. Access Tier Enforcement

**Threat Mitigated**: Prevents unauthorized data access.

**Implementation**: Access filtering built into repository layer (see ADR-0003).

```python
# Repository layer enforces access filtering
def get_submission_by_id(self, submission_id: str, access_level: AccessTier):
    submission = self._fetch_from_database(submission_id)

    # Filter based on access tier
    return self._filter_submission_by_access_level(submission, access_level)
```

**Access Tier Restrictions**:
- PUBLIC: Statistics only
- OBSERVER: Masked observables (first 10 chars + "...")
- CONTRIBUTOR: Full observables, anonymized targets
- PARTNER: Full submission data
- CORE_MEMBER: Full access + audit logs

### 6. HTTPS/TLS Everywhere

**Threat Mitigated**: Man-in-the-middle attacks, token interception.

**Implementation**:
- All APIs served over HTTPS (TLS 1.3)
- AWS Certificate Manager for SSL certificates
- HSTS headers enforced
- No HTTP fallback

### 7. Mock Cognito Security (Local Development)

**Threat**: Mock Cognito uses HS256 (shared secret) instead of RS256 (public key).

**Mitigation**:
- Mock Cognito ONLY used in local development
- Environment variable: `FRANK_AUTH_MODE=local` (explicit)
- Production MUST use `FRANK_AUTH_MODE=aws`
- CI/CD pipelines verify auth mode configuration
- Mock Cognito not deployed to cloud environments

**Why HS256 for Mock**:
- Simpler implementation for development
- No need to manage RSA key pairs locally
- Behavior is identical from API perspective
- Production always uses RS256

### 8. Organisation Membership Validation

**Threat**: User claims to belong to organisation they don't have access to.

**Mitigation**:
```python
@app.get("/organisations/{org_id}")
async def get_organisation(
    org_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: BaseFRANKDatabase = Depends(get_database)
):
    # Verify user is member of organisation
    membership = db.get_organisation_member(org_id, user.username)

    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organisation")

    return db.get_organisation(org_id)
```

### 9. Audit Logging

**Implementation**:
- All authentication events logged to CloudWatch
- All API requests logged with user context
- DynamoDB writes include submitter_id for audit trail

**Logged Events**:
- Login attempts (success/failure)
- Token refresh
- Logout
- User creation/deletion
- Organisation membership changes
- Submission creation
- Access denied events

### 10. Rate Limiting

**Implementation**:
- AWS WAF rate limiting rules
- API Gateway throttling
- Per-user rate limits based on access tier

**Limits**:
- OBSERVER: 100 requests/minute
- CONTRIBUTOR: 500 requests/minute
- PARTNER: 2000 requests/minute
- CORE_MEMBER: 5000 requests/minute

---

## Related ADR References

### ADR-0003: Tiered Access Control Model

**Relevance**: Defines the five-tier access model (PUBLIC → OBSERVER → CONTRIBUTOR → PARTNER → CORE_MEMBER) that Cognito groups map to.

**Key Points**:
- Progressive disclosure based on participation level
- Access filtering built into repository layer
- Consistent across all database implementations

**Integration**: Cognito groups (`FRANK_OBSERVER`, etc.) map directly to AccessTier enum.

### ADR-0005: AWS Cognito Authentication Strategy

**Relevance**: Comprehensive authentication strategy using AWS Cognito as single source of truth.

**Key Decisions**:
- Users exist ONLY in Cognito (no local users table)
- Dual-mode authentication (Mock Cognito for local, AWS Cognito for cloud)
- JWT token validation using JWKS endpoint
- Service accounts treated as regular Cognito users

**Validation**: Spike 014 validated Cognito integration patterns.

### ADR-0009: PostgreSQL for Management API Data Storage

**Relevance**: Defines PostgreSQL schema for Management API - explicitly excludes authentication tables.

**Key Schema**:
- `organisations` - Member organisations (identity--{uuid4})
- `organisation_members` - User-to-org relationships (includes service accounts)
- `refresh_tokens` (optional) - Logout revocation tracking
- NO `users` table (Cognito only)
- NO `api_keys` table (never intended per ADR-0005)

**Rationale**: PostgreSQL stores only business data (member orgs, memberships). Authentication data stored in Cognito.

---

## Deployment Architecture

### Local Development

```yaml
# docker-compose.local.yml

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: frank_management
      POSTGRES_USER: frank
      POSTGRES_PASSWORD: frank_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data

  mock-cognito:
    build: ./tests/spikes/014_cognito
    ports:
      - "8100:8100"
    environment:
      JWT_SECRET: local-dev-secret
      JWT_ALGORITHM: HS256

  management-api:
    build: .
    ports:
      - "8001:8001"
    environment:
      FRANK_AUTH_MODE: local
      FRANK_MOCK_COGNITO_URL: http://mock-cognito:8100
      DATABASE_URL: postgresql://frank:frank_dev@postgres:5432/frank_management
    depends_on:
      - postgres
      - mock-cognito

  sightings-api:
    build: .
    ports:
      - "8002:8002"
    environment:
      FRANK_AUTH_MODE: local
      FRANK_MOCK_COGNITO_URL: http://mock-cognito:8100
      DYNAMODB_ENDPOINT: http://localhost:8000  # LocalStack
    depends_on:
      - mock-cognito

volumes:
  postgres-data:
```

**Start Command**:
```bash
docker compose -f docker-compose.local.yml up
```

### AWS Production Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud (Production)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Route 53 DNS                                            │    │
│  │  • api.frank-platform.eu → ALB (Management)             │    │
│  │  • sightings.frank-platform.eu → ALB (Sightings)        │    │
│  └────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Application Load Balancer (ALB)                         │    │
│  │  • SSL Termination (AWS Certificate Manager)            │    │
│  │  • Health Checks (/health endpoint)                     │    │
│  │  • Target Groups (Management API, Sightings API)        │    │
│  └────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ ECS Fargate Cluster                                     │    │
│  │                                                         │    │
│  │  ┌──────────────────┐       ┌──────────────────┐      │    │
│  │  │ Management API   │       │ Sightings API    │      │    │
│  │  │ Service          │       │ Service          │      │    │
│  │  │                  │       │                  │      │    │
│  │  │ • Auto Scaling   │       │ • Auto Scaling   │      │    │
│  │  │   (2-10 tasks)   │       │   (2-20 tasks)   │      │    │
│  │  │ • Health Checks  │       │ • Health Checks  │      │    │
│  │  └──────────────────┘       └──────────────────┘      │    │
│  │          │                           │                 │    │
│  └──────────┼───────────────────────────┼─────────────────┘    │
│             │                           │                      │
│             ▼                           ▼                      │
│  ┌──────────────────┐       ┌──────────────────┐              │
│  │ RDS PostgreSQL   │       │ DynamoDB         │              │
│  │                  │       │                  │              │
│  │ • Multi-AZ       │       │ • On-Demand      │              │
│  │ • Encrypted      │       │ • Auto-Scaling   │              │
│  │ • Auto Backup    │       │ • TTL Enabled    │              │
│  └──────────────────┘       └──────────────────┘              │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ AWS Cognito User Pool                                   │    │
│  │  • JWT Token Issuance                                   │    │
│  │  • JWKS Endpoint                                        │    │
│  │  • MFA Enforcement                                      │    │
│  │  • CloudTrail Logging                                   │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ AWS Secrets Manager                                     │    │
│  │  • Database Passwords                                   │    │
│  │  • Service Account Credentials                          │    │
│  │  • JWT Secrets                                          │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ CloudWatch                                              │    │
│  │  • API Logs                                             │    │
│  │  • Metrics (Request Rate, Errors, Latency)             │    │
│  │  • Alarms (High Error Rate, Health Check Failures)     │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Environment Variables (ECS Task Definition)**:
```json
{
  "containerDefinitions": [
    {
      "name": "management-api",
      "image": "xxxx.dkr.ecr.eu-west-1.amazonaws.com/frank-management-api:latest",
      "environment": [
        {"name": "FRANK_AUTH_MODE", "value": "aws"},
        {"name": "FRANK_COGNITO_REGION", "value": "eu-central-1"},
        {"name": "FRANK_COGNITO_USER_POOL_ID", "value": "eu-central-1_XXXXX"},
        {"name": "FRANK_COGNITO_CLIENT_ID", "value": "xxxxxxxxxxxxxxxxx"}
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:eu-west-1:xxxx:secret:frank-db-url"
        }
      ]
    }
  ]
}
```

---

## Conclusion

The FRANK high-level design demonstrates how using **one authentication system (AWS Cognito) for everything** dramatically simplifies the architecture:

**Eliminated Complexity**:
- ❌ No custom API key management
- ❌ No token storage tables
- ❌ No refresh token revocation lists
- ❌ No credential hashing/validation logic
- ❌ No key rotation management
- ❌ No dual authentication systems

**Achieved Simplicity**:
- ✅ ONE authentication provider (Cognito)
- ✅ Stateless JWT validation (JWKS)
- ✅ Service accounts = Cognito users
- ✅ Minimal database schema (business data only)
- ✅ No credential storage risk
- ✅ AWS-managed security

**Key Benefits**:
1. **Security**: No credential storage, AWS-managed authentication
2. **Simplicity**: One system for humans and services
3. **Scalability**: Stateless validation, horizontally scalable
4. **Maintainability**: Less code, fewer components
5. **Testability**: Mock Cognito 100% compatible with AWS Cognito

This design enables FRANK to focus on threat intelligence business logic while delegating authentication complexity to a proven, managed service.

---

**Document Change History**:
- 2026-01-31: Version 2.0 - Complete rewrite with dual-API architecture and unified Cognito authentication
- 2026-01-31: Version 1.0 - Initial version
