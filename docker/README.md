# FRANK Platform - Docker Setup

Docker containers for local development and deployment.

## Quick Start

### Start All Services

```bash
# Using make (recommended)
make docker-up

# Or directly with docker-compose
docker-compose -f docker-compose.local.yml up -d
```

### Access Points

Once started, services are available at:

- **Web GUI**: http://localhost:3000
- **Management API**: http://localhost:8001/docs (OpenAPI documentation)
- **Mock Cognito**: http://localhost:8100/health

### View Logs

```bash
# All services
make docker-logs

# Or specific service
docker-compose -f docker-compose.local.yml logs -f web-gui
docker-compose -f docker-compose.local.yml logs -f management-api
docker-compose -f docker-compose.local.yml logs -f mock-cognito
```

### Stop Services

```bash
make docker-down
```

## Services

### Web GUI (frank-web-gui)

Web-based user interface for organisation and user management.

- **Port**: 3000
- **Dockerfile**: `docker/Dockerfile.web`
- **Image**: Based on Python 3.13-slim
- **Dependencies**: Management API, Mock Cognito

### Management API (frank-management-api)

REST API for organisation and user CRUD operations.

- **Port**: 8001
- **Dockerfile**: `docker/Dockerfile.management`
- **Image**: Based on Python 3.13-slim
- **Database**: SQLite (persisted in docker volume)
- **Documentation**: http://localhost:8001/docs

### Mock Cognito (frank-mock-cognito)

Mock AWS Cognito service for local authentication.

- **Port**: 8100
- **Dockerfile**: `tests/spikes/014_cognito/Dockerfile.cognito`
- **Features**: RS256 JWT signing, user pool simulation

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key variables:

```bash
# Ports
WEB_GUI_PORT=3000
MANAGEMENT_API_PORT=8001
MOCK_COGNITO_PORT=8100

# Development
LOG_LEVEL=info
RELOAD=false                    # Hot-reload (true for development)
TEMPLATE_AUTO_RELOAD=false      # Template hot-reload (true for web dev)

# Session Security
FRANK_SESSION_SECRET=your-secret-key-here  # Change in production!
```

### Hot-Reload Development

Enable automatic code reloading:

```bash
# In .env file
RELOAD=true
TEMPLATE_AUTO_RELOAD=true

# Then restart services
make docker-down
make docker-up
```

**Note**: Hot-reload requires mounting source code as volumes. Add to `docker-compose.local.yml`:

```yaml
services:
  web-gui:
    volumes:
      - ./src:/app/src:ro
      - ./src/frank/web/templates:/app/src/frank/web/templates:ro
```

## Building Images

### Build All Images

```bash
make docker-build
```

### Build Specific Image

```bash
docker build -f docker/Dockerfile.web -t frank-web:latest .
docker build -f docker/Dockerfile.management -t frank-management:latest .
```

### Multi-Platform Builds

Build for both AMD64 (AWS Fargate) and ARM64 (M1/M2 Mac, AWS Graviton):

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -f docker/Dockerfile.web \
  -t frank-web:latest .
```

## Data Persistence

### SQLite Database

The Management API uses SQLite with data persisted in a Docker volume:

```bash
# View volume
docker volume inspect frank-data

# Backup database
docker cp frank-management-api:/data/frank.db ./backup-$(date +%Y%m%d).db

# Restore database
docker cp ./backup.db frank-management-api:/data/frank.db
```

### Reset Database

```bash
# Stop services
make docker-down

# Remove volume
docker volume rm frank-data

# Restart (creates fresh database)
make docker-up
```

## Health Checks

All services have health check endpoints:

```bash
# Web GUI
curl http://localhost:3000/health

# Management API
curl http://localhost:8001/health

# Mock Cognito
curl http://localhost:8100/health
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs
make docker-logs

# Check container status
docker-compose -f docker-compose.local.yml ps

# Rebuild images
make docker-build
make docker-up
```

### Port Conflicts

If ports are already in use, override in `.env`:

```bash
WEB_GUI_PORT=3001
MANAGEMENT_API_PORT=8002
MOCK_COGNITO_PORT=8101
```

### Permission Errors

All containers run as non-root user (`frankuser`). If you see permission errors:

```bash
# Check volume permissions
docker volume inspect frank-data

# Recreate volume
docker volume rm frank-data
make docker-up
```

## Network Architecture

Services communicate via internal Docker network (`frank-net`):

```
┌────────────────────────────────────────────────────────────┐
│                    Docker Network: frank-net                │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐           ┌─────────────────┐            │
│  │   Web GUI    │──────────▶│ Management API  │            │
│  │   :3000      │  HTTP/JSON│     :8001       │            │
│  │  (public)    │           │   (internal)    │            │
│  └──────────────┘           └────────┬────────┘            │
│         │                             │                     │
│         │                             │                     │
│         │                    ┌────────▼────────┐            │
│         └───────────────────▶│  Mock Cognito   │            │
│                      Auth    │     :8100       │            │
│                              │   (internal)    │            │
│                              └─────────────────┘            │
│                                                             │
│  Volume: frank-data (SQLite database)                       │
└────────────────────────────────────────────────────────────┘

External Access:
- localhost:3000  → web-gui (exposed)
- localhost:8001  → management-api (exposed)
- localhost:8100  → mock-cognito (exposed)
```

## Production Considerations

### Security

- **Change session secret**: Set strong `FRANK_SESSION_SECRET` (min 32 chars)
- **Use HTTPS**: Configure TLS termination (ALB, nginx, traefik)
- **Disable mock Cognito**: Use real AWS Cognito in production
- **Environment variables**: Use secrets management (AWS Secrets Manager, HashiCorp Vault)

### Deployment

- Use multi-stage builds for smaller images
- Set resource limits in production orchestration
- Configure proper health checks and auto-restart policies
- Use real database (RDS, Aurora) instead of SQLite volume

## Related Documentation

- [Project README](../README.md) - Overall project documentation
- [CLAUDE.md](../CLAUDE.md) - Development workflow and patterns
- [Evolutionary Design](../docs/evolutionary_design.md) - Architecture philosophy
