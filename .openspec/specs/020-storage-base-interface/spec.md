# BaseFRANKDatabase Interface Specification

**Domain:** Storage Layer / Database Abstraction
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06

**Owner:** FRANK Platform Team
**Related ADRs:** [ADR-0002](docs/adr/0002-repository-pattern-database-abstraction.md), [ADR-0003](docs/adr/0003-tiered-access-control-model.md)
**Implementation:** [src/frank/storage/base.py](src/frank/storage/base.py)
**Tests:** [tests/unit/storage/](tests/unit/storage/)

## Overview

The `BaseFRANKDatabase` abstract base class defines the **repository pattern interface** for all database operations in the FRANK platform. It solves a fundamental architectural challenge: FRANK must run unchanged across multiple database technologies (SQLite, DynamoDB, PostgreSQL, and eventually ScyllaDB) as the platform evolves through its four infrastructure stages.

### Philosophy

- **Technology Independence**: Business logic never imports database drivers directly (sqlite3, boto3, psycopg)
- **Repository Pattern**: Single abstraction layer for all data access operations
- **Consistent Behavior**: Access filtering works identically across all implementations
- **Safe Transitions**: Switching databases requires changing only configuration, not code
- **Evolutionary Design**: Enables FRANK's four-stage infrastructure evolution without rewrites

### Key Capabilities

- **Abstract Interface Contract**: All database operations defined as abstract methods
- **Access Tier Filtering**: Built-in privacy enforcement (PUBLIC, OBSERVER, CONTRIBUTOR, PARTNER, CORE_MEMBER)
- **Observable Hashing**: Consistent deduplication across all database backends
- **Health Checks**: Standardized health monitoring interface
- **Testability**: Interface can be mocked for unit tests without database dependency

This is the **single most important architectural abstraction** in FRANK, enabling the entire evolutionary design philosophy described in [ADR-0001](docs/adr/0001-four-stage-infrastructure-evolution.md).

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Usage in this specification**:
- **MUST/SHALL**: Abstract method implementation, access filtering enforcement
- **SHOULD**: Use factory pattern for database instantiation
- **MAY**: Implementations may add database-specific optimizations

---

## ADDED Requirements

### Requirement 1: Abstract Interface Contract

- **Description**: `BaseFRANKDatabase` must define abstract methods for all database operations that business logic requires. Concrete implementations must implement every abstract method.
- **Acceptance Criteria**:
  - [ ] Class inherits from `ABC` (Abstract Base Class)
  - [ ] All public database operations are declared as `@abstractmethod`
  - [ ] Attempting to instantiate `BaseFRANKDatabase` directly raises `TypeError`
  - [ ] Each concrete implementation (SQLite, DynamoDB, PostgreSQL) can be instantiated
- **Stage Availability**: All stages (1-4)
- **Related ADR**: [ADR-0002](docs/adr/0002-repository-pattern-database-abstraction.md)

### Requirement 2: Constructor and Initialization

- **Description**: All implementations share a common constructor that accepts connection parameters and an optional logger, then calls `initialize()` to set up the database.
- **Acceptance Criteria**:
  - [ ] Constructor accepts `connection_params: Dict[str, Any]` and optional `logger: logging.Logger`
  - [ ] Constructor stores `connection_params` and `logger` as instance attributes
  - [ ] Constructor calls `self.initialize()` automatically
  - [ ] `initialize()` sets up database connection and creates schema if needed
- **Stage Availability**: All stages (1-4)

### Requirement 3: Access Tier Filtering

- **Description**: Access control filtering is implemented once in the base class and inherited by all implementations, ensuring consistent privacy enforcement across all database backends.
- **Acceptance Criteria**:
  - [ ] `_filter_submission_by_access_level()` correctly filters for all five tiers
  - [ ] `_filter_observable_by_access_level()` correctly filters for all five tiers
  - [ ] PUBLIC tier returns only statistics (submission_id, timestamp, confidence, observation_count)
  - [ ] OBSERVER tier masks observable values (first 10 chars + "...") and removes hit_target/tlp_level
  - [ ] CONTRIBUTOR tier anonymizes hit_target (removes organisation_id, keeps sector)
  - [ ] PARTNER and CORE_MEMBER tiers return full data
  - [ ] Filtering is identical regardless of which database implementation is used
- **Stage Availability**: All stages (1-4)
- **Related ADR**: [ADR-0003](docs/adr/0003-tiered-access-control-model.md)

