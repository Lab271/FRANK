# ADR-013: Testing Philosophy and Local Services

- **Status:** Superseded by [ADR-018](018-container-is-the-reference-and-test-tiers.md) (four test tiers; no AWS services to mock)
- **Date:** 2026-01-31
- **Decision Makers:** Development Team
- **Related:** [ADR-005](005-three-layer-testing-strategy.md), [ADR-012](012-spike-integration-process.md)

## Context and Problem Statement

FRANK requires a comprehensive testing strategy that supports confident evolution across infrastructure stages while enabling rapid local development. How do we test systems that depend on AWS services (Cognito, DynamoDB) without incurring costs or requiring cloud access? When should we use mock services vs real services? How do we balance test coverage with development velocity? The testing philosophy needs to be explicitly documented to guide developers on when to use stubs, mocks, integration tests, and spike validation.

## Decision Drivers

- Must enable local development without AWS account or costs
- Need confidence that code works across all infrastructure stages
- Should support rapid feedback loops (fast tests for immediate feedback)
- Must prevent AWS service dependencies from blocking development
- Test strategy should complement evolutionary design philosophy
- Clear guidelines on when to use stubs vs mocks vs real services

## Considered Options

1. **Three-Layer Testing with Local Service Stubs** - Unit tests (fast), integration tests (confidence), spike tests (exploration), plus stub services for external dependencies
2. **Real Services Only** - Always test against real AWS services (Cognito, DynamoDB)
3. **Mocks Everywhere** - Mock all external dependencies at unit test level

## Decision Outcome

Chosen option: "Three-Layer Testing with Local Service Stubs", because it balances speed, confidence, and development cost while supporting FRANK's evolutionary philosophy.

### Positive Consequences

- Developers can work offline without AWS access
- Fast feedback from unit tests (<100ms per test)
- Confidence from integration tests against stub services
- Validation of real AWS integration in spike tests
- No AWS costs during development and testing
- Stub services can be shared across stages

### Negative Consequences

- Stub services require maintenance to match real service behavior
- Risk of stub divergence from real service (mitigated by spike validation)
- Additional infrastructure (stub services) to run and maintain

## Testing Philosophy

### Three-Layer Testing Strategy (ADR-0004)

FRANK uses three distinct test layers, each with a specific purpose:

#### Layer 1: Unit Tests (`tests/unit/`)

**Purpose:** Fast, isolated component testing for immediate feedback.

**Characteristics:**
- Execution: < 100ms per test
- Dependencies: Mocked or stubbed at function/class level
- Scope: Single function, class, or module
- Coverage: ≥85% of business logic (CI enforced)

**Organization:**
```
tests/unit/
├── core/           # Business logic tests
├── storage/        # Repository pattern tests
├── auth/           # Authentication tests
├── management/     # Management API tests
└── util/           # Utility function tests
```

**Example:**
```python
def test_observable_ipv4_validation():
    """Unit test: validates IPv4 observable creation"""
    obs = Observable.create_ipv4("192.168.1.1")
    assert obs.value == "192.168.1.1"
    assert obs.type == ObservableType.IPV4
```

**When to Use:** Testing business logic, data transformations, validations, and algorithms without external dependencies.

#### Layer 2: Integration Tests (`tests/integration/`)

**Purpose:** System confidence through component interaction testing.

**Characteristics:**
- Framework: Behave (BDD) with Gherkin syntax
- Scope: API endpoints, database operations, authentication flows
- Dependencies: Stub services (Mock Cognito, test databases)
- Features: Business scenarios in `.feature` files

**Organization:**
```
tests/integration/
├── features/           # Gherkin feature files
│   ├── frank_server_api.feature
│   ├── management_api_users.feature
│   └── authentication.feature
├── steps/              # Step implementations
│   ├── frank_api.steps.py
│   ├── management.steps.py
│   └── auth.steps.py
└── environment.py      # Behave setup/teardown
```

**Example Feature (Gherkin):**
```gherkin
Scenario: Service account authentication
  Given the Mock Cognito service is running
  And the Management API is running
  When I create a service account "service-acme-ingestion"
  And I login with the generated credentials
  Then I receive a valid JWT token
  And the token contains group "contributor"
```

**When to Use:** Testing API endpoints, database interactions, authentication flows, and multi-component scenarios.

#### Layer 3: Spike Tests (`tests/spikes/`)

**Purpose:** Hypothesis-driven learning and technology validation.

**Characteristics:**
- Time-boxed: 1-4 hours per spike
- Validation: Files ending in `*_test.py` run with pytest
- Scope: Explore new technologies, validate patterns
- Documentation: Each spike has README.md with results

**Organization:**
```
tests/spikes/
├── 003_pydantic/       # Pydantic v2 validation
├── 014_cognito/        # AWS Cognito authentication
├── 015_fastapi_testing/ # FastAPI testing patterns
└── index.md            # Spike inventory
```

