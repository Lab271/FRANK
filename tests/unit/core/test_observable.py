#!/usr/bin/env python3
"""
FRANK Platform - Observable Unit Tests

Comprehensive testing for the Observable Pydantic model using unittest framework.
Tests validation, serialization, factory methods, and "be forgiving" principles.
All based on Pydantic v2 models and validation

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest
from datetime import datetime, timezone
import json
import yaml
import uuid

from frank.core.models import Observable, Observables
from frank.core.enum import ObservableType


class TestObservableValidation(unittest.TestCase):
    """Test Observable validation and 'be forgiving' principles."""

    def test_create_ipv4_observable_minimal(self):
        """Test creating IPv4 observable with minimal required fields."""
        observable = Observable(
            observable_type=ObservableType.IPV4,
            value="192.168.1.1"
        )
        
        self.assertEqual(observable.observable_type, ObservableType.IPV4)
        self.assertEqual(observable.value, "192.168.1.1")
        self.assertIsNotNone(observable.id)
        self.assertTrue(observable.id.startswith("ipv4--"))

    def test_create_ipv4_observable_full(self):
        """Test creating IPv4 observable with all fields."""
        test_time = datetime.now()
        observable = Observable(
            type=ObservableType.IPV4,
            value="203.0.113.42",
            role="c2_server",
            port=443,
            protocol="tcp",
            first_seen=test_time,
            connection_count=15
        )
        
        self.assertEqual(observable.observable_type, ObservableType.IPV4)
        self.assertEqual(observable.value, "203.0.113.42")
        self.assertEqual(observable.role, "c2_server")
        self.assertEqual(observable.port, 443)
        self.assertEqual(observable.protocol, "tcp")
        self.assertEqual(observable.first_seen, test_time)
        self.assertEqual(observable.connection_count, 15)

    def test_create_ipv6_observable(self):
        """Test creating IPv6 observable."""
        observable = Observable(
            observable_type=ObservableType.IPV6,
            value="2001:db8::1"
        )
        
        self.assertEqual(observable.observable_type, ObservableType.IPV6)
        self.assertEqual(observable.value, "2001:db8::1")
        self.assertTrue(observable.id.startswith("ipv6--"))

    def test_create_domain_observable(self):
        """Test creating domain observable."""
        observable = Observable(
            observable_type=ObservableType.DOMAIN,
            value="malicious-site.com",
            role="phishing_domain"
        )
        
        self.assertEqual(observable.observable_type, ObservableType.DOMAIN)
        self.assertEqual(observable.value, "malicious-site.com")
        self.assertEqual(observable.role, "phishing_domain")
        self.assertTrue(observable.id.startswith("domain--"))

    def test_create_url_observable(self):
        """Test creating URL observable."""
        observable = Observable(
            observable_type=ObservableType.URL,
            value="https://malicious-site.com/payload.exe"
        )
        
        self.assertEqual(observable.observable_type, ObservableType.URL)
        self.assertEqual(observable.value, "https://malicious-site.com/payload.exe")
        self.assertTrue(observable.id.startswith("url--"))

    def test_create_email_observable(self):
        """Test creating email observable."""
        observable = Observable(
            observable_type=ObservableType.EMAIL,
            value="malicious@example.com"
        )
        
        self.assertEqual(observable.observable_type, ObservableType.EMAIL)
        self.assertEqual(observable.value, "malicious@example.com")
        self.assertTrue(observable.id.startswith("email--"))

    def test_stix_id_generation(self):
        """Test STIX-compliant ID generation."""
        observable = Observable(
            observable_type=ObservableType.IPV4,
            value="192.168.1.1"
        )
        
        self.assertIsNotNone(observable.id)
        self.assertEqual(len(observable.id.split("--")), 2)
        
        # Validate UUID part
        uuid_part = observable.id.split("--")[1]
        self.assertEqual(len(uuid_part), 36)  # UUID length
        # Test that UUID part is valid - should not raise exception
        try:
            uuid.UUID(uuid_part)
        except ValueError:
            self.fail(f"Invalid UUID format: {uuid_part}")

    def test_get_dict(self):
        """Test export to dict"""

class TestObservableSerialization(unittest.TestCase):
    """Test Observable serialization and deserialization with various formats."""
    
    def setUp(self):
        """Set up test data."""
        self.test_datetime = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        
        self.minimal_data = {
            "type": "ipv4",
            "value": "192.168.1.1"
        }
        
        self.full_data = {
            "id": "ipv4--12345678-1234-5678-9abc-123456789abc",
            "type": "ipv4",
            "value": "192.168.1.1",
            "role": "C2",
            "port": 80,
            "protocol": "tcp",
            "first_seen": self.test_datetime.isoformat(),
            "connection_count": 15
        }
        
        self.domain_data = {
            "type": "domain",
            "value": "MALICIOUS.EXAMPLE.COM",  # Test normalization
            "role": "exfiltration"
        }

    def test_dict_to_observable_minimal(self):
        """Test creating Observable from minimal dictionary."""
        observable = Observable(**self.minimal_data)
        
        self.assertEqual(observable.observable_type, ObservableType.IPV4)
        self.assertEqual(observable.value, "192.168.1.1")
        self.assertIsNotNone(observable.id)
        self.assertTrue(observable.id.startswith("ipv4--"))

    def test_dict_to_observable_full(self):
        """Test creating Observable from full dictionary."""
        observable = Observable(**self.full_data)
        
        self.assertEqual(observable.id, self.full_data["id"])
        self.assertEqual(observable.observable_type, ObservableType.IPV4)
        self.assertEqual(observable.value, "192.168.1.1")
        self.assertEqual(observable.role, "C2")
        self.assertEqual(observable.port, 80)
        self.assertEqual(observable.protocol, "tcp")
        self.assertIsInstance(observable.first_seen, datetime)
        self.assertEqual(observable.first_seen, self.test_datetime) 
        self.assertEqual(observable.connection_count, 15)

    def test_observable_to_dict_with_alias(self):
        """Test converting Observable to dictionary using aliases."""
        observable = Observable(**self.full_data)
        result = observable.model_dump(by_alias=True, exclude_none=True)
        
        self.assertIn("type", result)
        self.assertNotIn("observable_type", result)
        self.assertEqual(result["type"], "ipv4")
        self.assertEqual(result["value"], "192.168.1.1")
        self.assertEqual(result["port"], 80)
        self.assertIsInstance(result["first_seen"], str)
        self.assertEqual(result["first_seen"], "2025-01-15T10:30:00+00:00") 

    def test_observable_to_dict_with_field_names(self):
        """Test converting Observable to dictionary using field names."""
        observable = Observable(**self.full_data)
        result = observable.model_dump(by_alias=False, exclude_none=True)
        
        self.assertIn("observable_type", result)
        self.assertNotIn("type", result)
        self.assertEqual(result["observable_type"], "ipv4")

    def test_dict_roundtrip_minimal(self):
        """Test dictionary roundtrip with minimal data."""
        # Dict -> Observable -> Dict
        observable = Observable(**self.minimal_data)
        result_dict = observable.model_dump(by_alias=True, exclude_none=True)
        
        # Check essential fields survived
        self.assertEqual(result_dict["type"], self.minimal_data["type"])
        self.assertEqual(result_dict["value"], self.minimal_data["value"])
        self.assertIn("id", result_dict)

    def test_dict_roundtrip_full(self):
        """Test dictionary roundtrip with full data."""
        observable = Observable(**self.full_data)
        result_dict = observable.model_dump(by_alias=True, exclude_none=True)
        
        # Create new observable from result
        roundtrip_observable = Observable(**result_dict)
        
        self.assertEqual(observable.id, roundtrip_observable.id)
        self.assertEqual(observable.observable_type, roundtrip_observable.observable_type)
        self.assertEqual(observable.value, roundtrip_observable.value)
        self.assertEqual(observable.role, roundtrip_observable.role)
        self.assertEqual(observable.port, roundtrip_observable.port)

    def test_json_serialization(self):
        """Test JSON serialization."""
        observable = Observable(**self.full_data)
        json_str = observable.model_dump_json(by_alias=True, exclude_none=True)
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        self.assertEqual(parsed["type"], "ipv4")
        self.assertEqual(parsed["value"], "192.168.1.1")

    def test_json_deserialization(self):
        """Test JSON deserialization."""
        json_str = json.dumps(self.full_data)
        parsed_dict = json.loads(json_str)
        observable = Observable(**parsed_dict)
        
        self.assertEqual(observable.observable_type, ObservableType.IPV4)
        self.assertEqual(observable.value, "192.168.1.1")

    def test_json_roundtrip(self):
        """Test complete JSON roundtrip."""
        original = Observable(**self.full_data)
        
        # Observable -> JSON -> Dict -> Observable
        json_str = original.model_dump_json(by_alias=True, exclude_none=True)
        parsed_dict = json.loads(json_str)
        roundtrip = Observable(**parsed_dict)
        
        self.assertEqual(original.id, roundtrip.id)
        self.assertEqual(original.observable_type, roundtrip.observable_type)
        self.assertEqual(original.value, roundtrip.value)
        self.assertEqual(original.role, roundtrip.role)

    def test_yaml_serialization(self):
        """Test YAML serialization."""
        observable = Observable(**self.full_data)
        data = observable.model_dump(by_alias=True, exclude_none=True)
        yaml_str = yaml.dump(data, default_flow_style=False)
        
        # Verify YAML is valid and contains expected content
        self.assertIn("type: ipv4", yaml_str)
        self.assertIn("value: 192.168.1.1", yaml_str)
        self.assertIn("port: 80", yaml_str)

    def test_yaml_deserialization(self):
        """Test YAML deserialization."""
        yaml_str = """
        type: ipv4
        value: "10.0.0.1"
        role: "C2"
        port: 443
        protocol: "https"
        """
        
        parsed_dict = yaml.safe_load(yaml_str)
        observable = Observable(**parsed_dict)
        
        self.assertEqual(observable.observable_type, ObservableType.IPV4)
        self.assertEqual(observable.value, "10.0.0.1")
        self.assertEqual(observable.role, "C2")
        self.assertEqual(observable.port, 443)

    def test_yaml_roundtrip(self):
        """Test complete YAML roundtrip."""
        original = Observable(**self.full_data)
        
        # Observable -> YAML -> Dict -> Observable
        data = original.model_dump(by_alias=True, exclude_none=True)
        yaml_str = yaml.dump(data, default_flow_style=False)
        parsed_dict = yaml.safe_load(yaml_str)
        roundtrip = Observable(**parsed_dict)
        
        self.assertEqual(original.id, roundtrip.id)
        self.assertEqual(original.observable_type, roundtrip.observable_type)
        self.assertEqual(original.value, roundtrip.value)

    def test_normalization_in_serialization(self):
        """Test that normalization works during serialization roundtrips."""
        # Test domain normalization
        observable = Observable(**self.domain_data)
        
        # Value should be normalized to lowercase
        self.assertEqual(observable.value, "malicious.example.com")
        
        # Test roundtrip preserves normalization
        data = observable.model_dump(by_alias=True, exclude_none=True)
        roundtrip = Observable(**data)
        self.assertEqual(roundtrip.value, "malicious.example.com")

    def test_datetime_serialization_json(self):
        """Test datetime handling in JSON serialization."""
        data_with_datetime = self.full_data.copy()
        data_with_datetime["first_seen"] = self.test_datetime
        
        observable = Observable(**data_with_datetime)
        json_str = observable.model_dump_json(by_alias=True, exclude_none=True)
        
        # Parse back and verify datetime
        parsed = json.loads(json_str)
        self.assertIn("first_seen", parsed)
        
        # Recreate observable
        roundtrip = Observable(**parsed)
        self.assertIsInstance(roundtrip.first_seen, datetime)

    def test_field_name_vs_alias_parsing(self):
        """Test that both field names and aliases work for input."""
        # Using alias
        obs1 = Observable(type=ObservableType.DOMAIN, value="example.com")
        
        # Using field name
        obs2 = Observable(observable_type=ObservableType.DOMAIN, value="example.com")
        
        # Both should work and produce the same result
        self.assertEqual(obs1.observable_type, obs2.observable_type)
        self.assertEqual(obs1.value, obs2.value)

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored due to 'extra=ignore' config."""
        data_with_extra = self.minimal_data.copy()
        data_with_extra.update({
            "unknown_field": "should_be_ignored",
            "another_extra": 123
        })
        
        # Should not raise an error
        observable = Observable(**data_with_extra)
        self.assertEqual(observable.observable_type, ObservableType.IPV4)
        self.assertEqual(observable.value, "192.168.1.1")

    def test_invalid_data_validation(self):
        """Test that invalid data raises appropriate errors."""
        # Missing required field
        with self.assertRaises(Exception):
            Observable(type="ipv4")  # Missing value
        
        # Invalid port
        with self.assertRaises(Exception):
            Observable(type="ipv4", value="192.168.1.1", port=70000)
        
        # Invalid connection count
        with self.assertRaises(Exception):
            Observable(type="ipv4", value="192.168.1.1", connection_count=-1)

    def test_multiple_format_consistency(self):
        """Test that dict, JSON, and YAML produce consistent results."""
        original = Observable(**self.full_data)
        
        # Get data in different formats
        dict_data = original.model_dump(by_alias=True, exclude_none=True)
        json_data = json.loads(original.model_dump_json(by_alias=True, exclude_none=True))
        yaml_data = yaml.safe_load(yaml.dump(dict_data, default_flow_style=False))
        
        # Create observables from each format
        from_dict = Observable(**dict_data)
        from_json = Observable(**json_data)
        from_yaml = Observable(**yaml_data)
        
        # All should be equivalent
        observables = [from_dict, from_json, from_yaml]
        for obs in observables:
            self.assertEqual(obs.id, original.id)
            self.assertEqual(obs.observable_type, original.observable_type)
            self.assertEqual(obs.value, original.value)
            self.assertEqual(obs.role, original.role)

    def test_wrapped_yaml_format(self):
        """Test YAML with wrapper (like submission format)."""
        observable = Observable(**self.minimal_data)
        
        # Create wrapped format
        wrapped_data = {
            "observable": observable.model_dump(by_alias=True, exclude_none=True)
        }
        
        yaml_str = yaml.dump(wrapped_data, default_flow_style=False)
        
        # Parse back
        parsed = yaml.safe_load(yaml_str)
        roundtrip = Observable(**parsed["observable"])
        
        self.assertEqual(observable.observable_type, roundtrip.observable_type)
        self.assertEqual(observable.value, roundtrip.value)

    def test_dict_export(self):
        """Make sure we understand dict export"""
        observable_dict = {
            "network": [
                {
                    "type": ObservableType.IPV4.value,
                    "value": "198.51.100.1",
                    "confidence": 80,
                },
                {
                    "type": ObservableType.IPV6.value,
                    "value": "2001:db8::1",
                    "confidence": 70,
                },
                {
                    "type": ObservableType.DOMAIN.value,
                    "value": "malicious.example.com",
                    "confidence": 85,
                },
                {
                    "type": ObservableType.URL.value,
                    "value": "https://phishing.example.com/login",
                    "confidence": 90,
                },
                {
                    "type": ObservableType.EMAIL.value,
                    "value": "attacker@malicious.test",
                    "confidence": 75,
                },
                {
                    "type": ObservableType.CERTIFICATE.value,
                    "value": "40:6B:8B:CD:F9:27:A2:1C:42:8A:B9:F1:12:34:56:78:9A:BC:DE:F0",
                    "confidence": 75,
                }
            ],
            "file": [
                {
                    "type": ObservableType.FILE_HASH.value,
                    "value": "5d41402abc4b2a76b9719d911017c592",
                    "confidence": 95,
                },
                {
                    "type": ObservableType.FILE_HASH.value,
                    "value": "356a192b7913b04c54574d18c28d46e6395428ab",
                    "confidence": 90,
                },
                {
                    "type": ObservableType.FILE_HASH.value,
                    "value": "e258d248fda94c63753607f7c4494ee0fcbe92f1a76bfdac795c9d84101eb317",
                    "confidence": 100,
                }
             ],
            "process": [
                {
                    "type": ObservableType.MUTEX.value,
                    "value": "Global\\MalwareMutex",
                    "confidence": 85,
                },
                {
                    "type": ObservableType.MUTEX.value,
                    "value": "Local\\RansomwareLock",
                    "confidence": 90,
                },
                {
                    "type": ObservableType.REGISTRY_KEY.value,
                    "value": "HKEY_LOCAL_MACHINE\\SOFTWARE\\Malware\\Config",
                    "confidence": 80,
                },
                {
                    "type": ObservableType.REGISTRY_KEY.value,
                    "value": "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\Backdoor",
                    "confidence": 95,
                }
            ],
        }
        obs = Observables(**observable_dict)
        self.assertEqual(len(obs.network)+len(obs.file)+len(obs.process), 6+3+4)
        obs.network = []
        self.assertEqual(len(obs.network)+len(obs.file)+len(obs.process), 3+4)
        obs.process = None
        self.assertEqual(len(obs.network)+len(obs.file)+len(obs.process or []), 3)

