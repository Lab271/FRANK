#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)

These are all enum's for all categories used in the models.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
from enum import Enum
import yaml

def enum_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data.value))

def enum_constructor(enum_cls):
    def constructor(loader, node):
        value = loader.construct_scalar(node)
        # Try to match by value, fallback to name
        for member in enum_cls:
            if value == member.value or value == member.name:
                return member
        raise ValueError(f"{value} is not a valid {enum_cls.__name__}")
    return constructor

def register_enum_yaml(enum_cls):
    yaml.add_representer(enum_cls, enum_representer)
    yaml.add_constructor(f'!{enum_cls.__name__}', enum_constructor(enum_cls))

class AccessTier(str, Enum):
    """Access tier enumeration with validation"""

    PUBLIC = "public"
    OBSERVER = "observer"
    CONTRIBUTOR = "contributor"
    PARTNER = "partner"
    CORE_MEMBER = "core_member"

    def can_submit(self) -> bool:
        """Check if this tier level can submit data."""
        return self in {AccessTier.CONTRIBUTOR, AccessTier.PARTNER, AccessTier.CORE_MEMBER}

    def check_access_level(self, required_level) -> bool:
        """Check if user tier meets required access level using enum order."""
        members = list(type(self))
        return members.index(self) >= members.index(required_level)

    @classmethod
    def from_string(cls, value: str, default: bool = False) -> "AccessTier":
        """Convert string (case-insensitive) to AccessTier enum value.

        Args:
            value: String representation of access tier (case-insensitive)
            default: If True, return PUBLIC for invalid values instead of raising ValueError

        Returns:
            AccessTier enum value

        Raises:
            ValueError: If the string doesn't match any AccessTier value and default=False

        Examples:
            >>> AccessTier.from_string("contributor")
            <AccessTier.CONTRIBUTOR: 'contributor'>
            >>> AccessTier.from_string("PARTNER")
            <AccessTier.PARTNER: 'partner'>
            >>> AccessTier.from_string("Core_Member")
            <AccessTier.CORE_MEMBER: 'core_member'>
            >>> AccessTier.from_string("invalid", default=True)
            <AccessTier.PUBLIC: 'public'>
        """
        if not isinstance(value, str):
            if default:
                return cls.PUBLIC
            raise ValueError(f"Expected string, got {type(value).__name__}")

        # Normalize the input string: strip whitespace, lowercase, and replace spaces with underscores
        normalized = value.strip().lower().replace(" ", "_")

        # Try to find matching enum value
        for member in cls:
            if member.value == normalized:
                return member

        # If no direct match, either return default or raise error
        if default:
            return cls.PUBLIC

        valid_values = [member.value for member in cls]
        raise ValueError(f"'{value}' is not a valid AccessTier. Valid values are: {valid_values}")


class ObservableType(str, Enum):
    """Network observable types, this is a subset of STIX2 types"""

    IPV4_ADDR = "ipv4-addr"
    IPV6_ADDR = "ipv6-addr"
    DOMAIN_NAME = "domain-name"
    URL = "url"
    EMAIL_ADDR = "email-addr"
    FILE = "file"
    WINDOWS_REGISTRY_KEY = "windows-registry-key"
    MUTEX = "mutex"
    X509_CERTIFICATE = "x509-certificate"
    PROCESS = "process"
    AUTONOMOUS_SYSTEM = "autonomous-system"
    ARTIFACT = "artifact"
    DIRECTORY = "directory"
    NETWORK_TRAFFIC = "network-traffic"
    SOFTWARE = "software"
    USER_ACCOUNT = "user-account"
    CUSTOM = "custom"


class SeverityLevel(str, Enum):
    """Threat severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TLPLevel(str, Enum):
    """Traffic Light Protocol (TLP) classification levels."""

    RED = "RED"
    AMBER_PLUS = "AMBER+"  # DEFAULT
    AMBER = "AMBER"
    GREEN = "GREEN"
    CLEAR = "CLEAR"

    @classmethod
    def from_string(cls, value: str) -> "TLPLevel":
        """Normalize TLP input to enum value (case-insensitive, forgiving on input)"""
        if isinstance(value, cls):
            return value
        if value is None:
            return None
        normalized = str(value).strip().upper().replace(" ", "_").replace("-", "_")
        # Accept common variants
        tlp_map = {
            "RED": cls.RED,
            "AMBER": cls.AMBER,
            "AMBER_PLUS": cls.AMBER_PLUS,
            "AMBER+": cls.AMBER_PLUS,
            "AMBERPLUS": cls.AMBER_PLUS,
            "GREEN": cls.GREEN,
            "WHITE": cls.CLEAR,
            "CLEAR": cls.CLEAR,
        }
        if normalized in tlp_map:
            return tlp_map[normalized]
        raise ValueError(f"Unrecognized TLP level: {value}")


class SubmissionLevel(str, Enum):
    """Threat Submission complexity levels"""

    MINIMAL = "Level 1 - minimal"  # Absolute Minimal – Bare Essentials Submission
    STANDARD = "Level 2 - standard"  # Hit Target Region/Sector without organisational context
    SPECIFIC = "Level 3 - specific"  # Detailed submission with organisational context
    ENHANCED = "Level 4 - enhanced"  # Enhanced submission with additional metadata
    SIGMA = "Level 5 - sigma"  # Sigma submission with advanced analytics
    TTP = "Level 6 - ttp"  # TTP submission with tactical information

# Register enums for YAML serialization/deserialization
register_enum_yaml(AccessTier)
register_enum_yaml(ObservableType)
register_enum_yaml(SeverityLevel)
register_enum_yaml(TLPLevel)    
register_enum_yaml(SubmissionLevel) 
