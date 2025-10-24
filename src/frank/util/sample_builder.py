#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides core functionality for generating sample and demo
FRANK threat intelligence submissions.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List

import uuid
from datetime import datetime, timezone

from frank import __version__
from frank.core.enum import AccessTier, ObservableType, TLPLevel
from frank.core.models import Submission
from frank.core.exceptions import FRANKValidationError
from frank.storage.base import BaseFRANKDatabase


class FRANKDatabaseSeeder(ABC):
    """Base class for database seeders."""

    @abstractmethod
    def seed(self, db_client: BaseFRANKDatabase) -> None:
        """Seed the database with initial data."""
        pass 


class SampleDataSeeder(FRANKDatabaseSeeder):
    """Class to generate sample data for testing and demonstration."""

    def seed(self, db_client: BaseFRANKDatabase) -> None:
        """Seed the database with sample data."""

        for org in create_demo_orgs(id_fixed=True):
            db_client.upsert_organisation(org)

        # Create some demo submissions
        for i in range(5):
            demo_submission = generate_minimal_submission(org_id="demo-partner-org", access_level="partner", confidence=70 + i * 5)
            db_client.store_submission(demo_submission)

        return True


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
                                access_level: str = "partner",
                                observables: List[Dict] = None,
                                confidence: int = None) -> Dict[str, Any]:
    """
    Generate a minimal FRANK submission with only required fields.
    
    Args:
        org_id: organisation identifier (generated if None)
        access_level: organisation tier level
        observables: List of observable objects (default generated if None)
        confidence: Confidence level 0-100 (uses default if None)
        
    Returns:
        Dict containing minimal valid submission
        
    Raises:
        FRANKValidationError: If invalid values provided
    """ 
    # Validate inputs
    all_access_levels = [level.value for level in AccessTier]
    if access_level not in all_access_levels:
        raise FRANKValidationError(f"Invalid access level '{access_level}'. Must be one of: {all_access_levels}")

    if confidence is not None and not (0 <= confidence <= 100):
        raise FRANKValidationError(f"Confidence {confidence} out of range [0-100]")
    
    # Generate default values if not provided
    if org_id is None:
        org_id = f"identity--{uuid.uuid4()}"
        
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
                "organisation_id": org_id,
                "access_level": access_level,
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
    

def generate_minimal_submission(org_id: str = None, access_level: str = "partner", observables: list = None, confidence: int = None) -> Submission:
    """
    Generate a minimal Submission instance with only required fields.

    Args:
        org_id: organisation identifier (generated if None)
        access_level: organisation tier level
        observables: List of observable objects (default generated if None)
        confidence: Confidence level 0-100 (uses default if None)

    Returns:
        Submission instance containing minimal valid submission
    """
    submission_dict = generate_minimal_submission_dict(org_id=org_id, access_level=access_level, observables=observables, confidence=confidence)
    return Submission(**submission_dict["submission"])


def generate_sample_submission(org_id: str = None, sample_type: str = "default", **kwargs) -> Submission:
    """
    Generate a sample FRANKSubmission object for testing or demonstration purposes.

    Args:
        org_id (str, optional): organisation identifier. If None, a STIX-style UUID is generated.
        sample_type (str, optional): Type of sample observables to include. One of 'default', 'malware', 'phishing'.
        **kwargs: Additional parameters passed to generate_minimal_submission_dict (e.g., tier, confidence).

    Returns:
        FRANKSubmission: Instance containing a sample valid submission.

    """
    sample_dict = generate_minimal_submission_dict(org_id=org_id, observables=get_observables_by_category(None, sample_type), **kwargs)
    return Submission(**sample_dict["submission"])

