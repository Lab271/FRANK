# Design Document: [Feature Name]

⭐ **Required sections marked with star**

- **Status:** ⭐ DRAFT | REVIEW | APPROVED | IMPLEMENTED | SUPERSEDED
- **Version:** 1.0
- **Last Updated:** YYYY-MM-DD
- **Owner:** ⭐ [Name or Team]
- **Related Specification:** [spec.md](spec.md)
- **Issue:** ⭐ #XXX

---

## Overview

⭐ **How will we build this?** This document defines the **how** and implementation approach.

The companion documents:
- **[proposal.md](proposal.md)**: Why we need this change
- **[spec.md](spec.md)**: What we must do and how well
- **[tasks.md](tasks.md)**: Step-by-step implementation
- **[adr.md](adr.md)**: Architectural decisions

This design answers:
- **What's the overall approach?** (Architecture overview)
- **How do components interact?** (Data flow, dependencies)
- **What alternatives did we consider?** (Trade-offs, rationale)
- **What's the implementation strategy?** (Phased approach, stages)
- **How do we handle edge cases?** (Error handling, failure modes)

---

## 1. Architecture Overview

⭐ **High-level system design** showing how components fit together.

### System Context Diagram

```
┌─────────────────────────────────────────────────────────┐
│ External Systems                                         │
├─────────────────────────────────────────────────────────┤
│  AWS Cognito (Auth)  │  DynamoDB (DB)  │  CloudWatch    │
└──────────┬───────────────────┬──────────────────┬────────┘
           │                   │                  │
           ▼                   ▼                  ▼
    ┌──────────────────────────────────────────────────┐
    │ FastAPI Application (Sightings API)              │
    │ ┌────────────────────────────────────────────┐   │
    │ │ Router: /api/v1/sightings                  │   │
    │ │ - GET (query sightings)                    │   │
    │ │ - POST (create sighting)                   │   │
    │ │ - PUT/{id} (update sighting)               │   │
    │ │ - DELETE/{id} (delete sighting)            │   │
    │ └────────────────────────────────────────────┘   │
    │ ┌────────────────────────────────────────────┐   │
    │ │ Middleware                                 │   │
    │ │ - Authentication (validate JWT)            │   │
    │ │ - Authorization (access tier checks)       │   │
    │ │ - Logging (request/response tracing)       │   │
    │ └────────────────────────────────────────────┘   │
    │ ┌────────────────────────────────────────────┐   │
    │ │ Business Logic                             │   │
    │ │ - SightingService (create, query, delete)  │   │
    │ │ - AccessControl (tier filtering)           │   │
    │ └────────────────────────────────────────────┘   │
    │ ┌────────────────────────────────────────────┐   │
    │ │ Data Layer (Repository Pattern)            │   │
    │ │ - BaseFRANKDatabase (abstract interface)   │   │
    │ │ - SQLiteDatabase (Stage 1)                 │   │
    │ │ - DynamoDBDatabase (Stages 2-4)            │   │
    │ └────────────────────────────────────────────┘   │
    └──────────────────────────────────────────────────┘
           │                   │                  │
           ▼                   ▼                  ▼
    ┌──────────────────────────────────────────────────┐
    │ Data Stores                                      │
    │ - SQLite (Stage 1: laptop development)          │
    │ - DynamoDB (Stages 2-4: AWS cloud)              │
    └──────────────────────────────────────────────────┘
```

### Key Components

**FastAPI Router** (`src/frank/apis/sightings.py`):
- Entry point for API requests
- Route handlers: GET /sightings, POST /sightings, PUT /sightings/{id}, DELETE /sightings/{id}
- Request validation using Pydantic models
- Response serialization

**Authentication Middleware** (Cognito integration per [ADR-0005](../../../docs/adr/0005-cognito-authentication.md)):
- Validate JWT tokens from AWS Cognito
- Extract user context (org_id, access_tier, etc.)
- Inject context into request for downstream use

