# PostgreSQL Implementation Specification

**Domain:** Storage Layer / Relational Database
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06

**Owner:** FRANK Platform Team
**Related ADRs:** [ADR-0002](.openspec/architecture/decisions/004-repository-pattern-database-abstraction.md), [ADR-0003](.openspec/architecture/decisions/002-tiered-access-control.md), [ADR-0005](.openspec/architecture/decisions/006-cognito-authentication.md), [ADR-0009](.openspec/architecture/decisions/010-postgresql-management-api.md)
**Implementation:** [`src/frank/storage/postgresql.py`](src/frank/storage/postgresql.py)
**Tests:** [tests/unit/storage/test_dynamodb.py](tests/unit/storage/test_dynamodb.py)

## Overview

The `PostgreSQLFRANKDatabase` implements the `BaseFRANKDatabase` interface for **Management API data** in cloud deployments (Stage 3+). It handles the relational, low-volume, high-consistency workload of organisation management, member relationships, and refresh token tracking.

PostgreSQL was chosen for management data because:

- **Relational Integrity**: Organisation-to-member relationships require foreign keys and cascading deletes
- **Transactional Consistency**: ACID transactions for atomic membership changes
- **Structured Schema**: CHECK constraints enforce data validity at the database level
- **Query Power**: JOINs for user-to-organisation lookups, aggregation for statistics
- **UPSERT Support**: `ON CONFLICT ... DO UPDATE` for idempotent organisation management

**This is a purpose-built implementation.** It handles only management data (organisations, members, refresh tokens). Threat intelligence data (submissions, observables, sightings) is handled by DynamoDB (see [dynamodb.spec.md](../022-storage-dynamodb/spec.md)). This reflects the FRANK database selection strategy: use the right database for each data domain.

### Database Scope

**In Scope (PostgreSQL)**:
- Member organisations -- authenticated parties that use the platform
- Organisation members -- user-to-organisation relationships (humans + service accounts)
- Refresh tokens -- JWT revocation tracking for logout functionality

**Out of Scope (PostgreSQL)**:
- Users -- stored in Cognito only (ADR-0005)
- Passwords -- never stored in FRANK
- API keys -- not needed; Cognito handles authentication (ADR-0005)
- Target organisations -- victim orgs stored in DynamoDB with sightings
- Threat intelligence -- submissions, observables, sightings in DynamoDB

### Philosophy

- **Relational Data Only**: Focus on data requiring foreign keys, joins, and ACID transactions
- **Strong Consistency**: Use PostgreSQL's ACID guarantees for critical management operations
- **Schema Enforcement**: Database-level constraints ensure data integrity
- **Purpose-Built**: Only handles management data, not threat intelligence workloads
- **Complementary Design**: Works alongside DynamoDB, each handling appropriate workloads

### Key Capabilities

- **Organisation Management**: Full CRUD operations with UPSERT support
- **Member Relationships**: User-to-organisation mappings with role-based access
- **Refresh Token Tracking**: JWT revocation for logout functionality
- **Foreign Key Constraints**: Cascading deletes maintain referential integrity
- **Transactional Updates**: Atomic multi-table operations
- **Query Flexibility**: Complex JOINs for member lookups and aggregations
- **Not Implemented**: Threat intelligence operations (use DynamoDB instead)

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Usage in this specification**:
- **MUST/SHALL**: Strict requirements for correctness and compliance
- **SHOULD**: Recommended practices that may have valid exceptions
- **MAY**: Optional features or behaviors

---
## Requirements

### Requirement 1: Organisation Management (Implemented)

- **Description**: The system MUST provide full CRUD operations for member organisations with filtering and metadata support.
- **Acceptance Criteria**:
  - [ ] `create_organisation()` creates organisation and returns ID (delegates to `upsert_organisation`)
  - [ ] `upsert_organisation()` inserts new or updates existing organisation using `ON CONFLICT`
  - [ ] `get_organisation()` retrieves organisation by ID with parsed metadata
  - [ ] `list_organisations()` lists with optional filters (type, access_level, sector, limit)
  - [ ] `update_organisation()` updates specific fields dynamically
  - [ ] `delete_organisation()` deletes organisation with cascading member deletion
