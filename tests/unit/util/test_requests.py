#!/usr/bin/env python3
"""
FRANK Platform - API Unit Tests

Unit tests for frank/util/requests.py

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import types
import unittest

from frank.core.models import Submission, Sighting, Submitter
from frank.core.enum import TLPLevel
from frank.util import requests
from frank.util.requests import (
    SubmissionRequest,
    SubmissionResponse,
    SightingSearchResponse,
    ObservationsResponse
)

class TestSubmissionRequest(unittest.TestCase):
    """Unit tests for SubmissionRequest model validation and field handling."""
    def setUp(self):
        self.valid_sighting = Sighting()
        self.valid_submitter = Submitter(organisation_id="org--1")

    def test_valid_submission_request(self):
        """Test creating valid submission request with proper submission object."""
        submission = Submission(submission_id="sub1", sighting=self.valid_sighting, submitter=self.valid_submitter)
        req = SubmissionRequest(submission=submission)
        self.assertEqual(req.submission.submission_id, "sub1")

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored during submission request creation."""
        submission = Submission(submission_id="sub2", sighting=self.valid_sighting, submitter=self.valid_submitter)
        req = SubmissionRequest(submission=submission, extra_field="ignored")
        self.assertEqual(req.submission.submission_id, "sub2")
        self.assertFalse(hasattr(req, "extra_field"))

class TestSubmissionResponse(unittest.TestCase):
    """Unit tests for SubmissionResponse model fields and validation."""
    def test_submission_response_fields(self):
        """Test submission response creation with all required and optional fields."""
        resp = SubmissionResponse(
            timestamp="2025-01-01T12:00:00Z",
            status="accepted",
            submission_id="sub1",
            processing_status="queued",
            tlp_level=TLPLevel.AMBER_PLUS,
            validation_required=True,
            estimated_processing_time="2-5 minutes"
        )
        self.assertEqual(resp.status, "accepted")
        self.assertEqual(resp.submission_id, "sub1")
        self.assertEqual(resp.processing_status, "queued")
        self.assertEqual(resp.tlp_level, TLPLevel.AMBER_PLUS)
        self.assertTrue(resp.validation_required)
        self.assertEqual(resp.estimated_processing_time, "2-5 minutes")

class TestSightingSearchResponse(unittest.TestCase):
    """Unit tests for SightingSearchResponse model with various field combinations."""
    def test_sighting_search_response_minimal(self):
        """Test sighting search response with minimal required fields only."""
        resp = SightingSearchResponse(
            total_results=5,
            sightings=[{"id": 1}, {"id": 2}]
        )
        self.assertEqual(resp.total_results, 5)
        self.assertEqual(len(resp.sightings), 2)


class TestObservationsResponse(unittest.TestCase):
    """Unit tests for ObservationsResponse model with statistics and pagination."""
    def test_observations_response_minimal(self):
        """Test observations response with minimal required fields only."""
        resp = ObservationsResponse(
            total_results=3,
            observations=[{"type": "ipv4"}, {"type": "domain"}, {"type": "url"}],
        )
        self.assertEqual(resp.total_results, 3)
        self.assertEqual(len(resp.observations), 3)

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