class TestObservableBeForgivingPrinciple(unittest.TestCase):
    """Test 'be forgiving on what you receive' principle."""

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored per ConfigDict(extra='ignore')."""
        observable_data = {
            "type": ObservableType.IPV4,
            "value": "192.168.1.1",
            "unexpected_field": "should_be_ignored",
            "another_extra": 12345
        }
        
        observable = Observable(**observable_data)
        self.assertFalse(hasattr(observable, 'unexpected_field'))
        self.assertFalse(hasattr(observable, 'another_extra'))
        self.assertEqual(observable.observable_type, ObservableType.IPV4)
        self.assertEqual(observable.value, "192.168.1.1")

    def test_whitespace_trimming(self):
        """Test that values are trimmed of whitespace."""
        observable = Observable(
            observable_type=ObservableType.DOMAIN,
            value="  example.com  "
        )
        
        self.assertEqual(observable.value, "example.com")

    def test_case_normalization_domains(self):
        """Test that domains are normalized to lowercase."""
        observable = Observable(
            observable_type=ObservableType.DOMAIN,
            value="EXAMPLE.COM"
        )
        
        self.assertEqual(observable.value, "example.com")

    def test_case_normalization_ipv4(self):
        """Test that IPv4 addresses are normalized to lowercase."""
        observable = Observable(
            observable_type=ObservableType.IPV4,
            value="192.168.1.1"  # Already lowercase, but test the logic
        )
        
        self.assertEqual(observable.value, "192.168.1.1")

    def test_url_case_preservation(self):
        """Test that URLs preserve case (unlike domains)."""
        observable = Observable(
            observable_type=ObservableType.URL,
            value="  https://Example.com/Path  "
        )
        
        # URLs should only be trimmed, not lowercased
        self.assertEqual(observable.value, "https://Example.com/Path")

    def test_empty_optional_fields(self):
        """Test handling of None/empty optional fields."""
        observable = Observable(
            observable_type=ObservableType.IPV4,
            value="192.168.1.1",
            role=None,
            port=None,
            protocol=None,
            first_seen=None,
            connection_count=None
        )
        
        self.assertIsNone(observable.role)
        self.assertIsNone(observable.port)
        self.assertIsNone(observable.protocol)
        self.assertIsNone(observable.first_seen)
        self.assertIsNone(observable.connection_count)

class TestObservableFactoryMethods(unittest.TestCase):
    """Test factory methods for creating observables."""

    def test_create_ipv4_factory_with_role_and_port(self):
        """Test create_ipv4 factory method with role and port."""
        observable = Observable.create_ipv4(
            value="203.0.113.10",
            role="malware_c2",
            port=8080
        )
        
        self.assertEqual(observable.observable_type, ObservableType.IPV4)
        self.assertEqual(observable.value, "203.0.113.10")
        self.assertEqual(observable.role, "malware_c2")
        self.assertEqual(observable.port, 8080)

    def test_create_domain_factory_with_role(self):
        """Test create_domain factory method with role."""
        observable = Observable.create_domain(
            value="phishing-bank.com",
            role="phishing_domain"
        )
        
        self.assertEqual(observable.observable_type, ObservableType.DOMAIN)
        self.assertEqual(observable.value, "phishing-bank.com")
        self.assertEqual(observable.role, "phishing_domain")

    def test_factory_methods_generate_ids(self):
        """Test that factory methods generate proper STIX IDs."""
        ipv4_obs = Observable.create_ipv4("192.168.1.1")
        domain_obs = Observable.create_domain("example.com")
        
        self.assertTrue(ipv4_obs.id.startswith("ipv4--"))
        self.assertTrue(domain_obs.id.startswith("domain--"))
        self.assertNotEqual(ipv4_obs.id, domain_obs.id)

if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)