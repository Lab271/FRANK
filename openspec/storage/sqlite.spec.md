# SQLite Implementation Specification

**Domain:** Storage Layer / Database Implementations
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06

**FRANK-Specific Metadata**:
- **Owner:** FRANK Platform Team
- **Related ADRs:** [ADR-0002](docs/adr/0002-repository-pattern-database-abstraction.md), [ADR-0003](docs/adr/0003-tiered-access-control-model.md)
- **Implementation:** [src/frank/storage/sqlite.py](src/frank/storage/sqlite.py)
- **Tests:** [tests/unit/storage/test_sqlite.py](tests/unit/storage/test_sqlite.py)

## Overview

The `SQLiteFRANKDatabase` is the **reference implementation** of the `BaseFRANKDatabase` interface. It implements **every** method in the interface, making it the only complete implementation in the FRANK platform.

### Philosophy

- **Zero Infrastructure**: No server, no network, no configuration - just a file
- **Reference Implementation**: All 23 interface methods fully implemented
- **Development First**: Primary database for local development (Stage 1)
- **Universal Fallback**: Every stage can fall back to SQLite if cloud unavailable
- **Immediate Contribution**: Developers start coding without database installation

### Key Capabilities

- **Complete Interface Implementation**: All 23 methods from BaseFRANKDatabase
- **Auto-Schema Creation**: Tables and indexes created automatically on first use
- **Full Submission Pipeline**: Normalizes Pydantic models to relational tables
- **Access Tier Filtering**: Inherits filtering from base class
- **Observable Querying**: Complex filters on type, role, submitter, timerange
- **Transaction Safety**: All operations atomic with SQLite transactions
- **WAL Mode**: Write-Ahead Logging for better concurrency

SQLite was chosen for Stage 1 because it stores everything in a single file while providing relational integrity with foreign keys, transactions, and indexes. This enables immediate developer productivity.

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Usage in this specification**:
- **MUST/SHALL**: Complete interface implementation, schema creation, transaction atomicity
- **SHOULD**: Use WAL mode for better concurrency
- **MAY**: Add SQLite-specific optimizations (indexes, triggers)

---

## ADDED Requirements

### Requirement 1: Complete Interface Implementation

- **Description**: SQLiteFRANKDatabase must implement ALL abstract methods from BaseFRANKDatabase. No method may raise `NotImplementedError`.
- **Acceptance Criteria**:
  - [ ] All 23 abstract methods from BaseFRANKDatabase are implemented
  - [ ] All Organisation CRUD methods work (create, get, list, update, delete)
  - [ ] All Organisation Member methods work (add, remove, get, list)
  - [ ] All Refresh Token methods work (store, get, revoke, revoke_all)
  - [ ] All threat intelligence methods work (submissions, observables, statistics)
  - [ ] API key methods work (create, get_by_hash, list, update, revoke, update_last_used)
  - [ ] Health check returns table counts and database file size
- **Stage Availability**: All stages (1-4, as fallback)
- **Related ADR**: [ADR-0002](docs/adr/0002-repository-pattern-database-abstraction.md)

### Requirement 2: Schema Auto-Creation

- **Description**: The `initialize()` method must create all tables, indexes, and constraints on first use. Subsequent calls must be idempotent (no errors if tables already exist).
- **Acceptance Criteria**:
  - [ ] `CREATE TABLE IF NOT EXISTS` used for all tables
  - [ ] `CREATE INDEX IF NOT EXISTS` used for all indexes
  - [ ] Foreign keys are enabled via `PRAGMA foreign_keys = ON`
  - [ ] WAL journal mode enabled for better concurrency via `PRAGMA journal_mode = WAL`
  - [ ] Schema creation is transactional (commit at end of initialize)
- **Stage Availability**: All stages

### Requirement 3: Full Submission Storage Pipeline

