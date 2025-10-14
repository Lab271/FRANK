# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FRANK (Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling) is a threat intelligence platform demonstrating a structured evolutionary approach to software development. The project separates infrastructure complexity from functional complexity while maintaining working systems at every stage.

**Key Principle**: One unified code library (`src/frank/`) containing all business logic that runs unchanged across all infrastructure stages (SQLite → DynamoDB → ScyllaDB). Infrastructure changes require only new repository implementations.

## Development Commands

### Essential Commands

```bash
# Setup development environment
make dev          # Create virtualenv and install all dependencies
make env          # Install packages into existing virtualenv

# Activate virtual environment
source .frank/bin/activate    # Or use 'venv' alias if configured

# Testing
make test         # Run unit tests with coverage (requires >=85% coverage)
pytest tests/unit/                    # Run only unit tests
pytest tests/spikes/ -k "*_test.py"   # Run spike validation tests
behave tests/integration/             # Run BDD integration tests

# Development workflow
make check        # Validate development dependencies (Python/pip/docker)
make freeze       # Freeze pip requirements to requirements.txt
make outdated     # List all outdated packages

# Code quality
make lint         # Run tests then ruff static analysis

# Other commands
make version      # Show Python, FRANK, and AWS CLI versions
make clean        # Clean all build files and virtualenv
make check        # Validate development dependencies (Python/pip/docker)
```

### Running Individual Stages

```bash
# Stage 1 - SQLite + FastAPI (local)
python stages/stage1/server.py

# Stage 3 - DynamoDB + ECS (AWS)
ansible-playbook ansible/playbook.yml --tags create
```

## Architecture

### Four-Stage Infrastructure Evolution

FRANK evolves through controlled complexity stages, each building on the previous:

1. **Stage 1**: SQLite + FastAPI on laptop (foundation, proof of concept)
2. **Stage 2**: MySQL/DynamoDB + FastAPI on LocalStack/Docker (AWS patterns, containerization)
3. **Stage 3**: DynamoDB + FastAPI on ECS in AWS Cloud (cloud-native deployment)
4. **Stage 4**: ScyllaDB/MongoDB + FastAPI/Go on Kubernetes (cloud-agnostic, production scale)

**Important**: Infrastructure learning happens in Stages 1-2. Complex submission models are introduced in Stage 3 once infrastructure is stable.

### Core Code Structure

```
src/frank/
├── core/              # Business logic and data models (infrastructure-independent)
│   ├── models.py      # Pydantic v2 models (Observable, Submission, Sighting, etc.)
│   ├── enum.py        # ObservableType, AccessTier, SeverityLevel enums
│   └── exceptions.py  # Domain exceptions
├── storage/           # Database abstraction layer
│   ├── base.py        # BaseFRANKDatabase abstract interface
│   ├── sqlite.py      # SQLite implementation (Stage 1)
│   └── dynamodb.py    # DynamoDB implementation (Stages 2-3)
└── util/              # Utilities (server, logging, filters, requests)

stages/
├── stage1/            # Local SQLite + FastAPI
├── stage2/            # LocalStack + Dual DB (MySQL/DynamoDB)
├── stage3/            # AWS Cloud + ECS + DynamoDB
└── stage4/            # Kubernetes + ScyllaDB
```

### Database Abstraction Pattern

All database implementations extend `BaseFRANKDatabase` (src/frank/storage/base.py) with these key methods:

- `store_submission(submission: Submission)` - Store threat intelligence submission
- `get_submission_by_id(submission_id: str)` - Retrieve submission with access filtering
- `query_observables(org_id, observable_type, ...)` - Query with access control
- `upsert_organisation(org_data)` - Manage organization records
- `health_check()` - Database health status

Access filtering is built into the base class (`_filter_submission_by_access_level`, `_filter_observable_by_access_level`) supporting PUBLIC, OBSERVER, CONTRIBUTOR, PARTNER, and CORE_MEMBER access tiers.

### Data Models (Pydantic v2)

The platform uses Pydantic v2 models following "be forgiving on input, strong on return" principle:

