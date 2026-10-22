# FRANK Platform - Docker Containers

Shared Dockerfiles for FRANK application services.

These Dockerfiles are used across all environments (local-docker, aws-dev, aws-preprod, aws-prod).

## Container Images

### Dockerfile.management
Management API container (Port 8001)
- FastAPI REST API for organisation and user CRUD
- PostgreSQL/SQLite support
- Mock/AWS Cognito authentication

### Dockerfile.web
Web GUI container (Port 3000)
- Jinja2-templated user interface
- Session-based authentication
- Organisation and user management

### Dockerfile.admin (Future)
Admin API container (Port 8002)
- Administrative operations
- System configuration

## Quick Start

For local development, use the environment-specific setups:

### Local Docker Environment

```bash
cd environments/local-docker

# Start Stage 3 (full stack)
make stage3

# Or start Stage 2 (PostgreSQL + DynamoDB)
make stage2

# Or start Stage 1 (SQLite only)
make stage1
```

### Local Python Environment

```bash
cd environments/local-python

# Copy and configure .env
cp .env.stage3.example .env
vi .env

# Run Stage 3
./run-stage3.sh
```

See [`environments/README.md`](../environments/README.md) for complete environment documentation.

## Service Details

### Management API (frank-management-api)
- **Port**: 8001
- **Dockerfile**: `Dockerfile.management`
- **Base Image**: Python 3.13-slim
- **Database**: PostgreSQL or SQLite
- **Authentication**: Mock Cognito or AWS Cognito
- **API Docs**: http://localhost:8001/docs (when running)

### Web GUI (frank-web-gui)
- **Port**: 3000
- **Dockerfile**: `Dockerfile.web`
- **Base Image**: Python 3.13-slim
- **Dependencies**: Management API, Cognito
- **Template Engine**: Jinja2

### Admin API (future)
- **Port**: 8002
- **Dockerfile**: `Dockerfile.admin`
- **Purpose**: Administrative operations and system configuration

## Configuration

Environment-specific configuration is located in:
- `environments/local-docker/.env.example` - Docker Compose configuration
- `environments/local-python/.env.stage*.example` - Python virtualenv configuration
- `environments/aws-*/stage3/.env.stage3.example` - AWS deployment configuration

See environment READMEs for detailed configuration options.

## Building Images

### Build from Environment Directory

```bash
cd environments/local-docker
docker compose build
```

### Build Specific Image

```bash
# From project root
docker build -f docker/Dockerfile.management -t frank-management:latest .
docker build -f docker/Dockerfile.web -t frank-web:latest .
```

### Multi-Platform Builds

Build for AMD64 (AWS Fargate) and ARM64 (M1/M2 Mac, AWS Graviton):

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -f docker/Dockerfile.management \
  -t frank-management:latest .

docker buildx build --platform linux/amd64,linux/arm64 \
  -f docker/Dockerfile.web \
  -t frank-web:latest .
```

## Container Features

### Multi-Stage Builds
All Dockerfiles use multi-stage builds:
- **Builder stage**: Compiles dependencies with gcc/g++
- **Production stage**: Minimal runtime image with only necessary packages

### Non-Root User
Containers run as `frankuser` (non-root) for security.

### Health Checks
Built-in health check endpoints:
- Management API: `http://localhost:8001/health`
- Web GUI: `http://localhost:3000/health`

### Platform Support
- **linux/amd64**: AWS Fargate, x86_64 servers
- **linux/arm64**: Apple Silicon (M1/M2/M3), AWS Graviton

## Production Considerations

### Security
- Change `FRANK_SESSION_SECRET` (min 32 chars)
- Use HTTPS/TLS termination (ALB, nginx)
- Use AWS Cognito (not mock Cognito)
- Use AWS Secrets Manager for credentials

### Resource Limits
Configure in ECS task definitions or Kubernetes:
- CPU: 0.5-1 vCPU per container
- Memory: 512MB-1GB per container

### Database
- **Development**: SQLite or PostgreSQL
- **Production**: RDS PostgreSQL (Multi-AZ)

## Related Documentation

- **[Environments Guide](../environments/README.md)** - Environment-specific deployment
- **[Local Docker](../environments/local-docker/README.md)** - Docker Compose development
- **[Local Python](../environments/local-python/README.md)** - Python virtualenv development
- **[AWS Deployment](../environments/aws-prod/README.md)** - Production AWS deployment
- **[Project README](../README.md)** - Overall project documentation
- **[CLAUDE.md](../CLAUDE.md)** - Development workflow and patterns
