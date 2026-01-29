#!/usr/bin/env python3
"""
FRANK Platform - Admin TUI Module

Terminal-based admin interface for managing FRANK organisations and users.

Uses an MVC architecture:
- Models: DTOs in services/dto.py for typed data transfer
- Views: Textual screens in screens/ for UI rendering
- Services: Business logic in services/ that can be reused by web GUI

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from frank.admin.app import FrankAdminApp
from frank.admin.client import AdminClient
from frank.admin.config import AdminConfig
from frank.admin.services import (
    AuthResult,
    AuthService,
    HealthStatus,
    MemberDTO,
    OrganisationDTO,
    OrganisationListResult,
    OrganisationService,
    UserDTO,
    UserListResult,
    UserService,
)

__all__ = [
    # Core
    "FrankAdminApp",
    "AdminClient",
    "AdminConfig",
    # Services
    "AuthService",
    "OrganisationService",
    "UserService",
    # DTOs
    "AuthResult",
    "HealthStatus",
    "OrganisationDTO",
    "OrganisationListResult",
    "UserDTO",
    "UserListResult",
    "MemberDTO",
]
