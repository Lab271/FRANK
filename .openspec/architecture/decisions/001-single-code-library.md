# ADR 001: Single Code Library Across All Infrastructure Stages

**Status:** Accepted

**Date:** 2026-02-12

**Context:**

FRANK evolves through four infrastructure stages (SQLite → DynamoDB → ScyllaDB), each adding complexity. We need to decide whether to:
1. Maintain separate codebases per stage
2. Use feature flags to enable/disable functionality per stage
3. Create a single unified library that works unchanged across all stages

**Decision:**

We will maintain a **single unified code library** (`src/frank/`) containing all business logic that runs unchanged across all infrastructure stages.

**Rationale:**

### Benefits

1. **Zero Code Changes for Infrastructure Evolution**
   - Same Pydantic models work with SQLite, DynamoDB, and ScyllaDB
   - Application code never needs to know which database is running
   - Infrastructure changes require only new repository implementations

2. **Evolutionary Confidence**
   - Each stage validates that abstractions are correct
   - Stage 1 (SQLite) proves business logic before adding infrastructure
   - Stage 3 (DynamoDB) proves cloud deployment before adding complexity
   - Bugs found in Stage 1 are fixed once for all stages

3. **Testing Efficiency**
   - Write tests once, run against all implementations
   - SQLite enables fast unit tests
   - DynamoDB tests run on LocalStack before cloud deployment
   - Abstract base tests ensure behavioral parity

4. **Separation of Concerns**
   - Business logic (src/frank/core/) has zero infrastructure dependencies
   - Infrastructure decisions isolated in src/frank/storage/
   - Clean abstraction enables independent evolution

### Trade-offs

1. **Abstraction Cost**
   - Must design abstractions that work for all stages
   - Cannot use database-specific features directly
   - Requires repository pattern discipline

2. **Implementation Variance**
   - Some methods not available in all implementations (e.g., DynamoDB doesn't handle organization CRUD)
   - Must handle NotImplementedError gracefully
   - Documentation must clearly state what works where

3. **Performance Tuning**
   - Cannot optimize for specific database features
   - Must accept "good enough" performance across all implementations
   - Database-specific optimizations require abstraction changes

**Implementation Details:**

### Directory Structure
```
src/frank/
├── core/              # Infrastructure-independent (used by all stages)
│   ├── models.py      # Pydantic v2 models
│   ├── enum.py        # Enumerations
│   └── exceptions.py  # Domain exceptions
├── storage/           # Infrastructure abstraction
│   ├── base.py        # BaseFRANKDatabase interface
│   ├── sqlite.py      # Stage 1-2
│   ├── dynamodb.py    # Stage 2-3
│   └── postgresql.py  # Stage 3+ (management API)
└── util/              # Shared utilities
```

### Key Patterns

1. **Repository Pattern**
   - Abstract base class defines contract
   - Each implementation extends base
   - Application code depends only on abstraction

2. **Dependency Injection**
   - Database instance passed to API at startup
   - No hardcoded database choices in business logic
   - Environment determines which implementation loads

3. **Graceful Degradation**
   - Methods raise NotImplementedError with guidance
   - Documentation shows availability matrix
   - Fallback mechanisms where appropriate

**Consequences:**

### Positive

- ✅ Evolutionary design validated at each stage
- ✅ Testing simplified (SQLite for fast tests)
- ✅ Infrastructure changes don't require code rewrites
- ✅ Clear separation of business logic and infrastructure
- ✅ Same codebase in development and production

### Negative

- ❌ Cannot use database-specific features easily
- ❌ Must handle implementation variance explicitly
- ❌ Abstraction design requires upfront thought
- ❌ Performance tuning more complex

### Neutral

- 🔄 Requires discipline to maintain abstraction boundaries
- 🔄 Documentation must cover all stages
- 🔄 Tests must validate all implementations

**Validation:**

This decision has been validated through successful implementation:
- ✅ Stage 1: SQLite implementation complete and tested
- ✅ Stage 2: DynamoDB implementation on LocalStack
- ✅ Stage 3: DynamoDB running in AWS Cloud with ECS
- ✅ Zero business logic changes between stages
- ✅ 85%+ test coverage maintained

**References:**

- Implementation: `src/frank/core/`, `src/frank/storage/`
- Related ADRs:
  - ADR-0007: Forgiving Input, Strong Output
  - ADR-0003: Tiered Access Control Model
- Documentation: `docs/evolutionary_design.md`
- Specs:
  - `.openspec/specs/020-storage-base-interface/spec.md`
  - `.openspec/specs/021-storage-sqlite/spec.md`
  - `.openspec/specs/022-storage-dynamodb/spec.md`

**Review Date:** 2026-08-12 (6 months, before Stage 4 implementation)
