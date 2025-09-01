#!/usr/bin/env python3
"""
Unit tests for FRANK Sighting model
Tests the "be forgiving on what you receive, strong on what you return" principle
"""

import unittest
from unittest.mock import patch, MagicMock
import uuid
from datetime import datetime, timezone, timedelta
import json

# Import the models (adjust import path as needed)
from frank.core.models import Sighting, SeverityLevel, Observables
from pydantic import ValidationError


class TestSighting(unittest.TestCase):
    """Comprehensive unit tests for the Sighting model"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.base_timestamp = datetime(2024, 1, 15, 14, 30, 0)
        self.valid_sighting_data = {
            "confidence": 85,
            "severity": SeverityLevel.HIGH,
            "observation_count": 3
        }
        self.valid_network_observables = [
            NetworkObservable.create_ipv4("192.168.1.100", role="c2"),
            NetworkObservable.create_domain("malicious.example.com", role="phishing")
        ]

    def test_create_minimal_sighting(self):
        """Test creating a sighting with minimal required fields"""
        sighting = Sighting(observables=Observables(network=self.valid_network_observables))
        
        # Check that default values are set
        self.assertEqual(sighting.confidence, 69)  # Default confidence
        self.assertEqual(sighting.observation_count, 1)  # Default count
        
        # Check that auto-generated fields are populated
        self.assertIsNotNone(sighting.sighting_id)
        self.assertTrue(sighting.sighting_id.startswith("sighting--"))
        self.assertIsInstance(uuid.UUID(sighting.sighting_id.split("--")[1]), uuid.UUID)
        
        self.assertIsNotNone(sighting.timestamp)
        self.assertIsInstance(sighting.timestamp, datetime)
        
        # Optional fields should be None
        self.assertIsNone(sighting.first_observed)
        self.assertIsNone(sighting.last_observed)
        self.assertIsNone(sighting.severity)

    def test_create_sighting_with_all_fields(self):
        """Test creating a sighting with all fields provided"""
        sighting_id = f"sighting--{uuid.uuid4()}"
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        first_observed = datetime(2024, 1, 15, 9, 0, 0)
        last_observed = datetime(2024, 1, 15, 11, 0, 0)
        
        sighting = Sighting(
            sighting_id=sighting_id,
            timestamp=timestamp,
            confidence=95,
            first_observed=first_observed,
            last_observed=last_observed,
            observation_count=5,
            severity=SeverityLevel.CRITICAL
        )
        
        self.assertEqual(sighting.sighting_id, sighting_id)
        self.assertEqual(sighting.timestamp, timestamp)
        self.assertEqual(sighting.confidence, 95)
        self.assertEqual(sighting.first_observed, first_observed)
        self.assertEqual(sighting.last_observed, last_observed)
        self.assertEqual(sighting.observation_count, 5)
        self.assertEqual(sighting.severity, SeverityLevel.CRITICAL)

    def test_sighting_id_auto_generation(self):
        """Test that sighting_id is auto-generated when not provided"""
        # Test with None
        sighting1 = Sighting(sighting_id=None)
        self.assertIsNotNone(sighting1.sighting_id)
        self.assertTrue(sighting1.sighting_id.startswith("sighting--"))
        
        # Test with empty string
        sighting2 = Sighting(sighting_id="")
        self.assertIsNotNone(sighting2.sighting_id)
        self.assertTrue(sighting2.sighting_id.startswith("sighting--"))
        
        # Test different IDs are generated
        self.assertNotEqual(sighting1.sighting_id, sighting2.sighting_id)

    @patch('frank.core.models.datetime')
    def test_timestamp_auto_generation_with_mock(self, mock_datetime_module):
        """Test that timestamp is auto-generated when not provided (with proper mocking)"""
        # Mock the current time
        mock_now = datetime(2024, 2, 1, 12, 0, 0)
        
        # Create a mock datetime class that behaves like the real one
        mock_datetime_class = MagicMock()
        mock_datetime_class.utcnow.return_value = mock_now
        
        # Make the datetime constructor work normally
        def datetime_constructor(*args, **kwargs):
            return datetime(*args, **kwargs)
        mock_datetime_class.side_effect = datetime_constructor
        
        # Replace the datetime class in the module
        mock_datetime_module.utcnow = mock_datetime_class.utcnow
        
        # Test with None
        sighting1 = Sighting(timestamp=None)
        self.assertEqual(sighting1.timestamp, mock_now)
        
        # Test with empty string  
        sighting2 = Sighting(timestamp="")
        self.assertEqual(sighting2.timestamp, mock_now)

    def test_timestamp_auto_generation_simple(self):
        """Test timestamp auto-generation without mocking (simpler approach)"""
        # Capture time before and after to verify it's recent
        before = datetime.utcnow()
        
        sighting1 = Sighting(timestamp=None)
        sighting2 = Sighting(timestamp="")
        
        after = datetime.utcnow()
        
        # Verify timestamps are recent (between before and after)
        self.assertGreaterEqual(sighting1.timestamp, before)
        self.assertLessEqual(sighting1.timestamp, after)
        
        self.assertGreaterEqual(sighting2.timestamp, before) 
        self.assertLessEqual(sighting2.timestamp, after)

    def test_timestamp_string_parsing(self):
        """Test parsing timestamp from string formats - 'be forgiving'"""
        test_cases = [
            # ISO format
            ("2024-01-15T14:30:00Z", datetime(2024, 1, 15, 14, 30, 0)),
            ("2024-01-15T14:30:00+00:00", datetime(2024, 1, 15, 14, 30, 0)),
            ("2024-01-15T14:30:00", datetime(2024, 1, 15, 14, 30, 0)),
        ]
        
        for timestamp_str, expected_dt in test_cases:
            with self.subTest(timestamp_str=timestamp_str):
                sighting = Sighting(timestamp=timestamp_str)
                # For timezone-aware comparisons, normalize to UTC
                actual_dt = sighting.timestamp
                if actual_dt.tzinfo:
                    actual_dt = actual_dt.replace(tzinfo=None)
                self.assertEqual(actual_dt, expected_dt)

    def test_timestamp_invalid_string_fallback(self):
        """Test that invalid timestamp strings fall back to current time"""
        # Instead of mocking, test that we get a reasonable timestamp (recent)
        before_test = datetime.utcnow()
        
        invalid_timestamps = [
            "invalid-date",
            "2024-13-45",  # Invalid date
            "not-a-date-at-all",
            "2024/01/15",  # Wrong format
        ]
        
        for invalid_ts in invalid_timestamps:
            with self.subTest(invalid_timestamp=invalid_ts):
                sighting = Sighting(timestamp=invalid_ts)
                after_test = datetime.utcnow()
                
                # Verify the timestamp is between before and after the test
                # (i.e., it was set to "now" during the test)
                self.assertGreaterEqual(sighting.timestamp, before_test)
                self.assertLessEqual(sighting.timestamp, after_test)

    def test_confidence_validation(self):
        """Test confidence score validation"""
        # Valid confidence scores
        valid_scores = [0, 50, 69, 85, 100]
        for score in valid_scores:
            with self.subTest(score=score):
                sighting = Sighting(confidence=score)
                self.assertEqual(sighting.confidence, score)
        
        # Invalid confidence scores (out of range)
        invalid_scores = [-1, 101, 150, -50]
        for score in invalid_scores:
            with self.subTest(score=score):
                with self.assertRaises(ValidationError):
                    Sighting(confidence=score)

    def test_observation_count_validation(self):
        """Test observation count validation"""
        # Valid observation counts
        valid_counts = [1, 2, 10, 100, 1000]
        for count in valid_counts:
            with self.subTest(count=count):
                sighting = Sighting(observation_count=count)
                self.assertEqual(sighting.observation_count, count)
        
        # Invalid observation counts (zero or negative)
        invalid_counts = [0, -1, -10]
        for count in invalid_counts:
            with self.subTest(count=count):
                with self.assertRaises(ValidationError):
                    Sighting(observation_count=count)

    def test_severity_level_validation(self):
        """Test severity level validation"""
        # Valid severity levels
        valid_severities = [
            SeverityLevel.LOW,
            SeverityLevel.MEDIUM,
            SeverityLevel.HIGH,
            SeverityLevel.CRITICAL
        ]
        
        for severity in valid_severities:
            with self.subTest(severity=severity):
                sighting = Sighting(severity=severity)
                self.assertEqual(sighting.severity, severity)
        
        # Test with string values (should work with enum)
        sighting = Sighting(severity="high")
        self.assertEqual(sighting.severity, SeverityLevel.HIGH)
        
        # Test None (should be allowed)
        sighting = Sighting(severity=None)
        self.assertIsNone(sighting.severity)

    def test_invalid_severity_raises_error(self):
        """Test that invalid severity raises validation error"""
        with self.assertRaises(ValidationError) as context:
            Sighting(severity="invalid_severity")
        
        self.assertIn("severity", str(context.exception))

    def test_observation_times_validation(self):
        """Test validation of first_observed and last_observed times"""
        # Valid case: first_observed before last_observed
        first = datetime(2024, 1, 15, 9, 0, 0)
        last = datetime(2024, 1, 15, 10, 0, 0)
        
        sighting = Sighting(
            first_observed=first,
            last_observed=last
        )
        
        self.assertEqual(sighting.first_observed, first)
        self.assertEqual(sighting.last_observed, last)

    def test_observation_times_invalid_order(self):
        """Test that first_observed after last_observed raises error"""
        first = datetime(2024, 1, 15, 10, 0, 0)  # After last
        last = datetime(2024, 1, 15, 9, 0, 0)    # Before first
        
        with self.assertRaises(ValidationError) as context:
            Sighting(
                first_observed=first,
                last_observed=last
            )
        
        self.assertIn("first_observed cannot be after last_observed", str(context.exception))

    def test_observation_times_same_time(self):
        """Test that same first_observed and last_observed is allowed"""
        same_time = datetime(2024, 1, 15, 10, 0, 0)
        
        sighting = Sighting(
            first_observed=same_time,
            last_observed=same_time
        )
        
        self.assertEqual(sighting.first_observed, same_time)
        self.assertEqual(sighting.last_observed, same_time)

    def test_observation_times_none_values(self):
        """Test that None values for observation times are handled"""
        # Both None
        sighting1 = Sighting(first_observed=None, last_observed=None)
        self.assertIsNone(sighting1.first_observed)
        self.assertIsNone(sighting1.last_observed)
        
        # One None
        time_val = datetime(2024, 1, 15, 10, 0, 0)
        sighting2 = Sighting(first_observed=time_val, last_observed=None)
        self.assertEqual(sighting2.first_observed, time_val)
        self.assertIsNone(sighting2.last_observed)

    def test_factory_method_create(self):
        """Test the create factory method"""
        sighting = Sighting.create(
            confidence=90,
            severity=SeverityLevel.HIGH,
            observation_count=3
        )
        
        self.assertEqual(sighting.confidence, 90)
        self.assertEqual(sighting.severity, SeverityLevel.HIGH)
        self.assertEqual(sighting.observation_count, 3)
        self.assertIsNotNone(sighting.sighting_id)
        self.assertIsNotNone(sighting.timestamp)

    def test_factory_method_minimal(self):
        """Test factory method with minimal parameters"""
        sighting = Sighting.create()
        
        self.assertEqual(sighting.confidence, 69)  # Default
        self.assertIsNone(sighting.severity)
        self.assertEqual(sighting.observation_count, 1)  # Default
        self.assertIsNotNone(sighting.sighting_id)
        self.assertIsNotNone(sighting.timestamp)

    def test_model_dump(self):
        """Test serialization to dictionary"""
        timestamp = datetime(2024, 1, 15, 14, 30, 0)
        sighting = Sighting(
            timestamp=timestamp,
            confidence=85,
            severity=SeverityLevel.HIGH,
            observation_count=2
        )
        
        data = sighting.model_dump()
        
        # Check that all fields are present
        expected_fields = [
            "sighting_id", "timestamp", "confidence", "first_observed",
            "last_observed", "observation_count", "severity"
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Check values
        self.assertEqual(data["confidence"], 85)
        self.assertEqual(data["severity"], "high")  # Enum value
        self.assertEqual(data["observation_count"], 2)
        self.assertIsInstance(data["timestamp"], datetime)

    def test_model_dump_exclude_none(self):
        """Test serialization excluding None values"""
        sighting = Sighting(confidence=75)  # Other optional fields will be None
        
        data = sighting.model_dump(exclude_none=True)
        
        # Check that None fields are excluded
        self.assertNotIn("first_observed", data)
        self.assertNotIn("last_observed", data)
        self.assertNotIn("severity", data)
        
        # Check that non-None fields are present
        self.assertIn("sighting_id", data)
        self.assertIn("timestamp", data)
        self.assertIn("confidence", data)
        self.assertIn("observation_count", data)

    def test_json_serialization_with_datetime(self):
        """Test JSON serialization with datetime handling"""
        timestamp = datetime(2024, 1, 15, 14, 30, 0)
        sighting = Sighting(timestamp=timestamp, confidence=85)
        
        # Test model_dump_json
        json_str = sighting.model_dump_json()
        self.assertIsInstance(json_str, str)
        
        # Parse back to verify format
        data = json.loads(json_str)
        self.assertIn("2024-01-15T14:30:00", data["timestamp"])

    def test_model_config_extra_ignore(self):
        """Test that extra fields are ignored (be forgiving)"""
        # This should not raise an error due to extra="ignore"
        sighting = Sighting(
            confidence=80,
            unknown_field="should_be_ignored",
            another_extra_field=456
        )
        
        self.assertEqual(sighting.confidence, 80)
        # Extra fields should not be accessible
        self.assertFalse(hasattr(sighting, 'unknown_field'))

    def test_sighting_equality(self):
        """Test sighting equality comparison"""
        sighting_id = f"sighting--{uuid.uuid4()}"
        timestamp = datetime(2024, 1, 15, 14, 30, 0)
        
        sighting1 = Sighting(
            sighting_id=sighting_id,
            timestamp=timestamp,
            confidence=85
        )
        
        sighting2 = Sighting(
            sighting_id=sighting_id,
            timestamp=timestamp,
            confidence=85
        )
        
        # Different instances with same data should be equal
        self.assertEqual(sighting1, sighting2)

    def test_sighting_inequality(self):
        """Test sighting inequality"""
        sighting1 = Sighting(confidence=80)
        sighting2 = Sighting(confidence=90)
        
        # Different confidence should not be equal
        self.assertNotEqual(sighting1, sighting2)

    def test_repr_and_str(self):
        """Test string representations"""
        sighting = Sighting(confidence=85, severity=SeverityLevel.HIGH)
        
        repr_str = repr(sighting)
        str_str = str(sighting)
        
        self.assertIsInstance(repr_str, str)
        self.assertIsInstance(str_str, str)
        self.assertIn("Sighting", repr_str)

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Boundary confidence values
        sighting_min = Sighting(confidence=0)
        sighting_max = Sighting(confidence=100)
        self.assertEqual(sighting_min.confidence, 0)
        self.assertEqual(sighting_max.confidence, 100)
        
        # Large observation count
        sighting_large = Sighting(observation_count=999999)
        self.assertEqual(sighting_large.observation_count, 999999)
        
        # Very close timestamps (microsecond difference)
        base_time = datetime(2024, 1, 15, 10, 0, 0, 0)
        close_time = datetime(2024, 1, 15, 10, 0, 0, 1)  # 1 microsecond later
        
        sighting = Sighting(
            first_observed=base_time,
            last_observed=close_time
        )
        self.assertEqual(sighting.first_observed, base_time)
        self.assertEqual(sighting.last_observed, close_time)


class TestSightingIntegration(unittest.TestCase):
    """Integration tests for Sighting with other components"""

    def test_sighting_in_submission_context(self):
        """Test sighting validation in the context of a full submission"""
        sighting = Sighting(
            confidence=85,
            severity=SeverityLevel.HIGH,
            observation_count=3
        )
        
        # Should be able to access all required properties for submission validation
        self.assertIsNotNone(sighting.sighting_id)
        self.assertIsNotNone(sighting.timestamp)
        self.assertIsInstance(sighting.confidence, int)
        self.assertEqual(sighting.severity, SeverityLevel.HIGH)

    def test_multiple_sightings_unique_ids(self):
        """Test that multiple sightings get unique IDs"""
        sightings = [Sighting(confidence=i*10) for i in range(1, 11)]
        
        # All IDs should be unique
        ids = [s.sighting_id for s in sightings]
        self.assertEqual(len(ids), len(set(ids)))
        
        # All IDs should follow the pattern
        for sighting_id in ids:
            self.assertTrue(sighting_id.startswith("sighting--"))
            # Should be valid UUID format
            uuid_part = sighting_id.split("--")[1]
            self.assertIsInstance(uuid.UUID(uuid_part), uuid.UUID)

    def test_sighting_timeline_consistency(self):
        """Test sighting with consistent timeline"""
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        
        sighting = Sighting(
            timestamp=base_time,
            first_observed=base_time - timedelta(minutes=5),
            last_observed=base_time + timedelta(minutes=5),
            observation_count=10
        )
        
        # Timeline should be logically consistent
        self.assertLess(sighting.first_observed, sighting.timestamp)
        self.assertGreater(sighting.last_observed, sighting.timestamp)
        self.assertGreater(sighting.observation_count, 1)


class TestSightingPerformance(unittest.TestCase):
    """Performance-related tests for Sighting"""

    def test_bulk_creation_performance(self):
        """Test creating many sightings (basic performance check)"""
        import time
        
        start_time = time.time()
        sightings = []
        
        for i in range(100):
            sighting = Sighting(
                confidence=min(100, 50 + i),
                severity=SeverityLevel.MEDIUM,
                observation_count=i + 1
            )
            sightings.append(sighting)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should be able to create 100 sightings quickly
        self.assertLess(elapsed, 1.0)  # Less than 1 second
        self.assertEqual(len(sightings), 100)
        
        # All should have unique IDs
        ids = [s.sighting_id for s in sightings]
        self.assertEqual(len(ids), len(set(ids)))

    def test_datetime_parsing_performance(self):
        """Test performance of datetime parsing"""
        import time
        
        timestamp_strings = [
            "2024-01-15T10:30:00Z",
            "2024-01-15T11:30:00+00:00",
            "2024-01-15T12:30:00"
        ] * 50  # 150 total
        
        start_time = time.time()
        
        sightings = []
        for ts_str in timestamp_strings:
            sighting = Sighting(timestamp=ts_str, confidence=75)
            sightings.append(sighting)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should parse timestamps quickly
        self.assertLess(elapsed, 0.5)  # Less than 0.5 seconds
        self.assertEqual(len(sightings), 150)


if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)