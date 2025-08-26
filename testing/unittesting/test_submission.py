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
    FRANKValidator,
    validate_submission,
    validate_submission_dict,
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
        self.minimal = {
            "submission": {
                "submitter": {
                    "organization_id": "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
                    "tier": "partner"
                },
                "sighting": {
                    "sighting_id": "sighting-ee20065d-2555-424f-ad9e-0f8428623c75",
                    "timestamp": "2025-01-20T14:30:22Z",
                    #"confidence": 87,
                    "observables": {
                        "network": [
                            {
                                "id": "ipv4-addr-c4e54321-1234-5678-9abc-def012345678",
                                "type": "ipv4",
                                "value": "185.220.102.45"
                            },
                            {
                                "id": "domain-name-d5f65432-2345-6789-abcd-ef0123456789",
                                "type": "domain",
                                "value": "secure-bank-verify.nl"
                            }
                        ]
                    }
                }
            }
        }

    def _generate_minimal_submission(self):
        """Return a minimal valid FRANKSubmission instance for tests."""
        return FRANKSubmission.from_dict(self.minimal)
    
    def test_empty_submission(self):
        """Test empty FRANKSubmission initialization"""
        submission = FRANKSubmission.from_dict({})
        self.assertEqual(submission.confidence, 69)
        self.assertEqual(submission.submitter_tier, None)
        submission_dict = submission.to_dict()
        self.assertEqual(submission_dict, {'submission': {}})

    def test_init_from_dict(self):
        """Test FRANKSubmission initialization."""       
        submission = self._generate_minimal_submission()
        self.assertEqual(submission.confidence, 69)
        self.assertEqual(submission.submitter_org_id, self.minimal['submission']['submitter']['organization_id'])
        self.assertEqual(submission.submitter_tier, self.minimal['submission']['submitter']['tier'])
    
    def test_validate_submission_valid(self):
        """Test validation of valid submission."""
        submission = self._generate_minimal_submission()
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
        
        is_valid, issues = validate_submission(FRANKSubmission.from_dict(incomplete_submission))
        
        self.assertFalse(is_valid)
        self.assertGreater(len(issues), 0)
        
        # Check specific missing fields are reported
        issue_text = " ".join(issues)
        self.assertIn("submission.submitter.tier", issue_text)
        self.assertIn("submission.sighting", issue_text)
    
    def test_validate_submission_invalid_enums(self):
        """Test validation catches invalid enumerated values."""
        submission = self._generate_minimal_submission()
        
        # Make it invalid
        submission.submitter_tier = 'invalid_tier'
        submission.severity = 'invalid_severity'
        submission.confidence = 150
        
        # Add invalid sharing TLP
        submission.sharing = {'distribution_level': 'INVALID_TLP'}
        
        is_valid, issues = validate_submission(submission)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(issues), 0)
        
        issue_text = " ".join(issues)
        self.assertIn("Invalid tier", issue_text)
        self.assertIn("Invalid severity", issue_text)
        self.assertIn("Confidence 150 out of range", issue_text)
        self.assertIn("Invalid TLP level", issue_text)
    
    def test_validate_submission_empty_observables(self):
        """Test validation catches empty observables."""
        submission = self._generate_minimal_submission()
        submission.observables = {'network': []}
        
        is_valid, issues = validate_submission(submission)
        
        self.assertFalse(is_valid)
        self.assertIn("Observables section present but empty", " ".join(issues))
    
    def test_validate_submission_malformed_observables(self):
        """Test validation catches malformed observables."""
        submission = self._generate_minimal_submission()
        submission.observables = {
            'network': [
                {'type': 'ipv4'},  # Missing value
                {'value': '1.2.3.4', 'type': 'invalid_type'}  # Invalid type
            ]
        }
        
        is_valid, issues = validate_submission(submission)
        
        self.assertFalse(is_valid)
        issue_text = " ".join(issues)
        self.assertIn("Missing 'value'", issue_text)
        self.assertIn("Invalid observable type", issue_text)
    
    def test_validate_submission_exception_handling(self):
        """Test validation handles exceptions gracefully."""
        # Pass something that will cause an exception during validation
        invalid_input = {"hello": "world"}
        
        is_valid, issues = validate_submission_dict(invalid_input)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(issues), 0)
        self.assertIn("Missing required field:", " ".join(issues))
    
    def test_check_nested_field(self):
        """Test nested field checking utility method."""
        validator = FRANKValidator()
        data = {
            'level1': {
                'level2': {
                    'level3': 'value'
                }
            },
            'empty_value': None
        }
        
        # Existing field
        self.assertTrue(validator._check_nested_field(data, 'level1.level2.level3'))
        
        # Non-existing field
        self.assertFalse(validator._check_nested_field(data, 'level1.nonexistent'))
        
        # Deeper non-existing field
        self.assertFalse(validator._check_nested_field(data, 'level1.level2.level3.level4'))
        
        # None value should return False
        self.assertFalse(validator._check_nested_field(data, 'empty_value'))
        
        # Edge cases
        self.assertFalse(validator._check_nested_field({}, 'any.field'))
        self.assertFalse(validator._check_nested_field(data, 'level1.level2.level3.nonexistent'))
    
    def test_get_nested_field(self):
        """Test nested field getter utility method."""
        validator = FRANKValidator()
        data = {
            'level1': {
                'level2': {
                    'level3': 'value'
                }
            },
            'list_field': [1, 2, 3]
        }
        
        # Existing field
        self.assertEqual(validator._get_nested_field(data, 'level1.level2.level3'), 'value')
        
        # Non-existing field
        self.assertIsNone(validator._get_nested_field(data, 'level1.nonexistent'))
        
        # Partial path exists
        result = validator._get_nested_field(data, 'level1.level2')
        self.assertEqual(result, {'level3': 'value'})
        
        # List field
        self.assertEqual(validator._get_nested_field(data, 'list_field'), [1, 2, 3])
    

    
    def test_to_yaml(self):
        """Test YAML conversion functionality."""
        submission = self._generate_minimal_submission()
        yaml_str = to_yaml(submission)
        
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
        
        submission = from_yaml(yaml_str)
        
        self.assertEqual(submission.submitter_tier, 'partner')
        self.assertEqual(submission.confidence, 75)
    
    def test_from_yaml_invalid(self):
        """Test YAML parsing with invalid YAML raises exception."""
        invalid_yaml = "{ invalid: yaml: content: }"
        
        with self.assertRaises(FRANKFormatError) as context:
            from_yaml(invalid_yaml)
        
        self.assertIn("Invalid YAML format", str(context.exception))
    
    def test_to_json(self):
        """Test JSON conversion functionality."""
        submission = self._generate_minimal_submission()
        json_str = to_json(submission)
        
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
        
        submission = from_json(json_str)
        
        self.assertEqual(submission.submitter_tier, 'partner')
        self.assertEqual(submission.confidence, 75)
    
    def test_from_json_invalid(self):
        """Test JSON parsing with invalid JSON raises exception."""
        invalid_json = "{ invalid json content }"
        
        with self.assertRaises(FRANKFormatError) as context:
            from_json(invalid_json)
        
        self.assertIn("Invalid JSON format", str(context.exception))
    



