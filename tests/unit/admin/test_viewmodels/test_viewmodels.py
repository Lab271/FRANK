#!/usr/bin/env python3
"""
Tests for FRANK Admin View Models.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime

import pytest

from frank.admin.models import (
    HealthStatus,
    MemberDTO,
    MemberListResult,
    OrganisationDTO,
    OrganisationListResult,
    UserDTO,
    UserListResult,
)
from frank.admin.viewmodels import (
    HealthViewModel,
    MemberViewModel,
    OrganisationViewModel,
    UserViewModel,
)


class TestOrganisationViewModel:
    """Tests for OrganisationViewModel."""

    def test_from_dto(self):
        """Test creating view model from DTO."""
        dto = OrganisationDTO(
            organisation_id="org-123",
            name="Test Org",
            organisation_type="customer",
            sector="Technology",
            client_count=5,
        )

        vm = OrganisationViewModel.from_dto(dto)

        assert vm.id == "org-123"
        assert vm.name == "Test Org"

    def test_type_display_customer(self):
        """Test type display for customer."""
        dto = OrganisationDTO(
            organisation_id="org-123",
            name="Test",
            organisation_type="customer",
        )
        vm = OrganisationViewModel(dto=dto)

        assert vm.type_display == "Customer"

    def test_type_display_cyber_partner(self):
        """Test type display for cyber partner."""
        dto = OrganisationDTO(
            organisation_id="org-123",
            name="Test",
            organisation_type="cyber_partner",
        )
        vm = OrganisationViewModel(dto=dto)

        assert vm.type_display == "Cyber Partner"

    def test_sector_display_with_value(self):
        """Test sector display with value."""
        dto = OrganisationDTO(
            organisation_id="org-123",
            name="Test",
            organisation_type="customer",
            sector="Technology",
        )
        vm = OrganisationViewModel(dto=dto)

        assert vm.sector_display == "Technology"

    def test_sector_display_empty(self):
        """Test sector display when empty."""
        dto = OrganisationDTO(
            organisation_id="org-123",
            name="Test",
            organisation_type="customer",
        )
        vm = OrganisationViewModel(dto=dto)

        assert vm.sector_display == "-"

    def test_to_table_row(self):
        """Test conversion to table row."""
        dto = OrganisationDTO(
            organisation_id="org-123",
            name="Test Org",
            organisation_type="customer",
            sector="Tech",
            client_count=5,
        )
        vm = OrganisationViewModel(dto=dto)

        row = vm.to_table_row()

        assert row == ("org-123", "Test Org", "Customer", "Tech", "5")

    def test_from_list_result(self):
        """Test creating list of view models."""
        result = OrganisationListResult(
            organisations=[
                OrganisationDTO(organisation_id="org-1", name="Org 1", organisation_type="customer"),
                OrganisationDTO(organisation_id="org-2", name="Org 2", organisation_type="cyber_partner"),
            ],
            total=2,
        )

        vms = OrganisationViewModel.from_list_result(result)

        assert len(vms) == 2
        assert vms[0].name == "Org 1"
        assert vms[1].type_display == "Cyber Partner"


class TestUserViewModel:
    """Tests for UserViewModel."""

    def test_from_dto(self):
        """Test creating view model from DTO."""
        dto = UserDTO(
            username="testuser",
            email="test@example.com",
            groups=["FRANK_OBSERVER"],
            enabled=True,
        )

        vm = UserViewModel.from_dto(dto)

        assert vm.username == "testuser"
        assert vm.email == "test@example.com"

    def test_groups_display_with_groups(self):
        """Test groups display with groups."""
        dto = UserDTO(
            username="test",
            email="test@example.com",
            groups=["FRANK_OBSERVER", "FRANK_CONTRIBUTOR"],
        )
        vm = UserViewModel(dto=dto)

        assert vm.groups_display == "FRANK_OBSERVER, FRANK_CONTRIBUTOR"

    def test_groups_display_empty(self):
        """Test groups display when empty."""
        dto = UserDTO(username="test", email="test@example.com", groups=[])
        vm = UserViewModel(dto=dto)

        assert vm.groups_display == "-"

    def test_status_display_active(self):
        """Test status display when enabled."""
        dto = UserDTO(username="test", email="test@example.com", enabled=True)
        vm = UserViewModel(dto=dto)

        assert vm.status_display == "Active"
        assert vm.is_active is True

    def test_status_display_disabled(self):
        """Test status display when disabled."""
        dto = UserDTO(username="test", email="test@example.com", enabled=False)
        vm = UserViewModel(dto=dto)

        assert vm.status_display == "Disabled"
        assert vm.is_active is False

    def test_to_table_row(self):
        """Test conversion to table row."""
        dto = UserDTO(
            username="testuser",
            email="test@example.com",
            groups=["FRANK_OBSERVER"],
            enabled=True,
        )
        vm = UserViewModel(dto=dto)

        row = vm.to_table_row()

        assert row == ("testuser", "test@example.com", "FRANK_OBSERVER", "Active")

    def test_from_list_result(self):
        """Test creating list of view models."""
        result = UserListResult(
            users=[
                UserDTO(username="user1", email="user1@example.com"),
                UserDTO(username="user2", email="user2@example.com", enabled=False),
            ],
            total=2,
        )

        vms = UserViewModel.from_list_result(result)

        assert len(vms) == 2
        assert vms[0].username == "user1"
        assert vms[1].status_display == "Disabled"


class TestMemberViewModel:
    """Tests for MemberViewModel."""

    def test_from_dto(self):
        """Test creating view model from DTO."""
        dto = MemberDTO(username="testuser", role="admin")

        vm = MemberViewModel.from_dto(dto)

        assert vm.username == "testuser"

    def test_role_display_member(self):
        """Test role display for member."""
        dto = MemberDTO(username="test", role="member")
        vm = MemberViewModel(dto=dto)

        assert vm.role_display == "Member"

    def test_role_display_admin(self):
        """Test role display for admin."""
        dto = MemberDTO(username="test", role="admin")
        vm = MemberViewModel(dto=dto)

        assert vm.role_display == "Admin"

    def test_role_display_owner(self):
        """Test role display for owner."""
        dto = MemberDTO(username="test", role="owner")
        vm = MemberViewModel(dto=dto)

        assert vm.role_display == "Owner"

    def test_joined_display_with_date(self):
        """Test joined display with date."""
        dto = MemberDTO(
            username="test",
            role="member",
            joined_at=datetime(2025, 1, 15, 10, 30),
        )
        vm = MemberViewModel(dto=dto)

        assert vm.joined_display == "2025-01-15"

    def test_joined_display_no_date(self):
        """Test joined display without date."""
        dto = MemberDTO(username="test", role="member")
        vm = MemberViewModel(dto=dto)

        assert vm.joined_display == "-"

    def test_to_table_row(self):
        """Test conversion to table row."""
        dto = MemberDTO(
            username="testuser",
            role="admin",
            joined_at=datetime(2025, 1, 15),
        )
        vm = MemberViewModel(dto=dto)

        row = vm.to_table_row()

        assert row == ("testuser", "Admin", "2025-01-15")

    def test_from_list_result(self):
        """Test creating list of view models."""
        result = MemberListResult(
            members=[
                MemberDTO(username="user1", role="admin"),
                MemberDTO(username="user2", role="member"),
            ],
            total=2,
        )

        vms = MemberViewModel.from_list_result(result)

        assert len(vms) == 2
        assert vms[0].role_display == "Admin"


class TestHealthViewModel:
    """Tests for HealthViewModel."""

    def test_from_dto(self):
        """Test creating view model from DTO."""
        dto = HealthStatus(status="healthy", database="healthy")

        vm = HealthViewModel.from_dto(dto)

        assert vm.is_healthy is True

    def test_status_display(self):
        """Test status display."""
        dto = HealthStatus(status="healthy", database="healthy")
        vm = HealthViewModel(dto=dto)

        assert vm.status_display == "API: healthy | DB: healthy"

    def test_api_status(self):
        """Test API status property."""
        dto = HealthStatus(status="healthy", database="error")
        vm = HealthViewModel(dto=dto)

        assert vm.api_status == "healthy"
        assert vm.db_status == "error"

    def test_is_healthy_true(self):
        """Test is_healthy when all healthy."""
        dto = HealthStatus(status="healthy", database="healthy")
        vm = HealthViewModel(dto=dto)

        assert vm.is_healthy is True

    def test_is_healthy_false(self):
        """Test is_healthy when unhealthy."""
        dto = HealthStatus(status="error", database="healthy")
        vm = HealthViewModel(dto=dto)

        assert vm.is_healthy is False

    def test_error_factory(self):
        """Test error factory method."""
        vm = HealthViewModel.error("Connection failed")

        assert vm.is_healthy is False
        assert vm.api_status == "error"
        assert vm.error_message == "Connection failed"

    def test_error_message_empty(self):
        """Test error message when none."""
        dto = HealthStatus(status="healthy", database="healthy")
        vm = HealthViewModel(dto=dto)

        assert vm.error_message == ""