- **Stage Availability**: Stage 3+
- **Related ADR**: [ADR-0009](.openspec/architecture/decisions/010-postgresql-management-api.md)

#### Scenario: Create and Update Organisation
- GIVEN organisation data with STIX ID, type, and access level
- WHEN calling create_organisation() or upsert_organisation()
- THEN the organisation SHALL be inserted or updated using ON CONFLICT
- AND metadata SHALL be stored as JSON
- AND the organisation_id SHALL be returned

### Requirement 2: Organisation Member Management (Implemented)

- **Description**: The system MUST manage user-to-organisation relationships including service accounts.
- **Acceptance Criteria**:
  - [ ] `add_organisation_member()` adds user with role, upserts on conflict (updates role)
  - [ ] `remove_organisation_member()` removes user from organisation
  - [ ] `get_organisation_members()` lists members with optional role filter
  - [ ] `get_user_organisations()` returns all orgs a user belongs to (with JOIN)
  - [ ] `get_organisation_member()` returns specific membership record
  - [ ] Service accounts (username prefix `service-*`) treated as regular members
- **Stage Availability**: Stage 3+
- **Related ADR**: [ADR-0005](.openspec/architecture/decisions/006-cognito-authentication.md)

#### Scenario: Add Member with Role Upsert
- GIVEN an organisation and a user with role "admin"
- WHEN calling add_organisation_member()
- THEN the member SHALL be inserted using ON CONFLICT upsert
- AND if the member already exists, their role SHALL be updated
- AND the membership record SHALL be returned using RETURNING clause

### Requirement 3: Refresh Token Management (Implemented)

- **Description**: The system MUST store and manage refresh token hashes for JWT revocation tracking.
- **Acceptance Criteria**:
  - [ ] `store_refresh_token()` stores token hash with expiry
  - [ ] `get_refresh_token()` retrieves token if not revoked
  - [ ] `revoke_refresh_token()` marks single token as revoked
  - [ ] `revoke_all_user_refresh_tokens()` revokes all tokens for a user (logout/password change)
- **Stage Availability**: Stage 3+ (optional; Cognito can handle logout tracking)

#### Scenario: Revoke All User Tokens on Logout
- GIVEN a user with multiple active refresh tokens
- WHEN calling revoke_all_user_refresh_tokens()
- THEN all tokens for the user SHALL be marked as revoked (is_revoked = TRUE)
- AND subsequent token refresh attempts SHALL return 401 Unauthorized
- AND the count of revoked tokens SHALL be returned

### Requirement 4: Threat Intelligence (Not Implemented)

- **Description**: The system SHALL NOT implement threat intelligence operations in PostgreSQL. These methods SHALL raise `NotImplementedError`. DynamoDB handles these in Stage 3.
- **Methods**: `store_submission`, `get_submission_by_id`, `query_observables`, `search_observables_by_value`, `get_statistics_summary`
- **Error Message**: "Submissions/Observables/Statistics are stored in DynamoDB, not PostgreSQL"
- **Stage Availability**: Not available (use DynamoDB)

#### Scenario: Attempt Threat Intelligence Operations
- GIVEN a PostgreSQL database instance
- WHEN calling store_submission() or any threat intelligence method
- THEN a NotImplementedError SHALL be raised
- AND the error message SHALL guide users to use DynamoDB
- AND no threat intelligence data SHALL be written to PostgreSQL

### Requirement 5: Health Check (Implemented)

- **Description**: The system MUST verify PostgreSQL connectivity via health check.
- **Acceptance Criteria**:
  - [ ] `health_check()` returns `{"status": "healthy", "database": "postgresql"}` on success
  - [ ] Returns `{"status": "unhealthy", "error": "..."}` on failure
- **Stage Availability**: Stage 3+

#### Scenario: Check Database Health
- GIVEN a running PostgreSQL database connection
- WHEN calling health_check()
- THEN the system SHALL execute SELECT 1 to verify connectivity
- AND return {"status": "healthy", "database": "postgresql"} on success
- AND return {"status": "unhealthy", "error": "..."} on connection failure

