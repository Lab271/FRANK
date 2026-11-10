# ADR-005: Three-Layer Testing Strategy

- **Status:** Superseded by [ADR-018](018-container-is-the-reference-and-test-tiers.md) (four test tiers around the container image)
- **Date:** 2026-01-23

## Context

FRANK's evolutionary approach (ADR-0001) requires aggressive experimentation while maintaining system reliability. Each infrastructure stage transition introduces risk. Without comprehensive testing, the team cannot:

- Refactor safely
- Validate new technologies before adoption
- Ensure database implementations behave identically
- Maintain confidence during infrastructure evolution

Key requirements:
- Fast feedback for developers (unit tests < 100ms)
- Confidence in system integration (integration tests)
- Validation of new technologies before commitment (spike tests)
- Coverage threshold enforcement (>85%)

## Decision

Implement a **three-layer testing strategy** with distinct purposes:

### Layer 1: Unit Tests (`tests/unit/`)

**Purpose**: Fast, isolated component testing

**Characteristics**:
- Execution time: < 100ms per test
- Dependencies: Mocked or stubbed
- Scope: Single function, class, or module
- Coverage: High (>85% of business logic)

**Organization**:
```
tests/unit/
├── core/           # Business logic tests
│   ├── test_models.py
│   └── test_enum.py
├── storage/        # Repository tests
│   ├── test_sqlite.py
│   └── test_dynamodb.py
└── util/           # Utility tests
```

**Run**: `pytest tests/unit/` or `make test`

### Layer 2: Integration Tests (`tests/integration/`)

**Purpose**: System confidence through component interaction testing

**Characteristics**:
- Uses BDD/Behave with Gherkin syntax
- Tests real component interactions
- Validates API endpoints, database operations
- Slower than unit tests but higher confidence

**Organization**:
```
tests/integration/
├── features/
│   ├── submission.feature
│   └── access_control.feature
└── steps/
    └── submission_steps.py
```

**Run**: `behave tests/integration/`

### Layer 3: Spike Tests (`tests/spikes/`)

**Purpose**: Hypothesis-driven learning and technology validation

**Characteristics**:
- Time-boxed investigations (1-4 hours)
- Validate new technologies before adoption
- Files ending in `*_test.py` run with pytest
- Each spike includes `README.md` with hypothesis/results

**Organization**:
```
tests/spikes/
├── 010_cognito/
│   ├── README.md        # Hypothesis, approach, results
│   ├── cognito_test.py  # Validation tests
│   └── spike_code.py    # Experimental code
└── 011_fastapi/
    ├── README.md
    └── fastapi_test.py
```

**Run**: `pytest tests/spikes/ -k "*_test.py"`

### Coverage Requirements

- **CI/CD enforces 85% minimum**: `--cov-fail-under=85`
- Coverage reports uploaded as artifacts
- PR comments show coverage percentage

### Test Philosophy

> Tests are the safety net enabling aggressive experimentation.

Without comprehensive tests, infrastructure evolution becomes risky. With tests, the team can:
- Swap SQLite for DynamoDB and verify identical behavior
- Refactor business logic without fear
- Validate spikes before committing to technologies

## Consequences

### Positive

- **Fearless Refactoring**: High coverage enables aggressive improvement
- **Safe Technology Transitions**: Spike tests validate before commitment
- **Fast Feedback**: Unit tests catch issues immediately
- **Documentation**: Spike READMEs capture decision rationale

### Negative

- **Test Maintenance**: Three layers require ongoing effort
- **Spike Overhead**: Time-boxed investigations add process
- **Coverage Chasing**: 85% threshold may encourage low-value tests

### Tradeoffs

Higher coverage thresholds (e.g., 95%) would catch more edge cases but slow development. 85% balances confidence with velocity.

## Alternatives Considered

### Unit Tests Only
Skip integration and spike tests.

**Rejected**: Unit tests can't validate component interactions or technology decisions. Infrastructure transitions would be high-risk.

### End-to-End Tests Only
Test the full system through the UI/API.

**Rejected**: E2E tests are slow and brittle. Hard to isolate failures. Not suitable for fast development feedback.

### No Coverage Requirements
Let developers decide test coverage.

**Rejected**: Without enforcement, coverage drifts downward over time. 85% threshold maintains baseline quality.

## Validation

Testing strategy validated through:

1. **CI Pipeline**: GitHub Actions runs all three layers
2. **Coverage Reports**: Artifacts show coverage trends
3. **Spike Success Rate**: Technologies validated by spikes have lower failure rate in production

Evidence:
- `tests/spikes/010_cognito/` - Validated Cognito authentication
- `tests/spikes/011_fastapi/` - Established FastAPI testing patterns
- Coverage maintained >85% across releases

## Related ADRs

- ADR-0001: Four-Stage Infrastructure Evolution
- ADR-0002: Repository Pattern for Database Abstraction

## Implementation Notes

- pytest configuration: `pyproject.toml`
- CI workflow: `.github/workflows/main.yml`
- Coverage: `pytest --cov=src/frank --cov-report=term-missing`
- BDD: `behave tests/integration/`
