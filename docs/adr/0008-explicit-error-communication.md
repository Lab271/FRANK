# Explicit Error Communication

- **Status:** accepted
- **Date:** 2026-01-28
- **Decision Makers:** FRANK Architecture Team
- **Related:** [ADR-0007](0007-forgiving-input-strong-output.md)

## Context and Problem Statement

When threat intelligence submissions fail validation or processing, users need to understand what went wrong and how to fix it. Generic error messages ("Invalid submission") frustrate users and generate support overhead. How should FRANK communicate errors to enable users to quickly correct issues without requiring deep technical knowledge?

## Decision Drivers

- Users have varying technical expertise levels
- Need to minimize support burden from unclear errors
- Want high submission success rate on retry
- Must balance security (don't leak system details) with helpfulness
- Should guide users toward correct submission format
- Need machine-readable errors for automated systems

## Considered Options

1. **Explicit Actionable Errors** - Detailed field-level errors with correction guidance and examples
2. **Generic Errors** - Simple high-level error messages
3. **Code-Only Errors** - Error codes requiring documentation lookup

## Decision Outcome

Chosen option: "Explicit Actionable Errors", because it enables users to quickly understand and correct submission problems without support intervention while maintaining security boundaries.

All system errors provide clear, actionable feedback that enables users to correct issues without requiring system knowledge. Error messages include specific field validation failures, suggested corrections, and examples of valid input formats.

### Positive Consequences

- Users can self-correct submission errors
- Reduced support burden from unclear errors
- Higher retry success rate
- Better user experience and satisfaction
- Machine-readable error format for automation
- Field-level granularity speeds debugging
- Examples guide users toward correct format

### Negative Consequences

- More complex error handling logic
- Potential information disclosure risks (mitigated by careful message construction)
- Internationalization complexity
- Need to maintain error message quality
- Longer response payloads for errors

## Pros and Cons of the Options

### Explicit Actionable Errors

- Good, because users self-correct without support
- Good, because specific field-level guidance
- Good, because examples show correct format
- Good, because machine-readable structure
- Good, because faster retry success
- Bad, because error handling complexity
- Bad, because potential information disclosure
- Bad, because maintenance overhead

### Generic Errors

- Good, because simple to implement
- Good, because minimal information disclosure
- Good, because short error responses
- Bad, because frustrates users
- Bad, because high support burden
- Bad, because low retry success rate
- Bad, because difficult debugging

### Code-Only Errors

- Good, because concise responses
- Good, because easy internationalization
- Good, because minimal implementation
- Bad, because requires documentation lookup
- Bad, because interrupts workflow
- Bad, because difficult for humans
- Bad, because inconsistent documentation quality

## Implementation: Multi-Layer Error Communication

### Layer 1: HTTP Status Codes

Standard HTTP semantics:
- `400 Bad Request` - Client error (validation, malformed)
- `401 Unauthorized` - Missing or invalid authentication
- `403 Forbidden` - Insufficient access tier
- `404 Not Found` - Resource doesn't exist
- `409 Conflict` - Duplicate submission
- `422 Unprocessable Entity` - Valid format, invalid semantics
- `500 Internal Server Error` - Server-side failure
- `503 Service Unavailable` - Temporary unavailability

### Layer 2: Error Response Structure

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Submission validation failed",
    "details": [
      {
        "field": "sighting.observables.network[0].observable_value",
        "issue": "Invalid IPv4 address format",
        "received": "192.168.1.999",
        "expected": "Valid IPv4 address (e.g., 192.168.1.1)",
        "suggestion": "Check that each octet is 0-255"
      }
    ],
    "documentation": "https://frank.example.com/docs/api/observables#ipv4"
  }
}
```

**Key Components:**
- **code** - Machine-readable error category
- **message** - Human-readable summary
- **details** - Field-level error array
- **field** - JSONPath to problematic field
- **issue** - What's wrong
- **received** - What was provided (sanitized)
- **expected** - What format is valid
- **suggestion** - How to fix it
- **documentation** - Link to relevant docs

### Layer 3: Pydantic Validation Integration

```python
from pydantic import ValidationError, field_validator

try:
    submission = Submission.model_validate(data)
except ValidationError as e:
    # Transform Pydantic errors to FRANK error format
    errors = []
    for error in e.errors():
        field_path = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field_path,
            "issue": error["msg"],
            "type": error["type"],
            "suggestion": get_suggestion_for_error_type(error["type"])
        })
    raise FRANKValidationError(errors)
```

### Layer 4: Custom Domain Exceptions

```python
# src/frank/core/exceptions.py

class FRANKError(Exception):
    """Base exception with structured error information"""
    def __init__(self, message: str, code: str, details: Optional[List[dict]] = None):
        self.message = message
        self.code = code
        self.details = details or []

class ValidationError(FRANKError):
    """Validation failure with field-level details"""
    pass

class AccessDeniedError(FRANKError):
    """Insufficient access tier for operation"""
    def __init__(self, required_tier: AccessTier, user_tier: AccessTier):
        super().__init__(
            message=f"Access denied: {required_tier.value} tier required",
            code="ACCESS_DENIED",
            details=[{
                "required_tier": required_tier.value,
                "user_tier": user_tier.value,
                "suggestion": "Contact organization admin to upgrade access tier"
            }]
        )

