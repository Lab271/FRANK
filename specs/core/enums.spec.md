# FRANK Core Enumerations Specification

**Domain:** Core Models / Enumerations
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06

**FRANK-Specific Metadata**:
- **Owner:** FRANK Core Team
- **Related ADRs:** [ADR-0007: Forgiving Input, Strong Output](../../docs/adr/0007-forgiving-input-strong-output.md)
- **Implementation:** [src/frank/core/enum.py](../../src/frank/core/enum.py)
- **Tests:** [tests/unit/core/test_enum.py](../../tests/unit/core/test_enum.py)

## Overview

Defines core enumeration types for FRANK's data model including access control tiers, observable types, severity levels, and TLP classifications. All enums inherit from `str` and `Enum` to provide both type safety and JSON/YAML serialization compatibility.

## ADDED Requirements

### Requirement 1: AccessTier - Access Control Hierarchy

**Description**: Five-tier access control model progressing from public (lowest) to core_member (highest privilege).

**Enum Definition**:
```python
class AccessTier(str, Enum):
    PUBLIC = "public"           # Lowest privilege - read-only anonymized data
    OBSERVER = "observer"       # Read full data, no submission rights
    CONTRIBUTOR = "contributor" # Submit and read data
    PARTNER = "partner"         # Enhanced submission rights, campaign data
    CORE_MEMBER = "core_member" # Highest privilege - full platform access
```

**Methods**:
- `can_submit() -> bool` - Returns True for CONTRIBUTOR, PARTNER, CORE_MEMBER
- `check_access_level(required_level: AccessTier) -> bool` - Hierarchical access check
- `from_string(value: str, default: bool = False) -> AccessTier` - Case-insensitive parsing with optional fallback to PUBLIC

**Acceptance Criteria**:
- ✅ Enum values serialize to lowercase strings
- ✅ `can_submit()` returns False for PUBLIC and OBSERVER
- ✅ `can_submit()` returns True for CONTRIBUTOR, PARTNER, CORE_MEMBER
- ✅ `check_access_level()` enforces hierarchical ordering (PUBLIC < OBSERVER < CONTRIBUTOR < PARTNER < CORE_MEMBER)
- ✅ `from_string()` handles case-insensitive input ("PARTNER" → AccessTier.PARTNER)
- ✅ `from_string()` handles spaces ("core member" → AccessTier.CORE_MEMBER)
- ✅ `from_string()` with `default=True` returns PUBLIC for invalid inputs
- ✅ `from_string()` with `default=False` raises ValueError for invalid inputs

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**:
- `test_tier_level_values()` - Enum values match expected strings
- `test_tier_level_can_submit()` - Submission rights by tier
- `test_check_access_level()` - Hierarchical access validation
- `test_from_string_method()` - Case-insensitive parsing
- `test_from_string_with_spaces()` - Space normalization
- `test_from_string_default_parameter()` - Fallback behavior

### Requirement 2: ObservableType - Threat Indicator Types

**Description**: Types of observable threat indicators categorized as network, file, and process observables.

**Enum Definition**:
```python
class ObservableType(str, Enum):
    # Network Observables
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    DOMAIN = "domain"
    URL = "url"
    EMAIL = "email"
    CERTIFICATE = "certificate"

    # File Observables
    FILE_HASH = "file_hash"

    # Process Observables
    REGISTRY_KEY = "registry_key"
    MUTEX = "mutex"
```

**Acceptance Criteria**:
- ✅ All values are lowercase strings
- ✅ Network observables: IPV4, IPV6, DOMAIN, URL, EMAIL, CERTIFICATE
- ✅ File observables: FILE_HASH (supports MD5, SHA1, SHA256)
- ✅ Process observables: REGISTRY_KEY, MUTEX
- ✅ Values serialize correctly in JSON/YAML
- ✅ Type-safe enum comparison in Python

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**:
- `test_observable_type_values()` - All enum values defined
- `test_observable_type_string_comparison()` - String equality
- `test_observable_type_from_string()` - String to enum conversion
- `test_observable_type_network_categories()` - Network type coverage

### Requirement 3: SeverityLevel - Threat Severity Classification

**Description**: Four-tier threat severity classification from informational to critical impact.

**Enum Definition**:
```python
class SeverityLevel(str, Enum):
    LOW = "low"           # Informational, minimal impact
    MEDIUM = "medium"     # Moderate concern, monitoring recommended
    HIGH = "high"         # Serious threat, action required
    CRITICAL = "critical" # Severe threat, immediate response
```

