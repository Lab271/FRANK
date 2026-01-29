#!/usr/bin/env python3
"""
FRANK Platform - Admin TUI Application

Main Textual application for the admin interface.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging

from textual.app import App

from frank.admin.client import AdminClient
from frank.admin.config import AdminConfig
from frank.admin.screens.dashboard import DashboardScreen
from frank.admin.screens.login import LoginScreen
from frank.admin.screens.organisations import OrganisationDetailScreen, OrganisationsScreen
from frank.admin.screens.users import UserDetailScreen, UsersScreen

logger = logging.getLogger(__name__)


class FrankAdminApp(App):
    """
    FRANK Admin TUI Application.

    Terminal-based interface for managing organisations and users.
    """

    TITLE = "FRANK Admin"
    SUB_TITLE = "Organisation & User Management"

    CSS = """
    Screen {
        background: $surface;
    }

    Header {
        dock: top;
        height: 3;
        background: $primary;
    }

    Footer {
        dock: bottom;
        height: 1;
    }
    """

    SCREENS = {
        "login": LoginScreen,
        "dashboard": DashboardScreen,
        "organisations": OrganisationsScreen,
        "users": UsersScreen,
    }

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+d", "toggle_dark", "Dark Mode"),
    ]

    def __init__(self, config: AdminConfig = None, **kwargs):
        """
        Initialize the admin application.

        Args:
            config: Admin configuration (uses singleton if not provided)
        """
        super().__init__(**kwargs)
        self.config = config or AdminConfig.get()
        self._client: AdminClient = None

    @property
    def client(self) -> AdminClient:
        """Get the API client (lazy initialization)."""
        if self._client is None:
            self._client = AdminClient(config=self.config)
        return self._client

    async def on_mount(self) -> None:
        """Initialize the application."""
        # Initialize HTTP client
        self._client = AdminClient(config=self.config)
        await self._client.__aenter__()

        # Check for existing valid session
        if self._client.token_manager.has_valid_tokens():
            logger.info("Found valid session, going to dashboard")
            self.push_screen("dashboard")
        else:
            logger.info("No valid session, showing login")
            self.push_screen("login")

    async def on_unmount(self) -> None:
        """Cleanup on exit."""
        if self._client:
            await self._client.__aexit__(None, None, None)

    def action_toggle_dark(self) -> None:
        """Toggle dark/light mode."""
        self.dark = not self.dark

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()


def create_admin_app(config: AdminConfig = None) -> FrankAdminApp:
    """
    Factory function to create the admin app.

    Args:
        config: Optional configuration override

    Returns:
        Configured FrankAdminApp instance
    """
    return FrankAdminApp(config=config)
