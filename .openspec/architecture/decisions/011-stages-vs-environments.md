# ADR-011: Stages vs Environments Architecture

- **Status:** Superseded by [ADR-016](016-phase3-rust-on-db-core.md) (no stages, so no stage-to-environment mapping: one image, three deployments)
- **Date:** 2026-01-31
- **Decision Makers:** Development Team
- **Related:** [ADR-003](003-four-stage-infrastructure-evolution.md)

## Context and Problem Statement

FRANK uses "stages" to describe both infrastructure complexity levels (Stage 1: SQLite, Stage 2: PostgreSQL/DynamoDB, Stage 3: AWS ECS) and deployment targets (local, docker, AWS). This conflation creates confusion about what a "stage" represents and how the system should be deployed across different contexts. Do we deploy "Stage 3" to development? Do we run "Stage 1" in production? How do stages relate to traditional dev/staging/prod environments?

## Decision Drivers

- Need clear separation between infrastructure complexity and deployment context
- Must support multiple deployment targets for the same infrastructure stage
- Should align with industry standard terminology (dev/staging/prod environments)
- Must maintain FRANK's evolutionary philosophy and fallback capability
- Documentation should enable new team members to understand deployment options quickly

## Considered Options

1. **Define Stages and Environments as Separate Concepts** - Stages represent infrastructure complexity progression, Environments represent deployment targets
2. **Use Only Stages** - Continue current practice where stages implicitly include deployment context
3. **Use Only Environments** - Abandon stage terminology in favor of traditional environments

## Decision Outcome

Chosen option: "Define Stages and Environments as Separate Concepts", because it preserves FRANK's evolutionary philosophy while adding deployment flexibility and aligning with industry standards.

**Stage** = Infrastructure complexity level representing evolutionary progression
**Environment** = Deployment target representing where code runs

### Positive Consequences

- Clear mental model: Stages describe "how complex", Environments describe "where deployed"
- Same stage can run in multiple environments (Stage 1 works in Local Python AND Local Docker)
- Enables environment-specific configuration without changing stage implementation
- Aligns with industry terminology (dev/staging/prod) while preserving evolutionary approach
- Supports future multi-environment deployments (e.g., Stage 3 in both AWS Dev and AWS Prod)

### Negative Consequences

- Requires updating documentation to distinguish stages from environments
- Team must learn new terminology and mental model
- Some existing documentation conflates these concepts and needs revision

## Definitions

### Stages (Infrastructure Complexity)

Stages represent **evolutionary progression of infrastructure complexity**, each building on the previous:

| Stage | Infrastructure | Purpose | Fallback |
|-------|---------------|---------|----------|
| **Stage 1** | SQLite + FastAPI | Proof of concept, development baseline | None (this is the baseline) |
| **Stage 2** | PostgreSQL/DynamoDB + FastAPI + LocalStack | Learn AWS patterns without cloud costs | Stage 1 SQLite |
| **Stage 3** | DynamoDB + ECS + AWS Cloud | Production cloud deployment | Stage 2 LocalStack |
| **Stage 4** | ScyllaDB/MongoDB + Kubernetes | Cloud-agnostic production scale | Stage 3 AWS |

**Stage Characteristics:**
- **Complexity Level**: Each stage adds one major infrastructure dimension
- **Learning Focus**: Stages 1-2 focus on infrastructure, Stage 3+ on features
- **Working System**: Every stage is deployable and functional
- **Fallback Capability**: Can always revert to simpler stage if needed
- **Never Break Stage 1**: Simplest stage remains working forever

### Environments (Deployment Targets)

Environments represent **where code runs**, independent of infrastructure complexity:

| Environment | Description | Typical Use |
|------------|-------------|-------------|
| **Local Python** | Native Python on macOS/Linux | Development, debugging |
| **Local Docker** | Docker Compose on developer laptop | Integration testing, AWS simulation |
| **AWS Dev** | AWS development account | Learning, experimentation |
| **AWS Pre-Prod** | AWS staging environment | Validation before production |
| **AWS Prod** | AWS production environment | Customer-facing deployment |

**Environment Characteristics:**
- **Deployment Target**: Physical/virtual location where code executes
- **Configuration**: Environment-specific settings (URLs, credentials, scaling)
- **Isolation**: Separate environments prevent cross-contamination
- **Lifecycle**: Standard deployment pipeline (dev → staging → prod)

### Stage → Environment Mapping

The same stage can run in multiple environments with environment-specific configuration:

