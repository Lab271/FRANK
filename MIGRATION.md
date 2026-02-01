# Migration Guide: Environment-Centric Structure

This guide helps you migrate from the old stage-based structure to the new environment-centric structure introduced in Issue #93.

## What Changed?

FRANK has moved from a stage-centric structure (`stages/`) to an environment-centric structure (`environments/`) for better deployment organization.

### Before (Stage-Centric)
```
stages/
├── stage1/   # SQLite + FastAPI
├── stage2/   # PostgreSQL/DynamoDB + FastAPI
├── stage3/   # Full stack with Web GUI
└── stage4/   # Kubernetes deployment

docker-compose.local.yml  # Single Docker Compose file
.env.example               # Single .env file
```

### After (Environment-Centric)
```
environments/
├── local-docker/    # Docker Compose for all stages
├── local-python/    # Python virtualenv for all stages
├── aws-dev/         # AWS development environment
├── aws-preprod/     # AWS pre-production environment
└── aws-prod/        # AWS production environment
```

## Migration Paths

### 1. Docker Compose Users

**Before:**
```bash
# Old way
docker compose -f docker-compose.local.yml up -d
```

**After:**
```bash
# New way
cd environments/local-docker
make stage3  # or stage1, stage2

# Or using root Makefile
make docker-up  # delegates to environments/local-docker
```

**Benefits:**
- Multiple stage profiles (stage1, stage2, stage3)
- Better organized service dependencies
- Stage-specific service combinations
- Improved Makefile with health checks

### 2. Python Virtualenv Users

**Before:**
```bash
# Old way
python stages/stage1/server.py
```

**After:**
```bash
# New way
cd environments/local-python
cp .env.stage1.example .env
./run-stage1.sh  # or run-stage2.sh, run-stage3.sh
```

**Benefits:**
- Consistent .env configuration
- Prerequisite checking
- Clear stage separation
- Helper scripts for each stage

### 3. AWS Deployment Users

**Before:**
```bash
# Old way
cd stages/stage3
ansible-playbook ansible/playbook.yml --tags create
```

**After:**
```bash
# New way
cd environments/aws-prod/stage3  # or aws-dev, aws-preprod
cp .env.stage3.example .env.stage3
vi .env.stage3
ansible-playbook ../../ansible/playbook.yml --tags create
```

**Benefits:**
- Environment-specific configuration
- Separate dev/preprod/prod settings
- Clear deployment paths
- Comprehensive environment documentation

## Deprecated Files

The following files are deprecated and will be removed in a future version:

- ❌ `docker-compose.local.yml` → Use `environments/local-docker/docker-compose.yml`
- ❌ `.env.example` (root) → Use `environments/*/env.*.example`

## What About stages/?

The `stages/` directory contains legacy code that will be:
1. **Migrated** to `environments/` (deployment configurations)
2. **Donated** to `tests/spikes/` (experimental code)
3. **Removed** in a future major version

**Note**: This migration is planned but not yet started. See Issue #86 for details on application-level environment configuration.

## Quick Reference

### Environment Naming Convention

All environments use hyphen-separated naming:
- `local-docker` (not local_docker or localDocker)
- `local-python` (not local_python or localPython)
- `aws-dev` (not aws_dev or awsDev)
- `aws-preprod` (not aws_preprod or awsPreprod)
- `aws-prod` (not aws_prod or awsProd)

### FRANK_ENVIRONMENT Variable

All .env files set the `FRANK_ENVIRONMENT` variable:
```bash
# environments/local-docker/.env.example
FRANK_ENVIRONMENT=local-docker

# environments/local-python/.env.stage1.example
FRANK_ENVIRONMENT=local-python

# environments/aws-prod/stage3/.env.stage3.example
FRANK_ENVIRONMENT=aws-prod
```

### Triple Approach

FRANK supports three deployment approaches:
1. **Python Direct** (`local-python`) - Run natively in virtualenv
2. **Docker Local** (`local-docker`) - Run in Docker Compose
3. **AWS Deployment** (`aws-dev`, `aws-preprod`, `aws-prod`) - Deploy to AWS

## Documentation

- **[environments/README.md](environments/README.md)** - Complete environment guide
- **[environments/local-docker/README.md](environments/local-docker/README.md)** - Docker Compose guide
- **[environments/local-python/README.md](environments/local-python/README.md)** - Python virtualenv guide
- **[environments/aws-prod/README.md](environments/aws-prod/README.md)** - AWS deployment guide

## Need Help?

- Check the validation checklist: `.validation-checklist.md`
- Read the issue: [Issue #93](https://github.com/LAB271/FRANK/issues/93)
- Ask questions in the project discussion board

## Timeline

- **v0.x.x** - Environment-centric structure introduced (backward compatible)
- **v0.x+1.x** - Deprecation notices added (current)
- **v1.0.0** - Old structure removed (breaking change)

---

Migration guide created as part of Issue #93.
