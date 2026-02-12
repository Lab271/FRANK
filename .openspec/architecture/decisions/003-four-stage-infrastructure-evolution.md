# ADR-0001: Four-Stage Infrastructure Evolution

## Status

Accepted

## Context

Building a threat intelligence platform requires both complex infrastructure (databases, containers, cloud services) and complex business logic (threat models, access control, sharing protocols). Attempting to learn both simultaneously creates overwhelming complexity and high failure risk.

The challenge: How do we build a production-ready system without betting everything on untested technologies?

Key constraints:
- Team needs to learn AWS services, containers, and Kubernetes
- Business logic must remain stable as infrastructure changes
- System must be deployable at every stage (no "construction zone" phases)
- Technology decisions should be validated before commitment

## Decision

FRANK evolves through **four controlled infrastructure stages**, each introducing exactly one major complexity dimension while maintaining a fully working system.

### Stage 1: SQLite + FastAPI (Local)
- **Focus**: Core business logic and data models
- **Infrastructure**: SQLite database, FastAPI on laptop
- **Purpose**: Proof of concept, development baseline
- **Fallback**: This is the baseline

### Stage 2: MySQL/DynamoDB + LocalStack (Docker)
- **Focus**: Database abstraction and containerization
- **Infrastructure**: MySQL or DynamoDB, FastAPI in Docker, LocalStack for AWS simulation
- **Purpose**: Learn AWS patterns without cloud costs
- **Fallback**: Stage 1 SQLite

### Stage 3: DynamoDB + ECS (AWS Cloud)
- **Focus**: Cloud-native deployment, complex submission models
- **Infrastructure**: Real DynamoDB, ECS Fargate, ALB, Auto Scaling
- **Purpose**: Production cloud deployment
- **Fallback**: Stage 2 LocalStack

### Stage 4: ScyllaDB/MongoDB + Kubernetes (Cloud-Agnostic)
- **Focus**: Vendor independence and scale
- **Infrastructure**: ScyllaDB or MongoDB, Kubernetes
- **Purpose**: Multi-cloud production deployment
- **Fallback**: Stage 3 AWS

### Evolution Rules

1. **Simple models first**: Stages 1-2 use minimal submission models while learning infrastructure
2. **Complex features later**: Stage 3 introduces full submission complexity after infrastructure is stable
3. **Always deployable**: Every stage is a complete, working system
4. **Never break Stage 1**: It remains the development baseline forever

## Consequences

### Positive

- **Reduced Risk**: Infrastructure failures don't break business logic
- **Incremental Learning**: Team learns one technology at a time
- **Always Deployable**: Value delivered at every stage
- **Easy Rollback**: Each stage can fall back to the previous

### Negative

- **Slower Initial Progress**: Full system not available immediately
- **Multiple Implementations**: Database code exists for multiple backends
- **Testing Overhead**: Each stage needs its own integration tests

### Tradeoffs

The single library approach (`src/frank/`) means business logic is written once but tested against multiple database implementations. This increases testing effort but guarantees behavior consistency.

## Alternatives Considered

### Big-Bang Development
Build the full Stage 4 system directly.

**Rejected**: Too much simultaneous complexity. Team would struggle with Kubernetes, ScyllaDB, and business logic simultaneously. No fallback if any component fails.

### Microservices from Start
Split into separate services from the beginning.

**Rejected**: Premature complexity. Adding network boundaries before understanding domain increases risk. Monolith-first approach allows domain to stabilize.

### Cloud-Only Development
Skip local stages, develop directly in AWS.

**Rejected**: Slow feedback loops and cloud costs during exploration. LocalStack provides fast, free iteration for learning AWS patterns.

## Validation

- **Stage 1 validated**: SQLite implementation serves as development environment
- **Stage 2 validated**: LocalStack runs full test suite against DynamoDB API
- **Stage 3 in progress**: ECS deployment with DynamoDB operational
- **Stage 4 planned**: Kubernetes spike scheduled

Each stage transition includes:
1. Spike test to validate new technology
2. Repository implementation matching abstract interface
3. Integration tests proving identical behavior
4. Deployment runbook and rollback procedure

## Related ADRs

- ADR-0002: Repository Pattern for Database Abstraction
- ADR-0004: Three-Layer Testing Strategy

## Implementation Notes

- Stages implemented in `stages/` directory
- Ansible playbooks for Stage 3: `ansible/playbook.yml`
- Spike tests validate each transition: `tests/spikes/`