- **Description**: `store_submission()` must normalize a complete `Submission` Pydantic model into multiple relational tables in a single transaction.
- **Acceptance Criteria**:
  - [ ] Submission record stored in `submissions` table
  - [ ] Submitter organisation upserted in `organisations` table
  - [ ] Hit target organisation upserted (if present) in `organisations` table
  - [ ] Sighting record stored in `sightings` table
  - [ ] All observables stored in `observables` table with hashes
  - [ ] Observable statistics updated (aggregated counts, sectors, regions)
  - [ ] SIGMA rule stored (if present) in `sigma_rules` table
  - [ ] Campaign stored (if present) in `campaigns` table
  - [ ] Access log entry created
  - [ ] All operations within a single SQLite transaction (atomic)
- **Stage Availability**: All stages

### Requirement 4: Access Tier Filtered Retrieval

- **Description**: `get_submission_by_id()` must retrieve the full JSON submission from the database and apply access tier filtering before returning.
- **Acceptance Criteria**:
  - [ ] Retrieves `full_submission_json` from submissions table
  - [ ] Joins with organisations to get submitter access tier
  - [ ] Applies `_filter_submission_by_access_level()` from base class
  - [ ] Logs access via `_log_access()`
  - [ ] Returns `Submission` Pydantic model (not raw dict)
  - [ ] Returns `None` if submission not found
- **Stage Availability**: All stages

### Requirement 5: Observable Querying with Filters

- **Description**: `query_observables()` must support multi-dimensional filtering with access control.
- **Acceptance Criteria**:
  - [ ] Filter by `observable_type` (ipv4, domain, etc.)
  - [ ] Filter by `min_confidence` (average confidence >= threshold)
  - [ ] Filter by `sectors` (LIKE match on JSON array)
  - [ ] Filter by `days_back` (last_seen within N days)
  - [ ] Apply `_filter_observable_by_access_level()` to each result
  - [ ] Respect `limit` parameter
  - [ ] Order by `last_seen DESC`
  - [ ] Parse JSON fields (sectors_json, regions_json) in results
- **Stage Availability**: All stages

---

## 3. Non-Functional Requirements

### Performance

- **Initialization**: Schema creation < 100ms on modern hardware
- **Single Submission**: Store complete submission < 50ms
- **Observable Query**: Return filtered results < 100ms for datasets up to 100K observables
- **Index Coverage**: All query patterns covered by indexes (no full table scans for common queries)

### Concurrency

- **WAL Mode**: Enables concurrent readers with a single writer
- **Connection-per-Operation**: Each method opens and closes its own connection
- **Foreign Keys**: Enforced on every connection (`PRAGMA foreign_keys = ON`)

### Storage

- **File-Based**: Single `.db` file at configurable path (default: `/tmp/frank.db`)
- **Size**: Grows linearly with data; observable statistics provide aggregation to limit growth
- **Portability**: Database file can be copied, shared, backed up as a single file

### Reliability

- **Transactions**: All multi-table operations use SQLite transactions
- **INSERT OR REPLACE**: Upsert semantics for idempotent writes
- **Error Wrapping**: sqlite3 errors wrapped in FRANK domain exceptions

---

## 4. Data Model / Schema Design

### Database Configuration

```python
DEFAULT_CONFIG = {
    'database_type': 'sqlite',
    'database_path': '/tmp/frank.db',
    'log_level': 'INFO',
    'default_tier': 'contributor',
    'retention_days': 90
}
```

### Table: `organisations`

Stores both cyber partners (submitters) and customers (hit targets).

```sql
CREATE TABLE IF NOT EXISTS organisations (
    organisation_id    TEXT PRIMARY KEY,                    -- STIX format: identity--{uuid4}
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
    metadata_json      TEXT                                -- Flexible JSON for extra fields
);
```

### Table: `submissions`

Main submission records with full JSON payload.

```sql
CREATE TABLE IF NOT EXISTS submissions (
    submission_id        TEXT PRIMARY KEY,
    submitter_org_id     TEXT NOT NULL,
    hit_target_org_id    TEXT,
    format_version       TEXT DEFAULT 'unknown',
    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence           INTEGER CHECK (confidence >= 0 AND confidence <= 100),
    severity             TEXT CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    tlp_level            TEXT CHECK (tlp_level IN ('RED', 'AMBER+', 'AMBER', 'GREEN', 'CLEAR')),
    full_submission_json TEXT NOT NULL,                    -- Complete Pydantic model as JSON
    processed_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submitter_org_id) REFERENCES organisations (organisation_id),
    FOREIGN KEY (hit_target_org_id) REFERENCES organisations (organisation_id)
);
```