def generate_comprehensive_submission(
    org_id: str = None,
    access_level: str = "partner",
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
        org_id (str, optional): organisation identifier. If None, a STIX-style UUID is generated.
        tier (str, optional): organisation tier level. Defaults to "partner".
        hit_target_org (str, optional): organisation ID of the target (if applicable).
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
        org_id = f"identity--{uuid.uuid4()}"
    if observables is None:
        observables = get_default_observables()
    now = datetime.now(timezone.utc)
    submission = {
        "submission_id": f"submission--{uuid.uuid4()}",
        "format_version": __version__,
        "submission_method": "api",
        "processing_nodes": "comprehensive message for testing",
        "submitter": {
            "organisation_id": org_id,
            "access_level": access_level,
        },
        "sighting": {
            "sighting_id": f"sighting--{uuid.uuid4()}",
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
        submission["sighting"]["hit_target"] = {
            "organisation_id": hit_target_org, 
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


def create_demo_orgs(id_fixed: bool = True) -> List[Dict[str, Any]]:
    """
    Create a list of sample organisations for demonstration or testing purposes.

    Returns:
        List of organisation instances with sample data.
    """
    orgs = [
        {
            "organisation_id": "demo-observer-org" if id_fixed else f"identity--{uuid.uuid4()}",
            "access_level": "observer",
            "sector": "finance",
            "region": "europe"
        },
        {
            "organisation_id": "demo-partner-org" if id_fixed else f"identity--{uuid.uuid4()}",
            "access_level": "partner",
            "sector": "cybersecurity_services",
            "region": "nl"
        },
        {
            "organisation_id": "demo-contributor-org" if id_fixed else f"identity--{uuid.uuid4()}",
            "access_level": "contributur",
            "sector": "healthcare",
            "region": "north_america"
        },
        {
            "organisation_id": "demo-core_member-org" if id_fixed else f"identity--{uuid.uuid4()}",
            "access_level": "core_member",
            "sector": "government",
            "region": "asia_pacific"
        },
        {
            "organisation_id": "demo-main-org" if id_fixed else f"identity--{uuid.uuid4()}",
            "access_level": "core_member",
            "sector": "government",
            "region": "asia_pacific"
        }
    ]
    return orgs


# Example usage and testing functions
def example_usage():
    """Demonstrate Pydantic model usage"""
    
    print("=== FRANK Pydantic Models Sample Generator (v2 Compatible) ===\n")
    
    # 1. Create minimal submission using factory method
    print("1. Creating minimal submission...")
    minimal = generate_minimal_submission(
        org_id=f"identity--{uuid.uuid4()}",
        access_level="partner"
    )
    print("✓ Minimal submission created")

    # 2. Create sample submission
    print("2. Creating sample submission...")
    sample = generate_sample_submission(
        org_id=f"identity--{uuid.uuid4()}",
        sample_type="malware",
        access_level="partner"
    )
    print("✓ Sample submission created")

    # 3. Create comprehensive submission
    print("3. Creating comprehensive submission...")
    comprehensive = generate_comprehensive_submission(
        org_id=f"identity--{uuid.uuid4()}",
        access_level="partner",
        hit_target_org=f"identity--{uuid.uuid4()}",
        observables=get_default_observables(),
        campaign_context={"name": "test_campaign", "actor": "test_actor"},
        sigma_detection={"rule_id": "test-rule-123", "rule_name": "sigma_rule-12", "confidence": 0.95},
        impact_data={"severity": "high", "affected_systems": 5},
        tlp_level=TLPLevel.AMBER_PLUS
    )
    print("✓ Comprehensive submission created")

    # 4. Demo organisations
    print("4. Creating demo organisations...")
    demo_orgs = create_demo_orgs()
    print(f"✓ {len(demo_orgs)} demo organisations created")  

    # 5. Database seeding example (pseudo-code, requires actual db client)
    print("5. (Pseudo) Seeding database with sample data...")
    # db_client = YourDatabaseClient(...)  # Replace with actual database client initialization
    # client = FRANKClient(db_client)  # Replace with actual database client
    # seeder = SampleDataSeeder()
    # client.seed_database(seeder)
    print("✓ Database seeded with sample data (pseudo-code)")        