- [`Observable`](src/frank/core/models.py#L28) - Threat indicators (IPs, domains, hashes) with STIX-compliant IDs
- [`Submission`](src/frank/core/models.py#L371) - Complete threat intelligence submission
- [`Sighting`](src/frank/core/models.py#L290) - Observation details with observables
- [`Submitter`](src/frank/core/models.py#L88) - Submitting organization with access tier
- [`HitTarget`](src/frank/core/models.py#L143) - Affected organization with privacy controls
- [`Observables`](src/frank/core/models.py#L205) - Container for network/file/process observables
- [`ThreatContext`](src/frank/core/models.py#L259) - Campaign attribution and MITRE ATT&CK mapping

Models support:
- Factory methods: `Observable.create_ipv4()`, `Submission.create_minimal()`
- Legacy format parsing: `Submission.from_legacy_dict()`
- Serialization: `to_json()`, `to_yaml()`
- Automatic ID generation with STIX format
- Field normalization and validation

## Testing Strategy

FRANK uses three test layers for confident evolution:

1. **Unit Tests** (`tests/unit/`) - Fast (<100ms), isolated component testing
   - High coverage (≥85% required by CI/CD)
   - Test individual functions/classes with mocked dependencies
   - Run with: `pytest tests/unit/` or `make test`

2. **Integration Tests** (`tests/integration/`) - BDD/Behave tests for system confidence
   - Gherkin syntax for business scenarios
   - Test component interactions, API endpoints, database operations
   - Run with: `behave tests/integration/`

3. **Spike Tests** (`tests/spikes/`) - Hypothesis-driven learning and validation
   - Time-boxed investigations (1-4 hours) for new technologies
   - Files ending in `*_test.py` are part of pytest suite
   - Each spike has README.md documenting hypothesis, approach, results, decisions
   - Run validation tests: `pytest tests/spikes/ -k "*_test.py"`
   - Recent spikes: 010_cognito (AWS Cognito authentication), 011_fastapi (FastAPI testability patterns)

**Test Philosophy**: Tests are the safety net enabling aggressive experimentation. Database abstraction ensures all implementations behave identically.

**Test Organization**:
- `tests/unit/` - Core unit tests organized by module (core/, storage/, util/)
- `tests/integration/` - BDD tests with Gherkin feature files and step definitions
- `tests/spikes/` - Exploratory tests for new technologies and patterns
- `tests/parked/` - Temporarily disabled tests (e.g., MySQL implementation)

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/main.yml`):
- Triggers on pushes/PRs to main/develop branches affecting src/, tests/, or Python files
- Tests on Python 3.11 and 3.13 matrix
- Requires 85% minimum coverage (`--cov-fail-under=85`)
- Uploads test results and coverage reports (as artifacts)
- Comments PR with coverage percentage (excludes dependabot PRs)
- Uses pip caching for faster build times

## AWS Deployment (Stage 3)

Stage 3 uses Ansible for AWS infrastructure deployment:

```bash
# Deploy/update infrastructure
ansible-playbook ansible/playbook.yml --tags create

# Common tag combinations
--tags "ssl,docker"                    # SSL and Docker operations
--tags "cloudformation,deploy"         # Infrastructure and deployment
--tags "ssl,build,cloudformation,deploy"  # Full pipeline

# Cleanup
ansible-playbook ansible/playbook.yml --tags destroy
```

**Deployment Order**: Prerequisites → SSL Certificate → Docker Build/Push to ECR → DynamoDB Tables → CloudFormation (VPC, Security Groups, ALB, ECS, IAM) → Auto Scaling

**Key AWS Components**:
- **Networking**: Multi-AZ VPC with public (ALB) and private (ECS) subnets, zero-trust security groups
- **Compute**: ECS Fargate with auto-scaling (2-10 containers) based on CPU (70%), memory (80%), and request rate (1000 req/min per task)
- **Database**: DynamoDB main table (submissions, organizations, observables) and audit table (logs with TTL)
- **Health Checks**: 4 levels - Docker, ECS Task, ALB Target Group (`/v1/health`), Deep Application (`/v1/health/deep`)

## Code Patterns and Conventions

### When Adding New Features

1. Start with spike tests to validate approach (save in `tests/spikes/`)
2. Implement in core business logic (`src/frank/core/`)
3. If storage-related, update `BaseFRANKDatabase` interface and all implementations
4. Add unit tests achieving ≥85% coverage
5. Test across multiple stages to ensure abstraction works

### When Adding Database Storage

1. Define interface method in `src/frank/storage/base.py`
2. Implement in both `sqlite.py` and `dynamodb.py`
3. Ensure identical behavior across implementations (write tests!)
4. Consider access tier filtering requirements

### Pydantic Model Guidelines

- Use `ConfigDict(extra="ignore")` to be forgiving on input.
- Provide factory methods for common use cases.
- Implement `from_legacy_dict()` for backward compatibility.
- Use `model_validator(mode="after")` for cross-field validation.
- Always serialize datetimes as ISO strings with `field_serializer`.

### FastAPI Testing Patterns (Spike 011)

The 011_fastapi spike established comprehensive testing patterns for FastAPI applications:

- **Function-Based Architecture**: Use `create_app()` functions returning configured FastAPI instances for better testability
- **Bearer Token Authentication**: Implement `HTTPBearer` security with custom dependency functions
- **Exception Handling**: Support both standard HTTPException and custom exception extensions
- **Uvicorn Development**: Use argparse for `--reload` flag and configurable host/port
- **Test Structure**: Use pytest fixtures with `TestClient` for comprehensive endpoint testing
- **Authentication Testing**: Test valid tokens, invalid tokens, missing headers, and malformed headers
- **Logging Integration**: Implement middleware for request/response logging with timing

### FastAPI Testing Patterns (Spike 011)

The 011_fastapi spike established comprehensive testing patterns for FastAPI applications:

- **Function-Based Architecture**: Use `create_app()` functions returning configured FastAPI instances for better testability
- **Bearer Token Authentication**: Implement `HTTPBearer` security with custom dependency functions
- **Exception Handling**: Support both standard HTTPException and custom exception extensions
- **Uvicorn Development**: Use argparse for `--reload` flag and configurable host/port
- **Test Structure**: Use pytest fixtures with `TestClient` for comprehensive endpoint testing
- **Authentication Testing**: Test valid tokens, invalid tokens, missing headers, and malformed headers
- **Logging Integration**: Implement middleware for request/response logging with timing

### Running Single Tests

```bash
# Run specific test file
pytest tests/unit/core/test_models.py

# Run specific test function
pytest tests/unit/core/test_models.py::test_observable_creation

# Run tests matching pattern
pytest -k "observable"

# Verbose output with coverage
pytest tests/unit/ -v --cov=src/frank --cov-report=term-missing
```

## Important Notes

- **Never break Stage 1**: It's the development baseline. All stages must maintain fallback capability.
- **Coverage requirement**: Tests must maintain ≥85% coverage (CI fails below 85%)
- **Git tags**: Functional milestones use version tags (0.1.0, 0.2.0, etc.)
- **Documentation**: Each spike must have README.md capturing hypothesis, results, and decisions
- **Ruff configuration**: Line length limit is 120 characters (pyproject.toml)
- **AWS profiles**: Development uses `spike-account` profile, main account for SSL certificates
- **Python versions**: Support 3.11 and 3.13 (tested in CI)
- **Testing tools**: pytest 8.4.2, coverage 7.10.7 with C extension

## Recent Developments

### Spike 010: AWS Cognito Authentication
Time-boxed exploration of AWS Cognito integration for user authentication, token management, and secure API access patterns.

### Spike 011: FastAPI Testability Validation
Established comprehensive patterns for:
- Function-based FastAPI architecture for improved testability
- Bearer token authentication with HTTPBearer security
- Exception handling (standard and custom HTTPException extensions)
- Uvicorn development workflow with hot-reload
- Comprehensive pytest testing patterns with TestClient
- Request/response logging middleware

These patterns are now applicable across all FRANK API implementations.

## Evolutionary Design Philosophy

Read `docs/evolutionary_design.md` before making architectural changes. Key principles:

- Structured evolution over big-bang development
- One complexity dimension at a time
- Working systems at every stage
- Comprehensive testing enables confident experimentation
- Infrastructure complexity separated from functional complexity
- Single library approach ensures consistency across stages

## Dependency Management

- **Package Management**: Uses setuptools with dynamic versioning via setuptools_scm
- **Version File**: Auto-generated `src/frank/__version__.py` from git tags
- **Requirements**: Frozen requirements in `requirements.txt` (use `make freeze` to update)
- **Virtual Environment**: `.frank/` directory (created by `make dev` or `make env`)
- **Dependency Checking**: `make outdated` lists packages needing updates
- **Build System**: Modern pyproject.toml configuration (PEP 621)
