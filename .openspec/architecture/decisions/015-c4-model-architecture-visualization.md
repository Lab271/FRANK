# ADR-015: C4 Model for Architecture Visualization

- **Status:** Deprecated (proposed; the per-stage C4 diagrams left the tree with Phase 2)
- **Date:** 2026-02-06
- **Decision Makers:** Architecture Team, agent-2
- **Related:** [ADR-003](003-four-stage-infrastructure-evolution.md), [ADR-011](011-stages-vs-environments.md)

## Context and Problem Statement

FRANK has extensive textual documentation (HLD, functional HLD, 12 ADRs, design documents) and agent-1 is creating formal specifications following Specification-Driven Development. However, we lack visual architecture documentation to complement these textual artifacts. How should we visualize FRANK's architecture to effectively communicate:

- System context and boundaries
- Four-stage infrastructure evolution (SQLite → DynamoDB → AWS ECS → Kubernetes)
- Component relationships and dependencies
- Container-level deployment architecture

The challenge is finding a visual notation that supports evolutionary architecture, remains maintainable as code, and doesn't require specialized UML expertise.

## Decision Drivers

- **Evolutionary Architecture**: Must clearly show progression across FRANK's four stages
- **Maintainability**: Diagrams should be version-controlled as code, not binary images
- **Simplicity**: Team members with varying backgrounds should understand diagrams
- **Tool Support**: Standard tooling for diagram generation and updates
- **Complementary to Specs**: Should enhance, not duplicate, agent-1's specification work
- **ADR Integration**: Must reference and support existing architectural decisions
- **GitHub Native**: Ideally renders in GitHub without external tools

## Considered Options

- **Option 1: C4 Model** (Context, Container, Component, Code diagrams)
- **Option 2: arc42 Architecture Documentation Template**
- **Option 3: 4+1 Architectural View Model** (Logical, Development, Process, Physical, Scenarios)
- **Option 4: UML Diagrams** (Component, Deployment, Class diagrams)
- **Option 5: Custom ASCII Art** (extend existing approach in highlevel_design.md)

## Decision Outcome

Chosen option: "**C4 Model**", because it provides hierarchical abstraction levels perfectly suited for FRANK's evolutionary architecture, uses simple notation accessible to all team members, supports diagrams-as-code with multiple tooling options (PlantUML, Mermaid, Structurizr), and complements our specification-driven development approach.

### Positive Consequences

- **Clear hierarchy**: Four levels (Context, Container, Component, Code) allow appropriate detail
- **Evolution-friendly**: Can create separate Container diagrams for each stage (1-4)
- **Low barrier**: Simple boxes-and-arrows notation, no UML expertise required
- **Tooling choices**: PlantUML with C4 extension, Mermaid (GitHub native), or Structurizr DSL
- **Version control**: Text-based source stored in Git, rendered on demand
- **Separation of concerns**: Specs document behavior, C4 documents structure
- **ADR integration**: Diagrams can reference specific ADRs for decisions
- **Quick wins**: Existing highlevel_design.md ASCII art maps to C4 Container diagrams

### Negative Consequences

- **Learning curve**: Team must learn C4 notation and chosen tooling
- **Maintenance overhead**: Diagrams require updates as architecture evolves
- **Limited code detail**: C4 Level 4 (Code) rarely used, not suitable for detailed class relationships
- **Tool dependency**: Rendering requires PlantUML/Mermaid infrastructure
- **Not comprehensive**: Focuses on structural views, doesn't capture behavioral or deployment concerns comprehensively

## Pros and Cons of the Options

### Option 1: C4 Model

Example: https://c4model.com/

- **Good**, because hierarchical levels match FRANK's needs (system → containers → components)
- **Good**, because simple notation accessible to non-architects
- **Good**, because designed specifically for software architecture visualization
- **Good**, because supports evolutionary architecture with separate diagrams per stage
- **Good**, because multiple tool options (PlantUML, Mermaid, Structurizr)
- **Good**, because created by Simon Brown with active community and documentation
- **Bad**, because requires learning specific notation conventions
- **Bad**, because doesn't capture behavioral or sequence-based interactions well

### Option 2: arc42 Architecture Documentation Template

Example: https://arc42.org/

- **Good**, because comprehensive 14-section template covers all architectural aspects
- **Good**, because well-established in enterprise environments
- **Good**, because includes context, constraints, building blocks, concepts, decisions
- **Bad**, because heavyweight and prescriptive, may be overkill for FRANK
- **Bad**, because focuses on textual documentation (we already have extensive docs)
- **Bad**, because doesn't provide specific visual notation guidance
- **Bad**, because difficult to show evolutionary architecture across stages

### Option 3: 4+1 Architectural View Model

Example: Logical, Development, Process, Physical views + Scenarios

- **Good**, because provides multiple viewpoints for different stakeholders
- **Good**, because academic rigor and well-documented approach
- **Good**, because separation of concerns across views
- **Bad**, because complex with five distinct views to maintain
- **Bad**, because requires UML expertise for proper implementation
- **Bad**, because more suited to upfront architecture than evolutionary approach
- **Bad**, because doesn't naturally map to FRANK's stage-based evolution

