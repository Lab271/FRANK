# Spike Index

Spikes are time-boxed experiments (1-4 hours) validating hypotheses before integration into the main codebase.

**For complete spike process documentation, see [ADR-0011: Spike Integration Process](../../.openspec/architecture/decisions/0011-spike-integration-process.md)**

## Status Legend

- **INTEGRATED**: Patterns adopted into main codebase, actively used in production
- **ACTIVE**: Currently being developed/validated
- **SUPERSEDED**: Replaced by newer approach
- **ABANDONED**: Did not prove viable

## Comprehensive Spike Overview

| # | Name | Status | Stages | Hypothesis | Key Learnings |
|---|------|--------|--------|------------|---------------|
| 001 | genparse | INTEGRATED | 1-4 | Can Python dataclasses provide maintainable, type-safe foundation for threat intelligence models? | Factory methods, type safety, YAML serialization patterns (later superseded by Pydantic v2) |
| 002 | filter | INTEGRATED | 1-4 | Can rule-based filtering provide granular access control while preserving analytical value? | Tier hierarchy, 6 filter actions (ALLOW/REMOVE/HASH/MASK/AGGREGATE/GENERALIZE) |
| 003 | pydantic | INTEGRATED | 1-4 | Can Pydantic v2 provide better validation than dataclasses while maintaining established patterns? | Performance improvements, field/model validators, forgiving input with `extra="ignore"` |
| 004 | sqlite | INTEGRATED | 1 | Can SQLite provide sufficient performance for local development with data integrity? | JSON columns, foreign keys, query performance for development volumes |
| 005 | server | INTEGRATED | 1-4 | Can FastAPI provide performance and security for production threat intelligence platform? | Async capabilities, auto-generated OpenAPI, middleware patterns |
| 006 | dynamodb | INTEGRATED | 2-3 | Can DynamoDB provide scalable cloud storage maintaining same interface as SQLite? | Single-table design, composite keys (PK/SK), GSI for lookups, LocalStack for dev |
| 007 | fastapi | INTEGRATED | 1-4 | Can comprehensive exception handling improve API reliability with consistent responses? | Custom HTTPException subclasses, RequestValidationError handling |
| 008 | aws_tf | ABANDONED | - | Terraform-based infrastructure as code for AWS | Superseded by Ansible-based deployment (spikes 009-013) |
| 009 | aws_ecs_basic | INTEGRATED | 3 | Can single containerized FastAPI app deploy to ECS Fargate with minimal infrastructure? | Fargate eliminates EC2 management, public subnet simplicity, foundation for scaling |
| 010 | aws_alb | INTEGRATED | 3 | Can ALB + private subnet achieve stable endpoints and improved security? | Stable DNS, health checks at `/v1/health`, private subnet security |
| 011 | aws_ssl | INTEGRATED | 3 | Can SSL termination at ALB provide production HTTPS with custom domain support? | ACM auto-renewal, Route 53 DNS, HTTP→HTTPS redirects |
| 012 | aws_dynamodb | INTEGRATED | 3 | Can DynamoDB + Multi-AZ provide production-ready scalable resilient architecture? | DynamoDB serverless scale, 99.9%+ availability, auto-scaling, ECS Task Roles |
| 013 | aws_observability | ACTIVE | 3 | Can CloudWatch provide comprehensive logging and monitoring patterns? | (Documentation in progress) |
| 014 | cognito | INTEGRATED | 3+ | Can AWS Cognito provide user auth and RBAC via incremental integration? | Mock Cognito 100% API compatibility, JWT tokens (HS256/RS256), zero code changes for migration |
| 015 | fastapi_testing | INTEGRATED | 1-4 | Can function-based FastAPI with pytest establish testable API framework? | `create_app()` pattern, 4 endpoint types, Bearer token auth, logging integration |

## Detailed Integration Status

### Foundation Layer (Spikes 001-007)

