# FastAPI Testing Patterns Specification

**Domain:** Testing / API Testing Patterns
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06

**Owner:** Development Team
- **Related Spike:** [Spike 015: FastAPI Testing](tests/spikes/015_fastapi_testing/README.md)
- **Integration:** Applied across all FRANK APIs

## Overview

Documents standard testing patterns for FastAPI applications in FRANK. Establishes pytest-based testing approaches for authenticated endpoints, exception handling, and comprehensive API coverage.

### Philosophy

- **Test-Driven Reliability**: Comprehensive testing (≥85% coverage) ensures API reliability
- **Reusable Patterns**: Standardized test patterns accelerate development
- **Authentication First**: Systematic testing of auth scenarios prevents security gaps
- **From Spike to Standard**: Patterns validated in Spike 015, now production standard

### Key Capabilities

- **Function-Based FastAPI**: Factory functions (`create_app()`) for better testability
- **TestClient Integration**: FastAPI TestClient for request/response testing
- **Bearer Token Testing**: Comprehensive authentication scenario coverage
- **Exception Handling**: Standardized error response testing
- **Logging Integration**: Request/response logging with timing

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Usage in this specification**:
- **MUST/SHALL**: Test coverage requirements, authentication testing
- **SHOULD**: Follow established patterns for consistency
- **MAY**: Add API-specific test scenarios

---

## Requirements

### Requirement 1: Function-Based FastAPI Architecture

- **Description**: FastAPI applications must use factory functions (`create_app()`) returning configured application instances for better testability.
- **Acceptance Criteria**:
  - [ ] App creation function accepts configuration parameters
  - [ ] Function returns FastAPI instance with all routes registered
  - [ ] Tests can create isolated app instances per test
  - [ ] Dependency overrides work correctly in tests
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: N/A

#### Scenario: Creating app instance with custom configuration
- GIVEN a create_app() factory function
- WHEN I call create_app(db_path="/tmp/test.db", log_level="DEBUG")
- THEN a FastAPI instance is returned with custom configuration
- AND the database uses the test path
- AND logging is set to DEBUG level

#### Scenario: Isolated app instances per test
- GIVEN two parallel test cases
- WHEN test_1 creates app_1 with config_1
- AND test_2 creates app_2 with config_2
- THEN each app has independent configuration
- AND no state is shared between tests
- AND both tests can run simultaneously

#### Scenario: All routes registered at creation
- GIVEN a create_app() function
- WHEN I create an app instance
- THEN all endpoints are registered (/health, /submit, /observables)
- AND I can query the app.routes to verify registration
- AND OpenAPI schema includes all endpoints

#### Scenario: Dependency override for testing
- GIVEN a production authentication dependency
- WHEN I create a test app and override the auth dependency with a mock
- THEN test requests bypass real authentication
- AND the mock auth returns test user data
- AND tests run without needing real JWT tokens

#### Scenario: Lifespan events in testing
- GIVEN a create_app() with lifespan events (database initialization)
- WHEN I create the app in a test using TestClient context manager
- THEN startup events execute before tests
- AND shutdown events execute after tests
- AND resources are properly cleaned up

### Requirement 2: Comprehensive Endpoint Test Coverage

- **Description**: All API endpoints must have tests covering public access, authenticated access, validation errors, and exception scenarios.
- **Acceptance Criteria**:
  - [ ] Public endpoints tested without authentication
  - [ ] Protected endpoints tested with valid/invalid/missing tokens
  - [ ] Validation errors return 400 Bad Request with details
  - [ ] Exceptions return appropriate status codes (401, 403, 404, 500)
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: N/A

#### Scenario: Testing public health endpoint
- GIVEN a FastAPI application with /health endpoint
- WHEN I send GET /health without authentication
- THEN the response is 200 OK
- AND the response JSON includes {"status": "healthy"}
- AND no Authorization header is required

