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


class ObservableType(str, Enum):
    """Network observable types"""
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    DOMAIN = "domain"
    URL = "url"
    EMAIL = "email"
    FILE_HASH = 'file_hash'
    REGISTRY_KEY = "registry_key"


class SeverityLevel(str, Enum):
    """Threat severity levels"""
    LOW = "low"
    MEDIUM = "medium"  
    HIGH = "high"
    CRITICAL = "critical"

class TLPLevel(str, Enum):
    RED = "RED"
    AMBER_PLUS = "AMBER+"
    AMBER = "AMBER"
    GREEN = "GREEN"
    CLEAR = "CLEAR"