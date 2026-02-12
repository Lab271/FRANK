# FRANK Stages: Infrastructure Evolution

## Overview

FRANK evolves through **four controlled infrastructure stages**, each introducing exactly one major complexity dimension while maintaining a fully working system. This staged approach separates infrastructure learning from functional complexity, enabling incremental mastery without overwhelming the development team.

**Key Principle**: Stages represent **infrastructure complexity levels**, not deployment targets. A single stage can run in multiple environments (local Python, local Docker, AWS, etc.). See [ADR-0010: Stages vs Environments](../.openspec/architecture/decisions/0010-stages-vs-environments.md) for the critical distinction.

## Stages Quick Reference

| Stage | Database | Compute | Location | Purpose | Status |
|-------|----------|---------|----------|---------|--------|
| [Stage 1](stage1/) | SQLite | FastAPI | Local | Foundation & Development Baseline | ✅ COMPLETE |
| [Stage 2](stage2/) | PostgreSQL/DynamoDB | FastAPI + Docker | LocalStack | AWS Patterns Learning | ✅ COMPLETE |
| [Stage 3](stage3/) | DynamoDB | ECS Fargate | AWS Cloud | Production Cloud Deployment | ✅ COMPLETE |
| [Stage 4](stage4/) | ScyllaDB/MongoDB | Kubernetes | Multi-Cloud | Cloud-Agnostic Scale | ⏳ PLANNED |

## Stage Selection Guide

### When to Use Each Stage

**Stage 1: Foundation**
- Initial development and prototyping
- Quick iteration on business logic
- Learning core FRANK concepts
- Running on laptop without Docker/AWS

**Stage 2: AWS Patterns**
- Learning DynamoDB patterns locally
- Testing containerization approaches
- Validating AWS service integration without cloud costs
- Dual database experimentation (PostgreSQL vs DynamoDB)

**Stage 3: Cloud Deployment**
- Production-ready AWS deployment
- Learning ECS, ALB, Auto Scaling, CloudFormation
- Full authentication with AWS Cognito
- Complex submission models in production

**Stage 4: Cloud-Agnostic Scale**
- Multi-cloud deployment capabilities
- Kubernetes orchestration
- Vendor-independent architecture
- Maximum submission model complexity

## Evolutionary Philosophy

### Core Principles

1. **One Complexity Dimension at a Time**
   - Stage 1→2: Add containerization and database abstraction
   - Stage 2→3: Add cloud deployment and complex models
   - Stage 3→4: Add cloud-agnostic orchestration

2. **Always Deployable**
   - Every stage is a complete, working system
   - No "under construction" phases
   - Value delivered at each stage

3. **Never Break Stage 1**
   - Stage 1 remains the development baseline forever
   - All stages can fall back to simpler infrastructure
   - Business logic remains unchanged across stages

4. **Validate Before Commitment**
   - Spikes validate each new technology
   - Integration tests prove behavior consistency
   - Fallback paths always available

For complete design philosophy, see [Evolutionary Design](../docs/evolutionary_design.md).

## Stage Progression

```
┌─────────────┐
│   Stage 1   │  SQLite + FastAPI (Local)
│  Foundation │  ↓ Add containerization & database abstraction
└─────────────┘
       ↓
┌─────────────┐
│   Stage 2   │  PostgreSQL/DynamoDB + Docker + LocalStack
│ AWS Patterns│  ↓ Add cloud deployment & complex models
└─────────────┘
       ↓
┌─────────────┐
│   Stage 3   │  DynamoDB + ECS + AWS Cloud
│Cloud Deploy │  ↓ Add cloud-agnostic orchestration
└─────────────┘
       ↓
┌─────────────┐
│   Stage 4   │  ScyllaDB/MongoDB + Kubernetes
│Multi-Cloud  │
└─────────────┘
```

## Fallback Paths

Each stage can fall back to the previous stage if issues arise:

- **Stage 4** → Stage 3 (AWS ECS if Kubernetes fails)
- **Stage 3** → Stage 2 (LocalStack if AWS fails)
- **Stage 2** → Stage 1 (SQLite if Docker/DB fails)
- **Stage 1** → Baseline (always works)

## Directory Structure

```
stages/
├── README.md           # This file - navigation hub
├── stage1/             # SQLite + FastAPI (Local)
│   ├── README.md
│   └── server.py
├── stage2/             # PostgreSQL/DynamoDB + Docker
│   ├── README.md
│   ├── docker-compose.yml
│   └── ...
├── stage3/             # DynamoDB + ECS (AWS)
│   ├── README.md
│   ├── ansible/
│   └── ...
└── stage4/             # ScyllaDB/MongoDB + Kubernetes
    ├── README.md
    ├── DATABASE_CONNECTION_GUIDE.md
    └── ...
```

## Contributing Spikes

Each stage is validated through time-boxed spikes (1-4 hour experiments) before integration:

**Stage 1 Spikes** (Foundation):
- 001_genparse - Dataclass validation patterns
- 002_filter - Access-tier filtering
- 003_pydantic - Pydantic v2 models
- 004_sqlite - SQLite storage layer
- 005_server - FastAPI server patterns
- 007_fastapi - Exception handling patterns

**Stage 2 Spikes** (AWS Patterns):
- 006_dynamodb - DynamoDB storage layer

**Stage 3 Spikes** (Cloud Deployment):
- 009_aws_ecs_basic - ECS Fargate deployment
- 010_aws_alb - Application Load Balancer
- 011_aws_ssl - SSL/TLS termination
- 012_aws_dynamodb - Multi-AZ DynamoDB
- 014_cognito - AWS Cognito authentication

**Stage 4 Spikes** (Cloud-Agnostic):
- Future spikes for Kubernetes, ScyllaDB, multi-cloud patterns

See [tests/spikes/index.md](../tests/spikes/index.md) for complete spike documentation.

## Quick Start by Use Case

### "I want to start developing"
→ **Stage 1** - Run locally with SQLite
```bash
cd environments/local-python
cp .env.stage1.example .env
./run-stage1.sh
```

### "I want to learn AWS patterns"
→ **Stage 2** - Run with LocalStack
```bash
cd environments/local-docker
make stage2
```

### "I want to deploy to AWS"
→ **Stage 3** - Deploy with Ansible
```bash
cd environments/aws-dev/stage3
cp .env.stage3.example .env.stage3
ansible-playbook ../../ansible/playbook.yml --tags create
```

### "I want multi-cloud deployment"
→ **Stage 4** - Kubernetes (planned)
```bash
# Coming soon - see stage4/README.md for architecture
```

## Related Documentation

### Architectural Decision Records
- [ADR-0001: Four-Stage Infrastructure Evolution](../.openspec/architecture/decisions/0001-four-stage-infrastructure-evolution.md) - Why stages exist
- [ADR-0010: Stages vs Environments](../.openspec/architecture/decisions/0010-stages-vs-environments.md) - Critical distinction
- [ADR-0011: Spike Integration Process](../.openspec/architecture/decisions/0011-spike-integration-process.md) - Validation approach

### Planning and Design
- [Implementation Plan](../docs/implementation_plan.md) - Detailed stage roadmap
- [Evolutionary Design](../docs/evolutionary_design.md) - Design philosophy
- [Glossary](../docs/glossary.md) - Terminology definitions

### Deployment Guides
- [Environments README](../environments/README.md) - Deployment target documentation
- [Migration Guide](../MIGRATION.md) - Moving between stages/environments

---

*Last updated: 2026-02-01*