**Authorization Layer** (Access control per [ADR-0003](../../../docs/adr/0003-tiered-access-control-model.md)):
- Check access tier before operations (OBSERVER, CONTRIBUTOR, PARTNER, CORE_MEMBER)
- Filter results based on organization and access tier
- Enforce row-level security

**SightingService** (`src/frank/core/sighting_service.py`):
- Business logic for sighting operations
- Query building and filtering
- Audit logging
- Error handling and validation

**Repository Pattern** (`src/frank/storage/base.py` + implementations):
- Abstract database interface (BaseFRANKDatabase)
- Concrete implementations (SQLiteDatabase, DynamoDBDatabase)
- Ensures identical behavior across storage backends
- Handles stage-specific optimizations

---

## 2. Data Flow Diagrams

⭐ **How data moves through the system** for key operations.

### Flow: Create Sighting

```
User Request
    │
    ▼
POST /api/v1/sightings
{
  "observable_id": "observable--...",
  "observed_at": "2026-02-06T14:30:00Z",
  "confidence": 95,
  "details": {...}
}
    │
    ▼
FastAPI Route Handler (sightings_router.create_sighting)
    ├─ Parse request JSON into SightingCreateRequest
    ├─ Extract JWT token from Authorization header
    ▼
Authentication Middleware
    ├─ Validate JWT with AWS Cognito
    ├─ Extract user_id, org_id, access_tier
    ├─ Inject context into request
    ▼
Authorization Check
    ├─ Verify user has CONTRIBUTOR+ tier
    ├─ Verify user is in submitting organization
    ├─ Return 403 Forbidden if check fails
    ▼
SightingService.create_sighting()
    ├─ Generate sighting ID (sighting--{uuid})
    ├─ Set created_at = now(), created_by = user_id
    ├─ Build Sighting object
    ├─ Validate against Pydantic model
    ├─ Set access_tier from user context
    ▼
Repository.store_sighting(sighting)
    │
    ├─ SQLite (Stage 1)
    │   ├─ Execute INSERT INTO sightings (...)
    │   ├─ Commit transaction
    │   ▼
    │
    └─ DynamoDB (Stages 2-4)
        ├─ PUT item to sightings table
        ├─ Sighting becomes available immediately
        ▼
Response Builder
    ├─ Serialize Sighting to JSON
    ├─ Set Location header: /api/v1/sightings/{id}
    ├─ Set status code: 201 Created
    ▼
User Response
{
  "id": "sighting--f0d4c9ac-...",
  "observable_id": "observable--...",
  "observed_at": "2026-02-06T14:30:00Z",
  "confidence": 95,
  "details": {...},
  "created_at": "2026-02-06T14:32:15Z",
  "created_by": "analyst@acme.corp",
  "access_tier": "CONTRIBUTOR"
}
HTTP 201 Created
Location: /api/v1/sightings/sighting--f0d4c9ac-...
```

### Flow: Query Sightings with Filtering

```
User Request
    │
    ▼
GET /api/v1/sightings?observable_id=observable--...&min_confidence=80
    │
    ▼
Authentication & Authorization (same as create)
    ▼
SightingService.query_sightings(filters, user_context)
    ├─ Build query: observable_id=?, confidence >= ?
    ├─ Add access tier filtering:
    │   ├─ OBSERVER: only PUBLIC sightings
    │   ├─ CONTRIBUTOR: PUBLIC + OBSERVER from org
    │   ├─ PARTNER: above + partner org sightings
    │   ├─ CORE_MEMBER: all sightings
    │
    ▼
Repository.query_sightings(query_params)
    │
    ├─ SQLite (Stage 1)
    │   ├─ SELECT * FROM sightings
    │   ├─ WHERE observable_id=? AND confidence >= ? AND access_tier IN (...)
    │   ├─ ORDER BY observed_at DESC
    │   ├─ LIMIT 100 (pagination)
    │   ▼
    │
    └─ DynamoDB (Stages 2-4)
        ├─ Query on observable_id index
        ├─ Filter by confidence, access_tier
        ├─ Apply pagination token
        ▼
Result Processing
    ├─ Count total results (for total_count field)
    ├─ Generate pagination token if more results exist
    ├─ Apply field-level access filtering (some fields restricted by tier)
    ├─ Serialize to JSON
    ▼
User Response
{
  "sightings": [...],
  "total_count": 42,
  "returned_count": 50,
  "next_page_token": "eyJvZmZzZXQiOiA1MH0=",
  "query_time_ms": 125
}
HTTP 200 OK
```

