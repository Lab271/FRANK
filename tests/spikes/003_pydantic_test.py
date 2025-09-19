#!/usr/bin/env python3
"""
FRANK Platform - Sighting Parser and Generator
Handles parsing and generation of FRANK sighting submissions in YAML format.
Second attemtpt using Pydantic models (v2 compatible).
"""

import yaml
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ================================
# PYDANTIC MODELS (Based on your existing SQLite models)
# ================================

class Observable(BaseModel):
    """Observable model based on examples/minimal_submission.yaml"""
    id: str = Field(default_factory=lambda: f"observable--{uuid.uuid4()}")
    observable_type: str = Field(..., alias="type", description="Observable type")
    value: str = Field(..., description="Observable value")
    role: Optional[str] = Field(None, description="Role in attack (C2, exfiltration, etc)")
    port: Optional[int] = Field(None, ge=1, le=65535, description="Network port")

    @field_validator('observable_type', mode='before')
    def validate_type(cls, v):
        allowed_types = ['ipv4', 'ipv6', 'domain', 'url', 'file_hash', 'email', 'registry_key']
        if v not in allowed_types:
            raise ValueError(f'Observable type must be one of: {allowed_types}')
        return v

    @model_validator(mode='after')
    def ensure_id_generated(self):
        """Ensure ID is always generated after all fields are set"""
        if not self.id:
            self.id = f"{self.observable_type}--{uuid.uuid4()}"
        return self

    @classmethod
    def create_ipv4(cls, value: str, role: str = None, port: int = None):
        """Factory method for IPv4 observables"""
        return cls(
            type='ipv4',
            value=value,
            role=role,
            port=port
        )
    
    @classmethod 
    def create_domain(cls, value: str, role: str = None):
        """Factory method for domain observables"""
        return cls(
            type='domain',
            value=value,
            role=role
        )

class Observables(BaseModel):
    """Container for all observables with validation."""
    network: List[Observable] = Field(default_factory=list, description="Network observables")


class Sighting(BaseModel):
    """Core sighting information with automatic timestamp generation."""
    sighting_id: Optional[str] = Field(None, description="STIX sighting identifier")
    observables: Observables = Field(..., description="Threat observables")

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Sighting timestamp")
    confidence: int = Field(..., ge=0, le=100, description="Confidence level (0-100)")
    severity: Optional[str] = Field(None, description="Threat severity")
    observation_count: Optional[int] = Field(1, ge=1, description="Number of observations")
    first_observed: Optional[datetime] = Field(None, description="First observed time")
    last_observed: Optional[datetime] = Field(None, description="Last observed time")

    @model_validator(mode='after')
    def validate_observation_times_and_ensure_ids(self):
        """Ensure observation times are logical and IDs are set"""
        # Ensure required fields are set
        if not self.sighting_id:
            self.sighting_id = f"sighting--{uuid.uuid4()}"
        if not self.timestamp:
            self.timestamp = datetime.utcnow()
            
        # Validate observation times
        if self.first_observed and self.last_observed and self.first_observed > self.last_observed:
            raise ValueError("first_observed cannot be after last_observed")
        return self
    
    @classmethod
    def create(cls, observables: Observables = None, confidence: int = 69, severity: str = None, observation_count: int = 1):
        """Factory method for creating sightings"""
        return cls(
            confidence=confidence,
            observables=observables,
            severity=severity,
            observation_count=observation_count
        )

class Submitter(BaseModel):
    """Submitting organisation with validation and auto-generation."""
    organisation_id: Optional[str] = Field(None, description="STIX identity for organisation")
    organisation_type: str = Field(default="cyber_partner", description="organisation type")
    access_level: Optional[str] = Field(None, description="organisation tier")
    sector: Optional[str] = Field(None, description="Industry sector")
    region: Optional[str] = Field(None, description="Geographic region")    

    @field_validator('access_level', mode='before')
    def validate_type(cls, v):
        allowed_types = ['partner', 'contributor', 'observer', 'public', 'core_member']
        if v not in allowed_types:
            raise ValueError(f'Tier type must be one of: {allowed_types}')
        return v
    
    @model_validator(mode='after') 
    def ensure_org_id(self):
        """Ensure organisation ID is always set"""
        if not self.organisation_id:
            self.organisation_id = f"identity--{uuid.uuid4()}"
        return self

    @classmethod
    def create(cls, access_level: str, organisation_type: str = "cyber_partner", sector: str = None, region: str = None):
        """Factory method for creating submitters"""
        return cls(
            access_level=access_level,
            organisation_type=organisation_type,
            sector=sector,
            region=region
        )

