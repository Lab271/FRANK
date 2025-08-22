#!/usr/bin/env python3
"""
FRANK Platform - Minimal Submission Test Script
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This script demonstrates generating and parsing minimal threat intelligence submissions
following the "be forgiving on what you receive and strong on what you return" principle.
"""

import yaml
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FRANKSubmission:
    """
    Handles FRANK threat intelligence submissions with minimal required fields
    and graceful handling of optional extended data.
    """
    
    # Required fields for minimal submission
    REQUIRED_FIELDS = {
        'submission.submitter.organization_id',
        'submission.submitter.tier', 
        'submission.sighting.sighting_id',
        'submission.sighting.timestamp',
        'submission.sighting.observables'
    }
    
    # Default values following "be forgiving" principle
    DEFAULTS = {
        'confidence': 69,  # Default confidence as specified
        'format_version': '1.0',
        'submission_method': 'manual',
        'anonymization_level': 'moderate'
    }
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def generate_minimal_submission(self, 
                                  org_id: str = None,
                                  tier: str = "partner",
                                  observables: List[Dict] = None) -> Dict[str, Any]:
        """
        Generate a minimal FRANK submission with only required fields.
        Optional parameters allow customization while maintaining minimalism.
        """
        
        # Generate default values if not provided
        if org_id is None:
            org_id = f"identity-{uuid.uuid4()}"
            
        if observables is None:
            observables = [
                {
                    "id": f"ipv4-addr-{uuid.uuid4()}",
                    "type": "ipv4",
                    "value": "185.220.102.45"
                },
                {
                    "id": f"domain-name-{uuid.uuid4()}",
                    "type": "domain", 
                    "value": "secure-bank-verify.nl"
                }
            ]
        
        submission = {
            "submission": {
                "submitter": {
                    "organization_id": org_id,
                    "tier": tier
                },
                "sighting": {
                    "sighting_id": f"sighting-{uuid.uuid4()}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "confidence": self.DEFAULTS['confidence'],
                    "observables": {
                        "network": observables
                    }
                }
            }
        }
        
        self.logger.info(f"Generated minimal submission for org {org_id}")
        return submission
    
    def validate_submission(self, submission: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate submission following "be forgiving" principle.
        Returns (is_valid, list_of_issues)
        """
        issues = []
        
        # Check required fields with graceful path traversal
        for field_path in self.REQUIRED_FIELDS:
            if not self._check_nested_field(submission, field_path):
                issues.append(f"Missing required field: {field_path}")
        
        # Validate observables structure if present
        try:
            observables = submission.get('submission', {}).get('sighting', {}).get('observables', {})
            if observables and not any(observables.values()):
                issues.append("Observables section present but empty")
        except Exception as e:
            issues.append(f"Error validating observables: {str(e)}")
        
        # Validate confidence range if present
        try:
            confidence = submission.get('submission', {}).get('sighting', {}).get('confidence')
            if confidence is not None and not (0 <= confidence <= 100):
                issues.append(f"Confidence {confidence} out of range [0-100]")
        except Exception as e:
            issues.append(f"Error validating confidence: {str(e)}")
        
        is_valid = len(issues) == 0
        self.logger.info(f"Validation result: {'PASSED' if is_valid else 'FAILED'} with {len(issues)} issues")
        
        return is_valid, issues
    
    def _check_nested_field(self, data: Dict, field_path: str) -> bool:
        """
        Check if a nested field exists using dot notation.
        Returns True if field exists, False otherwise.
        """
        keys = field_path.split('.')
        current = data
        
        try:
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return False
            return current is not None
        except:
            return False
    
    def enhance_submission(self, minimal_submission: Dict[str, Any], 
                          enhancements: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Enhance a minimal submission with additional data following "strong on return" principle.
        """
        if enhancements is None:
            enhancements = {}
        
        enhanced = minimal_submission.copy()
        
        # Add format version if not present
        if 'format_version' not in enhanced.get('submission', {}):
            enhanced.setdefault('submission', {})['format_version'] = self.DEFAULTS['format_version']
        
        # Add metadata section with defaults
        metadata = enhanced['submission'].setdefault('metadata', {})
        metadata.setdefault('submission_id', f"submission-{uuid.uuid4()}")
        metadata.setdefault('format_version', self.DEFAULTS['format_version'])
        metadata.setdefault('timestamp', datetime.now(timezone.utc).isoformat())
        
        # Enhance submitter information
        submitter = enhanced['submission']['submitter']
        submitter.setdefault('submission_method', self.DEFAULTS['submission_method'])
        
        # Enhance sighting information
        sighting = enhanced['submission']['sighting']
        sighting.setdefault('severity', 'medium')
        sighting.setdefault('observation_count', 1)
        
        # Apply any custom enhancements
        self._deep_merge(enhanced, enhancements)
        
        self.logger.info("Enhanced submission with additional metadata")
        return enhanced
    
    def _deep_merge(self, base: Dict, overlay: Dict) -> None:
        """
        Deep merge overlay dictionary into base dictionary.
        """
        for key, value in overlay.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def to_yaml(self, submission: Dict[str, Any]) -> str:
        """
        Convert submission to YAML format for storage/transmission.
        """
        return yaml.dump(submission, default_flow_style=False, sort_keys=False)
    
    def from_yaml(self, yaml_str: str) -> Dict[str, Any]:
        """
        Parse submission from YAML format with error handling.
        """
        try:
            return yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            self.logger.error(f"YAML parsing error: {e}")
            raise ValueError(f"Invalid YAML format: {e}")
    
    def to_json(self, submission: Dict[str, Any]) -> str:
        """
        Convert submission to JSON format for API transmission.
        """
        return json.dumps(submission, indent=2, default=str)
    
    def from_json(self, json_str: str) -> Dict[str, Any]:
        """
        Parse submission from JSON format with error handling.
        """
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            raise ValueError(f"Invalid JSON format: {e}")


def run_tests():
    """
    Run comprehensive tests of the FRANK submission system.
    """
    print("="*60)
    print("FRANK Platform - Minimal Submission Test Suite")
    print("="*60)
    
    frank = FRANKSubmission()
    
    # Test 1: Generate minimal submission
    print("\n1. Testing minimal submission generation...")
    minimal = frank.generate_minimal_submission()
    print("✓ Minimal submission generated")
    
    # Test 2: Validate minimal submission
    print("\n2. Testing submission validation...")
    is_valid, issues = frank.validate_submission(minimal)
    if is_valid:
        print("✓ Minimal submission is valid")
    else:
        print(f"✗ Validation failed: {issues}")
    
    # Test 3: YAML serialization
    print("\n3. Testing YAML serialization...")
    yaml_output = frank.to_yaml(minimal)
    print("✓ YAML serialization successful")
    print("YAML Preview:")
    print(yaml_output[:200] + "..." if len(yaml_output) > 200 else yaml_output)
    
    # Test 4: YAML parsing
    print("\n4. Testing YAML parsing...")
    parsed_yaml = frank.from_yaml(yaml_output)
    yaml_valid, yaml_issues = frank.validate_submission(parsed_yaml)
    if yaml_valid:
        print("✓ YAML round-trip successful")
    else:
        print(f"✗ YAML round-trip failed: {yaml_issues}")
    
    # Test 5: JSON serialization
    print("\n5. Testing JSON serialization...")
    json_output = frank.to_json(minimal)
    print("✓ JSON serialization successful")
    
    # Test 6: JSON parsing
    print("\n6. Testing JSON parsing...")
    parsed_json = frank.from_json(json_output)
    json_valid, json_issues = frank.validate_submission(parsed_json)
    if json_valid:
        print("✓ JSON round-trip successful")
    else:
        print(f"✗ JSON round-trip failed: {json_issues}")
    
    # Test 7: Enhancement
    print("\n7. Testing submission enhancement...")
    enhanced = frank.enhance_submission(minimal)
    enhanced_valid, enhanced_issues = frank.validate_submission(enhanced)
    if enhanced_valid:
        print("✓ Enhanced submission is valid")
        print(f"Enhanced submission has {len(str(enhanced))} characters vs {len(str(minimal))} in minimal")
    else:
        print(f"✗ Enhanced submission invalid: {enhanced_issues}")
    
    # Test 8: Error handling - Invalid submission
    print("\n8. Testing error handling...")
    invalid_submission = {"invalid": "structure"}
    is_valid, issues = frank.validate_submission(invalid_submission)
    if not is_valid:
        print(f"✓ Invalid submission correctly rejected: {len(issues)} issues found")
    else:
        print("✗ Invalid submission incorrectly accepted")
    
    # Test 9: Custom observables
    print("\n9. Testing custom observables...")
    custom_observables = [
        {
            "id": "file-hash-test",
            "type": "file_hash",
            "value": "d41d8cd98f00b204e9800998ecf8427e"
        }
    ]
    custom_submission = frank.generate_minimal_submission(
        org_id="test-org-123",
        observables=custom_observables
    )
    custom_valid, custom_issues = frank.validate_submission(custom_submission)
    if custom_valid:
        print("✓ Custom observables submission valid")
    else:
        print(f"✗ Custom observables submission invalid: {custom_issues}")
    
    print("\n" + "="*60)
    print("Test Suite Complete")
    print("="*60)
    
    return {
        'minimal_submission': minimal,
        'enhanced_submission': enhanced,
        'yaml_format': yaml_output,
        'json_format': json_output
    }


if __name__ == "__main__":
    results = run_tests()
    
    # Save sample outputs for reference
    frank = FRANKSubmission()
    
    print("\nSaving sample files...")
    
    with open('frank_minimal_sample.yaml', 'w') as f:
        f.write(results['yaml_format'])
    print("✓ Saved frank_minimal_sample.yaml")
    
    with open('frank_enhanced_sample.yaml', 'w') as f:
        f.write(frank.to_yaml(results['enhanced_submission']))
    print("✓ Saved frank_enhanced_sample.yaml")
    
    with open('frank_minimal_sample.json', 'w') as f:
        f.write(results['json_format'])
    print("✓ Saved frank_minimal_sample.json")
    
    print("\nFRANK local development environment ready!")
    print("Next steps:")
    print("- Run this script to test basic functionality")
    print("- Extend with database storage (SQLite for local dev)")
    print("- Add API endpoints (Flask/FastAPI)")
    print("- Implement contribution scoring")
    print("- Add access level filtering")