# [Feature/System Name] Specification

⭐ **Required fields marked with star**

- **Status:** ⭐ DRAFT | REVIEW | APPROVED | IMPLEMENTED | SUPERSEDED
- **Version:** 1.0
- **Last Updated:** YYYY-MM-DD
- **Owner:** ⭐ [Name or Team responsible for this spec]
- **Related ADRs:** [ADR-0000](../../docs/adr/0000-title.md), [ADR-0001](../../docs/adr/0001-title.md)
- **Issue:** ⭐ #XXX (GitHub issue number)
- **GitHub PR:** [Link to implementation PR(s) when implemented]

---

## 1. Purpose

⭐ **Why does this specification exist?** Provide a clear, concise explanation of:
- The problem this feature solves
- The business or technical value it provides
- Why now is the right time to implement it
- How it connects to FRANK's overall vision

**Example**:
> The Sightings API provides a unified interface for sharing threat intelligence observations across organizations. This addresses the core value proposition of FRANK: enabling structured feedback about cyber risks. Without a formal API, threat data remains siloed in individual systems.

---

## 2. Functional Requirements

⭐ **What must the system do?** List all functional requirements the implementation must satisfy.

### Requirement 1: [Title]
- **Description**: What is this requirement about?
- **Acceptance Criteria**: How do we verify this works?
  - [ ] Criterion A: testable condition
  - [ ] Criterion B: measurable outcome
  - [ ] Criterion C: verifiable behavior
- **Stage Availability**: Which FRANK stages support this? (Stages 1, 2, 3, 4 or subset)
- **Related ADR(s)**: [ADR-0002](../../docs/adr/0002-title.md)

### Requirement 2: [Title]
- **Description**: ...
- **Acceptance Criteria**:
  - [ ] ...
- **Stage Availability**: ...

### Requirement 3: [Title]
- **Description**: ...
- **Acceptance Criteria**:
  - [ ] ...
- **Stage Availability**: ...

**Example Requirements for an API**:

### Requirement 1: API Endpoint Structure
- **Description**: Sightings API must follow RESTful conventions with consistent URL patterns
- **Acceptance Criteria**:
  - [ ] POST `/api/v1/sightings` creates new sighting
  - [ ] GET `/api/v1/sightings/{id}` retrieves specific sighting
  - [ ] GET `/api/v1/sightings?filter=...` queries with filters
  - [ ] PUT `/api/v1/sightings/{id}` updates existing sighting
  - [ ] DELETE `/api/v1/sightings/{id}` removes sighting (with auth checks)
- **Stage Availability**: Stages 1, 2, 3, 4 (all stages support basic endpoints)

---

## 3. Non-Functional Requirements

⭐ **How well must it work?** Specify performance, scalability, security, and other quality attributes.

### Performance
- **Latency**: Target response times (e.g., "95th percentile < 500ms")
- **Throughput**: Request rate expectations (e.g., "1000 requests/second per stage")
- **Concurrency**: Expected simultaneous users or connections

### Scalability
- **Data Volume**: Expected dataset sizes (e.g., "millions of observables")
- **Growth Rate**: How fast data grows (e.g., "10% monthly increase")
- **Stage Scaling**: Approach for each evolutionary stage

### Reliability
- **Availability**: Uptime targets (e.g., "99.9% availability")
- **Error Handling**: How failures are managed and reported
- **Recovery**: Strategies for data loss prevention and recovery

### Security
- **Authentication**: Which authentication methods (see [ADR-0005](../../docs/adr/0005-cognito-authentication.md))
- **Authorization**: Access control model (see [ADR-0003](../../docs/adr/0003-tiered-access-control-model.md))
- **Data Protection**: Encryption, PII handling, audit logging

### Usability
- **API Clarity**: Clear error messages, documentation
- **Backwards Compatibility**: How existing clients are maintained
- **Migration Path**: How to upgrade from previous versions

**Example Non-Functional Requirements**:

### Performance
- **Latency**: 95th percentile response time < 200ms for query operations
- **Throughput**: Support 1000 sighting submissions per second per Stage
- **Concurrency**: Handle 100+ concurrent requests in Stage 1 (SQLite), 10000+ in Stage 3 (AWS)

### Security
- **Authentication**: AWS Cognito JWT tokens (per [ADR-0005](../../docs/adr/0005-cognito-authentication.md))
- **Authorization**: Access tier filtering (PUBLIC, OBSERVER, CONTRIBUTOR, etc. per [ADR-0003](../../docs/adr/0003-tiered-access-control-model.md))
- **Audit**: All sighting modifications logged with timestamp and actor

