#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)

These are all enum's for all categories used in the models.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
from enum import Enum


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
    def from_string(cls, value: str, default: bool = False) -> 'AccessTier':
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
    """Network observable types"""
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    DOMAIN = "domain"
    URL = "url"
    EMAIL = "email"
    FILE_HASH = 'file_hash'
    REGISTRY_KEY = "registry_key"
    MUTEX = "mutex"
    CERTIFICATE = "certificate"


class SeverityLevel(str, Enum):
    """Threat severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TLPLevel(str, Enum):
    """Traffic Light Protocol (TLP) classification levels."""
    RED = "RED"
    AMBER_PLUS = "AMBER+"
    AMBER = "AMBER"
    GREEN = "GREEN"
    CLEAR = "CLEAR"


class SubmissionLevel(str, Enum):
    """
    Submission analytical depth level per FRANK HLD Section 3.2.

    Levels range from basic technical observations to advanced behavioral analysis,
    each providing different types of value to the collaborative intelligence ecosystem.
    """

    L1_RAW_OBSERVABLE = "L1"
    """Basic IoC: IP, domain, hash with minimal metadata. Technical format validation only."""

    L2_CONTEXTUALIZED = "L2"
    """Operational context: timing, frequency, affected systems, response actions."""

    L3_ATTRIBUTION = "L3"
    """Expert analysis: links to threat actors, campaigns, malware families."""

    L4_SIGMA_DETECTION = "L4"
    """Rule development: SIGMA rule triggers with effectiveness metrics."""

    L5_BEHAVIORAL_ANALYSIS = "L5"
    """Advanced research: novel TTPs, original research, innovative defensive insights."""

    @property
    def analytical_requirement(self) -> str:
        """Human-readable analytical requirement for this level."""
        requirements = {
            self.L1_RAW_OBSERVABLE: "Minimal",
            self.L2_CONTEXTUALIZED: "Operational",
            self.L3_ATTRIBUTION: "Expert analysis",
            self.L4_SIGMA_DETECTION: "Rule development expertise",
            self.L5_BEHAVIORAL_ANALYSIS: "Advanced research capability",
        }
        return requirements.get(self, "Unknown")

    @property
    def community_value(self) -> str:
        """Community value provided by this submission level."""
        values = {
            self.L1_RAW_OBSERVABLE: "Basic IoC distribution",
            self.L2_CONTEXTUALIZED: "Operational intelligence",
            self.L3_ATTRIBUTION: "Strategic threat intelligence",
            self.L4_SIGMA_DETECTION: "Automated detection capability",
            self.L5_BEHAVIORAL_ANALYSIS: "Innovation and discovery",
        }
        return values.get(self, "Unknown")

    @classmethod
    def from_string(cls, value: str, default: bool = False) -> "SubmissionLevel":
        """Convert string to SubmissionLevel enum value.

        Args:
            value: String like "L1", "L2", "l3", "L4_SIGMA_DETECTION", etc.
            default: If True, return L1 for invalid values instead of raising ValueError

        Returns:
            SubmissionLevel enum value
        """
        if not isinstance(value, str):
            if default:
                return cls.L1_RAW_OBSERVABLE
            raise ValueError(f"Expected string, got {type(value).__name__}")

        normalized = value.strip().upper()

        # Try exact match first
        for member in cls:
            if member.value == normalized or member.name == normalized:
                return member

        # Try prefix match (e.g., "L1" matches L1_RAW_OBSERVABLE)
        for member in cls:
            if member.value == normalized[:2]:
                return member

        if default:
            return cls.L1_RAW_OBSERVABLE

        valid_values = [member.value for member in cls]
        raise ValueError(f"'{value}' is not a valid SubmissionLevel. Valid values are: {valid_values}")
