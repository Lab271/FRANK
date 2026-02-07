# Submitter & HitTarget Specification

**Domain:** Core Models / Organization Identity
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06

**FRANK-Specific Metadata**:
- **Owner:** FRANK Core Team
- **Related ADRs:** [ADR-0007: Forgiving Input, Strong Output](../../docs/adr/0007-forgiving-input-strong-output.md)
- **Implementation:** [src/frank/core/models.py#L89-L203](../../src/frank/core/models.py)
- **Tests:** [tests/unit/core/test_submitter.py](../../tests/unit/core/test_submitter.py), [tests/unit/core/test_hittarget.py](../../tests/unit/core/test_hittarget.py)

## Overview

Defines Submitter (threat intelligence contributor) and HitTarget (affected organization) models with STIX-compliant organization identities, access tier assignment, privacy controls, and sector normalization. These models enable attribution, access control, and anonymization in the FRANK platform.

## ADDED Requirements

### Requirement 1: Submitter Model

**Description**: Represents the organization submitting threat intelligence with access tier and metadata.

**Pydantic Schema**:
```python
class Submitter(BaseModel):
    model_config = ConfigDict(
        extra="ignore",           # Ignore unknown fields (be forgiving)
        use_enum_values=True,     # Serialize enums to strings
    )

    organisation_id: Optional[str] = Field(None, description="STIX identity for organisation")
    access_level: AccessTier = Field(..., description="Access tier level")
    organisation_type: str = Field(default="cyber_partner", description="organisation type")

    # Optional metadata
    sector: Optional[str] = Field(None, description="Industry sector")
    region: Optional[str] = Field(None, description="Geographic region")
    client_count: Optional[int] = Field(None, ge=0, description="Number of protected clients")
```

**Acceptance Criteria**:
- ✅ `organisation_id` auto-generated as `identity--{uuid}` if not provided
- ✅ `access_level` required (AccessTier enum)
- ✅ `organisation_type` defaults to "cyber_partner"
- ✅ `sector` normalized (e.g., "finance" → "financial", "healthcare" → "health")
- ✅ `client_count` non-negative
- ✅ Extra fields ignored (forgiving on input)

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_create_minimal_submitter](../../tests/unit/core/test_submitter.py#L36-L47), [test_create_submitter_with_all_fields](../../tests/unit/core/test_submitter.py#L49-L66)

### Requirement 2: HitTarget Model

**Description**: Represents the organization affected by threat activity with privacy controls.

**Pydantic Schema**:
```python
class HitTarget(BaseModel):
    model_config = ConfigDict(
        extra="ignore",           # Ignore unknown fields (be forgiving)
        use_enum_values=True,     # Serialize enums to strings
    )

    organisation_id: Optional[str] = Field(None, description="STIX identity for affected organisation")
    sector: str = Field(..., min_length=1, description="Industry sector of target")

    # Optional metadata
    organisation_type: Optional[str] = Field(default="customer", description="organisation type")
    organisation_size: Optional[str] = Field(None, description="organisation size category")
    region: Optional[str] = Field(None, description="Geographic region")
    anonymization_level: Optional[str] = Field(default="high", description="Data anonymization level")
```

**Acceptance Criteria**:
- ✅ `organisation_id` auto-generated as `identity--{uuid}` if not provided
- ✅ `sector` required (min 1 character)
- ✅ `organisation_type` defaults to "customer"
- ✅ `anonymization_level` defaults to "high"
- ✅ `organisation_size` normalized (e.g., "sme" → "small", "enterprise" → "large")
- ✅ Extra fields ignored (forgiving on input)

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_create_minimal_hittarget](../../tests/unit/core/test_hittarget.py#L33-L49), [test_create_hittarget_with_all_fields](../../tests/unit/core/test_hittarget.py#L51-L68)

### Requirement 3: STIX Organization ID Generation

**Description**: Auto-generate STIX 2.1 compliant organization identities if not provided.

**ID Format**: `identity--{uuid4}`

**Example**: `identity--550e8400-e29b-41d4-a716-446655440000`

**Generation Logic (Submitter)**:
```python
@model_validator(mode="after")
def ensure_org_id(self):
    """Ensure organisation ID is always set"""
    if not self.organisation_id:
        self.organisation_id = f"identity--{uuid.uuid4()}"
    return self
```

**Generation Logic (HitTarget)**:
```python
@field_validator("organisation_id", mode="before")
@classmethod
def generate_org_id(cls, v):
    """Generate target identity if not provided"""
    if v is None or v == "":
        return f"identity--{uuid.uuid4()}"
    return v

@model_validator(mode="after")
def ensure_org_id(self):
    """Ensure organisation ID is always set"""
    if not self.organisation_id:
        self.organisation_id = f"identity--{uuid.uuid4()}"
    return self
```

**Acceptance Criteria**:
- ✅ ID generated if None or empty string
- ✅ Existing IDs preserved (not overwritten)
- ✅ UUID format validated (36 characters, standard UUID4)
- ✅ Prefix is `identity--`
- ✅ Multiple instances get unique IDs
- ✅ Submitter and HitTarget IDs never collide

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_organisation_id_auto_generation (Submitter)](../../tests/unit/core/test_submitter.py#L68-L81), [test_organisation_id_auto_generation (HitTarget)](../../tests/unit/core/test_hittarget.py#L70-L88)

### Requirement 4: Sector Normalization (Submitter)

**Description**: Normalize sector names for consistency using forgiving mapping.

**Normalization Mapping**:
```python
sector_mappings = {
    "finance": "financial",
    "banking": "financial",
    "healthcare": "health",
    "medical": "health",
    "government": "public_sector",
    "gov": "public_sector",
    "tech": "technology",
    "it": "technology",
}
```

**Normalization Logic**:
```python
@field_validator("sector")
@classmethod
def normalize_sector(cls, v):
    """Normalize sector names - 'be forgiving' on input"""
    if v is None:
        return v

    sector_mappings = { ... }  # Mapping defined above

    normalized = v.lower().strip()
    return sector_mappings.get(normalized, normalized)
```

**Acceptance Criteria**:
- ✅ Case-insensitive ("FINANCE" → "financial")
- ✅ Whitespace trimmed ("  banking  " → "financial")
- ✅ Common aliases mapped ("healthcare" → "health")
- ✅ Unknown sectors preserved as-is (lowercased)
- ✅ None values preserved

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_sector_normalization](../../tests/unit/core/test_submitter.py#L83-L107)

### Requirement 5: Organisation Size Normalization (HitTarget)

**Description**: Normalize organization size categories for consistency.

**Size Mapping**:
```python
size_mappings = {
    "small": "small",
    "sme": "small",
    "startup": "small",
    "medium": "medium",
    "mid": "medium",
    "large": "large",
    "enterprise": "large",
    "multinational": "large",
}
```

**Normalization Logic**:
```python
@field_validator("organisation_size")
@classmethod
def normalize_org_size(cls, v):
    """Normalize organisation size categories"""
    if v is None:
        return v

    size_mappings = { ... }  # Mapping defined above

    normalized = v.lower().strip()
    return size_mappings.get(normalized, v)
```

**Acceptance Criteria**:
- ✅ Case-insensitive ("SME" → "small")
- ✅ Whitespace trimmed
- ✅ Common aliases mapped ("enterprise" → "large")
- ✅ Unknown sizes preserved as-is
- ✅ None values preserved

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_organisation_size_normalization](../../tests/unit/core/test_hittarget.py#L109-L133)

### Requirement 6: Factory Methods

**Description**: Convenience constructors for creating submitters and targets.

**Submitter Factory**:
```python
@classmethod
def create(cls, access_level: AccessTier, sector: str = None, region: str = None):
    """Factory method for creating submitters"""
    return cls(access_level=access_level, sector=sector, region=region)
```

**HitTarget Factory**:
```python
@classmethod
def create(cls, sector: str, organisation_size: str = None, region: str = None):
    """Factory method for creating hit targets"""
    return cls(sector=sector, organisation_size=organisation_size, region=region)
```

**Acceptance Criteria**:
- ✅ Factory methods set required fields
- ✅ Optional parameters passed through
- ✅ ID generation triggered automatically
- ✅ Return fully validated instances

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_factory_method_create (Submitter)](../../tests/unit/core/test_submitter.py#L152-L162), [test_factory_method_create (HitTarget)](../../tests/unit/core/test_hittarget.py#L164-L172)

### Requirement 7: Anonymization Levels (HitTarget)

**Description**: Privacy control for affected organization data.

**Anonymization Levels**:
- **high** (default): Minimal information shared, maximum privacy
- **medium**: Moderate information sharing
- **low**: Full organizational details shared

**Usage**: Affects how much identifying information is included in threat intelligence sharing.

**Acceptance Criteria**:
- ✅ Default value: "high"
- ✅ Optional field (can be None)
- ✅ Used by storage/API layers for filtering

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: Tested as part of HitTarget creation tests

## Non-Functional Requirements

### Performance
- **Creation Time**: < 1ms per instance
- **Normalization**: O(n) where n = string length
- **ID Generation**: O(1) UUID generation

### Validation
- **Access Level**: Valid AccessTier enum
- **Sector**: Non-empty for HitTarget (min_length=1)
- **Client Count**: Non-negative integer (≥ 0)
- **Organization ID**: STIX format `identity--{uuid}`

### Serialization
- **Enum Serialization**: String values (`"partner"` not `AccessTier.PARTNER`)
- **Field Exclusion**: `exclude_none=True` removes None values
- **Extra Fields**: Ignored (ConfigDict `extra="ignore"`)

## Data Model

### Complete Submitter Schema

```json
{
    "organisation_id": "identity--550e8400-e29b-41d4-a716-446655440000",
    "access_level": "partner",
    "organisation_type": "mssp",
    "sector": "financial",
    "region": "europe",
    "client_count": 150
}
```

### Complete HitTarget Schema

```json
{
    "organisation_id": "identity--8a7f9e23-1b42-4c8d-9f3a-2e5d7c6b4a1f",
    "sector": "healthcare",
    "organisation_type": "hospital",
    "organisation_size": "large",
    "region": "north_america",
    "anonymization_level": "high"
}
```

### Relationship to Submission

Submitter and HitTarget are embedded in Submission:
```python
class Submission(BaseModel):
    submitter: Optional[Submitter] = Field(None, description="Submitting organisation")
    hit_target: Optional[HitTarget] = Field(None, description="Affected organisation")
    # ... other fields
```

**Validation**: Submitter and HitTarget must have different `organisation_id` values (enforced by Submission model validator).

## Validation Rules

### Submitter Field Validation

1. **organisation_id** (Optional[str])
   - Generated if None or empty: `identity--{uuid4}`
   - Preserved if provided

2. **access_level** (AccessTier) - REQUIRED
   - Must be valid AccessTier enum value
   - Determines submission rights and data access

3. **organisation_type** (str)
   - Default: "cyber_partner"
   - Free-form string (e.g., "mssp", "soc", "cert")

4. **sector** (Optional[str])
   - Normalized via sector_mappings
   - Lowercase, trimmed

5. **region** (Optional[str])
   - Free-form string (e.g., "europe", "north_america")

6. **client_count** (Optional[int])
   - Must be non-negative (≥ 0)
   - ValidationError if negative

### HitTarget Field Validation

1. **organisation_id** (Optional[str])
   - Generated if None or empty: `identity--{uuid4}`
   - Dual validators (field + model)

2. **sector** (str) - REQUIRED
   - Minimum length: 1 character
   - Free-form string

3. **organisation_type** (Optional[str])
   - Default: "customer"
   - Free-form string

4. **organisation_size** (Optional[str])
   - Normalized via size_mappings
   - Values: "small", "medium", "large" (after normalization)

5. **region** (Optional[str])
   - Free-form string

6. **anonymization_level** (Optional[str])
   - Default: "high"
   - Values: "high", "medium", "low"

### Submission-Level Validation

Enforced by Submission model:
```python
@model_validator(mode="after")
def validate_submission_integrity(self):
    """Cross-field validation for submission integrity"""
    if not self.hit_target:
        return self

    submitter_id = self.submitter.organisation_id
    target_id = self.hit_target.organisation_id

    if submitter_id and target_id and submitter_id == target_id:
        raise ValueError("Submitter and hit_target cannot be the same organisation")

    return self
```

## Test Coverage Requirements

**Minimum Coverage**: ≥85% (enforced by CI/CD)

**Test Categories**:
1. **Creation Tests** - Minimal, full fields
2. **ID Generation Tests** - Auto-generation, uniqueness
3. **Normalization Tests** - Sector, organization size
4. **Validation Tests** - Field constraints, access level
5. **Factory Tests** - create() methods
6. **Serialization Tests** - JSON/YAML round-trips
7. **Integration Tests** - Submission validation

**Test Files**:
- [tests/unit/core/test_submitter.py](../../tests/unit/core/test_submitter.py) - Submitter tests
- [tests/unit/core/test_hittarget.py](../../tests/unit/core/test_hittarget.py) - HitTarget tests
- [tests/unit/core/test_submission.py](../../tests/unit/core/test_submission.py) - Integration tests

## Implementation Status

- [x] Design complete
- [x] Submitter model implemented
- [x] HitTarget model implemented
- [x] Organization ID generation implemented
- [x] Sector normalization implemented
- [x] Size normalization implemented
- [x] Factory methods implemented
- [x] Submission validation implemented
- [x] Tests written (≥85% coverage)
- [x] Code review passed
- [x] Merged to main

**PR Links**:
- Initial Submitter/HitTarget models: Merged in baseline
- Pydantic v2 migration: Part of core refactoring
- Comprehensive tests: Submitter, HitTarget test files

## Evolution Path Across FRANK Stages

### Stage 1 (SQLite)
- ✅ Full Submitter/HitTarget implementation
- ✅ Stored as JSON in SQLite TEXT columns
- ✅ Organization IDs indexed for lookups
- ✅ Access tier filtering in Python layer

### Stage 2 (DynamoDB + MySQL)
- ✅ Submitter/HitTarget unchanged
- ✅ DynamoDB stores in submission documents
- ✅ MySQL stores organizations separately (Management API)
- ✅ Organization registry for known submitters

### Stage 3 (AWS ECS)
- ✅ Submitter/HitTarget unchanged
- ✅ AWS Cognito groups mapped to AccessTier
- ✅ DynamoDB continues embedded storage
- ✅ PostgreSQL for organization management

### Stage 4 (Kubernetes + ScyllaDB)
- ✅ Submitter/HitTarget unchanged
- ✅ ScyllaDB stores organizations separately
- ✅ Organization table with access control metadata
- ✅ Advanced privacy controls for anonymization

## Usage Examples

### Creating Submitter

```python
from frank.core.models import Submitter
from frank.core.enum import AccessTier

# Minimal submitter
submitter = Submitter(access_level=AccessTier.PARTNER)

# With metadata
submitter = Submitter(
    access_level=AccessTier.CORE_MEMBER,
    sector="financial",
    region="europe",
    client_count=150
)

# Using factory method
submitter = Submitter.create(
    access_level=AccessTier.PARTNER,
    sector="technology",
    region="north_america"
)

# With explicit ID
submitter = Submitter(
    organisation_id="identity--12345678-1234-5678-1234-123456789abc",
    access_level=AccessTier.CONTRIBUTOR
)
```

### Creating HitTarget

```python
from frank.core.models import HitTarget

# Minimal target
target = HitTarget(sector="healthcare")

# With metadata
target = HitTarget(
    sector="financial",
    organisation_size="large",
    region="europe",
    anonymization_level="medium"
)

# Using factory method
target = HitTarget.create(
    sector="healthcare",
    organisation_size="small",
    region="asia"
)
```

### Sector Normalization

```python
# Submitter sector normalization
submitter1 = Submitter(access_level=AccessTier.PARTNER, sector="finance")
print(submitter1.sector)  # "financial"

submitter2 = Submitter(access_level=AccessTier.PARTNER, sector="HEALTHCARE")
print(submitter2.sector)  # "health"

submitter3 = Submitter(access_level=AccessTier.PARTNER, sector="  gov  ")
print(submitter3.sector)  # "public_sector"

# Unknown sectors preserved
submitter4 = Submitter(access_level=AccessTier.PARTNER, sector="manufacturing")
print(submitter4.sector)  # "manufacturing" (lowercased)
```

### Organization Size Normalization

```python
# HitTarget size normalization
target1 = HitTarget(sector="retail", organisation_size="SME")
print(target1.organisation_size)  # "small"

target2 = HitTarget(sector="retail", organisation_size="enterprise")
print(target2.organisation_size)  # "large"

target3 = HitTarget(sector="retail", organisation_size="mid")
print(target3.organisation_size)  # "medium"
```

### In Submission Context

```python
from frank.core.models import Submission, Submitter, HitTarget, Sighting
from frank.core.enum import AccessTier

# Create submission with submitter and target
submission = Submission(
    submitter=Submitter.create(
        access_level=AccessTier.PARTNER,
        sector="financial"
    ),
    hit_target=HitTarget.create(
        sector="healthcare",
        organisation_size="large"
    ),
    sighting=Sighting.create(confidence=85)
)

# Access organizations
print(submission.submitter.organisation_id)  # identity--...
print(submission.hit_target.organisation_id)  # identity--... (different)

# Validation ensures they're different
# This would raise ValueError:
# submission = Submission(
#     submitter=Submitter(organisation_id="identity--abc", access_level=...),
#     hit_target=HitTarget(organisation_id="identity--abc", sector="...")
# )
```

### Serialization

```python
submitter = Submitter.create(
    access_level=AccessTier.PARTNER,
    sector="financial",
    region="europe"
)

# Dictionary
data = submitter.model_dump(exclude_none=True)
print(data)
# {
#     "organisation_id": "identity--...",
#     "access_level": "partner",
#     "organisation_type": "cyber_partner",
#     "sector": "financial",
#     "region": "europe"
# }

# JSON
json_str = submitter.model_dump_json()
```

## References

- **ADR-0007**: [Forgiving Input, Strong Output](../../docs/adr/0007-forgiving-input-strong-output.md)
- **STIX 2.1**: [Identity Object](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html#_wh296fiwpklp)
- **Access Control**: [AccessTier Enum Specification](enums.spec.md)
- **Implementation**: [src/frank/core/models.py](../../src/frank/core/models.py)
- **Tests**: [tests/unit/core/test_submitter.py](../../tests/unit/core/test_submitter.py), [tests/unit/core/test_hittarget.py](../../tests/unit/core/test_hittarget.py)
