# FRANK Dataclass Serialization Guide

## Overview

The FRANK platform implements a clean serialization pipeline that transforms threat intelligence data between different representations while maintaining the "be forgiving on what you receive, strong on what you return" principle. This guide explains the complete round-trip journey from Python dataclass to serialized formats and back.

## Serialization Pipeline Architecture

```
Submission (Pydantic) 
    ↓ model_dump_json() / to_yaml()
JSON/YAML String
    ↓ Network/Storage
JSON/YAML String
    ↓ model_validate_json() / from_yaml()
Submission (Pydantic)
```

This is in Pydantic v2

## Step-by-Step Data Transformation

### 1. FRANKSubmission Dataclass → Python Dict

The `FRANKSubmission.to_dict()` method transforms the dataclass into a structured dictionary following the FRANK schema.

```python
from frank_submissions import FRANKSubmission

# Create a submission dataclass instance
submission = FRANKSubmission(
    submitter_org_id="identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
    submitter_access_level="partner",
    sighting_id="sighting-ee20065d-2555-424f-ad9e-0f8428623c75",
    timestamp="2025-01-20T14:30:22Z",
    observables={
        "network": [
            {
                "id": "ipv4-addr-c4e54321-1234-5678-9abc-def012345678",
                "type": "ipv4",
                "value": "185.220.102.45"
            }
        ]
    },
    confidence=87
)

# Convert to dictionary
submission_dict = submission.to_dict()
print(submission_dict)
```

**Output Structure:**
```python
{
    'submission': {
        'submitter': {
            'organization_id': 'identity-f431f809-377b-45e0-aa1c-6a4751cae5ff',
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

### 2. Python Dict → YAML/JSON String

The dictionary is serialized to YAML or JSON format using standard libraries.

#### YAML Serialization
```python
from frank_submissions import to_yaml

# Convert to YAML string
yaml_string = to_yaml(submission)
print(yaml_string)
```

**YAML Output:**
```yaml
submission:
  submitter:
    organization_id: identity-f431f809-377b-45e0-aa1c-6a4751cae5ff
    access_level: partner
  sighting:
    sighting_id: sighting-ee20065d-2555-424f-ad9e-0f8428623c75
    timestamp: '2025-01-20T14:30:22Z'
    observables:
      network:
      - id: ipv4-addr-c4e54321-1234-5678-9abc-def012345678
        type: ipv4
        value: 185.220.102.45
    confidence: 87
```

#### JSON Serialization
```python
from frank_submissions import to_json

# Convert to JSON string
json_string = to_json(submission)
print(json_string)
```

**JSON Output:**
```json
{
  "submission": {
    "submitter": {
      "organization_id": "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
      "access_level": "partner"
    },
    "sighting": {
      "sighting_id": "sighting-ee20065d-2555-424f-ad9e-0f8428623c75",
      "timestamp": "2025-01-20T14:30:22Z",
      "observables": {
        "network": [
          {
            "id": "ipv4-addr-c4e54321-1234-5678-9abc-def012345678",
            "type": "ipv4",
            "value": "185.220.102.45"
          }
        ]
      },
      "confidence": 87
    }
  }
}
```

### 3. YAML/JSON String → Python Dict

Deserialization parses the string format back into a Python dictionary.

#### YAML Deserialization
```python
import yaml

# Parse YAML string back to dictionary
yaml_dict = yaml.safe_load(yaml_string)
print(yaml_dict)
```

#### JSON Deserialization
```python
import json

# Parse JSON string back to dictionary
json_dict = json.loads(json_string)
print(json_dict)
```

### 4. Python Dict → FRANKSubmission Dataclass

The `from_dict()` class method reconstructs the dataclass from the dictionary.

```python
from frank_submissions import from_yaml, from_json

# From YAML
restored_from_yaml = from_yaml(yaml_string)
print(f"Restored from YAML: {restored_from_yaml.sighting_id}")

# From JSON  
restored_from_json = from_json(json_string)
print(f"Restored from JSON: {restored_from_json.sighting_id}")

