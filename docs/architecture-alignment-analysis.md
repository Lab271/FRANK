# FRANK Architecture Alignment Analysis

**Date:** 2026-01-31
**Purpose:** Evaluate consistency between Issue #54, ADRs, Glossary, and High-Level Design

---

## Summary: Architecture Is Now Aligned ✅

The architecture is **CORRECT** after removing the API keys system. We're back to the original intended design from ADR-0005.

### ✅ What's Correct Now

| Component | Status | Notes |
|-----------|--------|-------|
| **Authentication** | ✅ Aligned | Cognito JWT tokens only (ADR-0005) |
| **Service Accounts** | ✅ Aligned | Cognito users with `service-*` naming |
| **Database Schema** | ✅ Aligned | PostgreSQL: organisations + members only |
| **Token Validation** | ✅ Aligned | Stateless JWKS validation |
| **Access Tiers** | ✅ Aligned | 5-tier model (ADR-0003) |
| **Member vs Target Orgs** | ✅ Aligned | Separate concepts (glossary) |

---

## Historical Context: The API Keys Detour

### Timeline

1. **Original Design (ADR-0005 - Date Unknown)**
   - Decision: **Cognito JWT for everything**
   - Explicitly rejected API keys as sole mechanism
   - Quote: "API Keys Only → **Rejected**: Doesn't support human users for admin interface"

2. **Issue #54 Created (Date Unknown)**
   - Added API keys back into token strategy:
     ```
     | API Key | 1 year | Scripts, integrations |
     ```
   - Architecture diagram shows `/api-keys/*` endpoint
   - **CONFLICT**: This contradicts ADR-0005

3. **Implementation Phase**
   - API keys implemented in Management API
   - `api_keys` table created in PostgreSQL
   - API key CRUD endpoints added