---

## 4. Data Model / API Contract

⭐ **What are the specific data structures, field definitions, and contracts?**

### Data Models

For backend specifications, define Pydantic models or database schemas:

```python
# Example: Sighting data model
class Sighting(BaseModel):
    """Observation of a threat indicator in the wild."""

    id: str = Field(
        default_factory=lambda: f"sighting--{uuid.uuid4()}",
        description="STIX-compliant sighting identifier"
    )
    observable_id: str = Field(
        description="Reference to Observable being sighted"
    )
    observed_at: datetime = Field(
        description="When the threat indicator was observed"
    )
    reporter_organization: str = Field(
        description="Organization that reported this sighting"
    )
    confidence: int = Field(
        ge=0, le=100,
        description="Confidence level (0-100)"
    )
    details: dict = Field(
        default_factory=dict,
        description="Free-form details about the sighting"
    )

    class Config:
        extra = "ignore"  # Be forgiving on input per ADR-0007
```

### API Endpoints

For API specifications, document each endpoint:

```
POST /api/v1/sightings
├─ Request
│  ├─ Headers: Authorization: Bearer {jwt_token}
│  ├─ Content-Type: application/json
│  └─ Body:
│     {
│       "observable_id": "observable--abc123",
│       "observed_at": "2026-02-06T10:30:00Z",
│       "reporter_organization": "ACME Corp",
│       "confidence": 95,
│       "details": {"context": "found in malware sample"}
│     }
├─ Response (201 Created):
│  ├─ Body: {full Sighting object}
│  └─ Headers: Location: /api/v1/sightings/{sighting_id}
├─ Error Responses:
│  ├─ 400 Bad Request: Invalid field values
│  ├─ 401 Unauthorized: Missing/invalid token
│  ├─ 403 Forbidden: Insufficient access tier
│  └─ 409 Conflict: Observable not found or archived

GET /api/v1/sightings/{id}
├─ Request
│  ├─ Headers: Authorization: Bearer {jwt_token}
│  ├─ Path Params: id (sighting ID)
│  └─ Query Params: None
├─ Response (200 OK):
│  └─ Body: {Sighting object}
├─ Error Responses:
│  ├─ 401 Unauthorized: Missing/invalid token
│  ├─ 403 Forbidden: Insufficient access to sighting's organization
│  └─ 404 Not Found: Sighting doesn't exist
```

### Error Response Format

All API errors follow a consistent format per [ADR-0008](../../docs/adr/0008-explicit-error-communication.md):

```json
{
  "error": {
    "type": "validation_error",
    "message": "Human-readable error message",
    "details": {
      "field": "field_name",
      "issue": "specific validation failure"
    }
  }
}
```

---

## 5. Test Coverage Requirements

⭐ **What tests must exist?** Define testing strategy and coverage targets.

### Unit Tests

Tests for individual functions and classes:

```python
# Location: tests/unit/apis/test_sightings_api.py
def test_create_sighting_with_valid_data():
    """Sightings API creates sighting with valid data."""
    # Arrange
    client = TestClient(app)
    valid_sighting = {...}

    # Act
    response = client.post("/api/v1/sightings", json=valid_sighting)

    # Assert
    assert response.status_code == 201
    assert response.json()["id"].startswith("sighting--")
```

**Required Unit Test Coverage**:
- [ ] Happy path: Valid input → Success
- [ ] Validation errors: Invalid input → 400 Bad Request
- [ ] Authentication: Missing/invalid tokens → 401 Unauthorized
- [ ] Authorization: Insufficient access → 403 Forbidden
- [ ] Edge cases: Boundary values, empty data, special characters
- [ ] Error handling: Database failures, timeouts, network errors

**Coverage Target**: ≥85% code coverage (per [ADR-0012](../../docs/adr/0012-testing-philosophy.md))

### Integration Tests

Tests for system-wide behavior using BDD/Behave:

```gherkin
# Location: tests/integration/sightings_api.feature
Feature: Sightings API

  Scenario: User submits sighting of known malicious IP
    Given an authenticated user with CONTRIBUTOR tier
    And a known malicious IPv4 observable exists
    When the user submits a sighting of that observable
    Then the sighting is stored successfully
    And the sighting is retrievable via API
    And the submission is audited
```

**Required Integration Test Scenarios**:
- [ ] Complete submission workflow (create → read → update → delete)
- [ ] Access control enforcement (different tiers see different data)
- [ ] Cross-stage compatibility (same data model across stages)
- [ ] Concurrent submissions (race conditions, atomicity)
- [ ] Database persistence (data survives restarts)

