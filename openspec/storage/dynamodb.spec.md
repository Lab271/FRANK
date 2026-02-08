# DynamoDB Implementation Specification

**Domain:** Storage Layer / Cloud NoSQL
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06

**FRANK-Specific Metadata**:
- **Owner:** FRANK Platform Team
- **Related ADRs:** [ADR-0002](docs/adr/0002-repository-pattern-database-abstraction.md), [ADR-0003](docs/adr/0003-tiered-access-control-model.md), [ADR-0009](docs/adr/0009-postgresql-management-api.md)
- **Implementation:** [`src/frank/storage/dynamodb.py`](src/frank/storage/dynamodb.py)
- **Tests:** [tests/unit/storage/test_dynamodb.py](tests/unit/storage/test_dynamodb.py)

## Overview

The `DynamoDBFRANKDatabase` implements the `BaseFRANKDatabase` interface for **threat intelligence data** in AWS cloud deployments (Stages 2-3). It handles the high-volume, write-heavy workload of submissions, observables, sightings, and statistics using DynamoDB's single-table design pattern.

DynamoDB was chosen for threat intelligence because:

- **High Write Throughput**: Threat intelligence ingestion is write-heavy (thousands of submissions/hour)
- **Auto-Scaling**: Pay-per-request billing scales automatically with load
- **TTL**: Built-in time-to-live for automatic data expiration
- **Global Secondary Indexes**: Efficient access patterns for different query dimensions
- **Managed Service**: Zero operational overhead for infrastructure management

**Critically, this is a partial implementation.** Organisation management (CRUD), API key management, and refresh token management are explicitly **not implemented** in DynamoDB. These are handled by PostgreSQL (see [postgresql.spec.md](../storage/postgresql.spec.md)) or Cognito. This design reflects a deliberate database selection strategy: different data has different access patterns, and each database handles what it does best.


## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Usage in this specification**:
- **MUST/SHALL**: Strict requirements for correctness and compliance
- **SHOULD**: Recommended practices that may have valid exceptions
- **MAY**: Optional features or behaviors

---
## ADDED Requirements

### Requirement 1: Threat Intelligence Storage (Implemented)

- **Description**: Store complete threat intelligence submissions with nested observables, sightings, and observable statistics.
- **Acceptance Criteria**:
  - [ ] `store_submission()` stores submission, organisation, sighting, and observables atomically using batch write
  - [ ] `get_submission_by_id()` retrieves complete submission by ID
  - [ ] `query_observables()` queries observables with type, confidence, sector, and time filters
  - [ ] `search_observables_by_value()` searches observables by substring match
  - [ ] `get_statistics_summary()` returns platform-wide statistics
  - [ ] `upsert_organisation()` stores basic organisation data for threat intelligence context
  - [ ] `log_access()` writes audit log entries to a separate audit table
  - [ ] `health_check()` returns DynamoDB connection status
- **Stage Availability**: Stages 2-3
- **Related ADR**: [ADR-0002](docs/adr/0002-repository-pattern-database-abstraction.md)

### Requirement 2: Organisation CRUD (Not Implemented)

- **Description**: Organisation lifecycle management is **not implemented** in DynamoDB. All 5 methods raise `NotImplementedError` with guidance to use SQLite or PostgreSQL.
- **Rationale**: Organisation data is relational (foreign keys, joins, transactional updates) and low-volume. DynamoDB's NoSQL model is not the right fit. PostgreSQL handles this in Stage 3.
- **Methods**: `create_organisation`, `get_organisation`, `list_organisations`, `update_organisation`, `delete_organisation`
- **Stage Availability**: Not available (use PostgreSQL)
- **Related ADR**: [ADR-0009](docs/adr/0009-postgresql-management-api.md)

### Requirement 3: Organisation Members (Not Implemented)

- **Description**: User-to-organisation relationships are **not implemented** in DynamoDB. All 5 methods raise `NotImplementedError`.
- **Rationale**: Member management requires relational integrity (foreign keys, unique constraints) and transactional consistency. PostgreSQL handles this.
- **Methods**: `add_organisation_member`, `remove_organisation_member`, `get_organisation_members`, `get_user_organisations`, `get_organisation_member`
- **Stage Availability**: Not available (use PostgreSQL)