**Example:**
```python
def test_cognito_jwt_validation():
    """Spike validation: Cognito stub generates valid JWTs"""
    from tests.stubs.cognito import create_jwt_token
    token = create_jwt_token(username="test", groups=["contributor"])
    payload = validate_token_locally(token)
    assert payload.username == "test"
    assert "contributor" in payload.groups
```

**When to Use:** Exploring new technologies, validating hypotheses, learning AWS service patterns before production implementation.

### Coverage Requirements

**CI/CD Enforcement:**
- Minimum 85% coverage (`--cov-fail-under=85`)
- Coverage reports uploaded as GitHub Actions artifacts
- PR comments show coverage percentage

**Why 85%?**
- Balances confidence with velocity
- Higher thresholds (95%+) slow development with diminishing returns
- Lower thresholds (<80%) allow quality drift and hidden bugs
- Empirically proven sweet spot for FRANK's complexity level

**What to Cover:**
- ✅ Business logic (models, validators, transformations)
- ✅ Database operations (repositories, queries)
- ✅ API endpoints (request/response handling)
- ✅ Authentication and authorization
- ❌ Third-party library code (trust the library)
- ❌ Trivial getters/setters (provide no business value)

## Local Services: Stubs vs Mocks

### Terminology

**Stub:** Minimal implementation of an external service that returns hardcoded responses for testing.
- Purpose: Enable testing without real service
- Behavior: Predictable, deterministic responses
- State: No interaction recording
- Example: Mock Cognito returns valid JWT tokens

**Mock:** Test double that records interactions for verification.
- Purpose: Verify component called correctly
- Behavior: Can be programmed with expectations
- State: Records calls, arguments, order
- Example: Mock database that asserts `save()` was called

**FRANK Uses Stubs (Not Mocks):** Our "Mock Cognito" is actually a **stub service** - it provides minimal Cognito implementation for local development, not interaction verification.

### Stub Services in FRANK

#### Cognito Stub Service

**Location:** `tests/stubs/cognito/stub_cognito.py`

**Purpose:** Local AWS Cognito emulation for development and testing without AWS costs.

**Features:**
- FastAPI-based HTTP service
- JWT token generation (HS256 for local, RS256 for AWS-compatible)
- User authentication simulation
- Group/role management
- Configuration endpoint for test automation (`/admin/reset`)
- JWKS endpoint for token validation

**Usage:**
```bash
# Start stub service
python tests/stubs/cognito/stub_cognito.py --port 8100

# Configure FRANK to use stub
export COGNITO_URL=http://localhost:8100
export FRANK_AUTH_MODE=mock
export JWT_ALGORITHM=HS256
```

**When to Use:**
- ✅ Local development without AWS account
- ✅ Integration tests (`tests/integration/`)
- ✅ CI/CD pipeline (no AWS credentials needed)
- ✅ Rapid iteration without network latency
- ❌ Production deployment (use real AWS Cognito)

#### Future Stub Services

As FRANK evolves, additional stub services may be needed:
- **Stub S3:** For file upload testing (LocalStack provides this)
- **Stub SQS:** For queue testing (LocalStack provides this)
- **Stub CloudWatch:** For logging testing (LocalStack provides this)

**Principle:** Use LocalStack for AWS services when available, create custom stubs only when necessary.

## Decision Tree: When to Use Each Test Type

```
┌─────────────────────────────────────────────────────────────┐
│  "I need to test..."                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  → Business logic calculation                               │
│    └─ Unit Test (tests/unit/)                               │
│                                                             │
│  → Database query                                           │
│    └─ Unit Test with in-memory SQLite                       │
│                                                             │
│  → API endpoint                                             │
│    └─ Integration Test (tests/integration/)                 │
│       with stub services                                    │
│                                                             │
│  → Authentication flow                                      │
│    └─ Integration Test (tests/integration/)                 │
│       with Mock Cognito stub                                │
│                                                             │
│  → New technology or pattern                                │
│    └─ Spike Test (tests/spikes/)                            │
│       with validation criteria                              │
│                                                             │
│  → Real AWS service integration                             │
│    └─ Spike Test (tests/spikes/)                            │
│       OR manual validation in AWS Dev environment           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Decision Tree: When to Use Stubs vs Real Services

```
┌─────────────────────────────────────────────────────────────┐
│  "Should I use a stub or real service?"                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Local Development?                                         │
│    └─ YES → Use stub service                                │
│    └─ NO → Continue...                                      │
│                                                             │
│  CI/CD Pipeline?                                            │
│    └─ YES → Use stub service (no AWS credentials)           │
│    └─ NO → Continue...                                      │
│                                                             │
│  Testing service-specific behavior?                         │
│  (e.g., DynamoDB conditional updates)                       │
│    └─ YES → Use real service in spike                       │
│    └─ NO → Continue...                                      │
│                                                             │
│  Need to validate AWS integration?                          │
│    └─ YES → Use real service in AWS Dev environment         │
│    └─ NO → Use stub service                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Repository Pattern and Database Abstraction Testing

