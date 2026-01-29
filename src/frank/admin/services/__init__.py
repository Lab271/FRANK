#!/usr/bin/env python3
"""
FRANK Platform - Admin Services Layer

Business logic services for the admin module.
Provides a testable layer between UI and API client.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from frank.admin.services.auth_service import AuthResult, AuthService
from frank.admin.services.dto import (
    HealthStatus,
    MemberDTO,
    OrganisationDTO,
    OrganisationListResult,
    UserDTO,
    UserListResult,
)
from frank.admin.services.organisation_service import OrganisationService
from frank.admin.services.user_service import UserService

__all__ = [
    # DTOs
    "OrganisationDTO",
    "UserDTO",
    "MemberDTO",
    "HealthStatus",
    "OrganisationListResult",
    "UserListResult",
    "AuthResult",
    # Services
    "AuthService",
    "OrganisationService",
    "UserService",
]