**Design Note**: The `full_submission_json` column stores the entire Pydantic Submission model as JSON. This enables retrieval of the complete submission without joining multiple tables, at the cost of some data duplication. The normalized columns (`confidence`, `severity`, `tlp_level`) enable efficient filtering without parsing JSON.

### Table: `sightings`

Individual threat sightings linked to submissions.

```sql
CREATE TABLE IF NOT EXISTS sightings (
    sighting_id          TEXT PRIMARY KEY,
    submission_id        TEXT NOT NULL,
    sighting_timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    first_observed       TIMESTAMP,
    last_observed        TIMESTAMP,
    observation_count    INTEGER DEFAULT 1,
    confidence           INTEGER,
    severity             TEXT,
    sigma_rule_id        TEXT,
    campaign_id          TEXT,
    affected_systems     INTEGER,
    compromised_accounts INTEGER,
    containment_time     TEXT,
    financial_impact_eur INTEGER,
    FOREIGN KEY (submission_id) REFERENCES submissions (submission_id) ON DELETE CASCADE
);
```

### Table: `observables`

Individual Indicators of Compromise (IoCs) and artifacts.

```sql
CREATE TABLE IF NOT EXISTS observables (
    observable_id    TEXT PRIMARY KEY,
    sighting_id      TEXT NOT NULL,
    observable_type  TEXT NOT NULL
        CHECK (observable_type IN ('ipv4', 'ipv6', 'domain', 'url', 'file_hash', 'email', 'registry_key')),
    observable_value TEXT NOT NULL,
    observable_hash  TEXT NOT NULL,         -- SHA-256 for quick lookups and deduplication
    role             TEXT,
    port             INTEGER,
    protocol         TEXT,
    first_seen       TIMESTAMP,
    metadata_json    TEXT,
    FOREIGN KEY (sighting_id) REFERENCES sightings (sighting_id) ON DELETE CASCADE
);
```

### Table: `observable_statistics`

Aggregated sighting data for observables (pre-computed analytics).

```sql
CREATE TABLE IF NOT EXISTS observable_statistics (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    observable_hash       TEXT NOT NULL UNIQUE,
    observable_type       TEXT NOT NULL,
    observable_value      TEXT NOT NULL,
    total_sightings       INTEGER DEFAULT 1,
    unique_organisations  INTEGER DEFAULT 1,
    first_seen            TIMESTAMP,
    last_seen             TIMESTAMP,
    avg_confidence        REAL,
    sectors_json          TEXT,             -- JSON array of affected sectors
    regions_json          TEXT,             -- JSON array of affected regions
    organisation_ids_json TEXT,             -- JSON array of unique organisation IDs
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Design Note**: This table serves as a materialized view of observable sighting data. It is updated incrementally during `store_submission()` to avoid expensive aggregation queries at read time.

### Table: `access_logs`

Audit trail for all data access events.

```sql
CREATE TABLE IF NOT EXISTS access_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id TEXT NOT NULL,
    action          TEXT NOT NULL,          -- SUBMIT, READ, QUERY, SEARCH, STATS
    resource_type   TEXT,                   -- submission, observables, sigma_rules, etc.
    resource_id     TEXT,
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_level    TEXT,
    success         BOOLEAN DEFAULT TRUE,
    ip_address      TEXT,
    user_agent      TEXT,
    details_json    TEXT
);
```

### Table: `organisation_members`

Maps Cognito users to organisations with roles.

```sql
CREATE TABLE IF NOT EXISTS organisation_members (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id TEXT NOT NULL,
    username        TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('member', 'admin', 'owner')),
    joined_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id) ON DELETE CASCADE,
    UNIQUE(organisation_id, username)
);
```

### Table: `sigma_rules`

SIGMA detection rules shared across the platform.

```sql
CREATE TABLE IF NOT EXISTS sigma_rules (
    rule_id             TEXT PRIMARY KEY,
    rule_name           TEXT NOT NULL,
    rule_version        TEXT,
    rule_status         TEXT CHECK (rule_status IN ('stable', 'test', 'experimental')),
    sigma_yaml          TEXT,
    created_by_org      TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    effectiveness_score REAL,
    false_positive_rate REAL,
    FOREIGN KEY (created_by_org) REFERENCES organisations (organisation_id)
);
```

### Table: `campaigns`

Threat campaign tracking and attribution.

```sql
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id        TEXT PRIMARY KEY,
    campaign_name      TEXT NOT NULL,
    attribution        TEXT,
    target_sectors_json TEXT,
    attack_vector      TEXT,
    payload_type       TEXT,
    campaign_start     TIMESTAMP,
    estimated_victims  INTEGER,
    confidence         INTEGER,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `api_keys`