### Requirement 6: Access Logging (Minimal Implementation)

- **Description**: The system SHALL implement `log_access()` as a passthrough that logs to the application logger.
- **Acceptance Criteria**:
  - [ ] Logs access event at DEBUG level via application logger
  - [ ] Returns `True` (no database write)
  - [ ] Does not store audit records in PostgreSQL (audit handled by DynamoDB audit table)
- **Stage Availability**: Stage 3+

#### Scenario: Log Access Event
- GIVEN an access event with organisation_id and action
- WHEN calling log_access()
- THEN the event SHALL be logged to application logger at DEBUG level
- AND no database write SHALL occur (returns True immediately)
- AND audit records SHALL be stored in DynamoDB audit table, not PostgreSQL

---

## Non-Functional Requirements

### Performance

- **Query Latency**: Organisation lookups < 10ms (indexed primary key)
- **Member Queries**: JOIN queries < 20ms for typical organisation sizes (< 100 members)
- **Connection Management**: New connection per operation (connection pooling recommended for production)

### Scalability

- **Data Volume**: Designed for hundreds to thousands of organisations, not millions
- **Growth**: Organisation data grows slowly (new organisations added infrequently)
- **Read Replicas**: RDS supports read replicas for high-read workloads

### Reliability

- **ACID Transactions**: All operations use PostgreSQL transactions
- **Foreign Key Constraints**: Cascading deletes ensure referential integrity
- **Unique Constraints**: Prevent duplicate organisation memberships
- **CHECK Constraints**: Validate data at database level (org types, roles, access levels)

### Security

- **Parameterized Queries**: All queries use parameterized statements (no SQL injection)
- **Connection String**: Sensitive connection details stored in environment variables
- **Password Security**: Token hashes stored (SHA-256), never raw tokens
- **AWS Integration**: RDS encryption at rest, Secrets Manager for credentials

---

## Data Model / Schema Design

### Connection Configuration

```python
connection_params = {
    "connection_string": "postgresql://user:password@host:port/database"
}
```

Environment variable: `DATABASE_URL`

### Table: `organisations`

```sql
CREATE TABLE IF NOT EXISTS organisations (
    organisation_id    TEXT PRIMARY KEY,      -- STIX format: identity--{uuid4}
    organisation_type  TEXT NOT NULL
        CHECK (organisation_type IN ('cyber_partner', 'customer')),
    access_level       TEXT
        CHECK (access_level IN ('public', 'observer', 'contributor', 'partner', 'core_member')),
    sector             TEXT,
    region             TEXT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active        TIMESTAMP,
    contribution_score INTEGER DEFAULT 0,
    client_count       INTEGER DEFAULT 0,
    metadata_json      TEXT                   -- Flexible JSON for extra fields
);
```

