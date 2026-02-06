# Specification: [Feature Name]

⭐ **Required sections marked with star**

- **Status:** ⭐ DRAFT | REVIEW | APPROVED | IMPLEMENTED | SUPERSEDED
- **Version:** 1.0
- **Last Updated:** YYYY-MM-DD
- **Owner:** ⭐ [Name or Team]
- **Related Proposal:** [proposal.md](proposal.md)
- **Issue:** ⭐ #XXX

---

## Overview

⭐ **What is this spec?** This document defines the **what** and **how well** for this feature.

The companion documents:
- **[proposal.md](proposal.md)**: Why we need this change
- **[design.md](design.md)**: How we'll implement it
- **[tasks.md](tasks.md)**: Step-by-step implementation
- **[adr.md](adr.md)**: Architectural decisions

This specification answers:
- **What must the system do?** (Functional Requirements)
- **How well must it work?** (Non-Functional Requirements)
- **What are the data contracts?** (Data Models & APIs)
- **How do we verify it works?** (Test Coverage)

---

## 1. Functional Requirements

⭐ **What must the system do?**

### Requirement 1: [Title]

- **Description**: Clear explanation of what this requirement means
- **Acceptance Criteria**:
  - [ ] Specific, testable condition A
  - [ ] Specific, testable condition B
  - [ ] Specific, testable condition C
- **Stage Availability**: Which FRANK stages support this? (Stages 1, 2, 3, 4 or subset)
- **Related Design**: See [design.md](design.md) → Implementation Approach → [Section name]
- **Related ADR(s)**: [ADR-0005](../../../docs/adr/0005-cognito-authentication.md)

### Requirement 2: [Title]

- **Description**: ...
- **Acceptance Criteria**:
  - [ ] ...
- **Stage Availability**: ...
- **Related Design**: ...
- **Related ADR(s)**: ...

### Requirement 3: [Title]

- **Description**: ...
- **Acceptance Criteria**:
  - [ ] ...
- **Stage Availability**: ...
- **Related Design**: ...
- **Related ADR(s)**: ...

---

### Example: Sightings API Requirements

### Requirement 1: Query Sightings by Observable

Users must be able to search for sightings of a specific threat indicator (observable).

- **Description**:
  The system shall provide an endpoint to query sightings filtered by observable ID. Authenticated users with appropriate access tiers can search for observations of specific threat indicators (IPv4/IPv6 addresses, domain names, file hashes, etc.).

- **Acceptance Criteria**:
  - [ ] `GET /api/v1/sightings?observable_id={id}` returns all sightings for that observable
  - [ ] Results respect access control (user only sees sightings from authorized organizations)
  - [ ] Response includes total count and pagination token for large result sets
  - [ ] Queries respond in < 200ms (95th percentile) for < 10,000 results
  - [ ] Invalid observable ID returns 400 Bad Request with descriptive error
  - [ ] Missing authentication returns 401 Unauthorized
  - [ ] Insufficient access tier returns 403 Forbidden

- **Stage Availability**:
  - Stage 1: ✅ Full implementation with SQLite queries
  - Stage 2: ✅ Full implementation with DynamoDB queries
  - Stage 3: ✅ Production deployment on AWS ECS
  - Stage 4: ✅ Kubernetes scaling with ScyllaDB backend

- **Related Design**: [design.md](design.md) → API Design → Query Sightings Endpoint

- **Related ADR(s)**:
  - [ADR-0003: Tiered Access Control](../../../docs/adr/0003-tiered-access-control-model.md)
  - [ADR-0002: Repository Pattern](../../../docs/adr/0002-repository-pattern-database-abstraction.md)

### Requirement 2: Submit New Sighting

Users must be able to report new observations of threat indicators.

- **Description**:
  The system shall accept new sighting submissions from authenticated users. A sighting captures an observation of a threat indicator (observable) at a specific time by a specific organization, including optional context details and confidence assessment.

- **Acceptance Criteria**:
  - [ ] `POST /api/v1/sightings` creates new sighting with valid data
  - [ ] Response includes created sighting object with assigned ID
  - [ ] Response status is 201 Created with Location header
  - [ ] Sighting ID follows STIX 2.1 format: `sighting--{uuid}`
  - [ ] Invalid fields return 400 Bad Request with field-specific errors
  - [ ] Missing required fields return 400 Bad Request
  - [ ] Duplicate submissions (same observable + time) are deduplicated or rejected gracefully
  - [ ] Submissions are persistent (survive database restarts)
  - [ ] Audit log records who submitted what when (for compliance)

