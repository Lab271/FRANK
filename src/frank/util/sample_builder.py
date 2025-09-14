#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides core functionality for generating, parsing, and validating
FRANK threat intelligence submissions following the "be forgiving on what you 
receive and strong on what you return" principle.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import uuid
from typing import Dict, Any, List
from datetime import datetime, timezone

from frank import __version__
from frank.core.enum import TierLevel, ObservableType
from frank.core.models import Submission
from frank.core.exceptions import FRANKValidationError


def get_default_observables() -> List[Dict[str, Any]]:
    """
    Generate default sample observables for testing/demo purposes.
    
    Returns:
        List of sample observable dictionaries
    """
    return [
        {
            "id": f"ipv4--{uuid.uuid4()}",
            "type": "ipv4",
            "value": "185.220.102.45"
        },
        {
            "id": f"domain--{uuid.uuid4()}",
            "type": "domain", 
            "value": "secure-bank-verify.nl"
        }
    ]
    
def get_sample_malware_observables() -> List[Dict[str, Any]]:
    """Generate sample malware-related observables."""
    return [
        {
            "id": f"file_hash--{uuid.uuid4()}",
            "type": "file_hash",
            "value": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
        },
        {
            "id": f"domain--{uuid.uuid4()}",
            "type": "domain",
            "value": "malicious-c2.example.com"
        }
    ]
    