4. **Correction (2026-01-31 - Today)**
   - Recognized architectural drift
   - Removed API keys system (PR #74)
   - Back to original ADR-0005 design

### Root Cause

**Issue #54 was written AFTER ADR-0005 but contradicted it.**

The API keys were added for "scripts, integrations" convenience without updating the ADR or recognizing the conflict with the original authentication architecture decision.

---

## Current Architecture (Correct State)

### Authentication: Cognito Only

```
┌─────────────────────────────────────────────────────────┐
│                  AWS Cognito (ONE System)               │
│                                                         │
│  Human Users:                                           │
│    username: "admin"                                    │
│    groups: ["FRANK_CORE_MEMBER"]                        │
│                                                         │
│  Service Accounts:                                      │
│    username: "service-rabobank-ingestion"               │
│    groups: ["FRANK_CONTRIBUTOR"]                        │
│    password: [auto-generated, not used for login]      │
│                                                         │
│  Tokens: JWT (RS256 in AWS, HS256 in Mock)             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
            ┌─────────────────────────────┐
            │  Management API             │
            │  Sightings API              │
            │                             │
            │  Validate JWT via JWKS      │
            │  (stateless)                │
            └─────────────────────────────┘
```

### Database Schema (PostgreSQL)

**Management API Storage:**
```sql
-- Member organisations (authenticated parties)
organisations (
    organisation_id TEXT PRIMARY KEY,  -- identity--rabobank
    organisation_type TEXT,            -- cyber_partner | customer
    access_level TEXT,                 -- observer | contributor | partner | core_member
    ...
)

-- Organisation members (humans + service accounts)
organisation_members (
    organisation_id TEXT,
    username TEXT,  -- From Cognito (includes service-*)
    role TEXT,      -- member | admin | owner
    ...
)

-- Token revocation (optional - Cognito can handle)
refresh_tokens (
    token_id TEXT,
    user_id TEXT,
    token_hash TEXT,
    expires_at TIMESTAMP,
    is_revoked BOOLEAN
)
```

**What's NOT in Database:**
- ❌ No `users` table (Cognito only)
- ❌ No `api_keys` table (removed)
- ❌ No password hashes (Cognito only)

---

## ADR Compliance Check

### ADR-0003: Tiered Access Control ✅

**Status:** COMPLIANT

Access tiers correctly defined and implemented:
- PUBLIC → OBSERVER → CONTRIBUTOR → PARTNER → CORE_MEMBER
- Mapped to Cognito groups: `FRANK_OBSERVER`, `FRANK_CONTRIBUTOR`, etc.
- Filtering logic in `BaseFRANKDatabase`

**Evidence:**
- `src/frank/core/enum.py` - AccessTier enum
- `src/frank/auth/` - Group to tier mapping
- `src/frank/storage/base.py` - Filter methods

### ADR-0005: Cognito Authentication ✅

**Status:** COMPLIANT (after PR #74)

Key requirements met:
- ✅ "Users exist ONLY in AWS Cognito"
- ✅ JWT token validation (JWKS)
- ✅ Mock Cognito for local development
- ✅ No password storage in FRANK
- ✅ Organisation membership in FRANK database

**Evidence:**
- `src/frank/auth/` - Auth module
- `tests/spikes/014_cognito/mock_cognito.py` - Mock implementation
- `docs/highlevel_design.md` - Architecture documentation

### ADR-0009: PostgreSQL for Management API ✅

**Status:** COMPLIANT (after PR #74)

Schema simplified to match intended design:
- ✅ organisations table
- ✅ organisation_members table (includes service accounts)
- ✅ refresh_tokens table (optional)
- ❌ api_keys table REMOVED

**Evidence:**
- `src/frank/storage/postgresql.py` - Schema implementation
- `docs/migrations/001_drop_api_keys_table.md` - Migration guide

---

## Glossary Alignment ✅

**File:** `docs/glossary.md`

### Key Definitions

**Member Organisation:**
- Authenticated party in Cognito
- Can file and read sightings
- Naming: `identity--{name}`
- Stored in PostgreSQL

**Target Organisation:**
- Victim in sightings
- NO Cognito account
- Naming: `target--{name}` or `victim--{identifier}`
- Stored in DynamoDB (within sightings)

**Service Account:**
- Cognito user with `service-*` prefix
- Authenticates with JWT tokens
- Example: `service-rabobank-ingestion`

### Architectural Recommendation

**Question:** Should member and target organisations be separate?

**Answer:** **YES - Keep them separate**

**Rationale:**
1. Identity layer vs data layer separation
2. Targets can be anonymized, members cannot
3. Cleaner access control
4. Better statistics/reporting

**Example:**
```python
# Rabobank testing their own infrastructure
submitter: {
    "organisation_id": "identity--rabobank"  # Member (auth)
}
hit_target: {
    "organisation_id": "target--rabobank"    # Victim (data)
}
```

**Status:** ✅ ALIGNED with architecture

---

## High-Level Design Alignment ✅

**File:** `docs/highlevel_design.md`

### Core Principles (Correct)

1. **Single Authentication Provider**: AWS Cognito ✅
2. **Stateless JWT Validation**: JWKS endpoint ✅
3. **Service Accounts = Cognito Users**: `service-*` naming ✅
4. **Minimal Database Schema**: No auth tables ✅
5. **Cognito for Everything**: Token refresh, logout ✅

### Architecture Diagram (Correct)

```
Users/Services → Cognito → [Management API, Sightings API]
                              ↓               ↓
                         PostgreSQL      DynamoDB
                         (orgs/members)  (intel data)
```

No API keys shown ✅
No custom token management ✅

**Status:** ✅ ALIGNED with ADRs

---

## Issue #54 Discrepancy ⚠️

**File:** GitHub Issue #54

### Conflicting Element

**Token Strategy Table:**
```
| Type          | Lifetime | Use Case              |
|---------------|----------|-----------------------|
| Access Token  | 1 hour   | API calls (interactive)|
| Refresh Token | 30 days  | Get new access token  |
| API Key       | 1 year   | Scripts, integrations | ← CONFLICT
```

**Architecture Diagram:**
```
│  Management API          │
│  • /orgs/*       │
│  • /users/*      │
│  • /auth/*       │
│  • /api-keys/*   │  ← CONFLICT
```

### Issue Status

**Current State:** Issue #54 is **OUTDATED**

The issue describes the original requirements but includes API keys which contradict ADR-0005. The issue should be:

**Recommendation:**
1. ✅ Mark sub-issues #55-59 as completed
2. ⚠️ Update issue #54 description to remove API keys
3. ✅ Close issue #54 as completed (with note about API keys removal)

**Proposed Comment for Issue #54:**
```markdown
## Update: API Keys Removed

During implementation, we identified that API keys contradict ADR-0005
(Cognito Authentication Strategy) which explicitly rejected API keys.

**Architectural Decision:**
- Service accounts authenticate via Cognito JWT tokens
- Naming: `service-{org}-{purpose}` (e.g., service-rabobank-ingestion)
- No custom API key system needed

**Completed:**
- ✅ Management API (#55)
- ✅ Cognito MFA (#56)
- ✅ JWT token refresh (#57) - via Cognito, no API keys
- ✅ TUI admin tool (#58)
- ✅ Web GUI (#59)

See PR #74 for unified Cognito authentication implementation.
```

---

## Remaining Inconsistencies

### None Identified ✅

After reviewing:
- ADR-0003: Access Tiers ✅
- ADR-0005: Cognito Auth ✅
- ADR-0009: PostgreSQL ✅
- Issue #54: Outdated but identified
- Glossary: Aligned ✅
- High-Level Design: Aligned ✅
- Implementation: Aligned ✅

**Architecture is consistent.**

---

## Recommendations

### 1. Update Issue #54 ⚠️

Add comment explaining API keys removal and mark as completed.

### 2. Create ADR-0016: No Custom API Tokens 📝

Document the decision to NOT implement custom API tokens:

```markdown
# ADR-0016: No Custom API Token System

## Status
Accepted

## Context
Issue #54 originally proposed API keys for service authentication.
This contradicts ADR-0005 which established Cognito as sole auth provider.

## Decision
Service accounts authenticate via Cognito JWT tokens, NOT custom API keys.

Service accounts:
- Are Cognito users with `service-*` prefix
- Authenticate with username/password to get JWT
- Use JWT for all API calls
- Have same access tiers as human users

## Rationale
1. Single authentication system (Cognito)
2. No token management complexity
3. Stateless validation via JWKS
4. Consistent with ADR-0005
5. No credential storage in FRANK

## Consequences
- Services must authenticate with Cognito before API calls
- JWT tokens expire (short-lived, must refresh)
- No long-lived API keys (security benefit)
```

### 3. Review Other Issues for Conflicts 🔍

Check if other issues reference API keys or contradict ADRs.

### 4. Lock Down Architecture Documentation 🔒

Make architectural principles explicit:

**Add to `docs/highlevel_design.md`:**
```markdown
## Architecture Principles (Non-Negotiable)

1. **ONE Authentication System**: Cognito only, no alternatives
2. **NO Custom Tokens**: No API keys, no custom JWT generation
3. **NO Credential Storage**: Passwords never stored in FRANK
4. **Stateless Validation**: JWKS endpoint only, no local state
5. **Service = User**: Service accounts are Cognito users
```

---

## Conclusion

### Current Status: ✅ ALIGNED

The architecture is **correct and consistent** after PR #74:
- ADR-0005 compliant (Cognito only)
- No custom API tokens
- Service accounts via Cognito
- Stateless JWT validation
- Clean PostgreSQL schema

### Historical Issue: Circular Work ⚠️

The API keys feature was:
1. Rejected in ADR-0005
2. Added back in Issue #54 (architectural drift)
3. Implemented (wasted effort)
4. Removed in PR #74 (circular work)

**Lesson:** ADRs should be updated if requirements change. Issue #54 should have triggered an ADR amendment or created a new ADR explicitly overriding ADR-0005.

### Prevention: Architecture Governance ✅

To prevent future drift:
1. ✅ Glossary established
2. ✅ High-level design documented
3. 📝 Propose ADR-0016 (no custom tokens)
4. 🔍 Review process for issues conflicting with ADRs
5. 🔒 Lock down core architectural principles

---

**Last Updated:** 2026-01-31
**Status:** Architecture aligned and documented
