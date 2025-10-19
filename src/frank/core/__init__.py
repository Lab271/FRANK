#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides the core models and exceptions for the FRANK platform.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import uuid

# RFC 4122 predefined namespace UUIDs for deterministic UUID generation
# This is the official OID namespace UUID from RFC 4122 Section 4.3
# Used with UUID5 to generate consistent user IDs from usernames
IDENTIFIER_NAMESPACE = uuid.NAMESPACE_OID     # OID namespace UUID

def gen_id(type_prefix: str, value: str) -> str:
    """Generate a unique identifier for FRANK entities."""
    namespace = IDENTIFIER_NAMESPACE
    name = f"{type_prefix}--{value}"  
    return f"{type_prefix}--{str(uuid.uuid5(namespace, name))}"
