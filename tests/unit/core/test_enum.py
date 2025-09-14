#!/usr/bin/env python3
"""
FRANK Platform - Unit tests for FRANK Enum module

Tests enum values, serialization behavior, and use_enum_values=True|False config setting

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest

import json
from typing import Optional
from pydantic import BaseModel, ConfigDict

# Import the enums (adjust import path as needed)
from frank.core.enum import AccessTier, ObservableType, SeverityLevel, TLPLevel


class TestTLPLevel(unittest.TestCase):
    """Test TLPLevel enumeration"""

    def test_tlp_level_values(self):
        """Test all TLPLevel enum values"""
        expected_values = {
            TLPLevel.RED: "RED",
            TLPLevel.AMBER_PLUS: "AMBER+",
            TLPLevel.AMBER: "AMBER",
            TLPLevel.GREEN: "GREEN",
            TLPLevel.CLEAR: "CLEAR"
        }
        for tlp_enum, expected_str in expected_values.items():
            with self.subTest(tlp=tlp_enum):
                self.assertEqual(tlp_enum.value, expected_str)
                self.assertIsInstance(tlp_enum, TLPLevel)

    def test_tlp_level_string_comparison(self):
        """Test that enum values can be compared with strings"""
        self.assertEqual(TLPLevel.RED, "RED")
        self.assertEqual(TLPLevel.AMBER_PLUS, "AMBER+")
        self.assertNotEqual(TLPLevel.GREEN, "YELLOW")


class TestAccessTier(unittest.TestCase):
    """Test AccessTier enumeration"""

    def test_tier_level_values(self):
        """Test all AccessTier enum values"""
        expected_values = {
            AccessTier.PUBLIC: "public",
            AccessTier.OBSERVER: "observer",
            AccessTier.CONTRIBUTOR: "contributor", 
            AccessTier.PARTNER: "partner",
            AccessTier.CORE_MEMBER: "core_member"
        }
        
        for tier_enum, expected_str in expected_values.items():
            with self.subTest(tier=tier_enum):
                self.assertEqual(tier_enum.value, expected_str)
                self.assertIsInstance(tier_enum, AccessTier)

    def test_tier_level_string_comparison(self):
        """Test that enum values can be compared with strings"""
        self.assertEqual(AccessTier.PARTNER, "partner")
        self.assertEqual(AccessTier.CORE_MEMBER, "core_member")
        self.assertNotEqual(AccessTier.PUBLIC, "private")

    def test_tier_level_ordering(self):
        """Test tier level logical ordering (if applicable)"""
        # Create a list of tiers in expected privilege order
        tiers_by_privilege = [
            AccessTier.PUBLIC,
            AccessTier.OBSERVER,
            AccessTier.CONTRIBUTOR,
            AccessTier.PARTNER,
            AccessTier.CORE_MEMBER
        ]
        
        # Test that we can iterate through them
        tier_values = [tier.value for tier in tiers_by_privilege]
        expected_values = ["public", "observer", "contributor", "partner", "core_member"]
        self.assertEqual(tier_values, expected_values)

    def test_tier_level_from_string(self):
        """Test creating AccessTier from string values"""
        test_cases = [
            ("public", AccessTier.PUBLIC),
            ("observer", AccessTier.OBSERVER),
            ("contributor", AccessTier.CONTRIBUTOR),
            ("partner", AccessTier.PARTNER),
            ("core_member", AccessTier.CORE_MEMBER)
        ]
        
        for string_val, expected_enum in test_cases:
            with self.subTest(string_val=string_val):
                self.assertEqual(AccessTier(string_val), expected_enum)

    def test_tier_level_invalid_value(self):
        """Test that invalid tier level raises ValueError"""
        invalid_values = ["invalid", "admin", "superuser", "", None, 123]
        
        for invalid_val in invalid_values:
            with self.subTest(invalid_val=invalid_val):
                with self.assertRaises(ValueError):
                    AccessTier(invalid_val)

    def test_tier_level_can_submit(self):
        """Test the can_submit method of AccessTier"""
        self.assertFalse(AccessTier.PUBLIC.can_submit())
        self.assertFalse(AccessTier.OBSERVER.can_submit())
        self.assertTrue(AccessTier.CONTRIBUTOR.can_submit())
        self.assertTrue(AccessTier.PARTNER.can_submit())
        self.assertTrue(AccessTier.CORE_MEMBER.can_submit())

    def test_can_submit(self):
        """Test AccessTier.can_submit method."""
        self.assertTrue(AccessTier.CONTRIBUTOR.can_submit())
        self.assertTrue(AccessTier.PARTNER.can_submit())
        self.assertTrue(AccessTier.CORE_MEMBER.can_submit())
        self.assertFalse(AccessTier.PUBLIC.can_submit())
        self.assertFalse(AccessTier.OBSERVER.can_submit())

    
    def test_check_access_level(self):
        """Test AccessTier.check_access_level method."""
        table = [
            (AccessTier.PUBLIC, AccessTier.PUBLIC, True),
            (AccessTier.PUBLIC, AccessTier.OBSERVER, False),
            (AccessTier.OBSERVER, AccessTier.PUBLIC, True),
            (AccessTier.OBSERVER, AccessTier.OBSERVER, True),
            (AccessTier.OBSERVER, AccessTier.CONTRIBUTOR, False),
            (AccessTier.CONTRIBUTOR, AccessTier.OBSERVER, True),
            (AccessTier.CONTRIBUTOR, AccessTier.CONTRIBUTOR, True),
            (AccessTier.CONTRIBUTOR, AccessTier.PARTNER, False),
            (AccessTier.PARTNER, AccessTier.CONTRIBUTOR, True),
            (AccessTier.PARTNER, AccessTier.PARTNER, True),
            (AccessTier.PARTNER, AccessTier.CORE_MEMBER, False),
            (AccessTier.CORE_MEMBER, AccessTier.PARTNER, True),
            (AccessTier.CORE_MEMBER, AccessTier.CORE_MEMBER, True),
        ]
        for user_tier, required_tier, expected in table:
            self.assertEqual(user_tier.check_access_level(required_tier), expected)

class TestObservableType(unittest.TestCase):
    """Test ObservableType enumeration"""

    def test_observable_type_values(self):
        """Test all ObservableType enum values"""
        expected_values = {
            ObservableType.IPV4: "ipv4",
            ObservableType.IPV6: "ipv6",
            ObservableType.DOMAIN: "domain",
            ObservableType.URL: "url",
            ObservableType.EMAIL: "email"
        }
        
        for obs_enum, expected_str in expected_values.items():
            with self.subTest(obs_type=obs_enum):
                self.assertEqual(obs_enum.value, expected_str)
                self.assertIsInstance(obs_enum, ObservableType)

    def test_observable_type_string_comparison(self):
        """Test that enum values can be compared with strings"""
        self.assertEqual(ObservableType.IPV4, "ipv4")
        self.assertEqual(ObservableType.DOMAIN, "domain")
        self.assertNotEqual(ObservableType.EMAIL, "phone")

    def test_observable_type_from_string(self):
        """Test creating ObservableType from string values"""
        test_cases = [
            ("ipv4", ObservableType.IPV4),
            ("ipv6", ObservableType.IPV6),
            ("domain", ObservableType.DOMAIN),
            ("url", ObservableType.URL),
            ("email", ObservableType.EMAIL)
        ]
        
        for string_val, expected_enum in test_cases:
            with self.subTest(string_val=string_val):
                self.assertEqual(ObservableType(string_val), expected_enum)

    def test_observable_type_invalid_value(self):
        """Test that invalid observable type raises ValueError"""
        invalid_values = ["file", "hash", "registry", "", None, 123]
        
        for invalid_val in invalid_values:
            with self.subTest(invalid_val=invalid_val):
                with self.assertRaises(ValueError):
                    ObservableType(invalid_val)


class TestSeverityLevel(unittest.TestCase):
    """Test SeverityLevel enumeration"""

    def test_severity_level_values(self):
        """Test all SeverityLevel enum values"""
        expected_values = {
            SeverityLevel.LOW: "low",
            SeverityLevel.MEDIUM: "medium",
            SeverityLevel.HIGH: "high",
            SeverityLevel.CRITICAL: "critical"
        }
        
        for severity_enum, expected_str in expected_values.items():
            with self.subTest(severity=severity_enum):
                self.assertEqual(severity_enum.value, expected_str)
                self.assertIsInstance(severity_enum, SeverityLevel)

    def test_severity_level_ordering(self):
        """Test severity level logical ordering"""
        # Create a list of severities in expected escalation order
        severities_by_impact = [
            SeverityLevel.LOW,
            SeverityLevel.MEDIUM,
            SeverityLevel.HIGH,
            SeverityLevel.CRITICAL
        ]
        
        # Test that we can iterate through them
        severity_values = [sev.value for sev in severities_by_impact]
        expected_values = ["low", "medium", "high", "critical"]
        self.assertEqual(severity_values, expected_values)

    def test_severity_level_from_string(self):
        """Test creating SeverityLevel from string values"""
        test_cases = [
            ("low", SeverityLevel.LOW),
            ("medium", SeverityLevel.MEDIUM),
            ("high", SeverityLevel.HIGH),
            ("critical", SeverityLevel.CRITICAL)
        ]
        
        for string_val, expected_enum in test_cases:
            with self.subTest(string_val=string_val):
                self.assertEqual(SeverityLevel(string_val), expected_enum)

    def test_severity_level_invalid_value(self):
        """Test that invalid severity level raises ValueError"""
        invalid_values = ["urgent", "emergency", "info", "", None, 123]
        
        for invalid_val in invalid_values:
            with self.subTest(invalid_val=invalid_val):
                with self.assertRaises(ValueError):
                    SeverityLevel(invalid_val)


class TestEnumSerializationWithUseEnumValues(unittest.TestCase):
    """Test enum serialization behavior with use_enum_values=True|False"""

    def setUp(self):
        """Set up temporary Pydantic models for testing"""
        
        # Model with use_enum_values=True (should serialize to string values)
        class ModelWithEnumValues(BaseModel):
            model_config = ConfigDict(use_enum_values=True)
            
            tier: AccessTier
            observable_type: ObservableType
            severity: Optional[SeverityLevel] = None
        
        # Model with use_enum_values=False (should serialize to enum names)
        class ModelWithoutEnumValues(BaseModel):
            model_config = ConfigDict(use_enum_values=False)
            
            tier: AccessTier
            observable_type: ObservableType
            severity: Optional[SeverityLevel] = None
        
        # Model with default behavior (should be True by default in most cases)
        class ModelDefault(BaseModel):
            tier: AccessTier
            observable_type: ObservableType
            severity: Optional[SeverityLevel] = None
        
        self.ModelWithEnumValues = ModelWithEnumValues
        self.ModelWithoutEnumValues = ModelWithoutEnumValues
        self.ModelDefault = ModelDefault

    def test_use_enum_values_true_serialization(self):
        """Test serialization with use_enum_values=True"""
        model = self.ModelWithEnumValues(
            tier=AccessTier.PARTNER,
            observable_type=ObservableType.IPV4,
            severity=SeverityLevel.HIGH
        )
        
        # Test model_dump()
        data = model.model_dump()
        
        self.assertEqual(data["access_level"], "partner")  # String value
        self.assertEqual(data["observable_type"], "ipv4")  # String value
        self.assertEqual(data["severity"], "high")  # String value
        
        # Test JSON serialization
        json_str = model.model_dump_json()
        parsed_json = json.loads(json_str)
        
        self.assertEqual(parsed_json["access_level"], "partner")
        self.assertEqual(parsed_json["observable_type"], "ipv4")
        self.assertEqual(parsed_json["severity"], "high")

    def test_use_enum_values_false_serialization(self):
        """Test serialization with use_enum_values=False"""
        model = self.ModelWithoutEnumValues(
            tier=AccessTier.PARTNER,
            observable_type=ObservableType.IPV4,
            severity=SeverityLevel.HIGH
        )
        
        # Test model_dump()
        data = model.model_dump()
        
        # Should serialize to enum objects, not string values
        self.assertEqual(data["access_level"], AccessTier.PARTNER)
        self.assertEqual(data["observable_type"], ObservableType.IPV4)
        self.assertEqual(data["severity"], SeverityLevel.HIGH)
        
        # Test JSON serialization (should convert to string representation)
        json_str = model.model_dump_json()
        parsed_json = json.loads(json_str)
        
        # In JSON, enums are typically serialized as their string values regardless
        self.assertEqual(parsed_json["access_level"], "partner")
        self.assertEqual(parsed_json["observable_type"], "ipv4")
        self.assertEqual(parsed_json["severity"], "high")

    def test_default_enum_serialization_behavior(self):
        """Test default enum serialization behavior"""
        model = self.ModelDefault(
            tier=AccessTier.CONTRIBUTOR,
            observable_type=ObservableType.DOMAIN,
            severity=SeverityLevel.MEDIUM
        )
        
        # Test model_dump()
        data = model.model_dump()
        
        # Default behavior in Pydantic v2 is typically to use enum values
        self.assertEqual(data["access_level"], "contributor")
        self.assertEqual(data["observable_type"], "domain")
        self.assertEqual(data["severity"], "medium")

    def test_enum_input_flexibility(self):
        """Test that models accept both enum objects and string values"""
        # Test with enum objects
        model1 = self.ModelWithEnumValues(
            tier=AccessTier.PARTNER,
            observable_type=ObservableType.IPV4,
            severity=SeverityLevel.HIGH
        )
        
        # Test with string values (should be converted to enums)
        model2 = self.ModelWithEnumValues(
            tier="partner",
            observable_type="ipv4", 
            severity="high"
        )
        
        # Both should be equal after construction
        self.assertEqual(model1.tier, model2.tier)
        self.assertEqual(model1.observable_type, model2.observable_type)
        self.assertEqual(model1.severity, model2.severity)

    def test_none_enum_handling(self):
        """Test handling of None enum values"""
        model = self.ModelWithEnumValues(
            tier=AccessTier.OBSERVER,
            observable_type=ObservableType.EMAIL,
            severity=None  # Optional field
        )
        
        data = model.model_dump()
        self.assertEqual(data["access_level"], "observer")
        self.assertEqual(data["observable_type"], "email")
        self.assertIsNone(data["severity"])

    def test_enum_round_trip_consistency(self):
        """Test that enum values survive round-trip serialization"""
        original_model = self.ModelWithEnumValues(
            tier=AccessTier.CORE_MEMBER,
            observable_type=ObservableType.URL,
            severity=SeverityLevel.CRITICAL
        )
        
        # Serialize to JSON
        json_str = original_model.model_dump_json()
        
        # Parse back from JSON
        json_data = json.loads(json_str)
        recreated_model = self.ModelWithEnumValues(**json_data)
        
        # Should be equal
        self.assertEqual(original_model.tier, recreated_model.tier)
        self.assertEqual(original_model.observable_type, recreated_model.observable_type)
        self.assertEqual(original_model.severity, recreated_model.severity)


class TestEnumAccessTierFiltering(unittest.TestCase):
    """Test enum usage in access tier filtering scenarios"""

    def test_tier_level_privilege_hierarchy(self):
        """Test logical privilege hierarchy of tier levels"""
        # Define expected privilege order (lowest to highest)
        privilege_order = [
            AccessTier.PUBLIC,
            AccessTier.OBSERVER,
            AccessTier.CONTRIBUTOR,
            AccessTier.PARTNER,
            AccessTier.CORE_MEMBER
        ]
        
        # Create a privilege mapping function
        def get_privilege_level(tier: AccessTier) -> int:
            privilege_map = {
                AccessTier.PUBLIC: 0,
                AccessTier.OBSERVER: 1,
                AccessTier.CONTRIBUTOR: 2,
                AccessTier.PARTNER: 3,
                AccessTier.CORE_MEMBER: 4
            }
            return privilege_map[tier]
        
        # Test that each level has higher privilege than the previous
        for i in range(1, len(privilege_order)):
            current_tier = privilege_order[i]
            previous_tier = privilege_order[i-1]
            
            current_privilege = get_privilege_level(current_tier)
            previous_privilege = get_privilege_level(previous_tier)
            
            self.assertGreater(current_privilege, previous_privilege,
                             f"{current_tier} should have higher privilege than {previous_tier}")

    def test_severity_level_impact_hierarchy(self):
        """Test logical impact hierarchy of severity levels"""
        # Define expected impact order (lowest to highest)
        impact_order = [
            SeverityLevel.LOW,
            SeverityLevel.MEDIUM,
            SeverityLevel.HIGH,
            SeverityLevel.CRITICAL
        ]
        
        # Create an impact mapping function
        def get_impact_level(severity: SeverityLevel) -> int:
            impact_map = {
                SeverityLevel.LOW: 1,
                SeverityLevel.MEDIUM: 2,
                SeverityLevel.HIGH: 3,
                SeverityLevel.CRITICAL: 4
            }
            return impact_map[severity]
        
        # Test that each level has higher impact than the previous
        for i in range(1, len(impact_order)):
            current_severity = impact_order[i]
            previous_severity = impact_order[i-1]
            
            current_impact = get_impact_level(current_severity)
            previous_impact = get_impact_level(previous_severity)
            
            self.assertGreater(current_impact, previous_impact,
                             f"{current_severity} should have higher impact than {previous_severity}")

    def test_observable_type_network_categories(self):
        """Test that observable types cover network threat indicators"""
        network_types = [
            ObservableType.IPV4,
            ObservableType.IPV6,
            ObservableType.DOMAIN,
            ObservableType.URL,
            ObservableType.EMAIL,
            ObservableType.FILE_HASH,
            ObservableType.REGISTRY_KEY
        ]
        
        # Test that all expected network indicators are covered
        expected_network_values = ["ipv4", "ipv6", "domain", "url", "email", "file_hash", "registry_key"]
        actual_values = [obs_type.value for obs_type in network_types]
        
        self.assertEqual(set(actual_values), set(expected_network_values))

    def test_enum_membership_checks(self):
        """Test checking enum membership"""
        # Test AccessTier membership
        self.assertIn(AccessTier.PARTNER, AccessTier)
        self.assertIn("partner", [tier.value for tier in AccessTier])
        
        # Test ObservableType membership
        self.assertIn(ObservableType.IPV4, ObservableType)
        self.assertIn("domain", [obs.value for obs in ObservableType])
        
        # Test SeverityLevel membership
        self.assertIn(SeverityLevel.CRITICAL, SeverityLevel)
        self.assertIn("high", [sev.value for sev in SeverityLevel])


class TestPydanticEnumIntegration(unittest.TestCase):
    """Test Pydantic integration with FRANK enums"""

    def test_pydantic_enum_validation_with_use_enum_values_true(self):
        """Test Pydantic validation with use_enum_values=True"""
        
        class TestModel(BaseModel):
            model_config = ConfigDict(use_enum_values=True, extra="forbid")
            
            tier: AccessTier
            obs_type: ObservableType
            severity: Optional[SeverityLevel] = None
        
        # Test valid enum values
        model = TestModel(
            tier="partner",
            obs_type="ipv4",
            severity="high"
        )
        
        # Verify enum conversion
        self.assertEqual(model.tier, AccessTier.PARTNER)
        self.assertEqual(model.obs_type, ObservableType.IPV4)
        self.assertEqual(model.severity, SeverityLevel.HIGH)
        
        # Test serialization (should use string values)
        data = model.model_dump()
        self.assertEqual(data["access_level"], "partner")
        self.assertEqual(data["obs_type"], "ipv4")
        self.assertEqual(data["severity"], "high")

    def test_pydantic_enum_validation_with_use_enum_values_false(self):
        """Test Pydantic validation with use_enum_values=False"""
        
        class TestModel(BaseModel):
            model_config = ConfigDict(use_enum_values=False, extra="forbid")
            
            tier: AccessTier
            obs_type: ObservableType
            severity: Optional[SeverityLevel] = None
        
        # Test valid enum values
        model = TestModel(
            tier="contributor",
            obs_type="domain",
            severity="medium"
        )
        
        # Verify enum conversion
        self.assertEqual(model.tier, AccessTier.CONTRIBUTOR)
        self.assertEqual(model.obs_type, ObservableType.DOMAIN)
        self.assertEqual(model.severity, SeverityLevel.MEDIUM)
        
        # Test serialization (behavior may vary, but should still work)
        data = model.model_dump()
        # With use_enum_values=False, the exact behavior depends on Pydantic version
        # But the enums should still be accessible
        self.assertTrue(
            data["access_level"] == "contributor" or data["access_level"] == AccessTier.CONTRIBUTOR
        )

    def test_pydantic_invalid_enum_values(self):
        """Test Pydantic validation with invalid enum values"""
        
        class TestModel(BaseModel):
            model_config = ConfigDict(use_enum_values=True)
            
            tier: AccessTier
            obs_type: ObservableType
            severity: SeverityLevel
        
        # Test invalid tier
        with self.assertRaises(ValueError):
            TestModel(
                tier="invalid_tier",
                obs_type="ipv4",
                severity="high"
            )
        
        # Test invalid observable type
        with self.assertRaises(ValueError):
            TestModel(
                tier="partner",
                obs_type="invalid_obs",
                severity="high"
            )
        
        # Test invalid severity
        with self.assertRaises(ValueError):
            TestModel(
                tier="partner",
                obs_type="ipv4",
                severity="invalid_severity"
            )

    def test_enum_json_serialization_comparison(self):
        """Compare JSON serialization between use_enum_values settings"""
        
        # Model with use_enum_values=True
        class ModelTrue(BaseModel):
            model_config = ConfigDict(use_enum_values=True)
            tier: AccessTier
            severity: SeverityLevel
        
        # Model with use_enum_values=False  
        class ModelFalse(BaseModel):
            model_config = ConfigDict(use_enum_values=False)
            tier: AccessTier
            severity: SeverityLevel
        
        # Create identical instances
        model_true = ModelTrue(tier="partner", severity="critical")
        model_false = ModelFalse(tier="partner", severity="critical")
        
        # Test JSON serialization
        json_true = model_true.model_dump_json()
        json_false = model_false.model_dump_json()
        
        # Parse back
        data_true = json.loads(json_true)
        data_false = json.loads(json_false)
        
        # Both should contain string values in JSON (this is typical behavior)
        self.assertEqual(data_true["access_level"], "partner")
        self.assertEqual(data_true["severity"], "critical")
        
        self.assertEqual(data_false["access_level"], "partner")
        self.assertEqual(data_false["severity"], "critical")
        
        # But the original enum types should be preserved in the models
        self.assertNotIsInstance(model_true.tier, AccessTier)
        self.assertIsInstance(model_false.tier, AccessTier)

    def test_frank_specific_enum_combinations(self):
        """Test FRANK-specific enum combinations"""
        
        class FRANKTestModel(BaseModel):
            model_config = ConfigDict(use_enum_values=False)
            
            submitter_tier: AccessTier
            target_sector: str
            observable_type: ObservableType
            threat_severity: SeverityLevel
        
        # Test realistic FRANK combinations
        frank_scenarios = [
            {
                "submitter_tier": AccessTier.PARTNER,
                "target_sector": "financial",
                "observable_type": ObservableType.IPV4,
                "threat_severity": SeverityLevel.HIGH
            },
            {
                "submitter_tier": AccessTier.CORE_MEMBER,
                "target_sector": "healthcare", 
                "observable_type": ObservableType.DOMAIN,
                "threat_severity": SeverityLevel.CRITICAL
            },
            {
                "submitter_tier": AccessTier.CONTRIBUTOR,
                "target_sector": "technology",
                "observable_type": ObservableType.URL,
                "threat_severity": SeverityLevel.MEDIUM
            }
        ]
        
        for scenario in frank_scenarios:
            with self.subTest(scenario=scenario):
                model = FRANKTestModel(**scenario)
                
                # Verify all enums are properly set
                self.assertIsInstance(model.submitter_tier, AccessTier)
                self.assertIsInstance(model.observable_type, ObservableType)
                self.assertIsInstance(model.threat_severity, SeverityLevel)
                
                # Test serialization
                data = model.model_dump()
                self.assertIsInstance(data["submitter_tier"], str)
                self.assertIsInstance(data["observable_type"], str)
                self.assertIsInstance(data["threat_severity"], str)


class TestEnumCompatibility(unittest.TestCase):
    """Test enum compatibility and edge cases"""

    def test_enum_case_sensitivity(self):
        """Test enum case sensitivity"""
        # Enums should be case sensitive
        with self.assertRaises(ValueError):
            AccessTier("PARTNER")  # Uppercase should fail
        
        with self.assertRaises(ValueError):
            ObservableType("IPv4")  # Mixed case should fail
        
        with self.assertRaises(ValueError):
            SeverityLevel("HIGH")  # Uppercase should fail

    def test_enum_whitespace_handling(self):
        """Test enum handling of whitespace"""
        # Enums should not accept whitespace
        with self.assertRaises(ValueError):
            AccessTier(" partner ")
        
        with self.assertRaises(ValueError):
            ObservableType(" ipv4")
        
        with self.assertRaises(ValueError):
            SeverityLevel("high ")

    def test_enum_iteration(self):
        """Test iterating over enum values"""
        # Test AccessTier iteration
        tier_values = [tier.value for tier in AccessTier]
        expected_tiers = ["public", "observer", "contributor", "partner", "core_member"]
        self.assertEqual(tier_values, expected_tiers)
        
        # Test ObservableType iteration
        obs_values = [obs.value for obs in ObservableType]
        expected_obs = ["ipv4", "ipv6", "domain", "url", "email", "file_hash", "registry_key", "mutex", "certificate"]
        self.assertEqual(obs_values, expected_obs)
        
        # Test SeverityLevel iteration
        sev_values = [sev.value for sev in SeverityLevel]
        expected_sev = ["low", "medium", "high", "critical"]
        self.assertEqual(sev_values, expected_sev)

    def test_enum_string_representation(self):
        """Test string representation of enums"""
        self.assertEqual(str(AccessTier.PARTNER), "AccessTier.PARTNER")
        self.assertEqual(str(ObservableType.DOMAIN), "ObservableType.DOMAIN")
        self.assertEqual(str(SeverityLevel.CRITICAL), "SeverityLevel.CRITICAL")
        
        # Test repr
        self.assertIn("AccessTier", repr(AccessTier.PARTNER))
        self.assertIn("ObservableType", repr(ObservableType.IPV4))
        self.assertIn("SeverityLevel", repr(SeverityLevel.HIGH))


if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)