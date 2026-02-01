# FRANK Main API (Sightings API)

Threat intelligence submission and query API for the FRANK platform.

## Overview

The Main API is the core threat intelligence interface for FRANK, handling:
- **Submission**: Service accounts submit threat sightings with observables
- **Query**: Authenticated users query observables and statistics
- **Access Control**: Tiered access filtering based on Cognito JWT tokens

This API complements the Management API (user/org administration) in FRANK's dual-API architecture.

## Quick Start

### Local Development

```bash
# Set environment variables
export FRANK_ENVIRONMENT=local-docker
export FRANK_STAGE=3
export DYNAMODB_ENDPOINT=http://localhost:4566  # LocalStack
export COGNITO_URL=http://localhost:8100       # Stub Cognito

# Start dependencies (Stub Cognito + LocalStack)
cd environments/local-docker
docker compose up -d

# Run Main API with hot-reload
python -m frank.main.server --port 8002 --reload

# Visit API documentation
open http://localhost:8002/docs
```

### Production (AWS)

```bash
export FRANK_ENVIRONMENT=aws-prod
export FRANK_STAGE=3
export AWS_REGION=eu-west-1

# Run on ECS (managed by CloudFormation/Ansible)
# Environment variables injected via ECS task definition
```

## API Endpoints

### Health

- `GET /health` - Basic health check
- `GET /health/deep` - Component health (database, auth)

### Authentication

- `POST /auth/login` - Service account login
  ```json
  {
    "username": "service-rabobank-ingestion",
    "password": "secret"
  }
  ```
  Returns JWT access token and refresh token.

- `POST /auth/refresh` - Refresh access token (placeholder)

### Submission

- `POST /submit` - Submit threat intelligence (requires auth)
  ```json
  {
    "timestamp": "2026-02-01T10:00:00Z",
    "observables": [
      {"observable_type": "ipv4", "value": "192.0.2.1", "role": "C2"},
      {"observable_type": "domain", "value": "evil.example.com"}
    ],
    "confidence_score": 0.8,
    "severity": "HIGH",
    "description": "Malicious C2 infrastructure"
  }
  ```
  Returns submission ID.

- `GET /submissions/{id}` - Retrieve submission (requires auth, access filtered)

### Query

- `GET /observables` - Query observables (requires auth)
  - Query params: `observable_type`, `limit`, `offset`
  - Returns access-filtered observables

- `GET /statistics` - Platform statistics (requires auth)
  - Query params: `days` (default: 30)
  - Returns submission counts, observable types, contributors

## Authentication

### Service Account Pattern

Service accounts authenticate like human users but with `service-*` naming:

```python
import requests

# 1. Login
response = requests.post(
    "http://localhost:8002/auth/login",
    json={
        "username": "service-rabobank-ingestion",
        "password": os.environ["FRANK_SERVICE_PASSWORD"]
    }
)
tokens = response.json()
access_token = tokens["access_token"]

# 2. Submit threat intelligence
response = requests.post(
    "http://localhost:8002/submit",
    headers={"Authorization": f"Bearer {access_token}"},
    json={
        "observables": [
            {"observable_type": "ipv4", "value": "192.0.2.1"}
        ],
        "confidence_score": 0.7
    }
)
submission = response.json()
print(f"Submission ID: {submission['submission_id']}")
```

### Access Tiers

JWT tokens contain Cognito groups that map to access tiers:

| Cognito Group | Access Tier | Permissions |
|---------------|-------------|-------------|
| FRANK_OBSERVER | OBSERVER | Statistics only, masked observables |
| FRANK_CONTRIBUTOR | CONTRIBUTOR | Submit sightings, query own data |
| FRANK_PARTNER | PARTNER | Full submission access, anonymized targets |
| FRANK_CORE_MEMBER | CORE_MEMBER | Full access including audit logs |

Access filtering is applied automatically via the repository layer.

## Environment Configuration

The Main API uses `EnvironmentConfig` to determine database and auth services:

### Local Environments

**local-python** (native Python):
```bash
FRANK_ENVIRONMENT=local-python
SQLITE_DB_PATH=/tmp/frank_main.db
COGNITO_URL=http://localhost:8100
```

**local-docker** (Docker Compose):
```bash
FRANK_ENVIRONMENT=local-docker
DYNAMODB_ENDPOINT=http://localstack:4566
COGNITO_URL=http://stub-cognito:8100
```

### AWS Environments

**aws-dev** / **aws-preprod** / **aws-prod**:
```bash
FRANK_ENVIRONMENT=aws-prod
FRANK_STAGE=3
AWS_REGION=eu-west-1
DYNAMODB_TABLE=frank-submissions
# Cognito URL constructed from region automatically
```

## Database Integration

### DynamoDB (Preferred)

For local development with LocalStack:
```bash
DYNAMODB_ENDPOINT=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
DYNAMODB_TABLE=frank-submissions
```

For AWS production:
```bash
AWS_REGION=eu-west-1
DYNAMODB_TABLE=frank-submissions
# AWS credentials from IAM role (ECS task execution)
```

### SQLite (Fallback)

