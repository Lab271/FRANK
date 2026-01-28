#!/usr/bin/env python3
"""
FRANK Platform - Admin TUI Module

Terminal-based admin interface for managing FRANK organisations and users.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from frank.admin.app import FrankAdminApp
from frank.admin.client import AdminClient
from frank.admin.config import AdminConfig

__all__ = [
    "FrankAdminApp",
    "AdminClient",
    "AdminConfig",
]
