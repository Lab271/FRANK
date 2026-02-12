# Stage 1: Foundation - SQLite + FastAPI

## Overview

Stage 1 establishes the foundation for FRANK's evolutionary development approach. It focuses on core business logic, data models, and baseline functionality using the simplest possible infrastructure: SQLite database and FastAPI running directly on your laptop.

**Purpose**: Proof of concept, development baseline, rapid iteration
**Technology Stack**: SQLite (local file), FastAPI (Python web framework)
**Location**: Local development (macOS/Linux native Python)
**Submissions**: Minimal model (Observable, Submitter, Sighting only)
**Key Learning Objectives**: Core FRANK concepts, data modeling, API design
**Implementation Focus**: Business logic over infrastructure complexity

## Architecture

### Simple Stack
```
┌─────────────────────────────────────┐
│  FastAPI Application                │
│  - REST API endpoints               │
│  - Pydantic v2 models               │
│  - Access tier filtering            │
└──────────┬──────────────────────────┘
           │
           ↓
┌─────────────────────────────────────┐
│  SQLite Database (frank.db)         │
│  - Single file on disk              │
│  - Normalized schema                │
│  - No network overhead              │
└─────────────────────────────────────┘
```

**Data Flow**:
1. Client sends HTTP request to FastAPI
2. FastAPI validates with Pydantic models
3. BaseFRANKDatabase interface processes request
4. SQLiteDatabase implementation executes SQL
5. Results filtered by access tier
6. JSON response returned to client

## Quick Start

### Prerequisites

- Python 3.11 or 3.13
- `uv` package manager (recommended) or `pip`
- Git (for cloning repository)

### Setup

```bash
# Clone repository
git clone https://github.com/LAB271/FRANK.git
cd FRANK

# Install dependencies
uv sync                     # Using uv (recommended)
# OR
pip install -e .            # Using pip

# Activate virtual environment
source .venv/bin/activate   # Or your venv alias
```

### Running Stage 1

**Option 1: Direct Python execution**
```bash
python stages/stage1/server.py
```

**Option 2: Environment-based approach**
```bash
cd environments/local-python
cp .env.stage1.example .env
./run-stage1.sh
```

**Access the API**:
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Database File: `./frank.db` (created automatically)

## Implementation Focus

### Core Business Logic

Stage 1 concentrates on **business logic over infrastructure complexity**:

- ✅ Pydantic v2 data models with validation
- ✅ Observable types (IPv4, IPv6, Domain, URL, Hash, Email)
- ✅ Access tier system (PUBLIC, OBSERVER, CONTRIBUTOR, PARTNER, CORE_MEMBER)
- ✅ STIX-compliant ID generation
- ✅ Submission workflow with validation
- ✅ RESTful API design patterns

### What Stage 1 Does NOT Include

- ❌ Container orchestration (added in Stage 2)
- ❌ Cloud deployment (added in Stage 3)
- ❌ Complex submission models (added in Stage 3)
- ❌ AWS Cognito authentication (added in Stage 3)
- ❌ Multiple database options (added in Stage 2)

## Key Learning Objectives

1. **FRANK Core Concepts**
   - Threat intelligence submissions
   - Observable classification
   - Access tier filtering
   - Organization management

2. **Data Modeling**
   - Pydantic v2 validation patterns
   - STIX-compliant identifiers
   - Relational database normalization

3. **API Design**
   - RESTful endpoint patterns
   - FastAPI dependency injection
   - OpenAPI documentation

4. **Development Workflow**
   - Local iteration without infrastructure overhead
   - Unit testing with pytest
   - Debugging with native Python tools

## Success Criteria

Stage 1 is successful when:

- ✅ FastAPI server starts without errors
- ✅ Health check endpoint returns 200 OK
- ✅ Can create submissions with observables
- ✅ Can query submissions by organization
- ✅ Access tier filtering works correctly
- ✅ Unit tests pass with ≥85% coverage
- ✅ Database file created and persisted

## Configuration

### Environment Variables