### Requirement 4: API Key Management (Not Implemented)

- **Description**: API key lifecycle is **not implemented** in DynamoDB. All 6 methods raise `NotImplementedError`.
- **Rationale**: AWS Cognito handles all authentication in Stages 2+. API keys are not needed and were never intended per [ADR-0005](docs/adr/0005-cognito-authentication.md).
- **Methods**: `create_api_key`, `get_api_key_by_hash`, `list_api_keys`, `update_api_key`, `revoke_api_key`, `update_api_key_last_used`
- **Stage Availability**: Not available (Cognito handles auth)

### Requirement 5: Refresh Token Management (Not Implemented)

- **Description**: Refresh token lifecycle is **not implemented** in DynamoDB. All 4 methods raise `NotImplementedError`.
- **Rationale**: AWS Cognito manages token lifecycle. If local revocation tracking is needed, PostgreSQL handles it.
- **Methods**: `store_refresh_token`, `get_refresh_token`, `revoke_refresh_token`, `revoke_all_user_refresh_tokens`
- **Stage Availability**: Not available (Cognito handles tokens)

---

## Non-Functional Requirements

### Performance

- **Write Latency**: Single-digit millisecond writes for individual items
- **Batch Write**: Up to 25 items per batch (DynamoDB API limit), chunked automatically
- **Query Latency**: GSI queries return in < 100ms for typical workloads
- **Scan Operations**: Used for statistics and search (less efficient, acceptable for low-frequency operations)

### Scalability