def get_sample_phishing_observables() -> List[Dict[str, Any]]:
    """Generate sample phishing-related observables."""
    return [
        {
            "id": f"url--{uuid.uuid4()}",
            "type": "url",
            "value": "https://fake-bank-login.suspicious.tld/auth"
        },
        {
            "id": f"email--{uuid.uuid4()}",
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
    # Validate inputs
    all_tiers = [level.value for level in TierLevel]
    if tier not in all_tiers:
        raise FRANKValidationError(f"Invalid tier '{tier}'. Must be one of: {all_tiers}")
    
    if confidence is not None and not (0 <= confidence <= 100):
        raise FRANKValidationError(f"Confidence {confidence} out of range [0-100]")
    
    # Generate default values if not provided
    if org_id is None:
        org_id = f"identity-{uuid.uuid4()}"
        
    if observables is None:
        observables = [
            {
                "id": f"ipv4--{uuid.uuid4()}",
                "type": "ipv4",
                "value": "185.220.102.45"
            },
            {
                "id": f"domain--{uuid.uuid4()}",
                "type": "domain", 
                "value": "secure-bank-verify.nl"
            }
        ]
    
    # Validate observables
    all_observable_types = [obs.value for obs in ObservableType]
    for obs in observables:
        if 'type' in obs and obs['type'] not in all_observable_types:
            raise FRANKValidationError(f"Invalid observable type '{obs['type']}'. Must be one of: {all_observable_types}")

    submission = {
        "submission": {
            "submitter": {
                "organization_id": org_id,
                "tier": tier
            },
            "sighting": {
                "sighting_id": f"sighting-{uuid.uuid4()}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence": confidence if confidence is not None else 69,
                "observables": {
                    "network": observables
                }
            }
        }
    }
    
    return submission
    

def generate_minimal_submission(org_id: str = None, tier: str = "partner", observables: list = None, confidence: int = None) -> Submission:
    """
    Generate a minimal Submission instance with only required fields.

    Args:
        org_id: Organization identifier (generated if None)
        tier: Organization tier level
        observables: List of observable objects (default generated if None)
        confidence: Confidence level 0-100 (uses default if None)

    Returns:
        Submission instance containing minimal valid submission
    """
    submission_dict = generate_minimal_submission_dict(org_id=org_id, tier=tier, observables=observables, confidence=confidence)
    return Submission(**submission_dict["submission"])


def generate_sample_submission(org_id: str = None, sample_type: str = "default", **kwargs) -> Submission:
    """
    Generate a sample FRANKSubmission object for testing or demonstration purposes.

    Args:
        org_id (str, optional): Organization identifier. If None, a STIX-style UUID is generated.
        sample_type (str, optional): Type of sample observables to include. One of 'default', 'malware', 'phishing'.
        **kwargs: Additional parameters passed to generate_minimal_submission_dict (e.g., tier, confidence).

    Returns:
        FRANKSubmission: Instance containing a sample valid submission.

    """
    sample_dict = generate_minimal_submission_dict(org_id=org_id, observables=get_observables_by_category(None, sample_type), **kwargs)
    return Submission(**sample_dict["submission"])

def generate_comprehensive_submission(
    org_id: str = None,
    tier: str = "partner",
    hit_target_org: str = None,
    sector: str = None,
    observables: list = None,
    severity: str = "high",
    confidence: int = 92,
    campaign_context: dict = None,
    sigma_detection: dict = None,
    impact_data: dict = None,
    tlp_level: str = None
) -> Submission:
    """
    Generate a comprehensive Submission instance with all major fields populated.

    Args:
        org_id (str, optional): Organization identifier. If None, a STIX-style UUID is generated.
        tier (str, optional): Organization tier level. Defaults to "partner".
        hit_target_org (str, optional): Organization ID of the target (if applicable).
        observables (list, optional): List of observable objects. If None, default observables are generated.
        severity (str, optional): Sighting severity. Defaults to "high".
        confidence (int, optional): Confidence level 0-100. Defaults to 92.
        campaign_context (dict, optional): Dictionary with campaign/actor context.
        sigma_detection (dict, optional): Dictionary with sigma rule detection info.
        impact_data (dict, optional): Dictionary with impact/severity/affected systems.
        tlp_level (str, optional): Dictionary with sharing preferences.

    Returns:
        Submission instance containing a comprehensive valid submission
    """
    if org_id is None:
        org_id = f"identity-{uuid.uuid4()}"
    if observables is None:
        observables = get_default_observables()
    now = datetime.now(timezone.utc)
    submission = {
        "submission_id": f"submission-{uuid.uuid4()}",
        "format_version": __version__,
        "submission_method": "api",
        "processing_nodes": "comprehensive message for testing",
        "submitter": {
            "organization_id": org_id,
            "tier": tier
        },
        "sighting": {
            "sighting_id": f"sighting-{uuid.uuid4()}",
            "timestamp": now.isoformat(),
            "first_observed": (now.replace(hour=0, minute=0, second=0, microsecond=0)).isoformat(),
            "last_observed": now.isoformat(),
            "confidence": confidence,
            "severity": severity,
            "observables": {
                "network": observables
            }
        },

    }
    if hit_target_org:
        submission["hit_target"] = {
            "organization_id": hit_target_org, 
            "sector": sector or "finance",
            "region": "europe",
            "anonymization_level": "low"
        }

    if tlp_level:
        submission["tlp_level"] = tlp_level
    if sigma_detection:
        submission["sighting"]["sigma_detection"] = sigma_detection
    if campaign_context:
        submission["sighting"]["threat_context"] = {'campaign': campaign_context}
    if impact_data:
        submission["sighting"]["impact"] = impact_data
    return Submission(**submission)

# Example usage and testing functions
def example_usage():
    """Demonstrate Pydantic model usage"""
    
    print("=== FRANK Pydantic Models Sample Generator (v2 Compatible) ===\n")
    
    # 1. Create minimal submission using factory method
    print("1. Creating minimal submission...")
    minimal = generate_minimal_submission(
        org_id=f"identity--{uuid.uuid4()}",
        tier="partner"
    )
    print("✓ Minimal submission created")

    # 2. Create sample submission
    print("2. Creating sample submission...")
    sample = generate_sample_submission(
        org_id=f"identity--{uuid.uuid4()}",
        sample_type="malware",
        tier="partner",
        confidence=80
    )
    print("✓ Sample submission created")

    # 3. Create comprehensive submission
    print("3. Creating comprehensive submission...")
    comprehensive = generate_comprehensive_submission(
        org_id=f"identity--{uuid.uuid4()}",
        tier="partner",
        hit_target_org=f"identity--{uuid.uuid4()}",
        observables=get_default_observables(),
        severity="high",
        confidence=95,
        campaign_context={"name": "test_campaign", "actor": "test_actor"},
        sigma_detection={"rule_id": "test-rule-123", "rule_name": "sigma_rule-12", "confidence": 0.95},
        impact_data={"severity": "high", "affected_systems": 5},
        tlp_level="TLP:AMBER"
    )
    print("✓ Comprehensive submission created")

    
if __name__ == "__main__":
    example_usage()