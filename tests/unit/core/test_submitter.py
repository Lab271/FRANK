#!/usr/bin/env python3
"""
FRANK Platform - Submitter Unit Tests

Tests the "be forgiving on what you receive, strong on what you return" principle
All based on Pydantic v2 models and validation

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest
import uuid
import json
import yaml

# Import the models (adjust import path as needed)
from frank.core.models import Submitter
from frank.core.enum import AccessTier
from pydantic import ValidationError


class TestSubmitter(unittest.TestCase):
    """Comprehensive unit tests for the Submitter model"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.valid_submitter_data = {
            "access_level": AccessTier.PARTNER,
            "sector": "financial",
            "region": "europe"
        }

    def test_create_minimal_submitter(self):
        """Test creating a submitter with minimal required fields"""
        submitter = Submitter(tier=AccessTier.PARTNER)
        
        # Check that required fields are set
        self.assertEqual(submitter.tier, AccessTier.PARTNER)
        self.assertEqual(submitter.organization_type, "cyber_partner")  # default
        
        # Check that organization_id is auto-generated
        self.assertIsNotNone(submitter.organization_id)
        self.assertTrue(submitter.organization_id.startswith("identity--"))
        self.assertIsInstance(uuid.UUID(submitter.organization_id.split("--")[1]), uuid.UUID)

    def test_create_submitter_with_all_fields(self):
        """Test creating a submitter with all fields provided"""
        org_id = f"identity--{uuid.uuid4()}"
        submitter = Submitter(
            organization_id=org_id,
            tier=AccessTier.CORE_MEMBER,
            organization_type="mssp",
            sector="technology",
            region="north_america",
            client_count=150
        )
        
        self.assertEqual(submitter.organization_id, org_id)
        self.assertEqual(submitter.tier, AccessTier.CORE_MEMBER)
        self.assertEqual(submitter.organization_type, "mssp")
        self.assertEqual(submitter.sector, "technology")
        self.assertEqual(submitter.region, "north_america")
        self.assertEqual(submitter.client_count, 150)

    def test_organization_id_auto_generation(self):
        """Test that organization_id is auto-generated when not provided"""
        # Test with None
        submitter1 = Submitter(tier=AccessTier.PARTNER, organization_id=None)
        self.assertIsNotNone(submitter1.organization_id)
        self.assertTrue(submitter1.organization_id.startswith("identity--"))
        
        # Test with empty string
        submitter2 = Submitter(tier=AccessTier.PARTNER, organization_id="")
        self.assertIsNotNone(submitter2.organization_id)
        self.assertTrue(submitter2.organization_id.startswith("identity--"))
        
        # Test different IDs are generated
        self.assertNotEqual(submitter1.organization_id, submitter2.organization_id)

    def test_sector_normalization(self):
        """Test sector name normalization - 'be forgiving' on input"""
        test_cases = [
            ("finance", "financial"),
            ("banking", "financial"),
            ("healthcare", "health"),
            ("medical", "health"),
            ("government", "public_sector"),
            ("gov", "public_sector"),
            ("tech", "technology"),
            ("it", "technology"),
            ("manufacturing", "manufacturing"),  # No change
            ("FINANCE", "financial"),  # Case insensitive
            ("  banking  ", "financial"),  # Whitespace handling
        ]
        
        for input_sector, expected_output in test_cases:
            with self.subTest(input_sector=input_sector):
                submitter = Submitter(tier=AccessTier.PARTNER, sector=input_sector)
                self.assertEqual(submitter.sector, expected_output)

    def test_sector_none_handling(self):
        """Test that None sector is handled properly"""
        submitter = Submitter(tier=AccessTier.PARTNER, sector=None)
        self.assertIsNone(submitter.sector)

    def test_tier_validation(self):
        """Test tier level validation"""
        # Valid tiers
        valid_tiers = [
            AccessTier.PUBLIC,
            AccessTier.OBSERVER,
            AccessTier.CONTRIBUTOR,
            AccessTier.PARTNER,
            AccessTier.CORE_MEMBER
        ]
        
        for tier in valid_tiers:
            with self.subTest(tier=tier):
                submitter = Submitter(tier=tier)
                self.assertEqual(submitter.tier, tier)
        
        # Test with string values (should work with enum)
        submitter = Submitter(tier="partner")
        self.assertEqual(submitter.tier, AccessTier.PARTNER)

    def test_invalid_tier_raises_error(self):
        """Test that invalid tier raises validation error"""
        with self.assertRaises(ValidationError) as context:
            Submitter(tier="invalid_tier")
        
        self.assertIn("access_level", str(context.exception))

    def test_client_count_validation(self):
        """Test client count validation"""
        # Valid client counts
        valid_counts = [0, 1, 100, 10000]
        for count in valid_counts:
            with self.subTest(count=count):
                submitter = Submitter(tier=AccessTier.PARTNER, client_count=count)
                self.assertEqual(submitter.client_count, count)
        
        # Invalid client count (negative)
        with self.assertRaises(ValidationError):
            Submitter(tier=AccessTier.PARTNER, client_count=-1)

    def test_factory_method_create(self):
        """Test the create factory method"""
        submitter = Submitter.create(
            tier=AccessTier.CONTRIBUTOR,
            sector="healthcare",
            region="asia_pacific"
        )
        
        self.assertEqual(submitter.tier, AccessTier.CONTRIBUTOR)
        self.assertEqual(submitter.sector, "health")  # Should be normalized
        self.assertEqual(submitter.region, "asia_pacific")
        self.assertIsNotNone(submitter.organization_id)

    def test_factory_method_minimal(self):
        """Test factory method with minimal parameters"""
        submitter = Submitter.create(tier=AccessTier.OBSERVER)
        
        self.assertEqual(submitter.tier, AccessTier.OBSERVER)
        self.assertIsNone(submitter.sector)
        self.assertIsNone(submitter.region)
        self.assertIsNotNone(submitter.organization_id)

    def test_model_dump(self):
        """Test serialization to dictionary"""
        submitter = Submitter(
            tier=AccessTier.PARTNER,
            sector="financial",
            region="europe",
            client_count=50
        )
        
        data = submitter.model_dump()
        
        # Check that all fields are present
        self.assertIn("organization_id", data)
        self.assertIn("access_level", data)
        self.assertIn("organization_type", data)
        self.assertIn("sector", data)
        self.assertIn("region", data)
        self.assertIn("client_count", data)
        
        # Check values
        self.assertEqual(data["access_level"], "partner")  # Enum value
        self.assertEqual(data["sector"], "financial")
        self.assertEqual(data["region"], "europe")
        self.assertEqual(data["client_count"], 50)

    def test_model_dump_exclude_none(self):
        """Test serialization excluding None values"""
        submitter = Submitter(tier=AccessTier.PARTNER)  # sector, region, client_count will be None
        
        data = submitter.model_dump(exclude_none=True)
        
        # Check that None fields are excluded
        self.assertNotIn("sector", data)
        self.assertNotIn("region", data)
        self.assertNotIn("client_count", data)
        
        # Check that non-None fields are present
        self.assertIn("organization_id", data)
        self.assertIn("access_level", data)

    def test_json_serialization(self):
        """Test JSON serialization"""
        submitter = Submitter(
            tier=AccessTier.PARTNER,
            sector="technology"
        )
        
        json_str = submitter.model_dump_json()
        self.assertIsInstance(json_str, str)
        self.assertIn("partner", json_str)
        self.assertIn("technology", json_str)

    def test_model_config_extra_ignore(self):
        """Test that extra fields are ignored (be forgiving)"""
        # This should not raise an error due to extra="ignore"
        submitter = Submitter(
            tier=AccessTier.PARTNER,
            sector="financial",
            unknown_field="should_be_ignored",
            another_extra_field=123
        )
        
        self.assertEqual(submitter.tier, AccessTier.PARTNER)
        self.assertEqual(submitter.sector, "financial")
        # Extra fields should not be accessible
        self.assertFalse(hasattr(submitter, 'unknown_field'))

    def test_submitter_equality(self):
        """Test submitter equality comparison"""
        org_id = f"identity--{uuid.uuid4()}"
        
        submitter1 = Submitter(
            organization_id=org_id,
            tier=AccessTier.PARTNER,
            sector="financial"
        )
        
        submitter2 = Submitter(
            organization_id=org_id,
            tier=AccessTier.PARTNER,
            sector="financial"
        )
        
        # Different instances with same data should be equal
        self.assertEqual(submitter1, submitter2)

    def test_submitter_inequality(self):
        """Test submitter inequality"""
        submitter1 = Submitter(tier=AccessTier.PARTNER, sector="financial")
        submitter2 = Submitter(tier=AccessTier.CONTRIBUTOR, sector="financial")
        
        # Different tiers should not be equal
        self.assertNotEqual(submitter1, submitter2)

    def test_repr_and_str(self):
        """Test string representations"""
        submitter = Submitter(tier=AccessTier.PARTNER, sector="financial")
        
        repr_str = repr(submitter)
        str_str = str(submitter)
        
        self.assertIsInstance(repr_str, str)
        self.assertIsInstance(str_str, str)
        self.assertIn("Submitter", repr_str)

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Empty strings should be handled
        submitter = Submitter(
            tier=AccessTier.PARTNER,
            sector="",  # Empty string
            region=""   # Empty string
        )
        
        # Empty sector should be normalized (though result might be empty)
        self.assertIsNotNone(submitter.sector)
        
        # Very long strings (should be accepted)
        long_sector = "a" * 1000
        submitter_long = Submitter(tier=AccessTier.PARTNER, sector=long_sector)
        self.assertEqual(submitter_long.sector, long_sector)


