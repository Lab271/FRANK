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
source .venv/bin/activate    # Or use 'venv' alias if configured

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

### Running FRANK Environments

```bash
# Local Docker - Stage 3 (Full stack with Web GUI)
cd environments/local-docker
make stage3

# Local Docker - Stage 1 (SQLite only)
cd environments/local-docker
make stage1

# Local Python - Stage 1 (SQLite, native Python)
cd environments/local-python
cp .env.stage1.example .env
./run-stage1.sh

# AWS Deployment - Stage 3
cd environments/aws-dev/stage3  # or aws-preprod, aws-prod
cp .env.stage3.example .env.stage3
ansible-playbook ../../ansible/playbook.yml --tags create
```

See **[environments/README.md](environments/README.md)** for complete documentation.

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
│   ├── sqlite.py      # SQLite implementation (Stage 1, all methods)
│   ├── dynamodb.py    # DynamoDB implementation (Stages 2-3, threat intelligence only)
│   └── postgresql.py  # PostgreSQL implementation (Management API only)
└── util/              # Utilities (server, logging, filters, requests)

environments/
├── local-docker/      # Docker Compose (all stages)
├── local-python/      # Python virtualenv (all stages)
├── aws-dev/           # AWS development (Stage 3)
├── aws-preprod/       # AWS pre-production (Stage 3)
└── aws-prod/          # AWS production (Stage 3)

stages/                # Legacy: being migrated to environments/ and tests/spikes/
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

#### Database Implementation Status

**SQLite** (`sqlite.py`): ✅ All methods fully implemented
- Complete implementation for all stages
- Single-file database for local development
- Supports all BaseFRANKDatabase methods

**DynamoDB** (`dynamodb.py`): ⚠️ Partial implementation
- ✅ Threat intelligence operations (submissions, observables, sightings)
- ❌ 20 methods raise `NotImplementedError` with fallback guidance:
  - Organisation CRUD (10 methods) - redirects to SQLite/PostgreSQL
  - API key management (6 methods) - not needed (AWS Cognito handles auth)
  - Refresh token management (4 methods) - not needed (AWS Cognito handles tokens)
- **Design**: DynamoDB handles high-volume threat data; PostgreSQL handles management data

**PostgreSQL** (`postgresql.py`): ✅ Management API operations
- ✅ Organisation management (CRUD operations)
- ✅ Organisation member management
- ✅ Refresh token storage (for logout tracking)
- ❌ Threat intelligence operations - use DynamoDB instead
- **Purpose**: Management API backend (organisations, members) in cloud deployments

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
   - **All spikes** (001-015): genparse, filter, pydantic, sqlite, server, dynamodb, fastapi, aws_tf, aws_ecs_basic, aws_alb, aws_ssl, aws_dynamodb, aws_observability, cognito, fastapi_testing
   - See spike README files for hypothesis, results, and integration status

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

## Specification-Driven Development (SDD)

FRANK uses **specification-driven development** to maintain context and build converging, high-quality systems. Specifications are written BEFORE code to define requirements, contracts, and behavior.

**Core Principle**: specs → code + unit tests + BDD + ADRs

### Directory Structure

```
specs/
├── README.md              # SDD guide and usage
├── _template.spec.md      # Standard specification template
├── core/                  # Core data model specifications (5 specs)
│   ├── submission.spec.md
│   ├── observable.spec.md
│   ├── sighting.spec.md
│   ├── submitter-target.spec.md
│   └── enums.spec.md
├── apis/                  # API endpoint specifications (3 specs)
│   ├── sightings-api.spec.md
│   ├── management-api.spec.md
│   └── authentication.spec.md
├── storage/               # Database layer specifications (4 specs)
│   ├── base-interface.spec.md
│   ├── sqlite.spec.md
│   ├── dynamodb.spec.md
│   └── postgresql.spec.md
└── changes/               # OpenSpec-style change proposals
    ├── _template/         # Change proposal template
    │   ├── proposal.md    # Why we need this change
    │   ├── spec.md        # What it should do
    │   ├── design.md      # How to implement it
    │   ├── tasks.md       # Implementation checklist
    │   └── adr.md         # Architectural decisions
    └── archive/           # Completed changes
```

### When to Create Specs

**ALWAYS create specs for**:
- New features (API endpoints, data models, background jobs)
- Significant refactoring affecting multiple files
- Database schema changes or new storage implementations
- Authentication/authorization changes
- Performance-critical components
- Any change affecting multiple FRANK stages

**Skip specs for** (lightweight changes):
- Bug fixes (unless architectural)
- Documentation updates
- Simple typo corrections
- Minor test additions
- Well-established patterns already documented

### Workflow: Spec → Test → Code → ADR

**Step 1: Create Specification**
```bash
# For core models, APIs, storage
cp specs/_template.spec.md specs/core/new-model.spec.md

# For new features (OpenSpec-style)
cp -r specs/changes/_template specs/changes/001-background-tasks
# Edit: proposal.md → spec.md → design.md → tasks.md → adr.md
```

**Step 2: Write Tests Based on Spec**
```bash
# Unit tests for requirements
# FR1: Model validation → test_model_validation()
# FR2: Factory methods → test_factory_methods()

# BDD tests for behavior
# Scenario: User submits threat intelligence
# Given authenticated user with PARTNER tier
# When POST /submit with observables
# Then submission stored with STIX ID
```

