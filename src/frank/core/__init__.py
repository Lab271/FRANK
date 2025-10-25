#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides the core models and exceptions for the FRANK platform.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import uuid
from typing import Optional

# RFC 4122 predefined namespace UUIDs for deterministic UUID generation
# This is the official OID namespace UUID from RFC 4122 Section 4.3
# Used with UUID5 to generate consistent user IDs from usernames
IDENTIFIER_NAMESPACE = uuid.NAMESPACE_OID     # OID namespace UUID

def gen_stix_id(id_prefix: str, value: Optional[str] = None) -> str:
    """Generate a unique identifier for FRANK entities in STIX format, random when value not provided."""
    if value is None:
        value = str(uuid.uuid4())
        return f"{id_prefix}--{value}"

    namespace = IDENTIFIER_NAMESPACE
    name = f"{id_prefix}--{value}"  
    return f"{id_prefix}--{str(uuid.uuid5(namespace, name))}"
