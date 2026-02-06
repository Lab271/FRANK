# Specification: Sightings API (Main API)

## Metadata

| Attribute | Value |
|-----------|-------|
| **Spec ID** | SPEC-API-001 |
| **Status** | IMPLEMENTED |
| **Version** | 0.2.0 |
| **Component** | src/frank/main/api.py |
| **Database** | DynamoDB (Stages 2-3), SQLite (Stage 1) |
| **Related ADRs** | ADR-0005 (Cognito Auth), ADR-0003 (Access Tiers) |
| **Related Specs** | [Authentication](authentication.spec.md), [Submission](../core/submission.spec.md) |
| **Test Files** | tests/integration/test_main_api.py |

---

## Purpose

The Sightings API (Main API) provides high-volume threat intelligence submission and query capabilities for the FRANK platform. It serves as the primary interface for service accounts and automated threat feed ingestion.

**Key Responsibilities**:
- Accept threat intelligence submissions from authenticated sources
- Provide filtered access to submissions based on access tier
- Query observables with access control
- Deliver platform statistics
- Authenticate service accounts via Cognito

---

## Functional Requirements

### FR1: Threat Intelligence Submission
**Requirement**: Accept and store threat intelligence submissions from authenticated users with CONTRIBUTOR or higher access.

**Acceptance Criteria**:
- POST /submit endpoint accepts SubmissionRequest with observables
- Validates JWT token and extracts access tier
- Categorizes observables by type (network/file/process)
- Generates STIX-compliant submission ID
- Stores in database via BaseFRANKDatabase.store_submission()
- Returns 201 Created with submission_id
- Returns 401 Unauthorized if not authenticated
- Returns 403 Forbidden if insufficient permissions

### FR2: Submission Retrieval with Access Filtering
**Requirement**: Retrieve submissions by ID with field-level access filtering based on user's access tier.

**Acceptance Criteria**:
- GET /submissions/{submission_id} returns filtered submission
- Access filtering applied automatically via BaseFRANKDatabase
- OBSERVER: Masked observables (first 10 chars + "...")
- CONTRIBUTOR: Full observables, anonymized targets
- PARTNER: Full submission data
- CORE_MEMBER: Complete access including audit logs
- Returns 404 Not Found if submission doesn't exist
- Returns 403 Forbidden if insufficient access

### FR3: Observable Query with Pagination
**Requirement**: Query threat observables with type filtering, pagination, and access control.

**Acceptance Criteria**:
- GET /observables endpoint with optional type filter
- Supports limit (default: 100) and offset (default: 0) parameters
- Filters results by user's access tier automatically
- Returns JSON with observables array, total count, pagination metadata
- Requires authentication (any tier)

### FR4: Platform Statistics
**Requirement**: Provide aggregated platform statistics with detail level based on access tier.

**Acceptance Criteria**:
- GET /statistics endpoint with optional days parameter (default: 30)
- Returns submission counts, observable types, severity distribution
- Detail level varies by access tier
- PUBLIC: Basic counts only
- OBSERVER+: Detailed breakdowns and trends
- Requires authentication

### FR5: Service Account Authentication
**Requirement**: Authenticate service accounts using Cognito and issue JWT tokens.

**Acceptance Criteria**:
- POST /auth/login accepts username/password
- Proxies authentication to Cognito (AWS or Stub)
- Returns access_token, refresh_token, expires_in
- Returns 401 Unauthorized for invalid credentials
- Logs authentication attempts
- Service accounts follow naming convention: service-{org}-{purpose}

### FR6: Health Monitoring
**Requirement**: Provide basic and deep health check endpoints for monitoring.

**Acceptance Criteria**:
- GET /health returns status, version, timestamp (no auth required)
- GET /health/deep checks database connectivity and auth service
- Returns "healthy", "degraded", or "unhealthy" status
- Deep health includes component-level status

---

## Non-Functional Requirements

### NFR1: Performance
- Submission endpoint: < 500ms response time (p95)
- Query endpoints: < 200ms response time (p95)
- Health check: < 100ms response time
- Supports concurrent requests with auto-scaling (ECS Fargate)

### NFR2: Scalability
- Handles 2,000+ submissions per minute (ECS auto-scaling)
- Query pagination prevents memory exhaustion
- DynamoDB provides unlimited horizontal scaling

### NFR3: Security
- All endpoints except /health require JWT authentication
- HTTPS/TLS 1.3 in production (AWS ALB termination)
- CORS middleware configured for production origins
- SQL injection prevention via Pydantic validation
- Access tier enforcement at repository layer

