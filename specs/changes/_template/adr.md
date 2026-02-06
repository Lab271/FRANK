# Architectural Decision Record: [Feature Name]

⭐ **Required sections marked with star**

- **Status:** ⭐ PROPOSED | ACCEPTED | DEPRECATED | SUPERSEDED
- **ADR Number:** [Will be assigned upon acceptance, e.g., ADR-0013]
- **Date:** YYYY-MM-DD
- **Decision Makers:** ⭐ [Names of people involved in decision]
- **Related:** ⭐ [Related ADRs and specifications]

---

## Overview

⭐ **What architectural decision did we make and why?** This document captures significant design decisions for this feature.

This ADR documents decisions made during the feature development in:
- **[proposal.md](proposal.md)**: Why we need this feature
- **[spec.md](spec.md)**: What we must do
- **[design.md](design.md)**: How we'll build it
- **[tasks.md](tasks.md)**: Step-by-step implementation

Upon completion of implementation, this ADR becomes a formal architectural record in `/docs/adr/`.

---

## Decision 1: [Title of First Major Decision]

### Context and Problem Statement

⭐ **What problem are we solving?** Describe the architectural challenge.

**Example (Sightings API)**:
> We need to expose threat intelligence data through an API so organizations can query observations of threat indicators. The challenge is balancing flexibility (support SQLite in Stage 1, DynamoDB in Stages 2-4) with consistency (identical behavior across storage backends) and performance (low latency at scale).

### Decision Drivers

⭐ **What factors influenced the decision?** List forces and concerns.

**Example**:
- **Consistency**: API must work identically across all FRANK stages
- **Performance**: Query latency must be < 200ms (95th percentile)
- **Testability**: Easy to test with fake data, mocks
- **Scalability**: Support 100K+ submissions/second in Stage 4
- **Team Experience**: Team comfortable with REST APIs, not GraphQL
- **Evolutionary Design**: Design must support growth from Stage 1 → Stage 4
- **Security**: Access control must be enforced consistently

### Considered Options

⭐ **What alternatives did we evaluate?** Document trade-offs.

#### Option A: [First Alternative]

**Description**: Brief explanation of approach

**Pros**:
- ✅ Pro 1 (advantage)
- ✅ Pro 2 (advantage)

**Cons**:
- ❌ Con 1 (disadvantage)
- ❌ Con 2 (disadvantage)

**Trade-offs**: [Any other considerations]

#### Option B: [Second Alternative]

**Description**: Brief explanation of approach

**Pros**:
- ✅ Pro 1
- ✅ Pro 2

**Cons**:
- ❌ Con 1
- ❌ Con 2

**Trade-offs**: [Any other considerations]

#### Option C: [Third Alternative]

**Description**: Brief explanation of approach

**Pros**:
- ✅ Pro 1
- ✅ Pro 2

**Cons**:
- ❌ Con 1
- ❌ Con 2

**Trade-offs**: [Any other considerations]

### Decision Outcome

⭐ **What option did we choose and why?** State the decision clearly.

**Chosen Option**: [Option Name]

**Justification**: [Explain why this option was selected]

**Example (Sightings API)**:
> We chose the **REST API with Repository Pattern** approach because it:
> - Maintains consistency across all stages by delegating database differences to repository implementations
> - Provides familiar API style (GraphQL rejected due to team unfamiliarity)
> - Enables easy testing with mocks and fakes
> - Aligns with existing FRANK patterns (Spike 007, ADR-0002 Repository Pattern)
> - Supports performance requirements with appropriate indexing

### Positive Consequences

⭐ **What good things result from this decision?**

- ✅ **Consistency**: Identical API behavior across SQLite, DynamoDB, ScyllaDB
- ✅ **Testability**: Easy to mock repository for unit tests
- ✅ **Familiarity**: Team comfortable with REST design patterns
- ✅ **Evolutionary Design**: Repository pattern supports adding new backends (PostgreSQL, MongoDB) without API changes
- ✅ **Performance**: Repository implementations can optimize per storage system
- ✅ **Alignment**: Consistent with [ADR-0002 Repository Pattern](../../../docs/adr/0002-repository-pattern-database-abstraction.md)

### Negative Consequences

⭐ **What trade-offs or downsides result?**

