# FRANK Implementation Plan - Stage 2: LocalStack + Dual Database

## Overview
This stage 2 is part of the 4-stage progressive development approach for FRANK (Feedback Infrastructure for Cyber Risk Analysis and Network Knowledge sharing), evolving from a local SQLite/FastAPI prototype to a scalable Cloud agnostic production system.

This stage implements the FRANK platform with LocalStack simulation for AWS services and dual database support (MySQL + DynamoDB) for performance comparison and learning.


**Technology Stack**:
- **Database**: MySQL (LocalStack RDS) + LocalStack DynamoDB (parallel testing)
- **API**: FastAPI
- **Location**: Local development with LocalStack
- **Submissions**: Minimal model (unchanged)

**NB:** RDS is now part of the professional license of LocalStack, we therefore run a separate MySQL Container. Of course you could also use the Pro license and go Localstack native. This this [site](https://docs.localstack.cloud/aws/licensing/#service-coverage-clarification) for more details on supported services.

**Key Learning Objectives**:
- AWS database service patterns (MySQL configuration, connection management)
- Docker containerization and service orchestration
- Database abstraction layer implementation
- LocalStack simulation environment setup

**Implementation Focus**:
- Dual database support (MySQL and DynamoDB side-by-side)
- Repository pattern for database abstraction
- Docker Compose orchestration
- Environment-based configuration management

**Success Criteria**:
- FastAPI application connects to both MySQL (LocalStack RDS) and DynamoDB
- Same Submission model works with both databases
- Performance comparison between SQL and NoSQL approaches
- Stable local development environment

**Risk Mitigation**:
- Fallback to Stage 1 (SQLite) always available
- Parallel database testing reduces commitment risk
- Infrastructure patterns learned apply to real AWS


For more details see the [/docs/implementation plan](../../docs/implementation_plan.md#Stage-2).

## Overview

**Stage 2 Goals:**
- ✅ AWS service simulation with LocalStack
- ✅ Dual database implementation (MySQL + DynamoDB)
- ✅ Performance comparison between SQL and NoSQL
- ✅ Container orchestration with Docker Compose
- ✅ Repository pattern for database abstraction
- ✅ Minimal submission model (preparing for Stage 4 expansion)

## Architecture

```
┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI App    │    │   LocalStack     │    │   Admin Tools   │
│   (Port 8000)    │    │   (Port 4566)    │    │   (Port 8001)   │
│                  │    │                  │    │                 │
│ ┌──────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │ Dual Repo    │ │◄──►│ │  DynamoDB    │ │    │ │DynamoDB GUI │ │
│ │  Manager     │ │    │ │              │ │    │ │(Port 8001)  │ │
│ └──────────────┘ │    │ └──────────────┘ │    │ └─────────────┘ │
│ ┌──────────────┐ │    │ ┌──────────────┐ │    │                 │
│ │MySQL Repo    │ │◄──┐│ │      S3      │ │    │                 │
│ │(Replacement) │ │   ││ │   (Future)   │ │    │                 │
│ └──────────────┘ │   ││ └──────────────┘ │    │                 │
│ ┌──────────────┐ │   │└──────────────────┘    └─────────────────┘
│ │DynamoDB Repo │ │   │
│ └──────────────┘ │   │
└──────────────────┘   │
                       │
                    ┌──▼──────────────────────┐
                    │    MySQL Container      │
                    │     (Port 3306)         │
                    │                         │
                    │ ┌─────────────────────┐ │
                    │ │   MySQL Database    │ │
                    │ │                     │ │
                    │ │ • frank_sightings   │ │
                    │ │ • frank_aggregates  │ │
                    │ │ • frank_submitters. │ │
                    │ │ • frank_idempotency │ │
                    │ └─────────────────────┘ │
                    └─────────────────────────┘
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Make (optional, for convenience commands)
- curl (for testing)

### Setup and Run

```bash
# 1. Clone and setup
git clone <your-repo>
cd frank-platform

# 2. Setup Stage 2 environment
make setup

# 3. Start all services
make up

# 4. Wait for services to be ready (about 30 seconds)
# Check status
make status

# 5. Test the API
make test-api
```

### Service URLs
- **FRANK API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **MySQL**: localhost:3306
- **DynamoDB Admin**: http://localhost:8001
- **LocalStack Dashboard**: http://localhost:4571

## Usage Examples

### Submit Threat Intelligence

```bash
# Submit to both databases (dual mode)
curl -X POST "http://localhost:8000/v1/submissions" \
  -H "Content-Type: application/json" \
  -d '{
    "submitter_org_id": "security-team-alpha",
    "observables": [
      {
        "type": "ipv4",
        "value": "203.0.113.42",
        "confidence": 90
      },
      {
        "type": "domain",
        "value": "malicious.example.com",
        "confidence": 85
      }
    ],
    "confidence": 87
  }'

# Submit to specific database
curl -X POST "http://localhost:8000/v1/submissions?database=dynamodb" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Query Data

```bash
# Get specific submission
curl "http://localhost:8000/v1/submissions/{submission_id}?database=dynamodb"

# List organisation submissions
curl "http://localhost:8000/v1/organisations/security-team-alpha/submissions"

# Get performance comparison
curl "http://localhost:8000/v1/performance"
```

### Generate Test Data

```bash
# Generate sample submissions for testing
make generate-data

# Or manually:
curl -X POST "http://localhost:8000/v1/test/generate-sample-data?count=10"
```

## Database Comparison

### MySQL Approach
```sql
-- Normalized relational design
CREATE TABLE submissions (
    submission_id VARCHAR(255) PRIMARY KEY,
    submitter_org_id VARCHAR(255) NOT NULL,
    confidence INT,
    submission_timestamp TIMESTAMP
);

CREATE TABLE observables (
    observable_id VARCHAR(255) PRIMARY KEY,
    submission_id VARCHAR(255) NOT NULL,
    observable_type VARCHAR(50),
    observable_value TEXT
);
```

### DynamoDB Approach
```python
# Single-table design
Table: frank-data-dev

# Submission record
PK: "ORG#security-team-alpha"
SK: "SUB#2025-01-15T10:30:00Z#uuid"
{
    "item_type": "submission",
    "submission_id": "uuid",
    "full_submission": {...}
}

# Observable record
PK: "OBS#ipv4#203.0.113.42"
SK: "SUB#uuid"
{
    "item_type": "observable",
    "observable_type": "ipv4",
    "observable_value": "203.0.113.42"
}
```

## Performance Testing

The system automatically tracks performance metrics for both databases:

```bash
# Run performance benchmark
make benchmark

# View performance data
make performance
```

**Sample Performance Output:**
```json
{
  "performance_summary": {
    "total_operations": 50,
    "databases": {
      "dynamodb": {
        "operations": 50,
        "avg_ms": 45.2,
        "min_ms": 23.1,
        "max_ms": 89.5
      },
      "rds": {
        "operations": 50,
        "avg_ms": 78.3,
        "min_ms": 45.2,
        "max_ms": 156.7
      }
    }
  }
}
```

## Configuration

### Environment Variables

```bash
# Stage 2 Configuration
FRANK_ENVIRONMENT=localstack

# LocalStack
ENDPOINT=http://localhost:4566

# RDS Settings
RDS_HOST=mysql
RDS_PORT=3066
RDS_DATABASE=frank
RDS_USERNAME=frank_user
RDS_PASSWORD=frank_pass

# DynamoDB Settings
DYNAMODB_TABLE=frank-data-dev
AWS_DEFAULT_REGION=eu-west-1

# AWS Credentials (LocalStack)
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
```

### Database Selection

The API supports three database modes:

1. **`database=dual`** (default): Save to both MySQL and DynamoDB
2. **`database=dynamodb`**: DynamoDB only
3. **`database=rds/mysql`**: MySQL/RDS only

## Development Workflow

### Daily Development
```bash
# Start development environment
make up

# Make code changes...

# Test changes
make test-api

# View logs
make logs-app

# Stop when done
make down
```

### Database Inspection
```bash
# Inspect RDS data
make db-inspect-rds
# Then visit http://localhost:8080

# Inspect DynamoDB data  
make db-inspect-dynamo
# Then visit http://localhost:8001
```

### Testing
```bash
# Run unit tests
make test

# Test specific functionality
make test-submission
make migrate-test
```

## Troubleshooting

### Common Issues

**LocalStack not starting:**
```bash
# Check Docker and try again
docker system prune -f
make down
make up
```

**Database connection errors:**
```bash
# Check LocalStack logs
make logs-localstack

# Restart LocalStack
docker-compose restart localstack
```

**Performance issues:**
```bash
# Check container resources
docker stats

# Increase LocalStack memory if needed
export LOCALSTACK_MEMORY=2048
```

### Debugging

```bash
# Open shell in application container
make shell

# View detailed logs
make logs

# Check service health
curl http://localhost:8000/v1/health
```

## Data Models

### Minimal Submission (Current Stage)
```python
class MinimalSubmission:
    submission_id: str
    submitter_org_id: str
    observables: List[SimpleObservable]
    confidence: Optional[int]
    submission_timestamp: datetime
    format_version: str = "1.0"

class SimpleObservable:
    id: str
    type: str  # ipv4, domain, hash, etc.
    value: str
    confidence: Optional[int]
```

This minimal model will be expanded to the maximum model in Stage 4 when we have stable infrastructure.

## Next Steps to Stage 3

Stage 2 prepares for Stage 3 (Lambda conversion) by:

1. ✅ **Repository Pattern**: Database abstraction ready for Lambda
2. ✅ **AWS Service Integration**: LocalStack experience transfers to real AWS
3. ✅ **Performance Baseline**: Know what to expect when converting to Lambda
4. ✅ **Container Experience**: Docker knowledge applies to Lambda packaging

**Ready for Stage 3 when:**
- [ ] Both databases work reliably
- [ ] Performance comparison shows acceptable metrics
- [ ] All API endpoints tested and working
- [ ] Development workflow established

## Clean Up

```bash
# Stop all services and clean up
make clean

# This removes:
# - All containers
# - All volumes
# - LocalStack data
# - Application logs
```

---

This Stage 2 implementation provides a solid foundation for learning AWS patterns while maintaining the flexibility to compare database approaches before committing to the final architecture in later stages.