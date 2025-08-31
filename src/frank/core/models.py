#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)
Replaces dataclass implementation with robust validation for cybersecurity data.
Implements "be forgiving on what you receive, strong on what you return" principle.
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import re
import ipaddress

from .enum import *

class NetworkObservable(BaseModel):
    """
    Network observable with automatic validation and STIX-compliant IDs.
    """
    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True
    )
    
    id: Optional[str] = Field(None, description="STIX-formatted observable ID")
    type: ObservableType = Field(..., description="Type of network observable")
    value: str = Field(..., min_length=1, description="Observable value")
    role: Optional[str] = Field(None, description="Role in attack (C2, exfiltration, etc)")
    port: Optional[int] = Field(None, ge=1, le=65535, description="Network port")
    protocol: Optional[str] = Field(None, description="Network protocol")
    first_seen: Optional[datetime] = Field(None, description="First observation time")
    connection_count: Optional[int] = Field(None, ge=0, description="Number of connections")
    
    @field_validator('id', mode='before')
    @classmethod
    def generate_stix_id(cls, v, info=None):
        """Generate STIX-compliant ID if not provided"""
        if v is None or v == "":
            # Try to get type from other fields if available
            if info and info.data:
                observable_type = info.data.get('type', 'unknown')
            else:
                observable_type = 'unknown'
                
            if observable_type in ['ipv4', 'ipv6']:
                return f"ipv4-addr--{uuid.uuid4()}"
            elif observable_type == 'domain':
                return f"domain-name--{uuid.uuid4()}"
            elif observable_type == 'url':
                return f"url--{uuid.uuid4()}"
            else:
                return f"observable--{uuid.uuid4()}"
        return v
    
    @model_validator(mode='after')
    def ensure_id_generated(self):
        """Ensure ID is always generated after all fields are set"""
        if not self.id:
            if self.type in [ObservableType.IPV4, ObservableType.IPV6]:
                self.id = f"ipv4-addr--{uuid.uuid4()}"
            elif self.type == ObservableType.DOMAIN:
                self.id = f"domain-name--{uuid.uuid4()}"
            elif self.type == ObservableType.URL:
                self.id = f"url--{uuid.uuid4()}"
            else:
                self.id = f"observable--{uuid.uuid4()}"
        return self
    
    @field_validator('value')
    @classmethod
    def validate_observable_value(cls, v, info=None):
        """Validate observable value based on type - 'be forgiving' principle"""
        if not info or not info.data:
            return v.strip()
            
        obs_type = info.data.get('type')
        
        if obs_type == ObservableType.IPV4:
            try:
                ipaddress.IPv4Address(v)
            except ipaddress.AddressValueError:
                raise ValueError(f"Invalid IPv4 address: {v}")
                
        elif obs_type == ObservableType.IPV6:
            try:
                ipaddress.IPv6Address(v)
            except ipaddress.AddressValueError:
                raise ValueError(f"Invalid IPv6 address: {v}")
                
        elif obs_type == ObservableType.DOMAIN:
            # Be forgiving - allow various domain formats
            domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
            if not re.match(domain_pattern, v):
                raise ValueError(f"Invalid domain format: {v}")
                
        elif obs_type == ObservableType.URL:
            # Be forgiving - basic URL validation
            if not (v.startswith('http://') or v.startswith('https://') or v.startswith('ftp://')):
                raise ValueError(f"URL must include protocol: {v}")
        
        return v.strip().lower() if obs_type != ObservableType.URL else v.strip()

    @classmethod
    def create_ipv4(cls, value: str, role: str = None, port: int = None):
        """Factory method for IPv4 observables"""
        return cls(
            type=ObservableType.IPV4,
            value=value,
            role=role,
            port=port
        )
    
    @classmethod 
    def create_domain(cls, value: str, role: str = None):
        """Factory method for domain observables"""
        return cls(
            type=ObservableType.DOMAIN,
            value=value,
            role=role
        )


