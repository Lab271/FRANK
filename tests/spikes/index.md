# Spike Index

Spikes are time-boxed experiments validating hypotheses before integration into the main codebase.

## Status Legend

- **INTEGRATED**: Patterns adopted into main codebase
- **ACTIVE**: Currently being developed/validated
- **SUPERSEDED**: Replaced by newer approach
- **ABANDONED**: Did not prove viable

## Spikes

| # | Name | Status | Integrated Into | Description |
|---|------|--------|-----------------|-------------|
| 001 | genparse | INTEGRATED | src/frank/core/models.py | Dataclass validation patterns |
| 002 | filter | INTEGRATED | src/frank/storage/base.py | Access-tier filtering |
| 003 | pydantic | INTEGRATED | src/frank/core/models.py | Pydantic v2 models |
| 004 | sqlite | INTEGRATED | src/frank/storage/sqlite.py | SQLite storage layer |
| 005 | server | INTEGRATED | stages/stage1/ | FastAPI server patterns |
| 006 | dynamodb | INTEGRATED | src/frank/storage/dynamodb.py | DynamoDB storage layer |
| 007 | fastapi | INTEGRATED | src/frank/util/server.py | Exception handling patterns |
| 008 | terraform | ABANDONED | - | Terraform IaC exploration |
| 009 | aws_ecs_basic | INTEGRATED | stages/stage3/ | Basic ECS Fargate deployment |
| 010 | aws_alb | INTEGRATED | stages/stage3/ | Application Load Balancer |
| 011 | aws_ssl | INTEGRATED | stages/stage3/ | SSL/TLS termination |
| 012 | aws_dynamodb | INTEGRATED | stages/stage3/ | Multi-AZ + DynamoDB |
| 013 | aws_observability | ACTIVE | - | Logging architecture |
| 014 | cognito | INTEGRATED | stages/stage3/ | AWS Cognito auth |
| 015 | fastapi_testing | INTEGRATED | all stages | FastAPI testing patterns |

## Evolution Timeline

```
Foundation (001-007)     AWS Infrastructure (009-013)     Advanced (014-015)
├─ 001 genparse          ├─ 009 aws_ecs_basic             ├─ 014 cognito
├─ 002 filter            ├─ 010 aws_alb                   └─ 015 fastapi_testing
├─ 003 pydantic          ├─ 011 aws_ssl
├─ 004 sqlite            ├─ 012 aws_dynamodb
├─ 005 server            └─ 013 aws_observability
├─ 006 dynamodb
├─ 007 fastapi
└─ 008 terraform (abandoned)
```

## Spike Development Process

### Creating a New Spike

1. Create folder with next sequential number: `NNN_descriptive_name/`
2. Add `README.md` with:
   - Hypothesis to validate
   - Expected outcomes
   - Validation criteria
3. Implement validation code (tests ending in `_test.py` or `test_*.py`)
4. Document results and learnings

### Completing a Spike

1. Update README with final status
2. Document "Integrated Into" paths
3. Capture key learnings
4. Update this index

## Directory Structure

```
tests/spikes/
├── index.md                    # This file
├── 001_genparse/
│   ├── README.md
│   └── test_genparse.py
├── 002_filter/
│   ├── README.md
│   └── test_filter.py
├── ...
├── 009_aws_ecs_basic/
│   ├── README.md
│   ├── Dockerfile
│   └── ...
└── 015_fastapi_testing/
    ├── README.md
    └── ...
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
