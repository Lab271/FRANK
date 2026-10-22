# Local Python Environment

Run FRANK stages natively on your laptop using Python in a virtual environment.

## Overview

- **Environment**: `local-python`
- **Deployment**: Native Python 3.11+ execution
- **Database**: File-based (SQLite for Stage 1, can use PostgreSQL/LocalStack for Stage 2/3)
- **Best for**: Development, debugging, fast iteration

## Prerequisites

- Python 3.11 or 3.13
- `uv` package manager (recommended) or `pip`
- Virtual environment activated

## Setup

### 1. Create Virtual Environment

```bash
# Using project's Makefile
make dev

# Or manually with uv
uv venv
source .venv/bin/activate  # or 'venv' alias if configured
```

### 2. Install Dependencies

```bash
make env
# or
uv pip install -e .
```

### 3. Configure Environment

Copy the appropriate `.env` file for your stage:

```bash
# For Stage 1 (SQLite)
cp .env.stage1.example .env

# For Stage 2 (PostgreSQL/DynamoDB)
cp .env.stage2.example .env

# For Stage 3 (Full stack)
cp .env.stage3.example .env
```

Edit `.env` and customize as needed.

## Running Stages

### Stage 1: SQLite + FastAPI

```bash
./run-stage1.sh

# Or manually
python stages/stage1/server.py
```

**Access:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

### Stage 2: PostgreSQL/DynamoDB + LocalStack

```bash
# Requires PostgreSQL and LocalStack running
# Start services first (use environments/local-docker/)
cd ../local-docker
make up-postgres up-localstack

# Then run Stage 2
cd ../local-python
./run-stage2.sh

# Or manually
python stages/stage2/frank_stage2.py
```

### Stage 3: Full Stack

```bash
# Requires all services (PostgreSQL, Mock Cognito, DynamoDB)
cd ../local-docker
make up-stage3-services

# Then run Stage 3
cd ../local-python
./run-stage3.sh

# Or manually
python stages/stage3/frank_stage3.py
```

## Environment Variables

All `.env` files must include:

```bash
# Environment identifier (DO NOT CHANGE)
FRANK_ENVIRONMENT=local-python

# Stage-specific settings
# (varies by .env.stage1, .env.stage2, .env.stage3)
```

## Testing

```bash
# Run unit tests
make test

# Run with coverage
pytest tests/unit/ --cov=src/frank --cov-report=term-missing

# Run specific test file
pytest tests/unit/core/test_models.py
```

## Debugging

Advantages of local Python vs Docker:
- ✅ Set breakpoints in IDE
- ✅ Hot-reload with `--reload` flag
- ✅ Direct access to logs
- ✅ Faster startup (no container build)
- ✅ Easy dependency inspection

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use IDE debugger (VS Code, PyCharm)
```

## Troubleshooting

### ImportError: No module named 'frank'

```bash
# Reinstall in editable mode
uv pip install -e .
```

### Database connection errors

```bash
# Check PostgreSQL is running (for Stage 2/3)
docker ps | grep postgres

# Check LocalStack (for Stage 2/3)
docker ps | grep localstack
```

### Port already in use

```bash
# Find process using port 8000
lsof -ti:8000 | xargs kill -9

# Or change port in .env
PORT=8001
```

## Related

- **Docker alternative**: `environments/local-docker/` - Same stages in containers
- **AWS deployment**: `environments/aws-dev/` - Cloud deployment
- **Documentation**: `docs/environments.md` - Comprehensive guide