class DuplicateSubmissionError(FRANKError):
    """Submission already exists"""
    def __init__(self, existing_id: str):
        super().__init__(
            message="Duplicate submission detected",
            code="DUPLICATE_SUBMISSION",
            details=[{
                "existing_id": existing_id,
                "suggestion": "Check if this submission was already processed"
            }]
        )
```

## Error Message Examples

### Validation Error (Field-Level)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Observable validation failed",
    "details": [
      {
        "field": "sighting.observables.network[2].observable_value",
        "issue": "Invalid domain format",
        "received": "example..com",
        "expected": "Valid domain name (e.g., example.com)",
        "suggestion": "Remove consecutive dots from domain name",
        "documentation": "https://frank.example.com/docs/api/observables#domain"
      }
    ]
  }
}
```

### Access Control Error

```json
{
  "error": {
    "code": "ACCESS_DENIED",
    "message": "Insufficient access tier",
    "details": [
      {
        "operation": "view_core_member_submissions",
        "required_tier": "CORE_MEMBER",
        "user_tier": "CONTRIBUTOR",
        "suggestion": "Contact your organization administrator to request CORE_MEMBER access"
      }
    ],
    "documentation": "https://frank.example.com/docs/access-tiers"
  }
}
```

### Business Logic Error

```json
{
  "error": {
    "code": "INVALID_SIGHTING_DATE",
    "message": "Sighting date validation failed",
    "details": [
      {
        "field": "sighting.sighted_at",
        "issue": "Sighting date is in the future",
        "received": "2027-06-15T10:00:00Z",
        "current_time": "2026-01-28T14:30:00Z",
        "suggestion": "Verify sighting timestamp - future dates not allowed",
        "note": "System clock differences may cause this error"
      }
    ]
  }
}
```

### Multiple Errors

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Multiple validation errors",
    "details": [
      {
        "field": "submitter.org_id",
        "issue": "Invalid organization ID format",
        "received": "123",
        "expected": "STIX format: org--<uuid>",
        "example": "org--550e8400-e29b-41d4-a716-446655440000"
      },
      {
        "field": "sighting.observables.file[0].hash_value",
        "issue": "Invalid SHA256 hash length",
        "received": "abc123",
        "expected": "64 hexadecimal characters",
        "example": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
      }
    ]
  }
}
```

## Security Considerations

### Information Disclosure Prevention

**Do NOT include in errors:**
- Internal system paths or file names
- Database schema details
- Stack traces in production
- Authentication credentials or tokens
- Internal service names or IPs
- Version numbers (unless public API)

**Safe to include:**
- Field paths within submitted data
- Validation rule descriptions
- Sanitized user input (truncated if needed)
- Public API documentation links
- Generic error categories

### Input Sanitization in Errors

```python
def sanitize_for_error_message(value: Any, max_length: int = 100) -> str:
    """Sanitize user input for safe inclusion in error messages"""
    str_value = str(value)

    # Truncate long values
    if len(str_value) > max_length:
        str_value = str_value[:max_length] + "..."

    # Remove control characters
    str_value = "".join(c for c in str_value if c.isprintable() or c in "\n\t")

    # HTML entity encode
    str_value = html.escape(str_value)

    return str_value
```

## API Error Response Guidelines

### Logging vs. User Messages

**Log (internal):**
```python
logger.error(
    "Submission validation failed",
    extra={
        "submission_id": submission_id,
        "user_id": user_id,
        "validation_errors": validation_errors,
        "stack_trace": traceback.format_exc()
    }
)
```

**Return (external):**
```python
return {
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Submission validation failed",
        "details": sanitized_field_errors  # No stack traces!
    }
}
```

### Progressive Error Detail

Development vs. Production:

```python
def format_error_response(error: FRANKError, environment: str) -> dict:
    response = {
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details
        }
    }

    # Additional debug info in development only
    if environment == "development":
        response["error"]["debug"] = {
            "exception_type": type(error).__name__,
            "timestamp": datetime.utcnow().isoformat()
        }

    return response
```

## Testing Error Communication

### Error Message Quality Tests

```python
def test_validation_error_includes_field_path():
    """Validation errors must specify exact field location"""
    with pytest.raises(ValidationError) as exc_info:
        Observable.create_ipv4("999.999.999.999")

    error = exc_info.value
    assert error.details[0]["field"] == "observable_value"
    assert "expected" in error.details[0]
    assert "suggestion" in error.details[0]

def test_error_message_actionable():
    """Error messages must be actionable (not just descriptive)"""
    with pytest.raises(AccessDeniedError) as exc_info:
        submission.view(requester_tier=AccessTier.OBSERVER)

    error = exc_info.value
    assert "suggestion" in error.details[0]
    assert "contact" in error.details[0]["suggestion"].lower()
```

### Error Response Format Tests

```python
def test_api_error_response_structure():
    """API errors must follow standard structure"""
    response = client.post("/v1/submissions", json=invalid_data)

    assert response.status_code == 400
    error = response.json()["error"]

    assert "code" in error
    assert "message" in error
    assert "details" in error
    assert isinstance(error["details"], list)
```

## Links

- Enables [ADR-0007: Forgiving Input, Strong Output](0007-forgiving-input-strong-output.md)
- Implementation: [src/frank/core/exceptions.py](../../src/frank/core/exceptions.py)
- API Documentation: [docs/api/error-handling.md](../api/error-handling.md) (to be created)
