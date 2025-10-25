#!/usr/bin/env python3
"""
FRANK Platform - API Unit Tests

Unit tests for frank/util/requests.py

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import types
import unittest
from datetime import datetime, timezone, timedelta

from frank.core.models import Submission, Sighting, Submitter, ObservableType
from frank.core.enum import TLPLevel
from frank.util import requests
from frank.util.http_exceptions import BadRequestException
from frank.util.requests import (
    SubmissionRequest,
    SubmissionResponse,
    SightingSearchResponse,
    ObservationsResponse,
    ObservationsSearchQuery,
    OrganisationRequest
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

class TestOrganisationRequest(unittest.TestCase):
    """Unit tests for OrganisationRequest model validation."""
    
    def test_valid_organisation_request(self):
        """Test creating valid organisation request with proper submitter object."""
        submitter = Submitter(organisation_id="org--123")
        req = OrganisationRequest(organisation=submitter)
        self.assertEqual(req.organisation.organisation_id, "org--123")
    
    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored during organisation request creation."""
        submitter = Submitter(organisation_id="org--456")
        req = OrganisationRequest(organisation=submitter, extra_field="ignored")
        self.assertEqual(req.organisation.organisation_id, "org--456")
        self.assertFalse(hasattr(req, "extra_field"))


class TestObservationsSearchQuery(unittest.TestCase):
    """Unit tests for ObservationsSearchQuery model validation and methods."""
    
    def test_valid_search_query_minimal(self):
        """Test creating search query with minimal fields."""
        query = ObservationsSearchQuery()
        self.assertIsNone(query.observable)
        self.assertIsNone(query.observable_type)
        self.assertEqual(query.limit, 100)  # Default value
    
    def test_valid_search_query_with_observable(self):
        """Test creating search query with observable value."""
        query = ObservationsSearchQuery(observable="192.168.1.1")
        self.assertEqual(query.observable, "192.168.1.1")
    
    def test_valid_search_query_with_type(self):
        """Test creating search query with observable type."""
        query = ObservationsSearchQuery(observable_type=ObservableType.IPV4_ADDR)
        self.assertEqual(query.observable_type, ObservableType.IPV4_ADDR)
    
    def test_valid_search_query_with_dates(self):
        """Test creating search query with valid date range."""
        start = datetime.now(timezone.utc) - timedelta(days=7)
        end = datetime.now(timezone.utc)
        query = ObservationsSearchQuery(start_date=start, end_date=end)
        self.assertEqual(query.start_date, start)
        self.assertEqual(query.end_date, end)
    
    def test_invalid_date_range_raises_exception(self):
        """Test that invalid date range raises BadRequestException."""
        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc) - timedelta(days=1)
        
        with self.assertRaises(BadRequestException) as context:
            ObservationsSearchQuery(start_date=start, end_date=end)
        
        self.assertIn("Invalid date range", str(context.exception.detail))
        self.assertIn("start_date must be before end_date", str(context.exception.detail))
    
    def test_equal_start_and_end_date_raises_exception(self):
        """Test that equal start and end dates raise BadRequestException."""
        same_time = datetime.now(timezone.utc)
        
        with self.assertRaises(BadRequestException) as context:
            ObservationsSearchQuery(start_date=same_time, end_date=same_time)
        
        self.assertIn("Invalid date range", str(context.exception.detail))
    
    def test_to_dict_basic(self):
        """Test to_dict method with basic fields."""
        query = ObservationsSearchQuery(observable="test.com", limit=50)
        result = query.to_dict()
        
        self.assertEqual(result["observable"], "test.com")
        self.assertEqual(result["limit"], 50)
    
    def test_to_dict_with_start_date(self):
        """Test to_dict method calculates days_back from start_date."""
        # Create a start date 10 days ago
        start = datetime.now(timezone.utc) - timedelta(days=10)
        query = ObservationsSearchQuery(start_date=start)
        result = query.to_dict()
        
        self.assertIn("days_back", result)
        # days_back should be around 10 (allowing for slight timing differences)
        self.assertGreaterEqual(result["days_back"], 9)
        self.assertLessEqual(result["days_back"], 11)
    
    def test_to_dict_with_all_fields(self):
        """Test to_dict method with all fields populated."""
        start = datetime.now(timezone.utc) - timedelta(days=5)
        end = datetime.now(timezone.utc)
        query = ObservationsSearchQuery(
            observable="malicious.com",
            observable_type=ObservableType.DOMAIN_NAME,
            start_date=start,
            end_date=end,
            limit=200
        )
        result = query.to_dict()
        
        self.assertEqual(result["observable"], "malicious.com")
        self.assertEqual(result["observable_type"], ObservableType.DOMAIN_NAME)
        self.assertEqual(result["limit"], 200)
        self.assertIn("days_back", result)
    
    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored in search query."""
        query = ObservationsSearchQuery(observable="test", extra_field="ignored")
        self.assertEqual(query.observable, "test")
        self.assertFalse(hasattr(query, "extra_field"))


class TestRequests(unittest.TestCase):
    """Unit tests for requests module functionality and structure."""
    def test_module_exists(self):
        """Test that the requests module is imported and is a module."""
        self.assertTrue(isinstance(requests, types.ModuleType))

if __name__ == "__main__":
    unittest.main()
