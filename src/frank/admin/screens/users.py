#!/usr/bin/env python3
"""
FRANK Platform - Users Screen

User list and detail screens.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Label, Select, Static, Switch


class UsersScreen(Screen):
    """List and manage users."""

    CSS = """
    UsersScreen {
        layout: vertical;
    }

    #content {
        padding: 1;
        height: 1fr;
    }

    #filter-bar {
        height: 3;
        padding: 0 1;
    }

    #toolbar {
        height: 3;
        padding: 0 1;
    }

    #user-table {
        height: 1fr;
        min-height: 10;
    }

    #status {
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
    }
    """

    BINDINGS = [
        ("n", "new_user", "New"),
        ("r", "refresh", "Refresh"),
        ("d", "delete", "Delete"),
        ("escape", "back", "Back"),
        ("enter", "view_detail", "View"),
    ]

    def __init__(self, organisation_id: str = None, **kwargs):
        """
        Initialize users screen.

        Args:
            organisation_id: Filter users by organisation (optional)
        """
        super().__init__(**kwargs)
        self.organisation_id = organisation_id

    def compose(self) -> ComposeResult:
        """Create the users list layout."""
        yield Header()

        with Container(id="content"):
            with Horizontal(id="filter-bar"):
                yield Label("Organisation:")
                yield Select([], id="org-filter", prompt="All organisations")

            with Horizontal(id="toolbar"):
                yield Button("New User", variant="primary", id="btn-new")
                yield Button("Refresh", id="btn-refresh")
                yield Button("Delete", variant="error", id="btn-delete")

            yield DataTable(id="user-table")

        yield Static("Loading...", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the users table."""
        # Setup table
        table = self.query_one("#user-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Username", "Email", "Groups", "Status")

        # Load organisations for filter
        await self._load_org_filter()

        # Load users
        await self._load_users()

    async def _load_org_filter(self) -> None:
        """Load organisations for the filter dropdown."""
        try:
            result = await self.app.client.list_organisations()
            orgs = result.get("organisations", [])

            select = self.query_one("#org-filter", Select)
            options = [(org["name"], org["organisation_id"]) for org in orgs]
            select.set_options(options)

            if self.organisation_id:
                select.value = self.organisation_id

        except Exception as e:
            self.query_one("#status", Static).update(f"Error loading orgs: {e}")

    async def _load_users(self) -> None:
        """Load users from API."""
        table = self.query_one("#user-table", DataTable)
        table.clear()

        self.query_one("#status", Static).update("Loading users...")

        try:
            org_id = self.query_one("#org-filter", Select).value

            if org_id and org_id != Select.BLANK:
                result = await self.app.client.list_users(org_id)
                users = result.get("users", [])
            else:
                # No org selected - show message
                self.query_one("#status", Static).update("Select an organisation to view users")
                return

            for user in users:
                groups = ", ".join(user.get("groups", []))
                status = "Active" if user.get("enabled", True) else "Disabled"

                table.add_row(
                    user.get("username", ""),
                    user.get("email", ""),
                    groups or "-",
                    status,
                )

            self.query_one("#status", Static).update(f"Loaded {len(users)} users")

        except Exception as e:
            self.query_one("#status", Static).update(f"Error: {e}")

    @on(Select.Changed, "#org-filter")
    async def org_filter_changed(self, event: Select.Changed) -> None:
        """Handle organisation filter change."""
        await self._load_users()

    @on(Button.Pressed, "#btn-new")
    def action_new_user(self) -> None:
        """Open new user dialog."""
        org_id = self.query_one("#org-filter", Select).value
        if not org_id or org_id == Select.BLANK:
            self.query_one("#status", Static).update("Select an organisation first")
            return

        self.app.push_screen(UserDetailScreen(username=None, organisation_id=org_id))

    @on(Button.Pressed, "#btn-refresh")
    async def action_refresh(self) -> None:
        """Refresh the users list."""
        await self._load_users()

    @on(Button.Pressed, "#btn-delete")
    async def action_delete(self) -> None:
        """Delete selected user."""
        table = self.query_one("#user-table", DataTable)
        if table.cursor_row is not None:
            row = table.get_row_at(table.cursor_row)
            username = row[0]

            try:
                await self.app.client.delete_user(username)
                self.query_one("#status", Static).update(f"Deleted user: {username}")
                await self._load_users()
            except Exception as e:
                self.query_one("#status", Static).update(f"Error deleting: {e}")

    @on(DataTable.RowSelected)
    def action_view_detail(self, event: DataTable.RowSelected = None) -> None:
        """View user details."""
        table = self.query_one("#user-table", DataTable)
        if table.cursor_row is not None:
            row = table.get_row_at(table.cursor_row)
            username = row[0]
            self.app.push_screen(UserDetailScreen(username=username))

    def action_back(self) -> None:
        """Go back to dashboard."""
        self.app.pop_screen()


