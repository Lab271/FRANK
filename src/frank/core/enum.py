#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)

These are all enum's for all categories used in the models.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
from enum import Enum

class TierLevel(str, Enum):
    """Access tier enumeration with validation"""
    PUBLIC = "public"
    OBSERVER = "observer" 
    CONTRIBUTOR = "contributor"
    PARTNER = "partner"
    CORE_MEMBER = "core_member"

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