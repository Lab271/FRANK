#!/usr/bin/env python3
"""
FRANK Platform - Baseclass database
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

Unit tests for BaseFRANKDatabase abstract base class in base.py

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
from unittest.mock import MagicMock
from frank.core.enum import AccessTier
from frank.storage import BaseFRANKDatabase

class DummyDatabase(BaseFRANKDatabase):
    """
    Minimal concrete implementation for testing BaseFRANKDatabase.

    This assures that we keep track of all methods for the Base class.
    Functionally it is not very exciting.

    It also tests the initialization logic
    """
    def initialize(self):
        # Not recommended: calling super() abstract method for coverage only
        super().initialize()
        self.initialized = True

    def upsert_organization(self, org_data):
        # Not recommended: calling super() abstract method for coverage only
        super().upsert_organization(org_data)
        return True

    def store_submission(self, submission):
        # Not recommended: calling super() abstract method for coverage only
        super().store_submission(submission)
        return None

    def get_submission_by_id(self, submission_id):
        # Not recommended: calling super() abstract method for coverage only
        super().get_submission_by_id(submission_id)
        return {"submission_id": submission_id} if submission_id == "subid" else None

    def query_observables(self, org_id, observable_type=None, limit=100, access_level=None,
                         min_confidence=None, sectors=None, days_back=None):
        # Not recommended: calling super() abstract method for coverage only
        super().query_observables(org_id, observable_type, limit, access_level,
                                 min_confidence, sectors, days_back)
        return []

    def get_statistics_summary(self, org_id, days=30):
        # Not recommended: calling super() abstract method for coverage only
        super().get_statistics_summary(org_id, days)
        return {"count": 0}

    def search_observables_by_value(self, org_id, search_value, access_level=AccessTier.CONTRIBUTOR):
        # Not recommended: calling super() abstract method for coverage only
        super().search_observables_by_value(self, org_id, search_value, access_level)
        return [{"value":0}]
    
    def log_access(self, org_id, action, resource_type=None, resource_id=None, details=None):
        # Not recommended: calling super() abstract method for coverage only
        super().log_access(org_id, action, resource_type, resource_id, details)
        return True

    def health_check(self):
        # Not recommended: calling super() abstract method for coverage only
        super().health_check()
        return {"status": "ok"}

class TestBaseFRANKDatabaseAbstractMethods(unittest.TestCase):
    """
    Unit tests for the BaseFRANKDatabase abstract base class.
    """

    def setUp(self):
        """Set up DummyDatabase instance."""
        connection_params = {"test_param": "value"}
        self.db = DummyDatabase(connection_params=connection_params)
        
    def test_logger_injection(self):
        """Test DummyDatabase instantiation with a mock logger."""
        class MockLogger:
            def info(self, msg):
                self.last_msg = msg

        mock_logger = MockLogger()
        db_with_logger = DummyDatabase(connection_params={}, logger=mock_logger)
        self.assertIs(db_with_logger.logger, mock_logger)
        db_with_logger.logger.info("test message")
        self.assertEqual(mock_logger.last_msg, "test message")

    def test_initialize(self):
        """Test database initialization and connection_params."""
        self.assertTrue(hasattr(self.db, 'initialized'))
        self.assertTrue(self.db.initialized)
        # Ensure connection_params is a dict and can hold parameters
        self.db.connection_params['test_param'] = 'value'
        self.assertIn('test_param', self.db.connection_params)

    def test_upsert_organization(self):
        """Test upsert_organization method."""
        self.assertTrue(self.db.upsert_organization({"name": "TestOrg"}))

    def test_store_submission(self):
        """Test store_submission method."""
        self.assertIsNone(self.db.store_submission(None))

    def test_get_submission_by_id(self):
        """Test get_submission_by_id method."""
        self.assertIsNone(self.db.get_submission_by_id("none"))

    def test_get_submission_by_id_value(self):
        """Test get_submission_by_id method."""
        self.assertIsInstance(self.db.get_submission_by_id("subid"), dict)

    def test_query_observables(self):
        """Test query_observables method with all parameters."""
        result = self.db.query_observables(
            "orgid",
            observable_type=None,
            limit=100,
            access_level=None,
            min_confidence=None,
            sectors=None,
            days_back=None
        )
        self.assertEqual(result, [])

    def test_get_statistics_summary(self):
        """Test get_statistics_summary method."""
        summary = self.db.get_statistics_summary("orgid")
        self.assertIn("count", summary)
        self.assertEqual(summary["count"], 0)

    def test_log_access(self):
        """Test log_access method."""
        self.assertTrue(self.db.log_access("orgid", "read"))

    def test_health_check(self):
        """Test health_check method."""
        status = self.db.health_check()
        self.assertEqual(status["status"], "ok")


class TestBaseFRANKDatabase(unittest.TestCase):
    """
    Unit tests for the BaseFRANKDatabase methods.
    """

    def setUp(self):
        """Set up DummyDatabase instance."""
        connection_params = {"test_param": "value"}
        mock_logger = MagicMock()
        self.db = DummyDatabase(connection_params=connection_params, logger=mock_logger)


    def test_filter_submission_by_access_level_public(self):
        """Test _filter_submission_by_access_level for PUBLIC tier."""
        submission = {
            'submission_id': 'subid',
            'timestamp': '2025-09-14T00:00:00Z',
            'sighting': {
                'confidence': 80,
                'timestamp': '2025-09-14T00:00:00Z',
                'observation_count': 5,
                'observables': {}
            }
        }
        result = self.db._filter_submission_by_access_level(submission, AccessTier.PUBLIC)
        self.assertIn('submission', result)
        self.assertIn('sighting', result['submission'])
        self.assertEqual(result['submission']['sighting']['confidence'], 80)

    def test_filter_submission_by_access_level_observer(self):
        """Test _filter_submission_by_access_level for OBSERVER tier."""
        submission = {
            'submission_id': 'subid',
            'timestamp': '2025-09-14T00:00:00Z',
            'sighting': {
                'confidence': 80,
                'timestamp': '2025-09-14T00:00:00Z',
                'observation_count': 5,
                'observables': {
                    'ip': [{'value': '1.2.3.4.5.6.7.8.9.10'}]
                }
            },
            'hit_target': {'organization_id': 'orgid'},
            'tlp_level': 'red'
        }
        result = self.db._filter_submission_by_access_level(submission, AccessTier.OBSERVER)
        self.assertIn('submission', result)
        obs_val = result['submission']['sighting']['observables']['ip'][0]['value']
        self.assertTrue(obs_val.endswith('...'))
        self.assertNotIn('hit_target', result['submission'])
        self.assertNotIn('tlp_level', result['submission'])

    def test_filter_submission_by_access_level_contributor(self):
        """Test _filter_submission_by_access_level for CONTRIBUTOR tier."""
        submission = {
            'submission_id': 'subid',
            'timestamp': '2025-09-14T00:00:00Z',
            'sighting': {
                'confidence': 80,
                'timestamp': '2025-09-14T00:00:00Z',
                'observation_count': 5,
                'observables': {}
            },
            'hit_target': {'organization_id': 'orgid', 'sector': 'finance'}
        }
        result = self.db._filter_submission_by_access_level(submission, AccessTier.CONTRIBUTOR)
        self.assertIn('submission', result)
        hit_target = result['submission']['hit_target']
        self.assertNotIn('organization_id', hit_target)
        self.assertEqual(hit_target['sector'], 'finance')

    def test_filter_submission_by_access_level_partner(self):
        """Test _filter_submission_by_access_level for PARTNER tier (full access)."""
        submission = {'submission_id': 'subid', 'sighting': {}}
        result = self.db._filter_submission_by_access_level(submission, AccessTier.PARTNER)
        self.assertIn('submission', result)
        self.assertEqual(result['submission'], submission)

    def test_filter_observable_by_access_level_public(self):
        """Test _filter_observable_by_access_level for PUBLIC tier."""
        observable = {
            'observable_type': 'ip',
            'total_sightings': 10,
            'last_seen': '2025-09-14T00:00:00Z',
            'observable_value': '1.2.3.4'
        }
        result = self.db._filter_observable_by_access_level(observable, AccessTier.PUBLIC)
        self.assertIn('observable_type', result)
        self.assertIn('total_sightings', result)
        self.assertIn('last_seen', result)
        self.assertNotIn('observable_value', result)

    def test_filter_observable_by_access_level_observer(self):
        """Test _filter_observable_by_access_level for OBSERVER tier."""
        observable = {
            'observable_type': 'ip',
            'total_sightings': 10,
            'last_seen': '2025-09-14T00:00:00Z',
            'observable_value': '1.2.3.4.5.6.7.8.9.10'
        }
        result = self.db._filter_observable_by_access_level(observable, AccessTier.OBSERVER)
        self.assertIn('observable_value', result)
        self.assertTrue(result['observable_value'].endswith('...'))

    def test_filter_observable_by_access_level_contributor(self):
        """Test _filter_observable_by_access_level for CONTRIBUTOR tier (full access)."""
        observable = {
            'observable_type': 'ip',
            'total_sightings': 10,
            'last_seen': '2025-09-14T00:00:00Z',
            'observable_value': '1.2.3.4'
        }
        result = self.db._filter_observable_by_access_level(observable, AccessTier.CONTRIBUTOR)
        self.assertEqual(result, observable)

    def test_hash_observable(self):
        """Test hash_observable method."""
        hash1 = self.db.hash_observable("ipv4", "1.2.3.4")
        hash2 = self.db.hash_observable("ipv4", "1.2.3.4")
        self.assertEqual(hash1, hash2)
        self.assertIsInstance(hash1, str)

if __name__ == "__main__":
    unittest.main()
