# Documentation as Code

- **Status:** accepted
- **Date:** 2026-01-28
- **Decision Makers:** FRANK Architecture Team
- **Related:** [ADR-0010](0010-test-driven-technology-transitions.md), [ADR-0011](0011-immutable-versioned-evolution.md)

## Context and Problem Statement

Software projects often suffer from outdated documentation, lost decision context, and knowledge silos. As FRANK evolves through complex infrastructure stages with team changes, how can we preserve critical knowledge and decision rationale without creating documentation maintenance burdens?

## Decision Drivers

- Need to preserve architectural decision rationale
- Must maintain accurate documentation as code evolves
- Want to prevent knowledge loss during team transitions
- Require multiple documentation abstraction levels
- Need documentation that developers actually maintain
- Want to support AI-assisted development with clear constraints

## Considered Options

1. **Living Documentation in Code** - Documentation colocated with code, versioned together, multiple abstraction levels
2. **External Wiki** - Separate documentation system (Confluence, Wiki)
3. **Minimal Documentation** - Only code comments, rely on self-documenting code

## Decision Outcome

Chosen option: "Living Documentation in Code", because it keeps documentation synchronized with code evolution, preserves decision context, and provides multiple abstraction levels for different audiences.

Documentation captures knowledge at multiple abstraction levels and evolves alongside the codebase. Code-level docstrings, spike documentation, and architectural decisions are integral to the development process, not afterthoughts.

### Positive Consequences

- Documentation stays synchronized with code (versioned together)
- Decision rationale preserved for future reference
- Multiple abstraction levels serve different audiences
- Git history tracks documentation evolution
- Code review includes documentation validation
- AI tools have clear architectural constraints
- Knowledge preserved through team transitions

### Negative Consequences

- Requires documentation discipline from developers
- May slow initial development velocity
- Need to balance detail vs. maintenance burden
- Risk of documentation rot if not actively maintained

## Pros and Cons of the Options

### Living Documentation in Code

- Good, because documentation versions with code
- Good, because reviewed with code changes
- Good, because preserves decision context
- Good, because multiple abstraction levels
- Good, because no separate tool maintenance
- Good, because Git history tracks evolution
- Bad, because requires developer discipline
- Bad, because initial writing overhead

### External Wiki

- Good, because rich formatting options
- Good, because easy to browse and search
- Good, because non-developers can contribute
- Bad, because easily becomes outdated
- Bad, because separate from code
- Bad, because no version synchronization
- Bad, because additional tool maintenance

### Minimal Documentation

- Good, because no documentation burden
- Good, because forces clear code
- Bad, because loses decision rationale
- Bad, because no architectural context
- Bad, because knowledge loss during transitions
- Bad, because difficult onboarding

## Implementation: Multi-Level Documentation

### Level 1: Code-Level Documentation

**Docstrings** - API contracts and usage examples

```python
def store_submission(self, submission: Submission) -> str:
    """Store threat intelligence submission in database.

    Args:
        submission: Validated submission with observables and sighting data

    Returns:
        Unique submission ID (STIX format: submission--<uuid>)

    Raises:
        StorageError: If database operation fails
        ValidationError: If submission fails integrity checks

    Example:
        >>> db = FRANKDatabase()
        >>> submission = Submission.create_minimal(
        ...     submitter_org_id="org--123",
        ...     observable=Observable.create_ipv4("192.168.1.1")
        ... )
        >>> submission_id = db.store_submission(submission)
    """
```

**Requirements:**
- All public functions and classes have docstrings
- Include type hints for all parameters and returns
- Provide usage examples for complex APIs
- Document edge cases and error conditions

### Level 2: Spike Documentation

**Purpose:** Capture technology investigation learnings

**Location:** `tests/spikes/<number>_<name>/README.md`

**Required Sections:**
1. **Hypothesis** - What are we validating?
2. **Approach** - How will we test it?
3. **Implementation** - What did we build?
4. **Results** - What did we learn?
5. **Decision** - Adopt, reject, or revisit?
6. **References** - Links to relevant resources

