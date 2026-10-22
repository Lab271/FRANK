#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)

Unit tests for sample builders

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest
import uuid
from datetime import datetime, timezone

from pydantic import ValidationError

from frank.core.exceptions import FRANKValidationError
from frank.core.models import Submission
from frank.util import sample_builder
from frank.util.sample_builder import generate_minimal_submission


def stix_uuid(object_type: str) -> str:
    """Generate a STIX-compliant UUID for a given object type."""
    return f"{object_type}--{uuid.uuid4()}"



class TestSubmission(unittest.TestCase):
    def setUp(self):
        """Set up default variables for tests using STIX UUID format."""
        self.valid_org_id = stix_uuid("identity")
        self.valid_access_level = "partner"
        self.valid_observables = [
            {
                "id": stix_uuid("ipv4-addr"),
                "type": "ipv4",
                "value": "185.220.102.45"
            },
            {
                "id": stix_uuid("domain-name"),
                "type": "domain",
                "value": "secure-bank-verify.nl"
            }
        ]

    def test_generate_minimal_submission_defaults(self):
        """Test generating minimal submission with default values."""
        submission = generate_minimal_submission().model_dump()

        # Check structure
        self.assertIn('submitter', submission)
        self.assertIn('sighting', submission)

        # Check required fields
        submitter = submission['submitter']
        self.assertIn('organisation_id', submitter)
        self.assertEqual(submitter['access_level'], 'partner')  # default

        sighting = submission['sighting']
        self.assertIn('sighting_id', sighting)
        self.assertIn('timestamp', sighting)
        self.assertEqual(sighting['confidence'], 69)  # default
        self.assertIn('observables', sighting)

        # Check observables structure
        observables = sighting['observables']
        self.assertIn('network', observables)
        self.assertIsInstance(observables['network'], list)
        self.assertEqual(len(observables['network']), 2)  # default IP and domain

    def test_generate_minimal_submission_custom_params(self):
        """Test generating minimal submission with custom parameters."""
        submission = generate_minimal_submission(
            org_id=self.valid_org_id,
            access_level=self.valid_access_level,
            observables=self.valid_observables,
            confidence=85
        ).model_dump()

        submitter = submission['submitter']
        self.assertEqual(submitter['organisation_id'], self.valid_org_id)
        self.assertEqual(submitter['access_level'], self.valid_access_level)

        sighting = submission['sighting']
        self.assertEqual(sighting['confidence'], 85)
        self.assertEqual(len(sighting['observables']['network']), 2)

    def test_generate_minimal_submission_invalid_access_level(self):
        """Test generating submission with invalid access_level raises exception."""
        with self.assertRaises(FRANKValidationError) as context:
            generate_minimal_submission(access_level="invalid_access_level")

        self.assertIn("Invalid access level", str(context.exception))

    def test_generate_minimal_submission_invalid_confidence(self):
        """Test generating submission with invalid confidence raises exception."""
        with self.assertRaises(FRANKValidationError):
            generate_minimal_submission(confidence=150)

        with self.assertRaises(FRANKValidationError):
            generate_minimal_submission(confidence=-10)

    def test_generate_minimal_submission_invalid_observable_type(self):
        """Test generating submission with invalid observable type raises exception."""
        invalid_observables = [
            {
                "id": "test-invalid-1",
                "type": "invalid_type",
                "value": "some_value"
            }
        ]

        with self.assertRaises(FRANKValidationError) as context:
            generate_minimal_submission(observables=invalid_observables)

        self.assertIn("Invalid observable type", str(context.exception))

    def test_get_observables_by_category(self):
        """Test get_observables_by_category returns correct types."""
        from frank.util.sample_builder import get_observables_by_category
        default_obs = get_observables_by_category(None, 'default')
        malware_obs = get_observables_by_category(None, 'malware')
        phishing_obs = get_observables_by_category(None, 'phishing')
        self.assertTrue(any(obs['type'] == 'ipv4' for obs in default_obs))
        self.assertTrue(any(obs['type'] == 'file_hash' for obs in malware_obs))
        self.assertTrue(any(obs['type'] == 'url' for obs in phishing_obs))

    def test_generate_comprehensive_submission_dict(self):
        """Test generating comprehensive submission with all parameters."""
        from frank.util.sample_builder import generate_minimal_submission_dict
        # Simulate comprehensive submission using minimal dict and extra fields
        org_id = self.valid_org_id
        access_level = self.valid_access_level
        observables = self.valid_observables
        campaign_context = {"name": "test_campaign", "actor": "test_actor"}
        sigma_detection = {"rule_id": "test-rule-123", "rule_name": "sigma_rule", "confidence": 0.95}
        impact_data = {"severity": "high", "affected_systems": 5}
        tlp_level = "TLP:AMBER"
        submission_dict = generate_minimal_submission_dict(
            org_id=org_id,
            access_level=access_level,
            observables=observables,
            confidence=92
        )
        submission_dict['submission']['tlp_level'] = tlp_level
        submission_dict['submission']['submission_id'] = 'submission-123'
        submission_dict['submission']['format_version'] = '1.0'

        # Add comprehensive fields manually
        sighting = submission_dict['submission']['sighting']
        sighting['severity'] = 'high'
        sighting['first_observed'] = '2025-09-11T00:00:00Z'
        sighting['last_observed'] = '2025-09-11T12:00:00Z'
        sighting['sigma_detection'] = sigma_detection
        sighting['threat_context'] = campaign_context
        sighting['impact'] = impact_data

        submission = Submission(**submission_dict['submission'])

        # Check enhanced sighting using Pydantic model properties
        self.assertEqual(submission.sighting.severity, 'high')
        self.assertEqual(submission.sighting.first_observed, datetime(2025, 9, 11, 0, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(submission.sighting.last_observed, datetime(2025, 9, 11, 12, 0, 0, tzinfo=timezone.utc))
        self.assertIsNotNone(submission.sighting.sigma_detection)
        self.assertIsNotNone(submission.sighting.threat_context)
        self.assertIsNotNone(submission.sighting.impact)

        # Check sharing preferences
        self.assertEqual(submission.tlp_level, tlp_level)
        # Check metadata
        self.assertEqual(submission.submission_id, 'submission-123')
        self.assertEqual(submission.format_version, '1.0')




class TestSampleBuilderComprehensive(unittest.TestCase):
    def test_generate_sample_submission(self):
        """Test generate_sample_submission returns valid Submission object."""
        submission = sample_builder.generate_sample_submission()
        self.assertIsInstance(submission, Submission)
        self.assertIsNotNone(getattr(submission, "sighting", None))
        self.assertIsNotNone(getattr(submission, "submitter", None))
        sighting = getattr(submission, "sighting", None)
        self.assertTrue(sighting is not None and hasattr(sighting, "observables"))

    def test_generate_comprehensive_submission_minimal_required(self):
        """Test generate_comprehensive_submission with minimal required args."""
        org_id = stix_uuid("identity")
        hit_target_org = stix_uuid("identity")
        observables = sample_builder.get_default_observables()
        submission = sample_builder.generate_comprehensive_submission(
            org_id=org_id,
            access_level="partner",
            hit_target_org=hit_target_org,
            observables=observables,
            severity="medium",
            confidence=80
        )
        self.assertIsInstance(submission, Submission)
        submitter = getattr(submission, "submitter", None)
        self.assertIsNotNone(submitter)
        self.assertEqual(getattr(submitter, "organisation_id", None), org_id)
        sighting = getattr(submission, "sighting", None)
        self.assertIsNotNone(sighting)
        self.assertEqual(getattr(sighting, "severity", None), "medium")
        self.assertEqual(getattr(sighting, "confidence", None), 80)

    def test_generate_comprehensive_submission_missing_optional(self):
        """Test generate_comprehensive_submission with missing optional fields."""
        org_id = stix_uuid("identity")
        observables = sample_builder.get_default_observables()
        submission = sample_builder.generate_comprehensive_submission(
            org_id=org_id,
            access_level="partner",
            observables=observables,
            severity="low",
            confidence=50
        )
        self.assertIsInstance(submission, Submission)
        sighting = getattr(submission, "sighting", None)
        self.assertIsNotNone(sighting)
        self.assertEqual(getattr(sighting, "severity", None), "low")
        self.assertEqual(getattr(sighting, "confidence", None), 50)
        # Optional fields should be None or default
        tc = getattr(sighting, "threat_context", None)
        self.assertTrue(tc is None or hasattr(tc, "campaign"))

    def test_generate_comprehensive_submission_org_id(self):
        """Test generate_comprehensive_submission with no org_id generates alternative."""
        submission = sample_builder.generate_comprehensive_submission(
            org_id=None,
        )
        self.assertIsNotNone(submission.submitter.organisation_id)
        self.assertTrue(submission.submitter.organisation_id.startswith("identity--"))
        self.assertIsInstance(uuid.UUID(submission.submitter.organisation_id.split("--")[1]), uuid.UUID)

    def test_generate_comprehensive_submission_invalid_confidence(self):
        """Test generate_comprehensive_submission with invalid confidence raises exception."""
        org_id = stix_uuid("identity")
        with self.assertRaises(ValidationError):
            sample_builder.generate_comprehensive_submission(
                org_id=org_id,
                access_level="partner",
                severity="medium",
                confidence=150  # Invalid confidence
            )

    def test_example_usage_runs_without_error(self):
        """Test that example_usage runs"""
        try:
            _ = sample_builder.example_usage()
        except Exception as e:
            self.fail(f"example_usage() raised an exception: {e}")

    def test_generate_comprehensive_submission(self):
        """Test generating comprehensive submission using the function and check model properties."""
        from frank.util.sample_builder import generate_comprehensive_submission, get_default_observables
        org_id = stix_uuid("identity")
        hit_target_org = stix_uuid("identity")
        observables = get_default_observables()
        campaign_context = {"name": "test_campaign", "actor": "test_actor"}
        sigma_detection = {"rule_id": "test-rule-123", "rule_name": "sigma_rule-12", "confidence": 0.95}
        impact_data = {"financial_impact_eur": 10000000, "affected_systems": 5}
        tlp_level = "TLP:AMBER"
        submission = generate_comprehensive_submission(
            org_id=org_id,
            access_level="partner",
            hit_target_org=hit_target_org,
            observables=observables,
            severity="high",
            confidence=95,
            campaign_context=campaign_context,
            sigma_detection=sigma_detection,
            impact_data=impact_data,
            tlp_level=tlp_level
        )
        # Check model properties
        self.assertEqual(submission.submitter.organisation_id, org_id)
        self.assertEqual(submission.sighting.severity, "high")
        self.assertEqual(submission.sighting.confidence, 95)
        self.assertIsNotNone(submission.sighting.sigma_detection)
        self.assertIsNotNone(submission.sighting.threat_context)
        self.assertIsNotNone(submission.sighting.impact)
        self.assertEqual(submission.sighting.threat_context.campaign.name, campaign_context['name'])
        self.assertEqual(submission.sighting.sigma_detection.rule_id, sigma_detection['rule_id'])
        self.assertEqual(submission.sighting.impact.financial_impact_eur, impact_data['financial_impact_eur'])
        self.assertEqual(submission.tlp_level, tlp_level)
        # Robust check for hit_target
        self.assertIsNotNone(submission.hit_target)
        if submission.hit_target:
            self.assertEqual(submission.hit_target.organisation_id, hit_target_org)

class TestSampleBuilderAdditional(unittest.TestCase):

    def test_generate_sample_submission(self):
        """Test generate_sample_submission returns valid Submission object."""
        submission = sample_builder.generate_sample_submission()
        self.assertIsInstance(submission, Submission)
        self.assertIsNotNone(getattr(submission, "sighting", None))
        self.assertIsNotNone(getattr(submission, "submitter", None))
        sighting = getattr(submission, "sighting", None)
        self.assertTrue(sighting is not None and hasattr(sighting, "observables"))

    def test_generate_comprehensive_submission_minimal_required(self):
        """Test generate_comprehensive_submission with minimal required args."""
        org_id = stix_uuid("identity")
        hit_target_org = stix_uuid("identity")
        observables = sample_builder.get_default_observables()
        submission = sample_builder.generate_comprehensive_submission(
            org_id=org_id,
            access_level="partner",
            hit_target_org=hit_target_org,
            observables=observables,
            severity="medium",
            confidence=80
        )
        self.assertIsInstance(submission, Submission)
        self.assertEqual(submission.submitter.organisation_id, org_id)
        self.assertEqual(submission.sighting.severity, "medium")
        self.assertEqual(submission.sighting.confidence, 80)

    def test_generate_comprehensive_submission_missing_optional(self):
        """Test generate_comprehensive_submission with missing optional fields."""
        org_id = stix_uuid("identity")
        observables = sample_builder.get_default_observables()
        submission = sample_builder.generate_comprehensive_submission(
            org_id=org_id,
            access_level="partner",
            observables=observables,
            severity="low",
            confidence=50
        )
        self.assertIsInstance(submission, Submission)
        self.assertEqual(submission.sighting.severity, "low")
        self.assertEqual(submission.sighting.confidence, 50)
        # Optional fields should be None or default
        self.assertTrue(submission.sighting.threat_context is None or hasattr(submission.sighting.threat_context, "campaign"))

class TestSampleBuilderCoverage(unittest.TestCase):
    """Unit tests for sample_builder utility functions and classes."""

    def test_FRANKDatabaseSeeder_abstract(self):
        """Test abstract class cannot be instantiated."""
        # Should not instantiate directly
        with self.assertRaises(TypeError):
            sample_builder.FRANKDatabaseSeeder()

    def test_SampleDataSeeder_seed(self):
        """Test seeding with SampleDataSeeder and dummy DB client."""
        class DummyDBClient:
            def __init__(self):
                self.orgs = []
                self.submissions = []
            def upsert_organisation(self, org):
                self.orgs.append(org)
            def store_submission(self, sub):
                self.submissions.append(sub)
        seeder = sample_builder.SampleDataSeeder()
        db_client = DummyDBClient()
        result = seeder.seed(db_client)
        self.assertTrue(result)
        self.assertGreaterEqual(len(db_client.orgs), 1)
        self.assertEqual(len(db_client.submissions), 5)
        self.assertIsInstance(db_client.submissions[0], Submission)

    def test_get_default_observables(self):
        """Test retrieval of default observables."""
        obs = sample_builder.get_default_observables()
        self.assertIsInstance(obs, list)
        self.assertTrue(any(o['type'] == 'ipv4' for o in obs))
        self.assertTrue(any(o['type'] == 'domain' for o in obs))

    def test_get_sample_malware_observables(self):
        """Test retrieval of sample malware observables."""
        obs = sample_builder.get_sample_malware_observables()
        self.assertTrue(any(o['type'] == 'file_hash' for o in obs))
        self.assertTrue(any(o['type'] == 'domain' for o in obs))

    def test_get_sample_phishing_observables(self):
        """Test retrieval of sample phishing observables."""
        obs = sample_builder.get_sample_phishing_observables()
        self.assertTrue(any(o['type'] == 'url' for o in obs))
        self.assertTrue(any(o['type'] == 'email' for o in obs))

    def test_get_observables_by_category_default(self):
        """Test observables by 'default' category."""
        obs = sample_builder.get_observables_by_category(None, 'default')
        self.assertTrue(any(o['type'] == 'ipv4' for o in obs))

    def test_get_observables_by_category_malware(self):
        """Test observables by 'malware' category."""
        obs = sample_builder.get_observables_by_category(None, 'malware')
        self.assertTrue(any(o['type'] == 'file_hash' for o in obs))

    def test_get_observables_by_category_phishing(self):
        """Test observables by 'phishing' category."""
        obs = sample_builder.get_observables_by_category(None, 'phishing')
        self.assertTrue(any(o['type'] == 'url' for o in obs))

    def test_get_observables_by_category_unknown(self):
        """Test observables by unknown category falls back to default."""
        obs = sample_builder.get_observables_by_category(None, 'unknown')
        self.assertTrue(any(o['type'] == 'ipv4' for o in obs))

    def test_create_demo_orgs(self):
        """Test creation of demo organisations with fixed and random IDs."""
        orgs = sample_builder.create_demo_orgs(id_fixed=True)
        self.assertIsInstance(orgs, list)
        self.assertTrue(any('organisation_id' in o for o in orgs))
        orgs2 = sample_builder.create_demo_orgs(id_fixed=False)
        self.assertNotEqual(orgs[0]['organisation_id'], orgs2[0]['organisation_id'])

    def test_example_usage(self):
        """Test example usage runs without exceptions."""
        # Just run to ensure no exceptions
        sample_builder.example_usage()


if __name__ == "__main__":
    unittest.main(verbosity=2, buffer=True)