### NFR4: Reliability
- Graceful degradation if database unavailable (503 Service Unavailable)
- Proper error handling with structured error responses
- Audit logging for all submissions and queries
- Database health checks every 30 seconds

### NFR5: Observability
- Structured logging with username, access_tier, operation
- CloudWatch Logs integration (AWS deployment)
- Request/response timing metrics
- Error rate monitoring

---

## API Endpoints

### Health Endpoints

#### GET /health
**Summary**: Basic health check

**Authentication**: None required

**Response** (200 OK):
```json
{
  "status": "healthy",
  "timestamp": "2026-02-06T14:30:00Z",
  "version": "0.2.0"
}
```

**Implementation**: `src/frank/main/api.py:113`

---

#### GET /health/deep
**Summary**: Deep health check with component validation

**Authentication**: None required

**Response** (200 OK):
```json
{
  "status": "healthy",
  "timestamp": "2026-02-06T14:30:00Z",
  "version": "0.2.0",
  "components": {
    "database": {
      "status": "healthy",
      "type": "dynamodb"
    },
    "authentication": {
      "status": "healthy",
      "type": "cognito",
      "environment": "aws"
    }
  }
}
```

**Status Values**:
- `healthy`: All components operational
- `degraded`: Some components impaired but service functional
- `unhealthy`: Critical components failed

**Implementation**: `src/frank/main/api.py:131`

---

### Authentication Endpoints

#### POST /auth/login
**Summary**: Service account authentication

**Authentication**: None required (this IS the authentication endpoint)

**Request Body**:
```json
{
  "username": "service-rabobank-ingestion",
  "password": "secure-password-here"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600
}
```

**Error Responses**:
- 401 Unauthorized: Invalid credentials
- 500 Internal Server Error: Cognito service failure

**Implementation**: `src/frank/main/api.py:186`

**Related Spec**: [Authentication Patterns](authentication.spec.md)

---

#### POST /auth/refresh
**Summary**: Refresh access token using refresh token

