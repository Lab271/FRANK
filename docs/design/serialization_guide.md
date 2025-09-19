# FRANK Dataclass Serialization Guide

## Overview

The FRANK platform implements a clean serialization pipeline that transforms threat intelligence data between different representations while maintaining the "be forgiving on what you receive, strong on what you return" principle. This guide explains the complete round-trip journey from Python dataclass to serialized formats and back.

## Serialization Pipeline Architecture

```python
JSON/YAML String
    ↓ from_validate_json() / from_yaml()
Submission (Pydantic) 
    ↓ model_dump(exclude_none=True)
Python Dict
    ↓ Storage
Database record
    ↓ 
Python Dict
    ↓ 
Submission (Pydantic)
    ↓ to_json() / to_yaml()
JSON/YAML String
```

This is in Pydantic v2

## Step-by-Step Data Transformation

### 1. JSON → Pydantic Submission

**Input Structure:**
```json
submission_dict = {
    'submission': {
        'submitter': {
            'organisation_id': 'identity-f431f809-377b-45e0-aa1c-6a4751cae5ff',
            'access_level': 'partner'
        },
        'sighting': {
            'sighting_id': 'sighting-ee20065d-2555-424f-ad9e-0f8428623c75',
            'timestamp': '2025-01-20T14:30:22Z',
            'observables': {
                'network': [
                    {
                        'id': 'ipv4-addr-c4e54321-1234-5678-9abc-def012345678',
                        'type': 'ipv4',
                        'value': '185.220.102.45'
                    }
                ]
            },
            'confidence': 87
        }
    }
}
```


```python
class Submission(BaseModel):
    submission_id: Optional[str] = Field(None, description="Unique submission identifier")
    format_version: Optional[str] = Field(default=__version__, description="FRANK format version")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Submission timestamp")

    # Optional metadata - be forgiving on input
    submitter: Optional[Submitter] = Field(None, description="Submitting organisation")
    submission_method: Optional[str] = Field(default="api", description="Submission method")
    processing_notes: Optional[str] = Field(None, description="Processing notes")

    sighting: Optional[Sighting] = Field(None, description="Sighting details")
    # TODO: Move this to sighting?
    hit_target: Optional[HitTarget] = Field(None, description="Affected organisation")
    tlp_level: Optional[str] = Field("GREEN", description="TLP classification")
    confidence: Optional[int] = Field(None, ge=0, le=100, description="Overall confidence level")
    severity: Optional[str] = Field(None, description="Threat severity")
```


The `Submission(**submission_dict['submission'])` class method transforms the dict into a Pydantic class.