- ⚠️ **Limited Flexibility**: Predefined queries (can't do arbitrary filtering without API changes)
- ⚠️ **API Versioning**: Changing query parameters requires major version bump
- ⚠️ **Pagination Complexity**: Must implement pagination logic in application (not database)
- ⚠️ **N+1 Queries**: Access control filtering at application layer may require multiple queries

**Mitigation Strategies**:
- Document API stability commitment (v1 will be stable for 2+ years)
- Implement pagination efficiently with database cursors
- Consider caching for frequently-accessed data (if performance testing shows need)

---

## Decision 2: [Title of Second Major Decision]

### Context and Problem Statement

⭐ **What architectural challenge are we solving?**

**Example (Access Control)**:
> We need to enforce access control ensuring users only see threat data they're authorized to access. The challenge is implementing consistent access rules across different storage backends (SQLite, DynamoDB, PostgreSQL) without code duplication or security gaps.

### Decision Drivers

- **Security**: Access control critical for compliance and data protection
- **Consistency**: Rules must be identical across all backends
- **Flexibility**: Rules should be easy to extend (new access tiers, partnership rules)
- **Testability**: Easy to test access logic in isolation
- **Performance**: Shouldn't significantly impact query latency

### Considered Options

#### Option A: Database-Level Access Control

Store access rules in database, enforce with SQL/DynamoDB queries.

**Pros**:
- ✅ Filters data at source (efficient)
- ✅ Complex rules possible (joins, subqueries)

**Cons**:
- ❌ SQLite + DynamoDB have different SQL capabilities
- ❌ Dynamic WHERE clauses prone to SQL injection
- ❌ Hard to test (integration tests required for each backend)
- ❌ Difficult to extend without changing queries

#### Option B: Application-Layer Access Control

Implement access filtering in service layer (Python code), not SQL.

**Pros**:
- ✅ Single code path across all backends
- ✅ Easy to test (mock database, test access logic independently)
- ✅ Easy to extend (add new rules without database changes)
- ✅ Clear audit trail (logs show access decisions)
- ✅ Per [ADR-0007 Forgiving Input, Strong Output](../../../docs/adr/0007-forgiving-input-strong-output.md)

**Cons**:
- ⚠️ All data retrieved before filtering (less efficient)
- ⚠️ Pagination more complex (count before filtering)

#### Option C: Hybrid Approach

Basic filtering in database (obvious rules), detailed filtering in application.

**Pros**:
- ✅ Reasonable balance of efficiency and consistency

**Cons**:
- ⚠️ Complex implementation (two filtering layers)
- ⚠️ Harder to reason about (where is each rule enforced?)

### Decision Outcome

**Chosen Option**: **Application-Layer Access Control**

**Justification**:
Access control is a business rule, not a data storage concern. Implementing in application layer ensures:
- Consistency across all FRANK stages (no database-specific logic)
- Easy testing (mock repository, test access logic)
- Clear audit trail
- Flexible extension (new rules without SQL changes)
- Per ADR-0007: "Strong output" = filtered results before returning to user

This approach is consistent with [ADR-0003 Tiered Access Control Model](../../../docs/adr/0003-tiered-access-control-model.md).

### Positive Consequences

- ✅ **Consistency**: Same access logic across SQLite, DynamoDB, PostgreSQL
- ✅ **Testability**: Access rules testable in isolation without database
- ✅ **Flexibility**: New rules added without database changes
- ✅ **Auditability**: Access decisions logged with reasoning
- ✅ **Alignment**: Consistent with ADR-0003 and ADR-0007

### Negative Consequences

- ⚠️ **Performance Impact**: All matching records retrieved before filtering
  - **Mitigation**: Database indexes filter by observable_id (most specific), pagination reduces result sets
- ⚠️ **Memory Usage**: Large result sets may exceed memory
  - **Mitigation**: Pagination (default 100, max 1000), streaming results (future enhancement)
- ⚠️ **Pagination Complexity**: Can't rely on LIMIT clause for exact pagination
  - **Mitigation**: Fetch limit+1 to check if more exist, use cursor pagination

---

## Decision 3: [Title of Third Major Decision]

### Context and Problem Statement

⭐ **What architectural challenge?**

**Example (Error Handling)**:
> We need consistent error responses across the API so clients can predictably handle failures. The challenge is balancing specificity (detailed error messages) with simplicity (don't leak internal implementation details).

### Decision Drivers

- **Usability**: Clear error messages help users fix problems
- **Security**: Don't leak sensitive information (database errors, stack traces)
- **Debugging**: Correlation IDs help support teams trace issues
- **Consistency**: Identical format across all endpoints
- **Standards**: Follow REST/HTTP conventions

### Considered Options

#### Option A: Simple Error Messages

Return minimal error info (just message).

#### Option B: Detailed Error Objects

Return structured errors with type, message, details, correlation ID.

#### Option C: Custom Exception Classes

Create custom exceptions for each error type, serialize to JSON.

### Decision Outcome

**Chosen Option**: **Detailed Error Objects**

**Justification**:
Follow [ADR-0008 Explicit Error Communication](../../../docs/adr/0008-explicit-error-communication.md) pattern for structured, actionable errors.

**Example Error Response**:
```json
{
  "error": {
    "type": "validation_error",
    "message": "One or more validation errors occurred",
    "correlation_id": "req-abc123def456",
    "details": [
      {
        "field": "confidence",
        "message": "Must be between 0 and 100",
        "value": 150
      }
    ]
  }
}
```

### Positive Consequences

- ✅ **User-Friendly**: Specific field errors help users fix input
- ✅ **Debuggable**: Correlation IDs enable log tracing
- ✅ **Secure**: Structured format prevents leaking implementation details
- ✅ **Consistent**: All endpoints return same format

### Negative Consequences

- ⚠️ **Verbose**: Larger response payloads for errors
  - **Mitigation**: Clients likely to ignore error details anyway, insignificant impact
- ⚠️ **Client Complexity**: Clients must parse nested error structure
  - **Mitigation**: Provide error handling examples and libraries

---

## Decision 4: [Title of Fourth Major Decision]

### Context and Problem Statement

⭐ **What challenge?**

**Example (Authentication)**:
> We need to authenticate API requests while supporting both local development (Stage 1) and AWS production (Stages 2-4). The challenge is using a unified authentication approach that doesn't require major changes across stages.

### Decision Drivers

- **Stage Compatibility**: Must work in Stage 1 (local) through Stage 4 (Kubernetes)
- **Security**: Tokens must be cryptographically signed and validated
- **Developer Experience**: Local development shouldn't require AWS account setup
- **Operations**: Minimal ops overhead (use managed services where possible)
- **Standards**: Follow industry standards (JWT, OAuth2)

### Considered Options

#### Option A: Mock Authentication (Stage 1 Only)

Use fake JWT tokens in Stage 1, Cognito in production.

#### Option B: AWS Cognito Everywhere

Use Cognito even in local development (with test tenant).

#### Option C: API Key Authentication (Stage 1), JWT (Production)

Different auth strategies per stage.

### Decision Outcome

**Chosen Option**: **AWS Cognito Everywhere** (with mock tokens for testing)

**Justification**:
- Developers use mock tokens in unit/integration tests
- CI/CD pipeline uses mock tokens
- Local development uses test Cognito tenant (no AWS account overhead)
- Production uses production Cognito tenant
- Same code path across all stages → fewer bugs
- Per [ADR-0005 Cognito Authentication](../../../docs/adr/0005-cognito-authentication.md)

### Positive Consequences

- ✅ **Consistency**: Same auth code across all stages
- ✅ **Security**: Production-grade auth from day one
- ✅ **Flexibility**: Mock tokens for testing, real tokens for integration
- ✅ **Alignment**: Consistent with ADR-0005

### Negative Consequences

- ⚠️ **Setup Complexity**: Developers need Cognito user pool access
  - **Mitigation**: Well-documented setup process, admin provides test users
- ⚠️ **Token Expiry**: Tokens expire, tests may fail if tokens stale
  - **Mitigation**: Mock tokens with long expiry (or never expire) for tests

---

## Decision 5: [Title of Fifth Major Decision]

### Context and Problem Statement

⭐ **What challenge?**

**Example (Pagination)**:
> We need to efficiently handle large result sets (potentially millions of sightings). The challenge is implementing pagination that works consistently across SQLite, DynamoDB, and ScyllaDB without major differences in implementation.

### Decision Drivers

- **Consistency**: Pagination must work identically across backends
- **Efficiency**: Don't load entire result set into memory
- **Simplicity**: Client implementation straightforward
- **Correctness**: Handle concurrent additions/deletions (avoid gaps/duplicates)
- **Performance**: Pagination shouldn't significantly slow queries

### Considered Options

#### Option A: Offset/Limit Pagination

```sql
SELECT * FROM sightings LIMIT 100 OFFSET 200
```

#### Option B: Cursor-Based Pagination

Use opaque token (encoded cursor) to mark position.

#### Option C: Keyset Pagination

Use actual data values (observable_id, timestamp) as cursor.

### Decision Outcome

**Chosen Option**: **Cursor-Based Pagination**

**Justification**:
- Works consistently across SQLite, DynamoDB, ScyllaDB
- Handles concurrent insertions/deletions (doesn't skip items)
- Efficient (doesn't require OFFSET which can be slow)
- Opaque cursor token doesn't expose implementation details
- Standard industry practice (used by Twitter, Facebook APIs)

**Example**:
```python
# Request
GET /api/v1/sightings?observable_id=...&limit=100&page_token=eyJvZmZzZXQiOiAyMDB9

# Response
{
  "sightings": [...],  # 100 items
  "next_page_token": "eyJvZmZzZXQiOiAzMDB9",  # For next page
  "returned_count": 100,
  "total_count": 500
}
```

### Positive Consequences

- ✅ **Consistency**: Same pagination across all backends
- ✅ **Correctness**: Handles concurrent changes correctly
- ✅ **Efficiency**: Doesn't require expensive OFFSET operations
- ✅ **Simplicity**: Opaque token, client doesn't worry about implementation

### Negative Consequences

- ⚠️ **Statelessness**: Can't jump to arbitrary page (must page sequentially)
  - **Mitigation**: Acceptable for threat data (users typically page sequentially)
- ⚠️ **Token Expiry**: Cursor validity depends on data not being deleted
  - **Mitigation**: Sightings never deleted in normal operation (only archival)

---

## Decision 6: [Title of Sixth Major Decision]

### Context and Problem Statement

⭐ **What challenge?**

**Example (Testing Strategy)**:
> We need to test the API across multiple scenarios (valid input, invalid input, access control, concurrent requests) while maintaining test execution speed and developer productivity. The challenge is balancing test coverage with maintainability.

### Decision Drivers

- **Coverage**: ≥85% code coverage required (per [ADR-0012](../../../docs/adr/0012-testing-philosophy.md))
- **Speed**: Unit tests should execute in < 5 seconds total
- **Clarity**: Tests should be easy to understand and maintain
- **Isolation**: Unit tests shouldn't depend on external services
- **Confidence**: Tests should catch real bugs

### Considered Options

#### Option A: Unit Tests Only

Fast but limited coverage of system behavior.

#### Option B: Unit + Integration Tests

Better coverage but slower execution.

#### Option C: Unit + Integration + End-to-End Tests

Comprehensive but slow execution.

### Decision Outcome

**Chosen Option**: **Unit + Integration Tests** (per [ADR-0004 Three-Layer Testing Strategy](../../../docs/adr/0004-three-layer-testing-strategy.md))

**Structure**:
1. **Unit Tests** (`tests/unit/`) - Fast, isolated, mocked dependencies
2. **Integration Tests** (`tests/integration/`) - BDD scenarios, real database (SQLite)
3. **Spike/Validation Tests** (`tests/spikes/`) - Performance, load, new technologies

### Positive Consequences

- ✅ **Coverage**: Unit + integration tests provide ≥85% coverage
- ✅ **Speed**: Unit tests fast (< 100ms each), integration < 5 seconds total
- ✅ **Clarity**: BDD scenarios document intended behavior
- ✅ **Confidence**: Real database in integration tests catches issues unit tests miss
- ✅ **Alignment**: Consistent with [ADR-0004](../../../docs/adr/0004-three-layer-testing-strategy.md)

### Negative Consequences

- ⚠️ **Maintenance**: More test code to maintain
  - **Mitigation**: Clear structure, shared fixtures, code reuse
- ⚠️ **Debugging**: Integration test failures harder to debug
  - **Mitigation**: Clear error messages, detailed logging, step definitions document scenarios

---

## Cross-Decision Dependencies

These decisions are interdependent:

```
Decision 1: REST API + Repository Pattern
    ├─ Enables Decision 2: Application-Layer Access Control
    ├─ Enables Decision 4: Consistent Authentication
    └─ Requires Decision 6: Unit + Integration Testing

Decision 2: Application-Layer Access Control
    ├─ Requires Decision 6: Unit Tests with Mock Data
    └─ Requires Decision 5: Pagination Consistency

Decision 3: Detailed Error Objects
    └─ Supports all other decisions (consistent error handling)

Decision 4: Cognito Authentication
    ├─ Supports Decision 2: Access control based on user context
    └─ Requires Decision 6: Mock tokens for testing

Decision 5: Cursor-Based Pagination
    ├─ Supports Decision 1: REST API consistency
    └─ Enables handling large datasets

Decision 6: Testing Strategy
    └─ Validates all other decisions
```

---

## Implementation Status

- [ ] Design approved by technical leads
- [ ] Feature branch created
- [ ] Code implementing these decisions written
- [ ] All tests passing
- [ ] Code reviewed
- [ ] Merged to main
- [ ] Deployed to production
- [ ] ADR formally added to `/docs/adr/` directory

---

## Review & Approval

**Architecture Review**:
- [ ] Reviewed by: [Architects/Tech Leads]
- [ ] Date: YYYY-MM-DD
- [ ] Feedback: [Summary of review feedback]

**Final Decision**:
- [ ] Status: PROPOSED | ACCEPTED | REJECTED
- [ ] Approved by: [Decision maker(s)]
- [ ] Date: YYYY-MM-DD
- [ ] Notes: [Any final notes]

---

## Related Documentation

### ADRs

- [ADR-0002: Repository Pattern & Database Abstraction](../../../docs/adr/0002-repository-pattern-database-abstraction.md)
- [ADR-0003: Tiered Access Control Model](../../../docs/adr/0003-tiered-access-control-model.md)
- [ADR-0004: Three-Layer Testing Strategy](../../../docs/adr/0004-three-layer-testing-strategy.md)
- [ADR-0005: Cognito Authentication](../../../docs/adr/0005-cognito-authentication.md)
- [ADR-0007: Forgiving Input, Strong Output](../../../docs/adr/0007-forgiving-input-strong-output.md)
- [ADR-0008: Explicit Error Communication](../../../docs/adr/0008-explicit-error-communication.md)
- [ADR-0012: Testing Philosophy](../../../docs/adr/0012-testing-philosophy.md)

### Related Specifications

- [Proposal: [Feature Name]](proposal.md)
- [Specification: [Feature Name]](spec.md)
- [Design: [Feature Name]](design.md)
- [Implementation Tasks: [Feature Name]](tasks.md)

### Related Spikes

- [Spike 007: FastAPI Application Structure](../../../tests/spikes/007_fastapi/README.md)
- [Spike 012: DynamoDB Table Design](../../../tests/spikes/012_aws_dynamodb/README.md)
- [Spike 014: Cognito Integration](../../../tests/spikes/014_cognito/README.md)
- [Spike 015: FastAPI Testing Patterns](../../../tests/spikes/015_fastapi_testing/README.md)

---

## Future Considerations

**Potential Enhancements** (deferred from MVP):
- [ ] GraphQL API alternative (consider in Phase 2)
- [ ] Real-time notifications via WebSocket (Kafka-based)
- [ ] Caching layer for frequently-accessed data (Redis)
- [ ] Rate limiting per organization
- [ ] Bulk operations (bulk query, bulk update)
- [ ] Export formats (CSV, JSON, STIX)

**Evolution Path**:
- **Stage 1**: SQLite, all endpoints, mock tokens
- **Stage 2**: DynamoDB, LocalStack, same endpoints
- **Stage 3**: AWS production deployment
- **Stage 4**: ScyllaDB, Kubernetes, multi-region

---

## Appendix: Decision History

| Decision | Status | Date | Notes |
|----------|--------|------|-------|
| D1: REST API + Repository | ACCEPTED | YYYY-MM-DD | Chosen over GraphQL and event-driven approaches |
| D2: Application-Layer Access | ACCEPTED | YYYY-MM-DD | Chosen over database-level filtering |
| D3: Detailed Error Objects | ACCEPTED | YYYY-MM-DD | Per ADR-0008 pattern |
| D4: Cognito Authentication | ACCEPTED | YYYY-MM-DD | Per ADR-0005 pattern |
| D5: Cursor-Based Pagination | ACCEPTED | YYYY-MM-DD | Standard industry practice |
| D6: Unit + Integration Testing | ACCEPTED | YYYY-MM-DD | Per ADR-0004 three-layer strategy |

---

**Status**: [PROPOSED | ACCEPTED | DEPRECATED | SUPERSEDED]

**Next Steps**: [What happens after approval]

---

*This ADR was created during the feature development process. Upon completion and formal review, it will be integrated into `/docs/adr/` with an assigned ADR number (e.g., ADR-0013).*