class TestSubmitterIntegration(unittest.TestCase):
    """Integration tests for Submitter with other components"""

    def test_submitter_in_submission_context(self):
        """Test submitter validation in the context of a full submission"""
        # This tests that the submitter works properly as part of larger validation
        submitter = Submitter(tier=AccessTier.PARTNER, sector="financial")
        
        # Should be able to access all required properties for submission validation
        self.assertIsNotNone(submitter.organization_id)
        self.assertEqual(submitter.tier, AccessTier.PARTNER)
        self.assertEqual(submitter.sector, "financial")

    def test_multiple_submitters_unique_ids(self):
        """Test that multiple submitters get unique IDs"""
        submitters = [Submitter(tier=AccessTier.PARTNER) for _ in range(10)]
        
        # All IDs should be unique
        ids = [s.organization_id for s in submitters]
        self.assertEqual(len(ids), len(set(ids)))
        
        # All IDs should follow the pattern
        for org_id in ids:
            self.assertTrue(org_id.startswith("identity--"))
            # Should be valid UUID format
            uuid_part = org_id.split("--")[1]
            self.assertIsInstance(uuid.UUID(uuid_part), uuid.UUID)


class TestSubmitterPerformance(unittest.TestCase):
    """Performance-related tests for Submitter"""

    def test_bulk_creation_performance(self):
        """Test creating many submitters (basic performance check)"""
        import time
        
        start_time = time.time()
        submitters = []
        
        for i in range(100):
            submitter = Submitter(
                tier=AccessTier.PARTNER,
                sector="financial",
                client_count=i
            )
            submitters.append(submitter)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should be able to create 100 submitters quickly
        self.assertLess(elapsed, 1.0)  # Less than 1 second
        self.assertEqual(len(submitters), 100)
        
        # All should have unique IDs
        ids = [s.organization_id for s in submitters]
        self.assertEqual(len(ids), len(set(ids)))

