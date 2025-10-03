#!/usr/bin/env python3
"""
FRANK Platform - Unit tests for FRANK Server module

Tests high-level server interface, threat intelligence operations, and helper functions

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
from unittest.mock import MagicMock, patch

from frank.util.server import create_server, calculate_contribution_score
from frank.core.models import Submission, Submitter
from frank.core.enum import AccessTier

class TestFRANKServer(unittest.TestCase):
    """Unit tests for FRANK server operations and threat intelligence processing."""
    def setUp(self):
        """Set up test fixtures with mocked database and logger."""
        # Mock database and logger
        self.mock_db = MagicMock()
        self.mock_logger = MagicMock()
        self.server = create_server(self.mock_db, self.mock_logger)

    def test_submit_threat_intelligence_success(self):
        """Test successful threat intelligence submission with contribution score calculation."""
        submission = MagicMock(spec=Submission)
        submission.submission_id = "sub123"
        with patch('frank.util.server.calculate_contribution_score', return_value=15):
             score = self.server.submit_threat_intelligence("user1", submission)
        self.assertEqual(score, 15)
        self.mock_db.store_submission.assert_called_once_with(submission)
        self.mock_db.log_access.assert_called_once_with("user1", 'SUBMIT', 'submission', "sub123")

    def test_query_threats_observable(self):
        """Test querying threats with specific observable value."""
        self.mock_db.search_observables_by_value.return_value = [{"observable_hash": "abc", "observable_type": "ipv4"}]
        self.mock_db.query_observables.return_value = []
        result = self.server.query_threats("org1", AccessTier.CONTRIBUTOR, 10, 0, "summary", observable="1.2.3.4")
        self.mock_db.search_observables_by_value.assert_called_once()
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], 1)
        self.assertIsInstance(result[1], list)

    def test_query_threats_general(self):
        """Test general threat intelligence query without specific observable."""
        self.mock_db.search_observables_by_value.return_value = []
        self.mock_db.query_observables.return_value = [{"observable_hash": "def", "observable_type": "domain"}]
        result = self.server.query_threats("org1", AccessTier.OBSERVER, 10, 0, "summary")
        self.mock_db.query_observables.assert_called_once()
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], 1)
        self.assertIsInstance(result[1], list)

    def test_get_observations(self):
        """Test retrieving observable statistics and details."""
        self.mock_db.get_statistics_summary.return_value = {
            'observable_totals': {'ipv4': 5, 'domain': 3}
        }
        obs, stats = self.server.get_observations("org1", 30, None, 10)
        self.assertEqual(len(obs), 2)
        self.assertEqual(stats['observable_totals']['ipv4'], 5)

    def test_get_platform_statistics_observer(self):
        """Test platform statistics filtering for observer access tier."""
        self.mock_db.get_statistics_summary.return_value = {
            "total_submissions": 10,
            "observable_types": {"ipv4": 5},
            "daily_activity": {"2025-09-14": 2},
            "sensitive": "should not appear"
        }
        stats = self.server.get_platform_statistics("org1", AccessTier.OBSERVER, 30)
        self.assertIn("total_submissions", stats)
        self.assertNotIn("sensitive", stats)

    def test_get_platform_statistics_contributor(self):
        """Test platform statistics for contributor access tier."""
        self.mock_db.get_statistics_summary.return_value = {"total_submissions": 10}
        stats = self.server.get_platform_statistics("org1", AccessTier.CONTRIBUTOR, 30)
        self.assertIn("total_submissions", stats)

    def test_health_check(self):
        """Test server health check endpoint functionality."""
        self.mock_db.health_check.return_value = {"status": "healthy"}
        result = self.server.health_check()
        self.assertEqual(result["status"], "healthy")
        self.assertIn("database", result)
        self.assertIn("version", result)

    def test_seed_database_success(self):
        """Test successful database seeding operation."""
        seeder = MagicMock()
        seeder.seed.return_value = None
        self.assertTrue(self.server.seed_database(seeder))
        seeder.seed.assert_called_once_with(self.mock_db)

    def test_seed_database_failure(self):
        """Test database seeding failure handling and error logging."""
        seeder = MagicMock()
        seeder.seed.side_effect = Exception("fail")
        self.assertFalse(self.server.seed_database(seeder))
        self.mock_logger.error.assert_called()

    def test_upsert_organisation(self):
        """Test organisation upsert operation with access logging."""
        submitter = MagicMock(spec=Submitter)
        submitter.model_dump.return_value = {"organisation_id": "org123"}
        submitter.organisation_id = "org123"
        self.server.upsert_organisation(submitter)
        self.mock_db.upsert_organisation.assert_called_once_with({"organisation_id": "org123"})
        self.mock_db.log_access.assert_called_once_with("org123", 'UPSERT', 'organisation', "org123")

    def test_get_submission_by_id_found(self):
        """Test retrieving existing submission by ID with access filtering."""
        submission_dict = {"submission": {"submission_id": "sub1"}}
        self.mock_db.get_submission_by_id.return_value = submission_dict
        with patch('frank.util.server.FRANKFilter') as MockFilter:
            mock_filter = MockFilter.return_value
            mock_filter.submission_by_access_level.return_value = {"submission": {"submission_id": "sub1"}}
            result = self.server.get_submission_by_id("user1", AccessTier.CONTRIBUTOR, "sub1")
            self.assertIsNotNone(result)
            self.mock_db.log_access.assert_called_once_with("user1", 'READ', 'submission', "sub1")

    def test_get_submission_by_id_not_found(self):
        """Test retrieving non-existent submission returns None."""
        self.mock_db.get_submission_by_id.return_value = None
        result = self.server.get_submission_by_id("user1", AccessTier.CONTRIBUTOR, "sub1")
        self.assertIsNone(result)



class TestHelperFunctions(unittest.TestCase):
    """Unit tests for server helper functions and utility methods."""
    def test_calculate_contribution_score(self):
        """Test contribution score calculation based on submission content."""
        submission = MagicMock()
        submission.sighting.observables.network = [1,2]
        submission.sighting.observables.file = [3]
        submission.sighting.observables.process = []
        submission.sighting.sigma_detection = True
        submission.sighting.threat_context = True
        submission.sighting.impact = True
        score = calculate_contribution_score(submission)
        self.assertLessEqual(score, 25)

    def test_format_sighting_response_observer(self):
        """Test sighting response formatting for observer access tier."""
        from frank.util.server import format_sighting_response
        result = {"observable_hash": "abcdef123456", "last_seen": "2025-09-20T12:00:00Z", "observable_type": "ipv4", "observable_value": "1.2.3.4", "avg_confidence": 80}
        resp = format_sighting_response(result, AccessTier.OBSERVER, "summary")
        self.assertIn("sighting_id", resp)
        self.assertEqual(resp["observable_type"], "ipv4")
        self.assertEqual(resp["observable_value"], "1.2.3.***")
        from frank.util.server import format_sighting_response
        result = {"observable_hash": "abcdef123456", "last_seen": "2025-09-20T12:00:00Z", "observable_type": "ipv4", "observable_value": "1.2.3.4", "avg_confidence": 80}
        resp = format_sighting_response(result, AccessTier.OBSERVER, "summary")
        self.assertIn("sighting_id", resp)
        self.assertEqual(resp["observable_type"], "ipv4")
        self.assertEqual(resp["observable_value"], "1.2.3.4"[:6] + "***")

    def test_format_sighting_response_contributor(self):
        """Test sighting response formatting for contributor access tier."""
        from frank.util.server import format_sighting_response
        result = {"observable_hash": "abcdef1234567890", "last_seen": "2025-09-20T12:00:00Z", "observable_type": "domain", "observable_value": "example.com", "avg_confidence": 70, "total_sightings": 5, "sectors": ["finance"]}
        resp = format_sighting_response(result, AccessTier.CONTRIBUTOR, "summary")
        self.assertIn("sighting_id", resp)
        self.assertIn("observable", resp)
        self.assertEqual(resp["total_sightings"], 5)

    def test_format_sighting_response_partner(self):
        """Test sighting response formatting for partner access tier."""
        from frank.util.server import format_sighting_response
        result = {"observable_hash": "abcdef1234567890", "last_seen": "2025-09-20T12:00:00Z", "observable_type": "domain", "observable_value": "example.com", "avg_confidence": 90, "total_sightings": 10, "unique_organisations": 3, "first_seen": "2025-09-01T12:00:00Z", "sectors": ["finance"], "regions": ["EU"]}
        resp = format_sighting_response(result, AccessTier.PARTNER, "summary")
        self.assertIn("unique_organisations", resp)
        self.assertIn("regions", resp)

    def test_mask_observable_value(self):
        """Test observable value masking for different data types."""
        from frank.util.server import mask_observable_value
        self.assertEqual(mask_observable_value("1.2.3.4", "ipv4"), "1.2.3.***")
        self.assertTrue(mask_observable_value("example.com", "domain").startswith("*****"))
        self.assertEqual(mask_observable_value("longobservablevalue", "other"), "longobserv...")
        self.assertEqual(mask_observable_value("short", "other"), "short")

    def test_generate_aggregations(self):
        """Test statistical aggregation generation from threat intelligence results."""
        from frank.util.server import generate_aggregations
        results = [
            {"observable_hash": "a", "avg_confidence": 85, "total_sightings": 2},
            {"observable_hash": "b", "avg_confidence": 65, "total_sightings": 3},
            {"observable_hash": "c", "avg_confidence": 40, "total_sightings": 1},
        ]
        aggs = generate_aggregations(results, AccessTier.CONTRIBUTOR)
        self.assertEqual(aggs["total_organisations"], 3)
        self.assertEqual(aggs["confidence_distribution"], {"high": 1, "medium": 1, "low": 1})
        self.assertEqual(aggs["total_sightings"], 6)

    def test_generate_threat_context(self):
        """Test threat context information generation for high-tier users."""
        from frank.util.server import generate_threat_context
        results = [{}]
        context = generate_threat_context(results)
        self.assertIn("campaigns_involved", context)
        self.assertIn("mitre_attack", context)

    def test_create_server_factory(self):
        """Test server factory function creates proper FRANKServer instance."""
        from frank.util.server import create_server, FRANKServer
        db = MagicMock()
        logger = MagicMock()
        server = create_server(db, logger)
        self.assertIsInstance(server, FRANKServer)
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