# Direct from dictionary
restored_from_dict = FRANKSubmission.from_dict(submission_dict)
print(f"Restored from dict: {restored_from_dict.confidence}")
```

## Implementation Details

### Dataclass Structure

The `FRANKSubmission` dataclass uses the `@dataclass` decorator and implements two key methods:

```python
@dataclass
class FRANKSubmission:
    """Pure dataclass container for FRANK threat intelligence submissions."""
    
    # Core fields with defaults
    submitter_org_id: Optional[str] = None
    submitter_access_level: Optional[str] = None
    sighting_id: Optional[str] = None
    timestamp: Optional[str] = None
    observables: Optional[Dict[str, List[Dict[str, Any]]]] = None
    confidence: int = 69
    
    # Optional fields with defaults
    metadata: Optional[Dict[str, Any]] = None
    # ... additional fields
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FRANKSubmission':
        """Create FRANKSubmission from dictionary using safe extraction."""
        submission_data = _safe_get(data, 'submission')
        submitter = _safe_get(submission_data, 'submitter')
        sighting = _safe_get(submission_data, 'sighting')
        
        return cls(
            submitter_org_id=_safe_get(submitter, 'organization_id'),
            submitter_access_level=_safe_get(submitter, 'access_level'),
            sighting_id=_safe_get(sighting, 'sighting_id'),
            # ... map all fields
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, only including non-None values."""
        submission = {}
        
        # Build submitter section
        submitter = {}
        if self.submitter_org_id:
            submitter['organization_id'] = self.submitter_org_id
        if self.submitter_access_level:
            submitter['access_level'] = self.submitter_access_level
            
        # Build sighting section
        sighting = {}
        if self.sighting_id:
            sighting['sighting_id'] = self.sighting_id
        # ... build complete structure
        
        return {'submission': submission}
```

### Safe Extraction Helper

The `_safe_get()` function provides defensive programming for data extraction:

```python
def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """Get value from dict if it's a dict, otherwise return None."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default
```

This ensures the "be forgiving" principle - if data is malformed or missing, extraction continues gracefully.

### Serialization Helper Functions

The module provides convenience functions for common serialization operations:

```python
def to_yaml(submission: FRANKSubmission) -> str:
    """Convert submission to YAML format."""
    try:
        return yaml.dump(submission.to_dict(), default_flow_style=False, sort_keys=False)
    except Exception as e:
        raise FRANKFormatError(f"Failed to convert to YAML: {e}")

def from_yaml(yaml_str: str) -> FRANKSubmission:
    """Parse submission from YAML format."""
    try:
        data = yaml.safe_load(yaml_str)
        return FRANKSubmission.from_dict(data)
    except yaml.YAMLError as e:
        raise FRANKFormatError(f"Invalid YAML format: {e}")
```

## Validation Integration

The serialization process integrates with the validation framework:

```python
from frank_submissions import validate_submission, validate_submission_dict

# Validate dataclass
is_valid, issues = validate_submission(submission)
if not is_valid:
    print(f"Validation issues: {issues}")

# Validate dictionary
is_valid, issues = validate_submission_dict(submission_dict)
if not is_valid:
    print(f"Dictionary validation issues: {issues}")
```

## Error Handling

The serialization pipeline includes comprehensive error handling:

### Format Errors
```python
try:
    submission = from_yaml(malformed_yaml)
except FRANKFormatError as e:
    print(f"Format error: {e}")
    # Handle gracefully - perhaps try JSON parsing
```

### Validation Errors
```python
# Create submission with missing required fields
incomplete_submission = FRANKSubmission()

is_valid, issues = validate_submission(incomplete_submission)
if not is_valid:
    for issue in issues:
        print(f"Validation issue: {issue}")
```

## Best Practices

### 1. Always Validate After Deserialization
```python
# Good practice
submission = from_yaml(yaml_string)
is_valid, issues = validate_submission(submission)
if not is_valid:
    handle_validation_errors(issues)
```

### 2. Handle Serialization Errors Gracefully
```python
try:
    yaml_output = to_yaml(submission)
except FRANKFormatError as e:
    # Log error and try alternative format
    logger.error(f"YAML serialization failed: {e}")
    json_output = to_json(submission)
```

### 3. Preserve Original Data
```python
# Store original format for debugging
original_yaml = yaml_string
submission = from_yaml(original_yaml)

# Process submission...

# Can always reference original if issues arise
if validation_fails:
    debug_original_format(original_yaml)
```

### 4. Use Type Hints
```python
def process_submission(yaml_data: str) -> FRANKSubmission:
    """Process YAML submission data with proper typing."""
    submission: FRANKSubmission = from_yaml(yaml_data)
    is_valid, issues = validate_submission(submission)
    
    if not is_valid:
        raise ValueError(f"Invalid submission: {issues}")
    
    return submission
```

## Complete Example

Here's a complete example showing the full round-trip:

```python
#!/usr/bin/env python3
"""Complete FRANK serialization example."""

from frank_submissions import (
    FRANKSubmission, 
    to_yaml, from_yaml, 
    to_json, from_json,
    validate_submission
)

def main():
    # 1. Create dataclass instance
    original = FRANKSubmission(
        submitter_org_id="identity-test-123",
        submitter_access_level="contributor",
        sighting_id="sighting-test-456", 
        timestamp="2025-01-20T10:00:00Z",
        observables={
            "network": [{
                "id": "ip-test-789",
                "type": "ipv4", 
                "value": "192.168.1.100"
            }]
        },
        confidence=75
    )
    
    print("=== Original Dataclass ===")
    print(f"Sighting ID: {original.sighting_id}")
    print(f"Confidence: {original.confidence}")
    
    # 2. Serialize to YAML
    yaml_str = to_yaml(original)
    print("\n=== YAML Serialization ===")
    print(yaml_str)
    
    # 3. Deserialize from YAML
    restored = from_yaml(yaml_str)
    print("=== Restored from YAML ===")
    print(f"Sighting ID: {restored.sighting_id}")
    print(f"Confidence: {restored.confidence}")
    
    # 4. Validate round-trip integrity
    is_valid, issues = validate_submission(restored)
    print(f"\n=== Validation Results ===")
    print(f"Valid: {is_valid}")
    if issues:
        for issue in issues:
            print(f"Issue: {issue}")
    
    # 5. Test JSON round-trip
    json_str = to_json(original)
    json_restored = from_json(json_str)
    
    print(f"\n=== JSON Round-trip Test ===")
    print(f"Original confidence: {original.confidence}")
    print(f"JSON restored confidence: {json_restored.confidence}")
    print(f"Round-trip successful: {original.confidence == json_restored.confidence}")

if __name__ == "__main__":
    main()
```

This serialization system provides a robust, error-tolerant foundation for FRANK's threat intelligence sharing platform while maintaining the flexibility to handle both minimal and comprehensive submission formats.