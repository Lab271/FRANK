#!/usr/bin/env python3
"""
Unit tests for FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

Comprehensive test suite covering all functionality of the FRANKSubmission class
and related convenience functions.
"""

import unittest
import json
import yaml
from datetime import datetime, timezone
from unittest.mock import patch

# Import the module under test
from frank.core.submission import (
    FRANKSubmission,
    create_frank_submission,
    generate_minimal,
    validate_submission,
    to_yaml,
    from_yaml,
    to_json,
    from_json
)
from frank.core.exceptions import FRANKValidationError, FRANKFormatError


class TestFRANKSubmission(unittest.TestCase):
    """Test cases for the FRANKSubmission class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.frank = FRANKSubmission()
        self.valid_org_id = "test-org-123"
        self.valid_tier = "partner"
        self.valid_observables = [
            {
                "id": "test-ip-1",
                "type": "ipv4",
                "value": "192.168.1.100"
            },
            {
                "id": "test-domain-1",
                "type": "domain",
                "value": "malicious-site.com"
            }
        ]
    
    def test_init(self):
        """Test FRANKSubmission initialization."""
        frank = FRANKSubmission()
        self.assertIsNotNone(frank.logger)
        self.assertEqual(frank.DEFAULTS['confidence'], 69)
        self.assertIn('partner', frank.VALID_TIERS)
    
    def test_generate_minimal_submission_defaults(self):
        """Test generating minimal submission with default values."""
        submission = self.frank.generate_minimal_submission()
        
        # Check structure
        self.assertIn('submission', submission)
        self.assertIn('submitter', submission['submission'])
        self.assertIn('sighting', submission['submission'])
        
        # Check required fields
        submitter = submission['submission']['submitter']
        self.assertIn('organization_id', submitter)
        self.assertEqual(submitter['tier'], 'partner')  # default
        
        sighting = submission['submission']['sighting']
        self.assertIn('sighting_id', sighting)
        self.assertIn('timestamp', sighting)
        self.assertEqual(sighting['confidence'], 69)  # default
        self.assertIn('observables', sighting)
        
        # Check observables structure
        observables = sighting['observables']
        self.assertIn('network', observables)
        self.assertIsInstance(observables['network'], list)
        self.assertEqual(len(observables['network']), 2)  # default IP and domain
    
    def test_generate_minimal_submission_custom_params(self):
        """Test generating minimal submission with custom parameters."""
        submission = self.frank.generate_minimal_submission(
            org_id=self.valid_org_id,
            tier=self.valid_tier,
            observables=self.valid_observables,
            confidence=85
        )
        
        submitter = submission['submission']['submitter']
        self.assertEqual(submitter['organization_id'], self.valid_org_id)
        self.assertEqual(submitter['tier'], self.valid_tier)
        
        sighting = submission['submission']['sighting']
        self.assertEqual(sighting['confidence'], 85)
        self.assertEqual(len(sighting['observables']['network']), 2)
    
    def test_generate_minimal_submission_invalid_tier(self):
        """Test generating submission with invalid tier raises exception."""
        with self.assertRaises(FRANKValidationError) as context:
            self.frank.generate_minimal_submission(tier="invalid_tier")
        
        self.assertIn("Invalid tier", str(context.exception))
    
    def test_generate_minimal_submission_invalid_confidence(self):
        """Test generating submission with invalid confidence raises exception."""
        with self.assertRaises(FRANKValidationError):
            self.frank.generate_minimal_submission(confidence=150)
        
        with self.assertRaises(FRANKValidationError):
            self.frank.generate_minimal_submission(confidence=-10)
    
    def test_generate_minimal_submission_invalid_observable_type(self):
        """Test generating submission with invalid observable type raises exception."""
        invalid_observables = [
            {
                "id": "test-invalid-1",
                "type": "invalid_type",
                "value": "some_value"
            }
        ]
        
        with self.assertRaises(FRANKValidationError) as context:
            self.frank.generate_minimal_submission(observables=invalid_observables)
        
        self.assertIn("Invalid observable type", str(context.exception))
    
    def test_generate_comprehensive_submission(self):
        """Test generating comprehensive submission with all parameters."""
        campaign_context = {"name": "test_campaign", "actor": "test_actor"}
        sigma_detection = {"rule_id": "test-rule-123", "confidence": 0.95}
        impact_data = {"severity": "high", "affected_systems": 5}
        
        submission = self.frank.generate_comprehensive_submission(
            org_id=self.valid_org_id,
            tier=self.valid_tier,
            hit_target_org="target-org-456",
            observables=self.valid_observables,
            severity="high",
            confidence=92,
            campaign_context=campaign_context,
            sigma_detection=sigma_detection,
            impact_data=impact_data
        )
        
        # Check metadata
        self.assertIn('metadata', submission['submission'])
        metadata = submission['submission']['metadata']
        self.assertIn('submission_id', metadata)
        self.assertIn('format_version', metadata)
        
        # Check hit target
        self.assertIn('hit_target', submission['submission'])
        hit_target = submission['submission']['hit_target']
        self.assertEqual(hit_target['organization_id'], "target-org-456")
        
        # Check enhanced sighting
        sighting = submission['submission']['sighting']
        self.assertEqual(sighting['severity'], "high")
        self.assertIn('first_observed', sighting)
        self.assertIn('last_observed', sighting)
        self.assertIn('sigma_detection', sighting)
        self.assertIn('threat_context', sighting)
        self.assertIn('impact', sighting)
        
        # Check sharing preferences
        self.assertIn('sharing', submission['submission'])
        sharing = submission['submission']['sharing']
        self.assertIn('distribution_level', sharing)
        self.assertIn('anonymization_level', sharing)
    
    def test_validate_submission_valid(self):
        """Test validation of valid submission."""
        submission = self.frank.generate_minimal_submission()
        is_valid, issues = validate_submission(submission)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)
    
    def test_validate_submission_missing_required_fields(self):
        """Test validation catches missing required fields."""
        incomplete_submission = {
            "submission": {
                "submitter": {
                    "organization_id": "test-org"
                    # Missing tier
                }
                # Missing sighting entirely
            }
        }
        
        is_valid, issues = validate_submission(incomplete_submission)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(issues), 0)
        
        # Check specific missing fields are reported
        issue_text = " ".join(issues)
        self.assertIn("submission.submitter.tier", issue_text)
        self.assertIn("submission.sighting", issue_text)
    
    def test_validate_submission_invalid_enums(self):
        """Test validation catches invalid enumerated values."""
        submission = self.frank.generate_minimal_submission()
        
        # Make it invalid
        submission['submission']['submitter']['tier'] = 'invalid_tier'
        submission['submission']['sighting']['severity'] = 'invalid_severity'
        submission['submission']['sighting']['confidence'] = 150
        
        # Add invalid sharing TLP
        submission['submission']['sharing'] = {'distribution_level': 'INVALID_TLP'}
        
        is_valid, issues = self.frank.validate_submission(submission)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(issues), 0)
        
        issue_text = " ".join(issues)
        self.assertIn("Invalid tier", issue_text)
        self.assertIn("Invalid severity", issue_text)
        self.assertIn("Confidence 150 out of range", issue_text)
        self.assertIn("Invalid TLP level", issue_text)
    
    def test_validate_submission_empty_observables(self):
        """Test validation catches empty observables."""
        submission = self.frank.generate_minimal_submission()
        submission['submission']['sighting']['observables'] = {'network': []}
        
        is_valid, issues = self.frank.validate_submission(submission)
        
        self.assertFalse(is_valid)
        self.assertIn("Observables section present but empty", " ".join(issues))
    
    def test_validate_submission_malformed_observables(self):
        """Test validation catches malformed observables."""
        submission = self.frank.generate_minimal_submission()
        submission['submission']['sighting']['observables'] = {
            'network': [
                {'type': 'ipv4'},  # Missing value
                {'value': '1.2.3.4', 'type': 'invalid_type'}  # Invalid type
            ]
        }
        
        is_valid, issues = self.frank.validate_submission(submission)
        
        self.assertFalse(is_valid)
        issue_text = " ".join(issues)
        self.assertIn("Missing 'value'", issue_text)
        self.assertIn("Invalid observable type", issue_text)
    
    def test_validate_submission_exception_handling(self):
        """Test validation handles exceptions gracefully."""
        # Pass something that will cause an exception during validation
        invalid_input = {"hello": "world"}
        
        is_valid, issues = self.frank.validate_submission(invalid_input)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(issues), 0)
        self.assertIn("Missing required field:", " ".join(issues))
    
    def test_check_nested_field(self):
        """Test nested field checking utility method."""
        data = {
            'level1': {
                'level2': {
                    'level3': 'value'
                }
            },
            'empty_value': None
        }
        
        # Existing field
        self.assertTrue(self.frank._check_nested_field(data, 'level1.level2.level3'))
        
        # Non-existing field
        self.assertFalse(self.frank._check_nested_field(data, 'level1.nonexistent'))
        
        # Deeper non-existing field
        self.assertFalse(self.frank._check_nested_field(data, 'level1.level2.level3.level4'))
        
        # None value should return False
        self.assertFalse(self.frank._check_nested_field(data, 'empty_value'))
        
        # Edge cases
        self.assertFalse(self.frank._check_nested_field({}, 'any.field'))
        self.assertFalse(self.frank._check_nested_field(data, 'level1.level2.level3.nonexistent'))
    
    def test_get_nested_field(self):
        """Test nested field getter utility method."""
        data = {
            'level1': {
                'level2': {
                    'level3': 'value'
                }
            },
            'list_field': [1, 2, 3]
        }
        
        # Existing field
        self.assertEqual(self.frank._get_nested_field(data, 'level1.level2.level3'), 'value')
        
        # Non-existing field
        self.assertIsNone(self.frank._get_nested_field(data, 'level1.nonexistent'))
        
        # Partial path exists
        result = self.frank._get_nested_field(data, 'level1.level2')
        self.assertEqual(result, {'level3': 'value'})
        
        # List field
        self.assertEqual(self.frank._get_nested_field(data, 'list_field'), [1, 2, 3])
    
    def test_enhance_submission(self):
        """Test submission enhancement functionality."""
        minimal = self.frank.generate_minimal_submission()
        
        enhancements = {
            'submission': {
                'sighting': {
                    'severity': 'critical',
                    'custom_field': 'custom_value'
                },
                'custom_section': {
                    'data': 'test'
                }
            }
        }
        
        enhanced = self.frank.enhance_submission(minimal, enhancements)
        
        # Should have metadata added
        self.assertIn('metadata', enhanced['submission'])
        metadata = enhanced['submission']['metadata']
        self.assertIn('submission_id', metadata)
        self.assertIn('format_version', metadata)
        
        # Should have enhanced fields
        sighting = enhanced['submission']['sighting']
        self.assertEqual(sighting['severity'], 'critical')
        self.assertEqual(sighting['custom_field'], 'custom_value')
        
        # Should have new section
        self.assertIn('custom_section', enhanced['submission'])
        self.assertEqual(enhanced['submission']['custom_section']['data'], 'test')
        
        # Should have default submission method
        submitter = enhanced['submission']['submitter']
        self.assertEqual(submitter['submission_method'], 'manual')
    
    def test_deep_copy(self):
        """Test deep copy utility method."""
        original = {
            'dict': {'nested': 'value'},
            'list': [1, {'nested_in_list': 'value'}],
            'simple': 'value'
        }
        
        copied = self.frank._deep_copy(original)
        
        # Should be equal but not the same object
        self.assertEqual(copied, original)
        self.assertIsNot(copied, original)
        
        # Nested objects should also be different
        self.assertIsNot(copied['dict'], original['dict'])
        self.assertIsNot(copied['list'], original['list'])
        self.assertIsNot(copied['list'][1], original['list'][1])
        
        # Modifying copy shouldn't affect original
        copied['dict']['nested'] = 'modified'
        self.assertEqual(original['dict']['nested'], 'value')
    
    def test_deep_merge(self):
        """Test deep merge utility method."""
        base = {
            'existing': {
                'keep': 'original',
                'overwrite': 'original'
            },
            'simple': 'original'
        }
        
        overlay = {
            'existing': {
                'overwrite': 'new',
                'add': 'added'
            },
            'new_section': 'new'
        }
        
        self.frank._deep_merge(base, overlay)
        
        # Should merge nested dicts
        self.assertEqual(base['existing']['keep'], 'original')
        self.assertEqual(base['existing']['overwrite'], 'new')
        self.assertEqual(base['existing']['add'], 'added')
        
        # Should add new top-level keys
        self.assertEqual(base['new_section'], 'new')
        
        # Simple values should be overwritten
        self.assertEqual(base['simple'], 'original')
    
    def test_hash_observable(self):
        """Test observable hashing functionality."""
        hash1 = self.frank.hash_observable('ipv4', '192.168.1.1')
        hash2 = self.frank.hash_observable('ipv4', '192.168.1.1')
        hash3 = self.frank.hash_observable('ipv4', '192.168.1.2')
        hash4 = self.frank.hash_observable('domain', '192.168.1.1')
        
        # Same type and value should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Different values should produce different hashes
        self.assertNotEqual(hash1, hash3)
        
        # Different types should produce different hashes
        self.assertNotEqual(hash1, hash4)
        
        # Should be deterministic
        self.assertEqual(len(hash1), 64)  # SHA256 hex length
    
    def test_extract_observables(self):
        """Test observable extraction functionality."""
        submission = self.frank.generate_comprehensive_submission(
            org_id=self.valid_org_id,
            observables=self.valid_observables
        )
        
        extracted = self.frank.extract_observables(submission)
        
        self.assertEqual(len(extracted), 2)
        
        # Check structure of extracted observables
        obs1 = extracted[0]
        self.assertIn('id', obs1)
        self.assertIn('type', obs1)
        self.assertIn('value', obs1)
        self.assertIn('category', obs1)
        self.assertIn('hash', obs1)
        
        # Should have correct category
        self.assertEqual(obs1['category'], 'network')
        
        # Hash should be computed
        expected_hash = self.frank.hash_observable(obs1['type'], obs1['value'])
        self.assertEqual(obs1['hash'], expected_hash)
    
    def test_extract_observables_empty_submission(self):
        """Test observable extraction from submission without observables."""
        submission = {'submission': {'sighting': {}}}
        extracted = self.frank.extract_observables(submission)
        self.assertEqual(len(extracted), 0)
    
    def test_to_yaml(self):
        """Test YAML conversion functionality."""
        submission = self.frank.generate_minimal_submission()
        yaml_str = self.frank.to_yaml(submission)
        
        self.assertIsInstance(yaml_str, str)
        self.assertIn('submission:', yaml_str)
        self.assertIn('submitter:', yaml_str)
        self.assertIn('sighting:', yaml_str)
        
        # Should be valid YAML
        parsed = yaml.safe_load(yaml_str)
        self.assertEqual(parsed['submission']['submitter']['tier'], 'partner')
    
    def test_from_yaml(self):
        """Test YAML parsing functionality."""
        yaml_str = """
