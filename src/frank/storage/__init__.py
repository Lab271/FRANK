#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This modules provides utility functions to generate sample submissions
for testing and demonstration purposes with data conforming to FRANK v2 schema.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

# from frank.core.exceptions import *
# from .exceptions import *
from .base import BaseFRANKDatabase
from .sqlite import create_sqlite_database
from .mysql import create_mysql_database
from .dynamodb import create_dynamodb_database
from .exceptions import FRANKDatabaseError, FRANKConfigurationError, FRANKConnectionError
from .exceptions import FRANKStorageError, FRANKQueryError

__all__ = [
    'create_sqlite_database',
    'create_mysql_database',
    'create_dynamodb_database',
    'BaseFRANKDatabase',
    'FRANKDatabaseError',
    'FRANKConfigurationError',
    'FRANKConnectionError',
    'FRANKStorageError',
    'FRANKQueryError'
]
