#!/usr/bin/env python3
"""
FRANK Platform - Admin Screens

Textual screens for the admin TUI.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from frank.admin.screens.dashboard import DashboardScreen
from frank.admin.screens.login import LoginScreen
from frank.admin.screens.organisations import OrganisationDetailScreen, OrganisationsScreen
from frank.admin.screens.users import UserDetailScreen, UsersScreen

__all__ = [
    "LoginScreen",
    "DashboardScreen",
    "OrganisationsScreen",
    "OrganisationDetailScreen",
    "UsersScreen",
    "UserDetailScreen",
]
