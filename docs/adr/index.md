# Architectural Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) for the FRANK project. ADRs document significant architectural decisions, their context, considered alternatives, and rationale.

## What is an ADR?

An Architectural Decision Record (ADR) captures an important architectural decision made along with its context and consequences. ADRs help preserve the reasoning behind decisions, especially important for:

- Understanding why the system is designed the way it is
- Onboarding new team members
- Evaluating whether past decisions still apply
- Preventing repeated discussions of settled issues
- Supporting AI-assisted development with clear architectural constraints

## ADR Format

FRANK uses the MADR (Markdown Architectural Decision Records) format. See [0000-template.md](0000-template.md) for the template structure.

Each ADR includes:
- **Status**: proposed | accepted | rejected | deprecated | superseded
- **Date**: When the decision was made
- **Decision Makers**: Who was involved
- **Context**: The problem being solved
- **Decision Drivers**: Forces influencing the decision
- **Considered Options**: Alternatives evaluated
- **Decision Outcome**: What was chosen and why
- **Consequences**: Positive and negative impacts
- **Links**: Related ADRs and documentation

## ADR Index

### Implementation Decisions (0001-0006)

Specific implementation and technology choices:

| ADR | Title | Status | Category | Date |
|-----|-------|--------|----------|------|
| [0001](0001-four-stage-infrastructure-evolution.md) | Four-Stage Infrastructure Evolution | ✅ Accepted | Architecture | 2026-01-23 |
| [0002](0002-repository-pattern-database-abstraction.md) | Repository Pattern for Database Abstraction | ✅ Accepted | Architecture | 2026-01-23 |
| [0003](0003-tiered-access-control-model.md) | Tiered Access Control Model | ✅ Accepted | Security | 2026-01-23 |
| [0004](0004-three-layer-testing-strategy.md) | Three-Layer Testing Strategy | ✅ Accepted | Testing | 2026-01-23 |
| [0005](0005-cognito-authentication.md) | AWS Cognito Authentication Strategy | ✅ Accepted | Security | 2026-01-29 |
| [0006](0006-admin-mvc-architecture.md) | MVC Architecture for Admin Module | ✅ Accepted | Architecture | 2026-01-29 |

### Architecture Principles (0007-0014)

Foundational design principles that guide all decisions:

| ADR | Title | Status | Date | Related ADRs |
|-----|-------|--------|------|--------------|
| [0007](0007-single-source-of-truth.md) | Single Source of Truth | ✅ Accepted | 2026-01-28 | ADR-0008 |
| [0008](0008-infrastructure-agnosticism.md) | Infrastructure Agnosticism | ✅ Accepted | 2026-01-28 | ADR-0007, ADR-0009 |
| [0009](0009-controlled-complexity-introduction.md) | Controlled Complexity Introduction | ✅ Accepted | 2026-01-28 | ADR-0008, ADR-0010 |
| [0010](0010-test-driven-technology-transitions.md) | Test-Driven Technology Transitions | ✅ Accepted | 2026-01-28 | ADR-0008, ADR-0009 |
| [0011](0011-immutable-versioned-evolution.md) | Immutable Versioned Evolution | ✅ Accepted | 2026-01-28 | ADR-0009 |
| [0012](0012-documentation-as-code.md) | Documentation as Code | ✅ Accepted | 2026-01-28 | ADR-0010, ADR-0011 |
| [0013](0013-forgiving-input-strong-output.md) | Forgiving Input, Strong Output | ✅ Accepted | 2026-01-28 | ADR-0014 |
| [0014](0014-explicit-error-communication.md) | Explicit Error Communication | ✅ Accepted | 2026-01-28 | ADR-0013 |

## Core Architecture Principles Summary

### ADR-0007: Single Source of Truth
All business logic resides in the unified core library (`src/frank/`) ensuring identical behavior across all infrastructure implementations (SQLite, DynamoDB, ScyllaDB).

**Key Takeaway:** Business logic is tested once and works everywhere. Infrastructure adapters implement interfaces but contain no business rules.

### ADR-0008: Infrastructure Agnosticism
The system operates across diverse infrastructure environments (local SQLite, cloud DynamoDB, Kubernetes ScyllaDB) through abstract repository patterns, preventing vendor lock-in.

**Key Takeaway:** Database technology, compute platforms, and deployment environments remain interchangeable through abstraction layers.

### ADR-0009: Controlled Complexity Introduction
Each evolutionary stage introduces exactly one major complexity dimension (SQLite → DynamoDB → ECS → Kubernetes) while maintaining fully working systems at every step.

**Key Takeaway:** Infrastructure learning happens in early stages with simple data models. Complex features introduced only after infrastructure stabilizes.

### ADR-0010: Test-Driven Technology Transitions
Every infrastructure change validated through spike tests, performance benchmarks, and migration validation before production adoption.

**Key Takeaway:** Three-layer testing strategy (unit, integration, spikes) enables confident technology evolution with minimal risk.

### ADR-0011: Immutable Versioned Evolution
Each functional milestone tagged with semantic version, representing complete deployable system with aligned Git tags, Docker tags, and database schema versions.