class UserDetailScreen(Screen):
    """View and edit user details."""

    CSS = """
    UserDetailScreen {
        layout: vertical;
    }

    #form-container {
        padding: 2;
        width: 80;
        height: 1fr;
    }

    .form-field {
        margin: 1 0;
    }

    .field-label {
        padding: 0 0 0 1;
    }

    #groups-section {
        margin-top: 2;
        border: solid $primary;
        padding: 1;
    }

    .group-row {
        height: 3;
        padding: 0 1;
    }

    .group-label {
        width: 30;
    }

    #button-row {
        margin-top: 2;
    }

    #status {
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
    }
    """

    BINDINGS = [
        ("escape", "back", "Back"),
        ("ctrl+s", "save", "Save"),
    ]

    def __init__(self, username: str = None, organisation_id: str = None, **kwargs):
        """
        Initialize user detail screen.

        Args:
            username: Username to edit, or None for new user
            organisation_id: Organisation ID for new user
        """
        super().__init__(**kwargs)
        self.username = username
        self.organisation_id = organisation_id
        self.is_new = username is None

    def compose(self) -> ComposeResult:
        """Create the user form."""
        title = "New User" if self.is_new else f"Edit User: {self.username}"
        yield Header(name=title)

        with Container(id="form-container"):
            with Vertical(classes="form-field"):
                yield Label("Username", classes="field-label")
                yield Input(
                    placeholder="Username",
                    id="field-username",
                    disabled=not self.is_new,
                )

            with Vertical(classes="form-field"):
                yield Label("Email", classes="field-label")
                yield Input(placeholder="user@example.com", id="field-email")

            if self.is_new:
                with Vertical(classes="form-field"):
                    yield Label("Password", classes="field-label")
                    yield Input(placeholder="Initial password", password=True, id="field-password")

            with Vertical(classes="form-field"):
                yield Label("Enabled", classes="field-label")
                yield Switch(value=True, id="field-enabled")

            with Vertical(id="groups-section"):
                yield Label("Groups (select access level)", classes="field-label")
                with Horizontal(classes="group-row"):
                    yield Checkbox("Observer", id="group-observer")
                    yield Label("Basic read access", classes="group-label")
                with Horizontal(classes="group-row"):
                    yield Checkbox("Contributor", id="group-contributor")
                    yield Label("Can submit threat data", classes="group-label")
                with Horizontal(classes="group-row"):
                    yield Checkbox("Partner", id="group-partner")
                    yield Label("Partner organisation access", classes="group-label")
                with Horizontal(classes="group-row"):
                    yield Checkbox("Core Member", id="group-core-member")
                    yield Label("Full administrative access", classes="group-label")

            with Horizontal(id="button-row"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", id="btn-cancel")

        yield Static("", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        """Load user data if editing."""
        if not self.is_new:
            await self._load_user()

    async def _load_user(self) -> None:
        """Load user data into form."""
        try:
            user = await self.app.client.get_user(self.username)

            self.query_one("#field-username", Input).value = user.get("username", "")
            self.query_one("#field-email", Input).value = user.get("email", "")
            self.query_one("#field-enabled", Switch).value = user.get("enabled", True)

            groups = user.get("groups", [])
            # Set checkboxes based on user's groups
            self.query_one("#group-observer", Checkbox).value = "observer" in groups
            self.query_one("#group-contributor", Checkbox).value = "contributor" in groups
            self.query_one("#group-partner", Checkbox).value = "partner" in groups
            self.query_one("#group-core-member", Checkbox).value = "core_member" in groups

            self.query_one("#status", Static).update(f"Loaded: {self.username}")

        except Exception as e:
            self.query_one("#status", Static).update(f"Error: {e}")

    @on(Button.Pressed, "#btn-save")
    async def action_save(self) -> None:
        """Save user."""
        username = self.query_one("#field-username", Input).value.strip()
        email = self.query_one("#field-email", Input).value.strip()
        enabled = self.query_one("#field-enabled", Switch).value

        # Collect groups from checkboxes
        groups = []
        if self.query_one("#group-observer", Checkbox).value:
            groups.append("observer")
        if self.query_one("#group-contributor", Checkbox).value:
            groups.append("contributor")
        if self.query_one("#group-partner", Checkbox).value:
            groups.append("partner")
        if self.query_one("#group-core-member", Checkbox).value:
            groups.append("core_member")

        if not username or not email:
            self.query_one("#status", Static).update("Error: Username and email required")
            return

        try:
            if self.is_new:
                password = self.query_one("#field-password", Input).value
                if not password:
                    self.query_one("#status", Static).update("Error: Password required for new user")
                    return

                await self.app.client.create_user(
                    organisation_id=self.organisation_id,
                    username=username,
                    email=email,
                    password=password,
                    groups=groups,
                )
                self.query_one("#status", Static).update(f"Created user: {username}")
            else:
                await self.app.client.update_user(
                    username=self.username,
                    email=email,
                    enabled=enabled,
                    groups=groups,
                )
                self.query_one("#status", Static).update("Saved successfully")

            self.app.pop_screen()

        except Exception as e:
            self.query_one("#status", Static).update(f"Error: {e}")

    @on(Button.Pressed, "#btn-cancel")
    def action_back(self) -> None:
        """Go back without saving."""
        self.app.pop_screen()
