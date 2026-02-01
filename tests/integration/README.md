# FRANK Platform - Integration Tests

This directory contains BDD (Behavior-Driven Development) integration tests for the FRANK platform, organized into three separate test suites.

## Test Suites

### 1. Mock Cognito Tests
**File**: `features/cognito_management.feature`
**Script**: `run_cognito_tests.sh`
**Service**: Mock Cognito (port 8100)

Tests for Mock Cognito user and organization management:
- User CRUD operations
- Organization management
- Group/role assignments
- Authentication flows
- AWS Cognito API compatibility

### 2. FRANK Server API Tests
**File**: `features/frank_server_api.feature`
**Script**: `run_frank_api_tests.sh`
**Service**: FRANK Server API (port 8000)

Tests for the main FRANK threat intelligence API:
- Submission endpoints
- Query and search functionality
- Access level filtering
- Authentication and authorization
- Health checks and statistics

### 3. Management API Tests
**File**: `features/management_api_users.feature`
**Script**: `run_management_api_tests.sh`
**Services**: Management API (port 8200) + Mock Cognito (port 8100)

Tests for the FRANK Management API:
- User management via API
- Organization member operations
- Authentication flows
- Access control and permissions
- Edge cases and error handling

## Running Tests

### Run All Test Suites (Orchestrator)

The main orchestrator script checks service availability and runs all available test suites:

```bash
# Run all available tests (skips unavailable services)
./tests/integration/run_bdd_tests.sh

# Fail if any service is unavailable
./tests/integration/run_bdd_tests.sh --fail-on-unavailable
```

**Output Example:**
```
============================================================
FRANK Platform - BDD Test Suite Orchestrator
============================================================

Checking service availability...

✓ Mock Cognito is available
✗ FRANK Server API is NOT available
✗ Management API is NOT available

============================================================
Test Suite Execution Plan
============================================================
Mock Cognito Tests:    RUN
FRANK API Tests:       SKIP
Management API Tests:  SKIP
============================================================
```

### Run Individual Test Suites

Each test suite can be run independently:

```bash
# Mock Cognito tests
./tests/integration/run_cognito_tests.sh [cognito_port] [tags]

# FRANK Server API tests
./tests/integration/run_frank_api_tests.sh [server_port] [tags]

# Management API tests
./tests/integration/run_management_api_tests.sh [management_port] [cognito_port] [tags]
```

**Examples:**
```bash
# Run Mock Cognito tests on default port (8100)
./tests/integration/run_cognito_tests.sh

# Run FRANK API tests with specific tag
./tests/integration/run_frank_api_tests.sh 8000 @health

# Run Management API tests on custom ports
./tests/integration/run_management_api_tests.sh 9200 8100
```

### Run Specific Tags

Use Behave tags to run subsets of tests:

```bash
# Run only health check tests
./tests/integration/run_cognito_tests.sh 8100 @health

# Run only authentication tests
./tests/integration/run_management_api_tests.sh 8200 8100 @auth

# Run only user CRUD tests
./tests/integration/run_cognito_tests.sh 8100 @users
```

**Common Tags:**
- `@health` - Health check tests
- `@users` - User management tests
- `@organisations` - Organization tests
- `@auth` - Authentication tests
- `@crud` - Create/Read/Update/Delete tests
- `@cognito` - Mock Cognito specific tests
- `@management` - Management API specific tests

## Starting Services

Before running tests, ensure the required services are running:

### Mock Cognito
```bash
cd tests/spikes/014_cognito
uv run python mock_cognito.py
```
**Port**: 8100
**Health**: http://localhost:8100/health

### FRANK Server API
```bash
python -m frank.server
```
**Port**: 8000
**Health**: http://localhost:8000/v1/health

### Management API
```bash
python -m frank.management.server
```
**Port**: 8200
**Health**: http://localhost:8200/health

## Test Architecture

### Directory Structure
```
tests/integration/
├── features/                      # Gherkin feature files
│   ├── cognito_management.feature
│   ├── frank_server_api.feature
│   └── management_api_users.feature
├── steps/                         # Step definitions
│   ├── cognito_management.steps.py
│   ├── frank_api.steps.py
│   └── management_api_users.steps.py
├── environment.py                 # Behave hooks and configuration
├── run_bdd_tests.sh              # Orchestrator script
├── run_cognito_tests.sh          # Mock Cognito test runner
├── run_frank_api_tests.sh        # FRANK API test runner
├── run_management_api_tests.sh   # Management API test runner
└── README.md                     # This file
```

### Service Availability Checks

Each test script performs health checks before running tests:
- **Mock Cognito**: `http://localhost:8100/health`
- **FRANK Server API**: `http://localhost:8000/v1/health`
- **Management API**: `http://localhost:8200/health`

If a service is unavailable:
- Individual scripts: **Exit with error** and show instructions
- Orchestrator script: **Skip the suite** and continue with available services

### Database Seeding

The `environment.py` file handles automatic database seeding:
- **Mock Cognito**: Reset to fixtures before each `@cognito` scenario
- **Management API**: Reseed before each `@management` scenario
- **Conditional**: Only seeds when running tests with matching tags

This ensures test isolation without requiring manual cleanup.

## Configuration

### Environment Variables

You can override default ports using environment variables:

```bash
export COGNITO_PORT=8100
export SERVER_PORT=8000
export MANAGEMENT_PORT=8200

./tests/integration/run_bdd_tests.sh
```

### Custom Ports via Command Line

```bash
# Run specific test suite with custom port
./tests/integration/run_cognito_tests.sh 9100

# Override ports for orchestrator
COGNITO_PORT=9100 SERVER_PORT=9000 MANAGEMENT_PORT=9200 \
  ./tests/integration/run_bdd_tests.sh
```

## Troubleshooting

### Tests Fail with Connection Refused

**Cause**: Service not running
**Solution**: Start the required service (see "Starting Services" above)

### Warning: Could not seed database

**Cause**: Service unavailable during database seeding
**Solution**: Ensure service is running before executing tests

### ConfigError: No steps directory

**Cause**: Test script running from wrong directory
**Solution**: Scripts automatically change to correct directory; ensure you run from project root

### All Test Suites Skipped

**Cause**: No services are available
**Solution**: Start at least one service before running the orchestrator

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Start Mock Cognito
        run: |
          cd tests/spikes/014_cognito
          uv run python mock_cognito.py &
          sleep 2

      - name: Start FRANK Server
        run: |
          python -m frank.server &
          sleep 2

      - name: Start Management API
        run: |
          python -m frank.management.server &
          sleep 2

      - name: Run Integration Tests
        run: ./tests/integration/run_bdd_tests.sh --fail-on-unavailable
```

### Selective Testing

Run only specific suites in CI:

```yaml
- name: Run Mock Cognito Tests Only
  run: ./tests/integration/run_cognito_tests.sh
```

## Best Practices

1. **Always check service availability** before running tests
2. **Use the orchestrator** for comprehensive testing
3. **Use individual scripts** for focused development
4. **Use tags** to run specific subsets of tests
5. **Review logs** for database seeding warnings
6. **Keep services running** during iterative development

## Contributing

When adding new tests:

1. Add scenarios to the appropriate `.feature` file
2. Implement step definitions in the corresponding `steps/*.py` file
3. Use appropriate tags (`@cognito`, `@management`, etc.)
4. Ensure tests are idempotent and properly isolated
5. Test both with and without service availability

## License

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