**Key Differences from SQLite**:
- Schema is identical to SQLite for maximum compatibility
- PostgreSQL provides true concurrent access (no file locking)
- `ON CONFLICT` clause used for upsert operations (more explicit than SQLite's `INSERT OR REPLACE`)

### Table: `organisation_members`

```sql
CREATE TABLE IF NOT EXISTS organisation_members (
    id              SERIAL PRIMARY KEY,       -- Auto-incrementing (SERIAL vs AUTOINCREMENT)
    organisation_id TEXT NOT NULL,
    username        TEXT NOT NULL,             -- Cognito username (humans + service-* accounts)
    role            TEXT NOT NULL
        CHECK (role IN ('member', 'admin', 'owner')),
    joined_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id) ON DELETE CASCADE,
    UNIQUE(organisation_id, username)
);
```

**Key Features**:
- `ON DELETE CASCADE`: Deleting an organisation automatically removes all members
- `UNIQUE(organisation_id, username)`: Prevents duplicate memberships
- `ON CONFLICT ... DO UPDATE SET role = EXCLUDED.role`: Upsert for `add_organisation_member()`
- `RETURNING` clause: Returns created/updated record in `add_organisation_member()`

### Table: `refresh_tokens`

```sql
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_id   TEXT PRIMARY KEY,              -- JWT jti claim
    user_id    TEXT NOT NULL,                 -- Cognito username
    token_hash TEXT NOT NULL UNIQUE,          -- SHA-256 hash of refresh token
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_revoked BOOLEAN DEFAULT FALSE          -- Soft delete for revocation
);
```

**Key Differences from SQLite**:
- Uses PostgreSQL `BOOLEAN` (TRUE/FALSE) instead of SQLite `BOOLEAN` (0/1)
- No explicit expiry checking in query -- application checks expiry after retrieval

### Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_org_members_org_id    ON organisation_members(organisation_id);
CREATE INDEX IF NOT EXISTS idx_org_members_username   ON organisation_members(username);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash    ON refresh_tokens(token_hash);
```

**Note**: Fewer indexes than SQLite because PostgreSQL only manages 3 tables (vs SQLite's 10).

### Extensions

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

Enables PostgreSQL's native UUID generation (available but currently using Python-generated STIX-format IDs).

### Entity Relationship Diagram

```
organisations (1) ----< (many) organisation_members (ON DELETE CASCADE)
                                    |
                                    +-- UNIQUE(organisation_id, username)

refresh_tokens -- standalone (no foreign keys)
```

### Query Patterns

| Operation | SQL Pattern | Notes |
|-----------|-------------|-------|
| Upsert org | `INSERT ... ON CONFLICT (organisation_id) DO UPDATE SET ...` | Atomic upsert |
| List orgs | `SELECT * FROM organisations WHERE 1=1 [AND filters] ORDER BY created_at DESC` | Dynamic WHERE |
| Update org | `UPDATE organisations SET [dynamic fields] WHERE organisation_id = %s` | Dynamic SET |
| Delete org | `DELETE FROM organisations WHERE organisation_id = %s` | Cascades to members |
| Add member | `INSERT ... ON CONFLICT (org_id, username) DO UPDATE SET role = EXCLUDED.role RETURNING *` | Upsert with return |
| User's orgs | `SELECT o.*, m.role FROM organisations o JOIN organisation_members m ON ... WHERE m.username = %s` | JOIN query |
| Revoke tokens | `UPDATE refresh_tokens SET is_revoked = TRUE WHERE user_id = %s AND is_revoked = FALSE` | Batch soft delete |

### Factory Function

```python
def create_postgresql_database(
    connection_string: str,
    logger: Optional[logging.Logger] = None
) -> PostgreSQLFRANKDatabase:
```

**Example**:
```python
db = create_postgresql_database(
    "postgresql://frank:password@localhost:5432/frank_management"
)
```

---

## Implementation Status Matrix

### Implemented Methods (14 methods)

| Method | Status | Notes |
|--------|--------|-------|
| `initialize()` | Implemented | Creates tables + indexes + uuid-ossp extension |
| `upsert_organisation()` | Implemented | ON CONFLICT upsert |
| `create_organisation()` | Implemented | Delegates to upsert, returns ID |
| `get_organisation()` | Implemented | With metadata JSON parsing |
| `list_organisations()` | Implemented | Dynamic filters via **kwargs |
| `update_organisation()` | Implemented | Dynamic SET clause |
| `delete_organisation()` | Implemented | Cascading delete |
| `add_organisation_member()` | Implemented | Upsert with RETURNING |
| `remove_organisation_member()` | Implemented | DELETE with rowcount check |
| `get_organisation_members()` | Implemented | Optional role filter |
| `get_user_organisations()` | Implemented | JOIN query |
| `get_organisation_member()` | Implemented | Single record lookup |
| `store_refresh_token()` | Implemented | INSERT |
| `get_refresh_token()` | Implemented | WHERE is_revoked = FALSE |
| `revoke_refresh_token()` | Implemented | SET is_revoked = TRUE |
| `revoke_all_user_refresh_tokens()` | Implemented | Batch update, returns count |
| `log_access()` | Implemented | Application logger only (no DB write) |
| `health_check()` | Implemented | SELECT 1 connectivity check |

### NotImplementedError Methods (5 methods)

| Method | Error Message | Redirect To |
|--------|---------------|-------------|
| `store_submission()` | "Submissions are stored in DynamoDB, not PostgreSQL" | DynamoDB |
| `get_submission_by_id()` | "Submissions are stored in DynamoDB, not PostgreSQL" | DynamoDB |
| `query_observables()` | "Observables are stored in DynamoDB, not PostgreSQL" | DynamoDB |
| `search_observables_by_value()` | "Observables are stored in DynamoDB, not PostgreSQL" | DynamoDB |
| `get_statistics_summary()` | "Statistics are stored in DynamoDB, not PostgreSQL" | DynamoDB |

---

## Test Coverage Requirements

### Unit Tests

**Location**: `tests/unit/storage/test_dynamodb.py` (referenced in ADR-0009)

**Required Unit Test Coverage**:
- [ ] Schema creation (tables, indexes, extension)
- [ ] Organisation CRUD lifecycle (create, get, list, update, delete)
- [ ] Cascading delete (org deletion removes members)
- [ ] Organisation member management (add, remove, get, list)
- [ ] Upsert behavior (add_organisation_member updates role on conflict)
- [ ] User organisations query (JOIN correctness)
- [ ] Refresh token lifecycle (store, get, revoke, revoke_all)
- [ ] NotImplementedError for all 5 unimplemented methods
- [ ] Health check (healthy and unhealthy cases)
- [ ] Connection string validation (missing connection_string raises FRANKConnectionError)
- [ ] Metadata JSON parsing and storage
- [ ] Dynamic filter building in list_organisations

**Coverage Target**: >= 85% code coverage

### Integration Tests

**Location**: `tests/integration/features/management_api_users.feature`

**Required Integration Test Scenarios**:
- [ ] Create organisation and add members via Management API
- [ ] Service account creation with auto-generated password
- [ ] Organisation member role updates
- [ ] Database seeding on empty database
- [ ] PostgreSQL + Cognito integration (member lookup for JWT validation)

---

## Evolution Path Across FRANK Stages

### Stage 1: SQLite + FastAPI (Local Development)

- **Status**: Not used (SQLite handles all management data)
- **PostgreSQL is not needed for local development**

### Stage 2: DynamoDB + Docker (Learning Stage)

- **Status**: Optional (can use Docker PostgreSQL or SQLite fallback)
- **Environment**: PostgreSQL in Docker Compose alongside DynamoDB/LocalStack
- **Learning Goal**: Validate PostgreSQL schema, test migration from SQLite

### Stage 3: AWS ECS + DynamoDB + PostgreSQL (Cloud Deployment)

- **Status**: Production deployment
- **Infrastructure**: Amazon RDS PostgreSQL 16.x
- **Instance**: db.t4g.micro (development) to db.r6g.large (production)
- **Availability**: Multi-AZ for high availability
- **Security**: VPC-only access, KMS encryption, Secrets Manager for credentials
- **Backup**: Automated daily backups with 7-day retention
- **Monitoring**: CloudWatch metrics for connections, latency, storage

### Stage 4: Kubernetes + ScyllaDB (Production Scale)

- **Status**: Planned
- **PostgreSQL continues**: Management data remains in PostgreSQL (or cloud-native equivalent)
- **Rationale**: Management data is low-volume and relational; PostgreSQL remains the right choice
- **Alternative**: Cloud-managed PostgreSQL (Aurora, Cloud SQL, etc.)

### Migration Strategy from SQLite

```python
# Connect to both databases
sqlite_db = create_sqlite_database("/tmp/frank_management.db")
pg_db = create_postgresql_database("postgresql://frank:password@localhost:5432/frank_management")

# Migrate organisations
orgs = sqlite_db.list_organisations()
for org in orgs:
    pg_db.upsert_organisation(org)

# Migrate organisation members
for org in orgs:
    members = sqlite_db.get_organisation_members(org['organisation_id'])
    for member in members:
        pg_db.add_organisation_member(
            organisation_id=org['organisation_id'],
            username=member['username'],
            role=member['role']
        )

# Refresh tokens are short-lived, no migration needed
```

### Why PostgreSQL for Management Data

| Requirement | PostgreSQL | DynamoDB | SQLite |
|-------------|-----------|----------|--------|
| Foreign keys | Native | Not supported | Supported but fragile |
| Cascading deletes | Native | Not supported | Supported |
| JOIN queries | Efficient | Expensive (multiple queries) | Supported |
| ACID transactions | Full | Limited (25 items) | File-level locking |
| Unique constraints | Native | Conditional writes only | Supported |
| Concurrent writes | Excellent | Excellent | Single writer |
| Production multi-instance | Excellent | Excellent | Not supported |
| Operational overhead | Moderate (RDS manages) | Low (fully managed) | Zero |
| Cost | $15-300/month | Pay-per-request | Free |

---

## References

- **Related ADRs**:
  - [ADR-0002: Repository Pattern for Database Abstraction](.openspec/architecture/decisions/004-repository-pattern-database-abstraction.md)
  - [ADR-0003: Tiered Access Control Model](.openspec/architecture/decisions/002-tiered-access-control.md)
  - [ADR-0005: Cognito Authentication](.openspec/architecture/decisions/006-cognito-authentication.md)
  - [ADR-0009: PostgreSQL for Management API](.openspec/architecture/decisions/010-postgresql-management-api.md)

- **Related Specifications**:
  - [Base Interface Spec](../020-storage-base-interface/spec.md) -- interface this implements
  - [SQLite Implementation Spec](../021-storage-sqlite/spec.md) -- complete reference implementation
  - [DynamoDB Implementation Spec](../022-storage-dynamodb/spec.md) -- threat intelligence complement

- **Source Files**:
  - [`src/frank/storage/postgresql.py`](src/frank/storage/postgresql.py) -- Implementation
  - [`src/frank/storage/base.py`](src/frank/storage/base.py) -- Interface

- **Test Files**:
  - `tests/unit/storage/test_dynamodb.py` (referenced in ADR-0009)

- **Deployment Files**:
  - `docker-compose.local.yml` -- PostgreSQL Docker service
  - `docker/Dockerfile.management` -- Management API with psycopg dependencies

- **External References**:
  - [PostgreSQL 16 Documentation](https://www.postgresql.org/docs/16/)
  - [psycopg 3 Documentation](https://www.psycopg.org/psycopg3/docs/)
  - [Amazon RDS PostgreSQL](https://aws.amazon.com/rds/postgresql/)

---

## Open Questions & Decisions Pending

- [ ] **Connection Pooling**: Current implementation opens a new connection per operation. Should psycopg's `ConnectionPool` be used for production?
  - **Recommendation**: Use `psycopg_pool.ConnectionPool` for Stage 3 production
  - **Decision**: Pending production deployment experience

- [ ] **list_organisations Signature**: The PostgreSQL implementation uses `**filters` kwargs instead of the base class's explicit parameters. Should it match the base class signature exactly?
  - **Recommendation**: Align with base class signature for interface consistency
  - **Decision**: Pending code cleanup

- [ ] **log_access Implementation**: Currently a passthrough to application logger. Should PostgreSQL have its own audit table?
  - **Recommendation**: Keep passthrough; DynamoDB audit table is the canonical audit log
  - **Decision**: Accepted -- PostgreSQL only manages business data, not audit data

- [ ] **Automatic Seeding**: The Management API seeds PostgreSQL on startup if empty. Should this be documented as a formal behavior or a convenience feature?
  - **Recommendation**: Document as development convenience; production uses explicit seeding
  - **Decision**: Pending clarification

- [ ] **create_organisation Return Type**: Returns `Optional[str]` (organisation_id) instead of `Dict[str, Any]` as specified in base class. Should it be aligned?
  - **Recommendation**: Return full organisation dict to match base class contract
  - **Decision**: Pending code cleanup

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 2026-02-06 | 1.0 | FRANK Platform Team | Initial specification reverse-engineered from implementation |
