# FastAPI Testing Patterns Specification

- **Status:** ⭐ IMPLEMENTED
- **Version:** 1.0
- **Last Updated:** 2026-02-06
- **Owner:** ⭐ Development Team
- **Related ADRs:** N/A (extracted from spike 015)
- **Issue:** ⭐ #N/A (spike-derived specification)
- **GitHub PR:** Integrated across all FRANK APIs
- **Related Spike:** [Spike 015: FastAPI Testing](../../tests/spikes/015_fastapi_testing/README.md)

---

## 1. Purpose

⭐ This specification documents the standard testing patterns for FastAPI applications in FRANK. It establishes pytest-based testing approaches for authenticated endpoints, exception handling, and comprehensive API coverage.

**Problem Solved**: FastAPI applications require specific testing patterns for authentication, HTTP status codes, exception handling, and request/response validation. Without standardized patterns, test coverage becomes inconsistent and difficult to maintain across multiple APIs.

**Business Value**:
- Comprehensive test coverage (≥85%) for all APIs
- Faster development through reusable test patterns
- Consistent error handling and status code usage
- Reduced bugs through systematic authentication testing

**Why Now**: FRANK is transitioning from proof-of-concept to production-ready platform, requiring systematic testing approaches that scale across multiple APIs (Sightings API, Management API, Background Tasks API).

**Connection to Vision**: Supports FRANK's goal of mission-critical threat intelligence platform by ensuring API reliability through comprehensive testing.

---

## 2. Functional Requirements

### Requirement 1: Function-Based FastAPI Architecture

- **Description**: FastAPI applications must use factory functions (`create_app()`) returning configured application instances for better testability.
- **Acceptance Criteria**:
  - [ ] App creation function accepts configuration parameters
  - [ ] Function returns FastAPI instance with all routes registered
  - [ ] Tests can create isolated app instances per test
  - [ ] Dependency overrides work correctly in tests
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: N/A

### Requirement 2: Comprehensive Endpoint Test Coverage

- **Description**: All API endpoints must have tests covering public access, authenticated access, validation errors, and exception scenarios.
- **Acceptance Criteria**:
  - [ ] Public endpoints tested without authentication
  - [ ] Protected endpoints tested with valid/invalid/missing tokens
  - [ ] Validation errors return 400 Bad Request with details
  - [ ] Exceptions return appropriate status codes (401, 403, 404, 500)
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: N/A

### Requirement 3: Bearer Token Authentication Testing

- **Description**: Protected endpoints must use FastAPI Depends() pattern for authentication, with clear testing approach for token validation.
- **Acceptance Criteria**:
  - [ ] Authentication dependency function validates Bearer tokens
  - [ ] Tests use TestClient with Authorization headers
  - [ ] Invalid tokens return 401 Unauthorized
  - [ ] Missing tokens return 401 Unauthorized
  - [ ] Malformed headers return 401 Unauthorized
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: Spike 014 (Cognito integration)

### Requirement 4: Exception Handling Patterns

- **Description**: APIs must handle both standard HTTPException and custom exceptions with consistent error response formats.
- **Acceptance Criteria**:
  - [ ] Standard exceptions return proper status codes
  - [ ] Custom exceptions extend HTTPException with additional context
  - [ ] Unhandled exceptions caught by FastAPI and return 500
  - [ ] Error responses follow consistent JSON format
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: ADR-0008 (Explicit Error Communication)

### Requirement 5: TestClient Integration

- **Description**: Tests must use FastAPI's TestClient for realistic request/response testing with proper startup/shutdown handling.
- **Acceptance Criteria**:
  - [ ] TestClient instantiated with app fixture
  - [ ] Supports context manager for proper cleanup
  - [ ] Works with lifespan events
  - [ ] Handles cookies, headers, and redirects correctly
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: N/A

---

## 3. Non-Functional Requirements

### Test Performance

- **Execution Time**: Unit tests should complete in < 5 seconds for full suite
- **Isolation**: Each test runs independently without shared state
- **Parallelization**: Tests can run in parallel with pytest-xdist

### Test Coverage

- **Line Coverage**: ≥85% code coverage for all API code
- **Branch Coverage**: ≥80% branch coverage for conditional logic
- **Endpoint Coverage**: 100% of endpoints have tests

### Test Maintainability

- **Readability**: Tests follow Arrange-Act-Assert pattern
- **Reusability**: Common test fixtures shared across test modules
- **Documentation**: Complex test scenarios include docstrings

---

## 4. Data Model / API Contract

### Test Structure Pattern

