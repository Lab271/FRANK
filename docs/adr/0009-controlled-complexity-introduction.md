# Controlled Complexity Introduction

- **Status:** accepted
- **Date:** 2026-01-28
- **Decision Makers:** FRANK Architecture Team
- **Related:** [ADR-0008](0008-infrastructure-agnosticism.md), [ADR-0010](0010-test-driven-technology-transitions.md)

## Context and Problem Statement

Software evolution often fails when teams introduce multiple complexity dimensions simultaneously. How should FRANK evolve through four infrastructure stages while maintaining working systems and managing the cognitive load of learning new technologies?

## Decision Drivers

- Need to learn multiple new technologies (DynamoDB, ECS, Kubernetes, ScyllaDB)
- Must maintain working systems at every evolution step
- Prevent overwhelming complexity that blocks progress
- Enable team learning without system instability
- Support rollback to previous working configurations
- Separate infrastructure learning from functional complexity

## Considered Options

1. **One Dimension Per Stage** - Each stage introduces exactly one major complexity dimension
2. **Big Bang Evolution** - Build complete final architecture directly
3. **Feature-Driven Evolution** - Add functionality as primary driver, infrastructure as needed

## Decision Outcome

Chosen option: "One Dimension Per Stage", because it reduces risk, ensures continuous deliverability, and separates infrastructure complexity from functional complexity.

Each evolutionary stage introduces exactly one major complexity dimension while maintaining a fully working system. Infrastructure complexity remains separate from functional complexity throughout the evolution.

### Positive Consequences

- Manageable learning curve - team masters one technology at a time
- Reduced risk of overwhelming complexity
- Continuous deliverability at every stage
- Clear fallback to previous working configuration
- Infrastructure learning isolated from functional changes
- Each stage provides stable platform for next evolution

### Negative Consequences

- Slower overall evolution compared to direct implementation
- May require temporary scaffolding code
- Need discipline to resist adding multiple complexities simultaneously
- May delay some feature implementations until infrastructure stabilizes

## Pros and Cons of the Options

### One Dimension Per Stage

- Good, because manageable learning progression
- Good, because working system at every step
- Good, because clear fallback paths
- Good, because infrastructure and functional complexity separated
- Good, because team confidence builds gradually
- Bad, because slower overall timeline
- Bad, because may require temporary scaffolding

### Big Bang Evolution

- Good, because fastest path to final architecture
- Good, because no intermediate scaffolding
- Bad, because overwhelming complexity
- Bad, because high failure risk
- Bad, because long periods without working systems
- Bad, because difficult to isolate problems

### Feature-Driven Evolution

- Good, because focuses on business value
- Good, because user-visible progress
- Bad, because mixes infrastructure and functional complexity
- Bad, because infrastructure decisions driven by immediate needs
- Bad, because harder to maintain architectural consistency

## Implementation: Four-Stage Evolution

### Stage 1: Foundation (SQLite + FastAPI on laptop)

**Complexity Introduced:** Core data model and API design

- Simple, well-understood infrastructure (SQLite)
- Focus: Business logic, data models, API contracts
- Submission model: Simple (single sighting, basic observables)
- **Stable platform for:** Infrastructure learning

### Stage 2: AWS Patterns (DynamoDB + FastAPI on LocalStack/Docker)

**Complexity Introduced:** AWS services and containerization

- Learn DynamoDB and LocalStack patterns
- Focus: Cloud service interaction, container deployment
- Submission model: Remains simple (infrastructure learning priority)
- **Stable platform for:** Cloud deployment

### Stage 3: Cloud Deployment (DynamoDB + FastAPI on ECS)

**Complexity Introduced:** Production AWS infrastructure

- Real AWS cloud deployment (ECS, ALB, CloudFormation)
- Focus: Production operations, scaling, monitoring
- Submission model: Now complex (multiple sightings, rich observables)
- **Stable platform for:** Production operations

### Stage 4: Production Scale (ScyllaDB + Go on Kubernetes)

**Complexity Introduced:** Cloud-agnostic platform and performance

- Kubernetes orchestration, ScyllaDB scale
- Focus: Multi-cloud portability, high performance
- Submission model: Full complexity with all features
- **Stable platform for:** Global scale

### Discipline Rules

1. **Infrastructure learning happens in Stages 1-2** - Complex submission models wait until Stage 3
2. **One major technology per stage** - No simultaneous cloud + Kubernetes introduction
3. **Maintain working systems** - Each stage fully deployable and operational
4. **Explicit fallback paths** - Can revert to previous stage if needed

## Validation

- Each stage tagged in Git with functional milestone
- Integration tests validate working system at every stage
- Spike tests validate new technologies before stage adoption
- Performance benchmarks ensure no regression

## Links

- Depends on [ADR-0008: Infrastructure Agnosticism](0008-infrastructure-agnosticism.md)
- Supports [ADR-0010: Test-Driven Technology Transitions](0010-test-driven-technology-transitions.md)
- Related: [docs/evolutionary_design.md](../evolutionary_design.md)
- Implementation: [stages/](../../stages/)
