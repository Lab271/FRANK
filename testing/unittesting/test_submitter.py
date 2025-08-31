#!/usr/bin/env python3
"""
Unit tests for FRANK Submitter model
Tests the "be forgiving on what you receive, strong on what you return" principle
"""

import unittest
from unittest.mock import patch
import uuid
from datetime import datetime

# Import the models (adjust import path as needed)
from frank.core.models import Submitter, TierLevel
from pydantic import ValidationError


class TestSubmitter(unittest.TestCase):
    """Comprehensive unit tests for the Submitter model"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.valid_submitter_data = {
            "tier": TierLevel.PARTNER,
            "sector": "financial",
            "region": "europe"
        }

    def test_create_minimal_submitter(self):
        """Test creating a submitter with minimal required fields"""
        submitter = Submitter(tier=TierLevel.PARTNER)
        
        # Check that required fields are set
        self.assertEqual(submitter.tier, TierLevel.PARTNER)
        self.assertEqual(submitter.organization_type, "cyber_partner")  # default
        self.assertEqual(submitter.submission_method, "api")  # default
        
        # Check that organization_id is auto-generated
        self.assertIsNotNone(submitter.organization_id)
        self.assertTrue(submitter.organization_id.startswith("identity--"))
        self.assertIsInstance(uuid.UUID(submitter.organization_id.split("--")[1]), uuid.UUID)

    def test_create_submitter_with_all_fields(self):
        """Test creating a submitter with all fields provided"""
        org_id = f"identity--{uuid.uuid4()}"
        submitter = Submitter(
            organization_id=org_id,
            tier=TierLevel.CORE_MEMBER,
            organization_type="mssp",
            sector="technology",
            region="north_america",
            submission_method="automated_feed",
            client_count=150
        )
        
        self.assertEqual(submitter.organization_id, org_id)
        self.assertEqual(submitter.tier, TierLevel.CORE_MEMBER)
        self.assertEqual(submitter.organization_type, "mssp")
        self.assertEqual(submitter.sector, "technology")
        self.assertEqual(submitter.region, "north_america")
        self.assertEqual(submitter.submission_method, "automated_feed")
        self.assertEqual(submitter.client_count, 150)

    def test_organization_id_auto_generation(self):
        """Test that organization_id is auto-generated when not provided"""
        # Test with None
        submitter1 = Submitter(tier=TierLevel.PARTNER, organization_id=None)
        self.assertIsNotNone(submitter1.organization_id)
        self.assertTrue(submitter1.organization_id.startswith("identity--"))
        
        # Test with empty string
        submitter2 = Submitter(tier=TierLevel.PARTNER, organization_id="")
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
                submitter = Submitter(tier=TierLevel.PARTNER, sector=input_sector)
                self.assertEqual(submitter.sector, expected_output)

    def test_sector_none_handling(self):
        """Test that None sector is handled properly"""
        submitter = Submitter(tier=TierLevel.PARTNER, sector=None)
        self.assertIsNone(submitter.sector)

    def test_tier_validation(self):
        """Test tier level validation"""
        # Valid tiers
        valid_tiers = [
            TierLevel.PUBLIC,
            TierLevel.OBSERVER,
            TierLevel.CONTRIBUTOR,
            TierLevel.PARTNER,
            TierLevel.CORE_MEMBER
        ]
        
        for tier in valid_tiers:
            with self.subTest(tier=tier):
                submitter = Submitter(tier=tier)
                self.assertEqual(submitter.tier, tier)
        
        # Test with string values (should work with enum)
        submitter = Submitter(tier="partner")
        self.assertEqual(submitter.tier, TierLevel.PARTNER)

    def test_invalid_tier_raises_error(self):
        """Test that invalid tier raises validation error"""
        with self.assertRaises(ValidationError) as context:
            Submitter(tier="invalid_tier")
        
        self.assertIn("tier", str(context.exception))

    def test_client_count_validation(self):
        """Test client count validation"""
        # Valid client counts
        valid_counts = [0, 1, 100, 10000]
        for count in valid_counts:
            with self.subTest(count=count):
                submitter = Submitter(tier=TierLevel.PARTNER, client_count=count)
                self.assertEqual(submitter.client_count, count)
        
        # Invalid client count (negative)
        with self.assertRaises(ValidationError):
            Submitter(tier=TierLevel.PARTNER, client_count=-1)

    def test_factory_method_create(self):
        """Test the create factory method"""
        submitter = Submitter.create(
            tier=TierLevel.CONTRIBUTOR,
            sector="healthcare",
            region="asia_pacific"
        )
        
        self.assertEqual(submitter.tier, TierLevel.CONTRIBUTOR)
        self.assertEqual(submitter.sector, "health")  # Should be normalized
        self.assertEqual(submitter.region, "asia_pacific")
        self.assertIsNotNone(submitter.organization_id)

    def test_factory_method_minimal(self):
        """Test factory method with minimal parameters"""
        submitter = Submitter.create(tier=TierLevel.OBSERVER)
        
        self.assertEqual(submitter.tier, TierLevel.OBSERVER)
        self.assertIsNone(submitter.sector)
        self.assertIsNone(submitter.region)
        self.assertIsNotNone(submitter.organization_id)

    def test_model_dump(self):
        """Test serialization to dictionary"""
        submitter = Submitter(
            tier=TierLevel.PARTNER,
            sector="financial",
            region="europe",
            client_count=50
        )
        
        data = submitter.model_dump()
        
        # Check that all fields are present
        self.assertIn("organization_id", data)
        self.assertIn("tier", data)
        self.assertIn("organization_type", data)
        self.assertIn("sector", data)
        self.assertIn("region", data)
        self.assertIn("submission_method", data)
        self.assertIn("client_count", data)
        
        # Check values
        self.assertEqual(data["tier"], "partner")  # Enum value
        self.assertEqual(data["sector"], "financial")
        self.assertEqual(data["region"], "europe")
        self.assertEqual(data["client_count"], 50)

    def test_model_dump_exclude_none(self):
        """Test serialization excluding None values"""
        submitter = Submitter(tier=TierLevel.PARTNER)  # sector, region, client_count will be None
        
        data = submitter.model_dump(exclude_none=True)
        
        # Check that None fields are excluded
        self.assertNotIn("sector", data)
        self.assertNotIn("region", data)
        self.assertNotIn("client_count", data)
        
        # Check that non-None fields are present
        self.assertIn("organization_id", data)
        self.assertIn("tier", data)

    def test_json_serialization(self):
        """Test JSON serialization"""
        submitter = Submitter(
            tier=TierLevel.PARTNER,
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
            tier=TierLevel.PARTNER,
            sector="financial",
            unknown_field="should_be_ignored",
            another_extra_field=123
        )
        
        self.assertEqual(submitter.tier, TierLevel.PARTNER)
        self.assertEqual(submitter.sector, "financial")
        # Extra fields should not be accessible
        self.assertFalse(hasattr(submitter, 'unknown_field'))

    def test_submitter_equality(self):
        """Test submitter equality comparison"""
        org_id = f"identity--{uuid.uuid4()}"
        
        submitter1 = Submitter(
            organization_id=org_id,
            tier=TierLevel.PARTNER,
            sector="financial"
        )
        
        submitter2 = Submitter(
            organization_id=org_id,
            tier=TierLevel.PARTNER,
            sector="financial"
        )
        
        # Different instances with same data should be equal
        self.assertEqual(submitter1, submitter2)

    def test_submitter_inequality(self):
        """Test submitter inequality"""
        submitter1 = Submitter(tier=TierLevel.PARTNER, sector="financial")
        submitter2 = Submitter(tier=TierLevel.CONTRIBUTOR, sector="financial")
        
        # Different tiers should not be equal
        self.assertNotEqual(submitter1, submitter2)

    def test_repr_and_str(self):
        """Test string representations"""
        submitter = Submitter(tier=TierLevel.PARTNER, sector="financial")
        
        repr_str = repr(submitter)
        str_str = str(submitter)
        
        self.assertIsInstance(repr_str, str)
        self.assertIsInstance(str_str, str)
        self.assertIn("Submitter", repr_str)

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Empty strings should be handled
        submitter = Submitter(
            tier=TierLevel.PARTNER,
            sector="",  # Empty string
            region=""   # Empty string
        )
        
        # Empty sector should be normalized (though result might be empty)
        self.assertIsNotNone(submitter.sector)
        
        # Very long strings (should be accepted)
        long_sector = "a" * 1000
        submitter_long = Submitter(tier=TierLevel.PARTNER, sector=long_sector)
        self.assertEqual(submitter_long.sector, long_sector)


class TestSubmitterIntegration(unittest.TestCase):
    """Integration tests for Submitter with other components"""

    def test_submitter_in_submission_context(self):
        """Test submitter validation in the context of a full submission"""
        # This tests that the submitter works properly as part of larger validation
        submitter = Submitter(tier=TierLevel.PARTNER, sector="financial")
        
        # Should be able to access all required properties for submission validation
        self.assertIsNotNone(submitter.organization_id)
        self.assertEqual(submitter.tier, TierLevel.PARTNER)
        self.assertEqual(submitter.sector, "financial")

    def test_multiple_submitters_unique_ids(self):
        """Test that multiple submitters get unique IDs"""
        submitters = [Submitter(tier=TierLevel.PARTNER) for _ in range(10)]
        
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
                tier=TierLevel.PARTNER,
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


if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)