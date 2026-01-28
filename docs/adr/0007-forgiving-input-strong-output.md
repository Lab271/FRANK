# Forgiving Input, Strong Output

- **Status:** accepted
- **Date:** 2026-01-28
- **Decision Makers:** FRANK Architecture Team
- **Related:** [ADR-0008](0008-explicit-error-communication.md)

## Context and Problem Statement

Threat intelligence submissions come from diverse sources with varying data quality, formats, and completeness. How should FRANK balance accepting real-world messy data while maintaining internal consistency and producing reliable, well-structured output for consumers?

## Decision Drivers

- Real-world threat intelligence has inconsistent formats
- Need to maximize submission acceptance without sacrificing quality
- Must maintain internal data consistency
- API consumers require predictable, well-structured data
- Want to avoid brittleness from strict validation
- Need clear boundaries between external and internal representations

## Considered Options

1. **Postel's Law Approach** - "Be conservative in what you send, be liberal in what you accept"
2. **Strict Validation** - Reject any submission that doesn't match exact schema
3. **Permissive Everything** - Accept anything, do minimal validation

## Decision Outcome

Chosen option: "Postel's Law Approach", because it maximizes successful submissions while ensuring all system output is consistent and reliable.

The system accepts input in flexible formats while producing consistent, well-structured output. APIs tolerate variations in submission formats, field ordering, and optional data while ensuring all output follows strict schemas and validation rules.

### Positive Consequences

- Higher submission success rate from diverse sources
- Reduced friction for threat intelligence contributors
- Internal consistency maintained through normalization
- API consumers receive predictable data structures
- Legacy format support without internal technical debt
- Clear transformation point between external and internal models

### Negative Consequences

- Input parsing complexity increases
- Need comprehensive normalization logic
- Potential security risks from overly permissive input
- Must maintain both lenient input and strict output schemas
- Testing complexity for all input variations

## Pros and Cons of the Options

### Postel's Law Approach

- Good, because maximizes submission acceptance
- Good, because reduces contributor friction
- Good, because maintains internal consistency
- Good, because predictable output for consumers
- Good, because supports legacy formats
- Bad, because parsing complexity
- Bad, because requires careful security consideration

### Strict Validation

- Good, because simple validation logic
- Good, because clear error messages
- Good, because strong security boundaries
- Bad, because high rejection rate
- Bad, because frustrates contributors
- Bad, because brittle to format variations
- Bad, because difficult to evolve schema

### Permissive Everything

- Good, because highest acceptance rate
- Good, because minimal validation code
- Bad, because inconsistent internal data
- Bad, because unpredictable output
- Bad, because potential security vulnerabilities
- Bad, because maintenance nightmare

## Implementation: Pydantic V2 with Dual Schemas

### Input Models: Forgiving Configuration

```python
from pydantic import BaseModel, ConfigDict, field_validator

class SubmissionInput(BaseModel):
    """Forgiving input model for external submissions"""

    model_config = ConfigDict(
        extra="ignore",              # Ignore unknown fields
        str_strip_whitespace=True,   # Clean input strings
        str_min_length=0,            # Allow empty strings (will validate separately)
    )

    submitted_at: Optional[str] = None  # Accept multiple date formats

    @field_validator("submitted_at", mode="before")
    @classmethod
    def parse_flexible_datetime(cls, v):
        """Accept ISO, RFC, Unix timestamps, relative dates"""
        if v is None:
            return datetime.utcnow()
        # Try multiple formats...
        return normalized_datetime
```

### Internal Models: Strict Validation

```python
class Submission(BaseModel):
    """Strict internal model with guaranteed consistency"""

    model_config = ConfigDict(
        extra="forbid",              # Reject unknown fields
        validate_assignment=True,    # Validate on attribute assignment
    )

    submission_id: str = Field(pattern=r"^submission--[0-9a-f-]+$")
    submitted_at: datetime  # Always UTC datetime

    @field_serializer("submitted_at")
    def serialize_datetime(self, dt: datetime) -> str:
        """Always output ISO format"""
        return dt.isoformat() + "Z"
```

### Transformation Layer

```python
class Submission:
    @classmethod
    def from_legacy_dict(cls, data: dict) -> "Submission":
        """Parse legacy submission formats"""
        # Normalize field names (sighting_id → sighting-id)
        # Parse flexible date formats
        # Handle missing optional fields
        # Validate and construct strict internal model
        return cls(**normalized_data)

    def to_json(self) -> str:
        """Output strict, well-formatted JSON"""
        return self.model_dump_json(exclude_none=True, indent=2)
```

## Input Flexibility Examples

### Date Format Acceptance

