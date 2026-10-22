#!/usr/bin/env python3
"""
FRANK Platform - API Unit Tests

Unit tests for frank/util/requests.py

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import types
import unittest

from frank.core.models import Submission
from frank.util import requests
from frank.util.requests import ObservationsResponse, SightingSearchResponse, SubmissionRequest, SubmissionResponse


class TestSubmissionRequest(unittest.TestCase):
    """Unit tests for SubmissionRequest model validation and field handling."""
    def test_valid_submission_request(self):
        """Test creating valid submission request with proper submission object."""
        submission = Submission(submission_id="sub1")
        req = SubmissionRequest(submission=submission)
        self.assertEqual(req.submission.submission_id, "sub1")

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored during submission request creation."""
        submission = Submission(submission_id="sub2")
        req = SubmissionRequest(submission=submission, extra_field="ignored")
        self.assertEqual(req.submission.submission_id, "sub2")
        self.assertFalse(hasattr(req, "extra_field"))

class TestSubmissionResponse(unittest.TestCase):
    """Unit tests for SubmissionResponse model fields and validation."""
    def test_submission_response_fields(self):
        """Test submission response creation with all required and optional fields."""
        resp = SubmissionResponse(
            status="accepted",
            submission_id="sub1",
            contribution_score_impact=10,
            processing_status="queued",
            validation_required=True,
            estimated_processing_time="2-5 minutes"
        )
        self.assertEqual(resp.status, "accepted")
        self.assertEqual(resp.submission_id, "sub1")
        self.assertEqual(resp.contribution_score_impact, 10)
        self.assertEqual(resp.processing_status, "queued")
        self.assertTrue(resp.validation_required)
        self.assertEqual(resp.estimated_processing_time, "2-5 minutes")

class TestSightingSearchResponse(unittest.TestCase):
    """Unit tests for SightingSearchResponse model with various field combinations."""
    def test_sighting_search_response_minimal(self):
        """Test sighting search response with minimal required fields only."""
        resp = SightingSearchResponse(
            total_results=5,
            returned_results=2,
            sightings=[{"id": 1}, {"id": 2}],
            aggregations=None,
            threat_context=None,
            pagination=None
        )
        self.assertEqual(resp.total_results, 5)
        self.assertEqual(resp.returned_results, 2)
        self.assertEqual(len(resp.sightings), 2)
        self.assertIsNone(resp.aggregations)
        self.assertIsNone(resp.threat_context)
        self.assertIsNone(resp.pagination)

    def test_sighting_search_response_full(self):
        """Test sighting search response with all optional fields populated."""
        resp = SightingSearchResponse(
            total_results=10,
            returned_results=5,
            sightings=[{"id": i} for i in range(5)],
            aggregations={"total": 10},
            threat_context={"actor": "APT"},
            pagination={"has_next": True}
        )
        self.assertEqual(resp.aggregations["total"], 10)
        self.assertEqual(resp.threat_context["actor"], "APT")
        self.assertTrue(resp.pagination["has_next"])

class TestObservationsResponse(unittest.TestCase):
    """Unit tests for ObservationsResponse model with statistics and pagination."""
    def test_observations_response_minimal(self):
        """Test observations response with minimal required fields only."""
        resp = ObservationsResponse(
            total_results=3,
            returned_results=3,
            observations=[{"type": "ipv4"}, {"type": "domain"}, {"type": "url"}],
            stats=None,
            observable_types=None,
            pagination=None
        )
        self.assertEqual(resp.total_results, 3)
        self.assertEqual(resp.returned_results, 3)
        self.assertEqual(len(resp.observations), 3)
        self.assertIsNone(resp.stats)
        self.assertIsNone(resp.observable_types)
        self.assertIsNone(resp.pagination)

    def test_observations_response_full(self):
        """Test observations response with all optional fields populated."""
        resp = ObservationsResponse(
            total_results=5,
            returned_results=2,
            observations=[{"type": "ipv4"}, {"type": "domain"}],
            stats={"ipv4": 3, "domain": 2},
            observable_types=["ipv4", "domain"],
            pagination={"has_next": False}
        )
        self.assertEqual(resp.stats["ipv4"], 3)
        self.assertIn("domain", resp.observable_types)
        self.assertFalse(resp.pagination["has_next"])


class TestRequests(unittest.TestCase):
    """Unit tests for requests module functionality and structure."""
    def test_module_exists(self):
        """Test that the requests module is imported and is a module."""
        self.assertTrue(isinstance(requests, types.ModuleType))

    # Add more specific tests below if requests.py exposes functions/classes
    # Example:
    # def test_some_function(self):
    #     result = requests.some_function(args)
    #     self.assertEqual(result, expected)

if __name__ == "__main__":
    unittest.main()
