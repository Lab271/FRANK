# Implementation Tasks: [Feature Name]

⭐ **Required sections marked with star**

- **Status:** ⭐ DRAFT | REVIEW | APPROVED | IN-PROGRESS | COMPLETE
- **Version:** 1.0
- **Last Updated:** YYYY-MM-DD
- **Owner:** ⭐ [Name or Team]
- **Related Design:** [design.md](design.md)
- **Issue:** ⭐ #XXX

---

## Overview

⭐ **Step-by-step implementation plan.** This document breaks down the feature into concrete, actionable tasks.

The companion documents:
- **[proposal.md](proposal.md)**: Why we need this change
- **[spec.md](spec.md)**: What we must do
- **[design.md](design.md)**: How we'll build it
- **[adr.md](adr.md)**: Architectural decisions

---

## Implementation Summary

**Estimated Effort**: 15-20 developer days (2.5-3 weeks with 2-3 developers)

**Critical Path**:
1. Setup & planning (1 day)
2. Stage 1 implementation (5 days)
3. Testing & documentation (2 days)
4. Stage 3 AWS implementation (5 days)
5. Pilot deployment (3+ days)

**Team**:
- 2-3 backend developers
- 1 DevOps engineer (for AWS infrastructure)
- 1 technical writer (for documentation)

**Success Criteria**:
- [ ] All tasks completed
- [ ] Code passes tests (≥85% coverage)
- [ ] PR reviewed and approved
- [ ] Deployed to Stage 3 (AWS)
- [ ] Pilot organizations using API

---

## Phase 1: Setup & Planning (1 day)

Prepare foundation for implementation.

### Task 1.1: Create Specification & Design Documents

**Owner**: [Architect or tech lead]
**Effort**: 2-3 hours
**Depends On**: [ADR-0005 (Cognito)](../../../docs/adr/0005-cognito-authentication.md), [ADR-0003 (Access Control)](../../../docs/adr/0003-tiered-access-control-model.md)

**Definition of Done**:
- [ ] `spec.md` completed with all requirements
- [ ] `design.md` completed with architecture
- [ ] `adr.md` created documenting decisions
- [ ] Code review scheduled
- [ ] Team has reviewed and understands approach

**Deliverables**:
- [ ] spec.md - functional and non-functional requirements
- [ ] design.md - architecture and implementation approach
- [ ] adr.md - architectural decision record

**Acceptance Criteria**:
- [ ] Specification covers all functionality
- [ ] Design documents data flow and components
- [ ] ADR explains why architectural choices made

### Task 1.2: Setup Development Environment & Repository

**Owner**: [DevOps or lead dev]
**Effort**: 1-2 hours
**Depends On**: Task 1.1

**Definition of Done**:
- [ ] Feature branch created (`feat/sightings-api`)
- [ ] CI/CD pipeline configured
- [ ] Test database (SQLite) ready
- [ ] Local development environment verified
- [ ] Team can run `make test` successfully

**Deliverables**:
- [ ] Feature branch in git
- [ ] CI/CD workflow validated
- [ ] Local test environment working

**Acceptance Criteria**:
- [ ] `git checkout feat/sightings-api` works
- [ ] `make test` runs without errors
- [ ] GitHub CI/CD pipeline triggered on PR

### Task 1.3: Create Test Fixtures & Mocks

**Owner**: [QA or test-focused dev]
**Effort**: 2-3 hours
**Depends On**: Task 1.1, 1.2

**Definition of Done**:
- [ ] Fake Observable objects created for testing
- [ ] Test fixtures for various sighting scenarios
- [ ] Mock Cognito authentication tokens
- [ ] Test client (FastAPI TestClient) configured

**Deliverables**:
- [ ] `tests/conftest.py` - pytest fixtures
- [ ] `tests/unit/fixtures/sightings.py` - test data
- [ ] `tests/unit/fixtures/auth.py` - mock JWT tokens

**Acceptance Criteria**:
- [ ] Fixtures can be imported in unit tests
- [ ] Mock tokens pass JWT validation
- [ ] Test scenarios cover happy path and errors

---

## Phase 2: Stage 1 Implementation (5 days)

Implement full API on SQLite with comprehensive tests.

### Task 2.1: Create Sighting Data Models

**Owner**: [Backend developer]
**Effort**: 3-4 hours
**Depends On**: Task 1.1

**Definition of Done**:
- [ ] Sighting Pydantic model created
- [ ] SightingCreateRequest model for input
- [ ] SightingResponse model for output
- [ ] SightingsQueryResponse model for list responses
- [ ] All models documented with examples
- [ ] Unit tests verify model validation

