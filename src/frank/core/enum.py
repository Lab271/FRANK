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