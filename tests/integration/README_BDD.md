# FRANK BDD Tests with Command-Line Parameters

This guide shows how to run Behave BDD tests with configurable parameters.

## Quick Start

```bash
# Default (port 8000)
behave

# Custom server port
behave -D server_port=8080

# Custom server URL
behave -D server_url=http://localhost:8080

# Multiple parameters
behave -D server_port=8080 -D cognito_port=8100
```

## Available Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `server_url` | `http://localhost:8000` | Full API server URL |
| `server_port` | `8000` | API server port (builds URL) |
| `server_host` | `localhost` | API server hostname |
| `cognito_url` | `http://localhost:8100` | Cognito server URL |
| `cognito_port` | `8100` | Cognito server port |
| `timeout` | `30` | Request timeout in seconds |
| `verify_ssl` | `false` | Verify SSL certificates |
| `observer_token` | `observer_test_token` | Observer test token |
| `contributor_token` | `contributor_test_token` | Contributor test token |
| `partner_token` | `partner_test_token` | Partner test token |
| `core_member_token` | `core_test_token` | Core member test token |

## Common Scenarios

### 1. Test Against Simple API (Port 8080)

```bash
# Simple API runs on port 8080, Mock Cognito on 8100
behave -D server_port=8080 -D cognito_port=8100
```

### 2. Test Against Management API (Port 8000)

```bash
# Management API runs on port 8000
behave -D server_port=8000
```

### 3. Test Against Docker Compose Setup

```bash
# Services behind nginx on port 443
behave -D server_url=https://localhost:443 -D verify_ssl=false
```

### 4. Test Against Remote Server

```bash
# Remote server with real tokens
behave \
  -D server_url=https://api.frank.example.com \
  -D verify_ssl=true \
  -D partner_token="eyJhbGc..." \
  -D core_member_token="eyJhbGc..."
```

### 5. Run Specific Features/Scenarios

```bash
# Run specific feature file
behave features/frank_api.feature -D server_port=8080

# Run scenarios with specific tag
behave --tags=@health -D server_port=8080

# Run scenarios excluding a tag
behave --tags=~@slow -D server_port=8080

# Dry run to see what would be executed
behave --dry-run -D server_port=8080
```

## Using Environment Variables

Alternative to `-D` flags, you can set environment variables:

```bash
export API_BASE_URL=http://localhost:8080
export COGNITO_URL=http://localhost:8100
behave
```

**Note:** `-D` flags take precedence over environment variables.

## Configuration Priority

1. Command-line `-D` parameters (highest priority)
2. Environment variables
3. Default values (lowest priority)

## Example: Full Test Run Script

Create a test script `run_bdd_tests.sh`:

```bash
#!/bin/bash
# Run FRANK BDD tests against different configurations

set -e

echo "=== Testing Simple API (port 8080) ==="
behave -D server_port=8080 -D cognito_port=8100 --tags=@api

echo ""
echo "=== Testing Management API (port 8000) ==="
behave -D server_port=8000 --tags=@management

echo ""
echo "=== Testing Health Checks ==="
behave -D server_port=8080 --tags=@health

echo ""
echo "✅ All BDD tests passed!"
```

Make it executable:
```bash
chmod +x run_bdd_tests.sh
./run_bdd_tests.sh
```

## Output Options

### Pretty Format (Default)
```bash
behave -D server_port=8080
```

### JSON Output
```bash
behave -D server_port=8080 --format json --outfile results.json
```

### JUnit XML Output (for CI/CD)
```bash
behave -D server_port=8080 --junit --junit-directory results/
```

### Verbose Output
```bash
behave -D server_port=8080 --verbose
```

### Show Timings
```bash
behave -D server_port=8080 --show-timings
```

## Debugging

### Show Configuration
Configuration is logged at test start:
```
INFO: ============================================================
INFO: FRANK BDD Test Configuration
INFO: ============================================================
INFO: API Base URL: http://localhost:8080
INFO: Cognito URL: http://localhost:8100
INFO: Timeout: 30s
INFO: Verify SSL: False
INFO: ============================================================
```

### Capture Logs
```bash
behave -D server_port=8080 --logging-level DEBUG --logcapture
```

### Stop on First Failure
```bash
behave -D server_port=8080 --stop
```

### Run Single Scenario
```bash
behave features/frank_api.feature:25 -D server_port=8080
```
(Line 25 is the scenario start line)

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: BDD Tests
on: [push, pull_request]

jobs:
  bdd-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install behave requests hamcrest

      - name: Start services
        run: |
          docker compose up -d
          sleep 10  # Wait for services

      - name: Run BDD tests
        run: |
          behave \
            -D server_port=8080 \
            -D cognito_port=8100 \
            --junit \
            --junit-directory test-results/

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: bdd-results
          path: test-results/
```

## Testing Multiple Ports in Sequence

```bash
#!/bin/bash
# Test against multiple server configurations

PORTS=(8000 8080 8090)

for port in "${PORTS[@]}"; do
  echo "Testing port $port..."
  if behave -D server_port=$port --tags=@health; then
    echo "✅ Port $port: PASSED"
  else
    echo "❌ Port $port: FAILED"
    exit 1
  fi
done

echo "✅ All ports tested successfully!"
```

## Troubleshooting

### Connection Refused
```
requests.exceptions.ConnectionError: [Errno 61] Connection refused
```

**Solution:** Verify server is running on the specified port
```bash
# Check if service is listening
lsof -i :8080
netstat -an | grep 8080

# Start the service if needed
python stages/stage1/server.py --port 8080
```

### Wrong Port Configured
```
404 Not Found
```

**Solution:** Verify you're using the correct port
```bash
# Check which port your service is actually running on
ps aux | grep python
docker ps  # for containerized services
```

### SSL Certificate Errors
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Solution:** Disable SSL verification for self-signed certificates
```bash
behave -D server_url=https://localhost -D verify_ssl=false
```

## Best Practices

1. **Use `-D` flags for local development** - Easy to change on the fly
2. **Use environment variables for CI/CD** - Keeps secrets secure
3. **Tag your scenarios** - Use `@health`, `@api`, `@integration` for selective runs
4. **Start services before tests** - Use `docker compose up -d` or startup scripts
5. **Clean up after tests** - Remove test data or reset database state

## Example Feature with Tags

```gherkin
@health
Feature: Health Checks
  Scenario: API health endpoint responds
    Given the FRANK API is running
    When I query the health endpoint
    Then the response status should be 200

@api @authentication
Feature: Authentication
  Scenario: Valid token grants access
    Given I am authenticated as a partner user
    When I query protected endpoint
    Then the response status should be 200
```

Run health checks only:
```bash
behave --tags=@health -D server_port=8080
```

Run everything except authentication:
```bash
behave --tags=~@authentication -D server_port=8080
```

---

**For more information:** `behave --help`
