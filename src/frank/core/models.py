#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)

Replaces dataclass implementation with robust validation for cybersecurity data.
Implements "be forgiving on what you receive, strong on what you return" principle.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    field_serializer,
    ConfigDict,
)
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid

from frank.core.enum import ObservableType, AccessTier, SeverityLevel
from frank import __version__


class Observable(BaseModel):
    """
    Observable with automatic validation and STIX-compliant IDs.
    """

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
        populate_by_name=True,  # Allow both field name and alias
    )

    id: Optional[str] = Field(None, description="STIX-formatted observable ID")
    observable_type: ObservableType = Field(..., alias="type", description="Type of network observable")
    value: str = Field(..., min_length=1, description="Observable value")

    role: Optional[str] = Field(None, description="Role in attack (C2, exfiltration, etc)")
    port: Optional[int] = Field(None, ge=1, le=65535, description="Network port")
    protocol: Optional[str] = Field(None, description="Network protocol")
    first_seen: Optional[datetime] = Field(None, description="First observation time")
    connection_count: Optional[int] = Field(None, ge=0, description="Number of connections")

    @field_serializer("first_seen", when_used="always")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Always serialize datetime as ISO string"""
        if value is None:
            return None
        return value.isoformat()

    @model_validator(mode="after")
    def ensure_id_generated(self):
        """Ensure ID is always generated after all fields are set"""
        if not self.id:
            type_val = self.observable_type if isinstance(self.observable_type, str) else self.observable_type.value
            self.id = f"{type_val}--{uuid.uuid4()}"
        return self

    @model_validator(mode="after")
    def normalize_values(self):
        """Normalize values based on type after all fields are processed."""
        if self.observable_type == ObservableType.DOMAIN:
            self.value = self.value.strip().lower()
        elif self.observable_type in [ObservableType.IPV4, ObservableType.IPV6]:
            self.value = self.value.strip().lower()
        elif self.observable_type == ObservableType.URL:
            self.value = self.value.strip()  # Preserve case for URLs
        else:
            self.value = self.value.strip().lower()
        return self

    @classmethod
    def create_ipv4(cls, value: str, role: str = None, port: int = None):
        """Factory method for IPv4 observables"""
        return cls(observable_type=ObservableType.IPV4, value=value, role=role, port=port)

    @classmethod
    def create_domain(cls, value: str, role: str = None):
        """Factory method for domain observables"""
        return cls(observable_type=ObservableType.DOMAIN, value=value, role=role)


class Submitter(BaseModel):
    """
    Submitting organisation with validation and auto-generation.
    """

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
    )

    organisation_id: Optional[str] = Field(None, description="STIX identity for organisation")
    access_level: AccessTier = Field(..., description="Access tier level")
    organisation_type: str = Field(default="cyber_partner", description="organisation type")

    # Optional metadata
    sector: Optional[str] = Field(None, description="Industry sector")
    region: Optional[str] = Field(None, description="Geographic region")
    client_count: Optional[int] = Field(None, ge=0, description="Number of protected clients")

    @model_validator(mode="after")
    def ensure_org_id(self):
        """Ensure organisation ID is always set"""
        if not self.organisation_id:
            self.organisation_id = f"identity--{uuid.uuid4()}"
        return self

    @field_validator("sector")
    @classmethod
    def normalize_sector(cls, v):
        """Normalize sector names - 'be forgiving' on input"""
        if v is None:
            return v

        # Normalize common sector variations
        # TODO: outside model in separate file
        sector_mappings = {
            "finance": "financial",
            "banking": "financial",
            "healthcare": "health",
            "medical": "health",
            "government": "public_sector",
            "gov": "public_sector",
            "tech": "technology",
            "it": "technology",
        }

        normalized = v.lower().strip()
        return sector_mappings.get(normalized, normalized)

    @classmethod
    def create(cls, access_level: AccessTier, sector: str = None, region: str = None):
        """Factory method for creating submitters"""
        return cls(access_level=access_level, sector=sector, region=region)


class HitTarget(BaseModel):
    """
    Affected organisation with privacy controls.
    """

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
    )

    organisation_id: Optional[str] = Field(None, description="STIX identity for affected organisation")
    sector: str = Field(..., min_length=1, description="Industry sector of target")

    # Optional metadata
    organisation_type: Optional[str] = Field(default="customer", description="organisation type")
    organisation_size: Optional[str] = Field(None, description="organisation size category")
    region: Optional[str] = Field(None, description="Geographic region")
    anonymization_level: Optional[str] = Field(default="high", description="Data anonymization level")

    @field_validator("organisation_id", mode="before")
    @classmethod
    def generate_org_id(cls, v):
        """Generate target identity if not provided"""
        if v is None or v == "":
            return f"identity--{uuid.uuid4()}"
        return v

    @model_validator(mode="after")
    def ensure_org_id(self):
        """Ensure organisation ID is always set"""
        if not self.organisation_id:
            self.organisation_id = f"identity--{uuid.uuid4()}"
        return self

    @field_validator("organisation_size")
    @classmethod
    def normalize_org_size(cls, v):
        """Normalize organisation size categories"""
        if v is None:
            return v

        # TODO: outside model in separate file
        size_mappings = {
            "small": "small",
            "sme": "small",
            "startup": "small",
            "medium": "medium",
            "mid": "medium",
            "large": "large",
            "enterprise": "large",
            "multinational": "large",
        }

        normalized = v.lower().strip()
        return size_mappings.get(normalized, v)

    @classmethod
    def create(cls, sector: str, organisation_size: str = None, region: str = None):
        """Factory method for creating hit targets"""
        return cls(sector=sector, organisation_size=organisation_size, region=region)


class Observables(BaseModel):
    """
    Container for all observables with validation.
    """

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
    )

    network: Optional[List[Observable]] = Field(default_factory=list, description="Network observables")
    file: Optional[List[Observable]] = Field(default_factory=list, description="File observables")
    process: Optional[List[Observable]] = Field(default_factory=list, description="Process observables")

class SigmaDetection(BaseModel):
    """
    SIGMA rule detection metadata.
    """

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
    )

    rule_id: str = Field(default_factory=lambda: f"sigma--{uuid.uuid4()}", description="SIGMA rule identifier")
    rule_name: str = Field(..., min_length=1, description="SIGMA rule name")
    rule_version: Optional[str] = Field(None, description="Rule version")
    rule_status: Optional[str] = Field(None, description="Rule status")
    sigma_yaml: Optional[str] = Field(None, description="SIGMA rule YAML content")
    rule_effectiveness: Optional[float] = Field(None, description="Rule effectiveness score")
    false_positive_rate: Optional[float] = Field(None, description="False positive rate")


class Campaign(BaseModel):
    """
    Threat campaign metadata.
    """

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
    )
    
    id: str = Field(default_factory=lambda: f"campaign--{uuid.uuid4()}", description="Campaign identifier")
    name: Optional[str] = Field(None, description="Campaign name")
    attribution: Optional[str] = Field(None, description="Attributed threat actor")
    target_sectors: Optional[List[str]] = Field(None, description="Targeted sectors")
    attack_vector: Optional[str] = Field(None, description="Primary attack vector")
    payload_type: Optional[str] = Field(None, description="Type of payload used")
    campaign_start: Optional[datetime] = Field(None, description="Campaign start time")
    estimated_victims: Optional[int] = Field(None, description="Estimated number of victims")
    confidence: Optional[int] = Field(None, description="Attribution confidence")


class ThreatContext(BaseModel):
    """
    Threat context including campaign and MITRE mapping.
    """

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
    )
    
    campaign: Optional[Campaign] = Field(None, description="Campaign information")
    mitre_attack: Optional[Dict[str, Any]] = Field(None, description="MITRE ATT&CK mapping")
    malware_family: Optional[Dict[str, Any]] = Field(None, description="Malware family data")


class Impact(BaseModel):
    """
    Impact assessment metadata.
    """

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
    )

    affected_systems: Optional[int] = Field(None, description="Number of affected systems")
    compromised_accounts: Optional[int] = Field(None, description="Compromised accounts")
    containment_time: Optional[str] = Field(None, description="Time to containment")
    financial_impact_eur: Optional[int] = Field(None, description="Financial impact in EUR")


class Sighting(BaseModel):
    """
    Core sighting information with observables and automatic timestamp generation.
    """

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
    )

    sighting_id: Optional[str] = Field(None, description="STIX sighting identifier")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When threat was observed")
    confidence: int = Field(69, ge=0, le=100, description="Confidence score 0-100")
    observation_count: int = Field(default=1, ge=1, description="Number of observations")
    observables: Optional[Observables] = Field(None, description="Threat observables")

    # Optional extended threat metadata
    severity: Optional[SeverityLevel] = Field(None, description="Threat severity level")
    first_observed: Optional[datetime] = Field(None, description="First observation time")
    last_observed: Optional[datetime] = Field(None, description="Last observation time")
    sigma_detection: Optional[SigmaDetection] = Field(None, description="SIGMA detection data")
    threat_context: Optional[ThreatContext] = Field(None, description="Threat context")
    impact: Optional[Impact] = Field(None, description="Impact assessment")

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v):
        """Ensure observation times are logical and IDs are set"""
        # Ensure required fields are set
        if v is None or v == "":
            return datetime.now(timezone.utc)
        return v

    @field_serializer("timestamp", "first_observed", "last_observed", when_used="always")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Always serialize datetime as ISO string"""
        if value is None:
            return None
        return value.isoformat()

    @model_validator(mode="after")
    def validate_observation_times_and_ensure_ids(self):
        """Ensure observation times are logical and IDs are set"""
        # Ensure required fields are set
        if not self.sighting_id:
            self.sighting_id = f"sighting--{uuid.uuid4()}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc)

        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
        if self.first_observed and self.first_observed.tzinfo is None:
            self.first_observed = self.first_observed.replace(tzinfo=timezone.utc)
        if self.last_observed and self.last_observed.tzinfo is None:
            self.last_observed = self.last_observed.replace(tzinfo=timezone.utc)

        # Validate observation times
        if self.first_observed and self.last_observed:
            if self.first_observed > self.last_observed:
                raise ValueError("first_observed cannot be after last_observed")

        # Ensure observation times don't conflict with main timestamp
        if self.first_observed and self.timestamp:
            if self.first_observed > self.timestamp:
                raise ValueError("first_observed cannot be after main timestamp")
        return self

    @classmethod
    def create(
        cls,
        observables: Observables = None,
        confidence: int = 69,
        severity: SeverityLevel = None,
        observation_count: int = 1,
    ):
        """Factory method for creating sightings"""
        return cls(
            confidence=confidence,
            observables=observables,
            severity=severity,
            observation_count=observation_count,
        )