- **Stage Availability**:
  - Stage 1: ✅ Full implementation
  - Stage 2: ✅ Full implementation with async queuing (future)
  - Stage 3: ✅ High-throughput submission handling
  - Stage 4: ✅ Distributed submission processing

- **Related Design**: [design.md](design.md) → API Design → Submit Sighting Endpoint

- **Related ADR(s)**:
  - [ADR-0007: Forgiving Input, Strong Output](../../../docs/adr/0007-forgiving-input-strong-output.md)
  - [ADR-0008: Explicit Error Communication](../../../docs/adr/0008-explicit-error-communication.md)

### Requirement 3: Access Control Enforcement

Access to sightings must respect organizational boundaries and access tiers.

- **Description**:
  The system shall enforce access control rules ensuring users only see sightings from organizations they have permission to access, based on their access tier (PUBLIC, OBSERVER, CONTRIBUTOR, PARTNER, CORE_MEMBER per ADR-0003).

- **Acceptance Criteria**:
  - [ ] OBSERVER users see PUBLIC sightings only
  - [ ] CONTRIBUTOR users see PUBLIC + OBSERVER sightings from their organization
  - [ ] PARTNER users see sightings from partner organizations based on partnership tier
  - [ ] CORE_MEMBER users see all sightings (admin access)
  - [ ] Access filtering applied transparently (no API changes for different tiers)
  - [ ] Access decisions logged for audit trail
  - [ ] Bulk operations (exports, analytics) respect access control

- **Stage Availability**: All stages

- **Related Design**: [design.md](design.md) → Access Control Architecture

- **Related ADR(s)**:
  - [ADR-0003: Tiered Access Control](../../../docs/adr/0003-tiered-access-control-model.md)

### Requirement 4: Filter & Search Capabilities

Users need flexible ways to find relevant sightings.

- **Description**:
  The system shall support filtering sightings by multiple criteria including date range, confidence level, reporter organization, threat type, etc.

- **Acceptance Criteria**:
  - [ ] `GET /api/v1/sightings?observable_id={id}&min_date=...&max_date=...` filters by date
  - [ ] `GET /api/v1/sightings?observable_id={id}&min_confidence=80` filters by confidence
  - [ ] `GET /api/v1/sightings?reporter_org=ACME` filters by submitting organization
  - [ ] Multiple filters compose (AND logic): all conditions must be satisfied
  - [ ] Filters are optional (omitting filter returns all matching category)
  - [ ] Invalid filter values return 400 Bad Request with helpful message

- **Stage Availability**: All stages

- **Related Design**: [design.md](design.md) → Query Design

- **Related ADR(s)**: [ADR-0007: Input Validation](../../../docs/adr/0007-forgiving-input-strong-output.md)

---

## 2. Non-Functional Requirements

⭐ **How well must it work?**

### Performance

**Query Latency**:
- 95th percentile response time < 200ms for < 10,000 results
- Median response time < 50ms (optimistic case)
- Fallback: Queries > 100K results return paginated results with continuation token

**Throughput**:
- Stage 1: Support 10+ concurrent users (local development)
- Stage 2: Support 100+ concurrent users (learning/testing)
- Stage 3: Support 1000+ concurrent users (production pilot)
- Stage 4: Support 10,000+ concurrent users (enterprise scale)

**Submission Rate**:
- Stage 1: 100 submissions/second (SQLite)
- Stage 2: 1000 submissions/second (DynamoDB local)
- Stage 3: 10,000 submissions/second (AWS DynamoDB)
- Stage 4: 100,000+ submissions/second (ScyllaDB cluster)

### Scalability

**Data Volume**:
- Stage 1: 1M observables, 10M sightings (laptop SQLite)
- Stage 2: 10M observables, 100M sightings (local DynamoDB)
- Stage 3: 100M+ observables, 1B+ sightings (AWS at scale)
- Stage 4: Petabyte-scale threat data (enterprise clusters)

**Horizontal Scaling**:
- Stage 1: Not applicable (single-user development)
- Stage 2: Not applicable (local environment)
- Stage 3: ECS Fargate auto-scales 2-10 containers based on CPU/memory/request rate
- Stage 4: Kubernetes auto-scales pods based on threat data volume and latency

### Reliability

**Availability**:
- Target: ≥99.5% uptime (max 3.6 hours downtime/month)
- Includes planned maintenance windows
- Excludes external dependency failures (AWS API Gateway down)