### Option 4: UML Diagrams

Example: Component, Deployment, Class, Sequence diagrams

- **Good**, because standardized notation (ISO/IEC 19505)
- **Good**, because extensive tooling support
- **Good**, because can represent detailed relationships
- **Bad**, because complex notation requires UML expertise
- **Bad**, because often too detailed for high-level architecture communication
- **Bad**, because heavyweight and formal, discourages iterative updates
- **Bad**, because multiple diagram types without clear hierarchy

### Option 5: Custom ASCII Art

Example: Extend existing approach in `docs/highlevel_design.md`

- **Good**, because already familiar (existing ASCII diagrams)
- **Good**, because no tooling dependencies (plain text)
- **Good**, because version control native
- **Bad**, because difficult to maintain consistency as complexity grows
- **Bad**, because limited expressiveness for complex relationships
- **Bad**, because no standard notation or conventions
- **Bad**, because doesn't scale to detailed component views

## Implementation Plan

### Phase 1: Foundation (Issue #110)
1. Create `docs/architecture/c4/README.md` explaining C4 model usage
2. Choose tooling: **Mermaid** (first choice - GitHub native) or **PlantUML with C4 extension** (fallback)
3. Establish diagram templates and conventions

### Phase 2: Context & Containers (Issue #111)
1. **Context diagram** (Level 1): FRANK system boundaries, users (human, service accounts), external systems (AWS services)
2. **Container diagrams** (Level 2):
   - Stage 1: SQLite + FastAPI on laptop
   - Stage 2: LocalStack + DynamoDB/MySQL + FastAPI in Docker
   - Stage 3: AWS ECS + DynamoDB + RDS PostgreSQL + Cognito
   - Stage 4: Kubernetes + ScyllaDB + distributed services (future)

### Phase 3: Components (Issue #111)
1. **Sightings API components**: Submission endpoints, query handlers, access control
2. **Management API components**: User/org management, authentication proxy, admin operations
3. **Storage abstraction**: BaseFRANKDatabase, SQLite/DynamoDB/PostgreSQL implementations

### Phase 4: Integration
1. Cross-reference C4 diagrams ↔ ADRs
2. Link C4 diagrams ↔ agent-1's specifications
3. Update existing HLD documents to reference C4 visualizations

## C4 Levels for FRANK

### Level 1: Context Diagram
**Purpose**: System boundary, users, external dependencies
**FRANK usage**: Single diagram showing human users (Web GUI/TUI/CLI), service accounts, AWS services (Cognito, CloudWatch), external threat intelligence sources

### Level 2: Container Diagrams
**Purpose**: High-level technology choices and their interactions
**FRANK usage**: Four diagrams (one per stage) showing FastAPI containers, database containers, authentication services, load balancers, monitoring

### Level 3: Component Diagrams
**Purpose**: Major structural building blocks within containers
**FRANK usage**: Three focused diagrams:
- Sightings API internal components (submission handler, query engine, access filter)
- Management API internal components (user CRUD, org management, auth proxy)
- Storage abstraction layer (base interface, stage-specific implementations)

### Level 4: Code Diagrams
**Purpose**: Class-level relationships
**FRANK usage**: **Intentionally skipped** - agent-1's specifications and Python code provide this detail

## Tooling Decision

**Primary**: **Mermaid C4 diagrams** (GitHub native rendering)
- Renders directly in GitHub without external tools
- Simple syntax: `C4Context`, `C4Container`, `C4Component`
- Version controlled as markdown code blocks
- Example: https://mermaid.js.org/syntax/c4.html

**Fallback**: **PlantUML with C4-PlantUML extension**
- More expressive than Mermaid C4 support
- Requires rendering step (CI/CD or IDE plugin)
- Example: https://github.com/plantuml-stdlib/C4-PlantUML

**Not chosen**: Structurizr DSL (commercial tool, external dependency)

## Links

- **Related ADRs**:
  - [ADR-003: Four-Stage Infrastructure Evolution](003-four-stage-infrastructure-evolution.md) - Defines stages to visualize
  - [ADR-011: Stages vs Environments](011-stages-vs-environments.md) - Distinguishes infrastructure from deployment
- **Specifications**: Agent-1's specs/ directory complements C4 with behavioral requirements
- **Existing Documentation**:
  - docs/highlevel_design.md - Current ASCII art diagrams
  - docs/hld_functional.md - Functional/business context
- **External References**:
  - [C4 Model Official Site](https://c4model.com/)
  - [C4 Model Introduction](https://c4model.com/introduction)
  - [Mermaid C4 Diagrams](https://mermaid.js.org/syntax/c4.html)
  - [PlantUML C4 Extension](https://github.com/plantuml-stdlib/C4-PlantUML)
- **GitHub Issues**:
  - Issue #110: ADR-0013 (this document)
  - Issue #111: Create C4 Architecture Diagrams
