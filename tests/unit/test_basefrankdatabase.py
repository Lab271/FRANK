#!/usr/bin/env python3
"""
Unit tests for BaseFRANKDatabase abstract base class in base.py
"""
import unittest
from frank.db.base import BaseFRANKDatabase

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
        return True

    def get_submission_by_id(self, submission_id, org_id, access_level=None):
        # Not recommended: calling super() abstract method for coverage only
        super().get_submission_by_id(submission_id, org_id, access_level)
        return None

    def query_observables(self, org_id, observable_type=None, limit=100, access_level=None):
        # Not recommended: calling super() abstract method for coverage only
        super().query_observables(org_id, observable_type, limit, access_level)
        return []

    def get_statistics_summary(self, org_id, days=30):
        # Not recommended: calling super() abstract method for coverage only
        super().get_statistics_summary(org_id, days)
        return {"count": 0}

    def log_access(self, org_id, action, resource_type=None, resource_id=None, details=None):
        # Not recommended: calling super() abstract method for coverage only
        super().log_access(org_id, action, resource_type, resource_id, details)
        return True

    def health_check(self):
        # Not recommended: calling super() abstract method for coverage only
        super().health_check()
        return {"status": "ok"}

class TestBaseFRANKDatabase(unittest.TestCase):

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
        self.assertTrue(self.db.store_submission(None))

    def test_get_submission_by_id(self):
        """Test get_submission_by_id method."""
        self.assertIsNone(self.db.get_submission_by_id("subid", "orgid"))

    def test_query_observables(self):
        """Test query_observables method."""
        self.assertEqual(self.db.query_observables("orgid"), [])

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

    def test_hash_observable(self):
        """Test hash_observable method."""
        hash1 = self.db.hash_observable("ipv4", "1.2.3.4")
        hash2 = self.db.hash_observable("ipv4", "1.2.3.4")
        self.assertEqual(hash1, hash2)
        self.assertIsInstance(hash1, str)

if __name__ == "__main__":
    unittest.main()