**Acceptance Criteria**:
- ✅ Hierarchical ordering: LOW < MEDIUM < HIGH < CRITICAL
- ✅ All values lowercase for consistency
- ✅ Used in Sighting model for threat assessment
- ✅ JSON/YAML serialization compatible

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**:
- `test_severity_level_values()` - Enum values correct
- `test_severity_level_ordering()` - Impact hierarchy validation
- `test_severity_level_from_string()` - String conversion

### Requirement 4: TLPLevel - Traffic Light Protocol

**Description**: Standard TLP classification for information sharing restrictions (CLEAR, GREEN, AMBER, AMBER+, RED).

**Enum Definition**:
```python
class TLPLevel(str, Enum):
    RED = "RED"           # Restricted to specific individuals
    AMBER_PLUS = "AMBER+" # Limited distribution, no posting
    AMBER = "AMBER"       # Limited distribution within organization
    GREEN = "GREEN"       # Community-wide sharing
    CLEAR = "CLEAR"       # Public disclosure allowed
```

**Acceptance Criteria**:
- ✅ Values match TLP 2.0 standard (uppercase)
- ✅ Used in Submission model for data classification
- ✅ Enforced at storage and API layers
- ✅ Default value: GREEN

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**:
- `test_tlp_level_values()` - Standard TLP values
- `test_tlp_level_string_comparison()` - String equality

## Non-Functional Requirements

### Performance
- **Enum Lookup**: O(1) constant time for all enum operations
- **Serialization**: Zero-copy string values (enums inherit from str)
- **Memory**: Minimal overhead, enums are singletons

### Compatibility
- **Pydantic Integration**: Full support with `use_enum_values=True` config
- **JSON Serialization**: Automatic string conversion
- **YAML Serialization**: Compatible with safe_load/safe_dump
- **Database Storage**: Store as strings (e.g., "partner", "high")

### Validation
- **Type Safety**: Mypy and IDE support via Enum type hints
- **Runtime Validation**: Pydantic validates enum values on model construction
- **Error Messages**: Clear ValueError messages for invalid inputs

## Data Model

### Enum Inheritance Pattern

All FRANK enums follow this pattern:

```python
class FrankEnum(str, Enum):
    """Base pattern for all FRANK enums"""
    VALUE = "string_value"

    # Inherits from str for:
    # - Direct string comparison
    # - JSON serialization
    # - Database storage

    # Inherits from Enum for:
    # - Type safety
    # - IDE autocomplete
    # - Iteration support
```

### Pydantic Configuration

Models using enums should set:
```python
class Model(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True,  # Serialize to string values
        extra="ignore"          # Be forgiving on input
    )

    access_level: AccessTier
```

### Serialization Behavior

**Input (Forgiving)**:
- Accept enum objects: `AccessTier.PARTNER`
- Accept string values: `"partner"`
- Case-insensitive via `from_string()`: `"PARTNER"` → `AccessTier.PARTNER`

**Output (Strong)**:
- Always lowercase strings: `"partner"`
- Consistent ordering in JSON/YAML
- No enum representation leakage to API consumers

## Validation Rules

### AccessTier Validation
1. **Submission Rights**: Only CONTRIBUTOR+ can submit data
2. **Access Hierarchy**: Each tier can access data at its level and below
3. **String Conversion**: `from_string()` normalizes case and spaces
4. **Default Fallback**: Invalid values can default to PUBLIC if `default=True`

### ObservableType Validation
1. **Categorization**: Types grouped as network/file/process
2. **Value Normalization**: Observable values normalized per type (e.g., domains lowercased)
3. **STIX ID Generation**: ID prefix matches observable type (`ipv4--uuid`)

### SeverityLevel Validation
1. **Optional Field**: Can be None in Sighting model
2. **Impact Ordering**: LOW < MEDIUM < HIGH < CRITICAL
3. **Default Behavior**: No default value, must be explicitly set

### TLPLevel Validation
1. **Case Preservation**: TLP values remain uppercase (standard compliance)
2. **Default Value**: GREEN for most submissions
3. **API Enforcement**: Checked at submission and retrieval

## Test Coverage Requirements

**Minimum Coverage**: ≥85% (enforced by CI/CD)

