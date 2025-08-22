# FRANK Platform - Core API Endpoints

## Overview

The FRANK platform's core functionality centers around two primary API endpoints that enable threat intelligence submission and retrieval. These endpoints form the foundation of the collaborative threat intelligence ecosystem.

---

## API Endpoint Specifications

| Aspect | Specification |
|--------|---------------|
| **POST /v1/submission** | |
| Purpose | Submit threat intelligence sightings to the platform |
| Method | `POST` |
| Endpoint | `/v1/submission` |
| Authentication | Required (JWT + Client Certificate) |
| Access Level | Contributor, Partner, Core Member |
| Rate Limiting | 50/hour (Contributor), 100/hour (Partner), Unlimited (Core Member) |
| **GET /v1/sighting** | |
| Purpose | Retrieve threat intelligence sightings based on search criteria |
| Method | `GET` |
| Endpoint | `/v1/sighting` |
| Authentication | Required (JWT) |
| Access Level | Observer, Contributor, Partner, Core Member |
| Rate Limiting | 500/day (Observer), Unlimited (Others) |

---

## POST /v1/submission

### Request Details

| Property | Value |
|----------|-------|
| **Content-Type** | `application/yaml` or `application/json` |
| **Authorization** | `Bearer {jwt_token}` |
| **Headers** | `X-Client-Cert: {client_cert_fingerprint}` |

### Request Body Structure

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `submission.submitter.organization_id` | string | ✅ | Unique identifier for submitting organization |
| `submission.submitter.tier` | string | ✅ | Access tier: `contributor`, `partner`, `core_member` |
| `submission.sighting.sighting_id` | string | ✅ | UUID for the sighting event |
| `submission.sighting.timestamp` | ISO 8601 | ✅ | When the threat was observed |
| `submission.sighting.confidence` | integer | ✅ | Confidence score (0-100) |
| `submission.observables` | object | ✅ | Threat indicators and artifacts |

### Example Request

```yaml
submission:
  submitter:
    organization_id: "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff"
    tier: "partner"
  sighting:
    sighting_id: "sighting-ee20065d-2555-424f-ad9e-0f8428623c75"
    timestamp: "2025-01-20T14:30:22Z"
    confidence: 87
    severity: "high"
  observables:
    network:
      - type: "ipv4"
        value: "185.220.102.45"
        role: "c2_server"
        port: 443
      - type: "domain"
        value: "secure-bank-verify.nl"
        role: "phishing_domain"
    files:
      - type: "executable"
        name: "banking_update.exe"
        hash_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
```

### Response Structure

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Processing status: `accepted`, `rejected`, `pending_validation` |
| `submission_id` | string | Unique identifier for tracking this submission |
| `contribution_score_impact` | integer | Points added to organization's contribution score |
| `processing_status` | string | Current processing state: `queued`, `processing`, `completed` |
| `validation_required` | boolean | Whether community validation is needed |
| `errors` | array | Validation errors if status is `rejected` |

### Example Response

```json
{
  "status": "accepted",
  "submission_id": "sub-a1b2c3d4-5678-90ef-abcd-1234567890ab",
  "contribution_score_impact": 15,
  "processing_status": "queued",
  "validation_required": false,
  "estimated_processing_time": "2-5 minutes",
  "next_steps": {
    "track_status": "/v1/submission/sub-a1b2c3d4-5678-90ef-abcd-1234567890ab/status",
    "view_contribution": "/v1/organizations/me/contributions"
  }
}
```

---

## GET /v1/sighting

### Request Details

| Property | Value |
|----------|-------|
| **Content-Type** | `application/json` |
| **Authorization** | `Bearer {jwt_token}` |

### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `observable` | string | ❌ | Specific IoC to search for | `185.220.102.45` |
| `type` | string | ❌ | Observable type filter | `ipv4`, `domain`, `file_hash` |
| `start_date` | ISO 8601 | ❌ | Search start date | `2025-01-01T00:00:00Z` |
| `end_date` | ISO 8601 | ❌ | Search end date | `2025-01-20T23:59:59Z` |
| `sector` | string | ❌ | Target sector filter | `financial`, `healthcare` |
| `confidence_min` | integer | ❌ | Minimum confidence score | `70` |
| `tlp_level` | string | ❌ | Traffic Light Protocol level | `green`, `amber`, `red` |
| `campaign` | string | ❌ | Threat campaign identifier | `banking_campaign_2025` |
| `limit` | integer | ❌ | Maximum results to return | `100` (default: 50, max: 1000) |
| `offset` | integer | ❌ | Pagination offset | `0` |
| `format` | string | ❌ | Response format | `summary`, `detailed`, `full` |

### Example Request URLs