class Submitter(BaseModel):
    """
    Submitting organization with validation and auto-generation.
    """
    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True
    )
    
    organization_id: Optional[str] = Field(None, description="STIX identity for organization")
    tier: TierLevel = Field(..., description="Access tier level")
    organization_type: str = Field(default="cyber_partner", description="Organization type")
    sector: Optional[str] = Field(None, description="Industry sector") 
    region: Optional[str] = Field(None, description="Geographic region")
    submission_method: Optional[str] = Field(default="api", description="How submission was made")
    client_count: Optional[int] = Field(None, ge=0, description="Number of protected clients")
    
    @field_validator('organization_id', mode='before')
    @classmethod
    def generate_org_id(cls, v):
        """Generate STIX identity if not provided - 'be forgiving'"""
        if v is None or v == "":
            return f"identity--{uuid.uuid4()}"
        return v
    
    @model_validator(mode='after') 
    def ensure_org_id(self):
        """Ensure organization ID is always set"""
        if not self.organization_id:
            self.organization_id = f"identity--{uuid.uuid4()}"
        return self
    
    @field_validator('sector')
    @classmethod
    def normalize_sector(cls, v):
        """Normalize sector names - 'be forgiving' on input"""
        if v is None:
            return v
        
        # Normalize common sector variations
        sector_mappings = {
            'finance': 'financial',
            'banking': 'financial', 
            'healthcare': 'health',
            'medical': 'health',
            'government': 'public_sector',
            'gov': 'public_sector',
            'tech': 'technology',
            'it': 'technology'
        }
        
        normalized = v.lower().strip()
        return sector_mappings.get(normalized, normalized)
    
    @classmethod
    def create(cls, tier: TierLevel, sector: str = None, region: str = None):
        """Factory method for creating submitters"""
        return cls(
            tier=tier,
            sector=sector,
            region=region
        )


class HitTarget(BaseModel):
    """
    Affected organization with privacy controls.
    """
    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True
    )
    
    organization_id: Optional[str] = Field(None, description="STIX identity for affected organization") 
    sector: str = Field(..., min_length=1, description="Industry sector of target")
    organization_type: Optional[str] = Field(default="customer", description="Organization type")
    organization_size: Optional[str] = Field(None, description="Organization size category")
    region: Optional[str] = Field(None, description="Geographic region")
    anonymization_level: Optional[str] = Field(default="high", description="Data anonymization level")
    
    @field_validator('organization_id', mode='before')
    @classmethod
    def generate_org_id(cls, v):
        """Generate target identity if not provided"""
        if v is None or v == "":
            return f"identity--{uuid.uuid4()}"
        return v

    @model_validator(mode='after') 
    def ensure_org_id(self):
        """Ensure organization ID is always set"""
        if not self.organization_id:
            self.organization_id = f"identity--{uuid.uuid4()}"
        return self

    @field_validator('organization_size')
    @classmethod
    def normalize_org_size(cls, v):
        """Normalize organization size categories"""
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
    def create(cls, sector: str, organization_size: str = None, region: str = None):
        """Factory method for creating hit targets"""
        return cls(
            sector=sector,
            organization_size=organization_size,
            region=region
        )