- **Billing Mode**: PAY_PER_REQUEST (auto-scales with load, no capacity planning)
- **Partition Strategy**: PK-based partitioning distributes load across DynamoDB partitions
- **No Hot Partitions**: Entity type prefixes (SUB#, OBS#, ORG#) distribute writes

### Reliability

- **Transactional Writes**: `transact_write_items` ensures atomicity within 25-item chunks
- **Retry Logic**: Automatic retry for unprocessed items in batch operations
- **Encryption**: Server-side encryption with AWS KMS (`SSEType: KMS`)
- **TTL**: Automatic data expiration (configurable per entity type)

### Security

- **Encryption at Rest**: AWS KMS server-side encryption enabled
- **IAM Authentication**: Production uses ECS Task Role (no explicit credentials)
- **LocalStack Support**: Dummy credentials for local development
- **Data Classification**: Tagged as `confidential`

---

## Data Model / Table Design

### Single-Table Design Pattern

DynamoDB uses a **single-table design** where all entity types coexist in one table, distinguished by key patterns and the `EntityType` attribute. A separate audit table handles access logs.

### Table Configuration

```json
{
    "TableName": "frank_table",
    "BillingMode": "PAY_PER_REQUEST",
    "SSESpecification": {
        "Enabled": true,
        "SSEType": "KMS"
    },
    "Tags": [
        {"Key": "Application", "Value": "FRANK"},
        {"Key": "Environment", "Value": "development"},
        {"Key": "DataClassification", "Value": "confidential"}
    ]
}
```

### Key Schema

```json
{
    "KeySchema": [
        {"AttributeName": "PK", "KeyType": "HASH"},
        {"AttributeName": "SK", "KeyType": "RANGE"}
    ],
    "AttributeDefinitions": [
        {"AttributeName": "PK", "AttributeType": "S"},
        {"AttributeName": "SK", "AttributeType": "S"},
        {"AttributeName": "GSI1PK", "AttributeType": "S"},
        {"AttributeName": "GSI1SK", "AttributeType": "S"}
    ]
}
```

### Global Secondary Index (GSI1)

```json
{
    "IndexName": "GSI1",
    "KeySchema": [
        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
        {"AttributeName": "GSI1SK", "KeyType": "RANGE"}
    ],
    "Projection": {"ProjectionType": "ALL"}
}
```

### Entity Types and Key Patterns

#### Main Table (`frank_table`)

| Entity Type | PK | SK | GSI1PK | GSI1SK | Description |
|-------------|----|----|--------|--------|-------------|
| `organisation` | `ORG#{org_id}` | `ORG` | `TIER#SUBMITTER` or `TIER#TARGET` | `{timestamp}` | Organisation metadata |
| `Submission` | `SUB#{submission_id}` | `SUB` | `ORG#{submitter_org_id}` | `{timestamp}` | Complete submission with nested JSON |
| `Sighting` | `SIGHT#{sighting_id}` | `SUB#{submission_id}` | `ORG#{submitter_org_id}` | `{timestamp}` | Sighting details |
| `ObservableIndex` | `OBS#{obs_hash}` | `SUB#{submission_id}` | `TYPE#{obs_type}` | `{timestamp}` | Observable cross-reference index |
| `STAT` (statistics) | `STAT#{obs_hash}` | `STAT#{obs_type}` | (none) | (none) | Observable aggregated statistics |

#### Audit Table (`frank_audit`)

| Entity Type | PK | SK | GSI1PK | GSI1SK | Description |
|-------------|----|----|--------|--------|-------------|
| `AccessLog` | `LOG#{org_id}` | `LOG#{timestamp}` | `ACTION#{action}` | `{timestamp}` | Audit trail entry |

### Access Patterns

| Access Pattern | Query Method | Key Condition | Index |
|---------------|-------------|---------------|-------|
| Get submission by ID | `get_item` | `PK = SUB#{id}, SK = SUB` | Table |
| Get submissions by org | `query` | `GSI1PK = ORG#{org_id}` | GSI1 |
| Get observables by type | `query` | `GSI1PK = TYPE#{type}` | GSI1 |
| Get sightings for submission | `query` | `SK = SUB#{submission_id}` | Table |
| Search observables by value | `scan` | `contains(observable_value, search)` | Table (full scan) |
| Get observable statistics | `get_item` | `PK = STAT#{hash}, SK = STAT#{type}` | Table |
| Get access logs by org | `query` | `PK = LOG#{org_id}` | Audit Table |
| Get access logs by action | `query` | `GSI1PK = ACTION#{action}` | Audit GSI1 |
| Count entities by type | `scan` | `begins_with(PK, prefix)` | Table (full scan) |

### TTL Strategy

All entities include a `TTL` attribute for automatic expiration:

| Entity Type | TTL Duration | Rationale |
|-------------|-------------|-----------|
| Submission | ~7 years (2555 days) | Long-term threat intelligence retention |
| Organisation | ~7 years (2555 days) | Organisation context needed as long as submissions exist |
| Sighting | ~7 years (2555 days) | Linked to submissions |
| ObservableIndex | ~7 years (2555 days) | Cross-reference data |
| Observable Statistics | ~7 years (2555 days) | Aggregated analytics |
| Access Logs | 90 days | Compliance-driven audit retention |

### Submission Item Structure

```python
submission_item = {
    'PK': f"SUB#{submission.submission_id}",
    'SK': 'SUB',
    'GSI1PK': f"ORG#{submission.submitter.organisation_id}",
    'GSI1SK': timestamp_str,                              # ISO format
    'EntityType': 'Submission',
    'submission_id': submission.submission_id,
    'submitter_id': submission.submitter.organisation_id,
    'access_level': submission.submitter.access_level,    # Explicit for filtering
    'submission_timestamp': timestamp_str,
    'tlp_level': submission.tlp_level,
    'submission_data': submission.model_dump(...),         # Complete Pydantic model as dict
    'processed_at': timestamp_str,
    'TTL': int((timestamp + timedelta(days=2555)).timestamp())
}
```

### Observable Index Item Structure

```python
observable_index_item = {
    'PK': f"OBS#{obs_hash}",
    'SK': f"SUB#{submission.submission_id}",
    'GSI1PK': f"TYPE#{obs_type}",
    'GSI1SK': timestamp_str,
    'EntityType': 'ObservableIndex',
    'observable_hash': obs_hash,
    'observable_type': obs_type,
    'observable_value': obs_value,
    'submission_id': submission.submission_id,
    'submitter_id': submission.submitter.organisation_id,
    'sighting_id': sighting.sighting_id,
    'confidence': sighting.confidence,
    'severity': sighting.severity,
    'role': obs.get('role'),
    'port': obs.get('port'),
    'first_seen': obs.get('first_seen', timestamp).isoformat(),
    'timestamp': timestamp_str,
    'TTL': int((timestamp + timedelta(days=2555)).timestamp())
}
```

### Observable Statistics Item Structure

```python
stat_item = {
    'PK': f'STAT#{obs_hash}',
    'SK': f'STAT#{obs_type}',
    'observable_hash': obs_hash,
    'observable_type': obs_type,
    'observable_value': obs_value,
    'first_seen': timestamp_str,
    'last_seen': timestamp_str,
    'hit_targets': list_of_target_org_ids,   # Set of affected organisations
    'sectors': list_of_affected_sectors,      # Set of affected sectors
    'total_hits': 1,                          # Incremented on each sighting
    'TTL': int(expiry_timestamp)
}
```

### DynamoDB-Specific Data Handling

#### Float to Decimal Conversion

DynamoDB does not support Python `float` types. All float values must be converted to `Decimal` before writing and back to `float` after reading:

```python
def _convert_floats_to_decimal(self, obj: Any) -> Any:
    """Convert float values to Decimal for DynamoDB compatibility."""

def _convert_decimals_to_float(self, obj: Any) -> Any:
    """Convert Decimal values back to float for JSON serialization."""
```

#### Batch Write with Chunking

DynamoDB limits batch operations to 25 items. The `_batch_write_items()` method:

1. Chunks items into groups of 25
2. Uses `transact_write_items` for atomic writes within each chunk
3. Retries unprocessed items automatically
4. Raises `FRANKStorageError` on persistent failure

### Connection Configuration

```python
connection_params = {
    "DYNAMODB_TABLE": "frank_table",          # Main data table
    "DYNAMODB_AUDIT_TABLE": "frank_audit",    # Audit log table
    "ENDPOINT": "http://localstack:4566",     # LocalStack endpoint (None for AWS)
    "AWS_ACCESS_KEY_ID": "test",              # Credentials (or IAM role)
    "AWS_SECRET_ACCESS_KEY": "test",
    "AWS_DEFAULT_REGION": "eu-west-1"
}
```

### Credential Resolution

1. **LocalStack** (endpoint provided): Uses explicit credentials (can be dummy)
2. **AWS with explicit credentials** (no endpoint, real key_id): Uses provided credentials
3. **AWS with IAM role** (no endpoint, no/test key_id): Uses default AWS credential chain (ECS Task Role, EC2 Instance Profile, environment variables)

### Factory Function

```python
def create_dynamodb_database(
    table_name: str = "frank_table",
    audit_table_name: str = "frank_audit",
    region: str = "eu-west-1",
    endpoint: str = "http://localstack:4566",
    aws_access_key_id: str = "test",
    aws_secret_access_key: str = "test",
    logger: Optional[logging.Logger] = None
) -> DynamoDBFRANKDatabase:
```

---

## Implementation Status Matrix

### Implemented Methods (9 methods)

| Method | Status | Notes |
|--------|--------|-------|
| `initialize()` | Implemented | Creates tables + GSI + TTL |
| `store_submission()` | Implemented | Batch atomic write of all entities |
| `get_submission_by_id()` | Implemented | Direct get_item lookup |
| `query_observables()` | Implemented | GSI query + filters + deduplication |
| `search_observables_by_value()` | Implemented | Table scan with contains filter |
| `get_statistics_summary()` | Implemented | Multiple scans + GSI queries per type |
| `upsert_organisation()` | Implemented | Simple put_item for org context |
| `log_access()` | Implemented | Writes to separate audit table |
| `health_check()` | Implemented | Returns table name + region |

### NotImplementedError Methods (20 methods)

#### Organisation CRUD (5 methods) -- Use PostgreSQL

| Method | Error Message |
|--------|---------------|
| `create_organisation()` | "DynamoDB organisation CRUD not yet implemented. Use SQLite." |
| `get_organisation()` | "DynamoDB organisation CRUD not yet implemented. Use SQLite." |
| `list_organisations()` | "DynamoDB organisation CRUD not yet implemented. Use SQLite." |
| `update_organisation()` | "DynamoDB organisation CRUD not yet implemented. Use SQLite." |
| `delete_organisation()` | "DynamoDB organisation CRUD not yet implemented. Use SQLite." |

#### Organisation Members (5 methods) -- Use PostgreSQL

| Method | Error Message |
|--------|---------------|
| `add_organisation_member()` | "DynamoDB organisation CRUD not yet implemented. Use SQLite." |
| `remove_organisation_member()` | "DynamoDB organisation CRUD not yet implemented. Use SQLite." |
| `get_organisation_members()` | "DynamoDB organisation CRUD not yet implemented. Use SQLite." |
| `get_user_organisations()` | "DynamoDB organisation CRUD not yet implemented. Use SQLite." |
| `get_organisation_member()` | "DynamoDB organisation CRUD not yet implemented. Use SQLite." |

#### API Key Management (6 methods) -- Cognito handles auth

| Method | Error Message |
|--------|---------------|
| `create_api_key()` | "DynamoDB API key management not yet implemented. Use SQLite." |
| `get_api_key_by_hash()` | "DynamoDB API key management not yet implemented. Use SQLite." |
| `list_api_keys()` | "DynamoDB API key management not yet implemented. Use SQLite." |
| `update_api_key()` | "DynamoDB API key management not yet implemented. Use SQLite." |
| `revoke_api_key()` | "DynamoDB API key management not yet implemented. Use SQLite." |
| `update_api_key_last_used()` | "DynamoDB API key management not yet implemented. Use SQLite." |

#### Refresh Token Management (4 methods) -- Cognito handles tokens

| Method | Error Message |
|--------|---------------|
| `store_refresh_token()` | "DynamoDB refresh token management not yet implemented. Use SQLite." |
| `get_refresh_token()` | "DynamoDB refresh token management not yet implemented. Use SQLite." |
| `revoke_refresh_token()` | "DynamoDB refresh token management not yet implemented. Use SQLite." |
| `revoke_all_user_refresh_tokens()` | "DynamoDB refresh token management not yet implemented. Use SQLite." |

---

## Test Coverage Requirements

### Unit Tests

**Location**: `tests/unit/storage/test_dynamodb.py`

**Required Unit Test Coverage**:
- [ ] Table creation and GSI setup (with mocked DynamoDB/LocalStack)
- [ ] Submission storage (batch write with correct key patterns)
- [ ] Observable extraction and indexing
- [ ] Observable statistics upsert (new + update)
- [ ] Query observables with type filter (GSI query)
- [ ] Query observables without type filter (scan)
- [ ] Search observables by value (scan with contains)
- [ ] Statistics summary computation
- [ ] Access logging to audit table
- [ ] Health check response structure
- [ ] Float/Decimal conversion
- [ ] Batch write chunking (>25 items)
- [ ] NotImplementedError for all 20 unimplemented methods
- [ ] Credential resolution (LocalStack vs AWS vs IAM role)

**Coverage Target**: >= 85% code coverage

### Integration Tests

**Location**: `tests/integration/`, `tests/spikes/006_dynamodb/`, `tests/spikes/012_aws_dynamodb/`

**Required Integration Test Scenarios**:
- [ ] End-to-end submission storage and retrieval against LocalStack
- [ ] Observable deduplication across multiple submissions
- [ ] TTL attribute presence on all items
- [ ] GSI query patterns return expected results

---

## 7. Evolution Path Across FRANK Stages

### Stage 1: SQLite + FastAPI (Local Development)

- **Status**: Not used (SQLite handles everything)
- **DynamoDB is not needed for local development**

### Stage 2: DynamoDB + Docker (Learning Stage)

- **Status**: Partially implemented (threat intelligence only)
- **Environment**: LocalStack in Docker simulates DynamoDB
- **Learning Goal**: Validate DynamoDB access patterns, single-table design, GSI queries
- **Organisation Data**: Falls back to SQLite
- **Key Achievement**: Proved that the repository pattern works across SQL and NoSQL

### Stage 3: AWS ECS + DynamoDB + PostgreSQL (Cloud Deployment)

- **Status**: Production deployment
- **Threat Intelligence**: DynamoDB handles all submissions, observables, sightings
- **Management Data**: PostgreSQL handles organisations, members (not DynamoDB)
- **Auto-Scaling**: Pay-per-request billing handles variable load
- **Multi-AZ**: DynamoDB automatically replicates across availability zones
- **Monitoring**: CloudWatch metrics for read/write capacity, throttling, latency

### Stage 4: Kubernetes + ScyllaDB (Production Scale)

- **Status**: Not yet implemented
- **Future**: DynamoDB may be replaced by ScyllaDB for cloud-agnostic deployment
- **Migration Path**: Same interface, new `ScyllaDBFRANKDatabase` implementation

### Trade-offs

| Aspect | DynamoDB Advantage | DynamoDB Limitation |
|--------|-------------------|---------------------|
| **Write Throughput** | Single-digit ms latency | 400KB item size limit |
| **Scaling** | Automatic, no capacity planning | Pay-per-request can be expensive at very high volume |
| **Query Flexibility** | Efficient for designed access patterns | Poor for ad-hoc queries (scan required) |
| **Consistency** | Eventual consistency (default) | Strong consistency available at 2x read cost |
| **Transactions** | TransactWriteItems for atomicity | Limited to 25 items per transaction |
| **Relational Data** | Not suitable | No foreign keys, joins, or constraints |
| **Schema Evolution** | Schema-free (add attributes anytime) | No schema enforcement (application must validate) |
| **Cost** | Pay-per-request scales to zero | GSI updates count as additional writes |

---

## 8. References

- **Related ADRs**:
  - [ADR-0002: Repository Pattern for Database Abstraction](docs/adr/0002-repository-pattern-database-abstraction.md)
  - [ADR-0003: Tiered Access Control Model](docs/adr/0003-tiered-access-control-model.md)
  - [ADR-0005: Cognito Authentication](docs/adr/0005-cognito-authentication.md)
  - [ADR-0009: PostgreSQL for Management API](docs/adr/0009-postgresql-management-api.md)

- **Related Specifications**:
  - [Base Interface Spec](../storage/base-interface.spec.md) -- interface this implements
  - [SQLite Implementation Spec](../storage/sqlite.spec.md) -- complete reference implementation
  - [PostgreSQL Implementation Spec](../storage/postgresql.spec.md) -- management data complement

- **Source Files**:
  - [`src/frank/storage/dynamodb.py`](src/frank/storage/dynamodb.py) -- Implementation
  - [`src/frank/storage/base.py`](src/frank/storage/base.py) -- Interface

- **Test Files**:
  - [`tests/unit/storage/test_dynamodb.py`](tests/unit/storage/test_dynamodb.py)

- **Related Spikes**:
  - [`tests/spikes/006_dynamodb/README.md`](tests/spikes/006_dynamodb/README.md) -- DynamoDB integration spike
  - [`tests/spikes/012_aws_dynamodb/README.md`](tests/spikes/012_aws_dynamodb/README.md) -- AWS DynamoDB table design

- **External References**:
  - [DynamoDB Single-Table Design](https://www.alexdebrie.com/posts/dynamodb-single-table/)
  - [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
  - [DynamoDB TransactWriteItems](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html)

---

## 9. Open Questions & Decisions Pending

- [ ] **Statistics Summary Performance**: `get_statistics_summary()` performs multiple table scans and per-type GSI queries. At scale, this could be slow and expensive.
  - **Options**: Pre-compute statistics periodically; use DynamoDB Streams for real-time aggregation; cache results
  - **Recommendation**: Add caching layer or pre-compute on write
  - **Decision**: Pending -- acceptable for current data volumes

- [ ] **Search by Value (Scan)**: `search_observables_by_value()` uses a full table scan with `contains()` filter. This is O(n) and does not scale.
  - **Options**: ElasticSearch/OpenSearch for full-text search; additional GSI on value prefixes; accept scan limitation
  - **Recommendation**: Accept for now; add OpenSearch in Stage 4 if needed
  - **Decision**: Pending -- acceptable for current workloads

- [ ] **Error Messages Reference SQLite**: The `NotImplementedError` messages say "Use SQLite" but in Stage 3 production, the correct fallback is PostgreSQL.
  - **Recommendation**: Update error messages to reference PostgreSQL for org-related methods
  - **Decision**: Pending code cleanup

- [ ] **TTL Duration**: All entities use ~7 years (2555 days). Should different entity types have different retention policies?
  - **Recommendation**: Define a retention policy per entity type, especially for access logs (currently 90 days) vs threat data
  - **Decision**: Access logs use 90 days; threat data uses 2555 days. Formalize in a retention policy document.

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 2026-02-06 | 1.0 | FRANK Platform Team | Initial specification reverse-engineered from implementation |