**Files to Create/Modify**:
- [ ] `src/frank/core/models.py` - Add Sighting models
- [ ] `tests/unit/core/test_models.py` - Test model validation

**Acceptance Criteria**:
- [ ] Models follow Pydantic v2 patterns
- [ ] Field validation works (confidence 0-100, required fields, etc.)
- [ ] Serialization/deserialization works
- [ ] Models can be instantiated with valid and invalid data

**Example**:
```python
class Sighting(BaseModel):
    id: str = Field(default_factory=lambda: f"sighting--{uuid.uuid4()}")
    observable_id: str
    observed_at: datetime
    reporter_organization: str
    confidence: int = Field(ge=0, le=100)
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    created_by: str
    access_tier: str = "CONTRIBUTOR"

    class Config:
        extra = "ignore"  # Forgiving on input per ADR-0007
```

### Task 2.2: Create FastAPI Router & Endpoints

**Owner**: [Backend developer]
**Effort**: 4-5 hours
**Depends On**: Task 2.1

**Definition of Done**:
- [ ] Sightings router created (`src/frank/apis/sightings.py`)
- [ ] All 5 endpoints implemented:
  - [ ] GET /api/v1/sightings (query)
  - [ ] GET /api/v1/sightings/{id} (get single)
  - [ ] POST /api/v1/sightings (create)
  - [ ] PUT /api/v1/sightings/{id} (update)
  - [ ] DELETE /api/v1/sightings/{id} (delete)
- [ ] Request/response validation working
- [ ] HTTP status codes correct (201 for create, 204 for delete, etc.)
- [ ] Error responses follow [ADR-0008](../../../docs/adr/0008-explicit-error-communication.md)

**Files to Create/Modify**:
- [ ] `src/frank/apis/sightings.py` - New router
- [ ] `src/frank/apis/__init__.py` - Register router with FastAPI app

**Acceptance Criteria**:
- [ ] Each endpoint handles requests/responses per spec.md
- [ ] Invalid input returns 400 Bad Request with field errors
- [ ] Missing auth returns 401 Unauthorized
- [ ] Successful create returns 201 Created with Location header
- [ ] Successful delete returns 204 No Content

**Example**:
```python
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/v1/sightings", tags=["sightings"])

@router.get("")
async def query_sightings(
    observable_id: Optional[str] = None,
    min_confidence: Optional[int] = None,
    limit: int = 100,
    current_user = Depends(get_current_user),
):
    """Query sightings with optional filters."""
    # Implementation
    pass

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_sighting(
    sighting: SightingCreateRequest,
    current_user = Depends(get_current_user),
):
    """Create new sighting."""
    # Implementation
    pass
```

### Task 2.3: Implement SightingService Business Logic

**Owner**: [Backend developer]
**Effort**: 3-4 hours
**Depends On**: Task 2.1, 2.2

**Definition of Done**:
- [ ] SightingService class created (`src/frank/core/sighting_service.py`)
- [ ] All business logic methods implemented:
  - [ ] `create(sighting_data, user_context)` - Create sighting
  - [ ] `get_by_id(id, user_context)` - Retrieve sighting
  - [ ] `query(filters, user_context)` - Query with filtering
  - [ ] `update(id, updates, user_context)` - Update sighting
  - [ ] `delete(id, user_context)` - Delete sighting
- [ ] Access control enforced per [ADR-0003](../../../docs/adr/0003-tiered-access-control-model.md)
- [ ] Audit logging added for all operations
- [ ] Unit tests verify business logic

**Files to Create/Modify**:
- [ ] `src/frank/core/sighting_service.py` - New service class
- [ ] `tests/unit/core/test_sighting_service.py` - Unit tests

**Acceptance Criteria**:
- [ ] Service methods implement spec.md requirements
- [ ] Access filtering works (OBSERVER, CONTRIBUTOR, PARTNER, CORE_MEMBER)
- [ ] Audit log recorded for create/update/delete operations
- [ ] Error handling clear and actionable

