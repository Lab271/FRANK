import unittest

from frank.utils.sample_builder import generate_minimal_submission
from frank.core.exceptions import FRANKValidationError

import uuid

def stix_uuid(object_type: str) -> str:
    """Generate a STIX-compliant UUID for a given object type."""
    return f"{object_type}--{uuid.uuid4()}"

class TestFRANKSubmission(unittest.TestCase):
    
    def setUp(self):
        """Set up default variables for tests using STIX UUID format."""
        self.valid_org_id = stix_uuid("identity")
        self.valid_tier = "partner"
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
        self.assertIn('organization_id', submitter)
        self.assertEqual(submitter['tier'], 'partner')  # default
        
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
            tier=self.valid_tier,
            observables=self.valid_observables,
            confidence=85
        ).model_dump()
        
        submitter = submission['submitter']
        self.assertEqual(submitter['organization_id'], self.valid_org_id)
        self.assertEqual(submitter['tier'], self.valid_tier)
        
        sighting = submission['sighting']
        self.assertEqual(sighting['confidence'], 85)
        self.assertEqual(len(sighting['observables']['network']), 2)
    
    def test_generate_minimal_submission_invalid_tier(self):
        """Test generating submission with invalid tier raises exception."""
        with self.assertRaises(FRANKValidationError) as context:
            generate_minimal_submission(tier="invalid_tier")
        
        self.assertIn("Invalid tier", str(context.exception))
    
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

    # def test_generate_comprehensive_submission(self):
    #     """Test generating comprehensive submission with all parameters."""
    #     campaign_context = {"name": "test_campaign", "actor": "test_actor"}
    #     sigma_detection = {"rule_id": "test-rule-123", "confidence": 0.95}
    #     impact_data = {"severity": "high", "affected_systems": 5}
    #     sharing = {"distribution_level": "TLP:AMBER", "anonymization_level": "moderate"}

    #     submission = generate_comprehensive_submission(
    #         org_id=self.valid_org_id,
    #         tier=self.valid_tier,
    #         hit_target_org="target-org-456",
    #         observables=self.valid_observables,
    #         severity="high",
    #         confidence=92,
    #         campaign_context=campaign_context,
    #         sigma_detection=sigma_detection,
    #         impact_data=impact_data,
    #         sharing=sharing
    #     ).to_dict()

    #     # Check metadata
    #     self.assertIn('metadata', submission['submission'])
    #     metadata = submission['submission']['metadata']
    #     self.assertIn('submission_id', metadata)
    #     self.assertIn('format_version', metadata)

    #     # Check hit target
    #     self.assertIn('hit_target', submission['submission'])
    #     hit_target = submission['submission']['hit_target']
    #     self.assertEqual(hit_target['organization_id'], "target-org-456")

    #     # Check enhanced sighting
    #     sighting = submission['submission']['sighting']
    #     self.assertEqual(sighting['severity'], "high")
    #     self.assertIn('first_observed', sighting)
    #     self.assertIn('last_observed', sighting)
    #     self.assertIn('sigma_detection', sighting)
    #     self.assertIn('threat_context', sighting)
    #     self.assertIn('impact', sighting)

    #     # Check sharing preferences
    #     self.assertIn('sharing', submission['submission'])
    #     sharing = submission['submission']['sharing']
    #     self.assertIn('distribution_level', sharing)
    #     self.assertIn('anonymization_level', sharing)

if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)