```http
GET /v1/sighting?observable=185.220.102.45&type=ipv4&start_date=2025-01-15T00:00:00Z

GET /v1/sighting?sector=financial&confidence_min=80&limit=100

GET /v1/sighting?campaign=banking_campaign_2025&format=detailed
```

### Response Structure

The response structure varies by access level and format parameter:

| Field | Type | Description | Access Level |
|-------|------|-------------|--------------|
| `total_results` | integer | Total matching sightings | All |
| `returned_results` | integer | Results in this response | All |
| `sightings` | array | Array of sighting objects | All |
| `aggregations` | object | Statistical summaries | Contributor+ |
| `threat_context` | object | Campaign and attribution data | Partner+ |
| `pagination` | object | Next/previous page information | All |

### Sighting Object Structure (by Access Level)

#### Observer Level Response
```json
{
  "total_results": 23,
  "returned_results": 10,
  "sightings": [
    {
      "sighting_id": "sighting-masked-12345",
      "timestamp": "2025-01-20T14:30:22Z",
      "observable_type": "ipv4",
      "observable_value": "185.220.102.***",
      "confidence": 87,
      "sector": "financial",
      "geographic_region": "nl_north_holland"
    }
  ],
  "aggregations": {
    "total_organizations": 8,
    "confidence_distribution": {
      "high": 15,
      "medium": 6,
      "low": 2
    }
  }
}
```

#### Partner Level Response
```json
{
  "total_results": 23,
  "returned_results": 10,
  "sightings": [
    {
      "sighting_id": "sighting-ee20065d-2555-424f-ad9e-0f8428623c75",
      "timestamp": "2025-01-20T14:30:22Z",
      "observable": {
        "type": "ipv4",
        "value": "185.220.102.45",
        "role": "c2_server",
        "port": 443
      },
      "confidence": 87,
      "severity": "high",
      "submitter": {
        "tier": "partner",
        "sector": "cybersecurity_services",
        "organization_id": "identity-masked-uuid"
      },
      "impact": {
        "affected_systems": 5,
        "containment_time": "00:45:00",
        "financial_impact_category": "medium"
      }
    }
  ],
  "threat_context": {
    "campaign": {
      "id": "campaign-c3d4e5f6-5678-9abc-def0-123456789012",
      "name": "banking_credential_harvest_2025_q1",
      "confidence": 78
    },
    "mitre_attack": {
      "techniques": ["T1566.001", "T1071.001"],
      "tactics": ["initial_access", "command_and_control"]
    },
    "malware_family": {
      "name": "trickbot_variant",
      "capabilities": ["credential_theft", "screen_capture"]
    }
  }
}
```

### Response Filtering by Access Level

| Data Element | Observer | Contributor | Partner | Core Member |
|--------------|----------|-------------|---------|-------------|
| Observable Values | Masked | Partial | Full | Full |
| Organization IDs | ❌ | Masked | Masked | Full |
| Financial Impact | ❌ | Category | Detailed | Full |
| Infrastructure Details | ❌ | Basic | Detailed | Full |
| Attribution Data | ❌ | Limited | Full | Full |
| Mitigation Actions | ❌ | Summary | Detailed | Full |

### Error Responses

| HTTP Code | Error Type | Description |
|-----------|------------|-------------|
| `400` | `INVALID_QUERY_PARAMETERS` | Malformed or invalid query parameters |
| `401` | `AUTHENTICATION_REQUIRED` | Missing or invalid JWT token |
| `403` | `INSUFFICIENT_ACCESS_LEVEL` | User tier doesn't permit this query |
| `429` | `RATE_LIMIT_EXCEEDED` | Too many requests within time window |
| `404` | `NO_RESULTS_FOUND` | No sightings match the search criteria |

### Example Error Response
```json
{
  "error": {
    "code": "INVALID_QUERY_PARAMETERS",
    "message": "Invalid date range: start_date must be before end_date",
    "details": {
      "start_date": "2025-01-20T00:00:00Z",
      "end_date": "2025-01-15T00:00:00Z"
    },
    "timestamp": "2025-01-20T14:30:22Z",
    "request_id": "req-abc123"
  }
}
```

---

## Implementation Notes

### Data Anonymization
- **Observer Level**: IP addresses masked (last octet), organization IDs removed
- **Contributor Level**: Partial observable data, pseudonymized organization IDs
- **Partner Level**: Full observables, anonymized organization details
- **Core Member**: Complete data access for platform governance

### Performance Considerations
- **Caching**: Frequently requested IoCs cached for 15 minutes
- **Pagination**: Default limit of 50 results, maximum 1000 per request
- **Indexing**: Optimized for queries by observable value, timestamp, and sector

### Security Measures
- **Input Validation**: All submissions validated against YAML/JSON schema
- **Rate Limiting**: Prevents abuse while supporting legitimate high-volume usage
- **Audit Logging**: All API calls logged for security and compliance monitoring