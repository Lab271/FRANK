#!/usr/bin/env python3
"""
FRANK Platform - Unit tests for FRANK HitTarget model

Tests the "be forgiving on what you receive, strong on what you return" principle

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest
import uuid
import json

from pydantic import ValidationError

# Import the models (adjust import path as needed)
from frank.core.models import HitTarget



class TestHitTarget(unittest.TestCase):
    """Comprehensive unit tests for the HitTarget model"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.valid_hittarget_data = {
            "sector": "financial",
            "organisation_type": "bank",
            "organisation_size": "large",
            "region": "europe"
        }

    def test_create_minimal_hittarget(self):
        """Test creating a hit target with minimal required fields"""
        hittarget = HitTarget(sector="medical")
        
        # Check that required fields are set
        self.assertEqual(hittarget.sector, "health")
        self.assertIsNone(hittarget.organisation_type)  # default
        self.assertEqual(hittarget.anonymization_level, "high")  # default
        
        # Check that organisation_id is None
        self.assertIsNone(hittarget.organisation_id)
        
        # Optional fields should be None
        self.assertIsNone(hittarget.organisation_size)
        self.assertIsNone(hittarget.region)

    def test_create_hittarget_with_all_fields(self):
        """Test creating a hit target with all fields provided"""
        org_id = f"identity--{uuid.uuid4()}"
        hittarget = HitTarget(
            organisation_id=org_id,
            sector="financial_services",
            organisation_type="credit_union",
            organisation_size="medium",
            region="north_america",
            anonymization_level="medium"
        )
        
        self.assertEqual(hittarget.organisation_id, org_id)
        self.assertEqual(hittarget.sector, "financial_services")
        self.assertEqual(hittarget.organisation_type, "credit_union")
        self.assertEqual(hittarget.organisation_size, "medium")
        self.assertEqual(hittarget.region, "north_america")
        self.assertEqual(hittarget.anonymization_level, "medium")

    def test_sector_validation_required(self):
        """Test that sector is required and validated"""
        # Valid sector
        hittarget = HitTarget(sector="technology")
        self.assertEqual(hittarget.sector, "technology")
        
        # Empty sector should raise error
        with self.assertRaises(ValidationError) as context:
            HitTarget(sector="")
        self.assertIn("sector", str(context.exception))
        
        # Missing sector should raise error
        with self.assertRaises(ValidationError):
            HitTarget()

    def test_organisation_size_normalization(self):
        """Test organisation size normalization - 'be forgiving' on input"""
        test_cases = [
            ("small", "small"),
            ("sme", "small"),
            ("startup", "small"),
            ("medium", "medium"),
            ("mid", "medium"),
            ("large", "large"),
            ("enterprise", "large"),
            ("multinational", "large"),
            ("unknown_size", "unknown_size"),  # No mapping, keep original
            ("SMALL", "small"),  # Case insensitive
            ("  medium  ", "medium"),  # Whitespace handling
        ]
        
        for input_size, expected_output in test_cases:
            with self.subTest(input_size=input_size):
                hittarget = HitTarget(sector="retail", organisation_size=input_size)
                self.assertEqual(hittarget.organisation_size, expected_output)

    def test_organisation_size_none_handling(self):
        """Test that None organisation size is handled properly"""
        hittarget = HitTarget(sector="manufacturing", organisation_size=None)
        self.assertIsNone(hittarget.organisation_size)

    def test_factory_method_create(self):
        """Test the create factory method"""
        hittarget = HitTarget.create(
            sector="healthcare",
            organisation_size="large",
            region="asia_pacific"
        )
        
        self.assertEqual(hittarget.sector, "health")
        self.assertEqual(hittarget.organisation_size, "large")
        self.assertEqual(hittarget.region, "asia_pacific")
        self.assertIsNone(hittarget.organisation_id)
        self.assertIsNone(hittarget.organisation_type)  # default
        self.assertEqual(hittarget.anonymization_level, "high")  # default

    def test_factory_method_minimal(self):
        """Test factory method with minimal parameters"""
        hittarget = HitTarget.create(sector="education")
        
        self.assertEqual(hittarget.sector, "education")
        self.assertIsNone(hittarget.organisation_size)
        self.assertIsNone(hittarget.region)
        self.assertIsNone(hittarget.organisation_id)

    def test_model_dump(self):
        """Test serialization to dictionary"""
        hittarget = HitTarget(
            sector="financial",
            organisation_type="bank",
            organisation_size="large",
            region="europe",
            anonymization_level="medium"
        )
        
        data = hittarget.model_dump()
        
        # Check that all fields are present
        expected_fields = [
            "organisation_id", "sector", "organisation_type", 
            "organisation_size", "region", "anonymization_level"
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Check values
        self.assertEqual(data["sector"], "financial")
        self.assertEqual(data["organisation_type"], "bank")
        self.assertEqual(data["organisation_size"], "large")
        self.assertEqual(data["region"], "europe")
        self.assertEqual(data["anonymization_level"], "medium")

    def test_model_dump_exclude_none(self):
        """Test serialization excluding None values"""
        hittarget = HitTarget(sector="technology")  # Other optional fields will be None
        
        data = hittarget.model_dump(exclude_none=True)
        
        # Check that None fields are excluded
        self.assertNotIn("organisation_size", data)
        self.assertNotIn("region", data)
        
        # Check that non-None fields are present
        self.assertNotIn("organisation_id", data)
        self.assertIn("sector", data)
        self.assertNotIn("organisation_type", data)
        self.assertIn("anonymization_level", data)

    def test_json_serialization(self):
        """Test JSON serialization"""
        hittarget = HitTarget(
            sector="manufacturing",
            organisation_size="medium",
            region="south_america"
        )
        
        json_str = hittarget.model_dump_json()
        self.assertIsInstance(json_str, str)
        
        # Parse back to verify
        data = json.loads(json_str)
        self.assertEqual(data["sector"], "manufacturing")
        self.assertEqual(data["organisation_size"], "medium")
        self.assertEqual(data["region"], "south_america")

    def test_model_config_extra_ignore(self):
        """Test that extra fields are ignored (be forgiving)"""
        # This should not raise an error due to extra="ignore"
        hittarget = HitTarget(
            sector="retail",
            unknown_field="should_be_ignored",
            another_extra_field=789
        )
        
        self.assertEqual(hittarget.sector, "retail")
        # Extra fields should not be accessible
        self.assertFalse(hasattr(hittarget, 'unknown_field'))

    def test_hittarget_equality(self):
        """Test hit target equality comparison"""
        org_id = f"identity--{uuid.uuid4()}"
        
        hittarget1 = HitTarget(
            organisation_id=org_id,
            sector="financial",
            organisation_size="large"
        )
        
        hittarget2 = HitTarget(
            organisation_id=org_id,
            sector="financial",
            organisation_size="large"
        )
        
        # Different instances with same data should be equal
        self.assertEqual(hittarget1, hittarget2)

    def test_hittarget_inequality(self):
        """Test hit target inequality"""
        hittarget1 = HitTarget(sector="healthcare", organisation_size="small")
        hittarget2 = HitTarget(sector="healthcare", organisation_size="large")
        
        # Different sizes should not be equal
        self.assertNotEqual(hittarget1, hittarget2)

    def test_repr_and_str(self):
        """Test string representations"""
        hittarget = HitTarget(sector="financial", organisation_size="large")
        
        repr_str = repr(hittarget)
        str_str = str(hittarget)
        
        self.assertIsInstance(repr_str, str)
        self.assertIsInstance(str_str, str)
        self.assertIn("HitTarget", repr_str)

    def test_anonymization_levels(self):
        """Test different anonymization levels"""
        anonymization_levels = ["low", "medium", "high", "maximum"]
        
        for level in anonymization_levels:
            with self.subTest(level=level):
                hittarget = HitTarget(
                    sector="technology",
                    anonymization_level=level
                )
                self.assertEqual(hittarget.anonymization_level, level)

    def test_organisation_types(self):
        """Test various organisation types"""
        org_types = [
            "customer", "prospect", "partner", "subsidiary", 
            "government_agency", "ngo", "educational_institution"
        ]
        
        for org_type in org_types:
            with self.subTest(org_type=org_type):
                hittarget = HitTarget(
                    sector="various",
                    organisation_type=org_type
                )
                self.assertEqual(hittarget.organisation_type, org_type)

    def test_sectors_validation(self):
        """Test various sector values"""
        test_sectors = [
            "financial", "healthcare", "technology", "manufacturing", "it", "tech",
            "retail", "education", "government", "gov", "energy", "telecommunications",
            "aerospace", "automotive", "construction", "media", "agriculture"
        ]
        
        valid_sectors = ["financial", "health", "technology", "manufacturing",
                         "retail", "education", "public_sector", "energy", "telecommunications",
                         "aerospace", "automotive", "construction", "media", "agriculture"]

        for sector in test_sectors:
            with self.subTest(sector=sector):
                hittarget = HitTarget(sector=sector)
                self.assertIn(hittarget.sector, valid_sectors)

    def test_regions_validation(self):
        """Test various region values"""
        valid_regions = [
            "north_america", "south_america", "europe", "asia_pacific", 
            "middle_east", "africa", "oceania", "global"
        ]
        
        for region in valid_regions:
            with self.subTest(region=region):
                hittarget = HitTarget(sector="technology", region=region)
                self.assertEqual(hittarget.region, region)

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Very long sector name
        long_sector = "a" * 1000
        hittarget_long = HitTarget(sector=long_sector)
        self.assertEqual(hittarget_long.sector, long_sector)
        
        # Single character sector (minimum length is 1)
        hittarget_short = HitTarget(sector="x")
        self.assertEqual(hittarget_short.sector, "x")
        
        # Special characters in sector
        special_sector = "high-tech_&_ai"
        hittarget_special = HitTarget(sector=special_sector)
        self.assertEqual(hittarget_special.sector, special_sector)

    def test_whitespace_handling(self):
        """Test handling of whitespace in various fields"""
        # Leading/trailing whitespace should be handled by normalization
        hittarget = HitTarget(
            sector="  finance  ",
            organisation_type="  bank  ",
            region="  europe  "
        )
        
        # Sector should resolve whitespace (automatic stripping)
        self.assertEqual(hittarget.sector, "financial")
        self.assertEqual(hittarget.organisation_type, "  bank  ")
        self.assertEqual(hittarget.region, "europe")


class TestHitTargetIntegration(unittest.TestCase):
    """Integration tests for HitTarget with other components"""

    def test_hittarget_in_submission_context(self):
        """Test hit target validation in the context of a full submission"""
        hittarget = HitTarget(
            sector="financial",
            organisation_size="large",
            region="europe"
        )
        
        # Should be able to access all required properties for submission validation
        self.assertIsNone(hittarget.organisation_id)
        self.assertIsInstance(hittarget.sector, str)
        self.assertGreater(len(hittarget.sector), 0)

class TestHitTargetValidationScenarios(unittest.TestCase):
    """Test various validation scenarios for HitTarget"""

    def test_sector_empty_string_validation(self):
        """Test that empty sector string is rejected"""
        with self.assertRaises(ValidationError) as context:
            HitTarget(sector="")
        
        error_str = str(context.exception)
        self.assertTrue(
            "at least 1 character" in error_str.lower() or
            "ensure this value has at least 1 character" in error_str.lower() or
            "string too short" in error_str.lower()
        )

    def test_sector_whitespace_only(self):
        """Test sector with only whitespace"""
        # This should be allowed and normalized)
        hittarget = HitTarget(sector="   ")
        self.assertEqual(hittarget.sector, "")

    def test_organisation_size_case_insensitive_normalization(self):
        """Test that organisation size normalization is case insensitive"""
        test_cases = [
            ("SMALL", "small"),
            ("Medium", "medium"),
            ("LARGE", "large"),
            ("Enterprise", "large"),
            ("SME", "small")
        ]
        
        for input_size, expected in test_cases:
            with self.subTest(input_size=input_size):
                hittarget = HitTarget(
                    sector="technology",
                    organisation_size=input_size
                )
                self.assertEqual(hittarget.organisation_size, expected)

    def test_invalid_field_types(self):
        """Test validation with invalid field types"""
        # sector must be string
        with self.assertRaises(ValidationError):
            HitTarget(sector=123)  # integer instead of string
        
        with self.assertRaises(ValidationError):
            HitTarget(sector=None)  # None instead of string
        
        with self.assertRaises(ValidationError):
            HitTarget(sector=["financial"])  # list instead of string


class TestHitTargetDataIntegrity(unittest.TestCase):
    """Test data integrity aspects of HitTarget"""

    def test_data_consistency_after_serialization(self):
        """Test that data remains consistent after serialization/deserialization"""
        original_hittarget = HitTarget(
            sector="healthcare",
            organisation_size="large",
            region="europe",
            anonymization_level="medium"
        )
        
        # Serialize to JSON
        json_data = original_hittarget.model_dump_json()
        
        # Parse back from JSON
        parsed_data = json.loads(json_data)
        recreated_hittarget = HitTarget(**parsed_data)
        
        # Should be equal
        self.assertEqual(original_hittarget, recreated_hittarget)
        self.assertEqual(original_hittarget.sector, recreated_hittarget.sector)
        self.assertEqual(original_hittarget.organisation_size, recreated_hittarget.organisation_size)
        self.assertEqual(original_hittarget.region, recreated_hittarget.region)


if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)