```
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: SQLite + FastAPI                                  │
│    ├─ Local Python   (native development)                   │
│    └─ Local Docker   (containerized)                        │
├─────────────────────────────────────────────────────────────┤
│  Stage 2: PostgreSQL/DynamoDB + LocalStack                  │
│    └─ Local Docker   (AWS simulation)                       │
├─────────────────────────────────────────────────────────────┤
│  Stage 3: DynamoDB + ECS + AWS                              │
│    ├─ AWS Dev        (learning/experimentation)             │
│    ├─ AWS Pre-Prod   (validation)                           │
│    └─ AWS Prod       (customer-facing)                      │
├─────────────────────────────────────────────────────────────┤
│  Stage 4: ScyllaDB + Kubernetes                             │
│    ├─ AWS Prod       (Kubernetes on EKS)                    │
│    ├─ GCP Prod       (Kubernetes on GKE)                    │
│    └─ Azure Prod     (Kubernetes on AKS)                    │
└─────────────────────────────────────────────────────────────┘
```

**Examples:**
- Stage 1 in Local Python: Developer running `python stages/stage1/server.py`
- Stage 1 in Local Docker: Same code in Docker Compose with SQLite volume
- Stage 3 in AWS Dev: DynamoDB + ECS with low-cost t3.micro instances
- Stage 3 in AWS Prod: DynamoDB + ECS with production-grade instances and Multi-AZ

## Pros and Cons of the Options

### Option 1: Define Stages and Environments as Separate Concepts (CHOSEN)

Separates infrastructure complexity (stages) from deployment context (environments).

- Good, because it provides clear mental model for team members
- Good, because it enables running same stage in multiple environments
- Good, because it aligns with industry standard terminology
- Good, because it preserves FRANK's evolutionary philosophy
- Good, because it supports future multi-cloud deployments
- Bad, because it requires documentation updates across the project
- Bad, because team must learn new concepts

### Option 2: Use Only Stages

Continue current practice where stages implicitly include deployment target.

- Good, because no changes required to existing codebase
- Good, because team already understands current model
- Bad, because conflates infrastructure complexity with deployment location
- Bad, because doesn't support running Stage 3 in multiple AWS accounts
- Bad, because makes it unclear how to deploy to dev/staging/prod
- Bad, because doesn't align with industry terminology

### Option 3: Use Only Environments

Abandon stage concept in favor of traditional dev/staging/prod environments.

- Good, because aligns with standard software engineering practices
- Good, because widely understood terminology
- Bad, because loses FRANK's evolutionary progression philosophy
- Bad, because hides infrastructure learning journey
- Bad, because doesn't capture fallback capability between complexity levels
- Bad, because doesn't emphasize "one complexity dimension at a time" approach

## Configuration Strategy

Environments are selected via `FRANK_ENVIRONMENT` variable:

```bash
# Local development
export FRANK_ENVIRONMENT=local_python
python stages/stage1/server.py

# Local Docker
export FRANK_ENVIRONMENT=local_docker
docker-compose up

# AWS environments
export FRANK_ENVIRONMENT=aws_dev
export FRANK_ENVIRONMENT=aws_preprod
export FRANK_ENVIRONMENT=aws_prod
```

Environment-specific configuration loaded from:
- `config/environments/{environment}.yaml` - Environment settings
- Environment variables - Secrets and dynamic configuration
- Defaults in code - Sensible fallbacks

## Migration Path

**Phase 1: Documentation (Current)**
- This ADR defines stages vs environments
- Update `docs/evolutionary_design.md` with references
- Add environment sections to stage README files

**Phase 2: Configuration (Future)**
- Implement `FRANK_ENVIRONMENT` variable support
- Create environment-specific config files
- Update deployment scripts to use environment terminology

**Phase 3: Communication (Ongoing)**
- Use correct terminology in PR descriptions, issues, and documentation
- When saying "stage", mean infrastructure complexity level
- When saying "environment", mean deployment target

## Examples

### Correct Usage

✅ "Deploy Stage 3 to AWS Dev environment for testing"
✅ "Stage 1 runs in both Local Python and Local Docker environments"
✅ "Promote Stage 3 from AWS Pre-Prod to AWS Prod environment"
✅ "We're on Stage 2 infrastructure, running in Local Docker environment"

### Incorrect Usage (Old Terminology)

❌ "Deploy Stage 3" (unclear where to deploy)
❌ "Stage 1 is only for development" (Stage 1 is an infrastructure level, not a deployment target)
❌ "Production is Stage 3" (production is an environment, Stage 3 is infrastructure complexity)

## Links

- [ADR-003: Four-Stage Infrastructure Evolution](003-four-stage-infrastructure-evolution.md) - Foundational stage philosophy
- `docs/evolutionary_design.md` - Complete evolutionary design approach
- `stages/*/README.md` - Individual stage documentation
- Future: ADR-00XX: Environment Configuration System (Issue #86)
