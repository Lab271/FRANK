#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)

Unit tests for FRANK Submission (FRANKSubmission) class
Tests the "be forgiving on what you receive, strong on what you return" principle

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest
import uuid

from frank import __version__
from frank.core.enum import AccessTier, ObservableType, SeverityLevel
from frank.core.models import Submission, Submitter, Observable, HitTarget, Sighting, Observables

from pydantic import ValidationError


class TestSubmission(unittest.TestCase):
    """Unit tests for the Submission Pydantic model"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.valid_network_observables = [
            Observable.create_ipv4("192.168.1.100", role="c2"),
            Observable.create_domain("malicious.example.com", role="phishing")
        ]
        
        self.valid_submitter = Submitter.create(
            organisation_id='identity--' + str(uuid.uuid4()),
            access_level=AccessTier.PARTNER,
            sector="financial"
        )
        
        self.valid_hit_target = HitTarget.create(
            sector="healthcare",
            organisation_size="large"
        )
        
        self.valid_sighting = Sighting.create(
            observables=Observables(network=self.valid_network_observables),
            observation_count=2
        )
        
        self.valid_sighting_hit_target = Sighting.create(
            observables=Observables(network=self.valid_network_observables),
            observation_count=2,
            hit_target=self.valid_hit_target
        )
        self.valid_observables = Observables(
            network=self.valid_network_observables
        )

    def test_create_minimal_valid_submission(self):
        """Test 1: Create a minimal valid Submission with all required components"""
        submission = Submission(
            submitter=self.valid_submitter,
            sighting=self.valid_sighting
        )
        
        # Verify all required components are present
        self.assertIsInstance(submission.submitter, Submitter)
        self.assertIsInstance(submission.sighting, Sighting)
        self.assertIsInstance(submission.sighting.observables, Observables)
        
        # Verify submitter properties
        self.assertEqual(submission.submitter.access_level, AccessTier.PARTNER)
        self.assertEqual(submission.submitter.sector, "financial")
        self.assertIsNotNone(submission.submitter.organisation_id)
        self.assertTrue(submission.submitter.organisation_id.startswith("identity--"))
              
        # Verify sighting properties
        self.assertEqual(submission.sighting.observation_count, 2)
        self.assertIsNotNone(submission.sighting.sighting_id)
        self.assertTrue(submission.sighting.sighting_id.startswith("sighting--"))
        self.assertIsNotNone(submission.sighting.timestamp)
        
        # Verify observables properties
        self.assertEqual(len(submission.sighting.observables.network), 2)
        self.assertIsInstance(submission.sighting.observables.network[0], Observable)
        self.assertEqual(submission.sighting.observables.network[0].observable_type, ObservableType.IPV4)
        self.assertEqual(submission.sighting.observables.network[0].value, "192.168.1.100")
        self.assertEqual(submission.sighting.observables.network[1].observable_type, ObservableType.DOMAIN)
        self.assertEqual(submission.sighting.observables.network[1].value, "malicious.example.com")
        
        # Verify default values
        self.assertEqual(submission.format_version, __version__)
        self.assertEqual(submission.submission_method, "api")
        self.assertIsNone(submission.processing_notes)

    def test_create_minimal_with_hit_target(self):
        """Test 2: Create a minimal valid Submission with hit_target"""
        submission = Submission(
            submitter=self.valid_submitter,
            sighting=self.valid_sighting_hit_target
        )
        
        # Verify all required components are present
        self.assertIsInstance(submission.submitter, Submitter)
        self.assertIsInstance(submission.sighting, Sighting)
        self.assertIsInstance(submission.sighting.observables, Observables)
        self.assertIsInstance(submission.sighting.hit_target, HitTarget)
        
        
        # # Verify hit_target properties
        self.assertEqual(submission.sighting.hit_target.sector, "healthcare")
        self.assertEqual(submission.sighting.hit_target.organisation_size, "large")
        self.assertIsNone(submission.sighting.hit_target.organisation_id)

    def test_factory_method_create_minimal(self):
        """Test 3: Test the create_minimal factory method functionality"""
        # Test with default parameters
        submission = Submission.create_minimal()
        
        # Verify basic structure
        self.assertIsInstance(submission, Submission)
        self.assertIsInstance(submission.submitter, Submitter)
        self.assertIsInstance(submission.sighting, Sighting)
        self.assertIsInstance(submission.sighting.observables, Observables)
        self.assertIsNone(submission.sighting.hit_target)
        
        # Verify default values from factory method
        self.assertEqual(submission.submitter.access_level, AccessTier.PARTNER)  # Default from factory
        self.assertEqual(len(submission.sighting.observables.network), 2)        # Default IPs from factory
        
        # Verify default threat IPs are created
        expected_ips = ["185.220.102.45", "203.0.113.42"]
        actual_ips = [obs.value for obs in submission.sighting.observables.network]
        self.assertEqual(actual_ips, expected_ips)
        
        # All network observables should have c2 role
        for obs in submission.sighting.observables.network:
            self.assertEqual(obs.role, "c2")
            self.assertEqual(obs.observable_type, ObservableType.IPV4)
        
        # Test with custom parameters
        custom_submission = Submission.create_minimal(
            submitter_access_level=AccessTier.CORE_MEMBER,
            target_sector="technology",
            threat_ips=["198.51.100.1", "203.0.113.50", "192.0.2.100"]
        )
        
        # Verify custom values
        self.assertEqual(custom_submission.submitter.access_level, AccessTier.CORE_MEMBER)
        self.assertEqual(len(custom_submission.sighting.observables.network), 3)
        
        custom_ips = [obs.value for obs in custom_submission.sighting.observables.network]
        expected_custom_ips = ["198.51.100.1", "203.0.113.50", "192.0.2.100"]
        self.assertEqual(custom_ips, expected_custom_ips)

    def test_submission_integrity_validation(self):
        """Test 4: Test cross-field validation ensuring submitter and target are different organisations"""
        # Create submitter and target with different org IDs (should pass)
        valid_submission = Submission(
            submitter=self.valid_submitter,
            sighting=self.valid_sighting_hit_target
        )
        
        # Should be valid - different organisations
        self.assertNotEqual(
            valid_submission.submitter.organisation_id,
            valid_submission.sighting.hit_target.organisation_id
        )
        
        # Create submitter and target with the same org ID (should fail)
        same_org_id = f"identity--{uuid.uuid4()}"
        
        same_org_submitter = Submitter(
            organisation_id=same_org_id,
            access_level=AccessTier.PARTNER,
            sector="financial"
        )


        same_org_target = HitTarget(
            organisation_id=same_org_id,  # Same as submitter - should cause error
            sector="healthcare"
        )

        same_org_sighting = Sighting(
            observables=self.valid_observables,
            hit_target=same_org_target
        )

        # This should raise a ValueError due to model validator
        with self.assertRaises(ValueError) as context:
            Submission(
                submitter=same_org_submitter,
                sighting=same_org_sighting
            )
        
        # Verify the error message mentions the validation rule
        error_str = str(context.exception)
        self.assertIn("Submitter and hit_target cannot be the same organisation", error_str)
   
    def test_multiple_submissions_unique_orgs(self):
        """Test 5: Create multiple submissions and ensure unique submitter and target organisations"""
        # Create multiple submissions
        submissions = []
        for i in range(10):
            submission = Submission.create_minimal(
                submitter_access_level=AccessTier.CONTRIBUTOR,
                target_sector=f"sector_{i}"
            )
            submissions.append(submission)

        # Verify all submitter org IDs are unique across submissions
        submitter_ids = [s.submitter.organisation_id for s in submissions]
        self.assertEqual(len(submitter_ids), len(set(submitter_ids)))

        # Verify all target org IDs are unique across submissions
        target_ids = [s.sighting.hit_target.organisation_id for s in submissions]
        self.assertEqual(len(set(target_ids)), 1)

        # Verify no overlap between submitter and target ID pools
        submitter_id_set = set(submitter_ids)
        target_id_set = set(target_ids)
        self.assertEqual(len(submitter_id_set.intersection(target_id_set)), 0)

class TestSubmissionSerialization(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.valid_network_observables = [
            Observable.create_ipv4("192.168.1.100", role="c2"),
            Observable.create_domain("malicious.example.com", role="phishing")
        ]
        
        self.valid_submitter = Submitter.create(
            organisation_id='identity--' + str(uuid.uuid4()),
            access_level=AccessTier.PARTNER,
            sector="financial"
        )
        
        self.valid_hit_target = HitTarget.create(
            sector="healthcare",
            organisation_size="large"
        )
        
        self.valid_sighting = Sighting.create(
            hit_target=self.valid_hit_target,
            observables=Observables(network=self.valid_network_observables),
            observation_count=2
        )
        
        self.valid_observables = Observables(
            network=self.valid_network_observables
        )

        self.valid_submission = Submission(
            submitter=self.valid_submitter,
            sighting=self.valid_sighting
        )  

    def test_to_yaml(self):
        yaml = self.valid_submission.to_yaml()
        self.assertGreater(len(yaml), 0)

    def test_to_json(self):
        yaml = self.valid_submission.to_json()
        self.assertGreater(len(yaml), 0)

if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)