import unittest
from datetime import datetime
from frank.util.stix import sighting_to_stix_bundle
from frank.core.models import Sighting, HitTarget, Observables, Observable
from frank.core.enum import ObservableType

class TestStixUtils(unittest.TestCase):
    def test_sighting_to_stix_bundle(self):
        # Create Observables using correct field names and ObservableType enum
        network_obs = [
            Observable(type=ObservableType.IPV4, value="1.2.3.4", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None),
            Observable(type=ObservableType.DOMAIN, value="example.com", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None)
        ]
        file_obs = [
            Observable(type=ObservableType.FILE_HASH, value="abcdef1234567890", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None)
        ]
        process_obs = [
            Observable(type=ObservableType.MUTEX, value="Global\\MutexName", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None)
        ]
        observables = Observables(network=network_obs, file=file_obs, process=process_obs)
        hit_target = HitTarget(organisation_id="org--1", sector="finance", region="eu", anonymization_level="low", organisation_type=None, organisation_size=None)
        sighting = Sighting(
            sighting_id="sighting--1234",
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            first_observed=None,
            last_observed=None,
            observation_count=1,
            observables=observables,
            hit_target=hit_target,
            sigma_detection=None,
            threat_context=None,
            impact=None
        )
        bundle = sighting_to_stix_bundle(sighting)
        self.assertEqual(bundle["type"], "bundle")
        self.assertEqual(bundle["id"], "bundle--1234")
        self.assertTrue(any(obj["type"] == "observed-data" for obj in bundle["objects"]))
        self.assertTrue(any(obj["type"] == "identity" for obj in bundle["objects"]))
        self.assertTrue(any(obj["type"] == "sighting" for obj in bundle["objects"]))
        # Check some observable details
        observed_data = next(obj for obj in bundle["objects"] if obj["type"] == "observed-data")
        self.assertIn("objects", observed_data)
        self.assertIn("0", observed_data["objects"])
        types_in_objects = [obj["type"] for obj in observed_data["objects"].values()]
        self.assertIn("ipv4-addr", types_in_objects)
        self.assertIn("domain-name", types_in_objects)
        # Check identity details
        identity = next(obj for obj in bundle["objects"] if obj["type"] == "identity")
        self.assertEqual(identity["id"], "org--1")
        self.assertEqual(identity["sectors"], ["finance"])
        self.assertEqual(identity["region"], "eu")
        self.assertEqual(identity["anonymization_level"], "low")
        # Check sighting details
        sighting_obj = next(obj for obj in bundle["objects"] if obj["type"] == "sighting")
        self.assertEqual(sighting_obj["id"], "sighting--1234")
        self.assertEqual(sighting_obj["count"], 1)
        self.assertEqual(sighting_obj["where_sighted_refs"], ["org--1"])
        self.assertEqual(sighting_obj["observed_data_refs"], [observed_data["id"]])

    def test_sighting_to_stix_bundle_all_observable_types(self):
        # Add examples for all ObservableType values
        all_obs = [
            Observable(type=ObservableType.IPV4, value="8.8.8.8", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None),
            Observable(type=ObservableType.IPV6, value="2001:db8::1", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None),
            Observable(type=ObservableType.DOMAIN, value="example.org", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None),
            Observable(type=ObservableType.URL, value="https://example.org/page", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None),
            Observable(type=ObservableType.EMAIL, value="user@example.org", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None),
            Observable(type=ObservableType.FILE_HASH, value="abcdef1234567890", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None),
            Observable(type=ObservableType.REGISTRY_KEY, value="HKEY_LOCAL_MACHINE\\Software\\Test", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None),
            Observable(type=ObservableType.MUTEX, value="Global\\MutexName", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None),
            Observable(type=ObservableType.CERTIFICATE, value="MIIDdzCCAl+gAwIBAgIEbG9jYWw=", id=None, role=None, port=None, protocol=None, first_seen=None, connection_count=None)
        ]
        observables = Observables(network=all_obs, file=[], process=[])
        hit_target = HitTarget(organisation_id="org--enumtest", sector="technology", region="us", anonymization_level="medium", organisation_type=None, organisation_size=None)
        sighting = Sighting(
            sighting_id="sighting--enumtest",
            timestamp=datetime(2025, 2, 2, 12, 0, 0),
            first_observed=None,
            last_observed=None,
            observation_count=1,
            observables=observables,
            hit_target=hit_target,
            sigma_detection=None,
            threat_context=None,
            impact=None
        )
        bundle = sighting_to_stix_bundle(sighting)
        self.assertEqual(bundle["type"], "bundle")
        self.assertEqual(bundle["id"], "bundle--enumtest")
        observed_data = next(obj for obj in bundle["objects"] if obj["type"] == "observed-data")
        # Check that all ObservableType values are present and mapped
        expected_types = [
            "ipv4-addr", "ipv6-addr", "domain-name", "url", "email-addr", "file-hash", "windows-registry-key", "mutex", "certificate"
            # "ipv4-addr", "domain-name"
        ]
        actual_types = [obj["type"] for obj in observed_data["objects"].values()]
        for etype in expected_types:
            self.assertIn(etype, actual_types)

if __name__ == "__main__":
    unittest.main()