```bash
# Database
FRANK_DB_PATH=./frank.db       # SQLite database file location

# Server
HOST=0.0.0.0                   # Bind address (default: 0.0.0.0)
PORT=8000                      # Port number (default: 8000)
RELOAD=true                    # Auto-reload on code changes
LOG_LEVEL=info                 # Logging level (debug, info, warning, error)

# Environment
FRANK_ENVIRONMENT=local-python # Deployment target
FRANK_STAGE=1                  # Infrastructure stage
```

### Database Schema

SQLite schema includes tables:
- `submissions` - Threat intelligence submissions
- `submitters` - Organization information
- `sightings` - Observation details
- `observables` - Threat indicators (IPs, domains, hashes, etc.)
- `hit_targets` - Affected organizations

All tables use STIX-compliant IDs and maintain referential integrity.

## Contributing Spikes

Stage 1 integrated the following validated spikes:

| Spike | Focus | Integration |
|-------|-------|-------------|
| [001_genparse](../../tests/spikes/001_genparse/) | Dataclass validation patterns | `src/frank/core/models.py` |
| [002_filter](../../tests/spikes/002_filter/) | Access-tier filtering logic | `src/frank/storage/base.py` |
| [003_pydantic](../../tests/spikes/003_pydantic/) | Pydantic v2 migration | `src/frank/core/models.py` |
| [004_sqlite](../../tests/spikes/004_sqlite/) | SQLite storage implementation | `src/frank/storage/sqlite.py` |
| [005_server](../../tests/spikes/005_server/) | FastAPI server patterns | `stages/stage1/server.py` |
| [007_fastapi](../../tests/spikes/007_fastapi/) | Exception handling | `src/frank/util/server.py` |

See [tests/spikes/index.md](../../tests/spikes/index.md) for complete spike documentation.

## Testing

### Running Tests

```bash
# All unit tests
uv run pytest tests/unit/ -v

# Stage 1 specific tests
uv run pytest tests/unit/storage/test_sqlite.py -v

# With coverage
uv run pytest tests/unit/ --cov=src/frank --cov-report=term-missing
```

### Integration Tests

```bash
# BDD tests (requires running server)
behave tests/integration/
```

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'frank'`
```bash
# Solution: Install package in editable mode
uv pip install -e .
```

**Issue**: `sqlite3.OperationalError: database is locked`
```bash
# Solution: Close other connections to frank.db
rm frank.db  # Delete and restart (loses data)
```

**Issue**: Port 8000 already in use
```bash
# Solution: Use different port
PORT=8001 python stages/stage1/server.py
```

**Issue**: Tests failing with coverage below 85%
```bash
# Solution: Add tests for uncovered code paths
uv run pytest tests/unit/ --cov=src/frank --cov-report=html
# Open htmlcov/index.html to see coverage details
```

## Next Steps to Stage 2

Once comfortable with Stage 1, progress to Stage 2 to learn:

- **Containerization**: Docker Compose for service orchestration
- **Database Abstraction**: PostgreSQL and DynamoDB implementations
- **AWS Patterns**: LocalStack for AWS service simulation
- **Dual Database Support**: Compare SQL vs NoSQL approaches

Stage 2 builds on Stage 1's business logic without changing it - only the infrastructure evolves.

See [stages/stage2/README.md](../stage2/README.md) for Stage 2 documentation.

## Fallback

Stage 1 **is the baseline** - there is no simpler fallback. All other stages can fall back to Stage 1 if infrastructure issues arise.

## Related Documentation

- [ADR-0001: Four-Stage Infrastructure Evolution](../../.openspec/architecture/decisions/0001-four-stage-infrastructure-evolution.md) - Stage rationale
- [ADR-0010: Stages vs Environments](../../.openspec/architecture/decisions/0010-stages-vs-environments.md) - Stage/environment distinction
- [Implementation Plan](../../docs/implementation_plan.md) - Detailed roadmap
- [Evolutionary Design](../../docs/evolutionary_design.md) - Design philosophy
- [environments/local-python/README.md](../../environments/local-python/README.md) - Deployment guide

---

*Last updated: 2026-02-01*
