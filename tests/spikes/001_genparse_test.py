#!/usr/bin/env python3
"""
FRANK Platform - Sighting Parser and Generator
Handles parsing and generation of FRANK sighting submissions in YAML format.
First attempt to create a model bases approach using dataclasses.
"""

import yaml
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class NetworkObservable:
    """Represents a network observable in a FRANK sighting."""
    id: str
    type: str
    value: str
    role: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    first_seen: Optional[str] = None
    connection_count: Optional[int] = None

    @classmethod
    def create_ipv4(cls, value: str, role: str = None, port: int = None) -> 'NetworkObservable':
        """Create an IPv4 observable with STIX-formatted ID."""
        return cls(
            id=f"ipv4-addr-{uuid.uuid4()}",
            type="ipv4",
            value=value,
            role=role,
            port=port
        )

    @classmethod
    def create_domain(cls, value: str, role: str = None) -> 'NetworkObservable':
        """Create a domain observable with STIX-formatted ID."""
        return cls(
            id=f"domain-name-{uuid.uuid4()}",
            type="domain",
            value=value,
            role=role
        )


@dataclass
class Submitter:
    """Represents the submitting organisation (cyber partner)."""
    organisation_id: str
    access_level: str
    organisation_type: Optional[str] = "cyber_partner"
    sector: Optional[str] = None
    region: Optional[str] = None
    submission_method: Optional[str] = "api"
    client_count: Optional[int] = None

    @classmethod
    def create(cls, access_level: str, sector: str = None, region: str = None) -> 'Submitter':
        """Create a submitter with auto-generated STIX ID."""
        return cls(
            organisation_id=f"identity-{uuid.uuid4()}",
            access_level=access_level,
            sector=sector,
            region=region
        )


@dataclass
class HitTarget:
    """Represents the affected customer organisation."""
    organisation_id: str
    sector: str
    organisation_type: Optional[str] = "customer"
    organisation_size: Optional[str] = None
    region: Optional[str] = None
    anonymization_level: Optional[str] = "high"

    @classmethod
    def create(cls, sector: str, organisation_size: str = None, region: str = None) -> 'HitTarget':
        """Create a hit target with auto-generated STIX ID."""
        return cls(
            organisation_id=f"identity-{uuid.uuid4()}",
            sector=sector,
            organisation_size=organisation_size,
            region=region
        )


@dataclass
class Sighting:
    """Represents the core sighting information."""
    sighting_id: str
    timestamp: str
    confidence: int
    first_observed: Optional[str] = None
    last_observed: Optional[str] = None
    observation_count: Optional[int] = 1
    severity: Optional[str] = None

    @classmethod
    def create(cls, confidence: int, severity: str = None, observation_count: int = 1) -> 'Sighting':
        """Create a sighting with auto-generated STIX ID and current timestamp."""
        return cls(
            sighting_id=f"sighting-{uuid.uuid4()}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            confidence=confidence,
            observation_count=observation_count,
            severity=severity
        )