class Sighting(BaseModel):
    """
    Core sighting information with automatic timestamp generation.
    """
    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() + "Z"
        }
    )
    
    sighting_id: Optional[str] = Field(None, description="STIX sighting identifier")
    timestamp: Optional[datetime] = Field(None, description="When threat was observed")
    confidence: int = Field(69, ge=0, le=100, description="Confidence score 0-100")
    first_observed: Optional[datetime] = Field(None, description="First observation time")
    last_observed: Optional[datetime] = Field(None, description="Last observation time") 
    observation_count: int = Field(default=1, ge=1, description="Number of observations")
    severity: Optional[SeverityLevel] = Field(None, description="Threat severity level")
    
    @field_validator('sighting_id', mode='before')
    @classmethod
    def generate_sighting_id(cls, v):
        """Generate STIX sighting ID if not provided"""
        if v is None or v == "":
            return f"sighting--{uuid.uuid4()}"
        return v
    
    @field_validator('timestamp', mode='before')
    @classmethod
    def set_timestamp(cls, v):
        """Set current timestamp if not provided - 'be forgiving'"""
        if v is None or v == "":
            return datetime.utcnow()
        
        # Handle string timestamps
        if isinstance(v, str):
            try:
                # Try parsing ISO format
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                # Fallback to current time if parsing fails
                return datetime.utcnow()
        
        return v
    
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
    def create(cls, confidence: int = 69, severity: SeverityLevel = None, observation_count: int = 1):
        """Factory method for creating sightings"""
        return cls(
            confidence=confidence,
            severity=severity,
            observation_count=observation_count
        )


class Observables(BaseModel):
    """
    Container for all observables with validation.
    """
    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True
    )
    
    network: List[NetworkObservable] = Field(default_factory=list, description="Network observables")
    file: Optional[List[Dict]] = Field(default_factory=list, description="File observables")
    process: Optional[List[Dict]] = Field(default_factory=list, description="Process observables")
    
    @field_validator('network')
    @classmethod
    def validate_network_observables(cls, v):
        """Ensure at least one network observable for threat intel"""
        if not v or len(v) == 0:
            raise ValueError("At least one network observable is required")
        return v


