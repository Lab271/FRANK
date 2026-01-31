# Running Mock Cognito BDD Tests

This guide shows how to run BDD tests specifically for Mock Cognito user and organisation management.

## Overview

We have **two separate sets of BDD tests**:

1. **`frank_server_api.feature`** - Tests FRANK server API (submissions, queries, access control)
2. **`cognito_management.feature`** - Tests Mock Cognito CRUD operations (users, organisations)

## Quick Start

### 1. Start Mock Cognito

In one terminal:
```bash
cd tests/spikes/014_cognito
uv run python mock_cognito.py --reload
```

You should see fixture data logged:
```
=== Organisations ===

CORE MEMBER:
  Schuberg Philis (identity--schuberg-philis)
    Users: admin, ijsbrand
...
```

### 2. Run Cognito Tests

In another terminal:
```bash
cd tests/integration

# Run all Cognito tests
behave features/cognito_management.feature -D cognito_port=8100

# Or use the helper script
./run_bdd_tests.sh 8000 8100 @cognito
```

## Test Categories

### Health & Seeding Tests
```bash
# Verify Mock Cognito is running and fixture data loaded
behave features/cognito_management.feature --tags=@health
behave features/cognito_management.feature --tags=@seeding
```

### User CRUD Tests
```bash
# Test user creation, reading, updating, deletion
behave features/cognito_management.feature --tags=@users

# Just CRUD operations
behave features/cognito_management.feature --tags=@crud
```

### Organisation Tests
```bash
# Test organisation queries (list users by org)
behave features/cognito_management.feature --tags=@organisations
```

### Authentication Tests
```bash
# Test login flows with different users
behave features/cognito_management.feature --tags=@authentication
```

### AWS Compatibility Tests
```bash
# Verify AWS Cognito API format compatibility
behave features/cognito_management.feature --tags=@aws-compatibility
```

### Group Management Tests
```bash
# Test adding/removing users from groups (access tiers)
behave features/cognito_management.feature --tags=@groups
```

## Test Scenarios

### Verify Seeded Data (7 users, 6 organisations)

```bash
behave features/cognito_management.feature --tags=@seeding -D cognito_port=8100
```

**What it tests:**
- All 7 fixture users exist
- Users have correct custom attributes (organisation_id, role)
- Users are in correct groups (core_member, partner, contributor, observer)
- Organisation filtering works

**Expected output:**
```
Scenario: Verify seeded fixture data           # features/cognito_management.feature:15
  When I list all users in Mock Cognito        # PASSED
  Then I should see 7 users in the system      # PASSED
  And user "admin" should exist with organisation "identity--schuberg-philis"  # PASSED
  ...
```

### Test User CRUD Operations

```bash
behave features/cognito_management.feature --tags=@crud -D cognito_port=8100
```

**What it tests:**
- Create user with custom attributes
- Get user shows UserAttributes array (AWS format)
- Update user's organisation
- Update user with UserAttributes format (AWS format)
- Delete user

### Test Organisation Queries

```bash
behave features/cognito_management.feature --tags=@organisations -D cognito_port=8100
```

**What it tests:**
- List users filtered by organisation_id
- Schuberg Philis has 2 members (admin, ijsbrand)
- S-Unit has 1 member (s_unit_analyst)
- Each organisation has correct access tier

### Test Authentication Flows

```bash
behave features/cognito_management.feature --tags=@authentication -D cognito_port=8100
```

**What it tests:**
- Authenticate with valid credentials
- JWT tokens contain correct groups
- Invalid password fails with NotAuthorizedException
- Non-existent user fails with UserNotFoundException

## Running Against Different Environments

### Local Mock Cognito (Development)
```bash
behave features/cognito_management.feature -D cognito_url=http://localhost:8100
```

### Docker Compose Mock Cognito
```bash
behave features/cognito_management.feature -D cognito_url=http://localhost:8100
```

### AWS Cognito (Production)
```bash
behave features/cognito_management.feature \
  -D cognito_url=https://cognito-idp.eu-west-1.amazonaws.com \
  -D verify_ssl=true
```

**Note:** Tests work identically against Mock or AWS Cognito!

## Complete Test Matrix

### Run Everything
```bash
# All Cognito tests
behave features/cognito_management.feature -D cognito_port=8100

# Specific test
behave features/cognito_management.feature:25 -D cognito_port=8100
```

### Run by Category
```bash
# Health + Seeding
behave features/cognito_management.feature --tags=@health,@seeding

# CRUD operations only
behave features/cognito_management.feature --tags=@crud

# Skip edge cases
behave features/cognito_management.feature --tags=~@edge-cases
```

## Separate from Server Tests

### Run ONLY Cognito Tests
```bash
behave features/cognito_management.feature -D cognito_port=8100
```

### Run ONLY Server Tests
```bash
behave features/frank_server_api.feature -D server_port=8000
```

### Run Both (Full Suite)
```bash
# Start both services first
cd tests/spikes/014_cognito
uv run python mock_cognito.py &  # Port 8100

cd ../..
python stages/stage1/server.py & # Port 8000

# Run all tests
cd tests/integration
behave -D server_port=8000 -D cognito_port=8100
```

