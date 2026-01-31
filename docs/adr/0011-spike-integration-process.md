# Spike Integration Process

- **Status:** accepted
- **Date:** 2026-01-31
- **Decision Makers:** Development Team
- **Related:** [ADR-0004](0004-three-layer-testing-strategy.md), [ADR-0001](0001-four-stage-infrastructure-evolution.md)

## Context and Problem Statement

FRANK uses time-boxed spikes (1-4 hours) to explore technologies, validate hypotheses, and learn patterns before committing to production implementation. However, the process for transitioning spike learnings into production code is not formally documented. When should a spike be considered "done"? How do we integrate validated patterns into stages? What happens to spike code after integration? This lack of process creates uncertainty about spike outcomes and makes it difficult to track which spikes contributed to which stage implementations.

## Decision Drivers

- Need clear criteria for when a spike successfully validates a hypothesis
- Must define the path from spike exploration to production integration
- Should maintain spike history for future reference and learning
- Must prevent spike code from being directly used in production
- Documentation should capture the relationship between spikes and stage features

## Considered Options

1. **Formalize Spike Lifecycle with Integration Checklist** - Define stages: Create → Validate → Integrate → Archive
2. **Informal Spike Process** - Continue current ad-hoc approach where spike outcomes are not tracked
3. **Spike-to-Production Direct Promotion** - Treat spikes as alpha implementations that can be promoted directly

## Decision Outcome

Chosen option: "Formalize Spike Lifecycle with Integration Checklist", because it provides clarity on spike outcomes, maintains institutional knowledge, and ensures production code is intentionally designed rather than promoted from experimental code.

### Positive Consequences

- Clear criteria for spike success or failure
- Documented path from exploration to production
- Spike history becomes learning resource for team
- Prevents experimental code from leaking into production
- Makes it easy to identify which spikes contributed to which features

### Negative Consequences

- Requires discipline to document spike outcomes
- Adds overhead to spike process (update README, track status)
- Team must remember to update spike index when integrating

## Spike Lifecycle

### Phase 1: Create (Hypothesis-Driven Exploration)

**Objective:** Explore a technology or pattern in a time-boxed manner to validate or reject a hypothesis.

**Process:**
1. Create spike directory: `tests/spikes/NNN_descriptive_name/`
2. Create `README.md` with required sections (see Template below)
3. Document clear hypothesis and validation criteria
4. Set time limit (typically 1-4 hours)
5. Implement minimal code to test hypothesis
6. Create validation tests (files ending in `*_test.py`)

**Outputs:**
- Spike directory with code and tests
- README documenting hypothesis and approach
- Initial validation results

**Example:** Spike 014_cognito explored AWS Cognito authentication patterns.

### Phase 2: Validate (Assess Outcomes)

**Objective:** Determine if the spike proved or disproved the hypothesis and decide next steps.

**Validation Criteria:**
- ✅ **Hypothesis Confirmed**: Technology/pattern works as expected
- ⚠️ **Hypothesis Modified**: Works, but with caveats or adjustments
- ❌ **Hypothesis Rejected**: Technology/pattern not suitable

**Process:**
1. Run validation tests: `pytest tests/spikes/NNN_*/test_*.py`
2. Document results in README "Validation Results" section
3. Capture learnings (surprises, gotchas, limitations)
4. Decide: Integrate, Archive, or Abandon
5. Update spike status in README

**Outputs:**
- Updated README with validation results
- Clear decision on next steps
- Documented learnings

**Example:** Spike 003_pydantic confirmed Pydantic v2 improved validation with factory methods and field validators.

### Phase 3: Integrate (Production Implementation)

**Objective:** Extract validated patterns from spike and implement them properly in production code.

