#!/usr/bin/env python3
"""
FRANK Platform - Dashboard Screen

Main dashboard with navigation to other screens.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static


class DashboardScreen(Screen):
    """Main dashboard screen with navigation."""

    CSS = """
    DashboardScreen {
        layout: grid;
        grid-size: 1;
        grid-rows: auto 1fr auto;
    }

    #dashboard-content {
        padding: 1 2;
    }

    #welcome {
        text-align: center;
        padding: 1;
        text-style: bold;
        color: $primary;
    }

    #status-bar {
        dock: bottom;
        height: 3;
        padding: 0 1;
        background: $surface;
    }

    #nav-container {
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
        padding: 2;
        height: auto;
    }

    .nav-card {
        border: solid $primary;
        padding: 1;
        height: auto;
        min-height: 8;
    }

    .nav-card:hover {
        border: solid $secondary;
    }

    .card-title {
        text-style: bold;
        color: $primary;
    }

    .card-description {
        color: $text-muted;
        padding-top: 1;
    }

    .card-button {
        margin-top: 1;
    }

    #health-status {
        text-align: right;
    }
    """

    BINDINGS = [
        ("o", "organisations", "Organisations"),
        ("u", "users", "Users"),
        ("q", "logout", "Logout"),
        ("escape", "logout", "Logout"),
    ]

    def compose(self) -> ComposeResult:
        """Create the dashboard layout."""
        yield Header()

        with Container(id="dashboard-content"):
            yield Static("Welcome to FRANK Admin", id="welcome")

            with Container(id="nav-container"):
                # Organisations card
                with Vertical(classes="nav-card"):
                    yield Label("Organisations", classes="card-title")
                    yield Static("Manage organisations and their settings", classes="card-description")
                    yield Button("Open", variant="primary", id="btn-organisations", classes="card-button")

                # Users card
                with Vertical(classes="nav-card"):
                    yield Label("Users", classes="card-title")
                    yield Static("Manage users and permissions", classes="card-description")
                    yield Button("Open", variant="primary", id="btn-users", classes="card-button")

                # API Keys card (placeholder for #57)
                with Vertical(classes="nav-card"):
                    yield Label("API Keys", classes="card-title")
                    yield Static("Generate and manage API keys", classes="card-description")
                    yield Button("Coming Soon", disabled=True, id="btn-apikeys", classes="card-button")

                # MFA Setup card (placeholder for #56)
                with Vertical(classes="nav-card"):
                    yield Label("MFA Setup", classes="card-title")
                    yield Static("Configure multi-factor authentication", classes="card-description")
                    yield Button("Coming Soon", disabled=True, id="btn-mfa", classes="card-button")

        with Horizontal(id="status-bar"):
            yield Static("", id="user-info")
            yield Static("", id="health-status")

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize dashboard data."""
        # Show logged in user
        tokens = self.app.client.token_manager.get_tokens()
        if tokens:
            self.query_one("#user-info", Static).update(f"Logged in as: {tokens.username}")

        # Check API health
        await self._check_health()

    async def _check_health(self) -> None:
        """Check Management API health."""
        try:
            health = await self.app.client.health_check()
            status = health.get("status", "unknown")
            db_status = health.get("database", "unknown")
            self.query_one("#health-status", Static).update(f"API: {status} | DB: {db_status}")
        except Exception as e:
            self.query_one("#health-status", Static).update(f"API: error ({e})")

    @on(Button.Pressed, "#btn-organisations")
    def goto_organisations(self) -> None:
        """Navigate to organisations screen."""
        self.action_organisations()

    @on(Button.Pressed, "#btn-users")
    def goto_users(self) -> None:
        """Navigate to users screen."""
        self.action_users()

    def action_organisations(self) -> None:
        """Open organisations screen."""
        self.app.push_screen("organisations")

    def action_users(self) -> None:
        """Open users screen."""
        self.app.push_screen("users")

    def action_logout(self) -> None:
        """Logout and return to login screen."""
        self.app.client.token_manager.clear_tokens()
        self.app.pop_screen()  # Back to login
