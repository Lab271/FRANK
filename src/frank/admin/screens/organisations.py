#!/usr/bin/env python3
"""
FRANK Platform - Organisations Screen

Organisation list and detail screens.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Select, Static


class OrganisationsScreen(Screen):
    """List and manage organisations."""

    CSS = """
    OrganisationsScreen {
        layout: vertical;
    }

    #content {
        height: 1fr;
        padding: 1;
    }

    #toolbar {
        height: 3;
        padding: 0 1;
    }

    #org-table {
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
        ("n", "new_org", "New"),
        ("r", "refresh", "Refresh"),
        ("d", "delete", "Delete"),
        ("escape", "back", "Back"),
        ("enter", "view_detail", "View"),
    ]

    def compose(self) -> ComposeResult:
        """Create the organisations list layout."""
        yield Header()

        with Container(id="content"):
            with Horizontal(id="toolbar"):
                yield Button("New Organisation", variant="primary", id="btn-new")
                yield Button("Refresh", id="btn-refresh")
                yield Button("Delete", variant="error", id="btn-delete")

            yield DataTable(id="org-table")

        yield Static("Loading...", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the organisations table."""
        table = self.query_one("#org-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Name", "Type", "Sector", "Members")

        await self._load_organisations()

    async def _load_organisations(self) -> None:
        """Load organisations from API."""
        table = self.query_one("#org-table", DataTable)
        table.clear()

        self.query_one("#status", Static).update("Loading organisations...")

        try:
            result = await self.app.client.list_organisations()

            # Handle potential error responses
            if "detail" in result:
                self.query_one("#status", Static).update(f"Error: {result['detail']}")
                return

            orgs = result.get("organisations", [])

            for org in orgs:
                table.add_row(
                    org.get("organisation_id", ""),
                    org.get("name", ""),
                    org.get("organisation_type", ""),
                    org.get("sector") or "-",
                    str(org.get("client_count", 0)),
                )

            self.query_one("#status", Static).update(f"Loaded {len(orgs)} organisations")

        except Exception as e:
            self.query_one("#status", Static).update(f"Error: {e}")

    @on(Button.Pressed, "#btn-new")
    def action_new_org(self) -> None:
        """Open new organisation dialog."""
        self.app.push_screen(OrganisationDetailScreen(organisation_id=None))

    @on(Button.Pressed, "#btn-refresh")
    async def action_refresh(self) -> None:
        """Refresh the organisations list."""
        await self._load_organisations()

    @on(Button.Pressed, "#btn-delete")
    async def action_delete(self) -> None:
        """Delete selected organisation."""
        table = self.query_one("#org-table", DataTable)
        if table.cursor_row is not None:
            row = table.get_row_at(table.cursor_row)
            org_id = row[0]

            try:
                await self.app.client.delete_organisation(org_id)
                self.query_one("#status", Static).update(f"Deleted organisation: {org_id}")
                await self._load_organisations()
            except Exception as e:
                self.query_one("#status", Static).update(f"Error deleting: {e}")

    @on(DataTable.RowSelected)
    def action_view_detail(self, event: DataTable.RowSelected = None) -> None:
        """View organisation details."""
        table = self.query_one("#org-table", DataTable)
        if table.cursor_row is not None:
            row = table.get_row_at(table.cursor_row)
            org_id = row[0]
            self.app.push_screen(OrganisationDetailScreen(organisation_id=org_id))

    def action_back(self) -> None:
        """Go back to dashboard."""
        self.app.pop_screen()


class OrganisationDetailScreen(Screen):
    """View and edit organisation details."""

    CSS = """
    OrganisationDetailScreen {
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

    #members-section {
        margin-top: 2;
        border: solid $primary;
        padding: 1;
    }

    #members-table {
        height: 10;
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

    def __init__(self, organisation_id: str = None, **kwargs):
        """
        Initialize organisation detail screen.

        Args:
            organisation_id: Organisation ID to edit, or None for new
        """
        super().__init__(**kwargs)
        self.organisation_id = organisation_id
        self.is_new = organisation_id is None

    def compose(self) -> ComposeResult:
        """Create the organisation form."""
        title = "New Organisation" if self.is_new else "Edit Organisation"
        yield Header(name=title)

        with Container(id="form-container"):
            with Vertical(classes="form-field"):
                yield Label("Name", classes="field-label")
                yield Input(placeholder="Organisation name", id="field-name")

            with Vertical(classes="form-field"):
                yield Label("Type", classes="field-label")
                yield Select(
                    [("Customer", "customer"), ("Cyber Partner", "cyber_partner")],
                    id="field-type",
                    value="customer",
                )

            with Vertical(classes="form-field"):
                yield Label("Sector", classes="field-label")
                yield Input(placeholder="Industry sector (optional)", id="field-sector")

            with Vertical(classes="form-field"):
                yield Label("Region", classes="field-label")
                yield Input(placeholder="Geographic region (optional)", id="field-region")

            if not self.is_new:
                with Vertical(id="members-section"):
                    yield Label("Members", classes="field-label")
                    yield DataTable(id="members-table")
                    with Horizontal():
                        yield Button("Add Member", id="btn-add-member")

            with Horizontal(id="button-row"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", id="btn-cancel")

        yield Static("", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        """Load organisation data if editing."""
        if not self.is_new:
            await self._load_organisation()
            await self._load_members()

    async def _load_organisation(self) -> None:
        """Load organisation data into form."""
        try:
            org = await self.app.client.get_organisation(self.organisation_id)

            self.query_one("#field-name", Input).value = org.get("name", "")
            self.query_one("#field-type", Select).value = org.get("organisation_type", "customer")
            self.query_one("#field-sector", Input).value = org.get("sector", "") or ""
            self.query_one("#field-region", Input).value = org.get("region", "") or ""

            self.query_one("#status", Static).update(f"Loaded: {self.organisation_id}")

        except Exception as e:
            self.query_one("#status", Static).update(f"Error: {e}")

    async def _load_members(self) -> None:
        """Load organisation members."""
        table = self.query_one("#members-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Username", "Role", "Joined")

        try:
            result = await self.app.client.list_members(self.organisation_id)
            members = result.get("members", [])

            for member in members:
                table.add_row(
                    member.get("username", ""),
                    member.get("role", ""),
                    member.get("joined_at", "-")[:10] if member.get("joined_at") else "-",
                )

        except Exception as e:
            self.query_one("#status", Static).update(f"Error loading members: {e}")

    @on(Button.Pressed, "#btn-save")
    async def action_save(self) -> None:
        """Save organisation."""
        data = {
            "name": self.query_one("#field-name", Input).value.strip(),
            "organisation_type": self.query_one("#field-type", Select).value,
        }

        sector = self.query_one("#field-sector", Input).value.strip()
        if sector:
            data["sector"] = sector

        region = self.query_one("#field-region", Input).value.strip()
        if region:
            data["region"] = region

        if not data["name"]:
            self.query_one("#status", Static).update("Error: Name is required")
            return

        try:
            if self.is_new:
                result = await self.app.client.create_organisation(data)
                self.query_one("#status", Static).update(f"Created: {result.get('organisation_id')}")
            else:
                await self.app.client.update_organisation(self.organisation_id, data)
                self.query_one("#status", Static).update("Saved successfully")

            # Go back after short delay
            self.app.pop_screen()

        except Exception as e:
            self.query_one("#status", Static).update(f"Error: {e}")

    @on(Button.Pressed, "#btn-cancel")
    def action_back(self) -> None:
        """Go back without saving."""
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-add-member")
    def add_member(self) -> None:
        """Add member dialog (placeholder)."""
        self.query_one("#status", Static).update("Add member: Not yet implemented")