submission:
  submitter:
    organization_id: test-org
    tier: partner
  sighting:
    sighting_id: test-sighting
    timestamp: "2023-01-01T00:00:00Z"
    confidence: 75
    observables:
      network:
        - id: test-ip
          type: ipv4
          value: 1.2.3.4
"""
        
        submission = self.frank.from_yaml(yaml_str)
        
        self.assertIn('submission', submission)
        self.assertEqual(submission['submission']['submitter']['tier'], 'partner')
        self.assertEqual(submission['submission']['sighting']['confidence'], 75)
    
    def test_from_yaml_invalid(self):
        """Test YAML parsing with invalid YAML raises exception."""
        invalid_yaml = "{ invalid: yaml: content: }"
        
        with self.assertRaises(FRANKFormatError) as context:
            self.frank.from_yaml(invalid_yaml)
        
        self.assertIn("Invalid YAML format", str(context.exception))
    
    def test_to_json(self):
        """Test JSON conversion functionality."""
        submission = self.frank.generate_minimal_submission()
        json_str = self.frank.to_json(submission)
        
        self.assertIsInstance(json_str, str)
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        self.assertEqual(parsed['submission']['submitter']['tier'], 'partner')
    
    def test_from_json(self):
        """Test JSON parsing functionality."""
        json_str = """
{
  "submission": {
    "submitter": {
      "organization_id": "test-org",
      "tier": "partner"
    },
    "sighting": {
      "sighting_id": "test-sighting",
      "timestamp": "2023-01-01T00:00:00Z",
      "confidence": 75,
      "observables": {
        "network": [
          {
            "id": "test-ip",
            "type": "ipv4",
            "value": "1.2.3.4"
          }
        ]
      }
    }
  }
}
"""
        
        submission = self.frank.from_json(json_str)
        
        self.assertIn('submission', submission)
        self.assertEqual(submission['submission']['submitter']['tier'], 'partner')
        self.assertEqual(submission['submission']['sighting']['confidence'], 75)
    
    def test_from_json_invalid(self):
        """Test JSON parsing with invalid JSON raises exception."""
        invalid_json = "{ invalid json content }"
        
        with self.assertRaises(FRANKFormatError) as context:
            self.frank.from_json(invalid_json)
        
        self.assertIn("Invalid JSON format", str(context.exception))
    
    def test_normalize_submission(self):
        """Test submission normalization functionality."""
        # Create minimal submission
        submission = self.frank.generate_minimal_submission()
        
        # Remove some optional fields to test normalization
        del submission['submission']['sighting']['confidence']
        
        normalized = self.frank.normalize_submission(submission)
        
        # Should have defaults filled in
        sighting = normalized['submission']['sighting']
        self.assertEqual(sighting['confidence'], 69)  # default
        self.assertEqual(sighting['severity'], 'medium')  # default
        
        # Should have metadata
        self.assertIn('metadata', normalized['submission'])
        metadata = normalized['submission']['metadata']
        self.assertIn('format_version', metadata)
        self.assertIn('submission_id', metadata)
        
        # Should have IDs for observables
        observables = normalized['submission']['sighting']['observables']['network']
        for obs in observables:
            self.assertIn('id', obs)
    
    def test_normalize_submission_invalid(self):
        """Test normalization rejects invalid submissions."""
        invalid_submission = {"invalid": "structure"}
        
        with self.assertRaises(FRANKValidationError) as context:
            self.frank.normalize_submission(invalid_submission)
        
        self.assertIn("Cannot normalize invalid submission", str(context.exception))
    
    def test_normalize_submission_timestamp_handling(self):
        """Test timestamp normalization in submissions."""
        submission = self.frank.generate_minimal_submission()
        
        # Test with Z timezone
        submission['submission']['sighting']['timestamp'] = "2023-01-01T12:00:00Z"
        normalized = self.frank.normalize_submission(submission)
        
        # Should be converted to proper ISO format
        timestamp = normalized['submission']['sighting']['timestamp']
        self.assertIn("+00:00", timestamp)
        
        # Test with invalid timestamp
        submission['submission']['sighting']['timestamp'] = "invalid-timestamp"
        normalized = self.frank.normalize_submission(submission)
        
        # Should be replaced with current timestamp
        timestamp = normalized['submission']['sighting']['timestamp']
        self.assertIsNotNone(timestamp)


class TestFRANKSubmissionFactory(unittest.TestCase):
    """Test cases for factory function and convenience functions."""
    
    def test_create_frank_submission(self):
        """Test factory function creates proper instance."""
        frank = create_frank_submission()
        self.assertIsInstance(frank, FRANKSubmission)
    
    def test_generate_minimal_convenience(self):
        """Test convenience function for generating minimal submission."""
        submission = generate_minimal("test-org-123", tier="partner")
        
        self.assertIn('submission', submission)
        self.assertEqual(submission['submission']['submitter']['organization_id'], "test-org-123")
        self.assertEqual(submission['submission']['submitter']['tier'], "partner")
    
    def test_validate_submission_convenience(self):
        """Test convenience function for validation."""
        submission = generate_minimal()
        is_valid, issues = validate_submission(submission)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)
    
    def test_yaml_conversion_convenience(self):
        """Test convenience functions for YAML conversion."""
        submission = generate_minimal()
        
        # Convert to YAML
        yaml_str = to_yaml(submission)
        self.assertIsInstance(yaml_str, str)
        
        # Parse back from YAML
        parsed = from_yaml(yaml_str)
        self.assertEqual(parsed['submission']['submitter']['tier'], 'partner')
    
    def test_json_conversion_convenience(self):
        """Test convenience functions for JSON conversion."""
        submission = generate_minimal()
        
        # Convert to JSON
        json_str = to_json(submission)
        self.assertIsInstance(json_str, str)
        
        # Parse back from JSON
        parsed = from_json(json_str)
        self.assertEqual(parsed['submission']['submitter']['tier'], 'partner')


class TestFRANKSubmissionEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        self.frank = FRANKSubmission()
    
    def test_very_large_submission(self):
        """Test handling of submissions with many observables."""
        # Create submission with many observables
        many_observables = []
        for i in range(1000):
            many_observables.append({
                "id": f"obs-{i}",
                "type": "ipv4",
                "value": f"192.168.{i//256}.{i%256}"
            })
        
        submission = self.frank.generate_minimal_submission(observables=many_observables)
        
        # Should handle large submissions
        is_valid, issues = self.frank.validate_submission(submission)
        self.assertTrue(is_valid)
        
        # Should extract all observables
        extracted = self.frank.extract_observables(submission)
        self.assertEqual(len(extracted), 1000)
    
    def test_unicode_and_special_characters(self):
        """Test handling of unicode and special characters."""
        unicode_observables = [
            {
                "id": "unicode-test",
                "type": "domain",
                "value": "тест.рф"  # Cyrillic domain
            },
            {
                "id": "special-chars",
                "type": "domain", 
                "value": "test-site_with.special-chars.com"
            }
        ]
        
        submission = self.frank.generate_minimal_submission(
            org_id="тест-орг",  # Unicode org ID
            observables=unicode_observables
        )
        
        # Should handle unicode correctly
        is_valid, issues = self.frank.validate_submission(submission)
        self.assertTrue(is_valid)
        
        # Should convert to/from formats correctly
        yaml_str = self.frank.to_yaml(submission)
        json_str = self.frank.to_json(submission)
        
        yaml_parsed = self.frank.from_yaml(yaml_str)
        json_parsed = self.frank.from_json(json_str)
        
        self.assertEqual(yaml_parsed['submission']['submitter']['organization_id'], "тест-орг")
        self.assertEqual(json_parsed['submission']['submitter']['organization_id'], "тест-орг")
    
    def test_nested_field_with_none_values(self):
        """Test nested field handling with None values."""
        data_with_nones = {
            'level1': {
                'level2': None,
                'other_field': 'value'
            },
            'none_field': None
        }
        
        # None values should be treated as non-existent
        self.assertFalse(self.frank._check_nested_field(data_with_nones, 'level1.level2'))
        self.assertFalse(self.frank._check_nested_field(data_with_nones, 'none_field'))
        
        # But should return actual None value with _get_nested_field
        self.assertIsNone(self.frank._get_nested_field(data_with_nones, 'level1.level2'))
        self.assertIsNone(self.frank._get_nested_field(data_with_nones, 'none_field'))
    
    def test_boundary_confidence_values(self):
        """Test boundary values for confidence scores."""
        # Test boundary values
        for confidence in [0, 1, 50, 99, 100]:
            submission = self.frank.generate_minimal_submission(confidence=confidence)
            is_valid, issues = self.frank.validate_submission(submission)
            self.assertTrue(is_valid, f"Confidence {confidence} should be valid")
    
    @patch('frank.core.submission.datetime')
    def test_timestamp_generation(self, mock_datetime):
        """Test timestamp generation with mocked datetime."""
        # Mock datetime to return fixed time
        fixed_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_time
        mock_datetime.fromisoformat = datetime.fromisoformat  # Keep real implementation
        
        submission = self.frank.generate_minimal_submission()
        
        timestamp = submission['submission']['sighting']['timestamp']
        self.assertEqual(timestamp, fixed_time.isoformat())
    
    def test_empty_observables_categories(self):
        """Test handling of empty observable categories."""
        submission = self.frank.generate_minimal_submission()
        
        # Add empty categories
        submission['submission']['sighting']['observables']['files'] = []
        submission['submission']['sighting']['observables']['emails'] = []
        
        # Should still be valid
        is_valid, issues = self.frank.validate_submission(submission)
        self.assertTrue(is_valid)
        
        # Extract should only return network observables
        extracted = self.frank.extract_observables(submission)
        categories = {obs['category'] for obs in extracted}
        self.assertEqual(categories, {'network'})


if __name__ == '__main__':
    # Configure test runner
    unittest.main(
        verbosity=2,
        failfast=False,
        buffer=True
    )