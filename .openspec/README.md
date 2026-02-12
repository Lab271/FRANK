# FRANK Specifications

This directory contains formal specifications for FRANK's core systems, following a **Specification-Driven Development (SDD)** approach that complements FRANK's [evolutionary design philosophy](../docs/evolutionary_design.md).

## Overview: Specification-Driven Development for FRANK

Specifications in FRANK serve as the bridge between **vision** (what we want to build) and **implementation** (how we build it). Unlike traditional documentation that follows code, specifications **precede and guide development**, enabling:

- **Clear Communication**: Align teams on requirements before coding
- **Change Control**: Manage feature evolution across FRANK's four stages
- **Testability**: Specs define test requirements and acceptance criteria
- **Evolutionary Planning**: Understand how features evolve from Stage 1 (SQLite) through Stage 4 (Kubernetes)
- **Knowledge Preservation**: Capture design decisions and trade-offs

## Directory Structure

Following [OpenSpec](https://github.com/Fission-AI/OpenSpec) conventions, specifications are organized in numbered directories under `.openspec/specs/`:

```
openspec/
├── .openspec/
│   └── specs/                    # Main specifications (source of truth)
│       ├── 001-submission/       # Core: Submission data model
│       ├── 002-observable/       # Core: Observable indicators
│       ├── 003-sighting/         # Core: Sighting details
│       ├── 004-submitter-target/ # Core: Submitter/Target entities
│       ├── 005-enums/            # Core: Enumeration types
│       ├── 010-sightings-api/    # API: Threat intelligence sightings
│       ├── 011-management-api/   # API: Management endpoints
│       ├── 012-authentication/   # API: Authentication flows
│       ├── 020-storage-base-interface/  # Storage: Base abstraction
│       ├── 021-storage-sqlite/   # Storage: SQLite implementation
│       ├── 022-storage-dynamodb/ # Storage: DynamoDB implementation
│       ├── 023-storage-postgresql/ # Storage: PostgreSQL implementation
│       ├── 030-infrastructure-ecs-fargate/  # Infrastructure: ECS deployment
│       └── 040-testing-fastapi-patterns/    # Testing: FastAPI patterns
├── README.md                     # This file
└── validate.py                   # OpenSpec validator
```

### Numbering Scheme

Specifications are numbered by domain:
- **001-009**: Core business logic and data models
- **010-019**: API endpoints and contracts
- **020-029**: Storage layer implementations
- **030-039**: Infrastructure and deployment
- **040-049**: Testing patterns and frameworks

### Change Proposals (Future)

`.openspec/changes/` - Formal change proposals following the **OpenSpec pattern** for introducing new features or major changes.

Each change lives in its own directory with a complete narrative:
- `proposal.md` - Why we need this change (problem statement, business value)
- `specs/NNN-name/spec.md` - What it should do (delta spec with lifecycle markers)
- `tasks.md` - Implementation checklist (step-by-step tasks)

**Delta Specs** use lifecycle markers:
- `## ADDED Requirements` - Brand new requirements being proposed
- `## MODIFIED Requirements` - Changes to existing requirements
- `## REMOVED Requirements` - Features being deprecated
- `## RENAMED Requirements` - Requirement name changes

**When to Create**: For any feature that:
- Introduces significant new functionality
- Changes existing APIs or data contracts
- Requires cross-stage coordination
- Affects multiple teams or components

## Spec Lifecycle

Specifications follow a formal lifecycle ensuring quality and community alignment:

```
DRAFT → REVIEW → APPROVED → IMPLEMENTED → ARCHIVED
   ↓        ↓         ↓          ↓            ↓
Create    Discuss   Finalize  Develop &   Move to
Draft      with     Status    Test       archive/
proposal   team                          when done
```

### 1. DRAFT
- **Who**: Feature owner or engineer proposing the change
- **Action**: Create new spec following the template (see below)
- **Duration**: 1-2 hours to capture initial vision
- **Deliverable**: Complete proposal, design outline, and task breakdown

### 2. REVIEW
- **Who**: Feature owner, technical leads, and team members
- **Action**: Comment on the proposal, discuss alternatives, raise concerns
- **Duration**: 1-3 days for community feedback
- **Deliverable**: Refined proposal with consensus on approach

### 3. APPROVED
- **Who**: Technical leads or architecture review board
- **Action**: Formally approve the spec and update status
- **Duration**: 1 day decision window
- **Deliverable**: Approved spec ready for implementation

### 4. IMPLEMENTED
- **Who**: Feature development team
- **Action**: Update spec with implementation notes, test results, and links to PRs
- **Duration**: Development cycle (varies by feature)
- **Deliverable**: Complete implementation with passing tests and code review

### 5. ARCHIVED
- **Who**: Project maintainers
- **Action**: Move completed spec to `changes/archive/` with final notes
- **Duration**: After feature merge and testing
- **Deliverable**: Historical record of the feature decision and implementation

## Using Specifications

### Creating a New Specification

1. **Determine the next spec number**:
   ```bash
   ls .openspec/specs/  # Find highest number in your domain range
   ```

   - **Core models**: 001-009
   - **APIs**: 010-019
   - **Storage**: 020-029
   - **Infrastructure**: 030-039
   - **Testing**: 040-049

2. **Create the spec directory and file**:
   ```bash
   mkdir -p .openspec/specs/NNN-spec-name
   # Create spec using OpenSpec template (see OpenSpec skill: /spec)
   ```

3. **Complete the template**:
   - Fill in all required sections (marked with ⭐)
   - Remove example text and placeholder sections
   - Reference relevant ADRs and existing documentation
   - Include examples where helpful

4. **Request review**:
   - Create a draft PR or GitHub discussion
   - Add label `spec-draft` or `spec-review`
   - Request feedback from relevant team members

5. **Finalize and implement**:
   - Update spec status to APPROVED
   - Reference spec in GitHub issue or PR
   - Update spec with implementation progress and PR links
   - Move to archive when complete

### Referencing Specifications in Code

When implementing a spec, always reference it in code comments and commit messages:

```python
# Implementation of Observable validation per openspec/.openspec/specs/002-observable/spec.md
# See openspec/.openspec/specs/002-observable/spec.md for requirements
def validate_observable(observable: Observable) -> bool:
    """Validate observable against spec requirements."""
    pass
```

In commit messages:
```
feat: Implement Sightings API per openspec/.openspec/specs/010-sightings-api/spec.md

This implementation fulfills all requirements from the approved spec.

Closes #92
```

### Updating Specifications

Specs are **living documents** that evolve with the system:

1. **Minor Updates**: Clarifications or corrections (update in-place)
2. **Major Changes**: New requirements or significant modifications (create new spec or change proposal)
3. **Implementation Notes**: Add section at end documenting actual implementation
4. **Superseding**: If a spec is superseded, mark status as SUPERSEDED and link to replacement

Example supersession header:
```markdown
- **Status:** Superseded by [002_submission_workflow](changes/002_submission_workflow/spec.md)
```

## Evolutionary Design Integration

FRANK's four-stage evolution requires specs to account for **stage-specific implementation paths**:

**Stage 1 (SQLite)**: Full implementation, all features available
**Stage 2 (DynamoDB + MySQL)**: Learning stage, some features may have fallbacks
**Stage 3 (AWS ECS)**: Cloud-native deployment, threat intelligence optimized
**Stage 4 (Kubernetes)**: Production scale, cloud-agnostic design

Every specification should include an **"Evolution Path"** section documenting:
- Which stages require which features
- How implementation differs across stages
- Fallback strategies for features unavailable in specific stages
- Migration requirements between stages

Example:
```markdown
## Evolution Path Across FRANK Stages

### Stage 1 (SQLite)
- ✅ All features fully implemented
- Single-file database on developer laptop
- Used for: Proof of concept, fast iteration

### Stage 2 (DynamoDB + MySQL)
- ✅ High-throughput threat intelligence storage (DynamoDB)
- ✅ Management API (MySQL) for organizations and users
- Learning stage for cloud patterns

### Stage 3 (AWS ECS)
- ✅ Production-grade DynamoDB infrastructure
- ✅ RDS PostgreSQL for management APIs
- ✅ CloudWatch monitoring and logging

### Stage 4 (Kubernetes)
- ✅ ScyllaDB for massive scale
- ✅ Pod autoscaling based on threat data volume
- ✅ Multi-region deployment support
```

## Templates

### Standard Spec Template: `_template.spec.md`

Use this template for any specification in `core/`, `apis/`, or `storage/`:

```markdown
# [Feature Name] Specification

- **Status:** DRAFT | REVIEW | APPROVED | IMPLEMENTED | SUPERSEDED
- **Version:** 1.0
- **Last Updated:** YYYY-MM-DD
- **Owner:** [Name/Team]
- **Related ADRs:** [ADR-0002](../../.openspec/architecture/decisions/0002-*.md), [ADR-0005](../../.openspec/architecture/decisions/0005-*.md)
- **Issue:** #123

## Purpose

[Concise explanation of why this spec exists and what problem it solves]

## Functional Requirements

[List of what the system must do]

### Requirement 1: [Title]
- **Description**: [Detail]
- **Acceptance Criteria**: [How to verify it works]
- **Stage Availability**: Stages 1, 2, 3, 4 (or subset)

## Non-Functional Requirements

[Performance, scalability, security, usability requirements]

## Data Model / API Contract

[Specific data structures, field definitions, API endpoints, error codes]

## Test Coverage Requirements

[What tests must exist, minimum coverage thresholds, integration test scenarios]

## Implementation Status

- [ ] Design complete
- [ ] Tests written
- [ ] Implementation complete
- [ ] Code review passed
- [ ] Merged to main

**PR Links**: [Link to GitHub PRs]

## Evolution Path Across FRANK Stages

[Document how this feature is implemented/available in each stage]

## References

- [Link to related documentation]
```

### Change Proposal Template: `changes/_template/`

For major features requiring full design documentation, use the complete OpenSpec pattern:

See [`changes/_template/`](#change-proposal-template-structure) below.

## Change Proposal Template Structure

The `changes/_template/` directory contains a complete change proposal template following OpenSpec:

```
changes/_template/
├── proposal.md      # Problem statement and business case
├── spec.md          # Requirements and behavior
├── design.md        # Architecture and implementation
├── tasks.md         # Step-by-step implementation tasks
└── adr.md           # Architectural decision record
```

### proposal.md: Problem Statement & Business Value
Answers "Why do we need this?"

### spec.md: Functional Specification
Answers "What should it do?"

### design.md: Design & Architecture
Answers "How do we build it?"

### tasks.md: Implementation Checklist
Answers "What work needs to happen?"

### adr.md: Architectural Decision Record
Answers "What significant decisions did we make?"

## Best Practices

1. **Be Specific**: Vague requirements create confusion and rework
2. **Reference Existing Work**: Link to ADRs, existing specs, and issue discussions
3. **Consider All Stages**: Account for how features work (or don't) in Stages 1-4
4. **Include Examples**: Show concrete examples of data structures, API calls, etc.
5. **Test-First Thinking**: Define test requirements before implementation
6. **Evolutionary Thinking**: Plan how features evolve across stages
7. **Keep Specs Current**: Update specs as implementation reveals issues or opportunities

## Quick Links

- **ADR Index**: [.openspec/architecture/decisions/index.md](../.openspec/architecture/decisions/index.md)
- **Evolutionary Design**: [docs/evolutionary_design.md](../docs/evolutionary_design.md)
- **Project CLAUDE.md**: [CLAUDE.md](../CLAUDE.md)
- **Spike Documentation**: [tests/spikes/README.md](../tests/spikes/README.md)

## Examples in This Repository

- **Submission Model**: `.openspec/specs/001-submission/spec.md` - Complete submission data structure
- **Observable Model**: `.openspec/specs/002-observable/spec.md` - Threat indicators specification
- **Sightings API**: `.openspec/specs/010-sightings-api/spec.md` - Threat intelligence API endpoints
- **Storage Base**: `.openspec/specs/020-storage-base-interface/spec.md` - Database abstraction layer

## Contributing

When contributing specifications:

1. Follow the appropriate template for your spec type
2. Be thorough but concise (aim for 2-10 pages per spec)
3. Include concrete examples and real use cases
4. Reference related ADRs and existing documentation
5. Consider the full evolutionary path across all stages
6. Request review before marking APPROVED

Questions? Check related ADRs, review existing specs, or ask in team discussions!
