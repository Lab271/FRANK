# Sightings API Specification

**Domain:** API / Threat Intelligence Submission & Query
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06

**FRANK-Specific Metadata**:
- **Owner:** API Team
- **Related ADR:** [ADR-0005](docs/adr/0005-cognito-authentication-strategy.md), [ADR-0003](docs/adr/0003-tiered-access-control-model.md)
- **Implementation:** src/frank/main/api.py
- **Database:** DynamoDB (Stages 2-3), SQLite (Stage 1)
- **Tests:** tests/integration/test_main_api.py

## Overview

The Sightings API (Main API) provides high-volume threat intelligence submission and query capabilities for the FRANK platform. It serves as the primary interface for service accounts and automated threat feed ingestion.

### Philosophy

- **High-Volume Ingestion**: Designed for automated threat feed submission at scale (2,000+ submissions/min)
- **Access-Filtered Queries**: Repository-layer filtering ensures users only see data their tier permits
- **Service Account First**: Optimized for programmatic access over human interaction
- **Stateless Authentication**: JWT validation without database lookups enables horizontal scaling

### Key Capabilities

- **Threat Intelligence Submission**: Accept SubmissionRequest with categorized observables (network/file/process)
- **Access-Filtered Retrieval**: Get submissions with automatic field masking by access tier
- **Observable Queries**: Query threat observables with type filtering and pagination
- **Platform Statistics**: Aggregated statistics with detail level by access tier
- **Service Account Auth**: Cognito-based authentication identical to human users
- **Health Monitoring**: Basic and deep health checks for load balancer probes

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Usage in this specification**:
- **MUST/SHALL**: Authentication enforcement, access tier filtering
- **SHOULD**: Pagination for large result sets, structured logging
- **MAY**: Additional query parameters, caching strategies

---

## ADDED Requirements

*This specification primarily documents API endpoints and contracts. Functional requirements are defined in related specifications: [Submission](../core/submission.spec.md), [Observable](../core/observable.spec.md), [Authentication](authentication.spec.md).*

*See Section 4 (API Endpoints) for detailed endpoint contracts.*

---

## 3. Non-Functional Requirements

### Performance

- **Submission Endpoint**: < 500ms response time (p95) including database write
- **Query Endpoints**: < 200ms response time (p95) with DynamoDB GSI
- **Health Check**: < 100ms response time
- **Concurrent Requests**: Supports auto-scaling (2-10 ECS tasks based on load)

### Scalability

- **Ingestion Rate**: Handles 2,000+ submissions per minute with ECS auto-scaling
- **Query Pagination**: Prevents memory exhaustion with limit/offset parameters
- **Database Scaling**: DynamoDB provides unlimited horizontal scaling
- **Stateless Design**: No session state enables adding API instances freely

### Security

- **Authentication Required**: All endpoints except /health require valid JWT token
- **TLS Encryption**: HTTPS/TLS 1.3 in production (AWS ALB termination)
- **CORS Configuration**: Middleware configured for production origins only
- **Input Validation**: Pydantic validation prevents SQL injection and malformed data
- **Access Tier Enforcement**: Repository layer enforces filtering (defense in depth)

### Reliability

- **Graceful Degradation**: Returns 503 Service Unavailable if database unreachable
- **Structured Errors**: ADR-0008 compliant error responses with clear messages
- **Audit Logging**: All submissions and queries logged with username, access_tier, operation
- **Health Checks**: Database connectivity validated every 30 seconds

### Observability

- **Structured Logging**: JSON logs with username, access_tier, operation, response_time
- **CloudWatch Integration**: Logs shipped to CloudWatch Logs (AWS deployments)
- **Metrics**: Request count, error rate, response time percentiles
- **Tracing**: Request ID tracking for distributed tracing

---

## 4. Data Model / API Contract