#### Scenario: Testing protected endpoint with valid token
- GIVEN a protected /submit endpoint requiring authentication
- WHEN I send POST /submit with valid Bearer token in Authorization header
- THEN the response is 201 Created
- AND the submission is processed successfully
- AND the response includes the submission_id

#### Scenario: Testing protected endpoint with missing token
- GIVEN a protected /submit endpoint
- WHEN I send POST /submit without Authorization header
- THEN the response is 401 Unauthorized
- AND the response includes error detail "Not authenticated"
- AND no submission is created

#### Scenario: Testing validation errors
- GIVEN a /submit endpoint expecting valid observable data
- WHEN I send POST /submit with invalid observable_type "invalid-type"
- THEN the response is 422 Unprocessable Entity
- AND the response includes detailed validation errors
- AND the error indicates which field failed validation

#### Scenario: Testing 404 Not Found error
- GIVEN a /submissions/{id} endpoint
- WHEN I request GET /submissions/submission--does-not-exist with valid auth
- THEN the response is 404 Not Found
- AND the response includes error message "Submission not found"
- AND the response follows standard error format

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

#### Scenario: Valid Bearer token authentication
- GIVEN an authentication dependency using HTTPBearer
- WHEN I send request with header "Authorization: Bearer valid-token-123"
- THEN the dependency validates the token
- AND extracts user information (username, access_tier)
- AND the endpoint receives authenticated user context

#### Scenario: Invalid Bearer token rejection
- GIVEN an authentication dependency
- WHEN I send request with header "Authorization: Bearer invalid-token"
- THEN the dependency rejects the token
- AND returns 401 Unauthorized
- AND the response includes WWW-Authenticate header
- AND the endpoint is never reached

#### Scenario: Missing Authorization header
- GIVEN a protected endpoint with auth dependency
- WHEN I send request without Authorization header
- THEN HTTPBearer returns 403 Forbidden (before dependency runs)
- AND the response indicates missing credentials
- AND the endpoint is never reached

#### Scenario: Malformed Authorization header
- GIVEN a protected endpoint
- WHEN I send request with header "Authorization: InvalidFormat token123"
- THEN HTTPBearer rejects the malformed header
- AND returns 403 Forbidden
- AND the response indicates invalid authentication scheme

#### Scenario: Testing with mock authentication
- GIVEN a test that needs authenticated context
- WHEN I override the auth dependency with a mock returning test user data
- THEN tests can bypass real token validation
- AND tests receive predictable user context (username="testuser", tier="PARTNER")
- AND no real Cognito calls are made during tests

### Requirement 4: Exception Handling Patterns

- **Description**: APIs must handle both standard HTTPException and custom exceptions with consistent error response formats.
- **Acceptance Criteria**:
  - [ ] Standard exceptions return proper status codes
  - [ ] Custom exceptions extend HTTPException with additional context
  - [ ] Unhandled exceptions caught by FastAPI and return 500
  - [ ] Error responses follow consistent JSON format
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: ADR-0008 (Explicit Error Communication)

#### Scenario: Standard HTTPException handling
- GIVEN an endpoint that raises HTTPException(status_code=404, detail="Not found")
- WHEN the exception is raised during request processing
- THEN FastAPI returns 404 Not Found
- AND the response JSON includes {"detail": "Not found"}
- AND the error format is standard FastAPI format

#### Scenario: Custom exception with context
- GIVEN a custom FRANKException extending HTTPException
- WHEN the endpoint raises FRANKException(status_code=403, detail="Access denied", context={"required_tier": "PARTNER"})
- THEN the response is 403 Forbidden
- AND the response includes both detail and context fields
- AND the custom exception handler formats the error consistently

#### Scenario: Unhandled exception returns 500
- GIVEN an endpoint with a bug causing unhandled ZeroDivisionError
- WHEN the endpoint is called and the exception occurs
- THEN FastAPI catches the exception
- AND returns 500 Internal Server Error
- AND the response includes generic error message (no stack trace in production)

