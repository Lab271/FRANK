#!/usr/bin/env python3
"""
FRANK Platform - Admin TUI Module

Terminal-based admin interface for managing FRANK organisations and users.

Uses an MVC architecture:
- Models: DTOs in models/ for typed data transfer
- ViewModels: Display logic in viewmodels/ for UI presentation
- Services: Business logic in services/ that can be reused by web GUI
- Screens: Textual views in screens/ for UI rendering

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from frank.admin.app import FrankAdminApp
from frank.admin.client import AdminClient
from frank.admin.config import AdminConfig

# Models (DTOs)
from frank.admin.models import (
    HealthStatus,
    MemberDTO,
    MemberListResult,
    OrganisationDTO,
    OrganisationListResult,
    UserDTO,
    UserListResult,
)

# Services
from frank.admin.services import (
    AuthResult,
    AuthService,
    OrganisationService,
    ServiceResult,
    UserService,
)

# ViewModels
from frank.admin.viewmodels import (
    HealthViewModel,
    MemberViewModel,
    OrganisationViewModel,
    UserViewModel,
)

__all__ = [
    # Core
    "FrankAdminApp",
    "AdminClient",
    "AdminConfig",
    # Models (DTOs)
    "HealthStatus",
    "OrganisationDTO",
    "OrganisationListResult",
    "UserDTO",
    "UserListResult",
    "MemberDTO",
    "MemberListResult",
    # Services
    "AuthService",
    "OrganisationService",
    "UserService",
    "ServiceResult",
    "AuthResult",
    # ViewModels
    "OrganisationViewModel",
    "UserViewModel",
    "MemberViewModel",
    "HealthViewModel",
]