**Key Takeaway:** No "work in progress" in version tags. Every tagged version is immediately deployable and represents real value.

### ADR-0012: Documentation as Code
Documentation colocated with code and versioned together, capturing knowledge at multiple abstraction levels (docstrings, spike READMEs, ADRs, guides).

**Key Takeaway:** Documentation is integral to development, not an afterthought. Preserves decision rationale and supports AI-assisted development.

### ADR-0013: Forgiving Input, Strong Output
System accepts flexible input formats (multiple date formats, field ordering, optional fields) while producing consistent, well-structured output following strict schemas.

**Key Takeaway:** Postel's Law - "Be conservative in what you send, be liberal in what you accept." Maximizes submission success while maintaining internal consistency.

### ADR-0014: Explicit Error Communication
All errors provide clear, actionable feedback with field-level validation failures, suggested corrections, and examples of valid formats.

**Key Takeaway:** Users can self-correct submission errors without support intervention. Machine-readable error structure for automation.

## Decision Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                    Foundation Decisions                      │
│                                                               │
│  ADR-0007: Single Source of Truth                           │
│          ↓                                                    │
│  ADR-0008: Infrastructure Agnosticism                       │
│          ↓                                                    │
│  ADR-0009: Controlled Complexity Introduction               │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                      ↓                    ↓
        ┌─────────────────────┐  ┌─────────────────────┐
        │  Evolution Support  │  │  Quality Assurance  │
        │                     │  │                     │
        │  ADR-0010: Testing  │  │  ADR-0012: Docs    │
        │  ADR-0011: Versions │  │                     │
        └─────────────────────┘  └─────────────────────┘
                                          ↓
                          ┌───────────────────────────┐
                          │   Data Quality            │
                          │                           │
                          │  ADR-0013: Forgiving I/O │
                          │  ADR-0014: Error Comms   │
                          └───────────────────────────┘
```

## When to Create an ADR

Create a new ADR when:

- **Adopting new architectural pattern** (e.g., event sourcing, CQRS)
- **Major technology selection** (e.g., choosing database, framework)
- **Establishing design principle** (e.g., error handling strategy)
- **Resolving significant trade-off** (e.g., performance vs. maintainability)
- **Changing existing architectural decision** (supersede previous ADR)

**Do NOT create ADRs for:**
- Routine implementation details
- Temporary workarounds
- Technology spike explorations (use spike README.md instead)
- Minor library choices

## ADR Workflow

### Creating a New ADR

1. **Check existing ADRs** - Ensure decision not already covered
2. **Copy template** - Use [0000-template.md](0000-template.md)
3. **Assign number** - Next sequential number (currently 0015)
4. **Name file** - Format: `NNNN-descriptive-title.md`
5. **Fill sections** - Complete all required sections
6. **Set status** - Start as "proposed"
7. **Link related ADRs** - Reference related decisions
8. **Submit for review** - PR with ADR for team discussion

### Reviewing an ADR

- Verify problem statement is clear
- Evaluate completeness of considered options
- Check that rationale justifies decision
- Ensure consequences are realistic
- Validate links to related ADRs
- Confirm implementation details are accurate

### Accepting an ADR

- Update status to "accepted"
- Update index.md (this file)
- Merge PR
- Reference ADR in code reviews for consistency

### Superseding an ADR

When changing a previous decision:

1. Create new ADR documenting new decision
2. Update old ADR status to "superseded by ADR-XXXX"
3. Link both ADRs bidirectionally
4. Document why previous decision no longer applies
5. Update index.md

## Using ADRs in Development

### During Code Review

Reference ADRs to ensure consistency:
```
This change violates ADR-0007 (Single Source of Truth) by
placing business logic in the infrastructure adapter.
Please move the logic to src/frank/core/.
```

### When Making Design Decisions

Consult relevant ADRs:
- Infrastructure evolution → ADR-0001 (Four-Stage Evolution)
- Database changes → ADR-0002, ADR-0008 (Repository Pattern, Infrastructure Agnosticism)
- Access control → ADR-0003 (Tiered Access Control)
- Testing strategy → ADR-0004, ADR-0010 (Three-Layer Testing, Test-Driven Transitions)
- Authentication → ADR-0005 (Cognito Authentication)
- Error handling → ADR-0014 (Explicit Error Communication)
- Input validation → ADR-0013 (Forgiving Input, Strong Output)
- Version releases → ADR-0011 (Immutable Versioned Evolution)

### For AI-Assisted Development

ADRs provide architectural constraints for AI tools (see [CLAUDE.md](../../CLAUDE.md)):
- Prevents violations of design principles
- Provides rationale for seemingly arbitrary decisions
- Guides technology selection within constraints
- Enables consistent code generation

## Further Reading

- **Evolutionary Design**: [docs/evolutionary_design.md](../evolutionary_design.md) - Overall evolution strategy
- **CLAUDE.md**: [CLAUDE.md](../../CLAUDE.md) - AI-assisted development guide
- **MADR Documentation**: https://adr.github.io/madr/ - ADR template documentation

---

*Last updated: 2026-01-29*
*Total ADRs: 14 accepted (6 implementation, 8 principles), 0 proposed, 0 rejected*
