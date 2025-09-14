import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from frank.util.client import create_client, calculate_contribution_score
from frank.core.models import Submission
from frank.core.enum import AccessTier

class TestFRANKClient(unittest.TestCase):
    def setUp(self):
        # Mock database and logger
        self.mock_db = MagicMock()
        self.mock_logger = MagicMock()
        self.client = create_client(self.mock_db, self.mock_logger)

    def test_submit_threat_intelligence_success(self):
        submission = MagicMock(spec=Submission)
        submission.submission_id = "sub123"
        self.mock_db.store_submission.return_value = True
        self.mock_db.log_access.return_value = True
        with patch('frank.util.client.calculate_contribution_score', return_value=15):
            success, score = self.client.submit_threat_intelligence("user1", submission)
        self.assertTrue(success)
        self.assertEqual(score, 15)
        self.mock_db.store_submission.assert_called_once_with(submission)
        self.mock_db.log_access.assert_called_once_with("user1", 'SUBMIT', 'submission', "sub123")

    def test_submit_threat_intelligence_failure(self):
        submission = MagicMock(spec=Submission)
        self.mock_db.store_submission.return_value = False
        success, score = self.client.submit_threat_intelligence("user1", submission)
        self.assertFalse(success)
        self.assertEqual(score, 0)

    def test_query_threats_observable(self):
        self.mock_db.search_observables_by_value.return_value = [{"observable_hash": "abc", "observable_type": "ipv4"}]
        self.mock_db.query_observables.return_value = []
        result = self.client.query_threats("org1", AccessTier.CONTRIBUTOR, 10, 0, "summary", observable="1.2.3.4")
        self.mock_db.search_observables_by_value.assert_called_once()
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], 1)
        self.assertIsInstance(result[1], list)

    def test_query_threats_general(self):
        self.mock_db.search_observables_by_value.return_value = []
        self.mock_db.query_observables.return_value = [{"observable_hash": "def", "observable_type": "domain"}]
        result = self.client.query_threats("org1", AccessTier.OBSERVER, 10, 0, "summary")
        self.mock_db.query_observables.assert_called_once()
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], 1)
        self.assertIsInstance(result[1], list)

    def test_get_observations(self):
        self.mock_db.get_statistics_summary.return_value = {
            'observable_totals': {'ipv4': 5, 'domain': 3}
        }
        obs, stats = self.client.get_observations("org1", 30, None, 10)
        self.assertEqual(len(obs), 2)
        self.assertEqual(stats['observable_totals']['ipv4'], 5)

    def test_get_platform_statistics_observer(self):
        self.mock_db.get_statistics_summary.return_value = {
            "total_submissions": 10,
            "observable_types": {"ipv4": 5},
            "daily_activity": {"2025-09-14": 2},
            "sensitive": "should not appear"
        }
        stats = self.client.get_platform_statistics("org1", 30, AccessTier.OBSERVER)
        self.assertIn("total_submissions", stats)
        self.assertNotIn("sensitive", stats)

    def test_get_platform_statistics_contributor(self):
        self.mock_db.get_statistics_summary.return_value = {"total_submissions": 10}
        stats = self.client.get_platform_statistics("org1", 30, AccessTier.CONTRIBUTOR)
        self.assertIn("total_submissions", stats)

    def test_health_check(self):
        self.mock_db.health_check.return_value = {"status": "healthy"}
        self.mock_db.name = "mockdb"
        result = self.client.health_check()
        self.assertEqual(result["status"], "healthy")
        self.assertIn("mockdb", result)
        self.assertIn("version", result)

    def test_seed_database_success(self):
        seeder = MagicMock()
        seeder.seed.return_value = None
        self.assertTrue(self.client.seed_database(seeder))
        seeder.seed.assert_called_once_with(self.mock_db)

    def test_seed_database_failure(self):
        seeder = MagicMock()
        seeder.seed.side_effect = Exception("fail")
        self.assertFalse(self.client.seed_database(seeder))
        self.mock_logger.error.assert_called()

class TestHelperFunctions(unittest.TestCase):
    def test_calculate_contribution_score(self):
        submission = MagicMock()
        submission.sighting.observables.network = [1,2]
        submission.sighting.observables.file = [3]
        submission.sighting.observables.process = []
        submission.sighting.sigma_detection = True
        submission.sighting.threat_context = True
        submission.sighting.impact = True
        score = calculate_contribution_score(submission)
        self.assertLessEqual(score, 25)

if __name__ == "__main__":
    unittest.main()