---

## 3. Implementation Strategy

⭐ **How we'll build and test this** across FRANK's evolutionary stages.

### Stage 1: SQLite + FastAPI (Weeks 1-2)

**Goal**: Proof of concept with rapid feedback loop

**Implementation**:
1. FastAPI router + endpoints
2. Pydantic models for request/response
3. SQLiteDatabase implementation (extend existing repository)
4. Authentication with mock tokens (before Cognito integration)
5. Unit tests and integration tests
6. Documentation

**Database Schema**:
```sql
CREATE TABLE sightings (
    id TEXT PRIMARY KEY,
    observable_id TEXT NOT NULL,
    observed_at DATETIME NOT NULL,
    reporter_organization TEXT NOT NULL,
    confidence INTEGER NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    details JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL,
    access_tier TEXT DEFAULT 'CONTRIBUTOR',
    FOREIGN KEY (observable_id) REFERENCES observables(id),
    INDEX idx_observable_id (observable_id),
    INDEX idx_observed_at (observed_at),
    INDEX idx_created_by (created_by)
);
```

**Key Decisions**:
- Use FastAPI dependency injection for authentication context
- Implement access filtering in SightingService, not SQL
- Store access_tier with each sighting (denormalization for performance)

### Stage 2: DynamoDB + LocalStack (Week 3, local testing only)

**Goal**: Validate DynamoDB access patterns and performance

**Implementation**:
1. DynamoDBDatabase implementation (extend existing repository)
2. Table design with optimal indexes for query patterns
3. Performance testing with realistic data volumes
4. LocalStack for local development/testing

**DynamoDB Table Design**:
```
Table: frank-sightings (Stage 2-4)
├─ Partition Key: observable_id (query most common operation)
├─ Sort Key: observed_at (order results by date)
├─ Global Secondary Index 1:
│   ├─ Partition Key: reporter_organization
│   ├─ Sort Key: observed_at
│   └─ Projection: ALL
├─ Global Secondary Index 2:
│   ├─ Partition Key: created_by
│   ├─ Sort Key: created_at
│   └─ Projection: ALL
└─ TTL: None (threat data retained indefinitely)

Attributes:
- id (PK from sighting--uuid)
- observable_id (String, Partition Key)
- observed_at (ISO 8601 String, Sort Key)
- reporter_organization (String)
- confidence (Number)
- details (Map)
- created_at (String, ISO 8601)
- created_by (String)
- access_tier (String, for filtering)
```

**Key Decisions**:
- Use observable_id as partition key (most common query)
- Store ISO 8601 strings, not timestamps (DynamoDB limitation)
- Implement access filtering in application layer, not DynamoDB filters
- Plan for pagination with ExclusiveStartKey

### Stage 3: AWS ECS + DynamoDB (Weeks 4-5, production)

**Goal**: Production-grade deployment with auto-scaling and monitoring

**Implementation**:
1. Use Stage 2 DynamoDB implementation without changes
2. CloudFormation template for DynamoDB tables
3. ECS Fargate task definition for API
4. Application Load Balancer with target groups
5. CloudWatch monitoring and logging
6. Auto-scaling based on CPU/memory/request rate

