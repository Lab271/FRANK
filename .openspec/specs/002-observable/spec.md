# Observable Specification

**Domain:** Threat Intelligence / Core Data Models
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06
**Owner:** FRANK Core Team

**Related ADRs:** [ADR-0007: Forgiving Input, Strong Output](.openspec/architecture/decisions/008-forgiving-input-strong-output.md)
**Implementation:** [src/frank/core/models.py#L29-L86](src/frank/core/models.py)
**Tests:** [tests/unit/core/test_observable.py](tests/unit/core/test_observable.py)

## Overview

Defines the Observable model representing individual threat indicators (IPs, domains, URLs, hashes, etc.) with STIX-compliant IDs, automatic normalization, and comprehensive validation. Observable is the atomic unit of threat intelligence in FRANK.

### Philosophy

- **STIX 2.1 Compliance**: Use STIX-compliant ID format (`{type}--{uuid}`) for interoperability
- **Automatic Normalization**: Values automatically normalized (lowercase, trimmed) per type
- **Be Forgiving on Input**: Accept diverse input formats, validate thoroughly, emit standardized data
- **Type Safety**: Strong typing with ObservableType enum prevents invalid indicator types

### Key Capabilities

- **Nine Observable Types**: Network (6), File (1), Process (2) threat indicators
- **Automatic ID Generation**: STIX-compliant IDs with type-specific prefixes
- **Value Normalization**: Type-specific normalization (lowercase, trim, case preservation for URLs)
- **Factory Methods**: Convenient constructors (create_ipv4, create_domain, create_url, etc.)
- **Validation**: Port ranges, hash formats, email patterns

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Usage in this specification**:
- **MUST/SHALL**: ID format, value normalization, type validation
- **SHOULD**: Factory method usage for consistency
- **MAY**: Optional metadata fields (role, port, protocol)

---

## Requirements

### Requirement 1: Core Observable Structure

**Description**: The system MUST provide a Pydantic v2 model with automatic ID generation, value normalization, and STIX compliance.

#### Scenario: Create Valid Observable
- GIVEN a valid observable type and value
- WHEN creating an observable instance
- THEN it SHALL have an auto-generated STIX ID in format `{type}--{uuid}`
- AND the value SHALL be normalized according to type rules

**Pydantic Schema**:
```python
class Observable(BaseModel):
    model_config = ConfigDict(
        extra="ignore",           # Ignore unknown fields (be forgiving)
        use_enum_values=True,     # Serialize enums to strings
        populate_by_name=True,    # Allow both field name and alias
    )

    id: Optional[str] = Field(None, description="STIX-formatted observable ID")
    observable_type: ObservableType = Field(..., alias="type", description="Type of network observable")
    value: str = Field(..., min_length=1, description="Observable value")

    # Optional metadata
    role: Optional[str] = Field(None, description="Role in attack (C2, exfiltration, etc)")
    port: Optional[int] = Field(None, ge=1, le=65535, description="Network port")
    protocol: Optional[str] = Field(None, description="Network protocol")
    first_seen: Optional[datetime] = Field(None, description="First observation time")
    connection_count: Optional[int] = Field(None, ge=0, description="Number of connections")
```

**Acceptance Criteria**:
- ✅ `id` auto-generated if not provided in format `{type}--{uuid}`
- ✅ `observable_type` accepts both field name and alias (`type`)
- ✅ `value` required, min 1 character
- ✅ `port` validated 1-65535 range
- ✅ `connection_count` must be non-negative
- ✅ Extra fields ignored (forgiving on input)
- ✅ Datetime fields serialize to ISO format

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_create_ipv4_observable_minimal](tests/unit/core/test_observable.py#L27-L38), [test_create_ipv4_observable_full](tests/unit/core/test_observable.py#L39-L59)

### Requirement 2: Observable Types

**Description**: The system MUST support nine observable types categorized as network, file, or process indicators.

**Observable Types**:

| Type | Category | Example | Normalization |
|------|----------|---------|---------------|
| IPV4 | Network | `192.168.1.1` | Lowercase, trimmed |
| IPV6 | Network | `2001:db8::1` | Lowercase, trimmed |
| DOMAIN | Network | `malicious.com` | Lowercase, trimmed |
| URL | Network | `https://evil.com/payload.exe` | Trimmed (case preserved) |
| EMAIL | Network | `attacker@evil.com` | Lowercase, trimmed |
| CERTIFICATE | Network | `40:6B:8B:CD:...` | Lowercase, trimmed |
| FILE_HASH | File | `5d41402abc4b2a76b9719d911017c592` | Lowercase, trimmed |
| REGISTRY_KEY | Process | `HKEY_LOCAL_MACHINE\...` | Lowercase, trimmed |
| MUTEX | Process | `Global\MalwareMutex` | Lowercase, trimmed |

**Acceptance Criteria**:
- ✅ All types defined in ObservableType enum
- ✅ ID prefix matches observable type
- ✅ Value normalization applied per type
- ✅ URLs preserve case (paths can be case-sensitive)
- ✅ Other types converted to lowercase

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_create_ipv6_observable](tests/unit/core/test_observable.py#L60-L69), [test_create_domain_observable](tests/unit/core/test_observable.py#L71-L82), [test_create_url_observable](tests/unit/core/test_observable.py#L84-L93)

#### Scenario: Create Observable with Specific Type
- GIVEN an observable type from the supported list
- WHEN creating an observable with that type
- THEN the STIX ID prefix SHALL match the observable type
- AND value normalization SHALL be applied according to type rules

### Requirement 3: STIX ID Generation

**Description**: The system MUST auto-generate STIX 2.1 compliant IDs if not provided.

**ID Format**: `{observable_type}--{uuid4}`

**Examples**:
- `ipv4--550e8400-e29b-41d4-a716-446655440000`
- `domain--8a7f9e23-1b42-4c8d-9f3a-2e5d7c6b4a1f`
- `file_hash--c3ab8ff13720e8ad9047dd39466b3c89`

**Generation Logic**:
```python
@model_validator(mode="after")
def ensure_id_generated(self):
    """Ensure ID is always generated after all fields are set"""
    if not self.id:
        type_val = self.observable_type if isinstance(self.observable_type, str) else self.observable_type.value
        self.id = f"{type_val}--{uuid.uuid4()}"
    return self
```

**Acceptance Criteria**:
- ✅ ID generated if None or empty string
- ✅ Existing IDs preserved (not overwritten)
- ✅ UUID format validated (36 characters, standard UUID4)
- ✅ Type prefix matches observable_type value
- ✅ Multiple observables get unique IDs

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_stix_id_generation](tests/unit/core/test_observable.py#L106-L123)

#### Scenario: Auto-Generate STIX ID
- GIVEN an observable created without an ID
- WHEN the observable is instantiated
- THEN a STIX ID SHALL be auto-generated in format `{type}--{uuid4}`
- AND subsequent observables SHALL receive unique IDs

### Requirement 4: Value Normalization

**Description**: The system MUST normalize observable values based on type for consistent storage and comparison.

**Normalization Rules**:

1. **DOMAIN**: `value.strip().lower()`
   - `"  EXAMPLE.COM  "` → `"example.com"`

2. **IPV4/IPV6**: `value.strip().lower()`
   - `"  192.168.1.1  "` → `"192.168.1.1"`

3. **URL**: `value.strip()` (preserve case)
   - `"  https://Example.com/Path  "` → `"https://Example.com/Path"`

4. **EMAIL, FILE_HASH, CERTIFICATE, REGISTRY_KEY, MUTEX**: `value.strip().lower()`

**Implementation**:
```python
@model_validator(mode="after")
def normalize_values(self):
    """Normalize values based on type after all fields are processed."""
    if self.observable_type == ObservableType.DOMAIN:
        self.value = self.value.strip().lower()
    elif self.observable_type in [ObservableType.IPV4, ObservableType.IPV6]:
        self.value = self.value.strip().lower()
    elif self.observable_type == ObservableType.URL:
        self.value = self.value.strip()  # Preserve case for URLs
    else:
        self.value = self.value.strip().lower()
    return self
```

**Acceptance Criteria**:
- ✅ Whitespace stripped from all values
- ✅ Domains converted to lowercase
- ✅ URLs preserve case sensitivity
- ✅ IPs normalized to lowercase (IPv6 hex)
- ✅ Normalization idempotent (repeated calls produce same result)

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_whitespace_trimming](tests/unit/core/test_observable.py#L511-L518), [test_case_normalization_domains](tests/unit/core/test_observable.py#L520-L527), [test_url_case_preservation](tests/unit/core/test_observable.py#L538-L546)

#### Scenario: Normalize Domain Value
- GIVEN a domain with mixed case and whitespace "  EXAMPLE.COM  "
- WHEN creating a domain observable
- THEN the value SHALL be normalized to "example.com"
- AND whitespace SHALL be trimmed

#### Scenario: Preserve URL Case
- GIVEN a URL "  https://Example.com/Path  "
- WHEN creating a URL observable
- THEN the value SHALL be "https://Example.com/Path"
- AND case SHALL be preserved for path sensitivity

### Requirement 5: Factory Methods

**Description**: The system SHOULD provide convenience constructors for common observable types.

**Factory Methods**:

1. **create_ipv4(value, role=None, port=None)**
   ```python
   ipv4_obs = Observable.create_ipv4("192.168.1.1", role="c2", port=443)
   ```

2. **create_domain(value, role=None)**
   ```python
   domain_obs = Observable.create_domain("malicious.com", role="phishing")
   ```

**Acceptance Criteria**:
- ✅ Factory methods set observable_type automatically
- ✅ Optional parameters (role, port) passed through
- ✅ ID generation triggered automatically
- ✅ Return fully validated Observable instance

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_create_ipv4_factory_with_role_and_port](tests/unit/core/test_observable.py#L569-L580), [test_create_domain_factory_with_role](tests/unit/core/test_observable.py#L582-L591)

#### Scenario: Use IPv4 Factory Method
- GIVEN a valid IPv4 address "192.168.1.1" with role "c2" and port 443
- WHEN using Observable.create_ipv4() factory method
- THEN a valid observable SHALL be created with type "ipv4"
- AND the role and port SHALL be set correctly

## Non-Functional Requirements

### Performance
- **Creation Time**: < 1ms per observable
- **Normalization**: O(n) where n = value length
- **ID Generation**: O(1) UUID generation

**Test**: [test_bulk_creation_performance](tests/unit/core/test_observable.py#L647-L672) - 100 observables < 1 second

### Validation
- **Port Range**: 1-65535 (standard TCP/UDP range)
- **Connection Count**: ≥ 0 (non-negative integer)
- **Value**: Non-empty string (min_length=1)
- **Datetime**: Timezone-aware or naive (handled by validator)

### Serialization
- **Datetime Format**: ISO 8601 with timezone
- **Enum Serialization**: String values (`"ipv4"` not `ObservableType.IPV4`)
- **Field Aliases**: Support both `type` and `observable_type`
- **Extra Fields**: Ignored (ConfigDict `extra="ignore"`)

## Data Model

### Complete Schema

```python
{
    "id": "ipv4--550e8400-e29b-41d4-a716-446655440000",  # Auto-generated STIX ID
    "type": "ipv4",                                      # Alias for observable_type
    "value": "203.0.113.42",                             # Required, normalized

    # Optional metadata
    "role": "c2",                                        # Attack role
    "port": 443,                                         # Network port (1-65535)
    "protocol": "tcp",                                   # Network protocol
    "first_seen": "2025-01-15T10:30:00+00:00",          # ISO datetime
    "connection_count": 15                               # Non-negative integer
}
```

### Observables Container

Observables are grouped by category in the `Observables` container:

```python
class Observables(BaseModel):
    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    network: Optional[List[Observable]] = Field(default_factory=list, description="Network observables")
    file: Optional[List[Observable]] = Field(default_factory=list, description="File observables")
    process: Optional[List[Observable]] = Field(default_factory=list, description="Process observables")
```

**Example**:
```python
observables = Observables(
    network=[
        Observable.create_ipv4("192.168.1.1", role="c2"),
        Observable.create_domain("evil.com", role="phishing")
    ],
    file=[
        Observable(observable_type=ObservableType.FILE_HASH, value="5d41402abc4b2a76b9719d911017c592")
    ],
    process=[
        Observable(observable_type=ObservableType.MUTEX, value="Global\\MalwareMutex")
    ]
)
```

## Validation Rules

### Field Validation

1. **id** (Optional[str])
   - Generated if None or empty string
   - Format: `{type}--{uuid4}`
   - Preserved if provided

2. **observable_type** (ObservableType) - REQUIRED
   - Must be valid ObservableType enum value
   - Accepts enum or string value
   - Alias: `type` (for API compatibility)

3. **value** (str) - REQUIRED
   - Minimum length: 1 character
   - Normalized based on observable_type
   - Whitespace trimmed

4. **port** (Optional[int])
   - Range: 1-65535 (inclusive)
   - ValidationError if out of range

5. **connection_count** (Optional[int])
   - Minimum: 0 (non-negative)
   - ValidationError if negative

6. **first_seen** (Optional[datetime])
   - Accepts datetime objects or ISO strings
   - Serialized as ISO 8601 with timezone

### Model Validators

**ensure_id_generated** (mode="after")
- Runs after all fields set
- Generates ID if missing
- Uses observable_type value for prefix

**normalize_values** (mode="after")
- Runs after ID generation
- Applies type-specific normalization
- Modifies `value` field in-place

### Serialization Rules

**Datetime Serialization**:
```python
@field_serializer("first_seen", when_used="always")
def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
    """Always serialize datetime as ISO string"""
    if value is None:
        return None
    return value.isoformat()
```

**Output Modes**:
- `model_dump()` - Dictionary with all fields
- `model_dump(exclude_none=True)` - Exclude None values
- `model_dump(by_alias=True)` - Use field aliases (`type` instead of `observable_type`)
- `model_dump_json()` - JSON string with automatic datetime serialization

## Test Coverage Requirements

**Minimum Coverage**: ≥85% (enforced by CI/CD)

**Test Categories**:
1. **Creation Tests** - All observable types (IPV4, IPV6, DOMAIN, URL, EMAIL, FILE_HASH, etc.)
2. **Validation Tests** - Field constraints (port range, connection count, value length)
3. **Normalization Tests** - Whitespace, case sensitivity, URL preservation
4. **Serialization Tests** - JSON/YAML round-trips, datetime handling
5. **Factory Method Tests** - create_ipv4(), create_domain()
6. **STIX ID Tests** - Auto-generation, uniqueness, format validation

**Test Files**:
- [tests/unit/core/test_observable.py](tests/unit/core/test_observable.py) - 605 lines, comprehensive coverage

**Key Test Classes**:
- `TestObservableValidation` - Basic observable creation and validation
- `TestObservableSerialization` - JSON/YAML/dict serialization
- `TestObservableBeForgivingPrinciple` - "Be forgiving" input handling
- `TestObservableFactoryMethods` - Factory method functionality

## Implementation Status

- [x] Design complete
- [x] Pydantic model implemented
- [x] STIX ID generation implemented
- [x] Value normalization implemented
- [x] Factory methods implemented
- [x] Serialization implemented
- [x] Tests written (≥85% coverage)
- [x] Code review passed
- [x] Merged to main

**PR Links**:
- Initial Observable model: Merged in baseline
- Pydantic v2 migration: Part of core refactoring
- Comprehensive tests: [tests/unit/core/test_observable.py](tests/unit/core/test_observable.py)

## Evolution Path Across FRANK Stages

### Stage 1 (SQLite)
- ✅ Full Observable implementation
- ✅ Stored as JSON in SQLite TEXT columns
- ✅ STIX IDs indexed for fast lookup
- ✅ Normalization ensures consistent queries

### Stage 2 (DynamoDB + MySQL)
- ✅ Observable unchanged, same model
- ✅ DynamoDB stores observables in LIST attribute
- ✅ Observables denormalized into submission documents
- ✅ GSI on observable values for fast queries

### Stage 3 (AWS ECS)
- ✅ Observable unchanged, cloud deployment
- ✅ DynamoDB continues JSON storage
- ✅ CloudWatch metrics on observable types
- ✅ Large observable lists handled efficiently

### Stage 4 (Kubernetes + ScyllaDB)
- ✅ Observable unchanged, production scale
- ✅ ScyllaDB stores observables in frozen collections
- ✅ Potential for separate observables table (many-to-many)
- ✅ Materialized views for observable searches

## Usage Examples

### Basic Observable Creation

```python
from frank.core.models import Observable
from frank.core.enum import ObservableType

# Minimal observable
obs1 = Observable(
    observable_type=ObservableType.IPV4,
    value="192.168.1.1"
)

# With metadata
obs2 = Observable(
    observable_type=ObservableType.DOMAIN,
    value="malicious.com",
    role="phishing",
    first_seen=datetime.now(timezone.utc)
)

# Using alias
obs3 = Observable(type="url", value="https://evil.com/payload.exe")
```

### Factory Methods

```python
# IPv4 observable
ipv4_obs = Observable.create_ipv4("203.0.113.42", role="c2", port=443)

# Domain observable
domain_obs = Observable.create_domain("evil.com", role="phishing")
```

### Normalization Examples

```python
# Domain normalization (lowercase)
obs1 = Observable(type="domain", value="  MALICIOUS.COM  ")
print(obs1.value)  # "malicious.com"

# URL case preservation
obs2 = Observable(type="url", value="  https://Example.com/Path  ")
print(obs2.value)  # "https://Example.com/Path" (case preserved)

# IPv6 normalization
obs3 = Observable(type="ipv6", value="  2001:DB8::1  ")
print(obs3.value)  # "2001:db8::1"
```

### Serialization

```python
obs = Observable.create_ipv4("192.168.1.1", role="c2", port=443)

# Dictionary (field names)
data1 = obs.model_dump()
print(data1["observable_type"])  # "ipv4"

# Dictionary (aliases)
data2 = obs.model_dump(by_alias=True)
print(data2["type"])  # "ipv4"

# JSON string
json_str = obs.model_dump_json(by_alias=True, exclude_none=True)

# Exclude None values
data3 = obs.model_dump(exclude_none=True)
# Only includes non-None fields
```

### Observables Container

```python
from frank.core.models import Observables

# Group observables by category
observables = Observables(
    network=[
        Observable.create_ipv4("192.168.1.1", role="c2"),
        Observable.create_domain("evil.com", role="phishing"),
    ],
    file=[
        Observable(type="file_hash", value="5d41402abc4b2a76b9719d911017c592")
    ]
)

# Access by category
for network_obs in observables.network:
    print(f"{network_obs.observable_type}: {network_obs.value}")

# Serialize to dict
data = observables.model_dump(by_alias=True, exclude_none=True)
```

## References

- **ADR-0007**: [Forgiving Input, Strong Output](.openspec/architecture/decisions/008-forgiving-input-strong-output.md)
- **STIX 2.1**: [Cyber Observable Objects](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html#_mlbmudhl16lr)
- **Pydantic V2**: [Model Validators](https://docs.pydantic.dev/latest/concepts/validators/)
- **Implementation**: [src/frank/core/models.py](src/frank/core/models.py)
- **Tests**: [tests/unit/core/test_observable.py](tests/unit/core/test_observable.py)
