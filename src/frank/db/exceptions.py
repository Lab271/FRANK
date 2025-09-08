#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This modules provides exception classes for database operations.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

class FRANKDatabaseError(Exception):
    """Base exception for FRANK database operations."""
    pass

class FRANKConfigurationError(FRANKDatabaseError):
    """Raised when database configuration fails."""
    pass

class FRANKConnectionError(FRANKDatabaseError):
    """Raised when database connection fails."""
    pass

class FRANKStorageError(FRANKDatabaseError):
    """Raised when storage operations fail."""
    pass

class FRANKQueryError(FRANKDatabaseError):
    """Raised when query operations fail."""
    pass
