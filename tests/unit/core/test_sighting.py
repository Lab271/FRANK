#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)

Unit tests for FRANK Sighting model
Tests the "be forgiving on what you receive, strong on what you return" principle

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest
from unittest.mock import patch
import pytest

import uuid
from datetime import datetime, timezone, timedelta
import json

# Import the models (adjust import path as needed)
from frank.core.models import Sighting, SeverityLevel, Observables, Observable
from frank.core.models import ThreatContext, Impact, Campaign, SigmaDetection
from pydantic import ValidationError


class TestSighting(unittest.TestCase):
    """Comprehensive unit tests for the Sighting model"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.base_timestamp = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        self.valid_sighting_data = {
            "confidence": 85,
            "severity": SeverityLevel.HIGH,
            "observation_count": 3
        }
        self.valid_network_observables = [
            Observable.create_ipv4("192.168.1.100", role="c2"),
            Observable.create_domain("malicious.example.com", role="phishing")
        ]

    def test_create_public_sighting(self):
        """Test creating a public sighting with required fields"""
        sighting = Sighting(**self.valid_sighting_data)

        self.assertIsInstance(sighting, Sighting)
        self.assertEqual(sighting.observation_count, 3)
        self.assertIsNone(sighting.observables)

    def test_create_minimal_sighting(self):
        """Test creating a sighting with minimal required fields"""
        sighting = Sighting(observables=Observables(network=self.valid_network_observables))

        # Check the set values
        self.assertIsInstance(sighting.observables, Observables)
        
        # Check that auto-generated fields are populated
        self.assertIsNotNone(sighting.sighting_id)
        self.assertTrue(sighting.sighting_id.startswith("sighting--"))
        self.assertIsInstance(uuid.UUID(sighting.sighting_id.split("--")[1]), uuid.UUID)
        self.assertIsNotNone(sighting.timestamp)
        self.assertIsInstance(sighting.timestamp, datetime)
        
        # Optional fields should be None
        self.assertIsNone(sighting.first_observed)
        self.assertIsNone(sighting.last_observed)
        self.assertIsNone(sighting.sigma_detection)
        self.assertIsNone(sighting.threat_context)
        self.assertIsNone(sighting.impact)

    def test_create_sighting_with_all_fields(self):
        """Test creating a sighting with all fields provided"""
        sighting_id = f"sighting--{uuid.uuid4()}"
        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        first_observed = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        last_observed = datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        
        sighting = Sighting(
            sighting_id=sighting_id,
            timestamp=timestamp,
            first_observed=first_observed,
            last_observed=last_observed,
            observation_count=5,
            severity=SeverityLevel.CRITICAL,
            observables=Observables(network=self.valid_network_observables)
        )
        
        self.assertIsInstance(sighting.observables, Observables)
        self.assertEqual(sighting.sighting_id, sighting_id)
        self.assertEqual(sighting.timestamp, timestamp)
        self.assertEqual(sighting.first_observed, first_observed)
        self.assertEqual(sighting.last_observed, last_observed)
        self.assertEqual(sighting.observation_count, 5)

    def test_sighting_id_auto_generation(self):
        """Test that sighting_id is auto-generated when not set"""
        # Test not provided
        sighting1 = Sighting(observables=Observables(network=self.valid_network_observables))
        self.assertIsNotNone(sighting1.sighting_id)
        self.assertTrue(sighting1.sighting_id.startswith("sighting--"))
        
        # Test with None
        sighting1 = Sighting(sighting_id=None,
                observables=Observables(network=self.valid_network_observables))
        self.assertIsNotNone(sighting1.sighting_id)
        self.assertTrue(sighting1.sighting_id.startswith("sighting--"))
        
        # Test with empty string
        sighting2 = Sighting(sighting_id="",
                observables=Observables(network=self.valid_network_observables))
        self.assertIsNotNone(sighting2.sighting_id)
        self.assertTrue(sighting2.sighting_id.startswith("sighting--"))
        
        # Test different IDs are generated
        self.assertNotEqual(sighting1.sighting_id, sighting2.sighting_id)

    def test_timestamp_auto_generation_branch(self):
        """Test Sighting auto-generates timestamp if None or empty string is provided (branch coverage)"""
        before = datetime.now(timezone.utc)
        sighting_none = Sighting(
            timestamp=None, confidence=80, observation_count=1,
            sighting_id=None, observables=None, severity=None,
            first_observed=None, last_observed=None,
            sigma_detection=None, threat_context=None, impact=None
        )
        sighting_empty = Sighting(
            timestamp="", confidence=80, observation_count=1,
            sighting_id=None, observables=None, severity=None,
            first_observed=None, last_observed=None,
            sigma_detection=None, threat_context=None, impact=None
        )
        after = datetime.now(timezone.utc)

        self.assertIsInstance(sighting_none.timestamp, datetime)
        self.assertIsInstance(sighting_empty.timestamp, datetime)
        self.assertGreaterEqual(sighting_none.timestamp, before)
        self.assertLessEqual(sighting_none.timestamp, after)
        self.assertGreaterEqual(sighting_empty.timestamp, before)
        self.assertLessEqual(sighting_empty.timestamp, after)

        # If a valid timestamp is provided, it should not be overwritten
        ts = datetime(2025, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
        sighting_valid = Sighting(
            timestamp=ts, confidence=80, observation_count=1,
            sighting_id=None, observables=None, severity=None,
            first_observed=None, last_observed=None,
            sigma_detection=None, threat_context=None, impact=None
        )
        self.assertEqual(sighting_valid.timestamp, ts)

    @patch('frank.core.models.datetime')
    def test_timestamp_auto_generation_with_mock(self, mock_datetime):
        """Test that timestamp is auto-generated when set to None (with proper mocking)"""
        # Mock the current time
        mock_now = datetime(2024, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now
        
        # Test with not provided
        sighting1 = Sighting(observables=Observables(network=self.valid_network_observables))
        self.assertEqual(sighting1.timestamp, mock_now)

        # Test with None
        sighting1 = Sighting(timestamp=None,
                observables=Observables(network=self.valid_network_observables))
        self.assertEqual(sighting1.timestamp, mock_now)

        # Test with empty string
        sighting2 = Sighting(timestamp="",
                observables=Observables(network=self.valid_network_observables))
        self.assertEqual(sighting2.timestamp, mock_now)

    def test_timestamp_auto_generation_simple(self):
        """Test timestamp auto-generation without mocking (simpler approach)"""
        # Capture time before and after to verify it's recent
        before = datetime.now(timezone.utc)

        sighting1 = Sighting(timestamp=None,
                observables=Observables(network=self.valid_network_observables))
        sighting2 = Sighting(timestamp="",
                observables=Observables(network=self.valid_network_observables))

        after = datetime.now(timezone.utc)

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
                sighting = Sighting(timestamp=timestamp_str,
                                    observables=Observables(network=self.valid_network_observables))
                # For timezone-aware comparisons, normalize to UTC
                actual_dt = sighting.timestamp
                if actual_dt.tzinfo:
                    actual_dt = actual_dt.replace(tzinfo=None)
                self.assertEqual(actual_dt, expected_dt)

    def test_timestamp_invalid_string_fallback(self):
        """Test that invalid timestamp strings fall back to current time"""
        # Instead of mocking, test that we get a reasonable timestamp (recent)
        before_test = datetime.now(timezone.utc)
        
        invalid_timestamps = [
            "invalid-date",
            "2024-13-45",  # Invalid date
            "not-a-date-at-all",
            "2024/01/15",  # Wrong format
        ]
        
        for invalid_ts in invalid_timestamps:
            with self.subTest(invalid_timestamp=invalid_ts):
                with self.assertRaises(ValidationError) as cm:
                    sighting = Sighting(timestamp=invalid_ts,
                                        observables=Observables(network=self.valid_network_observables))
 
                    after_test = datetime.now(timezone.utc)
                
                    # Verify the timestamp is between before and after the test
                    # (i.e., it was set to "now" during the test)
                    self.assertGreaterEqual(sighting.timestamp, before_test)
                    self.assertLessEqual(sighting.timestamp, after_test)

    def test_timestamp_timezone(self):
        """Test that Sighting timestamp is timezone-aware."""
        s = Sighting(confidence=50)
        assert s.timestamp.tzinfo is not None

    def test_timestamp_is_set(self):
        """Test that Sighting timestamp is set."""
        s = Sighting(timestamp=None)
        assert s.timestamp is not None

    def test_invalid_observation_time_last(self):
        """Test that Sighting raises error for invalid observation times."""
        first = datetime.now(timezone.utc)
        last = first - timedelta(days=1)
        with pytest.raises(ValueError) as exc:
            Sighting(confidence=50, first_observed=first, last_observed=last)
            self.assertIn("first_observed cannot be after last_observed", str(exc.value))

    def test_invalid_observation_time_timestamp(self):
        """Test that Sighting raises error for invalid observation times."""
        first = datetime.now(timezone.utc)
        last = first - timedelta(days=1)
        with pytest.raises(ValueError) as exc:
            Sighting(confidence=50, first_observed=first, timestamp=last)
            self.assertIn("first_observed cannot be after main timestamp", str(exc.value))


    def test_observation_count_validation(self):
        """Test observation count validation"""
        # Valid observation counts
        valid_counts = [1, 2, 10, 100, 1000]
        for count in valid_counts:
            with self.subTest(count=count):
                sighting = Sighting(observation_count=count,
                                    observables=Observables(network=self.valid_network_observables))
                self.assertEqual(sighting.observation_count, count)
        
        # Invalid observation counts (zero or negative)
        invalid_counts = [0, -1, -10]
        for count in invalid_counts:
            with self.subTest(count=count):
                with self.assertRaises(ValidationError):
                    Sighting(observation_count=count,
                              observables=Observables(network=self.valid_network_observables))

    def test_observation_times_validation(self):
        """Test validation of first_observed and last_observed times"""
        # Valid case: first_observed before last_observed
        first = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        last = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        sighting = Sighting(
            first_observed=first,
            last_observed=last,
            observables=Observables(network=self.valid_network_observables)
        )
        
        self.assertEqual(sighting.first_observed, first)
        self.assertEqual(sighting.last_observed, last)

    def test_observation_times_invalid_order(self):
        """Test that first_observed after last_observed raises error"""
        first = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)  # After last
        last = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)    # Before first

        with self.assertRaises(ValidationError) as context:
            Sighting(
                first_observed=first,
                last_observed=last,
                observables=Observables(network=self.valid_network_observables)
            )
        
        self.assertIn("first_observed cannot be after last_observed", str(context.exception))

    def test_observation_times_same_time(self):
        """Test that same first_observed and last_observed is allowed"""
        same_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        sighting = Sighting(
            first_observed=same_time,
            last_observed=same_time,
            observables=Observables(network=self.valid_network_observables)
        )
        
        self.assertEqual(sighting.first_observed, same_time)
        self.assertEqual(sighting.last_observed, same_time)

    def test_observation_times_none_values(self):
        """Test that None values for observation times are handled"""
        # Both None
        sighting1 = Sighting(first_observed=None, last_observed=None,
                              observables=Observables(network=self.valid_network_observables))
        self.assertIsNone(sighting1.first_observed)
        self.assertIsNone(sighting1.last_observed)
        
        # One None
        time_val = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        sighting2 = Sighting(first_observed=time_val, last_observed=None,
                              observables=Observables(network=self.valid_network_observables))
        self.assertEqual(sighting2.first_observed, time_val)
        self.assertIsNone(sighting2.last_observed)

    def test_factory_method_create(self):
        """Test the create factory method"""
        sighting = Sighting.create(
            observables=Observables(network=self.valid_network_observables)
        )
        
        self.assertEqual(sighting.observation_count, 2)
        self.assertIsNotNone(sighting.sighting_id)
        self.assertIsNotNone(sighting.timestamp)

    def test_model_dump(self):
        """Test serialization to dictionary"""
        timestamp = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        sighting = Sighting(
            timestamp=timestamp,
            observation_count=2,
            observables=Observables(network=self.valid_network_observables)
        )
        
        data = sighting.model_dump()
        
        # Check that all fields are present
        expected_fields = [
            "sighting_id", "timestamp", "first_observed",
            "last_observed", "observation_count", 
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Check values
        self.assertEqual(data["observation_count"], 2)
        self.assertIsInstance(data["timestamp"], str)

    def test_model_dump_exclude_none(self):
        """Test serialization excluding None values"""
        sighting = Sighting(
            observables=Observables(network=self.valid_network_observables))  # Other optional fields will be None

        data = sighting.model_dump(exclude_none=True)
        
        # Check that None fields are excluded
        self.assertNotIn("first_observed", data)
        self.assertNotIn("last_observed", data)
        
        # Check that non-None fields are present
        self.assertIn("sighting_id", data)
        self.assertIn("timestamp", data)
        self.assertIn("observation_count", data)

    def test_json_serialization_with_datetime(self):
        """Test JSON serialization with datetime handling"""
        timestamp = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        sighting = Sighting(timestamp=timestamp, confidence=85,
                            observables=Observables(network=self.valid_network_observables))

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
            unknown_field="should_be_ignored",
            another_extra_field=456,
            observables=Observables(network=self.valid_network_observables)
        )
        
        # Extra fields should not be accessible
        self.assertFalse(hasattr(sighting, 'unknown_field'))

    def test_sighting_equality(self):
        """Test sighting equality comparison"""
        sighting_id = f"sighting--{uuid.uuid4()}"
        timestamp = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)

        sighting1 = Sighting(
            sighting_id=sighting_id,
            timestamp=timestamp,
            confidence=85,
            observables=Observables(network=self.valid_network_observables) 
        )
        
        sighting2 = Sighting(
            sighting_id=sighting_id,
            timestamp=timestamp,
            confidence=85,
            observables=Observables(network=self.valid_network_observables)
        )
      
        # Different instances with same data should be equal
        self.assertEqual(sighting1, sighting2)

    def test_sighting_inequality(self):
        """Test sighting inequality"""
        sighting1 = Sighting(confidence=80,
                              observables=Observables(network=self.valid_network_observables))
        sighting2 = Sighting(confidence=90,
                              observables=Observables(network=self.valid_network_observables))

        # Different confidence should not be equal
        self.assertNotEqual(sighting1, sighting2)

    def test_repr_and_str(self):
        """Test string representations"""
        sighting = Sighting(confidence=85, severity=SeverityLevel.HIGH,
                            observables=Observables(network=self.valid_network_observables))

        repr_str = repr(sighting)
        str_str = str(sighting)
        
        self.assertIsInstance(repr_str, str)
        self.assertIsInstance(str_str, str)
        self.assertIn("Sighting", repr_str)

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Boundary confidence values
        sighting_min = Sighting(observables=Observables(network=self.valid_network_observables))
        sighting_max = Sighting(observables=Observables(network=self.valid_network_observables))

        # Large observation count
        sighting_large = Sighting(
            observation_count=999999, observables=Observables(network=self.valid_network_observables)
        )
        self.assertEqual(sighting_large.observation_count, 999999)

        # Very close timestamps (microsecond difference)
        base_time = datetime(2024, 1, 15, 10, 0, 0, 0, tzinfo=timezone.utc)
        close_time = datetime(2024, 1, 15, 10, 0, 0, 1, tzinfo=timezone.utc)  # 1 microsecond later

        sighting = Sighting(
            first_observed=base_time,
            last_observed=close_time,
            observables=Observables(network=self.valid_network_observables),
        )
        self.assertEqual(sighting.first_observed, base_time)
        self.assertEqual(sighting.last_observed, close_time)


class TestSightingIntegration(unittest.TestCase):
    """Integration tests for Sighting with other components"""

    def setUp(self):
        """Set up test fixtures"""
        self.valid_network_observables = [
             Observable.create_ipv4("192.168.1.100", role="c2")
        ]


    def test_sighting_in_submission_context(self):
        """Test sighting validation in the context of a full submission"""
        sighting = Sighting(
            observation_count=3,
            observables=Observables(network=self.valid_network_observables) 
        )
        
        # Should be able to access all required properties for submission validation
        self.assertIsNotNone(sighting.sighting_id)
        self.assertIsNotNone(sighting.timestamp)

    def test_multiple_sightings_unique_ids(self):
        """Test that multiple sightings get unique IDs"""
        sightings = [Sighting(confidence=i*10,
                               observables=Observables(network=self.valid_network_observables)) for i in range(1, 11)]

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
            observation_count=10,
            observables=Observables(network=self.valid_network_observables)
        )
        
        # Timeline should be logically consistent
        self.assertLess(sighting.first_observed, sighting.timestamp)
        self.assertGreater(sighting.last_observed, sighting.timestamp)
        self.assertGreater(sighting.observation_count, 1)


class TestSightingPerformance(unittest.TestCase):
    """Performance-related tests for Sighting"""    
    def setUp(self):
        """Set up test fixtures"""
        self.valid_network_observables = [
            Observable.create_ipv4("192.168.1.100", role="c2"),
            Observable.create_ipv4("192.168.1.101", role="c2"),
            Observable.create_ipv4("192.168.1.102", role="c2")
        ]

    def test_bulk_creation_performance(self):
        """Test creating many sightings (basic performance check)"""
        import time
        
        start_time = time.time()
        sightings = []
        
        for i in range(100):
            sighting = Sighting(
                confidence=min(100, 50 + i),
                severity=SeverityLevel.MEDIUM,
                observation_count=i + 1,
                observables=Observables(network=self.valid_network_observables) 
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
            sighting = Sighting(timestamp=ts_str, confidence=75,
                                observables=Observables(network=self.valid_network_observables))
            sightings.append(sighting)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should parse timestamps quickly
        self.assertLess(elapsed, 0.5)  # Less than 0.5 seconds
        self.assertEqual(len(sightings), 150)

class TestSerializationModels(unittest.TestCase):
    """Unit tests for serialization and deserialization of Submission submodels."""

    def test_threat_context_serialization(self):
        """Test ThreatContext serialization and deserialization."""
        campaign = Campaign(name="APT-Example", attribution="EvilCorp")
        tc = ThreatContext(campaign=campaign, mitre_attack={"tactic": "TA0001"}, malware_family={"name": "TrickBot"})
        tc_json = tc.model_dump_json()
        tc2 = ThreatContext.model_validate_json(tc_json)
        self.assertIsInstance(tc2.campaign, Campaign)
        self.assertEqual(tc2.campaign.name, "APT-Example")
        self.assertEqual(tc2.campaign.attribution, "EvilCorp")
        self.assertEqual(tc2.mitre_attack["tactic"], "TA0001")
        self.assertEqual(tc2.malware_family["name"], "TrickBot")

    def test_impact_serialization(self):
        """Test Impact serialization and deserialization."""
        impact = Impact(affected_systems=42, compromised_accounts=5, containment_time="2h", financial_impact_eur=10000)
        impact_json = impact.model_dump_json()
        impact2 = Impact.model_validate_json(impact_json)
        self.assertEqual(impact2.affected_systems, 42)
        self.assertEqual(impact2.compromised_accounts, 5)
        self.assertEqual(impact2.containment_time, "2h")
        self.assertEqual(impact2.financial_impact_eur, 10000)

    def test_campaign_serialization(self):
        """Test Campaign serialization and deserialization."""
        campaign = Campaign(
            name="Spring Offensive",
            attribution="APT-Example",
            target_sectors=["finance", "energy"],
            attack_vector="phishing",
            payload_type="malware",
            campaign_start=datetime(2024, 3, 1, 8, 0, 0, tzinfo=timezone.utc),
            estimated_victims=1000,
            confidence=85
        )
        campaign_json = campaign.model_dump_json()
        campaign2 = Campaign.model_validate_json(campaign_json)
        self.assertEqual(campaign2.name, "Spring Offensive")
        self.assertEqual(campaign2.attribution, "APT-Example")
        self.assertEqual(campaign2.target_sectors, ["finance", "energy"])
        self.assertEqual(campaign2.attack_vector, "phishing")
        self.assertEqual(campaign2.payload_type, "malware")
        self.assertEqual(campaign2.campaign_start, datetime(2024, 3, 1, 8, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(campaign2.estimated_victims, 1000)
        self.assertEqual(campaign2.confidence, 85)
        self.assertTrue(hasattr(campaign2, "id"))
        self.assertTrue(campaign2.id.startswith("campaign--"))

    def test_campaign_implicit_id_generation(self):
        """Test implicit ID generation for Campaign."""
        campaign = Campaign(name="Autumn Offensive")
        self.assertTrue(hasattr(campaign, "id"))
        self.assertTrue(campaign.id.startswith("campaign--"))

    def test_sigma_detection_serialization(self):
        """Test SigmaDetection serialization and deserialization."""
        sigma = SigmaDetection(rule_id=f"sigma--{uuid.uuid4()}", rule_name="Suspicious Login", rule_version="1.0", rule_status="active", sigma_yaml="rule: ...", rule_effectiveness=0.9, false_positive_rate=0.01)
        sigma_json = sigma.model_dump_json()
        sigma2 = SigmaDetection.model_validate_json(sigma_json)
        self.assertEqual(sigma2.rule_name, "Suspicious Login")
        self.assertEqual(sigma2.rule_version, "1.0")
        self.assertEqual(sigma2.rule_status, "active")
        self.assertEqual(sigma2.sigma_yaml, "rule: ...")
        self.assertEqual(sigma2.rule_effectiveness, 0.9)
        self.assertEqual(sigma2.false_positive_rate, 0.01)
        self.assertTrue(hasattr(sigma2, "rule_id"))
        self.assertIn("sigma--", sigma2.rule_id)

    def test_sigma_detection_implicit_id_generation(self):
        """Test implicit ID generation for SigmaDetection."""
        sigma = SigmaDetection(rule_name="Suspicious Login")
        self.assertTrue(hasattr(sigma, "rule_id"))
        self.assertTrue(sigma.rule_id.startswith("sigma--"))


if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)