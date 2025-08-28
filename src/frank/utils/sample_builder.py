#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides core functionality for generating, parsing, and validating
FRANK threat intelligence submissions following the "be forgiving on what you 
receive and strong on what you return" principle.
"""

import uuid
from typing import Dict, Any, List
import logging
from datetime import datetime, timezone

from frank.core.submission import FRANKSubmission, FRANKValidator
from frank.core.exceptions import FRANKFormatError, FRANKValidationError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_default_observables() -> List[Dict[str, Any]]:
    """
    Generate default sample observables for testing/demo purposes.
    
    Returns:
        List of sample observable dictionaries
    """
    return [
        {
            "id": f"ipv4-addr-{uuid.uuid4()}",
            "type": "ipv4",
            "value": "185.220.102.45"
        },
        {
            "id": f"domain-name-{uuid.uuid4()}",
            "type": "domain", 
            "value": "secure-bank-verify.nl"
        }
    ]
    
def get_sample_malware_observables() -> List[Dict[str, Any]]:
    """Generate sample malware-related observables."""
    return [
        {
            "id": f"file-hash-{uuid.uuid4()}",
            "type": "file_hash",
            "value": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
        },
        {
            "id": f"domain-name-{uuid.uuid4()}",
            "type": "domain",
            "value": "malicious-c2.example.com"
        }
    ]
    
def get_sample_phishing_observables() -> List[Dict[str, Any]]:
    """Generate sample phishing-related observables."""
    return [
        {
            "id": f"url-{uuid.uuid4()}",
            "type": "url",
            "value": "https://fake-bank-login.suspicious.tld/auth"
        },
        {
            "id": f"email-{uuid.uuid4()}",
            "type": "email",
            "value": "noreply@fake-bank.suspicious.tld"
        }
    ]
    
def get_observables_by_category(cls, category: str) -> List[Dict[str, Any]]:
    """
    Get sample observables by category.
    
    Args:
        category: Type of observables ('default', 'malware', 'phishing')
        
    Returns:
        List of appropriate sample observables
    """
    category_map = {
        'default': get_default_observables,
        'malware': get_sample_malware_observables,
        'phishing': get_sample_phishing_observables
    }
    
    generator = category_map.get(category, get_default_observables)
    return generator()

def generate_minimal_submission_dict(org_id: str = None,
                                tier: str = "partner",
                                observables: List[Dict] = None,
                                confidence: int = None) -> Dict[str, Any]:
    """
    Generate a minimal FRANK submission with only required fields.
    
    Args:
        org_id: Organization identifier (generated if None)
        tier: Organization tier level
        observables: List of observable objects (default generated if None)
        confidence: Confidence level 0-100 (uses default if None)
        
    Returns:
        Dict containing minimal valid submission
        
    Raises:
        FRANKValidationError: If invalid values provided
    """
    validator = FRANKValidator()
    
    # Validate inputs
    if tier not in validator.VALID_TIERS:
        raise FRANKValidationError(f"Invalid tier '{tier}'. Must be one of: {validator.VALID_TIERS}")
    
    if confidence is not None and not (0 <= confidence <= 100):
        raise FRANKValidationError(f"Confidence {confidence} out of range [0-100]")
    
    # Generate default values if not provided
    if org_id is None:
        org_id = f"identity-{uuid.uuid4()}"
        
    if observables is None:
        observables = [
            {
                "id": f"ipv4-addr-{uuid.uuid4()}",
                "type": "ipv4",
                "value": "185.220.102.45"
            },
            {
                "id": f"domain-name-{uuid.uuid4()}",
                "type": "domain", 
                "value": "secure-bank-verify.nl"
            }
        ]
    
    # Validate observables
    for obs in observables:
        if 'type' in obs and obs['type'] not in validator.VALID_OBSERVABLE_TYPES:
            raise FRANKValidationError(f"Invalid observable type '{obs['type']}'. Must be one of: {self.VALID_OBSERVABLE_TYPES}")
    
    submission = {
        "submission": {
            "submitter": {
                "organization_id": org_id,
                "tier": tier
            },
            "sighting": {
                "sighting_id": f"sighting-{uuid.uuid4()}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence": confidence if confidence is not None else 65,
                "observables": {
                    "network": observables
                }
            }
        }
    }
    
    logger.info(f"Generated minimal submission for org {org_id}")
    return submission
    
def generate_sample_submission(org_id: str = None, sample_type: str = "default", **kwargs) -> FRANKSubmission:
    """
    Generate a sample FRANKSubmission object for testing/demo purposes.
    """
    sample_dict = generate_minimal_submission_dict(org_id=org_id, observables=get_observables_by_category(None, sample_type), **kwargs)
    return FRANKSubmission(**sample_dict)