# class TestFRANKSubmissionFactory(unittest.TestCase):
#     """Test cases for factory function and convenience functions."""
    
#     def test_create_frank_submission(self):
#         """Test factory function creates proper instance."""
#         frank = create_frank_submission()
#         self.assertIsInstance(frank, FRANKSubmission)
    
#     def test_generate_minimal_convenience(self):
#         """Test convenience function for generating minimal submission."""
#         submission = generate_minimal("test-org-123", tier="partner")
        
#         self.assertIn('submission', submission)
#         self.assertEqual(submission['submission']['submitter']['organization_id'], "test-org-123")
#         self.assertEqual(submission['submission']['submitter']['tier'], "partner")
    
#     def test_validate_submission_convenience(self):
#         """Test convenience function for validation."""
#         submission = generate_minimal()
#         is_valid, issues = validate_submission(submission)
        
#         self.assertTrue(is_valid)
#         self.assertEqual(len(issues), 0)
    
#     def test_yaml_conversion_convenience(self):
#         """Test convenience functions for YAML conversion."""
#         submission = generate_minimal()
        
#         # Convert to YAML
#         yaml_str = to_yaml(submission)
#         self.assertIsInstance(yaml_str, str)
        
#         # Parse back from YAML
#         parsed = from_yaml(yaml_str)
#         self.assertEqual(parsed['submission']['submitter']['tier'], 'partner')
    
#     def test_json_conversion_convenience(self):
#         """Test convenience functions for JSON conversion."""
#         submission = generate_minimal()
        
#         # Convert to JSON
#         json_str = to_json(submission)
#         self.assertIsInstance(json_str, str)
        
#         # Parse back from JSON
#         parsed = from_json(json_str)
#         self.assertEqual(parsed['submission']['submitter']['tier'], 'partner')