**Test Categories**:
1. **Value Tests** - All enum values defined correctly
2. **Serialization Tests** - JSON/YAML round-trip consistency
3. **Validation Tests** - Invalid value handling
4. **Method Tests** - AccessTier methods (`can_submit`, `check_access_level`, `from_string`)
5. **Integration Tests** - Pydantic model integration with enums

**Key Test Files**:
- [tests/unit/core/test_enum.py](../../tests/unit/core/test_enum.py) - 933 lines, comprehensive coverage

## Evolution Path Across FRANK Stages

### Stage 1 (SQLite)
- ✅ All enums fully implemented
- ✅ Stored as strings in SQLite TEXT columns
- ✅ Simple access control via tier comparison

### Stage 2 (DynamoDB + MySQL)
- ✅ Enums unchanged, same string storage
- ✅ DynamoDB stores as strings in attributes
- ✅ MySQL uses VARCHAR for enum storage

### Stage 3 (AWS ECS)
- ✅ Enums unchanged, cloud deployment
- ✅ AWS Cognito groups mapped to AccessTier values
- ✅ DynamoDB continues string storage

### Stage 4 (Kubernetes + ScyllaDB)
- ✅ Enums unchanged, production scale
- ✅ ScyllaDB TEXT columns for enum storage
- ✅ Potential for enum tables for referential integrity (future optimization)

## Usage Examples

### Basic Enum Usage

```python
from frank.core.enum import AccessTier, ObservableType, SeverityLevel

# Direct enum usage
tier = AccessTier.PARTNER
print(tier.value)  # "partner"
print(tier.can_submit())  # True

# String comparison
if tier == "partner":  # Works due to str inheritance
    print("Partner tier detected")

# Access level check
if tier.check_access_level(AccessTier.CONTRIBUTOR):
    print("Has contributor access or higher")
```

### AccessTier.from_string()

```python
# Case-insensitive parsing
tier1 = AccessTier.from_string("CORE_MEMBER")  # AccessTier.CORE_MEMBER
tier2 = AccessTier.from_string("Partner")      # AccessTier.PARTNER
tier3 = AccessTier.from_string("core member")  # AccessTier.CORE_MEMBER (space → underscore)

# With default fallback
tier_safe = AccessTier.from_string("invalid", default=True)  # AccessTier.PUBLIC
# Without fallback (raises ValueError)
try:
    tier_strict = AccessTier.from_string("invalid", default=False)
except ValueError as e:
    print(f"Invalid tier: {e}")
```

### Pydantic Model Integration

```python
from pydantic import BaseModel, ConfigDict
from frank.core.enum import AccessTier, SeverityLevel

class Submission(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    access_level: AccessTier
    severity: SeverityLevel

# Create from strings (forgiving input)
sub = Submission(access_level="partner", severity="high")

# Serialize to dict (strong output)
data = sub.model_dump()
print(data)  # {"access_level": "partner", "severity": "high"}

# JSON serialization
json_str = sub.model_dump_json()
print(json_str)  # '{"access_level":"partner","severity":"high"}'
```

### Observable Type Usage

```python
from frank.core.enum import ObservableType
from frank.core.models import Observable

# Factory methods use enums internally
ipv4_obs = Observable.create_ipv4("192.168.1.1")
print(ipv4_obs.observable_type)  # ObservableType.IPV4
print(ipv4_obs.id)  # "ipv4--<uuid>"

# Direct enum usage
domain_obs = Observable(
    observable_type=ObservableType.DOMAIN,
    value="malicious.com"
)
```

## Implementation Status

- [x] Design complete
- [x] All enums implemented
- [x] AccessTier methods implemented (`can_submit`, `check_access_level`, `from_string`)
- [x] Tests written (≥85% coverage)
- [x] Code review passed
- [x] Merged to main

**PR Links**:
- Initial implementation: Merged in baseline
- `from_string()` method: Part of core implementation
- Comprehensive tests: [tests/unit/core/test_enum.py](../../tests/unit/core/test_enum.py)

## References

- **ADR-0007**: [Forgiving Input, Strong Output](../../docs/adr/0007-forgiving-input-strong-output.md) - Enum serialization philosophy
- **Pydantic V2 Docs**: [Enums in Pydantic](https://docs.pydantic.dev/latest/concepts/types/#enums)
- **TLP Standard**: [Traffic Light Protocol 2.0](https://www.first.org/tlp/)
- **STIX 2.1**: [Observable types mapping](https://docs.oasis-open.org/cti/stix/v2.1/)
