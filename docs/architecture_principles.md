# FRANK Architecture Principles

## Foundational Design Philosophy

These architecture principles guide all design decisions for FRANK (Feedback Infrastructure for Cyber Risk Analysis and Network Knowledge sharing). They emerge from our evolutionary development approach and ensure consistency as the system evolves through its four infrastructure stages.

## Core Principles

### AP-001: Single Source of Truth

All business logic, data models, and core functionality resides in the unified core library [`src/frank`](../src/frank/). Infrastructure adapters implement interfaces but contain no business rules. This principle ensures that the same logic works identically across SQLite, DynamoDB, and ScyllaDB implementations.

**Rationale:** Eliminates duplicate logic across infrastructure stages and guarantees consistent behavior regardless of deployment environment.

**Application:** Repository patterns abstract database interactions. Business logic never imports database-specific libraries. All data transformations occur within the core library.

### AP-002: Infrastructure Agnosticism

The system must operate across diverse infrastructure environments without code changes to business logic. Database technology, compute platforms, and deployment environments remain interchangeable through abstraction layers.

**Rationale:** Prevents vendor lock-in and enables confident technology evolution without business logic rewrites.

**Application:** Abstract repository interfaces define data access patterns. Environment-specific implementations handle infrastructure details. Container-based deployments enable portability across cloud providers.

### AP-003: Controlled Complexity Introduction

Each evolutionary stage introduces exactly one major complexity dimension while maintaining a fully working system. Infrastructure complexity remains separate from functional complexity throughout the evolution.

**Rationale:** Reduces risk by preventing overwhelming complexity increases and ensures continuous deliverability.

**Application:** Simple submission models during infrastructure learning phases. Complex functional features introduced only after infrastructure stabilizes. Each stage provides fallback to previous working configuration.

### AP-004: Test-Driven Technology Transitions

Every infrastructure change must be validated through comprehensive testing before production adoption. New database technologies, deployment platforms, or architectural patterns require spike implementations with performance benchmarks and migration validation before replacing existing systems.

**Rationale:** Infrastructure evolution carries significant risk. Testing validates that new technologies meet performance requirements and that data migrations preserve integrity before committing to changes.

**Application:** Spike tests validate new database implementations against existing performance benchmarks. Migration scripts tested with production data volumes in staging environments. Repository pattern enables A/B testing between old and new infrastructure. Integration tests verify identical behavior across different infrastructure implementations.

### AP-005: Immutable Versioned Evolution

Each functional milestone represents a complete, deployable system captured with Git version tags. No "work in progress" states exist in version tags, ensuring immediate value delivery at every evolution step.

**Rationale:** Maintains deployment confidence and enables precise tracking of capability growth over time.

**Application:** Git tags mark functional milestones. Docker tags correspond to deployment artifacts. Database schema versions enable migration tracking. Configuration versions support environment management.

### AP-006: Documentation as Code

Documentation captures knowledge at multiple abstraction levels and evolves alongside the codebase. Code-level docstrings, spike documentation, and architectural decisions are integral to the development process, not afterthoughts.

**Rationale:** Preserves decision rationale and prevents knowledge loss during team evolution and system growth.

**Application:** Comprehensive docstrings document API contracts and examples. Spike tests include hypothesis, approach, and results documentation. Architecture decisions record rationale and trade-offs. Living documentation updates with each evolution.

### AP-007: Forgiving Input, Strong Output

The system accepts input in flexible formats while producing consistent, well-structured output. APIs tolerate variations in submission formats, field ordering, and optional data while ensuring all output follows strict schemas and validation rules.

**Rationale:** Real-world threat intelligence comes from diverse sources with varying data quality and formats. Systems must accommodate this diversity while maintaining internal consistency.

**Application:** YAML and JSON input parsing handles missing optional fields gracefully. Multiple date format acceptance with normalization to ISO standards. Flexible observable field ordering with standardized output structure. Comprehensive input sanitization with strict output validation.

### AP-008: Explicit Error Communication

All system errors provide clear, actionable feedback that enables users to correct issues without requiring system knowledge. Error messages include specific field validation failures, suggested corrections, and examples of valid input formats.

**Rationale:** Effective threat intelligence sharing requires users to quickly understand and correct submission problems without deep technical knowledge.

**Application:** Pydantic validation errors include field paths and expected formats. API responses contain human-readable error descriptions alongside machine-readable codes. Failed submissions include corrected examples where possible. Documentation links provided for complex validation rules.

## Principle Application Guidelines

These principles guide design decisions through trade-off evaluation. When architectural choices conflict, the principles provide criteria for resolution. Team members use these principles during code reviews to ensure consistency with system philosophy. New features and technologies are evaluated against these principles before adoption.

The principles evolve with system understanding but maintain backward compatibility with existing design decisions. Changes to principles require explicit documentation and team consensus. Each principle includes concrete examples to guide implementation decisions.

## Evolution and Governance

Architecture principles are living documents that grow with system maturity. New insights from spike tests and production experience may suggest additional principles or refinements to existing ones. However, changes require careful consideration to maintain consistency with existing system design.

The numbered principle format enables clear references in design discussions and code reviews. Teams can reference specific principles when evaluating architectural alternatives or explaining design decisions to stakeholders.

These principles particularly support AI-assisted development by providing clear constraints that guide both human architects and AI tools toward consistent system design. The safety net of comprehensive testing and abstraction layers enables confident experimentation within the principle framework.