**Example**:
```python
class SightingService:
    def __init__(self, db: BaseFRANKDatabase):
        self.db = db

    def create(self, sighting_data: SightingCreateRequest, user_context: UserContext) -> Sighting:
        """Create new sighting."""
        # 1. Validate user permission
        if not self._can_create(user_context):
            raise PermissionError("User lacks CONTRIBUTOR tier")

        # 2. Build sighting object
        sighting = Sighting(
            observable_id=sighting_data.observable_id,
            observed_at=sighting_data.observed_at,
            confidence=sighting_data.confidence,
            details=sighting_data.details or {},
            created_by=user_context.user_id,
            created_at=datetime.now(timezone.utc),
            access_tier=user_context.access_tier,
            reporter_organization=user_context.org_id,
        )

        # 3. Store in database
        self.db.store_sighting(sighting)

        # 4. Audit log
        self._log_audit("sighting_created", sighting.id, user_context)

        return sighting
```

### Task 2.4: Extend SQLiteDatabase Repository

**Owner**: [Backend developer]
**Effort**: 2-3 hours
**Depends On**: Task 2.3, [ADR-0002](../../../docs/adr/0002-repository-pattern-database-abstraction.md)

**Definition of Done**:
- [ ] BaseFRANKDatabase extended with sighting methods:
  - [ ] `store_sighting(sighting: Sighting)`
  - [ ] `get_sighting_by_id(id: str) -> Sighting`
  - [ ] `query_sightings(filters: Dict) -> List[Sighting]`
  - [ ] `update_sighting(id: str, updates: Dict) -> Sighting`
  - [ ] `delete_sighting(id: str)`
- [ ] SQLiteDatabase implements all methods
- [ ] Database schema created (sightings table)
- [ ] Unit tests verify database operations

**Files to Create/Modify**:
- [ ] `src/frank/storage/base.py` - Add abstract methods
- [ ] `src/frank/storage/sqlite.py` - Implement SQLite
- [ ] Database migrations (if applicable)

**Acceptance Criteria**:
- [ ] Methods follow repository pattern
- [ ] SQLite schema includes all required fields
- [ ] Indexes created for common queries (observable_id, created_by)
- [ ] Transactions ensure data consistency

**SQLite Schema**:
```sql
CREATE TABLE IF NOT EXISTS sightings (
    id TEXT PRIMARY KEY,
    observable_id TEXT NOT NULL,
    observed_at DATETIME NOT NULL,
    reporter_organization TEXT NOT NULL,
    confidence INTEGER NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    details TEXT,  -- JSON
    created_at DATETIME NOT NULL,
    created_by TEXT NOT NULL,
    access_tier TEXT NOT NULL,
    FOREIGN KEY (observable_id) REFERENCES observables(id),
    INDEX idx_observable_id (observable_id),
    INDEX idx_observed_at (observed_at),
    INDEX idx_created_by (created_by)
);
```

### Task 2.5: Implement Authentication & Authorization

**Owner**: [Security-focused developer]
**Effort**: 2-3 hours
**Depends On**: Task 2.2, [ADR-0005](../../../docs/adr/0005-cognito-authentication.md), [ADR-0003](../../../docs/adr/0003-tiered-access-control-model.md)

**Definition of Done**:
- [ ] `get_current_user()` dependency implemented for FastAPI
- [ ] JWT token validation working (with mock tokens for Stage 1)
- [ ] Access tier extraction from token
- [ ] User context injected into requests
- [ ] `AccessControl` class implements filtering logic
- [ ] Unit tests verify auth and authz

**Files to Create/Modify**:
- [ ] `src/frank/util/auth.py` - Authentication utilities
- [ ] `src/frank/util/access_control.py` - Authorization logic
- [ ] `tests/unit/util/test_auth.py` - Auth tests
- [ ] `tests/unit/util/test_access_control.py` - Authz tests

**Acceptance Criteria**:
- [ ] Mock tokens work in unit/integration tests
- [ ] Access filtering blocks unauthorized reads
- [ ] Write operations check tier (CONTRIBUTOR+)
- [ ] Admin operations check tier (CORE_MEMBER)

**Example**:
```python
class AccessControl:
    @staticmethod
    def can_read_sighting(sighting: Sighting, user_context: UserContext) -> bool:
        """Check if user can read sighting."""
        # Same organization members
        if sighting.reporter_organization == user_context.org_id:
            return True

        # Public sightings
        if sighting.access_tier == AccessTier.PUBLIC:
            return True

        # Access tier rules
        match user_context.access_tier:
            case AccessTier.OBSERVER:
                return sighting.access_tier == AccessTier.PUBLIC
            case AccessTier.CONTRIBUTOR:
                return sighting.access_tier in [AccessTier.PUBLIC, AccessTier.OBSERVER]
            case AccessTier.PARTNER:
                return sighting.access_tier != AccessTier.CORE_MEMBER
            case AccessTier.CORE_MEMBER:
                return True

        return False
```