**Deployment Architecture**:
```
Internet
    │
    ▼
Route 53 (DNS)
    │
    ▼
Application Load Balancer (ALB)
├─ Public subnet (multi-AZ)
├─ HTTPS listener on port 443
├─ HTTP → HTTPS redirect
    │
    ▼
Target Group
├─ ECS service: frank-api
├─ Task count: 2-10 (auto-scaling)
├─ Health check: /api/v1/health
    │
    ▼
ECS Fargate Tasks (Private subnet)
├─ Container: frank-api:latest (ECR)
├─ CPU: 512 millicores
├─ Memory: 1024 MB
├─ Environment: DynamoDB_TABLE=frank-sightings
├─ Secrets: COGNITO_CLIENT_ID, etc. (AWS Secrets Manager)
    │
    ▼
DynamoDB (Multi-AZ, auto-scaling)
├─ On-demand pricing or provisioned capacity
├─ Point-in-time recovery enabled
├─ CloudWatch monitoring
```

**Key Decisions**:
- Use auto-scaling based on request rate and latency (not just CPU/memory)
- DynamoDB on-demand pricing for variable traffic
- CloudWatch for centralized logging and metrics

### Stage 4: Kubernetes + ScyllaDB (Future, not in MVP)

**Goal**: Cloud-agnostic, petabyte-scale deployment

**Implementation**:
1. Migrate to ScyllaDB (drop-in Cassandra replacement)
2. Kubernetes manifests and Helm charts
3. Pod autoscaling based on threat data volume
4. Service mesh (Istio) for advanced traffic management
5. Multi-region replication

---

## 4. Alternative Approaches Considered

⭐ **What other designs did we evaluate?** Document trade-offs and rationale.

### Alternative 1: Server-Side Filtering

**Approach**: Let database handle all filtering (WHERE clauses)

**Pros**:
- ✅ Filters data at source (efficient for large datasets)
- ✅ Simpler application code

**Cons**:
- ❌ Access tier logic complex in SQL (cross-table joins)
- ❌ Dynamic WHERE clauses prone to SQL injection
- ❌ SQLite + DynamoDB have different SQL capabilities
- ❌ Hard to test (integration tests required for every combination)

**Verdict**: Rejected - access control implemented in application layer per ADR-0003

### Alternative 2: Cache Frequently-Queried Sightings

**Approach**: Use Redis to cache popular queries (observable_id, date ranges)

**Pros**:
- ✅ Dramatically faster queries for hot data
- ✅ Reduces database load

**Cons**:
- ⚠️ Cache invalidation complexity (sighting updates, deletes)
- ⚠️ Stale data for fast-moving threat intelligence
- ⚠️ Additional infrastructure to maintain
- ⚠️ Complicates Stage 1 (SQLite only, no Redis)

**Verdict**: Deferred - implement if performance testing shows need (not in MVP)

### Alternative 3: Event-Driven Architecture

**Approach**: Emit Kafka events for sighting creation, downstream processors update analytics

**Pros**:
- ✅ Decouples sighting creation from analytics
- ✅ Enables real-time notifications

**Cons**:
- ❌ Major architectural complexity
- ❌ Kafka unavailable in Stage 1 (SQLite only)
- ❌ Async processing delays notifications
- ❌ Learning curve for team

**Verdict**: Rejected for MVP - implement after MVP with solid foundation

### Alternative 4: GraphQL API instead of REST

**Approach**: Full GraphQL for flexible querying

**Pros**:
- ✅ Clients request only needed fields
- ✅ Single endpoint for all queries

**Cons**:
- ❌ More complex implementation
- ❌ Team has no GraphQL experience
- ❌ Inconsistent with existing Spike 007 (FastAPI/REST patterns)
- ❌ Harder to debug for API consumers

**Verdict**: Rejected - stick with REST, consider GraphQL in future phase

### Recommended Approach

**REST API with Repository Pattern**

**Rationale**:
- ✅ Consistent with existing patterns (Spike 007, ADR-0002)
- ✅ Simple, proven technology stack
- ✅ Works identically across all stages
- ✅ Team comfortable with REST design
- ✅ Standard industry approach for threat intelligence APIs