```python
# tests/unit/apis/test_example_api.py
import pytest
from fastapi.testclient import TestClient
from frank.apis.example_api import create_app

@pytest.fixture
def client():
    """Create test client with app instance."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

def test_public_endpoint(client):
    """Public endpoint returns 200 OK without authentication."""
    # Arrange: No setup needed

    # Act: Make request without authentication
    response = client.get("/")

    # Assert: Verify response
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to FRANK"}

def test_protected_endpoint_with_valid_token(client):
    """Protected endpoint returns 200 OK with valid Bearer token."""
    # Arrange: Prepare authorization header
    headers = {"Authorization": "Bearer valid-token-here"}

    # Act: Make authenticated request
    response = client.get("/protected", headers=headers)

    # Assert: Verify authenticated response
    assert response.status_code == 200
    assert "user" in response.json()

def test_protected_endpoint_without_token(client):
    """Protected endpoint returns 401 Unauthorized without token."""
    # Act: Make request without authentication
    response = client.get("/protected")

    # Assert: Verify authentication required
    assert response.status_code == 401
    assert "detail" in response.json()

def test_protected_endpoint_with_invalid_token(client):
    """Protected endpoint returns 401 Unauthorized with invalid token."""
    # Arrange: Prepare invalid token
    headers = {"Authorization": "Bearer invalid-token"}

    # Act: Make request with invalid token
    response = client.get("/protected", headers=headers)

    # Assert: Verify rejection
    assert response.status_code == 401

def test_validation_error(client):
    """Endpoint returns 400 Bad Request for invalid input."""
    # Arrange: Prepare invalid payload
    invalid_data = {"field": "invalid-value"}

    # Act: POST invalid data
    response = client.post("/submit", json=invalid_data)

    # Assert: Verify validation error
    assert response.status_code == 400
    assert "detail" in response.json()

def test_exception_handling(client):
    """Endpoint returns 500 Internal Server Error for exceptions."""
    # Act: Trigger exception endpoint
    response = client.get("/error")

    # Assert: Verify error handling
    assert response.status_code == 500
    assert "error" in response.json()
```

### Authentication Dependency Pattern

```python
# src/frank/apis/example_api.py
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Validate Bearer token and return user info."""
    token = credentials.credentials

    # Validate token (mock for development, Cognito for production)
    if token != "valid-token-here":
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"username": "testuser", "access_tier": "CONTRIBUTOR"}

def create_app() -> FastAPI:
    """Create FastAPI application with routes."""
    app = FastAPI(title="FRANK Example API")

    @app.get("/")
    async def public_endpoint():
        """Public endpoint accessible without authentication."""
        return {"message": "Welcome to FRANK"}

    @app.get("/protected")
    async def protected_endpoint(user: dict = Depends(get_current_user)):
        """Protected endpoint requiring authentication."""
        return {"message": "Protected data", "user": user}

    return app
```

### Exception Handling Pattern

```python
# Custom exception extending HTTPException
class FRANKException(HTTPException):
    """FRANK custom exception with additional context."""
    def __init__(self, status_code: int, detail: str, context: dict = None):
        super().__init__(status_code=status_code, detail=detail)
        self.context = context or {}

# Exception handler registration
@app.exception_handler(FRANKException)
async def frank_exception_handler(request, exc: FRANKException):
    """Handle FRANK custom exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "frank_error",
                "message": exc.detail,
                "context": exc.context
            }
        }
    )
```

---

## 5. Test Coverage Requirements

### Unit Tests

**Location**: `tests/unit/apis/test_*_api.py`

**Required Test Scenarios**:
- [ ] Public endpoints (no auth required)
- [ ] Protected endpoints with valid token (200 OK)
- [ ] Protected endpoints without token (401 Unauthorized)
- [ ] Protected endpoints with invalid token (401 Unauthorized)
- [ ] Protected endpoints with malformed Authorization header (401)
- [ ] Validation errors (400 Bad Request)
- [ ] Resource not found (404 Not Found)
- [ ] Access forbidden (403 Forbidden)
- [ ] Internal server error (500)
- [ ] Custom exception handling

**Coverage Target**: ≥85% code coverage

### Integration Tests

**Location**: `tests/integration/*.feature` (BDD/Behave)

```gherkin
Feature: API Authentication

  Scenario: User accesses protected endpoint with valid token
    Given an authenticated user with CONTRIBUTOR tier
    When the user requests "/protected"
    Then the response status code is 200
    And the response contains user information

  Scenario: User accesses protected endpoint without token
    Given an unauthenticated user
    When the user requests "/protected"
    Then the response status code is 401
    And the response contains authentication error
```

### Manual Testing Checklist

```bash
# 1. Test public endpoint
curl http://localhost:8000/

# 2. Test protected endpoint without auth
curl http://localhost:8000/protected
# Expected: 401 Unauthorized

# 3. Test protected endpoint with auth
curl -H "Authorization: Bearer valid-token" http://localhost:8000/protected
# Expected: 200 OK with user data

# 4. Test invalid token
curl -H "Authorization: Bearer invalid" http://localhost:8000/protected
# Expected: 401 Unauthorized

# 5. Test malformed header
curl -H "Authorization: invalid-format" http://localhost:8000/protected
# Expected: 403 Forbidden (HTTPBearer validation)
```

---

## 6. Implementation Status

### Checklist

- [x] Specification complete and reviewed
- [x] Design patterns validated (spike 015)
- [x] Unit tests implemented for all FRANK APIs
- [x] Integration tests cover key workflows
- [x] Patterns documented and shared with team
- [x] Code review passed
- [x] Merged to main branch
- [x] Released in version 0.2.0