**Data Durability**:
- 100% of submitted sightings must persist
- Replicated across availability zones (Stage 3+)
- Regular backups tested for recovery

**Error Recovery**:
- Transient errors (network timeout): Automatic retry with exponential backoff
- Database connection pool: Automatic reconnection after failures
- Graceful degradation: Return cached results if database temporarily unavailable

### Security

**Authentication**:
- All API requests require valid AWS Cognito JWT token
- Token validation per [ADR-0005](../../../docs/adr/0005-cognito-authentication.md)
- Invalid/expired tokens return 401 Unauthorized

**Authorization**:
- Access control enforced per [ADR-0003](../../../docs/adr/0003-tiered-access-control-model.md)
- Users cannot access sightings outside their authorization scope
- Bulk operations respect authorization boundaries

**Data Protection**:
- HTTPS/TLS for all API traffic (encryption in transit)
- Sensitive fields (PII, credentials) not logged or cached
- Database encryption at rest (AWS native encryption)

**Audit Logging**:
- All API requests logged with timestamp, user, action, result
- Sensitive actions require approval (deletion, access tier changes)
- Audit logs retained for ≥90 days for compliance

### Usability

**API Clarity**:
- RESTful design following industry standards
- Clear, descriptive error messages with actionable remediation
- Consistent naming conventions across endpoints
- Comprehensive OpenAPI/Swagger documentation

**Developer Experience**:
- Code examples for Python, JavaScript, curl
- Integration guides for common tools (Postman, Insomnia)
- Troubleshooting guide for common errors
- Sample data for testing

**Backwards Compatibility**:
- API version in URL path: `/api/v1/sightings` (supports future `/api/v2/`)
- Deprecation period: 6 months notice before removing endpoints
- Changelog documents all breaking changes

### Supportability

**Observability**:
- Structured logging with request IDs for tracing
- CloudWatch metrics for latency, throughput, errors
- Dashboards for operations team monitoring
- Alerting for error rates, latency spikes

**Troubleshooting**:
- Health check endpoint `/api/v1/health` for readiness
- Deep health check `/api/v1/health/deep` testing database connectivity
- Error responses include correlation IDs for log lookup

**Operations**:
- Graceful shutdown (finish in-flight requests before shutdown)
- Connection pooling prevents resource exhaustion
- Rate limiting prevents abuse (future enhancement)

---

## 3. Data Model & API Contract

⭐ **What are the data structures and contracts?**

### Data Models

#### Sighting Model

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

class Sighting(BaseModel):
    """Observation of a threat indicator in the wild."""

    id: str = Field(
        default_factory=lambda: f"sighting--{uuid.uuid4()}",
        description="STIX 2.1 format sighting identifier",
        examples=["sighting--f0d4c9ac-a1a2-4fe9-ae3d-7e6e5d4c9ac"]
    )

    observable_id: str = Field(
        description="Reference to Observable (e.g., observable--d8f0eae0-...)",
        examples=["observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e"]
    )

    observed_at: datetime = Field(
        description="When the threat indicator was observed (ISO 8601 format)",
        examples=["2026-02-06T14:30:00Z"]
    )

    reporter_organization: str = Field(
        description="Organization that reported this sighting",
        examples=["ACME Corporation"]
    )

    confidence: int = Field(
        ge=0, le=100,
        description="Confidence level 0-100 (0=lowest, 100=highest)",
        examples=[95]
    )

    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form context about the sighting",
        examples=[{
            "source": "Email gateway log",
            "context": "Malicious attachment in phishing email",
            "count": 5,
            "targeted_users": ["user@acme.corp"]
        }]
    )

    created_at: datetime = Field(
        description="When this sighting was created in FRANK"
    )

    created_by: str = Field(
        description="User who created this sighting",
        examples=["analyst@acme.corp"]
    )

    access_tier: str = Field(
        default="CONTRIBUTOR",
        description="Access tier for this sighting (PUBLIC, OBSERVER, CONTRIBUTOR, PARTNER, CORE_MEMBER)",
        examples=["CONTRIBUTOR"]
    )

    class Config:
        extra = "ignore"  # Per ADR-0007: Be forgiving on input
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SightingResponse(Sighting):
    """Sighting response includes metadata."""
    pass


class SightingCreateRequest(BaseModel):
    """Input model for creating sightings (minimal required fields)."""

    observable_id: str = Field(
        description="Reference to Observable"
    )

    observed_at: datetime = Field(
        description="When the threat indicator was observed"
    )

    confidence: int = Field(
        ge=0, le=100,
        description="Confidence level 0-100"
    )

    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional context details"
    )

    class Config:
        extra = "ignore"  # Forgiving on input