### Requirement 4: Observable Hashing

- **Description**: A shared `hash_observable()` method provides consistent SHA-256 hashing for observable deduplication and quick lookups across all implementations.
- **Acceptance Criteria**:
  - [ ] `hash_observable(type, value)` returns SHA-256 hex digest
  - [ ] Hashing is case-insensitive (lowercases `type:value` before hashing)
  - [ ] Same type+value always produces the same hash
  - [ ] Hash is used consistently across SQLite and DynamoDB for deduplication
- **Stage Availability**: All stages (1-4)

---

## 3. Non-Functional Requirements

### Performance

- **Filtering Overhead**: Access tier filtering adds < 1ms per submission/observable
- **Hash Computation**: SHA-256 hash computation adds < 0.1ms per observable
- **Deep Copy**: `_deep_copy()` performs recursive copy without external dependencies

### Reliability

- **Error Handling**: All implementations use domain-specific exceptions from `frank.storage.exceptions`
- **Exception Hierarchy**: `FRANKDatabaseError` (base) -> `FRANKConnectionError`, `FRANKStorageError`, `FRANKQueryError`, `FRANKConfigurationError`
- **Logging**: All operations log through the instance logger for observability

### Security

- **Access Control**: Tier filtering enforces privacy at the data layer, not the API layer
- **Defense in Depth**: Even if API layer bypassed, database layer still filters sensitive fields
- **No Secrets in Logs**: Connection parameters should not be logged at INFO level

---

## 4. Data Model / Interface Contract

### Constructor

```python
class BaseFRANKDatabase(ABC):
    def __init__(
        self,
        connection_params: Dict[str, Any],
        logger: Optional[logging.Logger] = None
    ):
```

### Abstract Methods: Core Threat Intelligence

These methods handle the primary threat intelligence data flow.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `initialize` | `() -> None` | None | Set up database connection and schema |
| `store_submission` | `(submission: Submission) -> None` | None | Store a complete submission |
| `get_submission_by_id` | `(submission_id: str) -> Dict[str, Any]` | Submission dict or None | Retrieve submission with access filtering |
| `query_observables` | `(org_id, observable_type?, limit?, access_level?, min_confidence?, sectors?, days_back?) -> List[Observable]` | List of observables | Query observables with filters and access control |
| `search_observables_by_value` | `(org_id, search_value, access_level?) -> List[Dict]` | List of matches | Search observables by partial value match |
| `get_statistics_summary` | `(org_id, days?) -> Dict[str, Any]` | Statistics dict | Platform statistics summary |
| `upsert_organisation` | `(org_data: Dict) -> bool` | Success boolean | Insert or update organisation |
| `log_access` | `(org_id, action, resource_type?, details?) -> None` | None | Log access event for auditing |
| `health_check` | `() -> Dict[str, Any]` | Health status dict | Database connectivity and status check |

### Abstract Methods: Organisation CRUD

These methods manage organisation lifecycle.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `create_organisation` | `(org_data: Dict) -> Dict[str, Any]` | Created org with ID | Create new organisation |
| `get_organisation` | `(organisation_id: str) -> Optional[Dict]` | Org data or None | Get organisation by ID |
| `list_organisations` | `(organisation_type?, access_level?, sector?, limit?, offset?) -> List[Dict]` | List of orgs | List with optional filtering |
| `update_organisation` | `(organisation_id, updates: Dict) -> Optional[Dict]` | Updated org or None | Update existing organisation |
| `delete_organisation` | `(organisation_id: str) -> bool` | True if deleted | Delete organisation by ID |

### Abstract Methods: Organisation Members

These methods manage user-to-organisation relationships.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `add_organisation_member` | `(organisation_id, username, role?) -> Dict` | Membership record | Add user to organisation |
| `remove_organisation_member` | `(organisation_id, username) -> bool` | True if removed | Remove user from organisation |
| `get_organisation_members` | `(organisation_id, role?) -> List[Dict]` | List of members | Get members of organisation |
| `get_user_organisations` | `(username: str) -> List[Dict]` | List of orgs | Get orgs a user belongs to |
| `get_organisation_member` | `(organisation_id, username) -> Optional[Dict]` | Member or None | Get specific membership |

### Abstract Methods: Refresh Tokens