#### Scenario: Validation error returns 422
- GIVEN an endpoint expecting Pydantic model with required fields
- WHEN I send request with missing required field "observable_type"
- THEN FastAPI validation raises ValidationError
- AND returns 422 Unprocessable Entity
- AND the response includes detailed field-level errors

#### Scenario: Testing error response format consistency
- GIVEN multiple endpoints with different error types
- WHEN I test 401, 403, 404, 422, and 500 errors
- THEN all responses follow consistent JSON structure
- AND all include "detail" field
- AND custom errors include "context" field
- AND error format matches ADR-0008 specification

### Requirement 5: TestClient Integration

- **Description**: Tests must use FastAPI's TestClient for realistic request/response testing with proper startup/shutdown handling.
- **Acceptance Criteria**:
  - [ ] TestClient instantiated with app fixture
  - [ ] Supports context manager for proper cleanup
  - [ ] Works with lifespan events
  - [ ] Handles cookies, headers, and redirects correctly
- **Stage Availability**: All stages (1-4)
- **Related ADR(s)**: N/A

#### Scenario: TestClient with pytest fixture
- GIVEN a pytest fixture that creates TestClient with app
- WHEN tests use the client fixture
- THEN each test gets a fresh TestClient instance
- AND the app is created per fixture scope
- AND tests are isolated from each other

#### Scenario: Context manager for proper cleanup
- GIVEN a TestClient used with context manager
- WHEN I create the client with "with TestClient(app) as client:"
- THEN lifespan startup events run before tests
- AND tests execute with active client
- AND lifespan shutdown events run after tests
- AND resources are properly cleaned up

#### Scenario: Lifespan events for database setup
- GIVEN an app with lifespan context that initializes database
- WHEN TestClient is created with the app
- THEN the database initialization runs at startup
- AND tests can use the initialized database
- AND database connections are closed at shutdown

#### Scenario: Request headers and cookies
- GIVEN a TestClient instance
- WHEN I make request with custom headers {"X-Request-ID": "test-123"}
- THEN the headers are sent to the endpoint
- AND the endpoint can access the custom header
- AND cookies are maintained across requests if set

#### Scenario: Testing redirects
- GIVEN an endpoint that returns RedirectResponse to "/health"
- WHEN I make request with TestClient follow_redirects=True
- THEN TestClient follows the redirect automatically
- AND the final response is from /health endpoint
- AND the response history includes the redirect

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
# tests/unit/main/test_api.py
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
# src/frank/main/api.py
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

**Location**: `tests/unit/main/test_api.py, tests/unit/management/test_api.py`

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

**Location**: `tests/integration/features/cognito_management.feature, tests/integration/features/frank_server_api.feature, tests/integration/features/management_api_users.feature` (BDD/Behave)

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
  - [Sightings API Spec](../010-sightings-api/spec.md) - Uses these patterns
  - [Management API Spec](../011-management-api/spec.md) - Uses these patterns
  - [Authentication Spec](../012-authentication/spec.md) - Bearer token validation

- **Related Spikes**:
  - [Spike 015: FastAPI Testing](tests/spikes/015_fastapi_testing/README.md) - Original validation
  - [Spike 014: Cognito](tests/spikes/014_cognito/README.md) - JWT validation patterns

- **External Resources**:
  - [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/)
  - [Pytest Documentation](https://docs.pytest.org/)
  - [TestClient API Reference](https://www.starlette.io/testclient/)

- **Implementation Examples**:
  - `tests/unit/main/test_api.py` - Sightings API tests
  - `tests/unit/management/test_api.py` - Management API tests

---

## 9. Open Questions & Decisions Pending

*No pending questions - patterns validated and adopted*

---

## 10. Appendix: Examples

### Example 1: Complete Test Module Structure

```python
# tests/unit/main/test_api.py
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

**Questions or feedback?** See [Spike 015 README](tests/spikes/015_fastapi_testing/README.md) for original hypothesis and validation results.
