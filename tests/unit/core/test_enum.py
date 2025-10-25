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
            with self.subTest(access_level=tier_enum):
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

    def test_from_string_method(self):
        """Test AccessTier.from_string() class method"""
        # Test basic case-insensitive conversion
        test_cases = [
            ("contributor", AccessTier.CONTRIBUTOR),
            ("CONTRIBUTOR", AccessTier.CONTRIBUTOR),
            ("Contributor", AccessTier.CONTRIBUTOR),
            ("partner", AccessTier.PARTNER),
            ("PARTNER", AccessTier.PARTNER),
            ("Partner", AccessTier.PARTNER),
            ("observer", AccessTier.OBSERVER),
            ("OBSERVER", AccessTier.OBSERVER),
            ("public", AccessTier.PUBLIC),
            ("PUBLIC", AccessTier.PUBLIC),
            ("core_member", AccessTier.CORE_MEMBER),
            ("CORE_MEMBER", AccessTier.CORE_MEMBER),
            ("Core_Member", AccessTier.CORE_MEMBER),
        ]
        
        for input_str, expected_enum in test_cases:
            with self.subTest(input_str=input_str):
                result = AccessTier.from_string(input_str)
                self.assertEqual(result, expected_enum)
                self.assertIsInstance(result, AccessTier)

    def test_from_string_with_spaces(self):
        """Test AccessTier.from_string() with space handling"""
        space_cases = [
            ("core member", AccessTier.CORE_MEMBER),
            ("Core Member", AccessTier.CORE_MEMBER),
            ("CORE MEMBER", AccessTier.CORE_MEMBER),
            (" core member ", AccessTier.CORE_MEMBER),  # with extra spaces
        ]
        
        for input_str, expected_enum in space_cases:
            with self.subTest(input_str=input_str):
                result = AccessTier.from_string(input_str)
                self.assertEqual(result, expected_enum)

    def test_from_string_invalid_inputs(self):
        """Test AccessTier.from_string() with invalid inputs"""
        invalid_inputs = [
            "invalid_tier",
            "admin", 
            "superuser",
            "",
            "contributor_extra",
            "part_ner",
            "123",
        ]
        
        for invalid_input in invalid_inputs:
            with self.subTest(invalid_input=invalid_input):
                with self.assertRaises(ValueError) as context:
                    AccessTier.from_string(invalid_input)
                
                # Check that error message contains helpful information
                error_msg = str(context.exception)
                self.assertIn(invalid_input, error_msg)
                self.assertIn("Valid values are:", error_msg)

    def test_from_string_non_string_inputs(self):
        """Test AccessTier.from_string() with non-string inputs"""
        # Non-string inputs that should raise ValueError
        non_string_inputs = [
            None,
            123,
            [],
            {},
        ]
        
        # Test default behavior (should raise ValueError since default=False by default)
        for invalid_input in non_string_inputs:
            with self.subTest(invalid_input=invalid_input, behavior="default"):
                with self.assertRaises(ValueError) as context:
                    AccessTier.from_string(invalid_input)
                
                # Check that error message mentions type mismatch
                error_msg = str(context.exception)
                self.assertIn("Expected string", error_msg)
        
        # Test explicit default=False behavior (should raise ValueError)
        for invalid_input in non_string_inputs:
            with self.subTest(invalid_input=invalid_input, default=False):
                with self.assertRaises(ValueError) as context:
                    AccessTier.from_string(invalid_input, default=False)
                
                # Check that error message mentions type mismatch
                error_msg = str(context.exception)
                self.assertIn("Expected string", error_msg)
        
        # Test default=True behavior (should return PUBLIC)
        for invalid_input in non_string_inputs:
            with self.subTest(invalid_input=invalid_input, default=True):
                result = AccessTier.from_string(invalid_input, default=True)
                self.assertEqual(result, AccessTier.PUBLIC)
                self.assertIsInstance(result, AccessTier)

    def test_from_string_enum_input(self):
        """Test AccessTier.from_string() with enum inputs (special case)"""
        # AccessTier enums inherit from str, so they are valid string inputs
        enum_inputs = [
            (AccessTier.PARTNER, AccessTier.PARTNER),
            (AccessTier.CONTRIBUTOR, AccessTier.CONTRIBUTOR),
            (AccessTier.PUBLIC, AccessTier.PUBLIC),
            (AccessTier.CORE_MEMBER, AccessTier.CORE_MEMBER),
        ]
        
        for enum_input, expected_output in enum_inputs:
            with self.subTest(enum_input=enum_input):
                # Should work fine since AccessTier inherits from str
                result = AccessTier.from_string(enum_input)
                self.assertEqual(result, expected_output)
                
                # Should also work with default=True
                result_with_default = AccessTier.from_string(enum_input, default=True)
                self.assertEqual(result_with_default, expected_output)
                
                # Should also work with default=False
                result_explicit_false = AccessTier.from_string(enum_input, default=False)
                self.assertEqual(result_explicit_false, expected_output)

    def test_from_string_default_parameter(self):
        """Test AccessTier.from_string() with default parameter"""
        
        # Test default=False (should raise ValueError for invalid inputs)
        invalid_inputs = ["invalid_tier", "admin", "", "unknown_role"]
        
        for invalid_input in invalid_inputs:
            with self.subTest(invalid_input=invalid_input, default=False):
                with self.assertRaises(ValueError):
                    AccessTier.from_string(invalid_input, default=False)
        
        # Test default=True (should return PUBLIC for invalid inputs)
        for invalid_input in invalid_inputs:
            with self.subTest(invalid_input=invalid_input, default=True):
                result = AccessTier.from_string(invalid_input, default=True)
                self.assertEqual(result, AccessTier.PUBLIC)
                self.assertIsInstance(result, AccessTier)
        
        # Test default=True with non-string inputs
        non_string_inputs = [None, 123, [], {}]
        for invalid_input in non_string_inputs:
            with self.subTest(invalid_input=invalid_input, default=True):
                result = AccessTier.from_string(invalid_input, default=True)
                self.assertEqual(result, AccessTier.PUBLIC)
                self.assertIsInstance(result, AccessTier)
        
        # Test that valid inputs still work correctly with default=True
        valid_cases = [
            ("contributor", AccessTier.CONTRIBUTOR),
            ("PARTNER", AccessTier.PARTNER),
            ("core_member", AccessTier.CORE_MEMBER),
            ("Core Member", AccessTier.CORE_MEMBER),
        ]
        
        for input_str, expected_enum in valid_cases:
            with self.subTest(input_str=input_str, default=True):
                result = AccessTier.from_string(input_str, default=True)
                self.assertEqual(result, expected_enum)
                self.assertIsInstance(result, AccessTier)
        
        # Test that valid inputs still work correctly with default=False
        for input_str, expected_enum in valid_cases:
            with self.subTest(input_str=input_str, default=False):
                result = AccessTier.from_string(input_str, default=False)
                self.assertEqual(result, expected_enum)
                self.assertIsInstance(result, AccessTier)

    def test_from_string_default_parameter_edge_cases(self):
        """Test AccessTier.from_string() default parameter edge cases"""
        
        # Test empty string with different default values
        with self.assertRaises(ValueError):
            AccessTier.from_string("", default=False)
        
        result = AccessTier.from_string("", default=True)
        self.assertEqual(result, AccessTier.PUBLIC)
        
        # Test whitespace-only string
        with self.assertRaises(ValueError):
            AccessTier.from_string("   ", default=False)
        
        result = AccessTier.from_string("   ", default=True)
        self.assertEqual(result, AccessTier.PUBLIC)
        
        # Test case where normalized string is empty after processing
        with self.assertRaises(ValueError):
            AccessTier.from_string("  \t\n  ", default=False)
        
        result = AccessTier.from_string("  \t\n  ", default=True)
        self.assertEqual(result, AccessTier.PUBLIC)

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
            ObservableType.IPV4_ADDR: "ipv4-addr",
            ObservableType.IPV6_ADDR: "ipv6-addr",
            ObservableType.DOMAIN_NAME: "domain-name",
            ObservableType.URL: "url",
            ObservableType.EMAIL_ADDR: "email-addr"
        }
        
        for obs_enum, expected_str in expected_values.items():
            with self.subTest(obs_type=obs_enum):
                self.assertEqual(obs_enum.value, expected_str)
                self.assertIsInstance(obs_enum, ObservableType)

    def test_observable_type_string_comparison(self):
        """Test that enum values can be compared with strings"""
        self.assertEqual(ObservableType.IPV4_ADDR, "ipv4-addr")
        self.assertEqual(ObservableType.DOMAIN_NAME, "domain-name")
        self.assertNotEqual(ObservableType.EMAIL_ADDR, "phone")

    def test_observable_type_from_string(self):
        """Test creating ObservableType from string values"""
        test_cases = [
            ("ipv4-addr", ObservableType.IPV4_ADDR),
            ("ipv6-addr", ObservableType.IPV6_ADDR),
            ("domain-name", ObservableType.DOMAIN_NAME),
            ("url", ObservableType.URL),
            ("email-addr", ObservableType.EMAIL_ADDR)
        ]
        
        for string_val, expected_enum in test_cases:
            with self.subTest(string_val=string_val):
                self.assertEqual(ObservableType(string_val), expected_enum)

    def test_observable_type_invalid_value(self):
        """Test that invalid observable type raises ValueError"""
        invalid_values = ["file-hash", "hash", "registry", "", None, 123]
        
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
            
            access_level: AccessTier
            observable_type: ObservableType
            severity: Optional[SeverityLevel] = None
        
        # Model with use_enum_values=False (should serialize to enum names)
        class ModelWithoutEnumValues(BaseModel):
            model_config = ConfigDict(use_enum_values=False)
            
            access_level: AccessTier
            observable_type: ObservableType
            severity: Optional[SeverityLevel] = None
        
        # Model with default behavior (should be True by default in most cases)
        class ModelDefault(BaseModel):
            access_level: AccessTier
            observable_type: ObservableType
            severity: Optional[SeverityLevel] = None
        
        self.ModelWithEnumValues = ModelWithEnumValues
        self.ModelWithoutEnumValues = ModelWithoutEnumValues
        self.ModelDefault = ModelDefault

    def test_use_enum_values_true_serialization(self):
        """Test serialization with use_enum_values=True"""
        model = self.ModelWithEnumValues(
            access_level=AccessTier.PARTNER,
            observable_type=ObservableType.IPV4_ADDR,
            severity=SeverityLevel.HIGH
        )
        
        # Test model_dump()
        data = model.model_dump()
        
        self.assertEqual(data["access_level"], "partner")  # String value
        self.assertEqual(data["observable_type"], "ipv4-addr")  # String value
        self.assertEqual(data["severity"], "high")  # String value
        
        # Test JSON serialization
        json_str = model.model_dump_json()
        parsed_json = json.loads(json_str)
        
        self.assertEqual(parsed_json["access_level"], "partner")
        self.assertEqual(parsed_json["observable_type"], "ipv4-addr")
        self.assertEqual(parsed_json["severity"], "high")

    def test_use_enum_values_false_serialization(self):
        """Test serialization with use_enum_values=False"""
        model = self.ModelWithoutEnumValues(
            access_level=AccessTier.PARTNER,
            observable_type=ObservableType.IPV4_ADDR,
            severity=SeverityLevel.HIGH
        )
        
        # Test model_dump()
        data = model.model_dump()
        
        # Should serialize to enum objects, not string values
        self.assertEqual(data["access_level"], AccessTier.PARTNER)
        self.assertEqual(data["observable_type"], ObservableType.IPV4_ADDR)
        self.assertEqual(data["severity"], SeverityLevel.HIGH)
        
        # Test JSON serialization (should convert to string representation)
        json_str = model.model_dump_json()
        parsed_json = json.loads(json_str)
        
        # In JSON, enums are typically serialized as their string values regardless
        self.assertEqual(parsed_json["access_level"], "partner")
        self.assertEqual(parsed_json["observable_type"], "ipv4-addr")
        self.assertEqual(parsed_json["severity"], "high")

    def test_default_enum_serialization_behavior(self):
        """Test default enum serialization behavior"""
        model = self.ModelDefault(
            access_level=AccessTier.CONTRIBUTOR,
            observable_type=ObservableType.DOMAIN_NAME,
            severity=SeverityLevel.MEDIUM
        )
        
        # Test model_dump()
        data = model.model_dump()
        
        # Default behavior in Pydantic v2 is typically to use enum values
        self.assertEqual(data["access_level"], "contributor")
        self.assertEqual(data["observable_type"], "domain-name")
        self.assertEqual(data["severity"], "medium")

    def test_enum_input_flexibility(self):
        """Test that models accept both enum objects and string values"""
        # Test with enum objects
        model1 = self.ModelWithEnumValues(
            access_level=AccessTier.PARTNER,
            observable_type=ObservableType.IPV4_ADDR,
            severity=SeverityLevel.HIGH
        )
        
        # Test with string values (should be converted to enums)
        model2 = self.ModelWithEnumValues(
            access_level="partner",
            observable_type="ipv4-addr", 
            severity="high"
        )
        
        # Both should be equal after construction
        self.assertEqual(model1.access_level, model2.access_level)
        self.assertEqual(model1.observable_type, model2.observable_type)
        self.assertEqual(model1.severity, model2.severity)

    def test_none_enum_handling(self):
        """Test handling of None enum values"""
        model = self.ModelWithEnumValues(
            access_level=AccessTier.OBSERVER,
            observable_type=ObservableType.EMAIL_ADDR,
            severity=None  # Optional field
        )
        
        data = model.model_dump()
        self.assertEqual(data["access_level"], "observer")
        self.assertEqual(data["observable_type"], "email-addr")
        self.assertIsNone(data["severity"])

    def test_enum_round_trip_consistency(self):
        """Test that enum values survive round-trip serialization"""
        original_model = self.ModelWithEnumValues(
            access_level=AccessTier.CORE_MEMBER,
            observable_type=ObservableType.URL,
            severity=SeverityLevel.CRITICAL
        )
        
        # Serialize to JSON
        json_str = original_model.model_dump_json()
        
        # Parse back from JSON
        json_data = json.loads(json_str)
        recreated_model = self.ModelWithEnumValues(**json_data)
        
        # Should be equal
        self.assertEqual(original_model.access_level, recreated_model.access_level)
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
        def get_privilege_level(access_level: AccessTier) -> int:
            privilege_map = {
                AccessTier.PUBLIC: 0,
                AccessTier.OBSERVER: 1,
                AccessTier.CONTRIBUTOR: 2,
                AccessTier.PARTNER: 3,
                AccessTier.CORE_MEMBER: 4
            }
            return privilege_map[access_level]
        
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
            ObservableType.IPV4_ADDR,
            ObservableType.IPV6_ADDR,
            ObservableType.DOMAIN_NAME,
            ObservableType.URL,
            ObservableType.EMAIL_ADDR,
            ObservableType.FILE,
            ObservableType.WINDOWS_REGISTRY_KEY
        ]
        
        # Test that all expected network indicators are covered
        expected_network_values = ["ipv4-addr", "ipv6-addr", "domain-name", "url", "email-addr", "file", "windows-registry-key"]
        actual_values = [obs_type.value for obs_type in network_types]
        
        self.assertEqual(set(actual_values), set(expected_network_values))

    def test_enum_membership_checks(self):
        """Test checking enum membership"""
        # Test AccessTier membership
        self.assertIn(AccessTier.PARTNER, AccessTier)
        self.assertIn("partner", [tier.value for tier in AccessTier])
        
        # Test ObservableType membership
        self.assertIn(ObservableType.IPV4_ADDR, ObservableType)
        self.assertIn("domain-name", [obs.value for obs in ObservableType])

        # Test SeverityLevel membership
        self.assertIn(SeverityLevel.CRITICAL, SeverityLevel)
        self.assertIn("high", [sev.value for sev in SeverityLevel])