These methods manage OAuth2 refresh token lifecycle.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `store_refresh_token` | `(user_id, token_id, token_hash, expires_at) -> Dict` | Token metadata | Store refresh token hash |
| `get_refresh_token` | `(token_id: str) -> Optional[Dict]` | Token data or None | Get token (if not revoked/expired) |
| `revoke_refresh_token` | `(token_id: str) -> bool` | True if revoked | Revoke single token |
| `revoke_all_user_refresh_tokens` | `(user_id: str) -> int` | Count revoked | Revoke all tokens for user |

### Concrete Methods: Access Filtering

These are **not abstract** -- they are implemented once in the base class and shared by all implementations.

```python
def hash_observable(self, observable_type: str, observable_value: str) -> str:
    """SHA-256 hash of '{type}:{value}'.lower() for deduplication."""

def _filter_submission_by_access_level(
    self, submission: Dict[str, Any], access_level: AccessTier
) -> Dict[str, Any]:
    """Filter submission fields based on access tier."""

def _filter_observable_by_access_level(
    self, observable: Dict[str, Any], access_level: AccessTier
) -> Dict[str, Any]:
    """Filter observable fields based on access tier."""

def _deep_copy(self, obj: Any) -> Any:
    """Recursive deep copy without external dependencies."""
```

### Access Tier Filtering Rules

#### Submission Filtering (`_filter_submission_by_access_level`)

| Field | PUBLIC | OBSERVER | CONTRIBUTOR | PARTNER | CORE_MEMBER |
|-------|--------|----------|-------------|---------|-------------|
| `submission_id` | visible | visible | visible | visible | visible |
| `timestamp` | visible | visible | visible | visible | visible |
| `sighting.confidence` | visible | visible | visible | visible | visible |
| `sighting.timestamp` | visible | visible | visible | visible | visible |
| `sighting.observation_count` | visible | visible | visible | visible | visible |
| `sighting.observables` | hidden | masked (10 chars) | full | full | full |
| `hit_target` | hidden | hidden | anonymized* | full | full |
| `tlp_level` | hidden | hidden | visible | visible | visible |
| All other fields | hidden | visible | visible | visible | visible |

*Anonymized: `organisation_id` removed, `sector` kept with default "unknown"

#### Observable Filtering (`_filter_observable_by_access_level`)

| Field | PUBLIC | OBSERVER | CONTRIBUTOR+ |
|-------|--------|----------|-------------|
| `observable_type` | visible | visible | visible |
| `total_sightings` | visible | visible | visible |
| `last_seen` | visible | visible | visible |
| `observable_value` | hidden | masked (10 chars) | full |
| All other fields | hidden | visible | visible |

### Error Handling

All database operations use domain exceptions from `frank.storage.exceptions`:

```
FRANKDatabaseError (base)
  |-- FRANKConfigurationError   # Invalid configuration
  |-- FRANKConnectionError      # Cannot connect to database
  |-- FRANKStorageError         # Write/update/delete failures
  |-- FRANKQueryError           # Read/query failures
```

---

## 5. Test Coverage Requirements

### Unit Tests

**Location**: `tests/unit/storage/test_basefrankdatabase.py`

**Required Unit Test Coverage**:
- [ ] Access tier filtering: each tier returns correct fields for submissions
- [ ] Access tier filtering: each tier returns correct fields for observables
- [ ] Observable hashing: consistent, case-insensitive, deterministic
- [ ] Deep copy: correctly copies nested dicts and lists
- [ ] Cannot instantiate BaseFRANKDatabase directly (raises TypeError)

**Coverage Target**: >= 85% code coverage

### Integration Tests

**Location**: `tests/integration/`

**Required Integration Test Scenarios**:
- [ ] Same submission filtered at different tiers produces correct output
- [ ] Filtering is consistent between SQLite and DynamoDB implementations
- [ ] Access logging captures filtering decisions

---

## 6. Implementation Status

### Checklist

- [x] Specification complete and reviewed
- [x] Unit tests written and passing
- [x] Integration tests written and passing
- [x] Implementation complete
- [x] Code review passed
- [x] Merged to main branch

### Progress Notes

**Current Phase**: IMPLEMENTED

The `BaseFRANKDatabase` interface has been stable since early development and is the foundation for all three concrete implementations (SQLite, DynamoDB, PostgreSQL).

### Implementation Files