**Integration Checklist:**
- [ ] **Extract Patterns**: Identify reusable patterns from spike code
- [ ] **Design Production API**: Design proper interfaces (don't copy-paste spike code)
- [ ] **Implement in Main Codebase**: Write production-quality implementation in `src/frank/`
- [ ] **Add Production Tests**: Write comprehensive unit/integration tests
- [ ] **Update Documentation**: Document feature in relevant stage/module README
- [ ] **Update Spike README**: Document "Integrated Into" section with file paths
- [ ] **Update Spike Index**: Mark spike as INTEGRATED in `tests/spikes/index.md`

**Key Principle:** **Never directly promote spike code to production.** Spike code is experimental and exploratory. Production code should be intentionally designed based on spike learnings.

**Outputs:**
- Production implementation in `src/frank/` or `stages/`
- Production tests in `tests/unit/` or `tests/integration/`
- Updated spike README showing integration paths
- Updated spike index

**Example:** Spike 014_cognito patterns were integrated into:
- `src/frank/auth/jwt.py` - JWT validation patterns
- `src/frank/auth/cognito.py` - Cognito client wrapper
- `tests/stubs/cognito/` - Mock Cognito stub service (future location)

### Phase 4: Archive (Preserve Knowledge)

**Objective:** Maintain spike as reference documentation and historical record.

**Process:**
1. Spike directory remains in `tests/spikes/` (not deleted)
2. Spike README becomes reference for understanding production implementation
3. Spike validation tests may be removed if redundant with production tests
4. Spike status in index.md marked as INTEGRATED or ARCHIVED

**Spike Status Values:**
- **INTEGRATED**: Patterns successfully incorporated into production code
- **ACTIVE**: Currently being explored or integrated
- **ARCHIVED**: Exploration complete, kept for reference
- **ABANDONED**: Hypothesis rejected, kept as negative learning

**Outputs:**
- Preserved spike directory with README
- Historical record of what was tried and why
- Learning resource for future team members

## Spike README Template

Every spike must include a `README.md` with these sections:

```markdown
# Spike NNN: [Descriptive Title]

**Status:** ACTIVE | INTEGRATED | ARCHIVED | ABANDONED
**Time Box:** [X] hours
**Date:** YYYY-MM-DD

## Hypothesis

[Clear, testable statement of what you're exploring]

Example: "AWS Cognito can provide JWT-based authentication for FRANK APIs with role-based access control."

## Problem Statement

[What problem are we trying to solve?]
[Why do we need to explore this now?]

## Validation Criteria

[How will we know if the hypothesis is confirmed?]

- [ ] Criterion 1 (e.g., Can generate valid JWT tokens)
- [ ] Criterion 2 (e.g., Can validate tokens with JWKS)
- [ ] Criterion 3 (e.g., Supports role-based groups)

## Implementation

[Brief description of what you built to test the hypothesis]
[Key files and their purposes]

## Validation Results

[What did you learn?]
[Were validation criteria met?]
[Any surprises or gotchas?]

## Integration Status

**Integrated Into:**
- `src/frank/module/file.py` - [What pattern was extracted]
- `stages/stageN/` - [How it was used]

**Production Implementation:** [Link to relevant production code or PR]

## Learnings

[Key takeaways for the team]
[What would you do differently next time?]
[Any follow-up work needed?]

## References

[External documentation, blog posts, Stack Overflow links]
```

**Minimal Required Sections:**
- Hypothesis (what you're testing)
- Validation Criteria (how you'll know if it worked)
- Validation Results (what you learned)
- Integration Status (where patterns were used)

## Examples: Successful Spike Integrations

### Spike 003: Pydantic v2 Validation

**Hypothesis:** Pydantic v2 can improve FRANK's data model validation with factory methods and field validators.

**Validation:** ✅ Confirmed - Pydantic v2 provides excellent validation and serialization.

**Integration:**
- `src/frank/core/models.py` - All core models use Pydantic v2
- Factory methods: `Observable.create_ipv4()`, `Submission.create_minimal()`
- Field validators: `@field_validator()` for custom validation
- Model validators: `@model_validator(mode="after")` for cross-field checks
- Serializers: `@field_serializer()` for datetime → ISO string

**Learnings:**
- ConfigDict(extra="ignore") provides forgiving input parsing
- Factory methods improve API ergonomics
- Field serializers essential for consistent JSON output

### Spike 014: AWS Cognito Authentication

**Hypothesis:** AWS Cognito can provide JWT-based authentication with role-based access control for FRANK APIs.

**Validation:** ✅ Confirmed - Cognito supports JWT with custom groups for access tiers.

**Integration:**
- `src/frank/auth/jwt.py` - JWT validation with RS256 (JWKS) and HS256
- `src/frank/auth/cognito.py` - Cognito client wrapper
- `src/frank/auth/dependencies.py` - FastAPI dependencies for auth
- `tests/stubs/cognito/stub_cognito.py` - Stub Cognito service for local testing

**Learnings:**
- Mock Cognito service essential for local development
- JWKS endpoint pattern enables stateless validation
- Group-based access control maps cleanly to AccessTier enum

### Spike 008: Terraform (Abandoned Example)

**Hypothesis:** Terraform can manage FRANK's AWS infrastructure more effectively than Ansible.

**Validation:** ❌ Rejected - Terraform state management complexity outweighed benefits.

**Integration:** None (spike abandoned)

**Learnings:**
- Terraform state file creates single point of failure
- Ansible's idempotent playbooks sufficient for FRANK's needs
- Team familiarity with Ansible reduces cognitive load

**Status:** ABANDONED - Spike demonstrates what NOT to do is as valuable as what TO do.

## Integration vs Architecture Decisions

**Spike Integration (This ADR):**
- Tactical: How to implement a specific technology or pattern
- Time-boxed: 1-4 hours of exploration
- Code-focused: Produces working prototype
- Outcome: Integrate patterns into production or abandon

**Architecture Decisions (ADRs):**
- Strategic: Why we chose an approach or technology
- Timeless: Documents long-term decisions
- Rationale-focused: Explains trade-offs and consequences
- Outcome: Team alignment on architectural direction

**Relationship:** Major spikes that influence architecture should result in ADRs. For example, Spike 014 (Cognito) led to ADR-0005 (Cognito Authentication Strategy).

## Links

- [ADR-0004: Three-Layer Testing Strategy](0004-three-layer-testing-strategy.md) - Spike tests are Layer 3
- [ADR-0001: Four-Stage Infrastructure Evolution](0001-four-stage-infrastructure-evolution.md) - Spikes feed stage evolution
- `tests/spikes/index.md` - Spike inventory and status tracking
- `tests/spikes/*/README.md` - 15+ spike examples
