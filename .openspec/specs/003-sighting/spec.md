# Sighting Specification

**Domain:** Threat Intelligence / Core Data Models
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06
**Owner:** FRANK Core Team

**Related ADRs:** [ADR-0007: Forgiving Input, Strong Output](.openspec/architecture/decisions/0007-forgiving-input-strong-output.md)
**Implementation:** [src/frank/core/models.py#L291-L369](src/frank/core/models.py)
**Tests:** [tests/unit/core/test_sighting.py](tests/unit/core/test_sighting.py)

## Overview

Defines the Sighting model representing a single observation of threat activity. Contains core observation metadata (timestamp, confidence), observables (network/file/process indicators), and extended threat context (SIGMA detections, campaign attribution, MITRE ATT&CK mapping, impact assessment). Sightings are the primary threat intelligence payload in FRANK submissions.

### Philosophy

- **Rich Context Over Raw Data**: Capture not just indicators but full threat context (SIGMA, MITRE ATT&CK, campaigns)
- **STIX 2.1 Compliance**: Use STIX-compliant sighting IDs for threat intelligence sharing
- **Be Forgiving on Input**: Accept minimal or comprehensive submissions, validate thoroughly
- **Confidence Scoring**: Default to 69% (nice) confidence with explicit override capability

### Key Capabilities

- **Automatic ID Generation**: STIX-compliant sighting IDs (`sighting--{uuid}`)
- **Timestamp Management**: Auto-generated UTC timestamps with timezone awareness
- **Observable Containers**: Structured network/file/process observables
- **Extended Threat Context**: SIGMA detections, campaign attribution, MITRE ATT&CK mapping
- **Impact Assessment**: System/financial/organizational impact tracking
- **Observation Time Validation**: Ensures first_observed ≤ timestamp ≤ last_observed logic
- **Factory Method**: Convenient create() for quick sighting generation

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Usage in this specification**:
- **MUST/SHALL**: ID format, timestamp generation, observation time validation
- **SHOULD**: Include confidence scores, provide threat context when available
- **MAY**: Optional extended metadata (SIGMA, campaigns, MITRE ATT&CK, impact)

---

## Requirements

### Requirement 1: Core Sighting Structure

**Description**: The system MUST provide a Pydantic v2 model with automatic ID and timestamp generation, confidence scoring, and observable containers.

**Pydantic Schema**:
```python
class Sighting(BaseModel):
    model_config = ConfigDict(
        extra="ignore",           # Ignore unknown fields (be forgiving)
        use_enum_values=True,     # Serialize enums to strings
    )

    sighting_id: Optional[str] = Field(None, description="STIX sighting identifier")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When threat was observed")
    confidence: int = Field(69, ge=0, le=100, description="Confidence score 0-100")
    observation_count: int = Field(default=1, ge=1, description="Number of observations")
    observables: Optional[Observables] = Field(None, description="Threat observables")

    # Optional extended metadata
    severity: Optional[SeverityLevel] = Field(None, description="Threat severity level")
    first_observed: Optional[datetime] = Field(None, description="First observation time")
    last_observed: Optional[datetime] = Field(None, description="Last observation time")
    sigma_detection: Optional[SigmaDetection] = Field(None, description="SIGMA detection data")
    threat_context: Optional[ThreatContext] = Field(None, description="Threat context")
    impact: Optional[Impact] = Field(None, description="Impact assessment")
```

**Acceptance Criteria**:
- ✅ `sighting_id` auto-generated as `sighting--{uuid}` if not provided
- ✅ `timestamp` defaults to current UTC time
- ✅ `confidence` range validated 0-100, default 69
- ✅ `observation_count` minimum 1
- ✅ `first_observed` < `last_observed` validation
- ✅ `first_observed` <= `timestamp` validation
- ✅ Timezone-aware datetime handling
- ✅ Extra fields ignored (forgiving on input)

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_create_minimal_sighting](tests/unit/core/test_sighting.py#L60-L84), [test_create_sighting_with_all_fields](tests/unit/core/test_sighting.py#L86-L112)

#### Scenario: Create Minimal Sighting
- GIVEN a minimal sighting without ID or timestamp
- WHEN creating a Sighting instance
- THEN a sighting_id SHALL be auto-generated in format `sighting--{uuid}`
- AND timestamp SHALL default to current UTC time
- AND confidence SHALL default to 69

### Requirement 2: Automatic ID and Timestamp Generation

**Description**: The system MUST auto-generate STIX-compliant sighting IDs and UTC timestamps if not provided.

**ID Generation**:
```python
@model_validator(mode="after")
def validate_observation_times_and_ensure_ids(self):
    """Ensure observation times are logical and IDs are set"""
    if not self.sighting_id:
        self.sighting_id = f"sighting--{uuid.uuid4()}"
    # ... timezone and validation logic
    return self
```

**Timestamp Generation**:
```python
@field_validator("timestamp", mode="before")
@classmethod
def validate_timestamp(cls, v):
    """Ensure observation times are logical and IDs are set"""
    if v is None or v == "":
        return datetime.now(timezone.utc)
    return v
```

#### Scenario: Auto-Generate Sighting ID and Timestamp
- GIVEN a sighting created without sighting_id or timestamp
- WHEN the Sighting model is instantiated
- THEN sighting_id SHALL be auto-generated in format `sighting--{uuid}`
- AND timestamp SHALL be set to current UTC time
- AND both fields SHALL be populated before validation completes

**Acceptance Criteria**:
- ✅ `sighting_id` generated if None or empty string
- ✅ `timestamp` defaults to `datetime.now(timezone.utc)`
- ✅ Existing IDs preserved (not overwritten)
- ✅ Multiple sightings get unique IDs
- ✅ Timestamps are timezone-aware (UTC)

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_sighting_id_auto_generation](tests/unit/core/test_sighting.py#L113-L133), [test_timestamp_auto_generation_branch](tests/unit/core/test_sighting.py#L135-L167)

### Requirement 3: Observation Time Validation

**Description**: The system MUST validate logical consistency of observation timestamps.

**Validation Rules**:
1. `first_observed` <= `last_observed`
2. `first_observed` <= `timestamp`
3. All datetimes timezone-aware (converted to UTC if naive)

**Validation Implementation**:
```python
@model_validator(mode="after")
def validate_observation_times_and_ensure_ids(self):
    # Ensure timezone-aware datetimes
    if self.timestamp.tzinfo is None:
        self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
    if self.first_observed and self.first_observed.tzinfo is None:
        self.first_observed = self.first_observed.replace(tzinfo=timezone.utc)
    if self.last_observed and self.last_observed.tzinfo is None:
        self.last_observed = self.last_observed.replace(tzinfo=timezone.utc)

    # Validate observation times
    if self.first_observed and self.last_observed:
        if self.first_observed > self.last_observed:
            raise ValueError("first_observed cannot be after last_observed")

    if self.first_observed and self.timestamp:
        if self.first_observed > self.timestamp:
            raise ValueError("first_observed cannot be after main timestamp")
    return self
```

**Acceptance Criteria**:
- ✅ `first_observed` > `last_observed` raises ValueError
- ✅ `first_observed` > `timestamp` raises ValueError
- ✅ Same time for `first_observed` and `last_observed` allowed
- ✅ Naive datetimes converted to UTC
- ✅ None values handled correctly

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_observation_times_validation](tests/unit/core/test_sighting.py#L348-L361), [test_observation_times_invalid_order](tests/unit/core/test_sighting.py#L363-L375), [test_invalid_observation_time_last](tests/unit/core/test_sighting.py#L263-L269)

#### Scenario: Validate Observation Time Ordering
- GIVEN a sighting with first_observed at 09:00 and last_observed at 11:00
- WHEN creating the Sighting with timestamp at 10:00
- THEN validation SHALL pass with first_observed <= timestamp <= last_observed
- AND all timestamps SHALL be timezone-aware in UTC

### Requirement 4: Confidence Scoring

**Description**: The system MUST provide a confidence score (0-100) indicating reliability of threat intelligence.

**Confidence Levels**:
- 0-20: Very Low - Unverified, speculative
- 21-40: Low - Limited verification
- 41-60: Medium - Some verification
- 61-80: High - Well-verified
- 81-100: Very High - Confirmed, corroborated

**Default**: 69 (High confidence baseline)

**Acceptance Criteria**:
- ✅ Range validated: 0 ≤ confidence ≤ 100
- ✅ Default value: 69
- ✅ Integer type enforced
- ✅ Out-of-range values raise ValidationError

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_confidence_validation](tests/unit/core/test_sighting.py#L280-L295)

#### Scenario: Validate Confidence Score Range
- GIVEN a sighting with confidence score of 95
- WHEN creating the Sighting instance
- THEN the confidence SHALL be validated within range 0-100
- AND confidence values outside range SHALL raise ValidationError

### Requirement 5: Observables Container

**Description**: The system MUST provide a container for network, file, and process observables grouped by category.

**Structure**:
```python
class Observables(BaseModel):
    network: Optional[List[Observable]] = Field(default_factory=list)
    file: Optional[List[Observable]] = Field(default_factory=list)
    process: Optional[List[Observable]] = Field(default_factory=list)
```

**Observable Categories**:
- **Network**: IPV4, IPV6, DOMAIN, URL, EMAIL, CERTIFICATE
- **File**: FILE_HASH (MD5, SHA1, SHA256)
- **Process**: REGISTRY_KEY, MUTEX

**Acceptance Criteria**:
- ✅ Observables grouped by category
- ✅ Each category is optional (default empty list)
- ✅ Lists can contain multiple observables
- ✅ Empty lists allowed (no observables in category)

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: Test coverage in observable tests, integration in sighting tests

#### Scenario: Group Observables by Category
- GIVEN a sighting with 2 network observables and 1 file observable
- WHEN creating the Observables container
- THEN network observables SHALL be in the network list
- AND file observables SHALL be in the file list
- AND process list SHALL be empty

### Requirement 6: Extended Threat Metadata

**Description**: The system MAY include optional rich threat intelligence context including SIGMA rules, campaigns, MITRE ATT&CK, and impact data.

**Extended Models**:

1. **SigmaDetection** - SIGMA rule metadata
   ```python
   class SigmaDetection(BaseModel):
       rule_id: str = Field(default_factory=lambda: f"sigma--{uuid.uuid4()}")
       rule_name: str
       rule_version: Optional[str] = None
       rule_status: Optional[str] = None
       sigma_yaml: Optional[str] = None
       rule_effectiveness: Optional[float] = None
       false_positive_rate: Optional[float] = None
   ```

2. **Campaign** - Threat campaign attribution
   ```python
   class Campaign(BaseModel):
       id: str = Field(default_factory=lambda: f"campaign--{uuid.uuid4()}")
       name: Optional[str] = None
       attribution: Optional[str] = None
       target_sectors: Optional[List[str]] = None
       attack_vector: Optional[str] = None
       payload_type: Optional[str] = None
       campaign_start: Optional[datetime] = None
       estimated_victims: Optional[int] = None
       confidence: Optional[int] = None
   ```

3. **ThreatContext** - Campaign and MITRE mapping
   ```python
   class ThreatContext(BaseModel):
       campaign: Optional[Campaign] = None
       mitre_attack: Optional[Dict[str, Any]] = None
       malware_family: Optional[Dict[str, Any]] = None
   ```

4. **Impact** - Impact assessment
   ```python
   class Impact(BaseModel):
       affected_systems: Optional[int] = None
       compromised_accounts: Optional[int] = None
       containment_time: Optional[str] = None
       financial_impact_eur: Optional[int] = None
   ```

**Acceptance Criteria**:
- ✅ All extended metadata optional
- ✅ SIGMA rule ID auto-generated
- ✅ Campaign ID auto-generated
- ✅ MITRE ATT&CK as flexible dict
- ✅ Impact metrics optional

**Stage Availability**: Stages 1, 2, 3, 4 (Stage 3+ recommended for complex submissions)

**Test Coverage**: [test_threat_context_serialization](tests/unit/core/test_sighting.py#L702-L713), [test_campaign_serialization](tests/unit/core/test_sighting.py#L724-L747), [test_sigma_detection_serialization](tests/unit/core/test_sighting.py#L755-L768)

#### Scenario: Enrich Sighting with Threat Context
- GIVEN a sighting with basic observables
- WHEN adding SIGMA detection, campaign attribution, and MITRE ATT&CK mapping
- THEN the threat_context SHALL contain campaign and mitre_attack data
- AND the sigma_detection SHALL have auto-generated rule_id

### Requirement 7: Factory Method

**Description**: The system SHOULD provide a convenience factory method for creating sightings.

**Factory Method**:
```python
@classmethod
def create(
    cls,
    observables: Observables = None,
    confidence: int = 69,
    severity: SeverityLevel = None,
    observation_count: int = 1,
) -> "Sighting":
    """Factory method for creating sightings"""
    return cls(
        confidence=confidence,
        observables=observables,
        severity=severity,
        observation_count=observation_count,
    )
```

**Acceptance Criteria**:
- ✅ Sets confidence, severity, observation_count
- ✅ Auto-generates sighting_id and timestamp
- ✅ Returns fully validated Sighting instance

**Stage Availability**: Stages 1, 2, 3, 4

**Test Coverage**: [test_factory_method_create](tests/unit/core/test_sighting.py#L405-L418), [test_factory_method_minimal](tests/unit/core/test_sighting.py#L420-L430)

#### Scenario: Create Sighting Using Factory Method
- GIVEN observables and confidence score of 85
- WHEN calling Sighting.create() with observables and severity
- THEN a fully validated Sighting instance SHALL be returned
- AND sighting_id and timestamp SHALL be auto-generated

## Non-Functional Requirements

### Performance
- **Creation Time**: < 2ms per sighting
- **Validation**: O(n) where n = number of observables
- **Serialization**: Efficient JSON/YAML output

**Test**: [test_bulk_creation_performance](tests/unit/core/test_sighting.py#L647-L672) - 100 sightings < 1 second

### Validation
- **Confidence**: 0 ≤ confidence ≤ 100
- **Observation Count**: observation_count ≥ 1
- **Timestamps**: Logical ordering, timezone-aware
- **Severity**: Valid SeverityLevel enum or None

### Serialization
- **Datetime Format**: ISO 8601 with timezone (`2025-01-15T10:30:00+00:00`)
- **Enum Serialization**: String values (`"high"` not `SeverityLevel.HIGH`)
- **Field Exclusion**: `exclude_none=True` removes None values
- **Extra Fields**: Ignored (ConfigDict `extra="ignore"`)

## Data Model

### Complete Sighting Schema

```json
{
    "sighting_id": "sighting--550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00+00:00",
    "confidence": 85,
    "observation_count": 3,

    "observables": {
        "network": [
            {
                "id": "ipv4--a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
                "type": "ipv4",
                "value": "192.168.1.100",
                "role": "c2",
                "port": 443
            },
            {
                "id": "domain--f6e5d4c3-b2a1-4f5e-9d8c-7b6a5f4e3d2c",
                "type": "domain",
                "value": "malicious.com",
                "role": "phishing"
            }
        ],
        "file": [
            {
                "id": "file_hash--1a2b3c4d-5e6f-4a5b-8c9d-0e1f2a3b4c5d",
                "type": "file_hash",
                "value": "5d41402abc4b2a76b9719d911017c592"
            }
        ]
    },

    "severity": "high",
    "first_observed": "2025-01-15T09:00:00+00:00",
    "last_observed": "2025-01-15T11:00:00+00:00",

    "sigma_detection": {
        "rule_id": "sigma--abc123...",
        "rule_name": "Suspicious Process Execution",
        "rule_effectiveness": 0.92,
        "false_positive_rate": 0.03
    },

    "threat_context": {
        "campaign": {
            "id": "campaign--xyz789...",
            "name": "APT-Example Campaign",
            "attribution": "APT28",
            "target_sectors": ["financial", "healthcare"]
        },
        "mitre_attack": {
            "tactics": ["TA0001", "TA0002"],
            "techniques": ["T1059.001", "T1071.001"]
        }
    },

    "impact": {
        "affected_systems": 42,
        "compromised_accounts": 5,
        "containment_time": "2h",
        "financial_impact_eur": 50000
    }
}
```

## Validation Rules

### Field Validation

1. **sighting_id** (Optional[str])
   - Generated if None or empty: `sighting--{uuid4}`
   - Preserved if provided

2. **timestamp** (datetime) - REQUIRED
   - Default: `datetime.now(timezone.utc)`
   - Timezone-aware (converted if naive)

3. **confidence** (int) - REQUIRED
   - Range: 0-100 (inclusive)
   - Default: 69

4. **observation_count** (int) - REQUIRED
   - Minimum: 1
   - Default: 1

5. **severity** (Optional[SeverityLevel])
   - Valid enum or None
   - No default value

6. **first_observed, last_observed** (Optional[datetime])
   - Timezone-aware (converted if naive)
   - `first_observed` <= `last_observed`
   - `first_observed` <= `timestamp`

### Model Validators

**validate_timestamp** (mode="before")
- Converts None or empty string to current UTC time

**validate_observation_times_and_ensure_ids** (mode="after")
- Generates `sighting_id` if missing
- Adds timezone info to naive datetimes
- Validates observation time ordering

### Serialization Rules

**Datetime Serialization**:
```python
@field_serializer("timestamp", "first_observed", "last_observed", when_used="always")
def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
    """Always serialize datetime as ISO string"""
    if value is None:
        return None
    return value.isoformat()
```

## Test Coverage Requirements

**Minimum Coverage**: ≥85% (enforced by CI/CD)

**Test Categories**:
1. **Creation Tests** - Minimal, full fields, public/full sightings
2. **Validation Tests** - Confidence range, observation count, timestamps
3. **Datetime Tests** - Auto-generation, parsing, timezone handling
4. **Serialization Tests** - JSON/YAML round-trips, datetime formatting
5. **Factory Tests** - create() method with various parameters
6. **Extended Metadata Tests** - SIGMA, campaign, impact serialization
7. **Performance Tests** - Bulk creation, datetime parsing

**Test Files**:
- [tests/unit/core/test_sighting.py](tests/unit/core/test_sighting.py) - 779 lines, comprehensive coverage

**Key Test Classes**:
- `TestSighting` - Core sighting functionality
- `TestSightingIntegration` - Integration with submissions
- `TestSightingPerformance` - Performance benchmarks
- `TestSerializationModels` - Extended metadata serialization

## Implementation Status

- [x] Design complete
- [x] Pydantic model implemented
- [x] Auto-generation (ID, timestamp) implemented
- [x] Observation time validation implemented
- [x] Extended metadata models implemented
- [x] Factory method implemented
- [x] Serialization implemented
- [x] Tests written (≥85% coverage)
- [x] Code review passed
- [x] Merged to main

**PR Links**:
- Initial Sighting model: Merged in baseline
- Extended metadata: Part of Stage 3 enhancements
- Comprehensive tests: [tests/unit/core/test_sighting.py](tests/unit/core/test_sighting.py)

## Evolution Path Across FRANK Stages

### Stage 1 (SQLite)
- ✅ Full Sighting implementation
- ✅ Basic sightings (timestamp, confidence, observables)
- ✅ Extended metadata optional (SIGMA, campaign)
- ✅ Stored as JSON in SQLite TEXT column

### Stage 2 (DynamoDB + MySQL)
- ✅ Sighting unchanged, same model
- ✅ DynamoDB stores sightings in submission documents
- ✅ Learning stage for complex sightings

### Stage 3 (AWS ECS)
- ✅ Sighting unchanged, cloud deployment
- ✅ **Complex submissions introduced**: Rich SIGMA, campaign, impact data
- ✅ CloudWatch metrics on sighting counts
- ✅ DynamoDB optimized for sighting queries

### Stage 4 (Kubernetes + ScyllaDB)
- ✅ Sighting unchanged, production scale
- ✅ ScyllaDB stores sightings with materialized views
- ✅ Potential for sighting-level access control
- ✅ Advanced analytics on sighting trends

## Usage Examples

### Basic Sighting Creation

```python
from frank.core.models import Sighting, Observable, Observables
from frank.core.enum import SeverityLevel

# Minimal sighting
sighting = Sighting(
    confidence=85,
    observables=Observables(
        network=[Observable.create_ipv4("192.168.1.1", role="c2")]
    )
)

# With severity
sighting = Sighting(
    confidence=90,
    severity=SeverityLevel.HIGH,
    observation_count=5,
    observables=Observables(
        network=[
            Observable.create_ipv4("203.0.113.42", role="c2"),
            Observable.create_domain("evil.com", role="phishing")
        ]
    )
)
```

### Factory Method

```python
# Using create() factory
sighting = Sighting.create(
    confidence=85,
    severity=SeverityLevel.CRITICAL,
    observables=Observables(network=[...])
)
```

### Extended Metadata

```python
from frank.core.models import Campaign, ThreatContext, SigmaDetection, Impact

# SIGMA detection
sigma = SigmaDetection(
    rule_name="Suspicious Process Execution",
    rule_effectiveness=0.92,
    false_positive_rate=0.03
)

# Campaign attribution
campaign = Campaign(
    name="APT-Example Campaign",
    attribution="APT28",
    target_sectors=["financial", "healthcare"],
    attack_vector="spearphishing"
)

# Threat context
threat_context = ThreatContext(
    campaign=campaign,
    mitre_attack={"tactics": ["TA0001"], "techniques": ["T1059.001"]},
    malware_family={"name": "TrickBot", "variant": "v2.3"}
)

# Impact assessment
impact = Impact(
    affected_systems=42,
    compromised_accounts=5,
    containment_time="2h",
    financial_impact_eur=50000
)

# Complete sighting
sighting = Sighting(
    confidence=95,
    severity=SeverityLevel.CRITICAL,
    observation_count=10,
    observables=Observables(network=[...]),
    sigma_detection=sigma,
    threat_context=threat_context,
    impact=impact
)
```

### Observation Time Handling

```python
from datetime import datetime, timezone

# With observation timeline
sighting = Sighting(
    first_observed=datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc),
    last_observed=datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc),
    timestamp=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    confidence=85,
    observables=Observables(network=[...])
)

# Auto-generation (current time)
sighting = Sighting(confidence=85)  # timestamp = now()
```

### Serialization

```python
# Dictionary
data = sighting.model_dump(exclude_none=True)

# JSON
json_str = sighting.model_dump_json(by_alias=True, exclude_none=True)

# With datetime handling
print(data["timestamp"])  # "2025-01-15T10:30:00+00:00"
```

## References

- **ADR-0007**: [Forgiving Input, Strong Output](.openspec/architecture/decisions/0007-forgiving-input-strong-output.md)
- **STIX 2.1**: [Sighting Object](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html#_a795guqsap3r)
- **SIGMA**: [SIGMA Rule Format](https://github.com/SigmaHQ/sigma)
- **MITRE ATT&CK**: [Enterprise Matrix](https://attack.mitre.org/)
- **Implementation**: [src/frank/core/models.py](src/frank/core/models.py)
- **Tests**: [tests/unit/core/test_sighting.py](tests/unit/core/test_sighting.py)