| File | Purpose |
|------|---------|
| `src/frank/storage/base.py` | Abstract base class (529 lines) |
| `src/frank/storage/exceptions.py` | Exception hierarchy |
| `src/frank/storage/__init__.py` | Package exports and factory functions |
| `tests/unit/storage/test_basefrankdatabase.py` | Base class unit tests |

---

## 7. Evolution Path Across FRANK Stages

### Stage 1: SQLite + FastAPI (Local Development)

- **Status**: Fully implemented
- **Implementation**: `SQLiteFRANKDatabase` implements all abstract methods
- **Usage**: Single-file database, all features available locally
- **Fallback**: Always available as development baseline

### Stage 2: DynamoDB + Docker (Learning Stage)

- **Status**: Partially implemented
- **Implementation**: `DynamoDBFRANKDatabase` implements threat intelligence methods; organisation CRUD raises `NotImplementedError`
- **Usage**: DynamoDB for submissions/observables, SQLite fallback for organisations
- **Key Pattern**: Learning AWS access patterns while maintaining interface contract

### Stage 3: AWS ECS + DynamoDB + PostgreSQL (Cloud Deployment)

- **Status**: Fully implemented
- **Implementation**: DynamoDB for threat intelligence, PostgreSQL for management data
- **Usage**: Two implementations used in parallel, each handling different data domains
- **Key Pattern**: Database selection based on data characteristics, not infrastructure stage

### Stage 4: Kubernetes + ScyllaDB (Production Scale)

- **Status**: Not yet implemented
- **Future**: `ScyllaDBFRANKDatabase` will implement the same interface
- **Key Pattern**: Adding new implementations without changing business logic

### Database Selection Strategy

```
Data Type                  | Stage 1    | Stage 2-3        | Stage 4
---------------------------+------------+------------------+------------------
Threat Intelligence        | SQLite     | DynamoDB          | ScyllaDB
  (submissions, sightings, |            |                   |
   observables)            |            |                   |
Management Data            | SQLite     | PostgreSQL        | PostgreSQL
  (organisations, members) |            |                   |
All Features (dev/test)    | SQLite     | SQLite (fallback) | SQLite (fallback)
```

---

## 8. References

- **Related ADRs**:
  - [ADR-0001: Four-Stage Infrastructure Evolution](docs/adr/0001-four-stage-infrastructure-evolution.md)
  - [ADR-0002: Repository Pattern for Database Abstraction](docs/adr/0002-repository-pattern-database-abstraction.md)
  - [ADR-0003: Tiered Access Control Model](docs/adr/0003-tiered-access-control-model.md)

- **Related Specifications**:
  - [SQLite Implementation Spec](../021-storage-sqlite/spec.md)
  - [DynamoDB Implementation Spec](../022-storage-dynamodb/spec.md)
  - [PostgreSQL Implementation Spec](../023-storage-postgresql/spec.md)

- **Source Files**:
  - [`src/frank/storage/base.py`](src/frank/storage/base.py) - Interface definition
  - [`src/frank/storage/exceptions.py`](src/frank/storage/exceptions.py) - Exception hierarchy
  - [`src/frank/core/enum.py`](src/frank/core/enum.py) - AccessTier, ObservableType enums

- **Test Files**:
  - [`tests/unit/storage/test_basefrankdatabase.py`](tests/unit/storage/test_basefrankdatabase.py)

---

## 9. Open Questions & Decisions Pending

- [ ] **Return Type Consistency**: Some abstract methods declare `Dict[str, Any]` return but implementations return `Optional[Dict]` or `Submission`. Should the interface be stricter?
  - **Recommendation**: Align interface signatures with actual implementation return types
  - **Decision**: Pending code cleanup

- [ ] **API Key Methods**: The base class does not declare `create_api_key`, `get_api_key_by_hash`, etc. as abstract methods, but SQLite implements them and DynamoDB stubs them. Should they be added to the interface?
  - **Recommendation**: Remove per ADR-0005 (Cognito handles all authentication)
  - **Decision**: API key methods remain as implementation-specific, not part of the interface contract

- [ ] **Stage 4 ScyllaDB Interface**: Will the current interface accommodate ScyllaDB's distributed query patterns?
  - **Recommendation**: Validate through a spike test before Stage 4 implementation
  - **Decision**: Pending Stage 4 planning

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 2026-02-06 | 1.0 | FRANK Platform Team | Initial specification reverse-engineered from implementation |
