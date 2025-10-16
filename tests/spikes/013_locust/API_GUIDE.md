# FRANK Platform API Guide - Stage 3

## Overview

This guide covers the full RESTful API for Stage 3 of the FRANK platform. Stage 3 implements complete submission management, observable queries, and platform statistics with DynamoDB backend on AWS ECS.

## Table of Contents

- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
  - [Health & Status](#health--status)
  - [Submissions](#submissions)
  - [Observables](#observables)
  - [Statistics](#statistics)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Code Examples](#code-examples)
- [Testing](#testing)

## Quick Start

### Base URL

- **Local Development**: `http://localhost:8080`
- **AWS Deployment**: `https://frank-stage3.lab271.io`

### Interactive Documentation

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`

### Example Request

```bash
curl -X POST https://frank-stage3.lab271.io/api/v1/submissions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "submitter_access_level": "PARTNER",
    "hit_target_sector": "financial",
    "confidence": 85,
    "network_observables": [
      {"type": "ipv4", "value": "185.220.102.45", "role": "c2"}
    ]
  }'
```

## Authentication

All API endpoints (except health checks) require authentication via API key.

### API Key Format

Include your API key in the `Authorization` header using Bearer token format:

```
Authorization: Bearer <your-api-key>
```

### Getting an API Key

Contact your FRANK administrator to obtain an API key. In production, keys are managed through AWS Secrets Manager.

## API Endpoints

### Health & Status

#### GET /

Root endpoint with API information.

**Authentication:** Not required

**Response:**
```json
{
  "application": "FRANK Platform",
  "version": "0.1.0",
  "status": "running",
  "message": "Welcome to FRANK threat intelligence API",
  "api_docs": "/docs",
  "api_version": "v1"
}
```

#### GET /v1/health

Basic health check for load balancer.

**Authentication:** Not required

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "service": "FRANK",
  "version": "0.1.0"
}
```

#### GET /v1/health/deep

Comprehensive health check including database connectivity.

**Authentication:** Not required

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "version": "0.1.0",
  "checks": {
    "database": {
      "status": "healthy",
      "type": "dynamodb",
      "table": "frank-stage3-data"
    }
  },
  "duration": "0.123s"
}
```

### Submissions

#### POST /api/v1/submissions

Create a new threat intelligence submission.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `submitter_access_level` | string (enum) | Yes | Access level: PUBLIC, OBSERVER, CONTRIBUTOR, PARTNER, CORE_MEMBER |
| `submitter_sector` | string | No | Submitter's industry sector |
| `submitter_region` | string | No | Submitter's geographic region |
| `hit_target_sector` | string | Yes | Affected organization's sector |
| `hit_target_size` | string | No | Organization size: small, medium, large |
| `hit_target_region` | string | No | Affected organization's region |
| `confidence` | integer | No | Confidence score 0-100 (default: 69) |
| `severity` | string (enum) | No | LOW, MEDIUM, HIGH, CRITICAL |
| `network_observables` | array | No | Network observables (IPs, domains, URLs) |
| `file_observables` | array | No | File observables (hashes) |
| `process_observables` | array | No | Process observables |
| `tlp_level` | string | No | TLP classification: WHITE, GREEN, AMBER, RED |
| `processing_notes` | string | No | Additional processing notes |

**Example Request:**
```json
{
  "submitter_access_level": "PARTNER",
  "submitter_sector": "financial",
  "submitter_region": "eu-west",
  "hit_target_sector": "healthcare",
  "hit_target_size": "large",
  "hit_target_region": "eu-central",
  "confidence": 85,
  "severity": "HIGH",
  "network_observables": [
    {
      "type": "ipv4",
      "value": "185.220.102.45",
      "role": "c2",
      "port": 443,
      "protocol": "https",
      "connection_count": 127
    },
    {
      "type": "domain",
      "value": "malicious-c2.example.com",
      "role": "c2"
    }
  ],
  "file_observables": [
    {
      "type": "sha256",
      "value": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
    }
  ],
  "tlp_level": "AMBER",
  "processing_notes": "Detected via SIEM correlation rules."
}
```

**Response (201 Created):**
```json
{
  "submission_id": "submission--a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "created",
  "timestamp": "2025-01-15T10:30:00Z",
  "message": "Submission created successfully"
}
```

#### GET /api/v1/submissions/{submission_id}

Retrieve a specific submission by ID.

**Authentication:** Required

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `submission_id` | string | Yes | Submission identifier |

**Response (200 OK):**
```json
{
  "submission_id": "submission--a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "format_version": "0.1.0",
  "timestamp": "2025-01-15T10:30:00Z",
  "submitter": {
    "organisation_id": "identity--12345678-1234-1234-1234-123456789abc",
    "access_level": "PARTNER",
    "sector": "financial",
    "region": "eu-west"
  },
  "hit_target": {
    "organisation_id": "identity--87654321-4321-4321-4321-cba987654321",
    "sector": "healthcare",
    "organisation_size": "large",
    "region": "eu-central"
  },
  "sighting": {
    "sighting_id": "sighting--11111111-2222-3333-4444-555555555555",
    "timestamp": "2025-01-15T10:30:00Z",
    "confidence": 85,
    "severity": "HIGH",
    "observables": {
      "network": [
        {
          "id": "ipv4--aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
          "type": "ipv4",
          "value": "185.220.102.45",
          "role": "c2",
          "port": 443,
          "protocol": "https",
          "connection_count": 127
        }
      ],
      "file": [
        {
          "id": "sha256--ffffffff-0000-1111-2222-333333333333",
          "type": "sha256",
          "value": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
        }
      ]
    }
  },
  "tlp_level": "AMBER",
  "processing_notes": "Detected via SIEM correlation rules."
}
```

### Observables

#### GET /api/v1/observables

Query observables with optional filters.

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `observable_type` | string (enum) | No | Filter by type (ipv4, ipv6, domain, url, md5, sha256, etc.) |
| `min_confidence` | float | No | Minimum confidence score (0-100) |
| `sectors` | array[string] | No | Filter by sectors (comma-separated) |
| `days_back` | integer | No | Days to look back (1-365) |
| `limit` | integer | No | Maximum results (1-1000, default: 100) |

**Example Request:**
```bash
GET /api/v1/observables?observable_type=ipv4&min_confidence=80&days_back=7&limit=50
```

**Response (200 OK):**
```json
{
  "total": 15,
  "limit": 50,
  "observables": [
    {
      "observable_hash": "abc123def456...",
      "observable_type": "ipv4",
      "observable_value": "185.220.102.45",
      "total_sightings": 3,
      "first_seen": "2025-01-10T08:00:00Z",
      "last_seen": "2025-01-15T10:30:00Z",
      "unique_organisations": 2,
      "avg_confidence": 87.5
    },
    {
      "observable_hash": "789xyz012abc...",
      "observable_type": "ipv4",
      "observable_value": "203.0.113.42",
      "total_sightings": 1,
      "first_seen": "2025-01-14T14:20:00Z",
      "last_seen": "2025-01-14T14:20:00Z",
      "unique_organisations": 1,
      "avg_confidence": 85.0
    }
  ]
}
```

#### GET /api/v1/observables/search

Search for observables by value (substring match).

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `value` | string | Yes | Search value (substring match) |

**Example Request:**
```bash
GET /api/v1/observables/search?value=185.220
```

**Response (200 OK):**
```json
{
  "total": 3,
  "search_value": "185.220",
  "observables": [
    {
      "observable_type": "ipv4",
      "observable_value": "185.220.102.45",
      "submission_id": "submission--...",
      "submitter_id": "identity--...",
      "confidence": 85,
      "severity": "HIGH",
      "timestamp": "2025-01-15T10:30:00Z"
    }
  ]
}
```

### Statistics

#### GET /api/v1/statistics

Get platform statistics summary.

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `days` | integer | No | Number of days to include (1-365, default: 30) |

**Example Request:**
```bash
GET /api/v1/statistics?days=30
```

**Response (200 OK):**
```json
{
  "organisation_id": "org-001",
  "days": 30,
  "total_organisations": 15,
  "total_submissions": 142,
  "total_sightings": 156,
  "total_observables": 487,
  "observable_totals": {
    "ipv4": 234,
    "domain": 128,
    "url": 67,
    "sha256": 45,
    "md5": 13,
    "ipv6": 0,
    "sha1": 0
  }
}
```

## Data Models

### Observable Types

Supported observable types:

- `ipv4` - IPv4 address
- `ipv6` - IPv6 address
- `domain` - Domain name
- `url` - Full URL
- `md5` - MD5 file hash
- `sha1` - SHA-1 file hash
- `sha256` - SHA-256 file hash
- `email` - Email address
- `user_agent` - HTTP User-Agent string
- `process_name` - Process/executable name

### Access Tiers

FRANK implements a five-tier access control model:

1. **PUBLIC** - Limited access, heavily anonymized data
2. **OBSERVER** - Read-only access to aggregated threat data
3. **CONTRIBUTOR** - Can submit and view own submissions + public data
4. **PARTNER** - Full access to partner network submissions
5. **CORE_MEMBER** - Full platform access including sensitive metadata

### Severity Levels

- `LOW` - Low severity threat
- `MEDIUM` - Medium severity threat
- `HIGH` - High severity threat
- `CRITICAL` - Critical severity threat

### TLP Levels

Traffic Light Protocol (TLP) classification:

- `WHITE` - Unlimited disclosure
- `GREEN` - Community disclosure
- `AMBER` - Limited disclosure
- `RED` - No disclosure

## Error Handling

### HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid request format |
| 401 | Unauthorized - Missing or invalid API key |
| 404 | Not Found - Resource not found |
| 422 | Unprocessable Entity - Validation error |
| 500 | Internal Server Error - Server error |

### Error Response Format

All errors return a consistent JSON format:

```json
{
  "status_code": 422,
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": {
    "errors": [
      {
        "loc": ["body", "confidence"],
        "msg": "ensure this value is greater than or equal to 0",
        "type": "value_error.number.not_ge"
      }
    ]
  }
}
```

## Code Examples

### Python

```python
import requests
import json

# Configuration
API_BASE_URL = "https://frank-stage3.lab271.io"
API_KEY = "your-api-key"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Create a submission
submission_data = {
    "submitter_access_level": "PARTNER",
    "hit_target_sector": "financial",
    "confidence": 85,
    "severity": "HIGH",
    "network_observables": [
        {
            "type": "ipv4",
            "value": "185.220.102.45",
            "role": "c2",
            "port": 443
        }
    ],
    "tlp_level": "AMBER"
}

response = requests.post(
    f"{API_BASE_URL}/api/v1/submissions",
    headers=headers,
    json=submission_data
)

if response.status_code == 201:
    result = response.json()
    print(f"Submission created: {result['submission_id']}")
else:
    print(f"Error: {response.status_code} - {response.text}")

# Query observables
params = {
    "observable_type": "ipv4",
    "min_confidence": 80,
    "limit": 50
}

response = requests.get(
    f"{API_BASE_URL}/api/v1/observables",
    headers=headers,
    params=params
)

if response.status_code == 200:
    results = response.json()
    print(f"Found {results['total']} observables")
    for obs in results['observables']:
        print(f"  - {obs['observable_value']} (confidence: {obs['avg_confidence']})")
```

### cURL

```bash
# Create submission
curl -X POST https://frank-stage3.lab271.io/api/v1/submissions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "submitter_access_level": "PARTNER",
    "hit_target_sector": "financial",
    "confidence": 85,
    "network_observables": [
      {"type": "ipv4", "value": "185.220.102.45", "role": "c2"}
    ]
  }'

# Get submission
curl -X GET https://frank-stage3.lab271.io/api/v1/submissions/submission--a1b2c3d4-... \
  -H "Authorization: Bearer your-api-key"

# Query observables
curl -X GET "https://frank-stage3.lab271.io/api/v1/observables?observable_type=ipv4&limit=10" \
  -H "Authorization: Bearer your-api-key"

# Get statistics
curl -X GET "https://frank-stage3.lab271.io/api/v1/statistics?days=30" \
  -H "Authorization: Bearer your-api-key"
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const API_BASE_URL = 'https://frank-stage3.lab271.io';
const API_KEY = 'your-api-key';

const headers = {
  'Authorization': `Bearer ${API_KEY}`,
  'Content-Type': 'application/json'
};

// Create submission
async function createSubmission() {
  const submissionData = {
    submitter_access_level: 'PARTNER',
    hit_target_sector: 'financial',
    confidence: 85,
    severity: 'HIGH',
    network_observables: [
      {
        type: 'ipv4',
        value: '185.220.102.45',
        role: 'c2',
        port: 443
      }
    ],
    tlp_level: 'AMBER'
  };

  try {
    const response = await axios.post(
      `${API_BASE_URL}/api/v1/submissions`,
      submissionData,
      { headers }
    );
    console.log(`Submission created: ${response.data.submission_id}`);
    return response.data;
  } catch (error) {
    console.error('Error creating submission:', error.response?.data || error.message);
  }
}

// Query observables
async function queryObservables() {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/api/v1/observables`,
      {
        headers,
        params: {
          observable_type: 'ipv4',
          min_confidence: 80,
          limit: 50
        }
      }
    );
    console.log(`Found ${response.data.total} observables`);
    return response.data;
  } catch (error) {
    console.error('Error querying observables:', error.response?.data || error.message);
  }
}
```

## Testing

### Using the Test Script

A comprehensive test script is provided in `stages/stage3/test_api.py`:

```bash
# Run the test script
cd stages/stage3
python test_api.py
```

### Manual Testing

1. **Start the API server locally:**
```bash
cd stages/stage3
python api.py --environment localstack --port 8080 --reload
```

2. **Access the interactive docs:**
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

3. **Test with cURL:**
```bash
# Health check
curl http://localhost:8080/v1/health

# Create submission (with test API key)
curl -X POST http://localhost:8080/api/v1/submissions \
  -H "Authorization: Bearer dev-key-12345" \
  -H "Content-Type: application/json" \
  -d @example_submission.json
```

### Load Testing with Locust

FRANK uses Locust for Python-based load testing:

```bash
# Install Locust
pip install locust

# Quick validation test (2 minutes, 10 users)
python run_performance_test.py --quick --host http://localhost:8080

# Standard performance test (5 minutes, 50 users)
python run_performance_test.py --standard --host http://localhost:8080

# Stress test (10 minutes, 200 users)
python run_performance_test.py --stress --host http://localhost:8080

# Full test suite (all presets)
python run_performance_test.py --full --host http://localhost:8080

# Custom test
python run_performance_test.py \
  --users 100 \
  --spawn-rate 10 \
  --duration 5m \
  --host http://localhost:8080

# Interactive web UI
locust -f locustfile.py --host http://localhost:8080
# Then open http://localhost:8089
```

See [LOAD_TESTING.md](LOAD_TESTING.md) for comprehensive load testing guide.

## Performance Targets

- **API Response Time**: < 500ms (95th percentile)
- **Database Latency**: < 100ms (99th percentile)
- **Service Availability**: > 99.9%
- **Throughput**: 1000+ requests/minute per task

## Support

For issues or questions:

1. Check the [main README](README.md) for deployment information
2. Review the [CloudFormation template](ansible/templates/frank-stage3-infra.yaml)
3. Check CloudWatch Logs: `/ecs/frank-stage3`
4. Review the [CLAUDE.md](../../CLAUDE.md) project documentation

## License

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