API keys for programmatic access (implementation-specific, not in base interface).

```sql
CREATE TABLE IF NOT EXISTS api_keys (
    key_id      TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    key_hash    TEXT NOT NULL UNIQUE,
    key_prefix  TEXT NOT NULL,
    name        TEXT NOT NULL,
    expires_at  TIMESTAMP,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    is_active   BOOLEAN DEFAULT 1
);
```

**Note**: API key management is handled by AWS Cognito in Stages 2+. This table exists for Stage 1 local development convenience.

### Table: `refresh_tokens`

OAuth2 refresh token tracking for logout/revocation.

```sql
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_id   TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_revoked BOOLEAN DEFAULT 0
);
```

### Indexes

The following indexes are created for query performance optimization:

```sql
-- Submissions
CREATE INDEX IF NOT EXISTS idx_submissions_submitter  ON submissions (submitter_org_id);
CREATE INDEX IF NOT EXISTS idx_submissions_timestamp  ON submissions (submission_timestamp);
CREATE INDEX IF NOT EXISTS idx_submissions_severity   ON submissions (severity);
CREATE INDEX IF NOT EXISTS idx_submissions_tlp        ON submissions (tlp_level);

-- Sightings
CREATE INDEX IF NOT EXISTS idx_sightings_submission   ON sightings (submission_id);
CREATE INDEX IF NOT EXISTS idx_sightings_confidence   ON sightings (confidence);
CREATE INDEX IF NOT EXISTS idx_sightings_observed     ON sightings (first_observed);

-- Observables
CREATE INDEX IF NOT EXISTS idx_observables_hash       ON observables (observable_hash);
CREATE INDEX IF NOT EXISTS idx_observables_type       ON observables (observable_type);
CREATE INDEX IF NOT EXISTS idx_observables_sighting   ON observables (sighting_id);
CREATE INDEX IF NOT EXISTS idx_observables_value      ON observables (observable_value);

-- Observable Statistics
CREATE INDEX IF NOT EXISTS idx_statistics_hash        ON observable_statistics (observable_hash);
CREATE INDEX IF NOT EXISTS idx_statistics_type        ON observable_statistics (observable_type);
CREATE INDEX IF NOT EXISTS idx_statistics_updated     ON observable_statistics (updated_at);

-- Access Logs
CREATE INDEX IF NOT EXISTS idx_access_logs_org        ON access_logs (organisation_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp  ON access_logs (timestamp);
CREATE INDEX IF NOT EXISTS idx_access_logs_action     ON access_logs (action);

-- Organisations
CREATE INDEX IF NOT EXISTS idx_organisations_tier     ON organisations (tier);
CREATE INDEX IF NOT EXISTS idx_organisations_sector   ON organisations (sector);
CREATE INDEX IF NOT EXISTS idx_organisations_active   ON organisations (last_active);

-- Organisation Members
CREATE INDEX IF NOT EXISTS idx_org_members_org        ON organisation_members (organisation_id);
CREATE INDEX IF NOT EXISTS idx_org_members_user       ON organisation_members (username);

-- API Keys
CREATE INDEX IF NOT EXISTS idx_api_keys_user          ON api_keys (user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash          ON api_keys (key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_active        ON api_keys (is_active);

-- Refresh Tokens
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user    ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash    ON refresh_tokens (token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_revoked ON refresh_tokens (is_revoked);
```