## Test Output Examples

### Successful Run
```
Feature: Mock Cognito User and Organisation Management

  Background:
    Given Mock Cognito is running on port 8100  ... passed

  @seeding @cognito
  Scenario: Verify seeded fixture data
    When I list all users in Mock Cognito       ... passed
    Then I should see 7 users in the system     ... passed
    And user "admin" should exist with organisation "identity--schuberg-philis"  ... passed
    And user "ijsbrand" should exist with organisation "identity--schuberg-philis"  ... passed

  @organisations @cognito
  Scenario Outline: List users by organisation -- @1.1
    When I filter users by organisation "identity--schuberg-philis"  ... passed
    Then I should see 2 users                    ... passed
    And the users should be "admin,ijsbrand"     ... passed

6 features passed, 0 failed, 0 skipped
45 scenarios passed, 0 failed, 0 skipped
120 steps passed, 0 failed, 0 skipped, 0 undefined
```

### Failed Test (for debugging)
```
  @users @crud @cognito
  Scenario: Create a new user with organisation
    When I create a new user with the following details  ... failed

    Assertion Failed: User creation failed
    HTTP 409 Conflict: User already exists
```

## Debugging

### Verbose Output
```bash
behave features/cognito_management.feature -D cognito_port=8100 --verbose
```

### Show Request/Response
```bash
behave features/cognito_management.feature -D cognito_port=8100 --logging-level=DEBUG
```

### Stop on First Failure
```bash
behave features/cognito_management.feature -D cognito_port=8100 --stop
```

### Dry Run (see what would run)
```bash
behave features/cognito_management.feature -D cognito_port=8100 --dry-run
```

## CI/CD Integration

### GitHub Actions
```yaml
name: Cognito BDD Tests

on: [push, pull_request]

jobs:
  cognito-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install behave requests pyjwt hamcrest

      - name: Start Mock Cognito
        run: |
          cd tests/spikes/014_cognito
          python mock_cognito.py &
          sleep 5

      - name: Run Cognito BDD Tests
        run: |
          cd tests/integration
          behave features/cognito_management.feature \
            -D cognito_port=8100 \
            --junit \
            --junit-directory test-results/

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: cognito-test-results
          path: tests/integration/test-results/
```

## Troubleshooting

### Mock Cognito Not Running
```
Connection refused: http://localhost:8100
```

**Solution:**
```bash
# Check if running
lsof -i :8100

# Start it
cd tests/spikes/014_cognito
uv run python mock_cognito.py --reload
```

### Fixture Data Missing
```
AssertionError: Expected 7 users, got 0
```

**Solution:** Mock Cognito fixture data is in memory, loaded on startup. Restart Mock Cognito.

### Test Cleanup Issues
```
User "testuser1" already exists
```

**Solution:** Tests should clean up automatically. If not:
```bash
# Restart Mock Cognito to reset state
pkill -f mock_cognito
uv run python mock_cognito.py
```

### Wrong Port
```
404 Not Found
```

**Solution:** Verify port matches Mock Cognito:
```bash
# Check what port Mock Cognito is using
ps aux | grep mock_cognito

# Run tests with correct port
behave features/cognito_management.feature -D cognito_port=8100
```

## What Gets Tested

### ✅ User Operations
- [x] Create user with organisation
- [x] Get user with custom attributes
- [x] Update user organisation
- [x] Update user role
- [x] Delete user
- [x] List users
- [x] Filter users by organisation

### ✅ Organisation Operations
- [x] Query organisation members
- [x] Verify organisation structure
- [x] Count members per organisation
- [x] Verify access tiers

### ✅ Authentication
- [x] Login with valid credentials
- [x] Login failure with wrong password
- [x] Login failure with non-existent user
- [x] JWT token contains groups

### ✅ AWS Compatibility
- [x] AdminGetUser format (UserAttributes array)
- [x] AdminListUsers format (Users array)
- [x] AdminUpdateUserAttributes format
- [x] Custom attributes (custom:organisation_id, custom:role)

### ✅ Fixture Data
- [x] 7 users seeded correctly
- [x] 6 organisations represented
- [x] Correct custom attributes
- [x] Correct group memberships

## Best Practices

1. **Start Mock Cognito first** - Tests expect it to be running
2. **Use tags** - Run specific test categories with `--tags=@tag`
3. **Clean state** - Restart Mock Cognito between test runs for clean state
4. **Separate concerns** - Test Cognito separately from FRANK server
5. **Verify fixtures** - Run seeding tests first to verify base data

## Quick Reference

```bash
# Common commands
behave features/cognito_management.feature -D cognito_port=8100         # All tests
behave features/cognito_management.feature --tags=@seeding              # Fixture verification
behave features/cognito_management.feature --tags=@crud                 # CRUD operations
behave features/cognito_management.feature --tags=@organisations        # Org queries
behave features/cognito_management.feature --tags=@authentication       # Auth flows
behave features/cognito_management.feature --tags=@aws-compatibility    # AWS format
```

---

**For more information:** See `README_BDD.md` for general BDD testing guide