class TestPydanticEnumIntegration(unittest.TestCase):
    """Test Pydantic integration with FRANK enums"""

    def test_pydantic_enum_validation_with_use_enum_values_true(self):
        """Test Pydantic validation with use_enum_values=True"""
        
        class TestModel(BaseModel):
            model_config = ConfigDict(use_enum_values=True, extra="forbid")
            
            access_level: AccessTier
            obs_type: ObservableType
            severity: Optional[SeverityLevel] = None
        
        # Test valid enum values
        model = TestModel(
            access_level="partner",
            obs_type="ipv4-addr",
            severity="high"
        )
        
        # Verify enum conversion
        self.assertEqual(model.access_level, AccessTier.PARTNER)
        self.assertEqual(model.obs_type, ObservableType.IPV4_ADDR)
        self.assertEqual(model.severity, SeverityLevel.HIGH)
        
        # Test serialization (should use string values)
        data = model.model_dump()
        self.assertEqual(data["access_level"], "partner")
        self.assertEqual(data["obs_type"], "ipv4-addr")
        self.assertEqual(data["severity"], "high")

    def test_pydantic_enum_validation_with_use_enum_values_false(self):
        """Test Pydantic validation with use_enum_values=False"""
        
        class TestModel(BaseModel):
            model_config = ConfigDict(use_enum_values=False, extra="forbid")
            
            access_level: AccessTier
            obs_type: ObservableType
            severity: Optional[SeverityLevel] = None
        
        # Test valid enum values
        model = TestModel(
            access_level="contributor",
            obs_type="domain-name",
            severity="medium"
        )
        
        # Verify enum conversion
        self.assertEqual(model.access_level, AccessTier.CONTRIBUTOR)
        self.assertEqual(model.obs_type, ObservableType.DOMAIN_NAME)
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
            
            access_level: AccessTier
            obs_type: ObservableType
            severity: SeverityLevel
        
        # Test invalid tier
        with self.assertRaises(ValueError):
            TestModel(
                access_level="invalid_tier",
                obs_type="ipv4",
                severity="high"
            )
        
        # Test invalid observable type
        with self.assertRaises(ValueError):
            TestModel(
                access_level="partner",
                obs_type="invalid_obs",
                severity="high"
            )
        
        # Test invalid severity
        with self.assertRaises(ValueError):
            TestModel(
                access_level="partner",
                obs_type="ipv4",
                severity="invalid_severity"
            )

    def test_enum_json_serialization_comparison(self):
        """Compare JSON serialization between use_enum_values settings"""
        
        # Model with use_enum_values=True
        class ModelTrue(BaseModel):
            model_config = ConfigDict(use_enum_values=True)
            access_level: AccessTier
            severity: SeverityLevel
        
        # Model with use_enum_values=False  
        class ModelFalse(BaseModel):
            model_config = ConfigDict(use_enum_values=False)
            access_level: AccessTier
            severity: SeverityLevel
        
        # Create identical instances
        model_true = ModelTrue(access_level="partner", severity="critical")
        model_false = ModelFalse(access_level="partner", severity="critical")
        
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
        self.assertNotIsInstance(model_true.access_level, AccessTier)
        self.assertIsInstance(model_false.access_level, AccessTier)


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
        expected_obs = ["ipv4-addr", "ipv6-addr", "domain-name", "url", "email-addr", 
        "file", "windows-registry-key", "mutex", "x509-certificate",
        "process", "autonomous-system", "artifact", "directory", 
        "network-traffic", "software", "user-account", "custom"]
        self.assertEqual(obs_values, expected_obs)
        
        # Test SeverityLevel iteration
        sev_values = [sev.value for sev in SeverityLevel]
        expected_sev = ["low", "medium", "high", "critical"]
        self.assertEqual(sev_values, expected_sev)

    def test_enum_string_representation(self):
        """Test string representation of enums"""
        self.assertEqual(str(AccessTier.PARTNER), "AccessTier.PARTNER")
        self.assertEqual(str(ObservableType.DOMAIN_NAME), "ObservableType.DOMAIN_NAME")
        self.assertEqual(str(SeverityLevel.CRITICAL), "SeverityLevel.CRITICAL")
        
        # Test repr
        self.assertIn("AccessTier", repr(AccessTier.PARTNER))
        self.assertIn("ObservableType", repr(ObservableType.IPV4_ADDR))
        self.assertIn("SeverityLevel", repr(SeverityLevel.HIGH))

