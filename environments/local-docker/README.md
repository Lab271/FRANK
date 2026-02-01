# Local Docker Environment

Run FRANK stages in Docker containers on your laptop.

## Overview

- **Environment**: `local-docker`
- **Deployment**: Docker Compose
- **Database**: Containerized (PostgreSQL, Mock Cognito, LocalStack DynamoDB)
- **Best for**: Integration testing, AWS simulation, production-like local setup

## Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose v2+
- 8GB+ RAM recommended

## Quick Start

### Run All Services (Stage 3 Full Stack)

```bash
make up
# or
docker compose up -d
```

**Access:**
- Web GUI: http://localhost:3000
- Management API: http://localhost:8001/docs
- Mock Cognito: http://localhost:8100/health

### Run Specific Stage

```bash
# Stage 1 (SQLite + FastAPI)
make up-stage1

# Stage 2 (PostgreSQL/DynamoDB + LocalStack)
make up-stage2

# Stage 3 (Full stack with Mock Cognito)
make up-stage3
```

## Available Services

| Service | Stage | Port | Description |
|---------|-------|------|-------------|
| **postgres** | 2, 3 | 5432 | PostgreSQL database |
| **localstack** | 2, 3 | 4566 | AWS service emulation (DynamoDB, S3) |
| **mock-cognito** | 3 | 8100 | Authentication stub service |
| **management-api** | 3 | 8001 | User/org management REST API |
| **web-gui** | 3 | 3000 | Web interface |
| **frank-api** | 1, 2, 3 | 8000 | Main sightings API |

## Configuration

### Environment Files

```bash
# Stage 1 (SQLite)
.env.stage1           # Active config
.env.stage1.example   # Template

# Stage 2 (PostgreSQL/DynamoDB)
.env.stage2
.env.stage2.example

# Stage 3 (Full stack)
.env.stage3
.env.stage3.example
```

All `.env` files include:
```bash
FRANK_ENVIRONMENT=local-docker
```

### Copy Example Configuration

```bash
# For your working stage
cp .env.stage3.example .env.stage3
```

## Docker Compose Files

| File | Purpose | Usage |
|------|---------|-------|
| `docker-compose.yml` | Unified stack (all services) | Default `docker compose up` |
| `docker-compose.stage1.yml` | Stage 1 only (SQLite) | `docker compose -f docker-compose.stage1.yml up` |
| `docker-compose.stage2.yml` | Stage 2 (PostgreSQL/DynamoDB) | `docker compose -f docker-compose.stage2.yml up` |
| `docker-compose.stage3.yml` | Stage 3 (full stack) | `docker compose -f docker-compose.stage3.yml up` |

## Makefile Commands

### Start/Stop

```bash
make up               # Start all services
make up-stage1        # Start Stage 1 services only
make up-stage2        # Start Stage 2 services only
make up-stage3        # Start Stage 3 services only
make down             # Stop all services
make restart          # Restart all services
```

### Logs

```bash
make logs             # All services
make logs-api         # Main API only
make logs-mgmt        # Management API only
make logs-web         # Web GUI only
```

### Build

```bash
make build            # Build all images
make build-stage1     # Build Stage 1 image
make build-stage2     # Build Stage 2 image
make build-stage3     # Build Stage 3 image
```

### Health Checks

```bash
make health           # Check all services
curl http://localhost:8000/health     # Main API
curl http://localhost:8001/health     # Management API
curl http://localhost:3000/health     # Web GUI
curl http://localhost:8100/health     # Mock Cognito
```

## Data Persistence

### Volumes

```bash
# List volumes
docker volume ls | grep frank

# Inspect volume
docker volume inspect local-docker_postgres-data

# Remove volumes (WARNING: deletes data)
docker volume rm local-docker_postgres-data
```

### Database Backup

```bash
# PostgreSQL backup
docker exec frank-postgres pg_dump -U frank frank_management > backup.sql

# Restore
docker exec -i frank-postgres psql -U frank frank_management < backup.sql
```

## Troubleshooting

### Services won't start

```bash
# Check logs
make logs

# Check container status
docker ps -a

# Rebuild images
make build
make up
```

### Port conflicts

Edit `.env` file:
```bash
WEB_GUI_PORT=3001
MANAGEMENT_API_PORT=8002
MOCK_COGNITO_PORT=8101
```

### Out of memory

```bash
# Check Docker resource limits
docker stats

# Increase Docker Desktop memory (Settings → Resources)
# Recommended: 8GB minimum
```

### Reset everything

```bash
# Stop and remove all
make down
docker system prune -a --volumes

# Start fresh
make build
make up
```

## Development Workflow

### Hot-Reload

Enable in `.env`:
```bash
RELOAD=true
TEMPLATE_AUTO_RELOAD=true
```

Mount source code (add to docker-compose.yml):
```yaml
services:
  frank-api:
    volumes:
      - ../../src:/app/src:ro
```

### Run Tests in Container

```bash
docker exec -it frank-api pytest tests/unit/
docker exec -it frank-management-api pytest tests/unit/
```

## Integration with CI/CD

This environment is used for:
- ✅ Integration tests in GitHub Actions
- ✅ Pre-deployment validation
- ✅ LocalStack AWS simulation

See `.github/workflows/` for CI/CD usage.

## Related

- **Python alternative**: `environments/local-python/` - Run directly on laptop
- **AWS deployment**: `environments/aws-dev/` - Real cloud deployment
- **Documentation**: `docs/environments.md` - Comprehensive guide