### API Endpoints Summary

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/health` | GET | No | Basic health check |
| `/health/deep` | GET | No | Deep health check with component status |
| `/auth/login` | POST | No | Service account authentication |
| `/auth/refresh` | POST | No | Refresh access token (501 Not Implemented) |
| `/submit` | POST | Yes (CONTRIBUTOR+) | Submit threat intelligence |
| `/submissions/{id}` | GET | Yes (Any) | Get submission by ID |
| `/observables` | GET | Yes (Any) | Query observables with filters |
| `/statistics` | GET | Yes (Any) | Platform statistics |

### Health Endpoints

#### GET /health

**Summary**: Basic health check for load balancer probes

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

**Summary**: Service account authentication via Cognito

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

### Submission Endpoints

#### POST /submit

**Summary**: Submit threat intelligence sighting

**Authentication**: Required (Bearer token)

**Access Level**: CONTRIBUTOR, PARTNER, or CORE_MEMBER

**Request Body** (SubmissionRequest):
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
7. Store via `db.store_submission(submission)`
8. Log submission with user context
9. Return SubmissionResponse

**Error Responses**:
- 401 Unauthorized: Missing or invalid JWT
- 403 Forbidden: Insufficient access tier (OBSERVER/PUBLIC)
- 422 Unprocessable Entity: Invalid observable types or confidence score
- 500 Internal Server Error: Database failure

**Implementation**: `src/frank/main/api.py:281`

**Related Spec**: [Submission Model](../core/submission.spec.md)

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
- **PUBLIC**: Statistics only (submission_id, timestamp, confidence, observation_count)
- **OBSERVER**: Observable values masked (first 10 chars + "...")
- **CONTRIBUTOR**: Full observables, hit_targets anonymized (sector kept, organisation_id removed)
- **PARTNER**: Full submission data
- **CORE_MEMBER**: Complete access including audit context

**Error Responses**:
- 401 Unauthorized: Missing or invalid JWT
- 404 Not Found: Submission doesn't exist
- 403 Forbidden: Access tier insufficient for this submission
- 500 Internal Server Error: Database failure

**Implementation**: `src/frank/main/api.py:381`

**Related Spec**: [Submission Model](../core/submission.spec.md), [Access Tiers](../storage/base-interface.spec.md)

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

**Access Filtering**: Applied automatically via `db.query_observables()`

**Error Responses**:
- 401 Unauthorized: Missing or invalid JWT
- 500 Internal Server Error: Database failure

**Implementation**: `src/frank/main/api.py:440`

**Related Spec**: [Observable Model](../core/observable.spec.md)

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

### Data Models

**SubmissionRequest** (`src/frank/main/models.py`):
```python
class SubmissionRequest(BaseModel):
    observables: List[Observable]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    severity: Optional[str] = "MEDIUM"
    description: Optional[str] = None
    timestamp: Optional[datetime] = None
```

**SubmissionResponse** (`src/frank/main/models.py`):
```python
class SubmissionResponse(BaseModel):
    submission_id: str
    timestamp: datetime
    status: str
    message: str
```

**Related Specifications**: See [Submission Model](../core/submission.spec.md) for complete data model.

---

## 5. Test Coverage Requirements

### Integration Tests

**Location**: `tests/integration/test_main_api.py`

**Required Test Scenarios**:
- [ ] Health endpoints (basic and deep)
- [ ] Service account authentication flow
- [ ] Submission creation with various observable types
- [ ] Submission retrieval with access filtering (all tiers)
- [ ] Observable queries with pagination
- [ ] Platform statistics by access tier
- [ ] Error cases (401, 403, 404, 422, 500)

**Coverage Target**: ≥85% code coverage

### Manual Testing Checklist

```bash
# 1. Test public health endpoint
curl http://localhost:8000/health

# 2. Test authentication
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"service-test","password":"password"}'

# 3. Test submission (requires token)
curl -X POST http://localhost:8000/submit \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "observables": [{"observable_type":"ipv4","value":"1.2.3.4"}],
    "confidence_score": 0.8,
    "severity": "HIGH"
  }'