# class TestFRANKSubmissionEdgeCases(unittest.TestCase):
#     """Test edge cases and error conditions."""
    
#     def setUp(self):
#         self.frank = FRANKSubmission()
    
#     def test_very_large_submission(self):
#         """Test handling of submissions with many observables."""
#         # Create submission with many observables
#         many_observables = []
#         for i in range(1000):
#             many_observables.append({
#                 "id": f"obs-{i}",
#                 "type": "ipv4",
#                 "value": f"192.168.{i//256}.{i%256}"
#             })
        
#         submission = self.frank.generate_minimal_submission(observables=many_observables)
        
#         # Should handle large submissions
#         is_valid, issues = self.frank.validate_submission(submission)
#         self.assertTrue(is_valid)
        
#         # Should extract all observables
#         extracted = self.frank.extract_observables(submission)
#         self.assertEqual(len(extracted), 1000)
    
#     def test_unicode_and_special_characters(self):
#         """Test handling of unicode and special characters."""
#         unicode_observables = [
#             {
#                 "id": "unicode-test",
#                 "type": "domain",
#                 "value": "тест.рф"  # Cyrillic domain
#             },
#             {
#                 "id": "special-chars",
#                 "type": "domain", 
#                 "value": "test-site_with.special-chars.com"
#             }
#         ]
        
#         submission = self.frank.generate_minimal_submission(
#             org_id="тест-орг",  # Unicode org ID
#             observables=unicode_observables
#         )
        
#         # Should handle unicode correctly
#         is_valid, issues = self.frank.validate_submission(submission)
#         self.assertTrue(is_valid)
        
#         # Should convert to/from formats correctly
#         yaml_str = self.frank.to_yaml(submission)
#         json_str = self.frank.to_json(submission)
        
#         yaml_parsed = self.frank.from_yaml(yaml_str)
#         json_parsed = self.frank.from_json(json_str)
        
#         self.assertEqual(yaml_parsed['submission']['submitter']['organization_id'], "тест-орг")
#         self.assertEqual(json_parsed['submission']['submitter']['organization_id'], "тест-орг")
    
#     def test_nested_field_with_none_values(self):
#         """Test nested field handling with None values."""
#         data_with_nones = {
#             'level1': {
#                 'level2': None,
#                 'other_field': 'value'
#             },
#             'none_field': None
#         }
        
#         # None values should be treated as non-existent
#         self.assertFalse(self.frank._check_nested_field(data_with_nones, 'level1.level2'))
#         self.assertFalse(self.frank._check_nested_field(data_with_nones, 'none_field'))
        
#         # But should return actual None value with _get_nested_field
#         self.assertIsNone(self.frank._get_nested_field(data_with_nones, 'level1.level2'))
#         self.assertIsNone(self.frank._get_nested_field(data_with_nones, 'none_field'))
    
#     def test_boundary_confidence_values(self):
#         """Test boundary values for confidence scores."""
#         # Test boundary values
#         for confidence in [0, 1, 50, 99, 100]:
#             submission = self.frank.generate_minimal_submission(confidence=confidence)
#             is_valid, issues = self.frank.validate_submission(submission)
#             self.assertTrue(is_valid, f"Confidence {confidence} should be valid")
    
#     @patch('frank.core.submission.datetime')
#     def test_timestamp_generation(self, mock_datetime):
#         """Test timestamp generation with mocked datetime."""
#         # Mock datetime to return fixed time
#         fixed_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
#         mock_datetime.now.return_value = fixed_time
#         mock_datetime.fromisoformat = datetime.fromisoformat  # Keep real implementation
        
#         submission = self.frank.generate_minimal_submission()
        
#         timestamp = submission['submission']['sighting']['timestamp']
#         self.assertEqual(timestamp, fixed_time.isoformat())
    
#     def test_empty_observables_categories(self):
#         """Test handling of empty observable categories."""
#         submission = self.frank.generate_minimal_submission()
        
#         # Add empty categories
#         submission['submission']['sighting']['observables']['files'] = []
#         submission['submission']['sighting']['observables']['emails'] = []
        
#         # Should still be valid
#         is_valid, issues = self.frank.validate_submission(submission)
#         self.assertTrue(is_valid)
        
#         # Extract should only return network observables
#         extracted = self.frank.extract_observables(submission)
#         categories = {obs['category'] for obs in extracted}
#         self.assertEqual(categories, {'network'})


# if __name__ == '__main__':
#     # Configure test runner
#     unittest.main(
#         verbosity=2,
#         failfast=False,
#         buffer=True
#     )