### Spike/Validation Tests

For new technologies or patterns, use spike tests in `tests/spikes/`:

**Location**: `tests/spikes/XXX_feature_validation_test.py`

**Required Spike Tests**:
- [ ] Technology feasibility (does chosen technology work?)
- [ ] Performance validation (meets NFR targets?)
- [ ] Integration validation (works with existing systems?)

### Coverage Summary

| Test Type | Location | Coverage Target | Purpose |
|-----------|----------|-----------------|---------|
| Unit | `tests/unit/` | ≥85% | Fast feedback on component behavior |
| Integration | `tests/integration/` | Key workflows | System-wide behavior validation |
| Spike | `tests/spikes/` | New technologies | Proof of concept and learning |

---

## 6. Implementation Status

⭐ **What's the current state of implementation?** Update as work progresses.

### Checklist

- [ ] Specification complete and reviewed
- [ ] Design document approved
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Implementation complete
- [ ] Code review passed
- [ ] Documentation updated
- [ ] Merged to main branch
- [ ] Released in version X.Y.Z

### Progress Notes

**Current Phase**: [DRAFT | REVIEW | APPROVED | IN-PROGRESS | COMPLETE]

**Latest Update**: [Date and brief summary of progress]

### PR Links

- [PR #XXX](https://github.com/example/frank/pull/XXX) - Implementation
- [PR #XXX](https://github.com/example/frank/pull/XXX) - Tests
- [PR #XXX](https://github.com/example/frank/pull/XXX) - Documentation

### Implementation Notes

Document insights from actual implementation that differ from spec:

- **Discovered Issue A**: [Explanation and workaround]
- **Performance Finding B**: [Actual performance vs. expected]
- **Design Adjustment C**: [What changed and why]

---

## 7. Evolution Path Across FRANK Stages

⭐ **How does this feature work across FRANK's four evolutionary stages?**

Reference: [FRANK Four-Stage Evolution](../../docs/evolutionary_design.md)

### Stage 1: SQLite + FastAPI (Local Development)

- **Status**: ✅ Fully implemented | ⚠️ Partial | ❌ Not supported
- **Implementation Details**: How this feature works in Stage 1
- **Limitations**: Any constraints specific to SQLite
- **Example**: "All sightings stored in single SQLite database on developer laptop"

### Stage 2: DynamoDB + MySQL + Docker (Learning Stage)

- **Status**: ✅ Fully implemented | ⚠️ Partial | ❌ Not supported
- **Implementation Details**: How this feature works in Stage 2
- **New Patterns**: What cloud patterns are introduced
- **Trade-offs**: New limitations or improvements
- **Example**: "Threat intelligence stored in DynamoDB, organizations in MySQL"

### Stage 3: AWS ECS + DynamoDB (Cloud Deployment)

- **Status**: ✅ Fully implemented | ⚠️ Partial | ❌ Not supported
- **Implementation Details**: How this feature works in Stage 3
- **Scale Changes**: How scaling differs from Stage 2
- **New Capabilities**: Features enabled by AWS infrastructure
- **Example**: "Auto-scaled ECS tasks, CloudWatch monitoring, multi-AZ DynamoDB"

### Stage 4: Kubernetes + ScyllaDB (Production Scale)

- **Status**: ✅ Fully implemented | ⚠️ Partial | ❌ Not supported
- **Implementation Details**: How this feature works in Stage 4
- **Massive Scale**: Patterns for petabyte-scale threat data
- **Cloud-Agnostic**: Infrastructure portability considerations
- **Example**: "ScyllaDB cluster across regions, Kubernetes pod autoscaling"

**Example Evolution Path for Sightings API**:

### Stage 1: SQLite + FastAPI
- ✅ All endpoints implemented
- Single SQLite database on laptop
- No concurrency concerns
- Used for rapid prototyping and team development

### Stage 2: DynamoDB + LocalStack
- ✅ All endpoints implemented
- DynamoDB for sightings, MySQL for organizations (separate storage)
- Learning AWS access patterns
- Still single-region, locally containerized

### Stage 3: AWS ECS
- ✅ All endpoints implemented
- Production DynamoDB with multi-AZ replication
- RDS PostgreSQL for management API
- ECS Fargate auto-scaling (2-10 containers)
- CloudWatch logging and monitoring

### Stage 4: Kubernetes
- ✅ All endpoints implemented
- ScyllaDB distributed cluster
- Pod autoscaling based on threat data volume
- Multi-region deployment support
- Service mesh (Istio) for traffic management

---

## 8. References

Link to related documentation, ADRs, issues, and external resources:

- **Related ADRs**:
  - [ADR-0002: Repository Pattern & Database Abstraction](../../docs/adr/0002-repository-pattern-database-abstraction.md)
  - [ADR-0003: Tiered Access Control Model](../../docs/adr/0003-tiered-access-control-model.md)
  - [ADR-0005: Cognito Authentication](../../docs/adr/0005-cognito-authentication.md)
  - [ADR-0007: Forgiving Input, Strong Output](../../docs/adr/0007-forgiving-input-strong-output.md)
  - [ADR-0008: Explicit Error Communication](../../docs/adr/0008-explicit-error-communication.md)

- **Related Specifications**:
  - [Core Data Models Spec](core/models.spec.md)
  - [Access Control Spec](core/access_control.spec.md)

- **Related Spikes**:
  - [Spike 005: FastAPI Server Patterns](../../tests/spikes/005_server/README.md)
  - [Spike 007: FastAPI Application Structure](../../tests/spikes/007_fastapi/README.md)
  - [Spike 014: Cognito Integration](../../tests/spikes/014_cognito/README.md)
  - [Spike 015: FastAPI Testing](../../tests/spikes/015_fastapi_testing/README.md)

- **External Resources**:
  - [STIX 2.1 Specification](https://docs.oasis-open.org/cti/stix/v2.1/cs01/stix-v2.1-cs01.html)
  - [REST API Best Practices](https://restfulapi.net/)

- **GitHub Issues**:
  - [Issue #92: Implement Main API (Sightings API) for threat intelligence](https://github.com/example/frank/issues/92)

- **Implementation PRs**:
  - [PR #97: Implement Main API (Sightings API)](https://github.com/example/frank/pull/97)

---

## 9. Open Questions & Decisions Pending

Document any unresolved questions or decisions still needed:

- [ ] **Question A**: [Description]
  - **Options**: [Option 1, Option 2, ...]
  - **Recommendation**: [Which option and why]
  - **Decision**: [Final decision when made]

- [ ] **Question B**: [Description]
  - **Options**: [...]
  - **Recommendation**: [...]
  - **Decision**: [...]

**Example**:

- [ ] **Rate Limiting Strategy**: How should we limit API requests?
  - **Options**:
    - Per-organization limits (simple, fair distribution)
    - Per-user limits (more granular control)
    - Hybrid approach (both limits apply)
  - **Recommendation**: Hybrid approach - per-org quota + per-user burst limit
  - **Decision**: Pending approval from architecture team

---

## 10. Appendix: Examples

Include concrete examples demonstrating the feature:

### Example 1: Creating a Sighting

```bash
# Request
curl -X POST https://api.frank.local/api/v1/sightings \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "observable_id": "observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e",
    "observed_at": "2026-02-06T14:30:00Z",
    "reporter_organization": "ACME Corporation",
    "confidence": 95,
    "details": {
      "source": "Email gateway log",
      "context": "Malicious attachment in phishing email"
    }
  }'

# Response
{
  "id": "sighting--f0d4c9ac-a14262e0-7e6e-59d4-c9ac",
  "observable_id": "observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e",
  "observed_at": "2026-02-06T14:30:00Z",
  "reporter_organization": "ACME Corporation",
  "confidence": 95,
  "details": {
    "source": "Email gateway log",
    "context": "Malicious attachment in phishing email"
  },
  "created_at": "2026-02-06T14:32:15Z",
  "created_by": "user@acme.corp"
}
```

### Example 2: Querying Sightings with Filters

```bash
# Request: Get all sightings of a specific observable, filtered by confidence
curl -X GET "https://api.frank.local/api/v1/sightings?observable_id=observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e&min_confidence=80" \
  -H "Authorization: Bearer $JWT_TOKEN"

# Response
{
  "sightings": [
    {
      "id": "sighting--abc...",
      "observable_id": "observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e",
      "observed_at": "2026-02-06T14:30:00Z",
      ...
    },
    ...
  ],
  "total_count": 42,
  "next_page_token": "eyJvZmZzZXQiOiAyMH0="
}
```

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| YYYY-MM-DD | 1.0 | [Name] | Initial draft |
| YYYY-MM-DD | 1.1 | [Name] | Refined requirements based on review |
| YYYY-MM-DD | 2.0 | [Name] | Major revision after implementation |

---

**Questions or feedback?** Comment on related GitHub issue or PR, or reach out to spec owner.