**Core Data Models**
- **001 genparse** → `src/frank/core/models.py` - Factory method patterns
- **003 pydantic** → `src/frank/core/models.py` - All core models (Observable, Submission, Sighting, etc.)

**Access Control & Storage**
- **002 filter** → `src/frank/storage/base.py` - Access tier filtering logic
- **004 sqlite** → `src/frank/storage/sqlite.py` - SQLite implementation (Stage 1)
- **006 dynamodb** → `src/frank/storage/dynamodb.py` - DynamoDB implementation (Stages 2-3)

**Server Patterns**
- **005 server** → `src/frank/util/server.py` + all stage implementations
- **007 fastapi** → `src/frank/util/server.py` - Exception handling patterns

### AWS Infrastructure (Spikes 009-013)

All AWS spikes integrated into **Stage 3** deployment:

- **009 aws_ecs_basic** → `stages/stage3/` - ECS Fargate container orchestration
- **010 aws_alb** → `ansible/playbook.yml` - Application Load Balancer with health checks
- **011 aws_ssl** → `ansible/playbook.yml` - SSL/TLS certificates and Route 53 DNS
- **012 aws_dynamodb** → `stages/stage3/` - DynamoDB tables, Multi-AZ deployment, auto-scaling
- **013 aws_observability** → `stages/stage3/` - CloudWatch logging architecture (ACTIVE)

### Authentication & Testing (Spikes 014-015)

- **014 cognito** → `tests/stubs/cognito/stub_cognito.py` + Stage 3 - AWS Cognito authentication, JWT tokens, custom attributes
- **015 fastapi_testing** → All stages - Comprehensive FastAPI testing patterns with pytest

## Stage Integration Matrix

| Component | Stage 1 | Stage 2 | Stage 3 | Stage 4 |
|-----------|---------|---------|---------|---------|
| **Core Models** (001, 003) | ✅ | ✅ | ✅ | ✅ |
| **Access Control** (002) | ✅ | ✅ | ✅ | ✅ |
| **SQLite Storage** (004) | ✅ | ✅ | ✅ | ✅ |
| **DynamoDB Storage** (006, 012) | - | ✅ | ✅ | ✅ |
| **FastAPI Server** (005, 007) | ✅ | ✅ | ✅ | ✅ |
| **ECS Fargate** (009) | - | - | ✅ | ✅ |
| **ALB + SSL** (010, 011) | - | - | ✅ | ✅ |
| **CloudWatch** (013) | - | - | ✅ | ✅ |
| **AWS Cognito** (014) | - | - | ✅ | ✅ |
| **Testing Patterns** (015) | ✅ | ✅ | ✅ | ✅ |

## Related ADRs

- [ADR-0011: Spike Integration Process](../../.openspec/architecture/decisions/0011-spike-integration-process.md) - Spike lifecycle and integration patterns
- [ADR-0002: Repository Pattern Database Abstraction](../../.openspec/architecture/decisions/0002-repository-pattern-database-abstraction.md) - Storage layer patterns (Spikes 004, 006)
- [ADR-0003: Tiered Access Control Model](../../.openspec/architecture/decisions/0003-tiered-access-control-model.md) - Access filtering (Spike 002)
- [ADR-0005: AWS Cognito Authentication](../../.openspec/architecture/decisions/0005-cognito-authentication.md) - Authentication patterns (Spike 014)
- [ADR-0007: Forgiving Input, Strong Output](../../.openspec/architecture/decisions/0007-forgiving-input-strong-output.md) - Pydantic validation (Spike 003)

## Evolution Timeline

```
Foundation (001-007)     AWS Infrastructure (009-013)     Advanced (014-015)
├─ 001 genparse          ├─ 009 aws_ecs_basic             ├─ 014 cognito
├─ 002 filter            ├─ 010 aws_alb                   └─ 015 fastapi_testing
├─ 003 pydantic          ├─ 011 aws_ssl
├─ 004 sqlite            ├─ 012 aws_dynamodb
├─ 005 server            └─ 013 aws_observability (ACTIVE)
├─ 006 dynamodb
├─ 007 fastapi
└─ 008 terraform (ABANDONED)
```