```

#### Query Response Model

```python
from typing import List, Optional

class SightingsQueryResponse(BaseModel):
    """Response from sightings query endpoint."""

    sightings: List[SightingResponse] = Field(
        description="Array of sightings matching query"
    )

    total_count: int = Field(
        description="Total number of sightings matching query"
    )

    next_page_token: Optional[str] = Field(
        default=None,
        description="Pagination token for next page (if more results exist)"
    )

    returned_count: int = Field(
        description="Number of sightings in this response"
    )

    query_time_ms: int = Field(
        description="Time taken to execute query (milliseconds)"
    )
```

### API Endpoints

#### 1. Query Sightings

```
GET /api/v1/sightings
```

**Purpose**: Search for sightings with optional filters

**Authentication**: Required (Bearer token)

**Query Parameters**:
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `observable_id` | string | No | Filter by observable ID | `observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e` |
| `min_date` | ISO 8601 | No | Filter: observed_at >= min_date | `2026-01-01T00:00:00Z` |
| `max_date` | ISO 8601 | No | Filter: observed_at <= max_date | `2026-02-06T23:59:59Z` |
| `min_confidence` | integer | No | Filter: confidence >= min_confidence | `80` |
| `reporter_org` | string | No | Filter by reporting organization | `ACME Corporation` |
| `limit` | integer | No | Page size (default: 100, max: 1000) | `50` |
| `page_token` | string | No | Pagination token from previous response | `eyJvZmZzZXQiOiAyMH0=` |

**Request Example**:
```bash
GET /api/v1/sightings?observable_id=observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e&min_confidence=80&limit=50
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Success Response (200 OK)**:
```json
{
  "sightings": [
    {
      "id": "sighting--f0d4c9ac-a1a2-4fe9-ae3d-7e6e5d4c9ac",
      "observable_id": "observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e",
      "observed_at": "2026-02-06T14:30:00Z",
      "reporter_organization": "ACME Corporation",
      "confidence": 95,
      "details": {
        "source": "Email gateway log",
        "context": "Malicious attachment in phishing email"
      },
      "created_at": "2026-02-06T14:32:15Z",
      "created_by": "analyst@acme.corp",
      "access_tier": "CONTRIBUTOR"
    },
    ...
  ],
  "total_count": 42,
  "returned_count": 50,
  "next_page_token": "eyJvZmZzZXQiOiA1MH0=",
  "query_time_ms": 125
}
```

**Error Responses**:

| Status | Error Type | Message | Example |
|--------|-----------|---------|---------|
| 400 | `validation_error` | Invalid query parameter | `"min_date must be valid ISO 8601 datetime"` |
| 401 | `unauthorized` | Missing/invalid authentication token | `"Missing Authorization header"` |
| 403 | `forbidden` | User cannot access requested data | `"Insufficient access tier to view CORE_MEMBER sightings"` |
| 500 | `internal_error` | Server error (with correlation ID) | `"Database query failed. Correlation ID: abc123"` |

#### 2. Get Single Sighting

```
GET /api/v1/sightings/{id}
```

**Purpose**: Retrieve a specific sighting by ID

**Authentication**: Required (Bearer token)

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Sighting ID (e.g., `sighting--f0d4c9ac-...`) |