**Pattern:** All database implementations extend `BaseFRANKDatabase` interface.

**Benefit:** Same test cases can validate SQLite, DynamoDB, PostgreSQL implementations.

**Approach:**
```python
# tests/unit/storage/test_base_database.py
class BaseDatabaseTests:
    """Shared test cases for all database implementations"""

    def test_store_submission(self, db):
        submission = Submission.create_minimal(...)
        db.store_submission(submission)
        retrieved = db.get_submission_by_id(submission.submission_id)
        assert retrieved.submission_id == submission.submission_id

    def test_access_tier_filtering(self, db):
        # Test that OBSERVER can't see CONTRIBUTOR data
        pass

# tests/unit/storage/test_sqlite.py
class TestSQLite(BaseDatabaseTests):
    @pytest.fixture
    def db(self):
        return create_sqlite_database(":memory:")

# tests/unit/storage/test_dynamodb.py
class TestDynamoDB(BaseDatabaseTests):
    @pytest.fixture
    def db(self):
        return create_dynamodb_database(...)  # LocalStack
```

**Result:** Confidence that all implementations behave identically.

## Patterns from Spike 015: FastAPI Testing

Spike 015 established comprehensive patterns for testing FastAPI applications:

**1. Function-Based Architecture:**
```python
def create_app() -> FastAPI:
    """Factory function for configured FastAPI instance"""
    app = FastAPI()
    # Register routes, middleware, exception handlers
    return app
```

**2. Bearer Token Authentication:**
```python
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    # Validate token...
```

**3. TestClient Pattern:**
```python
@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_protected_endpoint(client):
    response = client.get("/protected", headers={"Authorization": "Bearer valid_token"})
    assert response.status_code == 200
```

**4. Authentication Testing:**
- Valid tokens → 200 OK
- Invalid tokens → 401 Unauthorized
- Missing headers → 401 Unauthorized
- Malformed headers → 401 Unauthorized

## Integration Test Setup

**File:** `tests/integration/environment.py`

**Responsibilities:**
- Load configuration (API URLs, ports)
- Start stub services (Mock Cognito, Management API)
- Reset databases before each scenario
- Provide test tokens for different access tiers
- Clean up after test run

**before_scenario() hook:**
```python
def before_scenario(context, scenario):
    # Reset Mock Cognito to fixture state
    requests.post(f"{COGNITO_URL}/admin/reset")

    # Reset Management API to seed data
    requests.post(f"{MANAGEMENT_URL}/admin/seed?force=true")

    # Clear scenario-specific state
    context.response = None
    context.submission_id = None
```

## Pros and Cons of the Options

### Option 1: Three-Layer Testing with Local Service Stubs (CHOSEN)

Combines unit tests, integration tests, spike tests, and stub services.

- Good, because developers can work offline without AWS
- Good, because fast feedback from unit tests
- Good, because confidence from integration tests
- Good, because no AWS costs during development
- Good, because stub services can be shared across stages
- Good, because supports evolutionary design philosophy
- Bad, because stub services require maintenance
- Bad, because risk of stub/real service divergence
- Bad, because additional infrastructure to manage

### Option 2: Real Services Only

Always test against real AWS services.

- Good, because no stub divergence risk
- Good, because tests real service behavior
- Bad, because requires AWS account for all developers
- Bad, because incurs AWS costs for every test run
- Bad, because slow (network latency)
- Bad, because blocks development when offline
- Bad, because CI/CD requires AWS credentials
- Bad, because difficult to reset state between tests

### Option 3: Mocks Everywhere

Mock all external dependencies at unit test level.

- Good, because very fast tests
- Good, because no external dependencies
- Bad, because no confidence in real integration
- Bad, because mocks drift from real behavior
- Bad, because doesn't test API contracts
- Bad, because brittle tests (over-mocking)
- Bad, because doesn't validate authentication flows

## Test Execution Commands

```bash
# Unit tests (fast feedback)
pytest tests/unit/ -v --cov=src/frank --cov-fail-under=85

# Integration tests (system confidence)
behave tests/integration/

# Spike validation tests
pytest tests/spikes/ -k "*_test.py" -v

# With custom configuration
behave tests/integration/ -D server_port=8080 -D cognito_port=8100

# All tests (make target)
make test

# Coverage report with missing lines
pytest tests/unit/ --cov=src/frank --cov-report=term-missing
```

## Links

- [ADR-005: Three-Layer Testing Strategy](005-three-layer-testing-strategy.md) - Foundational testing approach
- [ADR-012: Spike Integration Process](012-spike-integration-process.md) - How spike tests feed production
- [ADR-004: Repository Pattern and Database Abstraction](004-repository-pattern-database-abstraction.md) - Testing database implementations
- `tests/spikes/015_fastapi_testing/README.md` - FastAPI testing patterns
- `tests/spikes/014_cognito/README.md` - Cognito authentication spike (origin of stub)
- `tests/stubs/README.md` - Centralized stub services documentation
- `tests/stubs/cognito/` - Cognito stub service implementation