---

## 5. Implementation Approach by Component

⭐ **Detailed design for each major component**

### FastAPI Router Design

**Location**: `src/frank/apis/sightings.py`

**Structure**:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from frank.core.models import Sighting, SightingCreateRequest
from frank.core.sighting_service import SightingService
from frank.util.auth import get_current_user

router = APIRouter(prefix="/api/v1/sightings", tags=["sightings"])

@router.get("")
async def query_sightings(
    observable_id: Optional[str] = None,
    min_date: Optional[datetime] = None,
    max_date: Optional[datetime] = None,
    min_confidence: Optional[int] = None,
    reporter_org: Optional[str] = None,
    limit: int = 100,
    page_token: Optional[str] = None,
    current_user = Depends(get_current_user),
):
    """Query sightings with optional filters."""
    service = SightingService(db)
    results = service.query(
        observable_id=observable_id,
        min_date=min_date,
        max_date=max_date,
        min_confidence=min_confidence,
        reporter_org=reporter_org,
        user_context=current_user,
        limit=limit,
        page_token=page_token,
    )
    return results

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_sighting(
    sighting: SightingCreateRequest,
    current_user = Depends(get_current_user),
):
    """Create a new sighting."""
    service = SightingService(db)
    created = service.create(sighting, user_context=current_user)
    return created
```

**Key Patterns**:
- Use FastAPI dependency injection for authentication
- Minimal business logic in router (delegate to Service)
- Consistent error handling returning HTTPException
- Status codes per HTTP standards (201 for create, 200 for get, 204 for delete)

### SightingService Design

**Location**: `src/frank/core/sighting_service.py`

**Responsibilities**:
- Business logic for sighting operations
- Access control enforcement
- Input validation and error handling
- Audit logging
- Pagination and filtering

**Structure**:
```python
class SightingService:
    def __init__(self, db: BaseFRANKDatabase):
        self.db = db

    def create(self, sighting_data: SightingCreateRequest, user_context: UserContext) -> Sighting:
        """Create new sighting."""
        # 1. Validate user has permission
        if not self._can_create(user_context):
            raise PermissionError("Insufficient access tier")

        # 2. Build sighting object
        sighting = Sighting.from_create_request(
            sighting_data,
            created_by=user_context.user_id,
            access_tier=user_context.access_tier,
        )

        # 3. Store in database
        self.db.store_sighting(sighting)

        # 4. Audit log
        self._log_audit("sighting_created", sighting.id, user_context)

        return sighting

    def query(self, filters: Dict, user_context: UserContext) -> SightingsQueryResponse:
        """Query sightings with filtering."""
        # 1. Build database query
        db_results = self.db.query_sightings(**filters)

        # 2. Filter by access tier (application layer)
        filtered_results = self._apply_access_filter(db_results, user_context)

        # 3. Build response with pagination
        response = SightingsQueryResponse(
            sightings=filtered_results[:limit],
            total_count=len(db_results),  # Before pagination
            returned_count=len(filtered_results[:limit]),
            next_page_token=self._generate_page_token(...),
        )

        return response
```

### Access Control Design

**Location**: `src/frank/util/access_control.py`

**Principle**: Implement access filtering in application layer, not database queries

**Reasoning**:
- Same access logic across SQLite, DynamoDB, PostgreSQL
- Easier to test (mock database, test access logic independently)
- Follows "forgiving input, strong output" (ADR-0007) - filter results
- Supports complex rules (partnerships, exceptions) without database complexity

**Implementation**:
```python
class AccessControl:
    @staticmethod
    def can_read_sighting(sighting: Sighting, user_context: UserContext) -> bool:
        """Check if user can read this sighting."""
        # Rule 1: Users from same organization
        if sighting.reporter_organization == user_context.org_id:
            # Organization members can see own org's sightings at their tier
            return True

        # Rule 2: Public sightings available to all
        if sighting.access_tier == AccessTier.PUBLIC:
            return True

        # Rule 3: Access tier rules
        match user_context.access_tier:
            case AccessTier.OBSERVER:
                return False  # Only PUBLIC
            case AccessTier.CONTRIBUTOR:
                # Can see PUBLIC + OBSERVER from org
                return sighting.access_tier in [AccessTier.PUBLIC, AccessTier.OBSERVER]
            case AccessTier.PARTNER:
                # Can see PUBLIC + OBSERVER + PARTNER (from partner orgs)
                return sighting.access_tier != AccessTier.CORE_MEMBER
            case AccessTier.CORE_MEMBER:
                return True  # Admins see all

        return False