@dataclass
class FrankSubmission:
    """Complete FRANK sighting submission."""
    submitter: Submitter
    hit_target: HitTarget
    sighting: Sighting
    observables: Dict[str, List[NetworkObservable]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert submission to dictionary format."""
        return {
            "submission": {
                "submitter": asdict(self.submitter),
                "hit_target": asdict(self.hit_target),
                "sighting": asdict(self.sighting),
                "observables": {
                    "network": [asdict(obs) for obs in self.observables.get("network", [])]
                }
            }
        }

    def to_yaml(self) -> str:
        """Convert submission to YAML string."""
        data = self.to_dict()
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FrankSubmission':
        """Create FrankSubmission from dictionary."""
        submission_data = data["submission"]
        
        submitter = Submitter(**submission_data["submitter"])
        hit_target = HitTarget(**submission_data["hit_target"])
        sighting = Sighting(**submission_data["sighting"])
        
        observables = {"network": []}
        if "observables" in submission_data and "network" in submission_data["observables"]:
            observables["network"] = [
                NetworkObservable(**obs) for obs in submission_data["observables"]["network"]
            ]
        
        return cls(
            submitter=submitter,
            hit_target=hit_target,
            sighting=sighting,
            observables=observables
        )

    @classmethod
    def from_yaml(cls, yaml_string: str) -> 'FrankSubmission':
        """Create FrankSubmission from YAML string."""
        data = yaml.safe_load(yaml_string)
        return cls.from_dict(data)


class FrankSightingGenerator:
    """Generator for creating FRANK sightings programmatically."""
    
    @staticmethod
    def create_minimal_sighting(
        submitter_access_level: str,
        target_sector: str,
        confidence: int,
        ip_address: str,
        domain: str = None
    ) -> FrankSubmission:
        """Create a minimal FRANK sighting submission."""
        
        submitter = Submitter.create(access_level=submitter_access_level)
        hit_target = HitTarget.create(sector=target_sector)
        sighting = Sighting.create(confidence=confidence)
        
        network_observables = [NetworkObservable.create_ipv4(ip_address)]
        if domain:
            network_observables.append(NetworkObservable.create_domain(domain))
        
        return FrankSubmission(
            submitter=submitter,
            hit_target=hit_target,
            sighting=sighting,
            observables={"network": network_observables}
        )

    @staticmethod
    def create_banking_threat_sighting(
        submitter_access_level: str = "partner",
        confidence: int = 87
    ) -> FrankSubmission:
        """Create a sample banking threat sighting."""
        
        submitter = Submitter.create(
            access_level=submitter_access_level,
            sector="cybersecurity_services",
            region="nl_north_holland"
        )
        
        hit_target = HitTarget.create(
            sector="financial_services",
            organisation_size="medium",
            region="nl_north_holland"
        )
        
        sighting = Sighting.create(
            confidence=confidence,
            severity="high",
            observation_count=23
        )
        
        network_observables = [
            NetworkObservable.create_ipv4(
                value="185.220.102.45",
                role="c2_server",
                port=443
            ),
            NetworkObservable.create_domain(
                value="secure-bank-verify.nl",
                role="phishing_domain"
            )
        ]
        
        return FrankSubmission(
            submitter=submitter,
            hit_target=hit_target,
            sighting=sighting,
            observables={"network": network_observables}
        )


class FrankSightingParser:
    """Parser for processing FRANK sighting submissions."""
    
    @staticmethod
    def validate_submission(submission: FrankSubmission) -> List[str]:
        """Validate a FRANK submission and return list of errors."""
        errors = []
        
        # Validate required fields
        if not submission.submitter.organisation_id:
            errors.append("Submitter organisation_id is required")
        
        if not submission.hit_target.organisation_id:
            errors.append("Hit target organisation_id is required")
        
        if not submission.sighting.sighting_id:
            errors.append("Sighting ID is required")
        
        # Validate confidence range
        if not 0 <= submission.sighting.confidence <= 100:
            errors.append("Confidence must be between 0 and 100")
        
        # Validate tier
        valid_tiers = ["public", "observer", "contributor", "partner", "core_member"]
        if submission.submitter.access_level not in valid_tiers:
            errors.append(f"Invalid access_level: {submission.submitter.access_level}")
        
        # Validate network observables
        if not submission.observables.get("network"):
            errors.append("At least one network observable is required")
        
        for obs in submission.observables.get("network", []):
            if not obs.value:
                errors.append("Network observable value is required")
            if obs.type not in ["ipv4", "ipv6", "domain", "url"]:
                errors.append(f"Invalid network observable type: {obs.type}")
        
        return errors

    @staticmethod
    def extract_iocs(submission: FrankSubmission) -> Dict[str, List[str]]:
        """Extract IoCs from submission for further processing."""
        iocs = {
            "ip_addresses": [],
            "domains": [],
            "urls": []
        }
        
        for obs in submission.observables.get("network", []):
            if obs.type in ["ipv4", "ipv6"]:
                iocs["ip_addresses"].append(obs.value)
            elif obs.type == "domain":
                iocs["domains"].append(obs.value)
            elif obs.type == "url":
                iocs["urls"].append(obs.value)
        
        return iocs

    @staticmethod
    def anonymize_submission(submission: FrankSubmission, access_level: str) -> FrankSubmission:
        """Anonymize submission based on access level."""
        # Create a copy to avoid modifying original
        import copy
        anonymized = copy.deepcopy(submission)
        
        if access_level == "public":
            # Hash all observables for public access
            for obs in anonymized.observables.get("network", []):
                obs.value = f"hash_{hash(obs.value) % 10000:04d}"
        
        elif access_level == "observer":
            # Partial anonymization for observers
            for obs in anonymized.observables.get("network", []):
                if obs.type in ["ipv4", "ipv6"]:
                    parts = obs.value.split(".")
                    if len(parts) == 4:
                        obs.value = f"{parts[0]}.{parts[1]}.x.x"
        
        # Contributors and above get full data
        return anonymized


def test_run_spike():
    # Generate a minimal sighting
    generator = FrankSightingGenerator()
    minimal_sighting = generator.create_minimal_sighting(
        submitter_access_level="partner",
        target_sector="financial_services",
        confidence=87,
        ip_address="185.220.102.45",
        domain="secure-bank-verify.nl"
    )
    
    print("=== Minimal Sighting YAML ===")
    print(minimal_sighting.to_yaml())
    
    # Generate a complete banking threat sighting
    banking_sighting = generator.create_banking_threat_sighting()
    
    print("\n=== Banking Threat Sighting YAML ===")
    print(banking_sighting.to_yaml())
    
    # Parse YAML back to object
    yaml_string = minimal_sighting.to_yaml()
    parsed_sighting = FrankSubmission.from_yaml(yaml_string)
    
    print("\n=== Parsed Sighting (Round-trip test) ===")
    print(f"Submitter Tier: {parsed_sighting.submitter.access_level}")
    print(f"Target Sector: {parsed_sighting.hit_target.sector}")
    print(f"Confidence: {parsed_sighting.sighting.confidence}")
    print(f"Network Observables: {len(parsed_sighting.observables['network'])}")
    
    # Validate submission
    parser = FrankSightingParser()
    errors = parser.validate_submission(parsed_sighting)
    
    print(f"\n=== Validation Results ===")
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"- {error}")
    else:
        print("Submission is valid")
    
    # Extract IoCs
    iocs = parser.extract_iocs(parsed_sighting)
    print(f"\n=== Extracted IoCs ===")
    print(f"IP Addresses: {iocs['ip_addresses']}")
    print(f"Domains: {iocs['domains']}")
    
    # Test anonymization
    anonymized = parser.anonymize_submission(parsed_sighting, "observer")
    print(f"\n=== Anonymized for Observer ===")
    print(anonymized.to_yaml())
    assert True


# Example usage and testing
if __name__ == "__main__":
    test_run_spike()