**Request Example**:
```bash
GET /api/v1/sightings/sighting--f0d4c9ac-a1a2-4fe9-ae3d-7e6e5d4c9ac
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Success Response (200 OK)**:
```json
{
  "id": "sighting--f0d4c9ac-a1a2-4fe9-ae3d-7e6e5d4c9ac",
  "observable_id": "observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e",
  "observed_at": "2026-02-06T14:30:00Z",
  "reporter_organization": "ACME Corporation",
  "confidence": 95,
  "details": {...},
  "created_at": "2026-02-06T14:32:15Z",
  "created_by": "analyst@acme.corp",
  "access_tier": "CONTRIBUTOR"
}
```

**Error Responses**:
| Status | Error Type | Message |
|--------|-----------|---------|
| 401 | `unauthorized` | Missing/invalid token |
| 403 | `forbidden` | User cannot access this sighting |
| 404 | `not_found` | Sighting does not exist |

#### 3. Create Sighting

```
POST /api/v1/sightings
```

**Purpose**: Submit a new sighting

**Authentication**: Required (Bearer token)

**Content-Type**: `application/json`

**Request Body**:
```json
{
  "observable_id": "observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e",
  "observed_at": "2026-02-06T14:30:00Z",
  "confidence": 95,
  "details": {
    "source": "Email gateway log",
    "context": "Malicious attachment in phishing email"
  }
}
```

**Success Response (201 Created)**:
```json
{
  "id": "sighting--f0d4c9ac-a1a2-4fe9-ae3d-7e6e5d4c9ac",
  "observable_id": "observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e",
  "observed_at": "2026-02-06T14:30:00Z",
  "reporter_organization": "ACME Corporation",
  "confidence": 95,
  "details": {
    "source": "Email gateway log",
    "context": "Malicious attachment in phishing email"
  },
  "created_at": "2026-02-06T14:32:15Z",
  "created_by": "analyst@acme.corp",
  "access_tier": "CONTRIBUTOR"
}
```

**Headers**:
```
Location: /api/v1/sightings/sighting--f0d4c9ac-a1a2-4fe9-ae3d-7e6e5d4c9ac
```

**Error Responses**:
| Status | Error Type | Message Example |
|--------|-----------|---------|
| 400 | `validation_error` | `"observable_id: Field required"` or `"confidence: Must be between 0 and 100"` |
| 401 | `unauthorized` | Missing/invalid token |
| 403 | `forbidden` | User cannot submit sightings for this organization |
| 409 | `conflict` | Observable not found or archived |

#### 4. Update Sighting

```
PUT /api/v1/sightings/{id}
```

**Purpose**: Update an existing sighting (admin/author only)

**Authentication**: Required (Bearer token)

**Authorization**: User must be PARTNER+ tier and be the original submitter or admin

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Sighting ID |

**Request Body** (same as Create, all fields optional):
```json
{
  "confidence": 98,
  "details": {
    "source": "Email gateway log",
    "context": "Updated context with more info",
    "count": 10
  }
}
```

**Success Response (200 OK)**: Updated Sighting object

**Error Responses**:
| Status | Error Type | Message |
|--------|-----------|---------|
| 401 | `unauthorized` | Missing/invalid token |
| 403 | `forbidden` | Cannot update sightings by other users |
| 404 | `not_found` | Sighting does not exist |

#### 5. Delete Sighting

```
DELETE /api/v1/sightings/{id}
```

**Purpose**: Delete a sighting (admin/author only)

**Authentication**: Required (Bearer token)

**Authorization**: User must be PARTNER+ tier and be the original submitter or admin

**Success Response (204 No Content)**: No body

**Error Responses**:
| Status | Error Type | Message |
|--------|-----------|---------|
| 401 | `unauthorized` | Missing/invalid token |
| 403 | `forbidden` | Cannot delete sightings by other users |
| 404 | `not_found` | Sighting does not exist |

---

## 4. Test Coverage Requirements

⭐ **How do we verify this works?**

### Unit Tests (Location: `tests/unit/apis/test_sightings_api.py`)

#### Test: Create Sighting Happy Path

```python
def test_create_sighting_with_valid_data():
    """Sightings API creates sighting with valid input."""
    # Arrange
    client = TestClient(create_app())
    valid_sighting = {
        "observable_id": "observable--d8f0eae0-1e1f-59d4-c9ac-a14262e07e6e",
        "observed_at": "2026-02-06T14:30:00Z",
        "confidence": 95,
        "details": {"source": "email"}
    }

    # Act
    response = client.post("/api/v1/sightings", json=valid_sighting)

    # Assert
    assert response.status_code == 201
    assert response.json()["id"].startswith("sighting--")
    assert response.json()["confidence"] == 95
    assert "Location" in response.headers
```

#### Test: Validation Errors

```python
def test_create_sighting_with_invalid_confidence():
    """Sightings API rejects confidence outside 0-100."""
    client = TestClient(create_app())
    invalid_sighting = {
        "observable_id": "observable--...",
        "observed_at": "2026-02-06T14:30:00Z",
        "confidence": 150  # Invalid: > 100
    }

    response = client.post("/api/v1/sightings", json=invalid_sighting)

    assert response.status_code == 400
    assert "confidence" in response.json()["error"]["details"]
```

#### Test: Authentication

```python
def test_create_sighting_without_token():
    """Sightings API requires authentication."""
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/sightings",
        json={...},
        headers={}  # No Authorization header
    )

    assert response.status_code == 401