# 4. Test query observables
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/observables?limit=10"

# 5. Test statistics
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/statistics?days=7"
```

---

## 6. Implementation Status

### Checklist

- [x] Specification complete and reviewed
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
- [x] Integration tests written
- [x] Deployed to AWS ECS (Stage 3)

### Progress Notes

**Current Phase**: COMPLETE (except token refresh)

**Latest Update**: 2026-02-06 - Production deployment on AWS ECS with DynamoDB

### Implementation Notes

- **High-Volume Ingestion**: Handles 2,000+ submissions/min with ECS auto-scaling (2-10 tasks)
- **DynamoDB Performance**: Query latency < 20ms with GSI on observable_type
- **Access Filtering**: Zero security incidents with repository-layer enforcement
- **Service Accounts**: 15+ active service accounts across partner organizations

---

## 7. Evolution Path Across FRANK Stages

### Stage 1: SQLite + FastAPI (Local Development)

- ✅ Fully implemented
- **Database**: SQLite for all data
- **Authentication**: Mock Cognito (HS256 tokens)
- **Deployment**: Single-instance uvicorn server
- **Use Case**: Development and testing baseline

### Stage 2: DynamoDB + Docker (Learning Stage)

- ✅ Fully implemented
- **Database**: DynamoDB for submissions/observables
- **Authentication**: Mock Cognito in Docker
- **Deployment**: Docker Compose with LocalStack
- **Use Case**: Learning AWS access patterns

### Stage 3: AWS ECS + DynamoDB (Cloud Deployment)

- ✅ Fully implemented
- **Database**: AWS DynamoDB
- **Authentication**: AWS Cognito (RS256 tokens)
- **Deployment**: ECS Fargate with ALB, auto-scaling (2-10 tasks)
- **Use Case**: Production cloud deployment
- **Currently deployed**

### Stage 4: Kubernetes + ScyllaDB (Production Scale)

- ⏳ Planned
- **Database**: ScyllaDB for ultra-low latency
- **Authentication**: Multi-region Cognito
- **Deployment**: Kubernetes with service mesh
- **Use Case**: Global scale deployment

---

## 8. References

- **Related ADRs**:
  - [ADR-0005: Cognito Authentication Strategy](docs/adr/0005-cognito-authentication-strategy.md)
  - [ADR-0003: Tiered Access Control Model](docs/adr/0003-tiered-access-control-model.md)
  - [ADR-0008: Explicit Error Communication](docs/adr/0008-explicit-error-communication.md)

- **Related Specifications**:
  - [Authentication Patterns](authentication.spec.md) - JWT token validation
  - [Submission Model](../core/submission.spec.md) - Core data model
  - [Observable Model](../core/observable.spec.md) - Observable structure
  - [DynamoDB Storage](../storage/dynamodb.spec.md) - Database implementation

- **Implementation Files**:
  - `src/frank/main/api.py` - FastAPI application
  - `src/frank/main/models.py` - Request/response models
  - `tests/integration/test_main_api.py` - Integration tests

---

## 9. Open Questions & Decisions Pending

1. **Token Refresh**: When will POST /auth/refresh be implemented? (Currently 501)
2. **Rate Limiting**: Should rate limits be implemented in API or at ALB level?
3. **Caching**: Should frequent queries be cached? (e.g., Redis)
4. **Pagination**: Should cursor-based pagination replace offset-based for large result sets?
5. **GraphQL**: Should a GraphQL endpoint be added for complex queries?

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 2025-01-15 | 0.1 | API Team | Initial API implementation |
| 2025-02-01 | 0.9 | API Team | AWS ECS deployment |
| 2026-02-06 | 1.0 | SDD Migration | Formalized as specification |

---

**Questions or feedback?** See implementation at `src/frank/main/api.py` and tests at `tests/integration/test_main_api.py`.
