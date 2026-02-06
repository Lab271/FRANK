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

### `/specs/core/`
Specifications for FRANK's core business logic and data models:
- `models.spec.md` - Data model specifications (Observable, Submission, Sighting, etc.)
- `access_control.spec.md` - Access tier and permission models
- `validation.spec.md` - Data validation rules and error handling

**When to Create**: When designing new entity types, modifying data structures, or changing core business rules.

### `/specs/apis/`
API endpoint and contract specifications:
- `sightings_api.spec.md` - Threat intelligence sightings API (Issue #92)
- `submissions_api.spec.md` - Full submission workflow endpoints
- `health_check_api.spec.md` - System health check endpoints
- `admin_api.spec.md` - Administrative and management endpoints

**When to Create**: When designing new endpoints, changing API contracts, or versioning APIs.

### `/specs/storage/`
Database layer specifications and storage contracts:
- `database_abstraction.spec.md` - BaseFRANKDatabase interface and implementations
- `sqlite_storage.spec.md` - SQLite-specific implementation requirements
- `dynamodb_storage.spec.md` - DynamoDB-specific implementation requirements
- `postgresql_storage.spec.md` - PostgreSQL management API backend

**When to Create**: When designing database schemas, implementing new storage backends, or changing database interfaces.

### `/specs/changes/`
Formal change proposals following the **OpenSpec pattern** for introducing new features or major changes.

Each change lives in its own directory with a complete narrative:
- `proposal.md` - Why we need this change (problem statement, business value)
- `spec.md` - What it should do (functional requirements, behavior, contracts)
- `design.md` - How to implement it (architecture, trade-offs, alternatives)
- `tasks.md` - Implementation checklist (step-by-step tasks)
- `adr.md` - Architectural decisions (becomes ADR when approved)

**Examples**:
- `changes/001_sightings_api/` - Threat intelligence sightings API (Issue #92)
- `changes/002_submission_workflow/` - Complete submission workflow
- `changes/003_aws_deployment/` - AWS Stage 3 deployment architecture
- `changes/archive/` - Completed and archived changes

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

1. **Determine spec type**:
   - **Core system** → Create in `core/` (e.g., `core/new_model.spec.md`)
   - **API change** → Create in `apis/` (e.g., `apis/new_endpoint.spec.md`)
   - **Storage layer** → Create in `storage/` (e.g., `storage/new_db_backend.spec.md`)
   - **Major feature** → Create change proposal in `changes/` (e.g., `changes/XXX_feature_name/`)

2. **Copy the appropriate template**:
   - For core/apis/storage specs: Use `_template.spec.md`
   - For change proposals: Use entire `changes/_template/` directory structure

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
# Implementation of Observable validation per src/frank/core/models.spec.md
# See specs/core/models.spec.md#observable-validation for requirements
def validate_observable(observable: Observable) -> bool:
    """Validate observable against spec requirements."""
    pass
```

In commit messages:
```
feat: Implement Sightings API per specs/changes/001_sightings_api/spec.md

This implementation fulfills all requirements from the approved spec.
See specs/changes/001_sightings_api/ for complete design.

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
- **Related ADRs:** [ADR-0002](../../docs/adr/0002-*.md), [ADR-0005](../../docs/adr/0005-*.md)
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

- **ADR Index**: [docs/adr/index.md](../docs/adr/index.md)
- **Evolutionary Design**: [docs/evolutionary_design.md](../docs/evolutionary_design.md)
- **Project CLAUDE.md**: [CLAUDE.md](../CLAUDE.md)
- **Spike Documentation**: [tests/spikes/README.md](../tests/spikes/README.md)

## Examples in This Repository

- **Sightings API** (Issue #92): `changes/001_sightings_api/` - Complete change proposal for threat intelligence API
- **Data Models**: `core/models.spec.md` - Specification for Observable, Submission, Sighting models
- **Storage Layer**: `storage/database_abstraction.spec.md` - BaseFRANKDatabase interface and implementations

## Contributing

When contributing specifications:

1. Follow the appropriate template for your spec type
2. Be thorough but concise (aim for 2-10 pages per spec)
3. Include concrete examples and real use cases
4. Reference related ADRs and existing documentation
5. Consider the full evolutionary path across all stages
6. Request review before marking APPROVED

Questions? Check related ADRs, review existing specs, or ask in team discussions!