### Task 2.6: Write Unit Tests (Target ≥85% Coverage)

**Owner**: [QA or test-focused developer]
**Effort**: 4-5 hours
**Depends On**: All Tasks 2.1-2.5

**Definition of Done**:
- [ ] Test file created: `tests/unit/apis/test_sightings_api.py`
- [ ] All happy path scenarios tested
- [ ] Validation errors tested (400 responses)
- [ ] Authentication errors tested (401 responses)
- [ ] Authorization errors tested (403 responses)
- [ ] Pagination tested
- [ ] Database persistence tested
- [ ] Coverage report shows ≥85%

**Files to Create**:
- [ ] `tests/unit/apis/test_sightings_api.py` - API endpoint tests
- [ ] `tests/unit/core/test_sighting_service.py` - Service tests (if separate)
- [ ] `tests/unit/storage/test_sqlite_sightings.py` - Database tests

**Acceptance Criteria**:
- [ ] `pytest tests/unit/apis/test_sightings_api.py` passes
- [ ] `pytest --cov=src/frank/apis --cov=src/frank/core --cov-fail-under=85` passes
- [ ] All test cases documented with docstrings
- [ ] Test data fixtures used consistently

**Example Test**:
```python
def test_create_sighting_with_valid_data():
    """POST /api/v1/sightings with valid data creates sighting."""
    # Arrange
    app = create_app()  # Function-based app creation per Spike 015
    client = TestClient(app)
    valid_sighting = {
        "observable_id": "observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e",
        "observed_at": "2026-02-06T14:30:00Z",
        "confidence": 95,
        "details": {"source": "email"}
    }

    # Act
    response = client.post(
        "/api/v1/sightings",
        json=valid_sighting,
        headers={"Authorization": f"Bearer {get_mock_token()}"
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["id"].startswith("sighting--")
    assert data["confidence"] == 95
    assert response.headers["Location"]
```

### Task 2.7: Write Integration Tests (BDD/Behave)

**Owner**: [QA engineer]
**Effort**: 3-4 hours
**Depends On**: Task 2.6

**Definition of Done**:
- [ ] Feature file created: `tests/integration/sightings_api.feature`
- [ ] Step definitions implemented in Python
- [ ] Scenarios cover key workflows:
  - [ ] Create and query sighting
  - [ ] Access tier filtering
  - [ ] Error scenarios (invalid data, auth failures)
- [ ] All scenarios pass (`behave tests/integration/`)

**Files to Create**:
- [ ] `tests/integration/sightings_api.feature` - Gherkin scenarios
- [ ] `tests/integration/steps/sightings_api_steps.py` - Step definitions

**Acceptance Criteria**:
- [ ] `behave tests/integration/` passes with all scenarios
- [ ] Scenarios readable by non-technical stakeholders
- [ ] Database used for integration tests (SQLite)

**Example Scenario**:
```gherkin
Feature: Sightings API

  Scenario: Analyst submits and queries sighting
    Given an authenticated analyst with CONTRIBUTOR tier
    And a known malicious IPv4 observable exists
    When the analyst submits a sighting with confidence 95
    Then the sighting is created with ID starting with "sighting--"
    And the sighting can be queried by observable ID
    And the query returns exactly 1 result
```

---

## Phase 3: Testing & Documentation (2 days)

Comprehensive testing and user documentation.

### Task 3.1: Performance Testing & Optimization

**Owner**: [DevOps or senior developer]
**Effort**: 4-6 hours
**Depends On**: Task 2.7

**Definition of Done**:
- [ ] Load test created: `tests/spikes/XXX_sightings_api_performance_test.py`
- [ ] Performance targets validated:
  - [ ] Query latency < 200ms (95th percentile)
  - [ ] Throughput ≥ 100 submissions/second
  - [ ] Pagination handles 10K+ results
- [ ] Bottlenecks identified and documented
- [ ] Database indexes optimized if needed

**Files to Create**:
- [ ] `tests/spikes/XXX_sightings_api_performance_test.py` - Load tests

**Acceptance Criteria**:
- [ ] Load test runs successfully: `pytest tests/spikes/XXX_sightings_api_performance_test.py -v`
- [ ] Performance metrics recorded
- [ ] Bottlenecks documented for future optimization
- [ ] Caching strategy (if needed) documented