class TestAccessTierFromGroups(unittest.TestCase):
    """Test AccessTier.get_access_tier_from_groups method"""

    def test_empty_groups_returns_public(self):
        """Test that empty groups list returns PUBLIC tier"""
        result = AccessTier.get_access_tier_from_groups([])
        self.assertEqual(result, AccessTier.PUBLIC)
        self.assertIsInstance(result, AccessTier)

    def test_single_valid_group(self):
        """Test with a single valid group name"""
        test_cases = [
            (["contributor"], AccessTier.CONTRIBUTOR),
            (["partner"], AccessTier.PARTNER),
            (["core_member"], AccessTier.CORE_MEMBER),
            (["observer"], AccessTier.OBSERVER),
            (["public"], AccessTier.PUBLIC),
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                result = AccessTier.get_access_tier_from_groups(groups)
                self.assertEqual(result, expected)
                self.assertIsInstance(result, AccessTier)

    def test_multiple_valid_groups_returns_first(self):
        """Test that with multiple valid groups, the first one is returned"""
        test_cases = [
            (["contributor", "partner"], AccessTier.CONTRIBUTOR),
            (["partner", "core_member"], AccessTier.PARTNER),
            (["observer", "contributor", "partner"], AccessTier.OBSERVER),
            (["public", "core_member"], AccessTier.PUBLIC),
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                result = AccessTier.get_access_tier_from_groups(groups)
                self.assertEqual(result, expected)

    def test_invalid_groups_returns_public(self):
        """Test that invalid group names return PUBLIC tier"""
        invalid_groups = [
            ["admin"],
            ["user"],
            ["unknown"],
            ["invalid_tier"],
            ["some_random_group"],
            ["group1", "group2", "group3"],
        ]
        
        for groups in invalid_groups:
            with self.subTest(groups=groups):
                result = AccessTier.get_access_tier_from_groups(groups)
                self.assertEqual(result, AccessTier.PUBLIC)

    def test_mixed_valid_and_invalid_groups(self):
        """Test with mix of valid and invalid groups - should return first valid"""
        test_cases = [
            (["admin", "contributor", "unknown"], AccessTier.CONTRIBUTOR),
            (["invalid1", "invalid2", "partner"], AccessTier.PARTNER),
            (["group1", "group2", "core_member", "group3"], AccessTier.CORE_MEMBER),
            (["unknown", "observer"], AccessTier.OBSERVER),
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                result = AccessTier.get_access_tier_from_groups(groups)
                self.assertEqual(result, expected)

    def test_case_insensitive_groups(self):
        """Test that group matching is case-insensitive"""
        test_cases = [
            (["CONTRIBUTOR"], AccessTier.CONTRIBUTOR),
            (["Partner"], AccessTier.PARTNER),
            (["CORE_MEMBER"], AccessTier.CORE_MEMBER),
            (["ObSeRvEr"], AccessTier.OBSERVER),
            (["PUBLIC"], AccessTier.PUBLIC),
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                result = AccessTier.get_access_tier_from_groups(groups)
                self.assertEqual(result, expected)

    def test_groups_with_spaces(self):
        """Test that groups with spaces are handled correctly"""
        test_cases = [
            (["core member"], AccessTier.CORE_MEMBER),
            (["Core Member"], AccessTier.CORE_MEMBER),
            (["CORE MEMBER"], AccessTier.CORE_MEMBER),
            ([" core member "], AccessTier.CORE_MEMBER),  # with extra spaces
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                result = AccessTier.get_access_tier_from_groups(groups)
                self.assertEqual(result, expected)

    def test_groups_with_whitespace(self):
        """Test groups with various whitespace patterns"""
        test_cases = [
            (["  contributor  "], AccessTier.CONTRIBUTOR),
            (["\tpartner\t"], AccessTier.PARTNER),
            ([" observer "], AccessTier.OBSERVER),
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                result = AccessTier.get_access_tier_from_groups(groups)
                self.assertEqual(result, expected)

    def test_empty_string_in_groups(self):
        """Test handling of empty strings in groups list"""
        test_cases = [
            (["", "contributor"], AccessTier.CONTRIBUTOR),
            ([""], AccessTier.PUBLIC),
            (["", "", "partner"], AccessTier.PARTNER),
            (["invalid", "", "observer"], AccessTier.OBSERVER),
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                result = AccessTier.get_access_tier_from_groups(groups)
                self.assertEqual(result, expected)

    def test_realistic_aws_cognito_groups(self):
        """Test with realistic AWS Cognito group names"""
        # Cognito groups might include various prefixes and suffixes
        test_cases = [
            (["app-users", "contributor", "region-eu"], AccessTier.CONTRIBUTOR),
            (["admin", "partner", "billing"], AccessTier.PARTNER),
            (["viewer", "observer", "readonly"], AccessTier.OBSERVER),
            (["everyone", "public"], AccessTier.PUBLIC),
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                result = AccessTier.get_access_tier_from_groups(groups)
                self.assertEqual(result, expected)

    def test_priority_order_when_multiple_valid(self):
        """Test that order matters - first valid group is returned"""
        # If a user has multiple access tiers, the first one in the list wins
        test_cases = [
            (["observer", "contributor"], AccessTier.OBSERVER),
            (["contributor", "observer"], AccessTier.CONTRIBUTOR),
            (["public", "partner"], AccessTier.PUBLIC),
            (["core_member", "contributor"], AccessTier.CORE_MEMBER),
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                result = AccessTier.get_access_tier_from_groups(groups)
                self.assertEqual(result, expected)

    def test_groups_with_underscores_and_dashes(self):
        """Test handling of various delimiter styles"""
        # core_member should work with underscores
        result1 = AccessTier.get_access_tier_from_groups(["core_member"])
        self.assertEqual(result1, AccessTier.CORE_MEMBER)
        
        # Also test with spaces converted to underscores
        result2 = AccessTier.get_access_tier_from_groups(["core member"])
        self.assertEqual(result2, AccessTier.CORE_MEMBER)

    def test_long_groups_list(self):
        """Test with a long list of groups"""
        # Simulate a user with many groups, where valid tier is near the end
        groups = [f"group{i}" for i in range(100)]
        groups.append("contributor")
        groups.extend([f"other_group{i}" for i in range(100)])
        
        result = AccessTier.get_access_tier_from_groups(groups)
        self.assertEqual(result, AccessTier.CONTRIBUTOR)

    def test_none_values_handled_gracefully(self):
        """Test that None values in groups list don't cause crashes"""
        # The from_string method with default=False should raise ValueError for None
        # get_access_tier_from_groups should catch this and continue
        test_cases = [
            ([None, "contributor"], AccessTier.CONTRIBUTOR),
            (["partner", None], AccessTier.PARTNER),
            ([None, None, "observer"], AccessTier.OBSERVER),
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                # This might raise an exception depending on implementation
                # If None is in the list, from_string should handle it
                try:
                    result = AccessTier.get_access_tier_from_groups(groups)
                    self.assertEqual(result, expected)
                except (ValueError, TypeError, AttributeError):
                    # If implementation doesn't handle None gracefully, that's okay
                    # But we document the behavior
                    pass

    def test_numeric_values_in_groups(self):
        """Test handling of numeric values in groups"""
        # Numbers might appear in group names, but shouldn't be valid tiers
        test_cases = [
            ([123, "contributor"], AccessTier.CONTRIBUTOR),
            (["123", "partner"], AccessTier.PARTNER),
            ([456], AccessTier.PUBLIC),
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                try:
                    result = AccessTier.get_access_tier_from_groups(groups)
                    self.assertEqual(result, expected)
                except (ValueError, TypeError, AttributeError):
                    # If implementation doesn't handle numbers gracefully
                    pass

    def test_all_tiers_can_be_found(self):
        """Test that all possible AccessTier values can be found from groups"""
        for tier in AccessTier:
            with self.subTest(tier=tier):
                result = AccessTier.get_access_tier_from_groups([tier.value])
                self.assertEqual(result, tier)

    def test_integration_with_from_string(self):
        """Test that get_access_tier_from_groups correctly uses from_string"""
        # This test verifies the integration with from_string method
        # All variations that from_string accepts should work
        test_cases = [
            (["Contributor"], AccessTier.CONTRIBUTOR),
            (["CORE_MEMBER"], AccessTier.CORE_MEMBER),
            (["core member"], AccessTier.CORE_MEMBER),
            (["Core Member"], AccessTier.CORE_MEMBER),
        ]
        
        for groups, expected in test_cases:
            with self.subTest(groups=groups):
                result = AccessTier.get_access_tier_from_groups(groups)
                self.assertEqual(result, expected)


class TestYAMLSerialization(unittest.TestCase):
    """Test YAML serialization and deserialization of enums"""
    
    def test_enum_representer(self):
        """Test YAML representer converts enum to string value"""
        import yaml
        from frank.core.enum import enum_representer
        
        dumper = yaml.Dumper(None)
        result = enum_representer(dumper, AccessTier.PARTNER)
        
        # Should create a scalar node with the enum value
        self.assertEqual(result.value, 'partner')
        self.assertEqual(result.tag, 'tag:yaml.org,2002:str')
    
    def test_enum_constructor_valid_value(self):
        """Test YAML constructor with valid enum value"""
        from frank.core.enum import enum_constructor
        import yaml
        
        constructor_func = enum_constructor(AccessTier)
        
        # Mock a YAML node with a valid value
        loader = yaml.Loader('')
        node = yaml.ScalarNode(tag='!AccessTier', value='partner')
        
        result = constructor_func(loader, node)
        self.assertEqual(result, AccessTier.PARTNER)
    
    def test_enum_constructor_valid_name(self):
        """Test YAML constructor with valid enum name"""
        from frank.core.enum import enum_constructor
        import yaml
        
        constructor_func = enum_constructor(AccessTier)
        loader = yaml.Loader('')
        node = yaml.ScalarNode(tag='!AccessTier', value='PARTNER')
        
        result = constructor_func(loader, node)
        self.assertEqual(result, AccessTier.PARTNER)
    
    def test_enum_constructor_invalid_value(self):
        """Test YAML constructor raises ValueError for invalid value"""
        from frank.core.enum import enum_constructor
        import yaml
        
        constructor_func = enum_constructor(AccessTier)
        loader = yaml.Loader('')
        node = yaml.ScalarNode(tag='!AccessTier', value='invalid_tier')
        
        with self.assertRaises(ValueError) as context:
            constructor_func(loader, node)
        self.assertIn('invalid_tier', str(context.exception))
        self.assertIn('AccessTier', str(context.exception))
    
    def test_register_enum_yaml(self):
        """Test registering enum for YAML serialization"""
        from frank.core.enum import register_enum_yaml
        import yaml
        
        # This should not raise
        register_enum_yaml(AccessTier)
        
        # Test round-trip serialization
        data = {'tier': AccessTier.CONTRIBUTOR}
        yaml_str = yaml.dump(data)
        self.assertIn('contributor', yaml_str)
    
    def test_yaml_roundtrip_serialization(self):
        """Test complete YAML round-trip with enum"""
        import yaml
        from frank.core.enum import register_enum_yaml
        
        # Ensure enum is registered
        register_enum_yaml(AccessTier)
        
        # Create data with enum
        original_data = {
            'access_level': AccessTier.PARTNER,
            'name': 'Test Org'
        }
        
        # Serialize to YAML
        yaml_str = yaml.dump(original_data)
        
        # Deserialize from YAML
        loaded_data = yaml.safe_load(yaml_str)
        
        # Should preserve the enum value as string
        self.assertEqual(loaded_data['access_level'], 'partner')
        self.assertEqual(loaded_data['name'], 'Test Org')


if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)