### Progress Notes

**Current Phase**: COMPLETE

**Latest Update**: 2026-02-06 - Migrated from spike 015 to formal specification

### Implementation Notes

- **Spike Validation**: Spike 015 validated function-based architecture and comprehensive endpoint testing
- **Production Adoption**: All FRANK APIs (Sightings, Management) use these patterns
- **Test Coverage**: Achieved 90%+ coverage across all APIs using these patterns
- **Developer Experience**: Patterns significantly reduced time to add new endpoints with proper test coverage

---

## 7. Evolution Path Across FRANK Stages

### Stage 1: SQLite + FastAPI (Local Development)

- ✅ Fully applicable
- **Testing**: Mock authentication, in-memory database, fast test execution
- **Pattern**: Function-based app creation, pytest fixtures

### Stage 2: DynamoDB + MySQL + Docker (Learning Stage)

- ✅ Fully applicable
- **Testing**: Docker Compose for integration tests, LocalStack for AWS services
- **Pattern**: Same testing patterns with environment-specific configuration

### Stage 3: AWS ECS + DynamoDB (Cloud Deployment)

- ✅ Fully applicable
- **Testing**: AWS Cognito integration testing, DynamoDB test fixtures
- **Pattern**: Real JWT token validation, cloud resource mocking

### Stage 4: Kubernetes + ScyllaDB (Production Scale)

- ✅ Fully applicable
- **Testing**: Kubernetes test environments, distributed tracing validation
- **Pattern**: Service mesh aware testing, multi-region scenarios

---

## 8. References

- **Related ADRs**:
  - ADR-0008: Explicit Error Communication
  - ADR-0012: Testing Philosophy (when created)

- **Related Specifications**:
  - [Sightings API Spec](../apis/sightings-api.spec.md) - Uses these patterns
  - [Management API Spec](../apis/management-api.spec.md) - Uses these patterns
  - [Authentication Spec](../apis/authentication.spec.md) - Bearer token validation

- **Related Spikes**:
  - [Spike 015: FastAPI Testing](../../tests/spikes/015_fastapi_testing/README.md) - Original validation
  - [Spike 014: Cognito](../../tests/spikes/014_cognito/README.md) - JWT validation patterns

- **External Resources**:
  - [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/)
  - [Pytest Documentation](https://docs.pytest.org/)
  - [TestClient API Reference](https://www.starlette.io/testclient/)

- **Implementation Examples**:
  - `tests/unit/apis/test_sightings_api.py` - Sightings API tests
  - `tests/unit/apis/test_management_api.py` - Management API tests

---

## 9. Open Questions & Decisions Pending

*No pending questions - patterns validated and adopted*

---

## 10. Appendix: Examples

### Example 1: Complete Test Module Structure

```python
# tests/unit/apis/test_submission_api.py
import pytest
from fastapi.testclient import TestClient
from frank.apis.submission_api import create_app

@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_headers():
    """Valid authentication headers."""
    return {"Authorization": "Bearer valid-token"}

class TestPublicEndpoints:
    """Test public endpoints without authentication."""

    def test_health_check(self, client):
        """Health check endpoint returns 200 OK."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

class TestAuthenticatedEndpoints:
    """Test authenticated endpoints."""

    def test_submit_with_auth(self, client, auth_headers):
        """Submit endpoint with valid token returns 201 Created."""
        payload = {"observable": {"type": "ipv4", "value": "1.2.3.4"}}
        response = client.post("/v1/submit", json=payload, headers=auth_headers)
        assert response.status_code == 201

    def test_submit_without_auth(self, client):
        """Submit endpoint without token returns 401."""
        payload = {"observable": {"type": "ipv4", "value": "1.2.3.4"}}
        response = client.post("/v1/submit", json=payload)
        assert response.status_code == 401

class TestValidation:
    """Test input validation."""

    def test_invalid_observable_type(self, client, auth_headers):
        """Invalid observable type returns 400."""
        payload = {"observable": {"type": "invalid", "value": "test"}}
        response = client.post("/v1/submit", json=payload, headers=auth_headers)
        assert response.status_code == 400
        assert "detail" in response.json()
```

### Example 2: Testing Custom Exceptions

```python
# Test custom exception handler
def test_custom_exception_handler(client):
    """Custom exceptions return proper error format."""
    response = client.get("/trigger-custom-error")

    assert response.status_code == 403
    data = response.json()
    assert data["error"]["type"] == "frank_error"
    assert "message" in data["error"]
    assert "context" in data["error"]
```

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 2025-02-15 | 0.1 | Spike 015 | Initial spike validation |
| 2025-03-01 | 0.9 | Development Team | Adopted across all APIs |
| 2026-02-06 | 1.0 | SDD Migration | Formalized as specification |

---

**Questions or feedback?** See [Spike 015 README](../../tests/spikes/015_fastapi_testing/README.md) for original hypothesis and validation results.
