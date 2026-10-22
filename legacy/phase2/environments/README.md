# FRANK Environments

This directory contains environment-specific configurations and deployment files for FRANK platform.

## Overview

FRANK separates **Stages** (infrastructure complexity) from **Environments** (deployment targets):

- **Stages** = What infrastructure complexity level (Stage 1: SQLite, Stage 2: PostgreSQL/DynamoDB, Stage 3: AWS ECS)
- **Environments** = Where the code runs (Local Python, Local Docker, AWS Dev/Preprod/Prod)

## Available Environments

### Local Development

| Environment | Directory | Purpose | Stages Supported |
|------------|-----------|---------|------------------|
| **Local Python** | `local-python/` | Native Python on laptop (virtualenv) | 1, 2, 3 |
| **Local Docker** | `local-docker/` | Docker Compose on laptop | 1, 2, 3 |

### AWS Cloud

| Environment | Directory | Purpose | Stages Supported |
|------------|-----------|---------|------------------|
| **AWS Dev** | `aws-dev/` | AWS development account | 3 |
| **AWS Pre-Prod** | `aws-preprod/` | AWS staging environment | 3 |
| **AWS Prod** | `aws-prod/` | AWS production environment | 3 |

## Quick Start

### Run Stage 1 (SQLite) Locally

**Python:**
```bash
cd environments/local-python
./run-stage1.sh
```

**Docker:**
```bash
cd environments/local-docker
make up-stage1
```

### Run Stage 3 (Full Stack) in AWS Dev

```bash
cd environments/aws-dev/stage3
make deploy
```

## Environment Variables

Each environment uses the `FRANK_ENVIRONMENT` variable to identify itself:

```bash
# Local Python
FRANK_ENVIRONMENT=local-python

# Local Docker
FRANK_ENVIRONMENT=local-docker

# AWS environments
FRANK_ENVIRONMENT=aws-dev
FRANK_ENVIRONMENT=aws-preprod
FRANK_ENVIRONMENT=aws-prod
```

## Directory Structure

```
environments/
├── local-python/          # Native Python execution
│   ├── .env.stage1        # SQLite config
│   ├── .env.stage2        # PostgreSQL/DynamoDB config
│   ├── .env.stage3        # Local testing config
│   ├── run-stage1.sh      # Launch scripts
│   ├── run-stage2.sh
│   ├── run-stage3.sh
│   └── README.md
│
├── local-docker/          # Docker Compose
│   ├── docker-compose.yml          # Unified stack
│   ├── docker-compose.stage1.yml   # Stage 1 specific
│   ├── docker-compose.stage2.yml   # Stage 2 specific
│   ├── docker-compose.stage3.yml   # Stage 3 specific
│   ├── .env.stage1
│   ├── .env.stage2
│   ├── .env.stage3
│   ├── Makefile
│   └── README.md
│
├── aws-dev/               # AWS development
│   ├── stage3/
│   │   ├── ansible/      # Deployment automation
│   │   └── .env.stage3
│   └── README.md
│
├── aws-preprod/           # AWS pre-production
│   ├── stage3/
│   │   └── .env.stage3
│   └── README.md
│
├── aws-prod/              # AWS production
│   ├── stage3/
│   │   └── .env.stage3
│   └── README.md
│
└── README.md (this file)
```

## Related Documentation

- **ADR-0001**: Four-Stage Infrastructure Evolution
- **ADR-0010**: Stages vs Environments (implemented by this structure)
- **Issue #86**: Application-level environment configuration (Python code)
- **Issue #93**: Environment-centric deployment structure (this implementation)

## Migration from Legacy Structure

If you were previously using:
- `docker-compose.local.yml` (root) → Now: `environments/local-docker/docker-compose.yml`
- `stages/stage2/docker-compose.yml` → Now: `environments/local-docker/docker-compose.stage2.yml`
- `stages/stage3/ansible/` → Now: `environments/aws-dev/stage3/ansible/`

See `docs/migration-guide.md` for complete migration instructions.

## Support

For questions or issues:
1. Check environment-specific README files
2. See `docs/environments.md` for comprehensive guide
3. Review ADR-0010 for architecture decisions