class HitTarget(BaseModel):
    """Affected organisation with privacy controls. """   
    organisation_id: Optional[str] = Field(None, description="STIX identity for affected organisation") 
    sector: str = Field(..., min_length=1, description="Industry sector of target")
    organisation_type: Optional[str] = Field(default="customer", description="organisation type")
    organisation_size: Optional[str] = Field(None, description="organisation size category")
    region: Optional[str] = Field(None, description="Geographic region")
    anonymization_level: Optional[str] = Field(default="high", description="Data anonymization level")
    
    @model_validator(mode='after') 
    def ensure_org_id(self):
        """Ensure organisation ID is always set"""
        if not self.organisation_id:
            self.organisation_id = f"identity--{uuid.uuid4()}"
        return self

    @field_validator('organisation_size')
    @classmethod
    def normalize_org_size(cls, v):
        """Normalize organisation size categories"""
        if v is None:
            return v
            
        size_mappings = {
            'small': 'small',
            'sme': 'small',
            'startup': 'small',
            'medium': 'medium',
            'mid': 'medium',
            'large': 'large',
            'enterprise': 'large',
            'multinational': 'large'
        }
        
        normalized = v.lower().strip()
        return size_mappings.get(normalized, v)

    @classmethod
    def create(cls, sector: str, organisation_size: str = None, region: str = None):
        """Factory method for creating hit targets"""
        return cls(
            sector=sector,
            organisation_size=organisation_size,
            region=region
        )

class Submission(BaseModel):
    """Submission model based on your existing implementation"""
    submission_id: Optional[str] = Field(None, description="Unique submission identifier")
    confidence: Optional[int] = Field(None, ge=0, le=100, description="Overall confidence level")
    severity: Optional[str] = Field(None, description="Threat severity")
    submission_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    format_version: str = Field(default="1.0", description="Submission format version")
    tlp_level: Optional[str] = Field('GREEN', description="TLP classification")

    submitter: Submitter = Field(..., description="Submitting organisation")
    hit_target: Optional[HitTarget] = Field(None, description="Affected organisation")  
    sighting: Sighting = Field(..., description="Sighting details")

    
    @model_validator(mode='after') 
    def ensure_org_id(self):
        """Ensure organisation ID is always set"""
        if not self.submission_id:
            self.submission_id = f"submission--{uuid.uuid4()}"
        return self

    @field_validator('severity', mode='before')
    def validate_severity(cls, v):
        if v is not None:
            allowed = ['low', 'medium', 'high', 'critical']
            if v not in allowed:
                raise ValueError(f'Severity must be one of: {allowed}')
        return v

    @field_validator('tlp_level', mode='before')
    def validate_tlp(cls, v):
        if v is not None:
            allowed = ['RED', 'AMBER+', 'AMBER', 'GREEN', 'CLEAR']
            if v not in allowed:
                raise ValueError(f'TLP level must be one of: {allowed}')
        return v

    def to_yaml(self) -> str:
        """Serialize submission to YAML format."""
        return yaml.dump(
            {
                'submission': self.model_dump(
                    exclude_none=True,
                    by_alias=True
                )
            },
            default_flow_style=False,
            sort_keys=False
        )

    @classmethod
    def from_yaml(cls, yaml_string: str) -> 'Submission':
        """Deserialize submission from YAML format."""
        data = yaml.safe_load(yaml_string)
        if 'submission' not in data:
            raise ValueError("YAML does not contain 'submission' key")
        return cls.model_validate(data['submission'])   

class FrankSightingGenerator:
    """Generator for creating FRANK sightings programmatically."""
    
    @staticmethod
    def create_minimal_sighting(
        access_level: str,
        confidence: int,
        ip_address: str,
        target_sector: str = None,
        domain: str = None
    ) -> Submission:
        """Create a minimal FRANK sighting submission."""
        
        submitter = Submitter.create(access_level=access_level)
        if target_sector:
            hit_target = HitTarget.create(sector=target_sector)
        else:
            hit_target = None

        network_observables = [Observable.create_ipv4(ip_address)]
        if domain:
            network_observables.append(Observable.create_domain(domain))

        sighting = Sighting.create(confidence=confidence, observables=Observables(network=network_observables))
        
        return Submission(
            submitter=submitter,
            hit_target=hit_target,
            sighting=sighting
        )

    # @staticmethod
    # def create_banking_threat_sighting(
    #     submitter_access_level: str = "partner",
    #     confidence: int = 87
    # ) -> FrankSubmission:
    #     """Create a sample banking threat sighting."""
        
    #     submitter = Submitter.create(
    #         access_level=submitter_tier,
    #         sector="cybersecurity_services",
    #         region="nl_north_holland"
    #     )
        
    #     hit_target = HitTarget.create(
    #         sector="financial_services",
    #         organisation_size="medium",
    #         region="nl_north_holland"
    #     )
        
    #     sighting = Sighting.create(
    #         confidence=confidence,
    #         severity="high",
    #         observation_count=23
    #     )
        
    #     network_observables = [
    #         NetworkObservable.create_ipv4(
    #             value="185.220.102.45",
    #             role="c2_server",
    #             port=443
    #         ),
    #         NetworkObservable.create_domain(
    #             value="secure-bank-verify.nl",
    #             role="phishing_domain"
    #         )
    #     ]
        
    #     return FrankSubmission(
    #         submitter=submitter,
    #         hit_target=hit_target,
    #         sighting=sighting,
    #         observables={"network": network_observables}
    #     )