**Example Test**:
```python
def test_query_performance():
    """Query performance < 200ms for 10K sightings."""
    # Setup: Create 10K sightings
    for i in range(10000):
        create_sighting(observable_id=f"observable--{i % 100}")

    # Query all for one observable
    start = time.time()
    response = client.get(f"/api/v1/sightings?observable_id=observable--50")
    latency_ms = (time.time() - start) * 1000

    assert latency_ms < 200, f"Query took {latency_ms}ms, expected < 200ms"
```

### Task 3.2: Create User Documentation

**Owner**: [Technical writer or senior developer]
**Effort**: 3-4 hours
**Depends On**: Task 2.7

**Definition of Done**:
- [ ] API documentation created:
  - [ ] Swagger/OpenAPI specification auto-generated
  - [ ] Endpoint documentation (each endpoint with examples)
  - [ ] Authentication guide
  - [ ] Error reference
- [ ] Integration guide created:
  - [ ] Python integration example
  - [ ] JavaScript/curl integration example
  - [ ] Postman collection
- [ ] Troubleshooting guide created
- [ ] Documentation deployed (Swagger UI at `/docs`)

**Files to Create**:
- [ ] `docs/api/sightings_api.md` - API documentation
- [ ] `docs/guides/integrate_sightings_api.md` - Integration guide
- [ ] `docs/troubleshooting/sightings_api_errors.md` - Troubleshooting
- [ ] OpenAPI spec auto-generated at `/docs` (FastAPI feature)

**Acceptance Criteria**:
- [ ] API docs accessible at `http://localhost:8000/docs`
- [ ] Each endpoint documented with examples
- [ ] Error codes explained with remediation steps
- [ ] Integration examples executable

### Task 3.3: Code Review & Quality Gates

**Owner**: [Tech lead]
**Effort**: 2-3 hours
**Depends On**: Task 3.2

**Definition of Done**:
- [ ] All code reviewed by at least 2 team members
- [ ] Feedback addressed and resolved
- [ ] All tests pass:
  - [ ] `pytest tests/unit/ --cov-fail-under=85`
  - [ ] `behave tests/integration/`
  - [ ] `ruff check src/frank`
  - [ ] `mypy src/frank`
- [ ] No merge conflicts
- [ ] PR approved and ready to merge

**Files to Verify**:
- [ ] `src/frank/apis/sightings.py` - Code quality
- [ ] `src/frank/core/sighting_service.py` - Code quality
- [ ] `src/frank/storage/sqlite.py` - Database implementation
- [ ] All test files - Test quality

**Acceptance Criteria**:
- [ ] Ruff linting passes (0 violations)
- [ ] mypy type checking passes
- [ ] Coverage ≥85%
- [ ] All tests pass
- [ ] PR approved and ready to merge to main

---

## Phase 4: Stage 3 AWS Implementation (5 days)

Deploy to AWS with production infrastructure.

### Task 4.1: Design DynamoDB Tables for Production

**Owner**: [DevOps engineer]
**Effort**: 2-3 hours
**Depends On**: [ADR-0002](../../../docs/adr/0002-repository-pattern-database-abstraction.md), [Spike 012: DynamoDB](../../../tests/spikes/012_aws_dynamodb/README.md)

**Definition of Done**:
- [ ] DynamoDB table schema designed:
  - [ ] Partition key: observable_id
  - [ ] Sort key: observed_at
  - [ ] Global secondary indexes for common queries
  - [ ] TTL settings (if applicable)
- [ ] Capacity planning completed
- [ ] CloudFormation template created
- [ ] Cost estimates provided

**Files to Create**:
- [ ] `infrastructure/cloudformation/dynamodb_tables.yaml` - Table definitions

**Acceptance Criteria**:
- [ ] Table supports all query patterns from spec.md
- [ ] Indexes optimize common queries
- [ ] Capacity sized for expected load
- [ ] CloudFormation template valid

**Example Table Design**:
```yaml
SightingsTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: frank-sightings
    BillingMode: PAY_PER_REQUEST  # On-demand for variable traffic
    AttributeDefinitions:
      - AttributeName: observable_id
        AttributeType: S
      - AttributeName: observed_at
        AttributeType: S
      - AttributeName: created_by
        AttributeType: S
    KeySchema:
      - AttributeName: observable_id
        KeyType: HASH
      - AttributeName: observed_at
        KeyType: RANGE
    GlobalSecondaryIndexes:
      - IndexName: created_by_index
        KeySchema:
          - AttributeName: created_by
            KeyType: HASH
          - AttributeName: created_at
            KeyType: RANGE
        Projection:
          ProjectionType: ALL
    StreamSpecification:
      StreamViewType: NEW_AND_OLD_IMAGES
```

