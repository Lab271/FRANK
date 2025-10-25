#!/usr/bin/env python3
"""
FRANK Platform - Unit Tests for Filtering Module

Unit tests for submission filtering, observable filtering, and access-level based data masking.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
from unittest.mock import Mock
from datetime import datetime, timezone

from frank.util.filter import FRANKFilter
from frank.core.enum import AccessTier


class TestFRANKFilterInitialization(unittest.TestCase):
    """Test FRANKFilter initialization and configuration."""
    
    def test_initialization_without_logger(self):
        """FRANKFilter initializes without logger (uses NullLogger)."""
        frank_filter = FRANKFilter()
        self.assertIsNotNone(frank_filter.logger)
    
    def test_initialization_with_logger(self):
        """FRANKFilter initializes with provided logger."""
        mock_logger = Mock()
        frank_filter = FRANKFilter(logger=mock_logger)
        self.assertEqual(frank_filter.logger, mock_logger)


class TestDeepCopy(unittest.TestCase):
    """Test _deep_copy helper method."""
    
    def setUp(self):
        """Set up test fixture."""
        self.frank_filter = FRANKFilter()
    
    def test_deep_copy_dict(self):
        """Deep copy should create independent copy of dict."""
        original = {"key1": "value1", "key2": "value2"}
        copied = self.frank_filter._deep_copy(original)
        
        self.assertEqual(original, copied)
        self.assertIsNot(original, copied)
        
        # Modify copy - should not affect original
        copied["key3"] = "value3"
        self.assertNotIn("key3", original)
    
    def test_deep_copy_list(self):
        """Deep copy should create independent copy of list."""
        original = [1, 2, 3, 4]
        copied = self.frank_filter._deep_copy(original)
        
        self.assertEqual(original, copied)
        self.assertIsNot(original, copied)
        
        # Modify copy - should not affect original
        copied.append(5)
        self.assertEqual(len(original), 4)
        self.assertEqual(len(copied), 5)
    
    def test_deep_copy_nested_structure(self):
        """Deep copy should handle nested dict and list structures."""
        original = {
            "level1": {
                "level2": [1, 2, {"level3": "value"}]
            }
        }
        copied = self.frank_filter._deep_copy(original)
        
        self.assertEqual(original, copied)
        self.assertIsNot(original, copied)
        self.assertIsNot(original["level1"], copied["level1"])
        self.assertIsNot(original["level1"]["level2"], copied["level1"]["level2"])
        
        # Modify deep nested value
        copied["level1"]["level2"][2]["level3"] = "modified"
        self.assertEqual(original["level1"]["level2"][2]["level3"], "value")
    
    def test_deep_copy_primitive(self):
        """Deep copy should return primitives as-is."""
        self.assertEqual(self.frank_filter._deep_copy(42), 42)
        self.assertEqual(self.frank_filter._deep_copy("string"), "string")
        self.assertEqual(self.frank_filter._deep_copy(True), True)
        self.assertIsNone(self.frank_filter._deep_copy(None))


class TestSubmissionByAccessLevel(unittest.TestCase):
    """Test submission_by_access_level method."""
    
    def setUp(self):
        """Set up test fixture."""
        self.frank_filter = FRANKFilter()
        self.full_submission = {
            "submission_id": "sub-12345",
            "timestamp": "2025-10-25T12:00:00Z",
            "tlp_level": "amber",
            "sighting": {
                "timestamp": "2025-10-25T11:30:00Z",
                "observation_count": 10,
                "observables": {
                    "network": [
                        {"type": "ipv4", "value": "192.168.1.100"},
                        {"type": "domain", "value": "malicious.example.com"}
                    ],
                    "file": [
                        {"type": "sha256", "value": "a" * 64}
                    ]
                }
            },
            "hit_target": {
                "organisation_id": "org-67890",
                "sector": "finance"
            }
        }
    
    def test_public_access_returns_basic_stats_only(self):
        """PUBLIC access should return only basic statistics."""
        result = self.frank_filter.submission_by_access_level(
            self.full_submission, AccessTier.PUBLIC
        )
        
        self.assertIn("submission", result)
        submission = result["submission"]
        
        # Should have basic fields
        self.assertEqual(submission["submission_id"], "sub-12345")
        self.assertEqual(submission["timestamp"], "2025-10-25T12:00:00Z")
        
        # Should have sighting with limited info
        self.assertIn("sighting", submission)
        self.assertEqual(submission["sighting"]["timestamp"], "2025-10-25T11:30:00Z")
        self.assertEqual(submission["sighting"]["observation_count"], 10)
        
        # Should NOT have full observables, hit_target, or tlp_level
        self.assertNotIn("observables", submission["sighting"])
        self.assertNotIn("hit_target", submission)
        self.assertNotIn("tlp_level", submission)
    
    def test_observer_access_masks_observable_values(self):
        """OBSERVER access should mask observable values."""
        result = self.frank_filter.submission_by_access_level(
            self.full_submission, AccessTier.OBSERVER
        )
        
        submission = result["submission"]
        observables = submission["sighting"]["observables"]
        
        # Check network observables are masked
        ipv4_obs = observables["network"][0]
        self.assertEqual(ipv4_obs["value"], "192.168.1....")
        
        domain_obs = observables["network"][1]
        self.assertEqual(domain_obs["value"], "malicious....")
        
        # Check file observable is masked
        sha256_obs = observables["file"][0]
        self.assertEqual(sha256_obs["value"], "aaaaaaaaaa...")
    
    def test_observer_access_removes_sensitive_fields(self):
        """OBSERVER access should remove hit_target and tlp_level."""
        result = self.frank_filter.submission_by_access_level(
            self.full_submission, AccessTier.OBSERVER
        )
        
        submission = result["submission"]
        
        # Should NOT have sensitive fields
        self.assertNotIn("hit_target", submission)
        self.assertNotIn("tlp_level", submission)
    
    def test_observer_access_with_short_values(self):
        """OBSERVER access should handle short observable values correctly."""
        short_submission = {
            "submission_id": "sub-123",
            "timestamp": "2025-10-25T12:00:00Z",
            "sighting": {
                "timestamp": "2025-10-25T11:30:00Z",
                "observation_count": 5,
                "observables": {
                    "network": [
                        {"type": "ipv4", "value": "short"}
                    ]
                }
            }
        }
        
        result = self.frank_filter.submission_by_access_level(
            short_submission, AccessTier.OBSERVER
        )
        
        submission = result["submission"]
        ipv4_obs = submission["sighting"]["observables"]["network"][0]
        # Short values (<=10 chars) should not be truncated
        self.assertEqual(ipv4_obs["value"], "short")
    
    def test_contributor_access_removes_organisation_id(self):
        """CONTRIBUTOR access should remove organisation_id from hit_target."""
        result = self.frank_filter.submission_by_access_level(
            self.full_submission, AccessTier.CONTRIBUTOR
        )
        
        submission = result["submission"]
        
        # Should have hit_target but without organisation_id
        self.assertIn("hit_target", submission)
        self.assertNotIn("organisation_id", submission["hit_target"])
        self.assertEqual(submission["hit_target"]["sector"], "finance")
    
    def test_contributor_access_preserves_sector(self):
        """CONTRIBUTOR access should preserve sector field."""
        result = self.frank_filter.submission_by_access_level(
            self.full_submission, AccessTier.CONTRIBUTOR
        )
        
        submission = result["submission"]
        self.assertEqual(submission["hit_target"]["sector"], "finance")
    
    def test_contributor_access_without_hit_target(self):
        """CONTRIBUTOR access should handle missing hit_target gracefully."""
        submission_no_target = {
            "submission_id": "sub-12345",
            "timestamp": "2025-10-25T12:00:00Z",
            "sighting": {
                "timestamp": "2025-10-25T11:30:00Z",
                "observation_count": 10
            }
        }
        
        result = self.frank_filter.submission_by_access_level(
            submission_no_target, AccessTier.CONTRIBUTOR
        )
        
        # Should not error
        self.assertIn("submission", result)
    
    def test_partner_access_returns_full_data(self):
        """PARTNER access should return full submission data."""
        result = self.frank_filter.submission_by_access_level(
            self.full_submission, AccessTier.PARTNER
        )
        
        submission = result["submission"]
        
        # Should have all fields
        self.assertEqual(submission["submission_id"], "sub-12345")
        self.assertEqual(submission["tlp_level"], "amber")
        self.assertIn("hit_target", submission)
        self.assertEqual(submission["hit_target"]["organisation_id"], "org-67890")
        self.assertEqual(submission["hit_target"]["sector"], "finance")
        
        # Observables should not be masked
        ipv4_obs = submission["sighting"]["observables"]["network"][0]
        self.assertEqual(ipv4_obs["value"], "192.168.1.100")
    
    def test_core_member_access_returns_full_data(self):
        """CORE_MEMBER access should return full submission data."""
        result = self.frank_filter.submission_by_access_level(
            self.full_submission, AccessTier.CORE_MEMBER
        )
        
        submission = result["submission"]
        
        # Should have all fields including sensitive ones
        self.assertEqual(submission["submission_id"], "sub-12345")
        self.assertEqual(submission["tlp_level"], "amber")
        self.assertIn("hit_target", submission)
        self.assertEqual(submission["hit_target"]["organisation_id"], "org-67890")


class TestFilterObservableByAccessLevel(unittest.TestCase):
    """Test filter_observable_by_access_level method."""
    
    def setUp(self):
        """Set up test fixture."""
        self.frank_filter = FRANKFilter()
        self.full_observable = {
            "observable_type": "ipv4",
            "observable_value": "192.168.1.100",
            "total_sightings": 42,
            "last_seen": "2025-10-25T12:00:00Z",
            "first_seen": "2025-10-20T08:00:00Z",
            "unique_organisations": 5
        }
    
    def test_public_access_returns_basic_stats(self):
        """PUBLIC access should return only basic statistics."""
        result = self.frank_filter.filter_observable_by_access_level(
            self.full_observable, AccessTier.PUBLIC
        )
        
        # Should have only specific fields
        self.assertEqual(result["observable_type"], "ipv4")
        self.assertEqual(result["total_sightings"], 42)
        self.assertEqual(result["last_seen"], "2025-10-25T12:00:00Z")
        
        # Should NOT have detailed fields
        self.assertNotIn("observable_value", result)
        self.assertNotIn("first_seen", result)
        self.assertNotIn("unique_organisations", result)
    
    def test_observer_access_masks_value(self):
        """OBSERVER access should mask observable_value."""
        result = self.frank_filter.filter_observable_by_access_level(
            self.full_observable, AccessTier.OBSERVER
        )
        
        # Should have all fields
        self.assertEqual(result["observable_type"], "ipv4")
        self.assertEqual(result["total_sightings"], 42)
        
        # observable_value should be masked
        self.assertEqual(result["observable_value"], "192.168.1....")
        self.assertNotEqual(result["observable_value"], "192.168.1.100")
    
    def test_observer_access_with_short_value(self):
        """OBSERVER access should handle short values correctly."""
        short_observable = {
            "observable_type": "port",
            "observable_value": "443",
            "total_sightings": 10,
            "last_seen": "2025-10-25T12:00:00Z"
        }
        
        result = self.frank_filter.filter_observable_by_access_level(
            short_observable, AccessTier.OBSERVER
        )
        
        # Short values should not be truncated
        self.assertEqual(result["observable_value"], "443")
    
    def test_contributor_access_returns_full_data(self):
        """CONTRIBUTOR access should return full observable data."""
        result = self.frank_filter.filter_observable_by_access_level(
            self.full_observable, AccessTier.CONTRIBUTOR
        )
        
        # Should be identical to input
        self.assertEqual(result, self.full_observable)
        self.assertEqual(result["observable_value"], "192.168.1.100")
    
    def test_partner_access_returns_full_data(self):
        """PARTNER access should return full observable data."""
        result = self.frank_filter.filter_observable_by_access_level(
            self.full_observable, AccessTier.PARTNER
        )
        
        self.assertEqual(result, self.full_observable)
    
    def test_core_member_access_returns_full_data(self):
        """CORE_MEMBER access should return full observable data."""
        result = self.frank_filter.filter_observable_by_access_level(
            self.full_observable, AccessTier.CORE_MEMBER
        )
        
        self.assertEqual(result, self.full_observable)


class TestMaskObservableValue(unittest.TestCase):
    """Test _mask_observable_value helper method."""
    
    def setUp(self):
        """Set up test fixture."""
        self.frank_filter = FRANKFilter()
    
    def test_mask_ipv4_address(self):
        """IPv4 addresses should be masked properly."""
        masked = self.frank_filter._mask_observable_value("192.168.1.100", "ipv4")
        self.assertEqual(masked, "192.168.1.***")
    
    def test_mask_ipv4_with_invalid_format(self):
        """Invalid IPv4 format should fall back to generic masking."""
        # Not enough octets
        masked = self.frank_filter._mask_observable_value("192.168.1", "ipv4")
        self.assertEqual(masked, "192.168.1")  # Too short, no masking
        
        # No dots (not IP format) - Falls back to generic masking (>10 chars)
        masked = self.frank_filter._mask_observable_value("notanipaddress", "ipv4")
        self.assertEqual(masked, "notanipadd...")  # > 10 chars, gets truncated
    
    def test_mask_domain_name(self):
        """Domain names should be masked with asterisks."""
        masked = self.frank_filter._mask_observable_value("example.com", "domain")
        # Half of "example.com" (11 chars) = 5 chars masked, showing chars from index 5
        self.assertEqual(masked, "*****le.com")
    
    def test_mask_short_domain(self):
        """Short domain names should be masked correctly."""
        masked = self.frank_filter._mask_observable_value("ex.com", "domain")
        # Half of "ex.com" (6 chars) = 3 chars masked
        self.assertEqual(masked, "***com")
    
    def test_mask_long_generic_value(self):
        """Long generic values should be truncated."""
        long_value = "a" * 64
        masked = self.frank_filter._mask_observable_value(long_value, "sha256")
        self.assertEqual(masked, "aaaaaaaaaa...")
        self.assertEqual(len(masked), 13)  # 10 chars + "..."
    
    def test_mask_short_generic_value(self):
        """Short generic values should not be masked."""
        short_value = "short"
        masked = self.frank_filter._mask_observable_value(short_value, "unknown")
        self.assertEqual(masked, "short")


class TestFormatSightingResponse(unittest.TestCase):
    """Test format_sighting_response method."""
    
    def setUp(self):
        """Set up test fixture."""
        self.frank_filter = FRANKFilter()
        self.full_result = {
            "observable_hash": "abc123def456",
            "observable_type": "ipv4",
            "observable_value": "192.168.1.100",
            "last_seen": "2025-10-25T12:00:00Z",
            "first_seen": "2025-10-20T08:00:00Z",
            "total_sightings": 42,
            "unique_organisations": 5,
            "sectors": ["finance", "healthcare"],
            "regions": ["EU", "NA"]
        }
    
    def test_observer_format_minimal_data(self):
        """OBSERVER access should return minimal masked data."""
        result = self.frank_filter.format_sighting_response(
            self.full_result, AccessTier.OBSERVER, "json"
        )
        
        # Check sighting_id format
        self.assertTrue(result["sighting_id"].startswith("sighting-masked-"))
        self.assertIn("abc123de", result["sighting_id"])
        
        # Check masked value
        self.assertEqual(result["observable_value"], "192.168.1.***")
        
        # Check other fields
        self.assertEqual(result["observable_type"], "ipv4")
        self.assertEqual(result["geographic_region"], "masked")
        
        # Should NOT have detailed fields
        self.assertNotIn("total_sightings", result)
        self.assertNotIn("sectors", result)
    
    def test_observer_format_with_missing_hash(self):
        """OBSERVER format should handle missing observable_hash."""
        result_no_hash = self.full_result.copy()
        result_no_hash.pop("observable_hash")
        
        result = self.frank_filter.format_sighting_response(
            result_no_hash, AccessTier.OBSERVER, "json"
        )
        
        self.assertTrue(result["sighting_id"].startswith("sighting-masked-unknown"))
    
    def test_observer_format_uses_current_time_if_no_last_seen(self):
        """OBSERVER format should use current time if last_seen missing."""
        result_no_time = self.full_result.copy()
        result_no_time.pop("last_seen")
        
        result = self.frank_filter.format_sighting_response(
            result_no_time, AccessTier.OBSERVER, "json"
        )
        
        # Should have a timestamp (current time)
        self.assertIn("timestamp", result)
        self.assertIsNotNone(result["timestamp"])
    
    def test_contributor_format_partial_data(self):
        """CONTRIBUTOR access should return partial data."""
        result = self.frank_filter.format_sighting_response(
            self.full_result, AccessTier.CONTRIBUTOR, "json"
        )
        
        # Check sighting_id format (12 chars of hash)
        self.assertTrue(result["sighting_id"].startswith("sighting-abc123def456"))
        
        # Check observable is an object
        self.assertIn("observable", result)
        self.assertEqual(result["observable"]["type"], "ipv4")
        self.assertEqual(result["observable"]["value"], "192.168.1.100")
        
        # Check included fields
        self.assertEqual(result["total_sightings"], 42)
        self.assertEqual(result["sectors"], ["finance", "healthcare"])
        
        # Should NOT have all detailed fields
        self.assertNotIn("unique_organisations", result)
        self.assertNotIn("first_seen", result)
        self.assertNotIn("regions", result)
    
    def test_partner_format_full_data(self):
        """PARTNER access should return full data."""
        result = self.frank_filter.format_sighting_response(
            self.full_result, AccessTier.PARTNER, "json"
        )
        
        # Check sighting_id format (full hash)
        self.assertEqual(result["sighting_id"], "sighting-abc123def456")
        
        # Check all fields present
        self.assertEqual(result["observable"]["value"], "192.168.1.100")
        self.assertEqual(result["total_sightings"], 42)
        self.assertEqual(result["unique_organisations"], 5)
        self.assertEqual(result["first_seen"], "2025-10-20T08:00:00Z")
        self.assertEqual(result["sectors"], ["finance", "healthcare"])
        self.assertEqual(result["regions"], ["EU", "NA"])
    
    def test_core_member_format_full_data(self):
        """CORE_MEMBER access should return full data."""
        result = self.frank_filter.format_sighting_response(
            self.full_result, AccessTier.CORE_MEMBER, "json"
        )
        
        # Should have all fields like PARTNER
        self.assertEqual(result["sighting_id"], "sighting-abc123def456")
        self.assertEqual(result["unique_organisations"], 5)
        self.assertEqual(result["regions"], ["EU", "NA"])


class TestFilterWithLogger(unittest.TestCase):
    """Test FRANKFilter logging functionality."""
    
    def test_submission_filtering_logs_info(self):
        """submission_by_access_level should log filtering action."""
        mock_logger = Mock()
        frank_filter = FRANKFilter(logger=mock_logger)
        
        submission = {
            "submission_id": "test-123",
            "timestamp": "2025-10-25T12:00:00Z",
            "sighting": {
                "timestamp": "2025-10-25T11:30:00Z",
                "observation_count": 5
            }
        }
        
        frank_filter.submission_by_access_level(submission, AccessTier.PUBLIC)
        
        # Verify logger was called
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args[0][0]
        self.assertIn("access level", call_args.lower())


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def setUp(self):
        """Set up test fixture."""
        self.frank_filter = FRANKFilter()
    
    def test_submission_with_empty_observables(self):
        """Filter should handle empty observables list."""
        submission = {
            "submission_id": "test-123",
            "timestamp": "2025-10-25T12:00:00Z",
            "sighting": {
                "timestamp": "2025-10-25T11:30:00Z",
                "observation_count": 0,
                "observables": {}
            }
        }
        
        result = self.frank_filter.submission_by_access_level(
            submission, AccessTier.OBSERVER
        )
        
        # Should not error
        self.assertIn("submission", result)
    
    def test_submission_with_non_list_observables(self):
        """Filter should handle non-list observable values gracefully."""
        submission = {
            "submission_id": "test-123",
            "timestamp": "2025-10-25T12:00:00Z",
            "sighting": {
                "timestamp": "2025-10-25T11:30:00Z",
                "observation_count": 1,
                "observables": {
                    "network": "not-a-list"  # Invalid structure
                }
            }
        }
        
        result = self.frank_filter.submission_by_access_level(
            submission, AccessTier.OBSERVER
        )
        
        # Should not error and should preserve invalid structure
        self.assertIn("submission", result)
    
    def test_observable_without_value_field(self):
        """Filter should handle observables without value field."""
        submission = {
            "submission_id": "test-123",
            "timestamp": "2025-10-25T12:00:00Z",
            "sighting": {
                "timestamp": "2025-10-25T11:30:00Z",
                "observation_count": 1,
                "observables": {
                    "network": [
                        {"type": "ipv4"}  # Missing value field
                    ]
                }
            }
        }
        
        result = self.frank_filter.submission_by_access_level(
            submission, AccessTier.OBSERVER
        )
        
        # Should not error
        self.assertIn("submission", result)
    
    def test_format_sighting_with_empty_sectors_list(self):
        """Format sighting should handle empty sectors list."""
        result_data = {
            "observable_hash": "abc123",
            "observable_type": "ipv4",
            "observable_value": "192.168.1.100",
            "last_seen": "2025-10-25T12:00:00Z",
            "avg_confidence": 85,
            "total_sightings": 10,
            "sectors": []  # Empty list
        }
        
        result = self.frank_filter.format_sighting_response(
            result_data, AccessTier.CONTRIBUTOR, "json"
        )
        
        self.assertEqual(result["sectors"], [])


if __name__ == "__main__":
    """Run all unit tests for filter module."""
    unittest.main()