## Spike Development Process

**See [ADR-0011: Spike Integration Process](../../.openspec/architecture/decisions/0011-spike-integration-process.md) for complete lifecycle documentation.**

### Quick Reference: Creating a New Spike

1. Create folder with next sequential number: `NNN_descriptive_name/`
2. Add `README.md` with:
   - Clear hypothesis to validate
   - Expected outcomes and validation criteria
   - Time box (1-4 hours)
3. Implement validation code (tests ending in `_test.py` or `test_*.py`)
4. Document results and learnings

### Quick Reference: Completing a Spike

1. Update README with final status (INTEGRATED, ARCHIVED, ABANDONED)
2. Document "Integrated Into" paths with specific files
3. Capture key learnings and gotchas
4. Update this index with integration status and stage information

**Important:** Never directly promote spike code to production. Extract patterns and implement them properly in main codebase.

## Directory Structure

```
tests/spikes/
├── index.md                    # This file
├── 001_genparse/
│   ├── README.md               # Status: INTEGRATED
│   └── test_genparse.py
├── 002_filter/
│   ├── README.md               # Status: INTEGRATED
│   └── test_filter.py
├── 003_pydantic/
│   ├── README.md               # Status: INTEGRATED
│   └── test_pydantic.py
├── 004_sqlite/
│   ├── README.md               # Status: INTEGRATED
│   └── test_sqlite.py
├── 005_server/
│   ├── README.md               # Status: INTEGRATED
│   └── test_server.py
├── 006_dynamodb/
│   ├── README.md               # Status: INTEGRATED
│   └── test_dynamodb.py
├── 007_fastapi/
│   ├── README.md               # Status: INTEGRATED
│   └── test_fastapi.py
├── 008_aws_tf/
│   ├── README.md               # Status: ABANDONED
│   └── (Terraform exploration)
├── 009_aws_ecs_basic/
│   ├── README.md               # Status: INTEGRATED
│   └── (ECS Fargate deployment)
├── 010_aws_alb/
│   ├── README.md               # Status: INTEGRATED
│   └── (ALB configuration)
├── 011_aws_ssl/
│   ├── README.md               # Status: INTEGRATED
│   └── (SSL/TLS setup)
├── 012_aws_dynamodb/
│   ├── README.md               # Status: INTEGRATED
│   └── (DynamoDB + Multi-AZ)
├── 013_aws_observability/
│   ├── README.md               # Status: ACTIVE
│   └── (CloudWatch logging)
├── 014_cognito/
│   ├── README.md               # Status: INTEGRATED
│   └── (AWS Cognito auth)
└── 015_fastapi_testing/
    ├── README.md               # Status: INTEGRATED
    └── test_fastapi_testing.py
```

## Running Spike Tests

```bash
# Run all spike validation tests
uv run pytest tests/spikes/ -v

# Run tests for a specific spike
uv run pytest tests/spikes/001_genparse/ -v

# Run with coverage
uv run pytest tests/spikes/ --cov=src/frank --cov-report=term-missing
```

## Summary Statistics

- **Total Spikes**: 15
- **Integrated**: 13 (87%)
- **Active**: 1 (7%)
- **Abandoned**: 1 (7%)
- **Stage 1-4 Coverage**: 100% (all stages have multiple integrated spikes)
- **Core Models**: 3 spikes (001, 003, plus 002 for filtering)
- **Storage Layer**: 2 spikes (004 SQLite, 006 DynamoDB)
- **AWS Infrastructure**: 5 spikes (009-013)
- **Authentication**: 1 spike (014)
- **Testing**: 1 spike (015)