### Task 4.2: Implement DynamoDBDatabase Repository

**Owner**: [Backend developer]
**Effort**: 3-4 hours
**Depends On**: Task 4.1

**Definition of Done**:
- [ ] `DynamoDBDatabase` class extends `BaseFRANKDatabase`
- [ ] All sighting methods implemented:
  - [ ] `store_sighting(sighting)`
  - [ ] `get_sighting_by_id(id)`
  - [ ] `query_sightings(filters)`
  - [ ] `update_sighting(id, updates)`
  - [ ] `delete_sighting(id)`
- [ ] Query patterns optimized for DynamoDB
- [ ] Pagination with ExclusiveStartKey working
- [ ] Unit tests verify DynamoDB operations (using LocalStack for tests)

**Files to Create/Modify**:
- [ ] `src/frank/storage/dynamodb.py` - New DynamoDB implementation

**Acceptance Criteria**:
- [ ] Methods follow repository pattern
- [ ] Queries use appropriate indexes
- [ ] Pagination handles large result sets
- [ ] Tests pass with LocalStack DynamoDB

**Example Implementation**:
```python
class DynamoDBDatabase(BaseFRANKDatabase):
    def __init__(self, table_name: str, dynamodb_resource):
        self.table = dynamodb_resource.Table(table_name)

    def store_sighting(self, sighting: Sighting):
        """Store sighting in DynamoDB."""
        self.table.put_item(
            Item={
                'observable_id': sighting.observable_id,
                'observed_at': sighting.observed_at.isoformat(),
                'id': sighting.id,
                'reporter_organization': sighting.reporter_organization,
                'confidence': sighting.confidence,
                'details': sighting.details,
                'created_at': sighting.created_at.isoformat(),
                'created_by': sighting.created_by,
                'access_tier': sighting.access_tier,
            }
        )

    def query_sightings(self, observable_id: str, **kwargs) -> List[Sighting]:
        """Query sightings by observable."""
        response = self.table.query(
            KeyConditionExpression='observable_id = :id',
            ExpressionAttributeValues={':id': observable_id},
            Limit=kwargs.get('limit', 100),
        )
        return [Sighting(**item) for item in response['Items']]
```

### Task 4.3: Create CloudFormation Infrastructure Templates

**Owner**: [DevOps engineer]
**Effort**: 3-4 hours
**Depends On**: Task 4.1

**Definition of Done**:
- [ ] CloudFormation templates created:
  - [ ] DynamoDB tables
  - [ ] ECS Fargate service definition
  - [ ] Application Load Balancer
  - [ ] Security groups
  - [ ] IAM roles and policies
- [ ] Parameters for environment customization (dev/staging/prod)
- [ ] Outputs for reference (table names, ALB DNS, etc.)
- [ ] Templates tested (syntax validation)

**Files to Create**:
- [ ] `infrastructure/cloudformation/vpc.yaml` - Network infrastructure
- [ ] `infrastructure/cloudformation/dynamodb.yaml` - DynamoDB tables
- [ ] `infrastructure/cloudformation/ecs.yaml` - ECS cluster and service
- [ ] `infrastructure/cloudformation/alb.yaml` - Load balancer

**Acceptance Criteria**:
- [ ] Templates are valid YAML (AWS CloudFormation validation)
- [ ] Parameters allow environment customization
- [ ] Outputs export values for cross-stack references
- [ ] IAM roles follow least-privilege principle

### Task 4.4: Create Docker Image & ECR Repository

**Owner**: [DevOps engineer]
**Effort**: 2-3 hours
**Depends On**: Task 4.3

**Definition of Done**:
- [ ] Dockerfile created with:
  - [ ] Python 3.13 base image
  - [ ] Minimal layers (security, performance)
  - [ ] Health check endpoint
- [ ] ECR repository created in AWS
- [ ] Docker image built and pushed to ECR
- [ ] Image tagged with version and "latest"
- [ ] Image vulnerability scanning enabled

**Files to Create**:
- [ ] `docker/Dockerfile` - Container definition
- [ ] `docker/.dockerignore` - Exclude unnecessary files
- [ ] `infrastructure/build_and_push.sh` - Build script

**Acceptance Criteria**:
- [ ] `docker build -t frank-api:latest .` succeeds
- [ ] Container starts and listens on port 8000
- [ ] Health check endpoint `/api/v1/health` responds
- [ ] Image scanned for vulnerabilities