**Step 3: Implement Code Following Spec**
```python
# Follow spec contracts exactly
# Use Pydantic schemas from spec
# Implement all methods listed in spec
# Add docstrings referencing spec sections
```

**Step 4: Extract Decisions to ADR**
```bash
# If spec contains architectural decisions:
# specs/changes/001-background-tasks/adr.md
# → .openspec/architecture/decisions/00XX-background-task-queue.md

# Link spec ↔ ADR bidirectionally
```

**Step 5: Archive Completed Change**
```bash
# Move to archive with status update
mv specs/changes/001-background-tasks specs/changes/archive/
```

### Using Existing Specs

**Before modifying code**, check if spec exists:

```bash
# Find relevant spec
ls specs/core/          # Data models
ls specs/apis/          # API endpoints
ls specs/storage/       # Database layers

# Read spec before changing code
cat specs/core/submission.spec.md

# Verify implementation matches spec
# Check: Requirements section
# Check: API contracts
# Check: Test coverage requirements
```

**Example: Adding Observable Type**

```bash
# 1. Read current spec
cat specs/core/observable.spec.md

# 2. Update spec with new type
# Add to ObservableType enum: CERTIFICATE
# Add validation rules for X.509 format
# Update test coverage requirements

# 3. Write tests
pytest tests/unit/core/test_observable.py -k certificate

# 4. Implement in code
# src/frank/core/enum.py: Add CERTIFICATE to ObservableType
# src/frank/core/models.py: Add certificate validation

# 5. Verify against spec
make test  # Must pass with ≥85% coverage
```

### Integration with Existing Workflows

**With Evolutionary Design**:
- Specs document evolution across stages (1 → 4)
- Show which features work in which stages
- Link to stage-specific implementations

**With Spike Tests**:
- Spike results inform spec creation
- Validated patterns from spikes → formal specs
- Spike READMEs reference resulting specs

**With ADRs**:
- Major spec decisions → ADR documents
- ADRs explain "why", specs explain "what"
- Bidirectional linking maintained

**With Git Worktrees**:
- Each worktree can work on separate change proposals
- Specs in specs/changes/XXX-feature/ are isolated
- Parallel development without conflicts

### AI Agent Guidelines

**For AI agents working on FRANK**:

1. **Before implementing**, read relevant specs:
   ```bash
   # Implementing submission endpoint?
   cat specs/apis/sightings-api.spec.md
   cat specs/core/submission.spec.md
   ```

2. **Follow spec contracts exactly**:
   - Request/response schemas must match
   - Validation rules must be implemented
   - Error responses must match documented codes
   - Access tier filtering must work as specified

3. **Update specs when requirements change**:
   - Don't change code without updating spec
   - Keep spec and implementation synchronized
   - Link spec updates in commit messages

4. **Create change proposals for new features**:
   ```bash
   # New feature: Background task processing
   specs/changes/002-background-tasks/
   ├── proposal.md   # Problem and business value
   ├── spec.md       # Requirements and API contracts
   ├── design.md     # Implementation approach
   └── tasks.md      # Step-by-step checklist
   ```

5. **Validate implementations against specs**:
   - All FR requirements implemented? ✅
   - Test coverage ≥85%? ✅
   - API contracts match exactly? ✅
   - Access control working? ✅

### Quick Reference

**Comprehensive Guide**: See [SPEC-DRIVEN-DEVELOPMENT.md](SPEC-DRIVEN-DEVELOPMENT.md) for complete workflow documentation, diagrams, and examples.

**Templates**:
- Standard spec: `specs/_template.spec.md`
- Change proposal: `specs/changes/_template/`

**Existing Specs**:
- Core models: `specs/core/` (5 specs)
- APIs: `specs/apis/` (3 specs)
- Storage: `specs/storage/` (4 specs)

**Related Documentation**:
- [specs/README.md](specs/README.md) - Directory structure and usage
- [SPEC-DRIVEN-DEVELOPMENT.md](SPEC-DRIVEN-DEVELOPMENT.md) - Complete workflow guide
- [docs/evolutionary_design.md](docs/evolutionary_design.md) - Evolutionary philosophy

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

### Completed Spikes (001-015)

All 15 spikes have been completed and integrated into the FRANK platform. Key learnings:

**Early Spikes (001-007)**: Core patterns and local development
- 001_genparse: Submission generation and parsing
- 002_filter: Access tier filtering logic
- 003_pydantic: Pydantic v2 model validation
- 004_sqlite: SQLite database implementation
- 005_server: FastAPI server patterns
- 006_dynamodb: DynamoDB integration basics
- 007_fastapi: FastAPI application structure

**AWS Infrastructure Spikes (008-013)**: Cloud deployment
- 008_aws_tf: Terraform infrastructure as code
- 009_aws_ecs_basic: ECS Fargate container orchestration
- 010_aws_alb: Application Load Balancer setup
- 011_aws_ssl: SSL/TLS certificate management
- 012_aws_dynamodb: DynamoDB table design for threat intelligence
- 013_aws_observability: CloudWatch logging and monitoring

**Authentication & Testing Spikes (014-015)**: Production readiness
- 014_cognito: AWS Cognito authentication integration, JWT validation, service accounts
- 015_fastapi_testing: Comprehensive FastAPI testing patterns with TestClient

See `tests/spikes/*/README.md` for detailed hypothesis, approach, and integration status for each spike.

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