```

---

## 6. Error Handling Strategy

⭐ **How we handle failures and edge cases**

### Error Categories

**Input Validation Errors** (400 Bad Request):
- Invalid field format (e.g., confidence not integer)
- Out-of-range values (e.g., confidence > 100)
- Missing required fields
- Invalid date formats

**Authentication Errors** (401 Unauthorized):
- Missing Authorization header
- Expired or invalid JWT token
- Malformed token

**Authorization Errors** (403 Forbidden):
- Insufficient access tier
- User not in organization
- Cross-organization access attempts

**Resource Not Found** (404 Not Found):
- Sighting ID doesn't exist
- Observable doesn't exist (for queries)

**Conflict/Constraint Errors** (409 Conflict):
- Duplicate sighting (same observable + time)
- Observable archived or deleted

**Server Errors** (500 Internal Server Error):
- Database connection failures
- Unexpected exceptions
- Third-party service failures (Cognito, CloudWatch)

### Error Response Format

Per [ADR-0008 (Explicit Error Communication)](../../../docs/adr/0008-explicit-error-communication.md):

```json
{
  "error": {
    "type": "validation_error",
    "message": "One or more validation errors occurred",
    "correlation_id": "req-abc123def456",
    "details": [
      {
        "field": "confidence",
        "message": "Must be between 0 and 100",
        "value": 150
      }
    ]
  }
}
```

### Handling Database Failures

**SQLite (Stage 1)**:
- Automatic retry on SQLITE_BUSY (database locked)
- Transaction rollback on failure
- Clear error message to user

**DynamoDB (Stages 2-4)**:
- Exponential backoff for throttling
- Circuit breaker after N failures (prevent cascading failures)
- CloudWatch alarms for persistent failures

---

## 7. Testing Strategy

⭐ **How we validate this works correctly**

### Unit Tests

**Location**: `tests/unit/apis/test_sightings_api.py`, `tests/unit/core/test_sighting_service.py`

**Approach**:
- Mock database (FakeDatabase for testing)
- Mock Cognito authentication
- Test each endpoint and business logic function
- Fast execution (< 100ms per test)

**Coverage**: ≥85% per ADR-0012

### Integration Tests

**Location**: `tests/integration/sightings_api.feature`

**Approach**:
- BDD/Behave scenarios describing real workflows
- Use actual SQLite database for testing
- Test against TestClient (FastAPI's test client)

**Example Scenarios**:
```gherkin
Feature: Sightings API

  Scenario: User submits and queries sightings
    Given an authenticated analyst
    And a known malicious IP observable
    When the analyst submits a sighting
    Then the sighting is created
    When the analyst queries sightings for that observable
    Then the sighting appears in results
