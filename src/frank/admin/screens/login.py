#!/usr/bin/env python3
"""
FRANK Platform - Login Screen

Login screen with username/password authentication.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from textual import on
from textual.app import ComposeResult
from textual.containers import Center, Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static


class LoginScreen(Screen):
    """Login screen for user authentication."""

    CSS = """
    LoginScreen {
        align: center middle;
    }

    #login-container {
        width: 60;
        height: auto;
        border: solid $primary;
        padding: 1 2;
    }

    #login-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        color: $primary;
    }

    #login-subtitle {
        text-align: center;
        color: $text-muted;
        padding-bottom: 1;
    }

    .login-field {
        margin: 1 0;
    }

    .login-label {
        padding: 0 0 0 1;
    }

    #login-error {
        color: $error;
        text-align: center;
        padding: 1;
        display: none;
    }

    #login-error.visible {
        display: block;
    }

    #login-submit {
        margin-top: 1;
        width: 100%;
    }

    #login-status {
        text-align: center;
        color: $text-muted;
        padding: 1;
    }
    """

    BINDINGS = [
        ("escape", "quit", "Quit"),
        ("enter", "submit", "Login"),
    ]

    def compose(self) -> ComposeResult:
        """Create the login form."""
        with Center():
            with Container(id="login-container"):
                yield Static("FRANK Admin", id="login-title")
                yield Static("Organisation & User Management", id="login-subtitle")

                with Vertical(classes="login-field"):
                    yield Label("Username", classes="login-label")
                    yield Input(placeholder="Enter username", id="login-username")

                with Vertical(classes="login-field"):
                    yield Label("Password", classes="login-label")
                    yield Input(placeholder="Enter password", password=True, id="login-password")

                yield Static("", id="login-error")
                yield Button("Login", variant="primary", id="login-submit")
                yield Static("", id="login-status")

    def on_mount(self) -> None:
        """Focus username field on mount."""
        self.query_one("#login-username", Input).focus()

    def _show_error(self, message: str) -> None:
        """Display error message."""
        error = self.query_one("#login-error", Static)
        error.update(message)
        error.add_class("visible")

    def _hide_error(self) -> None:
        """Hide error message."""
        error = self.query_one("#login-error", Static)
        error.remove_class("visible")

    def _set_status(self, message: str) -> None:
        """Update status message."""
        self.query_one("#login-status", Static).update(message)

    def _set_loading(self, loading: bool) -> None:
        """Toggle loading state."""
        button = self.query_one("#login-submit", Button)
        button.disabled = loading
        button.label = "Logging in..." if loading else "Login"

    @on(Button.Pressed, "#login-submit")
    async def handle_login(self) -> None:
        """Handle login button press."""
        await self._do_login()

    async def action_submit(self) -> None:
        """Handle enter key press."""
        await self._do_login()

    async def _do_login(self) -> None:
        """Perform login attempt."""
        self._hide_error()
        self._set_loading(True)

        username = self.query_one("#login-username", Input).value.strip()
        password = self.query_one("#login-password", Input).value

        if not username or not password:
            self._show_error("Please enter username and password")
            self._set_loading(False)
            return

        self._set_status("Authenticating...")

        try:
            # Access client from app
            client = self.app.client
            await client.login(username, password)

            self._set_status("Login successful!")

            # Navigate to dashboard
            self.app.push_screen("dashboard")

        except Exception as e:
            self._show_error(str(e))
            self._set_status("")

        finally:
            self._set_loading(False)

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