### Entity Relationship Diagram

```
organisations (1) ----< (many) submissions (via submitter_org_id)
organisations (1) ----< (many) submissions (via hit_target_org_id)
organisations (1) ----< (many) organisation_members
organisations (1) ----< (many) sigma_rules (via created_by_org)

submissions   (1) ----< (many) sightings (ON DELETE CASCADE)
sightings     (1) ----< (many) observables (ON DELETE CASCADE)

observable_statistics -- aggregates observables by observable_hash (no FK)
access_logs           -- standalone audit table (no FK)
campaigns             -- standalone reference table (no FK)
api_keys              -- standalone auth table (no FK)
refresh_tokens        -- standalone auth table (no FK)
```

### Transaction Pattern

All multi-table write operations use a single connection with auto-commit at the end:

```python
with sqlite3.connect(db_path) as conn:
    conn.execute("PRAGMA foreign_keys = ON")
    # ... multiple INSERT/UPDATE operations ...
    conn.commit()
```

On error, the connection context manager automatically rolls back uncommitted changes.

### Factory Function

```python
def create_sqlite_database(
    db_path: str = "/tmp/frank_local.db",
    logger: Optional[logging.Logger] = None
) -> SQLiteFRANKDatabase:
```

---

## 5. Test Coverage Requirements

### Unit Tests

**Location**: `tests/unit/storage/test_sqlitedatabase.py`, `tests/unit/storage/test_organisation_crud.py`

**Required Unit Test Coverage**:
- [ ] Schema creation on fresh database
- [ ] Idempotent schema creation (call initialize twice)
- [ ] Store and retrieve submission round-trip
- [ ] Observable statistics aggregation (new + update)
- [ ] Organisation CRUD lifecycle (create, get, list, update, delete)
- [ ] Organisation member management (add, remove, list)
- [ ] Refresh token lifecycle (store, get, revoke, revoke_all)
- [ ] API key lifecycle (create, get, list, update, revoke)
- [ ] Access tier filtering on submissions and observables
- [ ] Query filtering (by type, confidence, sector, days_back)
- [ ] Search by observable value (LIKE matching)
- [ ] Statistics summary computation
- [ ] Health check returns correct structure
- [ ] Access logging
- [ ] Error handling for database failures
- [ ] Foreign key constraint enforcement

**Coverage Target**: >= 85% code coverage

### Integration Tests

**Location**: `tests/integration/`

**Required Integration Test Scenarios**:
- [ ] Full submission workflow: generate submission -> store -> retrieve -> filter
- [ ] Cross-database consistency: same tests pass on SQLite and DynamoDB
- [ ] Cascading delete: deleting organisation cascades to members

---

## 6. Implementation Status

### Checklist

- [x] Specification complete and reviewed
- [x] Unit tests written and passing
- [x] Integration tests written and passing
- [x] Implementation complete (ALL methods)
- [x] Code review passed
- [x] Merged to main branch

### Progress Notes

**Current Phase**: IMPLEMENTED

SQLiteFRANKDatabase is the most mature and complete implementation. It serves as the reference for all other implementations.

### Implementation Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/frank/storage/sqlite.py` | ~2025 | Full implementation |
| `tests/unit/storage/test_sqlitedatabase.py` | - | Core unit tests |
| `tests/unit/storage/test_organisation_crud.py` | - | Organisation CRUD tests |

### Additional Methods (Not in Base Interface)

The SQLite implementation provides additional methods beyond the base interface:

| Method | Description |
|--------|-------------|
| `get_organisation_info()` | Retrieve organisation with parsed metadata |
| `get_sigma_rules()` | Query SIGMA rules with status filtering |
| `get_campaigns()` | Query campaigns with active-only filter |
| `get_access_logs()` | Query audit logs by org, time, and action |
| `create_api_key()` | Create API key (Stage 1 only) |
| `get_api_key_by_hash()` | Lookup API key by hash |
| `list_api_keys()` | List API keys for user |
| `update_api_key()` | Update API key metadata |
| `revoke_api_key()` | Soft-delete API key |
| `update_api_key_last_used()` | Update last-used timestamp |