**Example Dockerfile**:
```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/v1/health')"

CMD ["uvicorn", "src.frank.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Task 4.5: Update Configuration for AWS Environment

**Owner**: [Backend developer]
**Effort**: 2-3 hours
**Depends On**: Task 4.2, 4.4

**Definition of Done**:
- [ ] Environment variables configured:
  - [ ] DynamoDB table name
  - [ ] AWS region
  - [ ] Cognito settings
  - [ ] CloudWatch logging
- [ ] Configuration loading per [ADR-0006](../../../docs/adr/0006-admin-mvc-architecture.md) (if applicable)
- [ ] Secrets management integrated (AWS Secrets Manager)
- [ ] Database initialization for Stage 3

**Files to Create/Modify**:
- [ ] `src/frank/config.py` - Configuration management
- [ ] `.env.aws.example` - Example AWS environment variables

**Acceptance Criteria**:
- [ ] Configuration loads from environment variables
- [ ] Secrets loaded securely (not hardcoded)
- [ ] Application starts with correct database backend (DynamoDB in AWS)

**Example**:
```python
# src/frank/config.py
import os
from enum import Enum

class Environment(Enum):
    LOCAL = "local"
    AWS = "aws"

FRANK_ENV = os.getenv("FRANK_ENV", Environment.LOCAL.value)
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "frank-sightings-dev")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")

def get_database():
    """Get appropriate database implementation."""
    if FRANK_ENV == Environment.AWS.value:
        import boto3
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        return DynamoDBDatabase(DYNAMODB_TABLE, dynamodb)
    else:
        return SQLiteDatabase(":memory:")
```

### Task 4.6: Deploy to AWS & Validation

**Owner**: [DevOps engineer]
**Effort**: 3-4 hours
**Depends On**: Task 4.1-4.5

**Definition of Done**:
- [ ] CloudFormation stack created in AWS
- [ ] DynamoDB tables created
- [ ] ECS service deployed
- [ ] Load balancer operational
- [ ] API accessible via HTTPS
- [ ] Health checks passing
- [ ] CloudWatch logs and metrics working
- [ ] Smoke tests passing

**Testing Steps**:
- [ ] API health check: `curl https://api.frank.example.com/api/v1/health`
- [ ] Create sighting via API
- [ ] Query sightings
- [ ] Check CloudWatch logs
- [ ] Verify DynamoDB entries

**Acceptance Criteria**:
- [ ] ECS tasks running (healthy status)
- [ ] API responds to requests
- [ ] Data persists in DynamoDB
- [ ] CloudWatch metrics available
- [ ] Auto-scaling configured and tested

---

## Phase 5: Pilot Deployment (3+ days)

Deploy to pilot organizations for real-world validation.

### Task 5.1: Onboard Pilot Organizations

**Owner**: [PM or product lead]
**Effort**: 4-6 hours
**Depends On**: Task 4.6

**Definition of Done**:
- [ ] Pilot organizations identified (3-5 organizations)
- [ ] API credentials provided to each organization
- [ ] Integration guide sent
- [ ] Kickoff meeting scheduled
- [ ] Support contact established

**Deliverables**:
- [ ] Pilot organization list with contacts
- [ ] API credentials (API keys or Cognito accounts)
- [ ] Integration documentation (link to API docs)
- [ ] Support SLA documented

**Acceptance Criteria**:
- [ ] Each organization has API access
- [ ] Technical contacts trained on API usage
- [ ] Support process established

### Task 5.2: Monitor Pilot Deployment

**Owner**: [DevOps engineer]
**Effort**: 2-3 hours/day during pilot
**Depends On**: Task 5.1

**Definition of Done**:
- [ ] Dashboards created in CloudWatch:
  - [ ] API latency (p50, p95, p99)
  - [ ] Error rate
  - [ ] Throughput
  - [ ] DynamoDB consumed capacity
- [ ] Alarms configured for anomalies
- [ ] Daily monitoring log maintained
- [ ] Issues escalated immediately

**Deliverables**:
- [ ] CloudWatch dashboards
- [ ] Daily status reports
- [ ] Issue tracking (GitHub issues)

**Acceptance Criteria**:
- [ ] Real-time visibility into API health
- [ ] Issues detected and resolved quickly
- [ ] Performance stays within SLOs

### Task 5.3: Gather Pilot Feedback

**Owner**: [PM]
**Effort**: Ongoing during pilot
**Depends On**: Task 5.1-5.2