# class FrankSightingParser:
#     """Parser for processing FRANK sighting submissions."""
    
#     @staticmethod
#     def validate_submission(submission: FrankSubmission) -> List[str]:
#         """Validate a FRANK submission and return list of errors."""
#         errors = []
        
#         # Validate required fields
#         if not submission.submitter.organisation_id:
#             errors.append("Submitter organisation_id is required")
        
#         if not submission.hit_target.organisation_id:
#             errors.append("Hit target organisation_id is required")
        
#         if not submission.sighting.sighting_id:
#             errors.append("Sighting ID is required")
        
#         # Validate confidence range
#         if not 0 <= submission.sighting.confidence <= 100:
#             errors.append("Confidence must be between 0 and 100")
        
#         # Validate tier
#         valid_tiers = ["public", "observer", "contributor", "partner", "core_member"]
#         if submission.submitter.access_level not in valid_tiers:
#             errors.append(f"Invalid access_level: {submission.submitter.access_level}")
        
#         # Validate network observables
#         if not submission.observables.get("network"):
#             errors.append("At least one network observable is required")
        
#         for obs in submission.observables.get("network", []):
#             if not obs.value:
#                 errors.append("Network observable value is required")
#             if obs.type not in ["ipv4", "ipv6", "domain", "url"]:
#                 errors.append(f"Invalid network observable type: {obs.type}")
        
#         return errors

#     @staticmethod
#     def extract_iocs(submission: FrankSubmission) -> Dict[str, List[str]]:
#         """Extract IoCs from submission for further processing."""
#         iocs = {
#             "ip_addresses": [],
#             "domains": [],
#             "urls": []
#         }
        
#         for obs in submission.observables.get("network", []):
#             if obs.type in ["ipv4", "ipv6"]:
#                 iocs["ip_addresses"].append(obs.value)
#             elif obs.type == "domain":
#                 iocs["domains"].append(obs.value)
#             elif obs.type == "url":
#                 iocs["urls"].append(obs.value)
        
#         return iocs

#     @staticmethod
#     def anonymize_submission(submission: FrankSubmission, access_level: str) -> FrankSubmission:
#         """Anonymize submission based on access level."""
#         # Create a copy to avoid modifying original
#         import copy
#         anonymized = copy.deepcopy(submission)
        
#         if access_level == "public":
#             # Hash all observables for public access
#             for obs in anonymized.observables.get("network", []):
#                 obs.value = f"hash_{hash(obs.value) % 10000:04d}"
        
#         elif access_level == "observer":
#             # Partial anonymization for observers
#             for obs in anonymized.observables.get("network", []):
#                 if obs.type in ["ipv4", "ipv6"]:
#                     parts = obs.value.split(".")
#                     if len(parts) == 4:
#                         obs.value = f"{parts[0]}.{parts[1]}.x.x"
        
#         # Contributors and above get full data
#         return anonymized

def test_run_spike():
    # Generate a minimal sighting
    generator = FrankSightingGenerator()
    minimal_sighting = generator.create_minimal_sighting(
        access_level="partner",
        confidence=87,
        ip_address="185.220.102.45",
        domain="secure-bank-verify.nl"
    )
    
    print("=== Minimal Sighting YAML No Hit Target ===")
    print(minimal_sighting.to_yaml())
    
    minimal_sighting = generator.create_minimal_sighting(
        access_level="partner",
        target_sector="financial_services",
        confidence=87,
        ip_address="185.220.102.45",
        domain="secure-bank-verify.nl"
    )
    
    print("=== Minimal Sighting YAML With Hit Target ===")
    print(minimal_sighting.to_yaml())

    # Parse YAML back to object
    yaml_string = minimal_sighting.to_yaml()
    parsed_submission = Submission.from_yaml(yaml_string)

    print("\n=== Parsed Sighting (Round-trip test) ===")
    print(f"Submitter Tier: {parsed_submission.submitter.access_level}")
    print(f"Target Sector: {parsed_submission.hit_target.sector}")
    print(f"Confidence: {parsed_submission.sighting.confidence}")
    print(f"Network Observables: {len(parsed_submission.sighting.observables.network)}")

# Example usage and testing
if __name__ == "__main__":
    test_run_spike()