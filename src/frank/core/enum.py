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
        """Check if user tier meets required access level"""
        tier_hierarchy = {
            AccessTier.PUBLIC: 0,
            AccessTier.OBSERVER: 1,
            AccessTier.CONTRIBUTOR: 2,
            AccessTier.PARTNER: 3,
            AccessTier.CORE_MEMBER: 4,
        }

        user_level = tier_hierarchy.get(self, 0)
        required_level_num = tier_hierarchy.get(required_level, 0)

        return user_level >= required_level_num

    # def __lt__(self, other):
    #     if self.__class__ is other.__class__:
    #         # Define order by enum definition order
    #         members = list(self.__class__)
    #         return members.index(self) < members.index(other)
    #     return NotImplemented


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