```

#### Test: Authorization

```python
def test_create_sighting_with_insufficient_tier():
    """Sightings API enforces access tier restrictions."""
    client = TestClient(create_app())

    # OBSERVER tier user (read-only)
    response = client.post(
        "/api/v1/sightings",
        json={...},
        headers={"Authorization": f"Bearer {observer_token}"}
    )

    assert response.status_code == 403
```

#### Test: Query with Filters

```python
def test_query_sightings_with_date_filter():
    """Sightings API filters by date range."""
    # Arrange: Create multiple sightings with different dates
    create_sighting(observed_at="2026-01-01T00:00:00Z")
    create_sighting(observed_at="2026-02-01T00:00:00Z")
    create_sighting(observed_at="2026-03-01T00:00:00Z")

    # Act
    response = client.get(
        "/api/v1/sightings?min_date=2026-02-01&max_date=2026-02-28"
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["returned_count"] == 1
```

#### Test: Pagination

```python
def test_query_sightings_pagination():
    """Sightings API handles large result sets."""
    # Arrange: Create 150 sightings
    for i in range(150):
        create_sighting(observable_id=f"observable--{i}")

    # Act: Request page 1
    response1 = client.get("/api/v1/sightings?limit=100")

    # Assert: First page has 100 results
    assert response1.json()["returned_count"] == 100
    assert response1.json()["total_count"] == 150
    assert "next_page_token" in response1.json()

    # Act: Request page 2
    response2 = client.get(
        f"/api/v1/sightings?limit=100&page_token={response1.json()['next_page_token']}"
    )

    # Assert: Second page has remaining 50 results
    assert response2.json()["returned_count"] == 50
```

### Unit Test Coverage Target

- **Code Coverage**: ≥85% of API code (per ADR-0012)
- **Branch Coverage**: All conditional paths tested
- **Error Cases**: All error codes tested (400, 401, 403, 404, 409, 500)

### Integration Tests (Location: `tests/integration/sightings_api.feature`)

```gherkin
Feature: Sightings API

  Scenario: Analyst submits observation of malicious IP
    Given an authenticated analyst with CONTRIBUTOR access
    And a known malicious IPv4 observable exists
    When the analyst submits a sighting with high confidence
    Then the sighting is created successfully
    And the sighting appears in query results
    And the submission is logged in audit trail

  Scenario: Observer user cannot create sightings
    Given an authenticated observer with OBSERVER access
    When the observer attempts to submit a sighting
    Then the request is denied with 403 Forbidden
    And the sighting is not created

  Scenario: Users only see sightings within access tier
    Given three organizations: A (CONTRIBUTOR), B (PARTNER), C (CORE_MEMBER)
    And sightings with different access tiers exist
    When user from organization A queries sightings
    Then user sees only PUBLIC sightings
    When user from organization B queries sightings
    Then user sees PUBLIC and PARTNER sightings
    When user from organization C queries sightings
    Then user sees all sightings
```

### Spike Tests (Location: `tests/spikes/XXX_sightings_api_test.py`)

- **Performance Validation**: Query latency under load
- **Concurrency Testing**: Race conditions, thread safety
- **Database Integration**: End-to-end with SQLite, DynamoDB

---

## 5. References

- **Proposal**: [proposal.md](proposal.md)
- **Design**: [design.md](design.md)
- **Implementation Tasks**: [tasks.md](tasks.md)
- **Architectural Decisions**: [adr.md](adr.md)

- **Related ADRs**:
  - [ADR-0002: Repository Pattern & Database Abstraction](../../../docs/adr/0002-repository-pattern-database-abstraction.md)
  - [ADR-0003: Tiered Access Control Model](../../../docs/adr/0003-tiered-access-control-model.md)
  - [ADR-0005: Cognito Authentication](../../../docs/adr/0005-cognito-authentication.md)
  - [ADR-0007: Forgiving Input, Strong Output](../../../docs/adr/0007-forgiving-input-strong-output.md)
  - [ADR-0008: Explicit Error Communication](../../../docs/adr/0008-explicit-error-communication.md)

- **Related Spikes**:
  - [Spike 007: FastAPI Application Structure](../../../tests/spikes/007_fastapi/README.md)
  - [Spike 012: DynamoDB Table Design](../../../tests/spikes/012_aws_dynamodb/README.md)
  - [Spike 014: Cognito Integration](../../../tests/spikes/014_cognito/README.md)
  - [Spike 015: FastAPI Testing](../../../tests/spikes/015_fastapi_testing/README.md)

---

**Next**: Read [`design.md`](design.md) for implementation architecture and approach.