```

### Spike/Validation Tests

**Location**: `tests/spikes/XXX_sightings_api_performance_test.py`

**Approach**:
- Performance testing under load
- Stress testing with concurrent submissions
- Database scaling tests

**Tests**:
- Query latency: Verify < 200ms for typical queries
- Throughput: Verify 1000+ submissions/second
- Concurrency: Verify thread safety
- Pagination: Verify handling of large result sets

---

## 8. Deployment Strategy

⭐ **How we deploy this to production**

### Stage 1 → Stage 2 (Local to LocalStack)

**Steps**:
1. No code changes (same FastAPI + Pydantic models)
2. Change database implementation: SQLiteDatabase → DynamoDBDatabase
3. Point to LocalStack DynamoDB instead of SQLite file
4. Run integration tests (identical to Stage 1)

**Rollback**: Switch back to SQLite database implementation

### Stage 2 → Stage 3 (LocalStack to AWS)

**Steps**:
1. Create DynamoDB tables in AWS (CloudFormation)
2. Create RDS PostgreSQL for management API
3. Build Docker image with API code
4. Push to ECR (AWS Elastic Container Registry)
5. Create ECS service and Fargate tasks
6. Configure ALB and Route 53
7. Deploy via Ansible playbook (existing infrastructure)
8. Run smoke tests against /api/v1/health

**Rollback**: Switch ECS service to previous Docker image version

### Blue-Green Deployments (Recommended)

```
Current State (Blue)
    ├─ ECS Service: frank-api:v1.0.0 (2 tasks)
    ├─ ALB Target Group: blue-targets

New Deployment (Green)
    ├─ ECS Service: frank-api:v1.1.0 (2 tasks, starting)
    ├─ ALB Target Group: green-targets

Cutover:
    ├─ Run smoke tests against green
    ├─ Gradually shift traffic: 10% → 50% → 100%
    ├─ Monitor metrics (latency, errors)
    ├─ If issues: revert to blue (instant)
```

---

## 9. Monitoring & Observability

⭐ **How we know if this is working**

### CloudWatch Metrics

**Application Metrics**:
- `api.sightings.create.latency` - Time to create sighting
- `api.sightings.query.latency` - Time to query sightings
- `api.sightings.errors` - Error count by error type
- `api.sightings.throughput` - Requests per second

**Infrastructure Metrics**:
- ECS CPU utilization
- ECS memory utilization
- DynamoDB consumed capacity units
- ALB response time

### CloudWatch Logs

**Structure**:
```json
{
  "timestamp": "2026-02-06T14:32:15.123Z",
  "level": "INFO",
  "request_id": "req-abc123def456",
  "user_id": "analyst@acme.corp",
  "action": "create_sighting",
  "observable_id": "observable--d8f0eae0-...",
  "duration_ms": 45,
  "result": "success"
}
```

### Alarms

**Critical Alarms** (immediate escalation):
- Error rate > 5%
- Response latency p95 > 1000ms
- DynamoDB throttled (too many writes)
- ECS task failures

**Warning Alarms** (investigate):
- Error rate > 1%
- Response latency p95 > 500ms
- Database utilization > 80%

---

## 10. References

- **Proposal**: [proposal.md](proposal.md)
- **Specification**: [spec.md](spec.md)
- **Implementation Tasks**: [tasks.md](tasks.md)
- **Architectural Decisions**: [adr.md](adr.md)

- **Related ADRs**:
  - [ADR-0002: Repository Pattern](../../../docs/adr/0002-repository-pattern-database-abstraction.md)
  - [ADR-0003: Tiered Access Control](../../../docs/adr/0003-tiered-access-control-model.md)
  - [ADR-0005: Cognito Authentication](../../../docs/adr/0005-cognito-authentication.md)
  - [ADR-0007: Forgiving Input](../../../docs/adr/0007-forgiving-input-strong-output.md)
  - [ADR-0008: Error Communication](../../../docs/adr/0008-explicit-error-communication.md)

- **Related Spikes**:
  - [Spike 007: FastAPI](../../../tests/spikes/007_fastapi/README.md)
  - [Spike 012: DynamoDB](../../../tests/spikes/012_aws_dynamodb/README.md)
  - [Spike 014: Cognito](../../../tests/spikes/014_cognito/README.md)
  - [Spike 015: FastAPI Testing](../../../tests/spikes/015_fastapi_testing/README.md)

---

**Next**: Read [`tasks.md`](tasks.md) for step-by-step implementation checklist.
