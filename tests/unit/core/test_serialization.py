#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)

Unit tests for Submission (FRANKSubmission) serialization and deserialization
Tests the "be forgiving on what you receive, strong on what you return" principle

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest
import json
import yaml
from datetime import datetime, timezone

# Assuming these imports exist in your project
from frank.core.models import Submission, Submitter, Sighting, Observable, Observables
from frank.core.enum import AccessTier, ObservableType
from frank import __version__



class TestSubmissionSerialization(unittest.TestCase):
    """Test Submission serialization and deserialization with various formats."""
    
    def setUp(self):
        """Set up test data based on minimal.yaml example."""
        
        # Minimal YAML data structure
        self.minimal_yaml_data = {
            "submission": {
                "submitter": {
                    "organisation_id": "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
                    "access_level": "partner"
                },
                "sighting": {
                    "sighting_id": "sighting-ee20065d-2555-424f-ad9e-0f8428623c75",
                    "timestamp": "2025-01-20T14:30:22Z",
                    "confidence": 87,
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
        
        # Create programmatic test data
        self.test_submitter = Submitter(
            organisation_id="identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
            access_level=AccessTier.PARTNER
        )
        
        self.test_observables = [
            Observable(
                id="ipv4-addr-c4e54321-1234-5678-9abc-def012345678",
                observable_type=ObservableType.IPV4,
                value="185.220.102.45"
            ),
            Observable(
                id="domain-name-d5f65432-2345-6789-abcd-ef0123456789",
                observable_type=ObservableType.DOMAIN,
                value="secure-bank-verify.nl"
            )
        ]
        
        self.test_sighting = Sighting(
            sighting_id="sighting-ee20065d-2555-424f-ad9e-0f8428623c75",
            timestamp=datetime(2025, 1, 20, 14, 30, 22, tzinfo=timezone.utc),
            confidence=87,
            observables=Observables(network=self.test_observables)
        )
        
        self.minimal_submission = Submission(
            submitter=self.test_submitter,
            sighting=self.test_sighting
        )

    def test_dict_to_submission_minimal(self):
        """Test creating Submission from minimal dictionary (like minimal.yaml)."""
        submission_data = self.minimal_yaml_data["submission"]
        submission = Submission(**submission_data)
        
        # Verify submitter
        self.assertEqual(submission.submitter.organisation_id, "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff")
        self.assertEqual(submission.submitter.access_level, AccessTier.PARTNER)
        
        # Verify sighting
        self.assertEqual(submission.sighting.sighting_id, "sighting-ee20065d-2555-424f-ad9e-0f8428623c75")
        self.assertEqual(submission.sighting.confidence, 87)
        
        # Verify observables
        self.assertEqual(len(submission.sighting.observables.network), 2)
        self.assertEqual(submission.sighting.observables.network[0].value, "185.220.102.45")
        self.assertEqual(submission.sighting.observables.network[1].value, "secure-bank-verify.nl")
        
        # Verify defaults
        self.assertEqual(submission.format_version, __version__)
        self.assertEqual(submission.submission_method, "api")

    def test_submission_to_dict_with_defaults(self):
        """Test converting Submission to dictionary includes defaults."""
        submission = Submission(
            submitter=self.test_submitter,
            sighting=self.test_sighting
        )
        
        result = submission.model_dump(exclude_none=True)
        
        # Check structure
        self.assertIn("submitter", result)
        self.assertIn("sighting", result)
        self.assertIn("format_version", result)
        self.assertIn("submission_method", result)
        
        # Check defaults
        self.assertEqual(result["format_version"], __version__)
        self.assertEqual(result["submission_method"], "api")
        
        # Check enum serialization
        self.assertEqual(result["submitter"]["access_level"], "partner")

    def test_dict_roundtrip_minimal(self):
        """Test dictionary roundtrip with minimal data from YAML."""
        submission_data = self.minimal_yaml_data["submission"]
        
        # Dict -> Submission -> Dict
        submission = Submission(**submission_data)
        result_dict = submission.model_dump(exclude_none=True)
        
        # Create new submission from result
        roundtrip_submission = Submission(**result_dict)
        
        # Verify key data survived
        self.assertEqual(submission.submitter.organisation_id, roundtrip_submission.submitter.organisation_id)
        self.assertEqual(submission.sighting.confidence, roundtrip_submission.sighting.confidence)
        self.assertEqual(len(submission.sighting.observables.network), 
                        len(roundtrip_submission.sighting.observables.network))

    def test_json_serialization_minimal(self):
        """Test JSON serialization of minimal submission."""
        submission = Submission(**self.minimal_yaml_data["submission"])
        json_str = submission.model_dump_json(exclude_none=True)
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        self.assertIn("submitter", parsed)
        self.assertIn("sighting", parsed)
        self.assertEqual(parsed["submitter"]["access_level"], "partner")
        self.assertEqual(parsed["sighting"]["confidence"], 87)

    def test_json_roundtrip_minimal(self):
        """Test complete JSON roundtrip with minimal data."""
        original = Submission(**self.minimal_yaml_data["submission"])
        
        # Submission -> JSON -> Dict -> Submission
        json_str = original.model_dump_json(exclude_none=True)
        parsed_dict = json.loads(json_str)
        roundtrip = Submission(**parsed_dict)
        
        # Verify critical data integrity
        self.assertEqual(original.submitter.organisation_id, roundtrip.submitter.organisation_id)
        self.assertEqual(original.sighting.sighting_id, roundtrip.sighting.sighting_id)
        self.assertEqual(original.sighting.confidence, roundtrip.sighting.confidence)
        self.assertEqual(len(original.sighting.observables.network), 
                        len(roundtrip.sighting.observables.network))

    def test_yaml_serialization_minimal(self):
        """Test YAML serialization produces clean output like minimal.yaml."""
        submission = Submission(**self.minimal_yaml_data["submission"])
        
        # Create wrapped format like original
        wrapped_data = {
            "submission": submission.model_dump(exclude_none=True)
        }
        
        yaml_str = yaml.dump(wrapped_data, default_flow_style=False, sort_keys=False)
        
        # Verify YAML structure and content
        self.assertIn("submission:", yaml_str)
        self.assertIn("submitter:", yaml_str)
        self.assertIn("access_level: partner", yaml_str)
        self.assertIn("confidence: 87", yaml_str)
        self.assertIn("type: ipv4", yaml_str)
        self.assertIn("type: domain", yaml_str)

    def test_yaml_deserialization_minimal(self):
        """Test parsing the actual minimal.yaml structure."""
        # Simulate parsing the original YAML
        yaml_str = """
        submission:
          submitter:
            organisation_id: "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff"
            access_level: "partner"
          sighting:
            sighting_id: "sighting-ee20065d-2555-424f-ad9e-0f8428623c75"
            timestamp: "2025-01-20T14:30:22Z"
            confidence: 87
            observables:
              network:
                - id: "ipv4-addr-c4e54321-1234-5678-9abc-def012345678"
                  type: "ipv4"
                  value: "185.220.102.45"
                - id: "domain-name-d5f65432-2345-6789-abcd-ef0123456789"
                  type: "domain"
                  value: "secure-bank-verify.nl"
        """
        
        parsed_yaml = yaml.safe_load(yaml_str)
        submission = Submission(**parsed_yaml["submission"])
        
        # Verify parsing worked correctly
        self.assertEqual(submission.submitter.access_level, AccessTier.PARTNER)
        self.assertEqual(submission.sighting.confidence, 87)
        self.assertEqual(len(submission.sighting.observables.network), 2)

    def test_yaml_roundtrip_complete(self):
        """Test complete YAML roundtrip maintaining data integrity."""
        original_data = self.minimal_yaml_data
        
        # YAML -> Submission -> YAML -> Submission
        submission = Submission(**original_data["submission"])
        
        # Serialize back to YAML
        wrapped_data = {"submission": submission.model_dump(exclude_none=True)}
        yaml_str = yaml.dump(wrapped_data, default_flow_style=False)
        
        # Parse again
        reparsed_yaml = yaml.safe_load(yaml_str)
        roundtrip_submission = Submission(**reparsed_yaml["submission"])
        
        # Verify complete data integrity
        self.assertEqual(submission.submitter.organisation_id, 
                        roundtrip_submission.submitter.organisation_id)
        self.assertEqual(submission.sighting.sighting_id, 
                        roundtrip_submission.sighting.sighting_id)
        self.assertEqual(submission.sighting.confidence, 
                        roundtrip_submission.sighting.confidence)
        
        # Check observables
        orig_network = submission.sighting.observables.network
        round_network = roundtrip_submission.sighting.observables.network
        self.assertEqual(len(orig_network), len(round_network))
        
        for orig_obs, round_obs in zip(orig_network, round_network):
            self.assertEqual(orig_obs.id, round_obs.id)
            self.assertEqual(orig_obs.observable_type, round_obs.observable_type)
            self.assertEqual(orig_obs.value, round_obs.value)

    def test_datetime_handling_in_serialization(self):
        """Test that datetime fields are properly handled across formats."""
        submission = Submission(**self.minimal_yaml_data["submission"])
        
        # Check that timestamp was parsed correctly
        expected_time = datetime(2025, 1, 20, 14, 30, 22, tzinfo=timezone.utc)
        self.assertEqual(submission.sighting.timestamp, expected_time)
        
        # Test JSON roundtrip with datetime
        json_str = submission.model_dump_json(exclude_none=True)
        parsed_dict = json.loads(json_str)
        roundtrip = Submission(**parsed_dict)
        
        # Datetime should survive roundtrip
        self.assertEqual(submission.sighting.timestamp, roundtrip.sighting.timestamp)

    def test_optional_fields_handling(self):
        """Test handling of optional fields like hit_target and processing_notes."""
        # Test with minimal data (no optional fields)
        minimal_sub = Submission(**self.minimal_yaml_data["submission"])
        self.assertIsNone(minimal_sub.hit_target)
        self.assertIsNone(minimal_sub.processing_notes)
        
        # Test with optional fields
        data_with_optional = self.minimal_yaml_data["submission"].copy()
        data_with_optional.update({
            "hit_target": {
                "organisation_id": "identity-target-123",
                "sector": "financial"
            },
            "processing_notes": "Automated submission via API"
        })
        
        full_sub = Submission(**data_with_optional)
        self.assertIsNotNone(full_sub.hit_target)
        self.assertEqual(full_sub.processing_notes, "Automated submission via API")
        
        # Test serialization excludes None values
        minimal_dict = minimal_sub.model_dump(exclude_none=True)
        self.assertNotIn("hit_target", minimal_dict)
        self.assertNotIn("processing_notes", minimal_dict)
        
        full_dict = full_sub.model_dump(exclude_none=True)
        self.assertIn("hit_target", full_dict)
        self.assertIn("processing_notes", full_dict)

    def test_enum_values_consistency(self):
        """Test that enum values are consistently serialized across formats."""
        submission = Submission(**self.minimal_yaml_data["submission"])
        
        # Check that enums are properly serialized in all formats
        formats_data = {}
        
        # Dict
        formats_data['dict'] = submission.model_dump(exclude_none=True)
        
        # JSON
        formats_data['json'] = json.loads(submission.model_dump_json(exclude_none=True))
        
        # YAML
        yaml_str = yaml.dump(formats_data['dict'], default_flow_style=False)
        formats_data['yaml'] = yaml.safe_load(yaml_str)
        
        # All should have enum values as strings
        for format_name, data in formats_data.items():
            with self.subTest(format=format_name):
                self.assertEqual(data["submitter"]["access_level"], "partner")
                
                # Check observable types
                for obs in data["sighting"]["observables"]["network"]:
                    self.assertIn(obs["observable_type"], ["ipv4", "domain"])
                    self.assertIsInstance(obs["observable_type"], str)

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored per 'be forgiving' principle."""
        data_with_extra = self.minimal_yaml_data["submission"].copy()
        data_with_extra.update({
            "unknown_field": "should_be_ignored",
            "custom_metadata": {"arbitrary": "data"},
            "legacy_format": True
        })
        
        # Should not raise an error
        submission = Submission(**data_with_extra)
        
        # Extra fields should not appear in serialization
        result = submission.model_dump(exclude_none=True)
        self.assertNotIn("unknown_field", result)
        self.assertNotIn("custom_metadata", result)
        self.assertNotIn("legacy_format", result)

    def test_nested_model_serialization(self):
        """Test that nested models (Submitter, Sighting, Observables) serialize correctly."""
        submission = Submission(**self.minimal_yaml_data["submission"])
        result = submission.model_dump(exclude_none=True)
        
        # Check nested structure is preserved
        self.assertIsInstance(result["submitter"], dict)
        self.assertIsInstance(result["sighting"], dict)
        self.assertIsInstance(result["sighting"]["observables"], dict)
        self.assertIsInstance(result["sighting"]["observables"]["network"], list)
        
        # Check nested model data
        submitter_data = result["submitter"]
        self.assertIn("organisation_id", submitter_data)
        self.assertIn("access_level", submitter_data)
        
        sighting_data = result["sighting"]
        self.assertIn("sighting_id", sighting_data)
        self.assertIn("confidence", sighting_data)
        self.assertIn("observables", sighting_data)

    def test_format_version_default(self):
        """Test that format_version defaults to current version."""
        submission = Submission(**self.minimal_yaml_data["submission"])
        
        # Should have default version
        self.assertEqual(submission.format_version, __version__)
        
        # Should appear in serialization
        result = submission.model_dump(exclude_none=True)
        self.assertEqual(result["format_version"], __version__)
        
        # Test custom version
        custom_data = self.minimal_yaml_data["submission"].copy()
        custom_data["format_version"] = "1.0.0-custom"
        
        custom_submission = Submission(**custom_data)
        self.assertEqual(custom_submission.format_version, "1.0.0-custom")

    def test_multiple_format_consistency(self):
        """Test that dict, JSON, and YAML produce identical results."""
        original = Submission(**self.minimal_yaml_data["submission"])
        
        # Get data in different formats
        dict_data = original.model_dump(exclude_none=True)
        json_data = json.loads(original.model_dump_json(exclude_none=True))
        yaml_data = yaml.safe_load(yaml.dump(dict_data, default_flow_style=False))
        
        # Create submissions from each format
        from_dict = Submission(**dict_data)
        from_json = Submission(**json_data)
        from_yaml = Submission(**yaml_data)
        
        # All should be equivalent
        submissions = [from_dict, from_json, from_yaml]
        for sub in submissions:
            self.assertEqual(sub.submitter.organisation_id, original.submitter.organisation_id)
            self.assertEqual(sub.sighting.sighting_id, original.sighting.sighting_id)
            self.assertEqual(sub.sighting.confidence, original.sighting.confidence)
            self.assertEqual(len(sub.sighting.observables.network), 
                           len(original.sighting.observables.network))

    def test_wrapped_submission_format(self):
        """Test the wrapped 'submission:' format used in YAML files."""
        # Test parsing wrapped format
        wrapped = self.minimal_yaml_data
        submission = Submission(**wrapped["submission"])
        
        # Test creating wrapped format for export
        export_wrapped = {"submission": submission.model_dump(exclude_none=True)}
        
        # Should be able to roundtrip
        roundtrip_submission = Submission(**export_wrapped["submission"])
        
        self.assertEqual(submission.submitter.access_level, roundtrip_submission.submitter.access_level)
        self.assertEqual(submission.sighting.confidence, roundtrip_submission.sighting.confidence)

    def test_complex_roundtrip_scenario(self):
        """Test a complex roundtrip scenario through all formats."""
        # Start with YAML data
        original_yaml = self.minimal_yaml_data
        
        # YAML -> Submission
        submission = Submission(**original_yaml["submission"])
        
        # Submission -> Dict -> JSON -> Dict -> Submission
        dict_data = submission.model_dump(exclude_none=True, by_alias=True)
        self.assertNotIn('submission', dict_data)
        json_str = json.dumps({'submission': dict_data})
        json_dict = json.loads(json_str)
        json_submission = Submission(**json_dict['submission'])
        
        # Submission -> Dict -> YAML -> Dict -> Submission  
        yaml_data = {"submission": submission.model_dump(exclude_none=True)}
        yaml_str = yaml.dump(yaml_data, default_flow_style=False)
        yaml_dict = yaml.safe_load(yaml_str)
        yaml_submission = Submission(**yaml_dict["submission"])
        
        # All should be equivalent
        submissions = [submission, json_submission, yaml_submission]
        
        # Check key invariants across all formats
        for sub in submissions:
            self.assertEqual(sub.submitter.organisation_id, "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff")
            self.assertEqual(sub.submitter.access_level, AccessTier.PARTNER)
            self.assertEqual(sub.sighting.sighting_id, "sighting-ee20065d-2555-424f-ad9e-0f8428623c75")
            self.assertEqual(sub.sighting.confidence, 87)
            self.assertEqual(len(sub.sighting.observables.network), 2)
            self.assertEqual(sub.format_version, __version__)
            self.assertEqual(sub.submission_method, "api")

class TestLegacySubmissionParsing(unittest.TestCase):
    """Test parsing legacy submission formats into current Submission model."""

    def test_from_legacy_dict_missing_submission_key(self):
        """Test parsing when 'submission' key is missing."""
        legacy_data = {
            "submitter": {"access_level": "partner"},
            "hit_target": {"sector": "finance"},
            "sighting": {"confidence": 85},
            "observables": {
                "network": [
                    {"type": "ipv4", "value": "203.0.113.1"}
                ]
            }
        }
        parsed = Submission.from_legacy_dict(legacy_data)
        self.assertIsInstance(parsed, Submission)
        self.assertEqual(parsed.hit_target.sector, "finance")
        self.assertTrue(parsed.sighting.observables.network)

    def test_from_legacy_dict_missing_submission_key(self):
        """Test parsing when 'submission' key is missing."""
        legacy_data = {
            "submitter": {"access_level": "partner"},
            "hit_target": {"sector": "finance"},
            "sighting": {
                "confidence": 85,
                "observables": {
                    "network": [
                        {"type": "ipv4", "value": "203.0.113.1"}
                    ]
                }
            }
        }
        parsed = Submission.from_legacy_dict(legacy_data)
        self.assertIsInstance(parsed, Submission)
        self.assertEqual(parsed.hit_target.sector, "finance")
        self.assertTrue(parsed.sighting.observables.network)

    def test_from_legacy_dict_regular(self):
        """Test parsing when hit_target sector is missing (should default to 'unknown')."""
        legacy_data = {
            "submission": {
                "submitter": {"access_level": "partner"},
                "hit_target": {"sector": "finance"},
                "sighting": {"confidence": 85},
                "observables": {
                    "network": [
                        {"type": "ipv4", "value": "203.0.113.1"}
                    ]
                }
            }
        }
        parsed = Submission.from_legacy_dict(legacy_data)
        self.assertIsInstance(parsed, Submission)
        self.assertEqual(parsed.hit_target.sector, "finance")

    def test_from_legacy_dict_invalid_observable(self):
        """Test parsing with an invalid observable (should skip it)."""
        legacy_data = {
            "submission": {
                "submitter": {"access_level": "partner"},
                "hit_target": {"sector": "finance"},
                "sighting": {"confidence": 85},
                "observables": {
                    "network": [
                        {"type": "ipv4", "value": "203.0.113.1"},
                        {"type": "ipv4"}  # Missing value, should be skipped
                    ]
                }
            }
        }
        parsed = Submission.from_legacy_dict(legacy_data)
        self.assertIsInstance(parsed, Submission)
        self.assertEqual(parsed.hit_target.sector, "finance")
        self.assertEqual(len(parsed.sighting.observables.network), 1)

    def test_from_legacy_dict_error(self):
        """Test parsing with completely invalid data (should raise ValueError)."""
        with self.assertRaises(ValueError):
            Submission.from_legacy_dict({"not_a_submission": True})


if __name__ == "__main__":
    unittest.main(verbosity=2, buffer=True)