# Immutable Versioned Evolution

- **Status:** accepted
- **Date:** 2026-01-28
- **Decision Makers:** FRANK Architecture Team
- **Related:** [ADR-0003](0003-controlled-complexity-introduction.md)

## Context and Problem Statement

Software projects often struggle with unclear progress tracking, difficulty reproducing issues, and uncertainty about deployment readiness. How should FRANK track its evolution through four stages while ensuring every captured state is deployable and represents real value?

## Decision Drivers

- Need precise tracking of capability growth over time
- Must enable reproduction of any historical state
- Want deployment confidence at every evolution step
- Require clear communication of delivered value to stakeholders
- Need rollback capability to known-good states
- Must support multiple concurrent version deployments

## Considered Options

1. **Milestone-Based Versioning** - Git tags for functional milestones, immutable deployable states
2. **Continuous Deployment** - No explicit versions, always deploy latest main
3. **Time-Based Releases** - Regular release cadence regardless of completeness

## Decision Outcome

Chosen option: "Milestone-Based Versioning", because it ensures every tagged version represents complete, deployable functionality and provides precise capability tracking.

Each functional milestone represents a complete, deployable system captured with Git version tags. No "work in progress" states exist in version tags, ensuring immediate value delivery at every evolution step.

### Positive Consequences

- Every version tag is deployable immediately
- Clear tracking of capability evolution over time
- Easy rollback to any previous working state
- Precise issue reproduction by version
- Stakeholder confidence in predictable value delivery
- Docker tags correspond to functional Git tags
- Database schema versions enable safe migrations

### Negative Consequences

- Requires discipline to wait for completion before tagging
- May create pressure to delay tags until "perfect"
- Need clear criteria for what constitutes a milestone
- Feature branches may live longer than continuous deployment

## Pros and Cons of the Options

### Milestone-Based Versioning

- Good, because every tag represents working functionality
- Good, because precise capability tracking
- Good, because reliable rollback capability
- Good, because clear stakeholder communication
- Good, because reproducible issue investigation
- Good, because aligns with staged evolution approach
- Bad, because requires versioning discipline
- Bad, because may slow apparent progress

### Continuous Deployment

- Good, because fastest time to production
- Good, because simple deployment process
- Good, because no versioning overhead
- Bad, because unclear what capabilities exist at any time
- Bad, because difficult to rollback to known-good state
- Bad, because hard to reproduce historical issues
- Bad, because stakeholder uncertainty about progress

### Time-Based Releases

- Good, because predictable release schedule
- Good, because regular stakeholder updates
- Bad, because may release incomplete features
- Bad, because artificial deadlines drive decisions
- Bad, because version numbers don't reflect capabilities
- Bad, because pressure to include "something" in each release

## Implementation: Multi-Layer Versioning

### Git Tags: Functional Milestones

Version format: `vMAJOR.MINOR.PATCH` (Semantic Versioning)

- **MAJOR** - Breaking changes or major stage completion
- **MINOR** - New features, infrastructure evolution
- **PATCH** - Bug fixes, minor improvements

**Tagging Rules:**
1. Only tag when functionality is complete and tested
2. Tag message describes capabilities delivered
3. All tests must pass before tagging
4. Documentation updated to reflect new capabilities
5. No "WIP" or incomplete features in tagged versions

**Stage Completion Tags:**
- `v0.1.0` - Stage 1 complete (SQLite + FastAPI)
- `v0.2.0` - Stage 2 complete (DynamoDB + LocalStack)
- `v0.3.0` - Stage 3 complete (DynamoDB + ECS)
- `v0.4.0` - Stage 4 complete (ScyllaDB + Kubernetes)

### Docker Tags: Deployment Artifacts

Docker images tagged to match Git versions:
```bash
frank:v0.2.1          # Specific version
frank:v0.2            # Latest patch in minor version
frank:stage2          # Latest for infrastructure stage
frank:latest          # Latest overall (stage3+ only)
```

**Immutability:** Once published, Docker tags never change (except `:latest` and stage tags)

### Database Schema Versions

Migration tracking in database:
```sql
CREATE TABLE schema_versions (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMP,
    git_tag TEXT,
    description TEXT
);
```

**Migration Rules:**
1. Migrations are forward-only (no down migrations in production)
2. Each migration tagged with Git version
3. Schema version checked at application startup
4. Rollback requires restoring database backup

### Configuration Versions

Environment configurations tracked in Git:
```
config/
├── stage1/
│   └── config.v0.1.0.yaml
├── stage2/
│   └── config.v0.2.0.yaml
└── stage3/
    └── config.v0.3.0.yaml
```

**Version Matching:** Configuration version must match application version

## Version Control Workflow

### Development Flow

1. **Feature Branch** - Work in progress, no version constraints
2. **Main Branch** - Only complete, tested features
3. **Version Tag** - Applied to main when milestone complete
4. **Release Branch** - Created from tag for production deployment

### CI/CD Integration

GitHub Actions workflow:
- **Trigger on tag push** - `v*` pattern
- **Build Docker image** - Tagged with Git version
- **Run full test suite** - Must pass for deployment
- **Push to registry** - Immutable image published
- **Update deployment** - Infrastructure deployment triggered

### Deployment Validation

Before tagging new version:
1. All unit tests pass (≥85% coverage)
2. All integration tests pass
3. Documentation updated
4. CHANGELOG.md updated with changes
5. Migration scripts tested (if database changes)
6. Stage-appropriate infrastructure validated

## Version Communication

### CHANGELOG.md

Maintains human-readable version history:
```markdown
# Changelog

## [0.2.1] - 2026-01-28

### Added
- DynamoDB query optimization
- Audit logging for all submissions

### Fixed
- Observable deduplication bug
- Access tier filtering edge case
```

### Version Information

Application exposes version information:
```python
# src/frank/__init__.py
__version__ = "0.2.1"

# API endpoint
GET /v1/version
{
    "version": "0.2.1",
    "stage": 2,
    "git_commit": "a48b475",
    "build_date": "2026-01-28T10:30:00Z"
}
```

## Links

- Supports [ADR-0003: Controlled Complexity Introduction](0003-controlled-complexity-introduction.md)
- Related: [CHANGELOG.md](../../CHANGELOG.md)
- Related: [docs/evolutionary_design.md](../evolutionary_design.md)