class TestSubmitterSerialization(unittest.TestCase):
    """Test Submitter serialization and deserialization with various formats."""
    
    def setUp(self):
        """Set up test data."""
        self.minimal_data = {
            "access_level": "partner"
        }
        
        self.full_data = {
            "organization_id": "identity--12345678-1234-5678-9abc-123456789abc",
            "access_level": "partner",
            "organization_type": "cyber_partner",
            "sector": "financial",
            "region": "north_america",
            "client_count": 150
        }
        
        self.sector_normalization_data = {
            "access_level": "observer",
            "sector": "Banking",  # Should normalize to "financial"
            "region": "europe"
        }
        
        self.factory_data = {
            "access_level": AccessTier.PARTNER,
            "sector": "healthcare",
            "region": "asia_pacific"
        }

    def test_dict_to_submitter_minimal(self):
        """Test creating Submitter from minimal dictionary."""
        submitter = Submitter(**self.minimal_data)
        
        self.assertEqual(submitter.tier, AccessTier.PARTNER)
        self.assertEqual(submitter.organization_type, "cyber_partner")  # Default value
        self.assertIsNotNone(submitter.organization_id)
        self.assertTrue(submitter.organization_id.startswith("identity--"))

    def test_dict_to_submitter_full(self):
        """Test creating Submitter from full dictionary."""
        submitter = Submitter(**self.full_data)
        
        self.assertEqual(submitter.organization_id, self.full_data["organization_id"])
        self.assertEqual(submitter.tier, AccessTier.PARTNER)
        self.assertEqual(submitter.organization_type, "cyber_partner")
        self.assertEqual(submitter.sector, "financial")
        self.assertEqual(submitter.region, "north_america")
        self.assertEqual(submitter.client_count, 150)

    def test_submitter_to_dict(self):
        """Test converting Submitter to dictionary."""
        submitter = Submitter(**self.full_data)
        result = submitter.model_dump(exclude_none=True)
        
        self.assertEqual(result["access_level"], "partner")  # use_enum_values=True
        self.assertEqual(result["organization_type"], "cyber_partner")
        self.assertEqual(result["sector"], "financial")
        self.assertEqual(result["client_count"], 150)

    def test_dict_roundtrip_minimal(self):
        """Test dictionary roundtrip with minimal data."""
        # Dict -> Submitter -> Dict
        submitter = Submitter(**self.minimal_data)
        result_dict = submitter.model_dump(exclude_none=True)
        
        # Check essential fields survived
        self.assertEqual(result_dict["access_level"], self.minimal_data["access_level"])
        self.assertIn("organization_id", result_dict)
        self.assertEqual(result_dict["organization_type"], "cyber_partner")

    def test_dict_roundtrip_full(self):
        """Test dictionary roundtrip with full data."""
        submitter = Submitter(**self.full_data)
        result_dict = submitter.model_dump(exclude_none=True)
        
        # Create new submitter from result
        roundtrip_submitter = Submitter(**result_dict)
        
        self.assertEqual(submitter.organization_id, roundtrip_submitter.organization_id)
        self.assertEqual(submitter.tier, roundtrip_submitter.tier)
        self.assertEqual(submitter.sector, roundtrip_submitter.sector)
        self.assertEqual(submitter.region, roundtrip_submitter.region)
        self.assertEqual(submitter.client_count, roundtrip_submitter.client_count)

    def test_json_serialization(self):
        """Test JSON serialization."""
        submitter = Submitter(**self.full_data)
        json_str = submitter.model_dump_json(exclude_none=True)
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        self.assertEqual(parsed["access_level"], "partner")
        self.assertEqual(parsed["sector"], "financial")
        self.assertEqual(parsed["client_count"], 150)

    def test_json_deserialization(self):
        """Test JSON deserialization."""
        json_str = json.dumps(self.full_data)
        parsed_dict = json.loads(json_str)
        submitter = Submitter(**parsed_dict)
        
        self.assertEqual(submitter.tier, AccessTier.PARTNER)
        self.assertEqual(submitter.sector, "financial")
        self.assertEqual(submitter.client_count, 150)

    def test_json_roundtrip(self):
        """Test complete JSON roundtrip."""
        original = Submitter(**self.full_data)
        
        # Submitter -> JSON -> Dict -> Submitter
        json_str = original.model_dump_json(exclude_none=True)
        parsed_dict = json.loads(json_str)
        roundtrip = Submitter(**parsed_dict)
        
        self.assertEqual(original.organization_id, roundtrip.organization_id)
        self.assertEqual(original.tier, roundtrip.tier)
        self.assertEqual(original.sector, roundtrip.sector)
        self.assertEqual(original.region, roundtrip.region)
        self.assertEqual(original.client_count, roundtrip.client_count)

    def test_yaml_serialization(self):
        """Test YAML serialization."""
        submitter = Submitter(**self.full_data)
        data = submitter.model_dump(exclude_none=True)
        yaml_str = yaml.dump(data, default_flow_style=False)
        
        # Verify YAML is valid and contains expected content
        self.assertIn("tier: partner", yaml_str)
        self.assertIn("sector: financial", yaml_str)
        self.assertIn("client_count: 150", yaml_str)

    def test_yaml_deserialization(self):
        """Test YAML deserialization."""
        yaml_str = """
        tier: "observer"
        sector: "technology"
        region: "europe"
        client_count: 75
        """
        
        parsed_dict = yaml.safe_load(yaml_str)
        submitter = Submitter(**parsed_dict)
        
        self.assertEqual(submitter.tier, AccessTier.OBSERVER)
        self.assertEqual(submitter.sector, "technology")
        self.assertEqual(submitter.region, "europe")
        self.assertEqual(submitter.client_count, 75)

    def test_yaml_roundtrip(self):
        """Test complete YAML roundtrip."""
        original = Submitter(**self.full_data)
        
        # Submitter -> YAML -> Dict -> Submitter
        data = original.model_dump(exclude_none=True)
        yaml_str = yaml.dump(data, default_flow_style=False)
        parsed_dict = yaml.safe_load(yaml_str)
        roundtrip = Submitter(**parsed_dict)
        
        self.assertEqual(original.organization_id, roundtrip.organization_id)
        self.assertEqual(original.tier, roundtrip.tier)
        self.assertEqual(original.sector, roundtrip.sector)
        self.assertEqual(original.region, roundtrip.region)

    def test_sector_normalization_in_serialization(self):
        """Test that sector normalization works during serialization roundtrips."""
        # Test various sector normalizations
        test_cases = [
            ("Banking", "financial"),
            ("finance", "financial"),
            ("Healthcare", "health"),
            ("medical", "health"),
            ("Government", "public_sector"),
            ("gov", "public_sector"),
            ("Tech", "technology"),
            ("IT", "technology"),
            ("custom_sector", "custom_sector")  # Unknown sector stays as-is
        ]
        
        for input_sector, expected_sector in test_cases:
            with self.subTest(input_sector=input_sector):
                data = self.minimal_data.copy()
                data["sector"] = input_sector
                
                submitter = Submitter(**data)
                self.assertEqual(submitter.sector, expected_sector)
                
                # Test roundtrip preserves normalization
                dict_data = submitter.model_dump(exclude_none=True)
                roundtrip = Submitter(**dict_data)
                self.assertEqual(roundtrip.sector, expected_sector)

    def test_factory_method_serialization(self):
        """Test factory method creates submitters that serialize correctly."""
        submitter = Submitter.create(
            tier=AccessTier.PARTNER,
            sector="healthcare",
            region="north_america"
        )
        
        # Test it serializes correctly
        data = submitter.model_dump(exclude_none=True)
        self.assertEqual(data["access_level"], "partner")
        self.assertEqual(data["sector"], "health")  # Should be normalized
        self.assertEqual(data["region"], "north_america")
        
        # Test roundtrip
        roundtrip = Submitter(**data)
        self.assertEqual(submitter.tier, roundtrip.tier)
        self.assertEqual(submitter.sector, roundtrip.sector)
        self.assertEqual(submitter.region, roundtrip.region)

    def test_organization_id_generation(self):
        """Test automatic organization ID generation."""
        submitter1 = Submitter(**self.minimal_data)
        submitter2 = Submitter(**self.minimal_data)
        
        # Both should have IDs
        self.assertIsNotNone(submitter1.organization_id)
        self.assertIsNotNone(submitter2.organization_id)
        
        # IDs should be unique
        self.assertNotEqual(submitter1.organization_id, submitter2.organization_id)
        
        # IDs should be STIX format
        self.assertTrue(submitter1.organization_id.startswith("identity--"))
        self.assertTrue(submitter2.organization_id.startswith("identity--"))
        
        # UUID part should be valid
        uuid_part1 = submitter1.organization_id.split("--")[1]
        uuid_part2 = submitter2.organization_id.split("--")[1]
        
        # Should not raise ValueError
        uuid.UUID(uuid_part1)
        uuid.UUID(uuid_part2)

    def test_predefined_organization_id_preserved(self):
        """Test that predefined organization IDs are preserved."""
        predefined_id = "identity--custom-12345678-1234-5678-9abc-123456789abc"
        data = self.minimal_data.copy()
        data["organization_id"] = predefined_id
        
        submitter = Submitter(**data)
        self.assertEqual(submitter.organization_id, predefined_id)
        
        # Test roundtrip preserves custom ID
        dict_data = submitter.model_dump(exclude_none=True)
        roundtrip = Submitter(**dict_data)
        self.assertEqual(roundtrip.organization_id, predefined_id)

    def test_default_values_serialization(self):
        """Test that default values are properly handled in serialization."""
        submitter = Submitter(**self.minimal_data)
        
        # Check defaults are set
        self.assertEqual(submitter.organization_type, "cyber_partner")
        
        # Check they appear in serialization
        data = submitter.model_dump(exclude_none=True)
        self.assertEqual(data["organization_type"], "cyber_partner")

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored due to 'extra=ignore' config."""
        data_with_extra = self.minimal_data.copy()
        data_with_extra.update({
            "unknown_field": "should_be_ignored",
            "random_data": {"nested": "value"},
            "extra_number": 999
        })
        
        # Should not raise an error
        submitter = Submitter(**data_with_extra)
        self.assertEqual(submitter.tier, AccessTier.PARTNER)
        
        # Extra fields should not appear in output
        data = submitter.model_dump(exclude_none=True)
        self.assertNotIn("unknown_field", data)
        self.assertNotIn("random_data", data)
        self.assertNotIn("extra_number", data)

    def test_invalid_data_validation(self):
        """Test that invalid data raises appropriate errors."""
        # Missing required field (tier)
        with self.assertRaises(Exception):
            Submitter(sector="financial")
        
        # Invalid client_count (negative)
        with self.assertRaises(Exception):
            Submitter(tier="partner", client_count=-5)
        
        # Invalid tier value
        with self.assertRaises(Exception):
            Submitter(tier="invalid_tier")

    def test_none_values_excluded(self):
        """Test that None values are properly excluded."""
        data = {
            "access_level": "partner",
            "sector": None,
            "region": None,
            "client_count": None
        }
        
        submitter = Submitter(**data)
        result = submitter.model_dump(exclude_none=True)
        
        # None values should be excluded
        self.assertNotIn("sector", result)
        self.assertNotIn("region", result)
        self.assertNotIn("client_count", result)
        
        # Required and default fields should be present
        self.assertIn("access_level", result)
        self.assertIn("organization_type", result)

    def test_multiple_format_consistency(self):
        """Test that dict, JSON, and YAML produce consistent results."""
        original = Submitter(**self.full_data)
        
        # Get data in different formats
        dict_data = original.model_dump(exclude_none=True)
        json_data = json.loads(original.model_dump_json(exclude_none=True))
        yaml_data = yaml.safe_load(yaml.dump(dict_data, default_flow_style=False))
        
        # Create submitters from each format
        from_dict = Submitter(**dict_data)
        from_json = Submitter(**json_data)
        from_yaml = Submitter(**yaml_data)
        
        # All should be equivalent
        submitters = [from_dict, from_json, from_yaml]
        for sub in submitters:
            self.assertEqual(sub.organization_id, original.organization_id)
            self.assertEqual(sub.tier, original.tier)
            self.assertEqual(sub.sector, original.sector)
            self.assertEqual(sub.region, original.region)
            self.assertEqual(sub.client_count, original.client_count)

    def test_wrapped_yaml_format(self):
        """Test YAML with wrapper (like submission format)."""
        submitter = Submitter(**self.minimal_data)
        
        # Create wrapped format
        wrapped_data = {
            "submitter": submitter.model_dump(exclude_none=True)
        }
        
        yaml_str = yaml.dump(wrapped_data, default_flow_style=False)
        
        # Parse back
        parsed = yaml.safe_load(yaml_str)
        roundtrip = Submitter(**parsed["submitter"])
        
        self.assertEqual(submitter.tier, roundtrip.tier)
        self.assertEqual(submitter.organization_type, roundtrip.organization_type)

    def test_enum_serialization_consistency(self):
        """Test that enum values are consistently serialized as strings."""
        # Test with different tier levels
        tiers = [AccessTier.PARTNER, AccessTier.CORE_MEMBER, AccessTier.CONTRIBUTOR, AccessTier.OBSERVER, AccessTier.PUBLIC]
        
        for tier in tiers:
            with self.subTest(tier=tier):
                submitter = Submitter(tier=tier)
                
                # Dict output should use enum value
                dict_data = submitter.model_dump()
                self.assertEqual(dict_data["access_level"], tier.value)
                
                # JSON output should use enum value
                json_data = json.loads(submitter.model_dump_json())
                self.assertEqual(json_data["access_level"], tier.value)
                
                # Roundtrip should work
                roundtrip = Submitter(**dict_data)
                self.assertEqual(roundtrip.tier, tier)

    def test_complex_serialization_scenario(self):
        """Test a complex scenario with factory method, normalization, and multiple formats."""
        # Create with factory method and data that needs normalization
        submitter = Submitter.create(
            tier=AccessTier.OBSERVER,
            sector="Banking",  # Should normalize to "financial"
            region="north_america"
        )
        
        # Add additional data
        submitter.client_count = 500
        
        # Test through all formats
        formats_data = {}
        
        # Dict
        formats_data['dict'] = submitter.model_dump(exclude_none=True)
        
        # JSON
        formats_data['json'] = json.loads(submitter.model_dump_json(exclude_none=True))
        
        # YAML
        yaml_str = yaml.dump(formats_data['dict'], default_flow_style=False)
        formats_data['yaml'] = yaml.safe_load(yaml_str)
        
        # All formats should produce the same data
        for format_name, data in formats_data.items():
            with self.subTest(format=format_name):
                reconstructed = Submitter(**data)
                self.assertEqual(reconstructed.tier, AccessTier.OBSERVER)
                self.assertEqual(reconstructed.sector, "financial")  # Normalized
                self.assertEqual(reconstructed.region, "north_america")
                self.assertEqual(reconstructed.client_count, 500)


if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)