```python
# All acceptable inputs (normalized to ISO UTC):
"2026-01-28T10:30:00Z"          # ISO with Z
"2026-01-28T10:30:00+00:00"     # ISO with timezone
"2026-01-28 10:30:00"           # Space separator
"1738064400"                    # Unix timestamp
"2 hours ago"                   # Relative time (development only)
```

**Output:** Always `"2026-01-28T10:30:00Z"`

### Field Ordering

```python
# Both inputs accepted:
{"observable_type": "ipv4", "observable_value": "192.168.1.1"}
{"observable_value": "192.168.1.1", "observable_type": "ipv4"}

# Output order guaranteed:
{
  "observable_type": "ipv4",
  "observable_value": "192.168.1.1",
  "observable_id": "observable--uuid"
}
```

### Optional Field Handling

```python
# Minimal input (many fields optional):
{
  "submitter_org_id": "org--123",
  "sighting": {
    "observables": [{"type": "ipv4", "value": "192.168.1.1"}]
  }
}

# Output includes defaults and generated fields:
{
  "submission_id": "submission--uuid",
  "submitter": {
    "org_id": "org--123",
    "access_tier": "CONTRIBUTOR"
  },
  "submitted_at": "2026-01-28T10:30:00Z",
  "sighting": {
    "sighting_id": "sighting--uuid",
    "observables": {
      "network": [{
        "observable_id": "observable--uuid",
        "observable_type": "ipv4",
        "observable_value": "192.168.1.1"
      }]
    }
  }
}
```

### Legacy Format Support

```python
# Old format (underscore field names):
{
  "sighting_id": "123",
  "observable_type": "IP",
  "observable_value": "192.168.1.1"
}

# Normalized internally, output modern format:
{
  "sighting-id": "sighting--uuid",
  "observables": [{
    "observable-id": "observable--uuid",
    "observable-type": "ipv4",
    "observable-value": "192.168.1.1"
  }]
}
```

## Output Consistency Guarantees

### Always Present Fields

Core fields always in output (never null/missing):
- `submission_id` - STIX format ID
- `submitted_at` - ISO UTC timestamp
- `submitter.org_id` - Organization identifier
- All IDs follow STIX pattern: `<type>--<uuid>`

### Predictable Structure

- Field order consistent across responses
- Empty collections as `[]`, never `null`
- Nested objects never `null` if parent exists
- Enumerations always uppercase strings

### Serialization Format

```python
# JSON output format (strict):
{
  "snake_case_fields": true,     # Consistent naming
  "dates": "ISO-8601-UTC",       # Standard format
  "ids": "stix--uuid-format",    # Standard pattern
  "empty_lists": [],             # Never null
  "sorted_keys": true            # Predictable order
}
```

## Security Boundaries

While input is forgiving, security validation remains strict:

**Always Validated (Security Critical):**
- SQL injection patterns in string fields
- XSS patterns in text content
- Path traversal in file references
- Maximum string lengths (prevent DoS)
- Maximum array sizes (prevent DoS)
- Observable value format matches declared type

**Sanitization Applied:**
- HTML entity encoding for text fields
- Whitespace normalization
- Unicode normalization (NFC)
- URL validation for link fields

## Testing Strategy

### Input Variation Testing

Test all accepted input formats:
```python
@pytest.mark.parametrize("date_input,expected", [
    ("2026-01-28T10:30:00Z", datetime(2026, 1, 28, 10, 30, 0)),
    ("2026-01-28 10:30:00", datetime(2026, 1, 28, 10, 30, 0)),
    (1738064400, datetime(2026, 1, 28, 10, 30, 0)),
    (None, datetime.utcnow()),  # Within 1 second tolerance
])
def test_flexible_date_parsing(date_input, expected):
    submission = Submission.from_dict({"submitted_at": date_input})
    assert submission.submitted_at == expected
```

### Output Consistency Testing

Verify output always follows strict schema:
```python
def test_output_format_consistency():
    submission = Submission.from_legacy_dict(legacy_data)
    output = json.loads(submission.to_json())

    assert "submission_id" in output
    assert re.match(r"^submission--[0-9a-f-]+$", output["submission_id"])
    assert output["submitted_at"].endswith("Z")
    assert isinstance(output["sighting"]["observables"], list)
```

### Legacy Format Testing

Ensure backward compatibility:
```python
def test_legacy_format_acceptance():
    legacy = {"sighting_id": "123", "observable_type": "IP"}
    submission = Submission.from_legacy_dict(legacy)
    assert submission.sighting.sighting_id.startswith("sighting--")
```

## Links

- Related to [ADR-0008: Explicit Error Communication](0008-explicit-error-communication.md)
- Implementation: [src/frank/core/models.py](../../src/frank/core/models.py)
- Testing: [tests/unit/core/test_models.py](../../tests/unit/core/test_models.py)