class FRANKSubmission(BaseModel):
    """
    Complete FRANK threat intelligence submission with comprehensive validation.
    Implements both 'be forgiving' (input) and 'strong on return' (output) principles.
    """
    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() + "Z"
        }
    )
    
    submitter: Submitter = Field(..., description="Submitting organization")
    hit_target: Optional[HitTarget] = Field(..., description="Affected organization")  
    sighting: Sighting = Field(..., description="Sighting details")
    observables: Observables = Field(..., description="Threat observables")
    
    # Optional metadata - be forgiving on input
    format_version: Optional[str] = Field(default="1.0", description="FRANK format version")
    submission_method: Optional[str] = Field(default="api", description="Submission method")
    processing_notes: Optional[str] = Field(None, description="Processing notes")

    @model_validator(mode='after')
    def validate_submission_integrity(self):
        """Cross-field validation for submission integrity"""
        # Ensure submitter and target are different organizations
        if not self.hit_target:
            return self
        
        submitter_id = self.submitter.organization_id
        target_id = self.hit_target.organization_id
        
        if submitter_id and target_id and submitter_id == target_id:
            raise ValueError("Submitter and hit_target cannot be the same organization")
        
        return self

    def to_api_format(self) -> Dict[str, Any]:
        """Convert to API format - 'strong on what you return'"""
        submission = {
            "submission": {
                "submitter": self.submitter.model_dump(),
                # "hit_target": self.hit_target.model_dump(),
                "sighting": self.sighting.model_dump(),
                "observables": self.observables.model_dump()
            }
        }
        if self.hit_target:
            submission['hit_target'] = self.hit_target.model_dump()
        return submission

    def to_yaml_safe(self) -> str:
        """Convert to YAML with proper formatting"""
        import yaml
        data = self.to_api_format()
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def extract_iocs(self) -> Dict[str, List[str]]:
        """Extract IoCs for threat intelligence processing"""
        iocs = {
            "ip_addresses": [],
            "domains": [], 
            "urls": [],
            "emails": []
        }
        
        for obs in self.observables.network:
            if obs.type in [ObservableType.IPV4, ObservableType.IPV6]:
                iocs["ip_addresses"].append(obs.value)
            elif obs.type == ObservableType.DOMAIN:
                iocs["domains"].append(obs.value)
            elif obs.type == ObservableType.URL:
                iocs["urls"].append(obs.value)
            elif obs.type == ObservableType.EMAIL:
                iocs["emails"].append(obs.value)
        
        return iocs

    def anonymize_for_tier(self, access_tier: TierLevel) -> 'FRANKSubmission':
        """Anonymize submission based on access tier - 'strong on return'"""
        import copy
        anonymized = copy.deepcopy(self)
        
        if access_tier == TierLevel.PUBLIC:
            # Heavy anonymization for public access
            for obs in anonymized.observables.network:
                obs.value = f"hash_{hash(obs.value) % 10000:04d}"
            # Remove detailed metadata
            anonymized.hit_target.organization_id = "redacted"
            anonymized.submitter.organization_id = "redacted"
            
        elif access_tier == TierLevel.OBSERVER:
            # Partial anonymization 
            for obs in anonymized.observables.network:
                if obs.type == ObservableType.IPV4:
                    parts = obs.value.split('.')
                    obs.value = f"{parts[0]}.{parts[1]}.x.x"
                elif obs.type == ObservableType.DOMAIN:
                    obs.value = f"*.{'.'.join(obs.value.split('.')[1:])}"
        
        return anonymized

    @classmethod
    def create_minimal(cls, 
                      submitter_tier: TierLevel = TierLevel.PARTNER,
                      target_sector: str = "financial",
                      threat_ips: List[str] = None) -> 'FRANKSubmission':
        """
        Factory method for creating minimal valid submissions.
        Implements 'be forgiving' by providing sensible defaults.
        """
        if threat_ips is None:
            threat_ips = ["185.220.102.45", "203.0.113.42"]
        
        # Create network observables
        network_obs = [
            NetworkObservable.create_ipv4(ip, role="c2") 
            for ip in threat_ips
        ]
        
        return cls(
            submitter=Submitter.create(tier=submitter_tier),
            # hit_target=HitTarget.create(sector=target_sector),
            sighting=Sighting.create(),
            observables=Observables(network=network_obs)
        )

    @classmethod 
    def from_legacy_dict(cls, data: Dict[str, Any]) -> 'FRANKSubmission':
        """
        Parse from legacy format - handles your current dataclass format.
        Implements 'be forgiving on what you receive' principle.
        """
        try:
            # Handle nested submission format
            if "submission" in data:
                submission_data = data["submission"]
            else:
                submission_data = data
            
            # Build submitter
            submitter_data = submission_data.get("submitter", {})
            submitter = Submitter(**submitter_data)
            
            # Build hit_target - be forgiving if missing
            target_data = submission_data.get("hit_target", {})
            if not target_data.get("sector"):
                target_data["sector"] = "unknown"  # Provide default
            hit_target = HitTarget(**target_data)
            
            # Build sighting
            sighting_data = submission_data.get("sighting", {})
            
            # Handle observables nested in sighting (legacy format)
            if "observables" in sighting_data:
                observables_data = sighting_data.pop("observables")
            else:
                observables_data = submission_data.get("observables", {})
            
            sighting = Sighting(**sighting_data)
            
            # Build observables - be forgiving on format
            network_obs = []
            if observables_data.get("network"):
                for obs_data in observables_data["network"]:
                    try:
                        network_obs.append(NetworkObservable(**obs_data))
                    except Exception as e:
                        # Log warning but continue - be forgiving
                        print(f"Warning: Skipping invalid observable: {e}")
                        continue
            
            observables = Observables(network=network_obs)
            
            return cls(
                submitter=submitter,
                hit_target=hit_target,
                sighting=sighting,
                observables=observables
            )
            
        except Exception as e:
            raise ValueError(f"Failed to parse legacy submission format: {e}")


class FRANKSubmissionWrapper(BaseModel):
    """
    API wrapper that handles the nested 'submission' format your API expects.
    """
    model_config = ConfigDict(
        extra="ignore",
        json_encoders={
            datetime: lambda v: v.isoformat() + "Z"
        }
    )
    
    submission: FRANKSubmission = Field(..., description="The actual FRANK submission")


