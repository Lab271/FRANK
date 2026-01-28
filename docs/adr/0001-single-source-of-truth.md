# Single Source of Truth for Business Logic

- **Status:** accepted
- **Date:** 2026-01-28
- **Decision Makers:** FRANK Architecture Team
- **Related:** [ADR-0002](0002-infrastructure-agnosticism.md)

## Context and Problem Statement

As FRANK evolves through multiple infrastructure stages (SQLite → DynamoDB → ScyllaDB), how do we ensure that business logic remains consistent and doesn't diverge across different database implementations? Without a clear organizational pattern, teams risk duplicating logic in infrastructure adapters, leading to inconsistent behavior and maintenance nightmares.

## Decision Drivers

- Need to maintain identical business logic behavior across all infrastructure stages
- Prevent code duplication and logic drift between database implementations
- Enable confident technology evolution without business logic rewrites
- Support multiple active infrastructure implementations simultaneously
- Facilitate testing and validation across different deployment environments

## Considered Options

1. **Unified Core Library** - All business logic in `src/frank/` with infrastructure adapters implementing abstract interfaces
2. **Per-Stage Logic** - Business logic distributed across stage-specific implementations
3. **Shared Utilities** - Common utilities shared but business logic duplicated per stage

## Decision Outcome

Chosen option: "Unified Core Library", because it guarantees identical behavior across all infrastructure implementations, eliminates duplicate logic, and enables seamless technology evolution.

All business logic, data models, and core functionality resides in the unified core library [`src/frank/`](../../src/frank/). Infrastructure adapters implement interfaces but contain no business rules.

### Positive Consequences

- Identical behavior guaranteed across SQLite, DynamoDB, and ScyllaDB implementations
- Single place to fix bugs and add features
- Testing validates core logic once rather than per-infrastructure
- Clear separation between business rules and infrastructure concerns
- Enables A/B testing between infrastructure implementations with confidence
- Reduces cognitive load - developers work in one codebase

### Negative Consequences

- Requires discipline to keep business logic out of infrastructure adapters
- Abstract interfaces may add initial complexity
- Performance optimizations may need infrastructure-specific implementations (mitigated by extension points)

## Pros and Cons of the Options

### Unified Core Library

- Good, because business logic tested once works everywhere
- Good, because eliminates duplicate code maintenance
- Good, because enables infrastructure swapping with confidence
- Good, because clear architectural boundaries
- Bad, because requires abstraction layer discipline
- Bad, because may limit infrastructure-specific optimizations initially

### Per-Stage Logic

- Good, because allows infrastructure-specific optimizations
- Good, because no abstraction complexity
- Bad, because business logic duplicates across stages
- Bad, because bug fixes must be applied multiple times
- Bad, because behavior can diverge between implementations
- Bad, because testing effort multiplies by number of stages

### Shared Utilities

- Good, because some code reuse between stages
- Good, because infrastructure freedom
- Bad, because incomplete solution - business logic still duplicates
- Bad, because unclear boundaries between shared and duplicated code
- Bad, because testing complexity remains high

## Implementation Details

### Structure

```
src/frank/
├── core/              # Business logic and data models (infrastructure-independent)
│   ├── models.py      # Pydantic v2 models
│   ├── enum.py        # Enumerations
│   └── exceptions.py  # Domain exceptions
├── storage/           # Database abstraction layer
│   ├── base.py        # BaseFRANKDatabase abstract interface
│   ├── sqlite.py      # SQLite implementation
│   └── dynamodb.py    # DynamoDB implementation
└── util/              # Utilities (server, logging, filters)
```

### Rules

1. **Business logic never imports database-specific libraries** - Only abstract interfaces
2. **Repository pattern abstracts database interactions** - Infrastructure details hidden
3. **All data transformations occur within core library** - No model manipulation in adapters
4. **Infrastructure adapters are thin** - Translate between core models and storage mechanisms

### Validation

- Unit tests validate core logic independently of infrastructure
- Integration tests verify identical behavior across all database implementations
- Repository interface compliance tests ensure consistent API contracts

## Links

- Supports [ADR-0002: Infrastructure Agnosticism](0002-infrastructure-agnosticism.md)
- Related to [docs/evolutionary_design.md](../evolutionary_design.md)
- Implementation: [src/frank/storage/base.py](../../src/frank/storage/base.py)