**Authentication**: None required

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600
}
```

**Error Responses**:
- 401 Unauthorized: Invalid or expired refresh token
- 501 Not Implemented: Currently not implemented

**Implementation**: `src/frank/main/api.py:251` (TODO)

---

### Submission Endpoints

#### POST /submit
**Summary**: Submit threat intelligence sighting

**Authentication**: Required (Bearer token)

**Access Level**: CONTRIBUTOR, PARTNER, or CORE_MEMBER

**Request Body**:
```json
{
  "observables": [
    {
      "observable_type": "ipv4",
      "value": "192.0.2.1",
      "role": "c2_server",
      "port": 443
    },
    {
      "observable_type": "domain",
      "value": "malicious.example.com",
      "role": "phishing"
    }
  ],
  "confidence_score": 0.85,
  "severity": "HIGH",
  "description": "Observed C2 communication",
  "timestamp": "2026-02-06T14:30:00Z"
}
```

**Request Model**: SubmissionRequest (src/frank/main/models.py)

**Response** (201 Created):
```json
{
  "submission_id": "submission--a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "timestamp": "2026-02-06T14:30:00Z",
  "status": "accepted",
  "message": "Submission accepted with 2 observables"
}
```

**Processing Flow**:
1. Extract user's access tier and organisation ID from JWT
2. Categorize observables by type (network/file/process)
3. Create Observables container (Pydantic model)
4. Create Sighting with confidence_score and severity
5. Create Submitter with organisation_id and access_level
6. Create Submission with STIX ID
7. Store via db.store_submission(submission)
8. Log submission with user context
9. Return SubmissionResponse

**Error Responses**:
- 401 Unauthorized: Missing or invalid JWT
- 403 Forbidden: Insufficient access tier (OBSERVER/PUBLIC)
- 422 Unprocessable Entity: Invalid observable types or confidence score
- 500 Internal Server Error: Database failure

**Implementation**: `src/frank/main/api.py:281`

---

#### GET /submissions/{submission_id}
**Summary**: Get submission by ID with access filtering

**Authentication**: Required (Bearer token)

**Access Level**: Any authenticated user

**Path Parameters**:
- `submission_id` (string, required): STIX submission ID (e.g., "submission--uuid")

**Response** (200 OK):
```json
{
  "submission_id": "submission--a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "timestamp": "2026-02-06T14:30:00Z",
  "submitter": {
    "organisation_id": "identity--rabobank",
    "access_level": "PARTNER",
    "organisation_type": "cyber_partner"
  },
  "sighting": {
    "sighting_id": "sighting--...",
    "observables": {
      "network": [
        {
          "observable_type": "ipv4",
          "value": "192.0.2.1",
          "role": "c2_server",
          "port": 443
        }
      ]
    },
    "confidence_score": 0.85,
    "severity_level": "HIGH"
  }
}
```

**Access Filtering**:
- **OBSERVER**: Observable values masked (e.g., "192.0.2.***")
- **CONTRIBUTOR**: Full observables, hit_targets anonymized
- **PARTNER**: Full submission data
- **CORE_MEMBER**: Complete access

**Error Responses**:
- 401 Unauthorized: Missing or invalid JWT
- 404 Not Found: Submission doesn't exist
- 403 Forbidden: Access tier insufficient for this submission
- 500 Internal Server Error: Database failure

**Implementation**: `src/frank/main/api.py:381`

**Related Spec**: [Submission Model](../core/submission.spec.md)

---

### Query Endpoints

#### GET /observables
**Summary**: Query threat observables with access filtering

**Authentication**: Required (Bearer token)

**Access Level**: Any authenticated user

**Query Parameters**:
- `observable_type` (string, optional): Filter by type (ipv4, domain, hash, etc.)
- `limit` (integer, optional): Max results (default: 100, max: 1000)
- `offset` (integer, optional): Pagination offset (default: 0)

**Response** (200 OK):
```json
{
  "observables": [
    {
      "observable_type": "ipv4",
      "value": "192.0.2.1",
      "role": "c2_server",
      "first_seen": "2026-02-06T10:00:00Z",
      "connection_count": 15
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0,
  "access_tier": "PARTNER"
}
```

**Access Filtering**: Applied automatically via db.query_observables()

**Error Responses**:
- 401 Unauthorized: Missing or invalid JWT
- 500 Internal Server Error: Database failure

**Implementation**: `src/frank/main/api.py:440`

---

#### GET /statistics
**Summary**: Platform statistics with detail level by access tier

**Authentication**: Required (Bearer token)

**Access Level**: Any authenticated user

**Query Parameters**:
- `days` (integer, optional): Number of days to include (default: 30)

**Response** (200 OK):
```json
{
  "total_submissions": 12543,
  "total_observables": 45621,
  "submission_rate_per_day": 418,
  "top_observable_types": {
    "ipv4": 15234,
    "domain": 12456,
    "hash": 8923
  },
  "severity_distribution": {
    "CRITICAL": 234,
    "HIGH": 1234,
    "MEDIUM": 5678,
    "LOW": 5397
  },
  "access_tier": "PARTNER",
  "requested_by": "service-rabobank-ingestion",
  "period_days": 30
}
```

**Detail Level by Access Tier**:
- **PUBLIC**: Total counts only
- **OBSERVER**: Aggregated statistics
- **CONTRIBUTOR+**: Detailed breakdowns and trends
- **CORE_MEMBER**: Platform-wide metrics

**Error Responses**:
- 401 Unauthorized: Missing or invalid JWT
- 500 Internal Server Error: Database failure

**Implementation**: `src/frank/main/api.py:500`

---

## Authentication & Authorization

### JWT Token Validation

All authenticated endpoints use the `get_current_user` dependency:

```python
from frank.auth import get_current_user

@app.post("/submit")
async def submit_sighting(
    user: TokenPayload = Depends(get_current_user),
    ...
):
    # user.username: Cognito username
    # user.access_tier: AccessTier enum
    # user.organisation_id: Organisation STIX ID
    # user.groups: List of Cognito groups
    pass
```

**Token Validation Process**:
1. Extract token from `Authorization: Bearer <token>` header
2. Validate JWT signature using Cognito JWKS endpoint
3. Verify expiration (`exp` claim)
4. Extract claims: username, groups, organisation_id
5. Map groups to AccessTier enum
6. Return TokenPayload

**JWKS Caching**: Public keys cached for 24 hours

**Related Spec**: [Authentication Patterns](authentication.spec.md)

---

### Access Tier Enforcement

Access tiers are enforced at two levels:

1. **Endpoint Level** (explicit check):
```python
@app.post("/submit")
async def submit_sighting(
    user: TokenPayload = Depends(get_current_user),
    ...
):
    # Any authenticated user can submit
    # Access tier used for attribution, not permission
    pass
```

2. **Repository Level** (automatic filtering):
```python
# BaseFRANKDatabase.get_submission_by_id()
submission = db.get_submission_by_id(
    submission_id=submission_id,
    access_level=user.access_tier  # Automatic filtering
)
```

**Related ADR**: ADR-0003 (Tiered Access Control Model)

---

## Data Models

### SubmissionRequest
**File**: src/frank/main/models.py

```python
class SubmissionRequest(BaseModel):
    observables: List[Observable]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    severity: Optional[str] = "MEDIUM"
    description: Optional[str] = None
    timestamp: Optional[datetime] = None
```

### SubmissionResponse
**File**: src/frank/main/models.py

```python
class SubmissionResponse(BaseModel):
    submission_id: str
    timestamp: datetime
    status: str
    message: str
```

### HealthResponse
**File**: src/frank/main/models.py

```python
class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
```

### DeepHealthResponse
**File**: src/frank/main/models.py

```python
class DeepHealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    components: Dict[str, Any]
```

---

## Error Handling

All endpoints follow ADR-0008 (Explicit Error Communication) format:

**Error Response Structure**:
```json
{
  "detail": "Human-readable error message",
  "status_code": 401
}
```

**Common HTTP Status Codes**:
- 200 OK: Successful GET request
- 201 Created: Successful POST /submit
- 401 Unauthorized: Missing/invalid JWT or credentials
- 403 Forbidden: Insufficient access tier
- 404 Not Found: Resource doesn't exist
- 422 Unprocessable Entity: Invalid request body
- 500 Internal Server Error: Database or service failure
- 503 Service Unavailable: Database not configured

**Related ADR**: ADR-0008 (Explicit Error Communication)

---

## Test Coverage

### Integration Tests
**File**: tests/integration/test_main_api.py

**Scenarios Covered**:
- [ ] Health endpoints (basic and deep)
- [ ] Service account authentication flow
- [ ] Submission creation with various observable types
- [ ] Submission retrieval with access filtering (all tiers)
- [ ] Observable queries with pagination
- [ ] Platform statistics by access tier
- [ ] Error cases (401, 403, 404, 422, 500)

### Unit Tests
**Files**: tests/unit/main/*.py

**Components Tested**:
- [ ] SubmissionRequest validation
- [ ] Observable categorization logic
- [ ] Submission ID generation
- [ ] Access tier extraction from JWT
- [ ] Error response formatting

**Coverage Target**: ≥85% (CI/CD enforced)

---

## Implementation Status

- [x] Health endpoints implemented
- [x] Service account authentication (Cognito proxy)
- [x] Submission endpoint (POST /submit)
- [x] Submission retrieval (GET /submissions/{id})
- [x] Observable query (GET /observables)
- [x] Platform statistics (GET /statistics)
- [ ] Token refresh endpoint (501 Not Implemented)
- [x] Access tier filtering (repository layer)
- [x] CORS middleware configured
- [x] Structured logging implemented
- [x] Error handling per ADR-0008

---

## Evolution Path

### Stage 1 (SQLite)
- SQLite database for all data
- Local Stub Cognito for authentication
- Single-instance FastAPI server
- Development and testing baseline

### Stage 2 (DynamoDB + LocalStack)
- DynamoDB for threat intelligence data
- LocalStack for AWS service emulation
- Docker Compose deployment
- Learning AWS patterns

### Stage 3 (AWS ECS + DynamoDB)
- AWS Cognito for authentication
- DynamoDB for submissions/observables
- ECS Fargate with auto-scaling (2-10 tasks)
- Application Load Balancer
- CloudWatch logging and monitoring
- **Currently implemented**

### Stage 4 (Kubernetes + ScyllaDB)
- ScyllaDB for threat intelligence (high performance)
- Kubernetes for container orchestration
- Multi-region deployment
- Advanced caching and CDN

---

## Related Documentation

- **ADR-0005**: Cognito Authentication Strategy
- **ADR-0003**: Tiered Access Control Model
- **ADR-0008**: Explicit Error Communication
- **Spec**: [Authentication Patterns](authentication.spec.md)
- **Spec**: [Submission Model](../core/submission.spec.md)
- **Spec**: [Observable Model](../core/observable.spec.md)
- **Spec**: [DynamoDB Storage](../storage/dynamodb.spec.md)
- **Implementation**: src/frank/main/api.py
- **Tests**: tests/integration/test_main_api.py

---

## Open Questions

1. **Token Refresh**: When will POST /auth/refresh be implemented? (Currently 501)
2. **Rate Limiting**: Should rate limits be implemented in API or at ALB level?
3. **Caching**: Should frequent queries be cached? (e.g., Redis)
4. **Pagination**: Should cursor-based pagination replace offset-based for large result sets?
5. **GraphQL**: Should a GraphQL endpoint be added for complex queries?

---

**Document Version**: 1.0
**Last Updated**: 2026-02-06
**Status**: Approved for implementation