**Definition of Done**:
- [ ] Feedback mechanisms established:
  - [ ] Weekly syncs with organizations
  - [ ] GitHub issue for feature requests
  - [ ] Email for support questions
- [ ] Feedback documented and categorized
- [ ] Issues prioritized for post-pilot improvements
- [ ] Success metrics tracked:
  - [ ] Organizations using API actively
  - [ ] Sightings submitted and queried
  - [ ] User satisfaction scores

**Deliverables**:
- [ ] Feedback log
- [ ] Feature request prioritization
- [ ] Post-pilot improvement roadmap

**Acceptance Criteria**:
- [ ] All organizations actively using API
- [ ] No critical issues blocking usage
- [ ] Feedback collected for future improvements

### Task 5.4: Post-Pilot Optimization & Documentation

**Owner**: [Tech lead]
**Effort**: 2-3 days after pilot
**Depends On**: Task 5.3

**Definition of Done**:
- [ ] Performance optimizations implemented (based on pilot data)
- [ ] Documentation updated based on pilot feedback
- [ ] Known issues documented
- [ ] Roadmap for future enhancements created
- [ ] Release notes prepared
- [ ] Feature considered production-ready

**Deliverables**:
- [ ] Optimized API performance
- [ ] Updated documentation
- [ ] Release notes
- [ ] Post-pilot improvements roadmap

**Acceptance Criteria**:
- [ ] All pilot feedback addressed
- [ ] Performance meets NFR targets
- [ ] Documentation reflects actual usage patterns
- [ ] Feature ready for general availability

---

## Task Dependencies

```
Phase 1: Setup & Planning
├─ Task 1.1: Create Specs
├─ Task 1.2: Setup Environment (depends on 1.1)
└─ Task 1.3: Test Fixtures (depends on 1.1, 1.2)

Phase 2: Stage 1 Implementation
├─ Task 2.1: Data Models (depends on 1.1)
├─ Task 2.2: FastAPI Router (depends on 2.1)
├─ Task 2.3: Service Logic (depends on 2.1, 2.2)
├─ Task 2.4: SQLite Repo (depends on 2.3)
├─ Task 2.5: Auth/Authz (depends on 2.2)
├─ Task 2.6: Unit Tests (depends on 2.1-2.5)
└─ Task 2.7: Integration Tests (depends on 2.6)

Phase 3: Testing & Documentation
├─ Task 3.1: Performance Testing (depends on 2.7)
├─ Task 3.2: Documentation (depends on 2.7)
└─ Task 3.3: Code Review (depends on 3.1, 3.2)

Phase 4: Stage 3 AWS Implementation
├─ Task 4.1: DynamoDB Design (depends on 3.3)
├─ Task 4.2: DynamoDB Repo (depends on 4.1)
├─ Task 4.3: CloudFormation (depends on 4.1)
├─ Task 4.4: Docker Image (depends on 4.3)
├─ Task 4.5: AWS Config (depends on 4.2, 4.4)
└─ Task 4.6: Deploy & Validate (depends on 4.1-4.5)

Phase 5: Pilot Deployment
├─ Task 5.1: Onboard Orgs (depends on 4.6)
├─ Task 5.2: Monitor (depends on 5.1)
├─ Task 5.3: Gather Feedback (depends on 5.1-5.2)
└─ Task 5.4: Post-Pilot Optimization (depends on 5.3)
```

---

## Progress Tracking

### Checkpoints

- [ ] **End of Phase 1** (1 day): Specifications complete, team aligned
- [ ] **End of Phase 2** (6 days): Stage 1 fully implemented and tested
- [ ] **End of Phase 3** (8 days): Documentation complete, code reviewed
- [ ] **End of Phase 4** (13 days): Deployed to AWS production
- [ ] **End of Phase 5** (16+ days): Pilot organizations using API, feedback collected

### Status Updates

Update this section as work progresses:

**Current Phase**: [PLANNING | PHASE 1 | PHASE 2 | PHASE 3 | PHASE 4 | PHASE 5 | COMPLETE]

**Latest Update**: [Date and progress summary]

**Blockers**: [Any blockers preventing progress]

---

## References

- **Proposal**: [proposal.md](proposal.md)
- **Specification**: [spec.md](spec.md)
- **Design Document**: [design.md](design.md)
- **Architectural Decisions**: [adr.md](adr.md)

---

**Next**: Read [`adr.md`](adr.md) for architectural decisions and rationale.
