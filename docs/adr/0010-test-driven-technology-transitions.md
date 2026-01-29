# Test-Driven Technology Transitions

- **Status:** accepted
- **Date:** 2026-01-28
- **Decision Makers:** FRANK Architecture Team
- **Related:** [ADR-0008](0008-infrastructure-agnosticism.md), [ADR-0009](0009-controlled-complexity-introduction.md)

## Context and Problem Statement

Infrastructure transitions (SQLite → DynamoDB, ECS → Kubernetes) carry significant risk of data loss, performance degradation, or behavioral changes. How can FRANK confidently adopt new technologies while ensuring they meet requirements before committing to production deployment?

## Decision Drivers

- Infrastructure changes carry high risk and cost
- Need performance validation before technology commitment
- Must ensure data migration integrity
- Cannot afford production failures during transitions
- Want ability to compare technologies objectively
- Need to validate new patterns before broad adoption

## Considered Options

1. **Spike-First Validation** - Time-boxed explorations with performance benchmarks before adoption
2. **Direct Production Migration** - Implement and deploy new technology directly
3. **Parallel Production** - Run both systems in production simultaneously

## Decision Outcome

Chosen option: "Spike-First Validation", because it validates technologies meet requirements with minimal risk and cost before committing to full implementation.

Every infrastructure change must be validated through comprehensive testing before production adoption. New database technologies, deployment platforms, or architectural patterns require spike implementations with performance benchmarks and migration validation.

### Positive Consequences

- Validates technology choices before expensive commitments
- Identifies performance issues early
- Ensures data migration integrity before production
- Enables objective comparison between alternatives
- Builds team confidence in new technologies
- Repository pattern enables A/B testing between implementations
- Spike documentation captures learnings for future reference

### Negative Consequences

- Requires time investment before technology adoption
- May delay implementation of new features
- Need to maintain spike test infrastructure
- Potential for false confidence if spike tests miss edge cases

## Pros and Cons of the Options

### Spike-First Validation

- Good, because validates requirements before commitment
- Good, because low-cost experimentation
- Good, because objective performance comparison
- Good, because builds team knowledge
- Good, because spike documentation preserves learnings
- Bad, because adds time before technology adoption
- Bad, because requires spike test maintenance

### Direct Production Migration

- Good, because fastest time to new technology
- Good, because no duplicate testing effort
- Bad, because high risk of production failures
- Bad, because expensive rollback if issues found
- Bad, because no performance validation beforehand
- Bad, because team learning under production pressure

### Parallel Production

- Good, because real production validation
- Good, because gradual migration possible
- Good, because immediate fallback available
- Bad, because doubles operational complexity
- Bad, because expensive (running two systems)
- Bad, because data synchronization challenges
- Bad, because still requires testing before parallel deployment

## Implementation: Three-Layer Testing Strategy

### Layer 1: Unit Tests ([tests/unit/](../../tests/unit/))

**Purpose:** Fast, isolated component testing

- High coverage (≥85% required by CI/CD)
- Test individual functions/classes with mocked dependencies
- Run time: <100ms per test
- Run with: `pytest tests/unit/` or `make test`

**Infrastructure Testing:**
- Repository interface compliance tests
- Model serialization/deserialization
- Access control logic
- Data validation

### Layer 2: Integration Tests ([tests/integration/](../../tests/integration/))

**Purpose:** System confidence through BDD scenarios

- Gherkin syntax for business scenarios
- Test component interactions, API endpoints, database operations
- Run with: `behave tests/integration/`

**Infrastructure Testing:**
- Complete API workflows
- Database CRUD operations
- Multi-component interactions
- Error handling and edge cases

### Layer 3: Spike Tests ([tests/spikes/](../../tests/spikes/))

**Purpose:** Hypothesis-driven technology validation

- Time-boxed (1-4 hours) investigations
- Files ending in `*_test.py` part of pytest suite
- Each spike has README.md documenting:
  - Hypothesis (what we're validating)
  - Approach (how we'll test it)
  - Results (what we learned)
  - Decision (adopt, reject, or revisit)
- Run validation: `pytest tests/spikes/ -k "*_test.py"`

**Recent Spikes:**
- **010_cognito** - AWS Cognito authentication patterns
- **011_fastapi** - FastAPI testability and architecture patterns

**Infrastructure Testing:**
- New database technology performance
- Deployment platform capabilities
- API framework patterns
- Migration validation with production data volumes

### Validation Requirements

Before adopting new infrastructure technology:

1. **Spike Test Created** - Time-boxed exploration documented
2. **Performance Benchmarks** - Meets or exceeds current performance
3. **Migration Validation** - Data integrity verified with production volumes
4. **Repository Compliance** - Implements `BaseFRANKDatabase` interface
5. **Integration Tests Pass** - Identical behavior to existing implementation
6. **Documentation Complete** - Spike README captures decisions

### Repository Pattern Enablement

Abstract interfaces enable safe experimentation:

```python
# Easy A/B testing between implementations
def get_database(use_experimental: bool = False) -> BaseFRANKDatabase:
    if use_experimental:
        return NewDatabaseImplementation()
    return CurrentDatabaseImplementation()
```

Both implementations must pass identical test suites.

## Validation Examples

### DynamoDB Adoption (Stage 2→3)

1. Spike 009 (hypothetical) validated DynamoDB patterns
2. Performance benchmarks compared to SQLite
3. Migration script tested with production data volumes
4. Integration tests verified identical API behavior
5. Parallel operation validated in Stage 2 (LocalStack)
6. Production deployment in Stage 3 after validation

### FastAPI Patterns (Spike 011)

1. Explored testability patterns
2. Validated function-based architecture
3. Tested bearer token authentication
4. Established exception handling patterns
5. **Result:** Patterns adopted across all stages

## Links

- Enables [ADR-0008: Infrastructure Agnosticism](0008-infrastructure-agnosticism.md)
- Supports [ADR-0009: Controlled Complexity Introduction](0009-controlled-complexity-introduction.md)
- Implementation: [tests/spikes/](../../tests/spikes/)
- Related: [CLAUDE.md Testing Strategy](../../CLAUDE.md#testing-strategy)