# Validation schemas for different use cases
class MinimalSubmissionRequest(BaseModel):
    """Minimal required fields for quick submissions"""
    model_config = ConfigDict(extra="forbid")  # Strict on input for requests
    
    submitter_tier: TierLevel
    target_sector: str = Field(..., min_length=1)
    threat_indicators: List[str] = Field(..., min_items=1)
    confidence: Optional[int] = Field(69, ge=0, le=100)


class SubmissionResponse(BaseModel):
    """Standardized response format - 'strong on what you return'"""
    model_config = ConfigDict(extra="forbid")  # Strict on output
    
    success: bool
    submission_id: str
    message: str
    validation_warnings: Optional[List[str]] = Field(default_factory=list)
    processing_time_ms: Optional[float] = None


# Example usage and testing functions
def example_usage():
    """Demonstrate Pydantic model usage"""
    
    print("=== FRANK Pydantic Models Demo (v2 Compatible) ===\n")
    
    # 1. Create minimal submission using factory method
    print("1. Creating minimal submission...")
    minimal = FRANKSubmission.create_minimal(
        submitter_tier=TierLevel.PARTNER,
        target_sector="financial", 
        threat_ips=["192.168.1.100", "malicious.example.com"]
    )
    print("✓ Minimal submission created")
    
    # # 2. Demonstrate validation - will catch errors
    # print("\n2. Testing validation...")
    # try:
    #     # This should fail validation
    #     invalid = NetworkObservable(
    #         type=ObservableType.IPV4,
    #         value="not.an.ip.address"  # Invalid IP
    #     )
    # except ValueError as e:
    #     print(f"✓ Validation caught invalid IP: {e}")
    
    # # 3. Demonstrate 'be forgiving' parsing
    # print("\n3. Testing 'be forgiving' legacy format parsing...")
    # legacy_data = {
    #     "submission": {
    #         "submitter": {"tier": "partner"},  # Missing org_id - will be generated
    #         "hit_target": {"sector": "finance"},  # Will be normalized to "financial"
    #         "sighting": {
    #             "confidence": 85,
    #             "observables": {  # Nested format - will be handled
    #                 "network": [
    #                     {"type": "ipv4", "value": "203.0.113.1"}
    #                 ]
    #             }
    #         }
    #     }
    # }
    
    # parsed = FRANKSubmission.from_legacy_dict(legacy_data)
    # print(f"✓ Legacy format parsed successfully")
    # print(f"  - Generated org IDs: {parsed.submitter.organization_id[:12]}...")
    # print(f"  - Normalized sector: {parsed.hit_target.sector}")
    
    # # 4. Demonstrate 'strong on return' 
    # print("\n4. Testing 'strong on return' output...")
    # api_output = parsed.to_api_format()
    # print("✓ Strict API format generated")
    
    # # 5. Demonstrate access-based anonymization
    # print("\n5. Testing tier-based anonymization...")
    # public_view = parsed.anonymize_for_tier(TierLevel.PUBLIC)
    # observer_view = parsed.anonymize_for_tier(TierLevel.OBSERVER)
    
    # print(f"  - Original IP: {parsed.observables.network[0].value}")
    # print(f"  - Observer view: {observer_view.observables.network[0].value}")
    # print(f"  - Public view: {public_view.observables.network[0].value}")
    
    # print("\n=== Pydantic v2 Benefits Demonstrated ===")
    # print("✓ Updated validation with helpful error messages")
    # print("✓ Type safety and IDE support") 
    # print("✓ Flexible input parsing ('be forgiving')")
    # print("✓ Strict output formatting ('strong on return')")
    # print("✓ Built-in serialization to JSON/YAML")
    # print("✓ Factory methods for common use cases")
    # print("✓ Access-tier based data filtering")
    # print("✓ Fixed @root_validator deprecation warnings")


if __name__ == "__main__":
    example_usage()