---

## 7. Evolution Path Across FRANK Stages

### Stage 1: SQLite + FastAPI (Local Development)

- **Status**: Fully implemented (reference implementation)
- **Database File**: Single `.db` file (default: `/tmp/frank_local.db`)
- **All Features**: Every interface method implemented and tested
- **Performance**: Sufficient for development workloads (thousands of submissions)
- **Concurrency**: WAL mode supports concurrent reads, single writer adequate for dev
- **This is the development baseline that must never break**

### Stage 2: DynamoDB + Docker (Learning Stage)

- **Status**: SQLite available as fallback
- **Usage**: SQLite used for organisation management while learning DynamoDB patterns
- **Migration**: No data migration needed; SQLite is always clean-startable

### Stage 3: AWS ECS + DynamoDB + PostgreSQL (Cloud Deployment)

- **Status**: SQLite available as local test/fallback only
- **Usage**: Development testing and CI/CD pipeline
- **Not in Production**: Production uses DynamoDB + PostgreSQL

### Stage 4: Kubernetes + ScyllaDB (Production Scale)

- **Status**: SQLite remains available as test/fallback
- **Usage**: Local development, test suites, emergency fallback

### Why SQLite Is the Development Baseline

1. **Zero Setup**: No server installation, no configuration, no Docker required
2. **Single File**: Easy to share, copy, back up, delete and start fresh
3. **Complete Features**: All methods implemented, no `NotImplementedError` stubs
4. **Relational Integrity**: Foreign keys, constraints, transactions -- validates data model
5. **Fast Tests**: In-memory or file-based, no network latency
6. **Always Available**: Works on any platform with Python installed

---

## 8. References

- **Related ADRs**:
  - [ADR-0002: Repository Pattern for Database Abstraction](docs/adr/0002-repository-pattern-database-abstraction.md)
  - [ADR-0003: Tiered Access Control Model](docs/adr/0003-tiered-access-control-model.md)

- **Related Specifications**:
  - [Base Interface Spec](base-interface.spec.md) -- interface this implements
  - [DynamoDB Implementation Spec](dynamodb.spec.md) -- cloud alternative for threat data
  - [PostgreSQL Implementation Spec](postgresql.spec.md) -- cloud alternative for management data

- **Source Files**:
  - [`src/frank/storage/sqlite.py`](src/frank/storage/sqlite.py) -- Implementation
  - [`src/frank/storage/base.py`](src/frank/storage/base.py) -- Interface

- **Test Files**:
  - [`tests/unit/storage/test_sqlitedatabase.py`](tests/unit/storage/test_sqlitedatabase.py)
  - [`tests/unit/storage/test_organisation_crud.py`](tests/unit/storage/test_organisation_crud.py)

- **Related Spikes**:
  - [`tests/spikes/004_sqlite/README.md`](tests/spikes/004_sqlite/README.md) -- SQLite implementation spike

---

## 9. Open Questions & Decisions Pending

- [ ] **DateTime Handling**: SQLite uses adapter/converter registration for datetime compatibility with Python 3.12+. Should this be more formally documented?
  - **Current**: `sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())`
  - **Decision**: Working correctly; document in CLAUDE.md if it causes confusion

- [ ] **JSON Storage vs Normalization**: `full_submission_json` stores the entire submission as JSON for easy retrieval, duplicating data already normalized into other tables. Is this the right trade-off?
  - **Recommendation**: Keep JSON storage for retrieval speed; normalized columns for query filtering
  - **Decision**: Accepted trade-off; storage cost is minimal for SQLite

- [ ] **Observable Statistics Updates**: Statistics are updated incrementally during `store_submission()`. Should there be a separate batch recomputation mechanism?
  - **Recommendation**: Add a `recompute_statistics()` method for data repair scenarios
  - **Decision**: Pending -- not yet needed in practice

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 2026-02-06 | 1.0 | FRANK Platform Team | Initial specification reverse-engineered from implementation |
