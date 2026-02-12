# Test Stubs

This directory contains reusable stub services and test doubles for integration testing without external dependencies.

## What are Stubs?

**Stubs** are simplified replacements for external services that provide deterministic, controlled responses for testing. They enable:
- Local development without cloud services
- Fast, repeatable integration tests
- Testing without AWS costs or network latency
- Offline development

## Terminology

FRANK uses precise testing terminology:

| Type | Purpose | Example |
|------|---------|---------|
| **Stub** | Provides canned responses | Mock Cognito returns valid JWT tokens |
| **Mock** | Verifies behavior/interactions | Assert function was called with specific args |
| **Fake** | Working implementation with shortcuts | In-memory SQLite instead of PostgreSQL |

**This directory contains stubs.** For mock/spy functionality, use `unittest.mock` or `pytest-mock` fixtures.

## Available Stubs

### Cognito Stub Service (`cognito/stub_cognito.py`)

A minimal FastAPI-based AWS Cognito emulation for local development and testing.

**Purpose**: Enable rapid authentication pattern development and testing without AWS dependencies.

**Features**:
- JWT token generation and validation (HS256 for local, RS256 for AWS-compatible)
- User authentication with predefined fixtures
- AWS Cognito API compatibility (`X-Amz-Target` header support)
- Role-based group membership (observer, contributor, partner, core_member)
- Admin endpoints for user management and database reset
- Health check and configuration endpoints
- JWKS endpoint for public key distribution

**Usage**:
```bash
# Direct execution
python tests/stubs/cognito/stub_cognito.py

# Using uv (recommended)
uv run python tests/stubs/cognito/stub_cognito.py --port 8100

# With custom configuration
uv run python tests/stubs/cognito/stub_cognito.py \
  --port 8100 \
  --jwt-algorithm HS256 \
  --jwt-secret my-secret-key
```

**Docker Usage**:
```bash
# Build and run via Docker Compose
docker-compose -f docker-compose.local.yml up mock-cognito

# Or use spike-specific docker-compose
docker-compose -f tests/spikes/014_cognito/docker-compose.yml up
```

**Imported By**:
- `tests/spikes/014_cognito/test_mock_cognito.py` - Stub validation tests
- `tests/unit/management/test_api.py` - Management API authentication tests
- `tests/integration/` - BDD/Behave integration tests

**Configuration**:
```python
from tests.stubs.cognito import AppConfig

config = AppConfig.set_config(
    jwt_algorithm="HS256",        # HS256 for local, RS256 for AWS-compatible
    jwt_secret="local-dev-secret",
    user_pool_id="eu-west-1_MOCKPOOL",
    client_id="mock-client-id-123456",
    region="eu-west-1"
)
```

**Test Fixtures** (Predefined Users):
- **Core Member**: `admin` (org: Schuberg Philis) - Full access
- **Partner**: `s_unit_analyst` (org: S-Unit) - Partner tier access
- **Contributor**: `rabobank_security`, `ing_soc` (orgs: Rabobank, ING) - Can submit data
- **Observer**: `amsterdam_monitor`, `kpn_observer` (orgs: Gemeente Amsterdam, KPN) - Read-only

All test users have password: `Test1234!`

**Endpoints**:
- `POST /` - AWS Cognito API (X-Amz-Target header)
- `GET /health` - Health check
- `GET /.well-known/jwks.json` - JWKS public keys
- `POST /admin/reset` - Reset database to fixtures (testing only)
- `GET /admin/config` - View current configuration

**Integration with FRANK**:
```python
# In test configuration
COGNITO_URL = "http://localhost:8100"
FRANK_AUTH_MODE = "mock"
JWT_ALGORITHM = "HS256"
VALIDATION_STRATEGY = "local_only"
```

## Adding New Stubs

When adding new stub services:

1. **Create subdirectory**: `tests/stubs/{service}/`
2. **Implement stub**: `{service}/stub_{service}.py`
3. **Add package file**: `{service}/__init__.py` with exports
4. **Document**: Create `{service}/README.md` with:
   - Purpose and features
   - Usage instructions
   - Configuration options
   - Integration examples
5. **Update this index**: Add reference to new stub
6. **Ensure determinism**: Stubs must provide repeatable, predictable responses

## Design Principles

**Stubs in FRANK follow these principles:**

1. **Minimal Implementation**: Only implement what's needed for testing
2. **Deterministic**: Same input always produces same output
3. **Fast**: No network calls, no external dependencies
4. **Self-Contained**: Include fixtures and configuration
5. **Discoverable**: Clear documentation and examples
6. **Resettable**: Provide admin endpoints to reset state between tests

## Using Stubs in Tests

### Unit Tests
```python
# tests/unit/auth/test_jwt.py
from tests.stubs.cognito import create_jwt_token

def test_token_validation():
    token = create_jwt_token(username="test", groups=["contributor"])
    payload = validate_token_locally(token)
    assert payload.username == "test"
```

### Integration Tests (Behave)
```python
# tests/integration/environment.py
import requests

def before_scenario(context, scenario):
    # Reset Cognito stub to fixture state
    requests.post("http://localhost:8100/admin/reset")
```

### Docker Compose
```yaml
# docker-compose.local.yml
services:
  mock-cognito:
    build:
      context: .
      dockerfile: tests/stubs/cognito/Dockerfile.stub_cognito
    ports:
      - "8100:8100"
    environment:
      - JWT_ALGORITHM=HS256
      - JWT_SECRET=local-dev-secret
```

## Related Documentation

- [ADR-0012: Testing Philosophy and Local Services](../.openspec/architecture/decisions/0012-testing-philosophy.md)
- [ADR-0011: Spike Integration Process](../.openspec/architecture/decisions/0011-spike-integration-process.md)
- [Spike 014: Cognito Authentication](../tests/spikes/014_cognito/README.md)

## Future Stubs

Potential stub services for FRANK:
- **S3 Stub**: File upload/download testing (or use LocalStack)
- **SQS Stub**: Message queue testing (or use LocalStack)
- **CloudWatch Stub**: Logging and metrics testing (or use LocalStack)

**Note**: For AWS services, prefer LocalStack when available. Create custom stubs only when LocalStack doesn't provide sufficient fidelity for testing needs.