**Example:** [tests/spikes/011_fastapi/README.md](../../tests/spikes/011_fastapi/README.md)

**Integration:**
- Created during time-boxed investigation (1-4 hours)
- Updated as spike progresses
- Reviewed before technology adoption
- Referenced in ADRs for context

### Level 3: Architectural Decision Records (This Document)

**Purpose:** Capture significant design decisions with rationale

**Location:** `docs/adr/<number>-<title>.md`

**Format:** MADR (Markdown Architectural Decision Records)

**Required Sections:**
- Status (proposed, accepted, rejected, deprecated, superseded)
- Date and decision makers
- Context and problem statement
- Decision drivers
- Considered options with pros/cons
- Decision outcome with consequences
- Implementation details
- Links to related ADRs

**When to Create:**
- New architectural pattern adoption
- Major technology selection
- Design principle establishment
- Significant trade-off resolution

**Numbering:** Sequential (0001, 0002, etc.) for cross-referencing

### Level 4: High-Level Guides

**Purpose:** Onboarding, architecture overview, development workflow

**Key Documents:**
- **[README.md](../../README.md)** - Project overview, quick start, key concepts
- **[CLAUDE.md](../../CLAUDE.md)** - AI-assisted development guide (project-specific)
- **[~/.claude/CLAUDE.md](~/.claude/CLAUDE.md)** - Global AI development preferences
- **[docs/evolutionary_design.md](../evolutionary_design.md)** - Evolution philosophy and stage details
- **[docs/architecture_principles.md](../architecture_principles.md)** - Core design principles summary
- **[CHANGELOG.md](../../CHANGELOG.md)** - Version history and changes

**Audience:** New team members, stakeholders, future maintainers

## Documentation Workflow

### During Development

1. **Write docstrings** as you write code (TDD for docs)
2. **Update spike README** as investigation progresses
3. **Reference existing ADRs** before making architectural decisions
4. **Create new ADR** if decision introduces new pattern

### During Code Review

1. **Verify docstrings** for new public APIs
2. **Check spike documentation** if technology exploration
3. **Validate ADR references** for architectural changes
4. **Update high-level docs** if major feature added

### During Release

1. **Update CHANGELOG.md** with version changes
2. **Verify README.md** reflects current capabilities
3. **Update CLAUDE.md** if development workflow changed
4. **Create ADR** for significant decisions made during release cycle

## AI-Assisted Development Support

Documentation provides critical constraints for AI tools:

**CLAUDE.md Benefits:**
- Specifies project structure conventions
- Documents testing strategy expectations
- Provides Git workflow guidelines
- References ADRs for architectural boundaries
- Guides tool selection (uv, pytest, ruff)

**ADR Benefits:**
- Prevents AI from violating design principles
- Provides rationale for seemingly arbitrary decisions
- Guides technology selection within constraints
- Enables consistent code generation

**Spike Documentation Benefits:**
- Prevents re-investigation of rejected approaches
- Provides context for technology adoption decisions
- Guides similar future explorations

## Documentation Quality Metrics

**Measurable Indicators:**
- All public APIs have docstrings (enforced by linters)
- All spikes have complete README.md
- Major decisions have corresponding ADRs
- CHANGELOG.md updated with each release
- Documentation reviewed during code review

**Red Flags:**
- Docstrings out of sync with implementation
- Spike decisions without documentation
- Architectural changes without ADR justification
- Outdated README or CLAUDE.md
- Undocumented breaking changes

## Links

- Enables [ADR-0010: Test-Driven Technology Transitions](0010-test-driven-technology-transitions.md)
- Supports [ADR-0011: Immutable Versioned Evolution](0011-immutable-versioned-evolution.md)
- Implementation: [docs/](../../docs/), [tests/spikes/](../../tests/spikes/)
- Related: [CLAUDE.md](../../CLAUDE.md)
