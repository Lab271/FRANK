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

All architectural decisions in chronological order:

| ADR | Title | Status | Category | Date |
|-----|-------|--------|----------|------|
| [0001](0001-four-stage-infrastructure-evolution.md) | Four-Stage Infrastructure Evolution | ✅ Accepted | Architecture | 2026-01-23 |
| [0002](0002-repository-pattern-database-abstraction.md) | Repository Pattern for Database Abstraction | ✅ Accepted | Architecture | 2026-01-23 |
| [0003](0003-tiered-access-control-model.md) | Tiered Access Control Model | ✅ Accepted | Security | 2026-01-23 |
| [0004](0004-three-layer-testing-strategy.md) | Three-Layer Testing Strategy | ✅ Accepted | Testing | 2026-01-23 |
| [0005](0005-cognito-authentication.md) | AWS Cognito Authentication Strategy | ✅ Accepted | Security | 2026-01-29 |
| [0006](0006-admin-mvc-architecture.md) | MVC Architecture for Admin Module | ✅ Accepted | Architecture | 2026-01-29 |
| [0007](0007-forgiving-input-strong-output.md) | Forgiving Input, Strong Output | ✅ Accepted | Data Quality | 2026-01-28 |
| [0008](0008-explicit-error-communication.md) | Explicit Error Communication | ✅ Accepted | Data Quality | 2026-01-28 |
| [0009](0009-postgresql-management-api.md) | PostgreSQL for Management API | ✅ Accepted | Infrastructure | 2026-01-31 |
| [0010](0010-stages-vs-environments.md) | Stages vs Environments Architecture | ✅ Accepted | Architecture | 2026-01-31 |
| [0011](0011-spike-integration-process.md) | Spike Integration Process | ✅ Accepted | Process | 2026-01-31 |
| [0012](0012-testing-philosophy.md) | Testing Philosophy and Local Services | ✅ Accepted | Testing | 2026-01-31 |

## Quick Reference

### Core Architecture Decisions
- **ADR-0001**: Four stages of infrastructure evolution (SQLite → DynamoDB → ECS → K8s)
- **ADR-0002**: Repository pattern for database abstraction
- **ADR-0003**: Five-tier access control (public → observer → contributor → partner → core_member)
- **ADR-0010**: Stages vs Environments - infrastructure complexity vs deployment target

### Security & Authentication
- **ADR-0005**: Cognito for ALL authentication (humans + services), no custom API keys
- **ADR-0003**: Tiered access control with progressive disclosure

### Testing & Validation
- **ADR-0004**: Three-layer testing (unit, integration, spikes)
- **ADR-0011**: Spike integration process - hypothesis validation to production
- **ADR-0012**: Testing philosophy with local service stubs

### Data Management
- **ADR-0007**: Forgiving input, strong output (Postel's Law)
- **ADR-0008**: Explicit error communication with field-level validation
- **ADR-0009**: PostgreSQL for member organisations, DynamoDB for threat intelligence

### Admin & Tools
- **ADR-0006**: MVC architecture for admin module (Web GUI, TUI)

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
3. **Assign number** - Next sequential number (currently 0013)
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
This change violates ADR-0002 (Repository Pattern) by
placing business logic in the infrastructure adapter.
Please move the logic to src/frank/core/.
```

### When Making Design Decisions

Consult relevant ADRs before implementing:
- Infrastructure evolution → ADR-0001, ADR-0010
- Database abstraction → ADR-0002
- Access control → ADR-0003
- Testing strategy → ADR-0004, ADR-0012
- Authentication → ADR-0005
- Admin interface → ADR-0006
- Input validation → ADR-0007
- Error handling → ADR-0008
- Database selection → ADR-0009
- Stages vs environments → ADR-0010
- Spike integration → ADR-0011
- Local service stubs → ADR-0012

### For AI-Assisted Development

ADRs provide architectural constraints for AI tools:
- Prevents violations of design principles
- Provides rationale for decisions
- Guides technology selection within constraints
- Ensures consistent implementation

## Further Reading

- **Evolutionary Design**: [docs/evolutionary_design.md](../evolutionary_design.md) - Overall evolution strategy
- **CLAUDE.md**: [CLAUDE.md](../../CLAUDE.md) - AI-assisted development guide
- **MADR Documentation**: https://adr.github.io/madr/ - ADR template documentation

---

*Last updated: 2026-01-31*
*Total ADRs: 12 accepted, 0 proposed, 0 rejected*
