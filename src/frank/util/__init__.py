#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This modules provides utility functions to generate sample submissions
for testing and demonstration purposes. 

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from .server import create_server
from .logger import NullLogger
from .http_exceptions import create_error_response


__all__ = [
    'NullLogger',
    'create_server',
    'create_error_response',
]