If DynamoDB is unavailable, Main API falls back to SQLite:
```bash
SQLITE_DB_PATH=/tmp/frank_main.db
```

## Architecture

### Request Flow

```
Service Account → POST /auth/login → Cognito → JWT Token
                ↓
Service Account → POST /submit → Main API → Validate JWT → DynamoDB
                                    ↓
                            Access Tier Filtering
                                    ↓
                            Store Submission
```

### Access Filtering

```
User queries submission → JWT validated → Access tier extracted
                              ↓
                    Repository layer filters data
                              ↓
                    Return filtered submission
```

### Data Models

Main API uses shared models from `frank.core.models`:
- `Observable` - Threat indicators (IPs, domains, hashes)
- `Submission` - Complete threat intelligence submission
- `Sighting` - Observation details
- `Submitter` - Organisation context

## Testing

### Unit Tests

```bash
# Run Main API unit tests
uv run pytest tests/unit/main/ -v

# With coverage
uv run pytest tests/unit/main/ --cov=src/frank/main --cov-report=term-missing
```

### Integration Tests

```bash
# Start test environment
cd environments/local-docker
docker compose up -d

# Run BDD tests
behave tests/integration/ -k main_api
```

### Manual Testing

```bash
# Start server
python -m frank.main.server --port 8002 --reload

# Health check
curl http://localhost:8002/health

# Login (requires Stub Cognito running)
curl -X POST http://localhost:8002/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Submit sighting (replace TOKEN with access_token from login)
curl -X POST http://localhost:8002/submit \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "observables": [
      {"observable_type": "ipv4", "value": "192.0.2.1", "role": "C2"}
    ],
    "confidence_score": 0.8
  }'
```

## Related Documentation

- **High-Level Design**: `docs/highlevel_design.md` (Section 3: Sightings API)
- **ADR-0005**: Cognito Authentication Strategy
- **ADR-0003**: Tiered Access Control Model
- **ADR-0009**: PostgreSQL for Management API (separation rationale)
- **Spike 015**: FastAPI Testability Validation (patterns used)
- **Management API**: `src/frank/management/README.md` (companion API)

## Development

### Module Structure

```
src/frank/main/
├── __init__.py     # Package exports
├── api.py          # FastAPI app with endpoints
├── models.py       # Request/response models
└── server.py       # Uvicorn entry point
```

### Adding New Endpoints

1. Define request/response models in `models.py`
2. Implement endpoint in `api.py` with proper auth
3. Add unit tests in `tests/unit/main/test_api.py`
4. Update this README with endpoint documentation

### Command-Line Options

```bash
python -m frank.main.server --help

Options:
  --host HOST           Host to bind (default: 0.0.0.0)
  --port PORT           Port to run on (default: 8002)
  --reload              Enable auto-reload for development
  --log-level LEVEL     Logging level (debug/info/warning/error)
  --environment ENV     FRANK environment (overrides FRANK_ENVIRONMENT)
  --stage STAGE         Infrastructure stage 1-4 (overrides FRANK_STAGE)
```

## Troubleshooting

### Database Connection Fails

**Symptom**: `Database not configured` or connection errors

**Solution**:
- Local: Ensure LocalStack is running (`docker compose up localstack`)
- AWS: Check IAM role permissions for DynamoDB access
- Check environment variables: `DYNAMODB_ENDPOINT`, `AWS_REGION`

### Authentication Fails

**Symptom**: `401 Unauthorized` responses

**Solution**:
- Local: Ensure Stub Cognito is running (`docker compose up stub-cognito`)
- AWS: Check Cognito User Pool configuration
- Verify JWT token is valid and not expired
- Check `COGNITO_URL` environment variable

### Access Denied for Queries

**Symptom**: `404 Not Found` or empty results

**Explanation**: Access tier filtering may hide data
- OBSERVER tier sees masked observables
- CONTRIBUTOR tier sees own submissions only
- PARTNER/CORE_MEMBER see full data

**Solution**: Check user's Cognito groups match expected access tier

## Performance

### Recommended Configuration

**Local Development**:
- SQLite: Single process, ~100 req/sec
- LocalStack DynamoDB: Multi-process, ~500 req/sec

**AWS Production**:
- DynamoDB on-demand: Auto-scales to demand
- ECS Fargate: 2-10 tasks based on CPU/memory/request rate
- Expected: ~2000 req/sec with 5 tasks

### Optimization Tips

1. **Use pagination**: Limit queries to 100-1000 results
2. **Cache tokens**: Reuse JWT tokens (1-hour validity)
3. **Batch submissions**: Group observables into single submission
4. **Monitor metrics**: Use CloudWatch to track response times

## Security

### Best Practices

✅ **DO**:
- Use service accounts for automated submission
- Rotate service passwords every 90 days
- Validate all input data
- Log all authentication attempts
- Use HTTPS in production

❌ **DON'T**:
- Store JWT tokens in localStorage
- Share service account credentials
- Submit sensitive data without encryption
- Bypass authentication for "testing"

### Audit Logging

All operations are logged with:
- Username and access tier
- Timestamp and operation
- Request parameters
- Success/failure status

Logs available in:
- Local: Console output
- AWS: CloudWatch Logs

## License

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
