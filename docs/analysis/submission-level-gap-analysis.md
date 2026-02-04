# Submission Level Gap Analysis

**Task**: Verify 5-level submission model (L1-L5) implementation matches HLD
**Date**: 2026-02-04
**Analyst**: agent-2

## HLD Requirements

The High-Level Design document specifies a 5-level submission model:

| Level | Name | Analytical Requirement | Example Content |
|-------|------|----------------------|-----------------|
| L1 | Raw Observable | Minimal | IP contacted server on port 443 |
| L2 | Contextualized Observable | Operational | 15 connections over 2 hours, blocked after 45 min containment, 3 systems affected |
| L3 | Threat Attribution | Expert analysis | Attributed to TrickBot campaign, 87% confidence |
| L4 | SIGMA Detection | Rule development | SIGMA rule triggered 23 times, 3% false positive rate |
| L5 | Behavioral Analysis | Advanced research | Novel persistence mechanism using undocumented registry keys |

## Current Implementation Status

### ✓ Data Structures Present

The following model classes support the submission levels:

1. **Observable** (`src/frank/core/models.py:28`)
   - Supports: IP, domain, URL, email, file_hash, registry_key, mutex, certificate
   - Has: value, type, role, port, protocol, first_seen, connection_count
   - Status: **Adequate for L1-L2**

2. **Sighting** (`src/frank/core/models.py:290`)
   - Has: confidence (0-100), observation_count, severity
   - Has: first_observed, last_observed timestamps
   - Status: **Adequate for L1-L2**

3. **Impact** (`src/frank/core/models.py:274`)
   - Has: affected_systems, compromised_accounts, containment_time, financial_impact_eur
   - Status: **Adequate for L2**

4. **ThreatContext** (`src/frank/core/models.py:259`)
   - Has: campaign (with attribution, target_sectors, confidence)
   - Has: mitre_attack mapping
   - Has: malware_family data
   - Status: **Adequate for L3**

5. **SigmaDetection** (`src/frank/core/models.py:219`)
   - Has: rule_id, rule_name, rule_version, rule_status
   - Has: sigma_yaml, rule_effectiveness, false_positive_rate
   - Status: **Adequate for L4**

### ✗ Missing Components

1. **SubmissionLevel Enum** - Not implemented
   - Need: `SubmissionLevel(L1, L2, L3, L4, L5)` enum
   - Location: Should be in `src/frank/core/enum.py`

2. **Level Assignment Logic** - Not implemented
   - Need: Method to calculate/validate submission level based on content
   - Should validate that required fields are present for claimed level

3. **Level Field on Submission** - Not implemented
   - Need: `submission_level: SubmissionLevel` field on Submission model
   - Should support both explicit assignment and auto-detection

4. **L5 Support** - Partial
   - Need: Additional fields for novel behavioral patterns
   - Consider: `novel_ttp`, `behavioral_indicators`, `research_notes` fields

## Recommendations

### Option A: Explicit Level Field (Recommended)

Add a `submission_level` field to the `Submission` model that submitters must set:

```python
# In src/frank/core/enum.py
class SubmissionLevel(str, Enum):
    """Submission analytical depth level"""
    L1_RAW_OBSERVABLE = "L1"           # Basic IoC
    L2_CONTEXTUALIZED = "L2"           # Operational context
    L3_ATTRIBUTION = "L3"              # Threat attribution
    L4_SIGMA_DETECTION = "L4"          # SIGMA rule triggered
    L5_BEHAVIORAL_ANALYSIS = "L5"      # Novel research

# In src/frank/core/models.py
class Submission(BaseModel):
    submission_level: SubmissionLevel = Field(
        default=SubmissionLevel.L1_RAW_OBSERVABLE,
        description="Analytical depth level of submission"
    )
```

### Option B: Auto-Calculated Level

Add a validator that calculates level based on populated fields:

```python
@model_validator(mode="after")
def calculate_submission_level(self):
    if self.sighting and self.sighting.sigma_detection:
        self.submission_level = SubmissionLevel.L4_SIGMA_DETECTION
    elif self.sighting and self.sighting.threat_context:
        self.submission_level = SubmissionLevel.L3_ATTRIBUTION
    elif self.sighting and self.sighting.impact:
        self.submission_level = SubmissionLevel.L2_CONTEXTUALIZED
    else:
        self.submission_level = SubmissionLevel.L1_RAW_OBSERVABLE
    return self
```

## Implementation Effort

| Component | Effort | Priority |
|-----------|--------|----------|
| SubmissionLevel enum | 30 min | High |
| Add field to Submission | 15 min | High |
| Level validation logic | 2 hours | Medium |
| L5 behavioral fields | 1 hour | Low |
| Unit tests | 2 hours | High |

**Total estimated effort**: 5-6 hours

## Conclusion

The current implementation has **70% of the data structures** needed for the 5-level model, but lacks:
- The explicit `SubmissionLevel` enum
- Level assignment/validation logic
- L5-specific fields for novel research

The gap is addressable with moderate effort and should be prioritized to align with the HLD.
