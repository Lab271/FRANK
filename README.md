# FRANK
This is the Feedbackinfrastructuur voor cyberRisico Analyse en netwerk Kennisdeling (FRANK) project. We have developed this in a 5-stage infra scaling process.

<!-- Simple minimalist badge -->
[![Python 3.13](https://img.shields.io/badge/python-v3.13-blue.svg)](https://www.python.org/downloads/release/python-3137/) 
[![Python 3.11](https://img.shields.io/badge/python-v3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

![AWS](https://img.shields.io/badge/AWS-Cloud-orange.svg?style=flat&logo=amazon-aws&logoColor=white)

![example workflow](https://github.com/LAB271/FRANK/actions/workflows/main.yml/badge.svg)


This project contains everything from design to implementation of the FRANK project. To get started, clone this project and run:

```bash
    $ uv sync                 # install all packages for development (uses uv package manager)
    $ source .venv/bin/activate  # start the virtual env
    # PS I have alias venv="source .venv/bin/activate"
    $ uv run pytest           # run all unittests locally
```

This will prep your machine to run FRANK locally. It assumes Docker/Python/uv/AWS CLI to be available, you can test it with `make check`.

**Build System**: This project uses [Hatch](https://hatch.pypa.io/) as the build system and [uv](https://docs.astral.sh/uv/) as the package manager for fast dependency installation and Python version management.

## Deployment Environments

FRANK supports multiple deployment environments, each optimized for different use cases:

### Local Development
- **[local-docker](environments/local-docker/)** - Docker Compose for full-stack local development (recommended)
- **[local-python](environments/local-python/)** - Python virtualenv for debugging and quick iteration

### AWS Deployment
- **[aws-dev](environments/aws-dev/)** - Development environment for testing AWS integrations
- **[aws-preprod](environments/aws-preprod/)** - Pre-production environment for final validation
- **[aws-prod](environments/aws-prod/)** - Production environment with high availability

See **[environments/README.md](environments/README.md)** for complete deployment documentation.

### Quick Start

```bash
# Local development with Docker (Stage 3 - Full stack)
cd environments/local-docker
make stage3

# Or run natively in Python (Stage 1 - SQLite)
cd environments/local-python
cp .env.stage1.example .env
./run-stage1.sh
```

### Environment Configuration

FRANK uses environment-based configuration to adapt behavior across deployment targets:

```python
from frank.config import Environment, EnvironmentConfig

# Get current environment configuration
config = EnvironmentConfig.get()

# Check environment type
if config.is_local:
    print(f"Running in {config.environment.value} (Stage {config.stage})")
elif config.is_production:
    print("Running in production - AWS")
```

**Environment Variables:**
- `FRANK_ENVIRONMENT`: Deployment target (`local-python`, `local-docker`, `aws-dev`, `aws-preprod`, `aws-prod`)
- `FRANK_STAGE`: Infrastructure stage (1-4)

**Available Environments:**
- `Environment.LOCAL_PYTHON` - Native Python execution
- `Environment.LOCAL_DOCKER` - Docker Compose stack
- `Environment.AWS_DEV` - AWS development account
- `Environment.AWS_PREPROD` - AWS pre-production
- `Environment.AWS_PROD` - AWS production

See `src/frank/config/environments.py` for the complete API and helper properties (`is_local`, `is_aws`, `is_production`, etc.).

## Architecture

Start to understand the [evolutionary design](docs/evolutionary_design.md) principles, before you continue coding on FRANK. 