class Submission(BaseModel):
    """
    Complete FRANK threat intelligence submission with comprehensive validation.
    """

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
    )

    submission_id: Optional[str] = Field(None, description="Unique submission identifier")
    format_version: Optional[str] = Field(default=__version__, description="FRANK format version")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),  description="Submission timestamp")

    # Optional metadata - be forgiving on input
    submitter: Optional[Submitter] = Field(None, description="Submitting organisation")
    submission_method: Optional[str] = Field(default="api", description="Submission method")
    processing_notes: Optional[str] = Field(None, description="Processing notes")

    sighting: Optional[Sighting] = Field(None, description="Sighting details")
    # TODO: Move this to sighting?
    hit_target: Optional[HitTarget] = Field(None, description="Affected organisation")
    tlp_level: Optional[str] = Field("GREEN", description="TLP classification")
    confidence: Optional[int] = Field(None, ge=0, le=100, description="Overall confidence level")
    severity: Optional[str] = Field(None, description="Threat severity")


    @field_serializer("timestamp", when_used="always")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Always serialize datetime as ISO string"""
        if value is None:
            return None
        return value.isoformat()

    @model_validator(mode="after")
    def validate_submission_integrity(self):
        """Cross-field validation for submission integrity"""
        # Ensure organisation ID is always set
        if not self.submission_id:
            self.submission_id = f"submission--{uuid.uuid4()}"

        # Ensure submitter and target are different organisations
        if not self.hit_target:
            return self

        submitter_id = self.submitter.organisation_id
        target_id = self.hit_target.organisation_id

        if submitter_id and target_id and submitter_id == target_id:
            raise ValueError("Submitter and hit_target cannot be the same organisation")

        return self

    def to_yaml(self) -> str:
        """Convert to YAML with proper formatting"""
        import yaml

        data = {"submission": self.model_dump(exclude_none=True, by_alias=True)}
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def to_json(self) -> str:
        """Convert to JSON with proper formatting"""
        import json

        data = {"submission": self.model_dump(exclude_none=True, by_alias=True)}
        return json.dumps(data)

    # TODO: add from_yaml/from_json classmethods

    # Move this to sighting?
    def extract_iocs(self) -> Dict[str, List[str]]:
        """Extract IoCs for threat intelligence processing"""
        iocs = {"ip_addresses": [], "domains": [], "urls": [], "emails": []}

        for obs in self.observables.network:
            if obs.type in [ObservableType.IPV4, ObservableType.IPV6]:
                iocs["ip_addresses"].append(obs.value)
            elif obs.type == ObservableType.DOMAIN:
                iocs["domains"].append(obs.value)
            elif obs.type == ObservableType.URL:
                iocs["urls"].append(obs.value)
            elif obs.type == ObservableType.EMAIL:
                iocs["emails"].append(obs.value)
            # TODO: extend for other types

        return iocs


    @classmethod
    def create_minimal(
        cls,
        submitter_access_level: AccessTier = AccessTier.PARTNER,
        target_sector: str = None,
        threat_ips: List[str] = None,
    ) -> "Submission":
        """
        Factory method for creating minimal valid submissions.
        Implements 'be forgiving' by providing sensible defaults.
        """
        if threat_ips is None:
            threat_ips = ["185.220.102.45", "203.0.113.42"]

        # Create network observables
        network_obs = Observables(network=[Observable.create_ipv4(ip, role="c2") for ip in threat_ips])

        hit_target = HitTarget.create(sector=target_sector) if target_sector else None

        return cls(
            submitter=Submitter.create(access_level=submitter_access_level),
            hit_target=hit_target,
            sighting=Sighting.create(observables=network_obs),
        )

    @classmethod
    # TODO: Improve this and use Sightings/Observables
    def from_legacy_dict(cls, data: Dict[str, Any]) -> "Submission":
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

            # Handle observables nested in sighting (legacy formats)
            if "observables" in submission_data:
                observables_data = submission_data.pop("observables")
            elif "observables" in sighting_data:
                observables_data = sighting_data.pop("observables", {})
            else:
                observables_data = {}

            # Build observables - be forgiving on format
            obs = {}
            for obs_type in ["network", "file", "process"]:
                obs[obs_type] = []  
                if observables_data.get(obs_type):
                    for obs_data in observables_data[obs_type]:
                        try:
                            obs[obs_type].append(Observable(**obs_data))
                        except Exception:
                            continue

            sighting = Sighting(observables=Observables(**obs), **sighting_data)

            return cls(
                submitter=submitter,
                hit_target=hit_target,
                sighting=sighting
            )

        except Exception as e:
            raise ValueError(f"Failed to parse legacy submission format: {e}")


# Example usage and testing functions
def example_usage():
    """Demonstrate Pydantic model usage"""

    print("=== FRANK Pydantic Models Demo (v2 Compatible) ===\n")

    # 1. Create minimal submission using factory method
    print("1. Creating minimal submission...")
    minimal = Submission.create_minimal(
        submitter_access_level=AccessTier.PARTNER,
        target_sector="financial",
        threat_ips=["192.168.1.100", "malicious.example.com"],
    )
    print("✓ Minimal submission created")

    # 2. Demonstrate validation - will catch errors
    print("\n2. Testing validation...")
    try:
        # This should fail validation
        invalid = Observable(
            type=ObservableType.IPV4,
            value="not.an.ip.address",  # Invalid IP
        )
    except ValueError as e:
        print(f"✓ Validation caught invalid IP: {e}")

    # 3. Demonstrate 'be forgiving' parsing
    print("\n3. Testing 'be forgiving' legacy format parsing...")
    legacy_data = {
        "submission": {
            "submitter": {"access_level": "partner"},  # Missing org_id - will be generated
            "hit_target": {"sector": "finance"},  # Will be normalized to "financial"
            "sighting": {
                "confidence": 85
            },
            "observables": {  # Old format in Submission
                "network": [
                    {"type": "ipv4", "value": "203.0.113.1"}
                ]
            }
        }
    }

    parsed = Submission.from_legacy_dict(legacy_data)
    print(f"✓ Legacy format parsed successfully")
    print(f"  - Generated org IDs: {parsed.submitter.organisation_id[:12]}...")
    print(f"  - Normalized sector: {parsed.hit_target.sector}")

    # 4. Demonstrate 'strong on return'
    print("\n4. Testing 'strong on return' output ...")
    api_output = parsed.model_dump(exclude_none=True, by_alias=True)
    print("✓ Strict API format generated")

    # 5. Demonstrate serialization
    print("\n5. Testing serialization to JSON/YAML ...")
    json_output = parsed.to_json()
    yaml_output = parsed.to_yaml()
    print(f"✓ JSON output length: {len(json_output)} characters")
    print(f"✓ YAML output length: {len(yaml_output)} characters")

    # 6. Demonstrate 'strong on return' output
    print("\n6. Testing 'strong on return' output ...")
    strong_output = parsed.model_dump(exclude_none=True, by_alias=True)
    print("✓ Strong output format generated")  
    print(f"  - Keys in output: {list(strong_output.keys())}")
    

    print("\n=== Pydantic v2 Benefits Demonstrated ===")
    print("✓ Updated validation with helpful error messages")
    print("✓ Type safety and IDE support")
    print("✓ Flexible input parsing ('be forgiving')")
    print("✓ Strict output formatting ('strong on return')")
    print("✓ Built-in serialization to JSON/YAML")
    print("✓ Factory methods for common use cases")
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
