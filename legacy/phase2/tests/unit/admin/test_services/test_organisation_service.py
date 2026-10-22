#!/usr/bin/env python3
"""
Tests for FRANK Admin OrganisationService.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from frank.admin.client import AdminClientError, ConflictError, NotFoundError
from frank.admin.config import AdminConfig
from frank.admin.models import HealthStatus, MemberListResult, OrganisationDTO, OrganisationListResult
from frank.admin.services import OrganisationService, ServiceResult


@pytest.fixture(autouse=True)
def reset_config():
    """Reset AdminConfig singleton before each test."""
    AdminConfig.reset()
    yield
    AdminConfig.reset()


@pytest.fixture
def mock_client():
    """Create a mock AdminClient."""
    client = MagicMock()
    client.health_check = AsyncMock()
    client.list_organisations = AsyncMock()
    client.get_organisation = AsyncMock()
    client.create_organisation = AsyncMock()
    client.update_organisation = AsyncMock()
    client.delete_organisation = AsyncMock()
    client.list_members = AsyncMock()
    client.add_member = AsyncMock()
    client.remove_member = AsyncMock()
    return client


class TestServiceResult:
    """Tests for ServiceResult dataclass."""

    def test_ok_with_data(self):
        """Test creating success result with data."""
        result = ServiceResult.ok(data={"key": "value"})

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_ok_without_data(self):
        """Test creating success result without data."""
        result = ServiceResult.ok()

        assert result.success is True
        assert result.data is None

    def test_fail(self):
        """Test creating failure result."""
        result = ServiceResult.fail("Something went wrong")

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.data is None


class TestOrganisationServiceHealth:
    """Tests for OrganisationService health check."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, mock_client):
        """Test health check when healthy."""
        mock_client.health_check.return_value = {"status": "healthy", "database": "healthy"}

        service = OrganisationService(mock_client)
        result = await service.health_check()

        assert isinstance(result, HealthStatus)
        assert result.is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_error(self, mock_client):
        """Test health check with error."""
        mock_client.health_check.side_effect = AdminClientError("Connection refused")

        service = OrganisationService(mock_client)
        result = await service.health_check()

        assert result.status == "error"
        assert "Connection refused" in result.message

    @pytest.mark.asyncio
    async def test_health_check_generic_exception(self, mock_client):
        """Test health check with generic exception."""
        mock_client.health_check.side_effect = Exception("Unexpected error")

        service = OrganisationService(mock_client)
        result = await service.health_check()

        assert result.status == "error"
        assert "Unexpected error" in result.message


class TestOrganisationServiceList:
    """Tests for OrganisationService list operations."""

    @pytest.mark.asyncio
    async def test_list_organisations_success(self, mock_client):
        """Test listing organisations."""
        mock_client.list_organisations.return_value = {
            "organisations": [
                {"organisation_id": "org-1", "name": "Org 1", "organisation_type": "customer"},
                {"organisation_id": "org-2", "name": "Org 2", "organisation_type": "cyber_partner"},
            ],
            "total": 2,
        }

        service = OrganisationService(mock_client)
        result = await service.list_organisations()

        assert result.success is True
        assert isinstance(result.data, OrganisationListResult)
        assert len(result.data.organisations) == 2

    @pytest.mark.asyncio
    async def test_list_organisations_with_filters(self, mock_client):
        """Test listing organisations with filters."""
        mock_client.list_organisations.return_value = {"organisations": [], "total": 0}

        service = OrganisationService(mock_client)
        await service.list_organisations(
            organisation_type="customer",
            sector="Technology",
            limit=50,
            offset=10,
        )

        mock_client.list_organisations.assert_called_once_with(
            organisation_type="customer",
            sector="Technology",
            limit=50,
            offset=10,
        )

    @pytest.mark.asyncio
    async def test_list_organisations_error(self, mock_client):
        """Test listing organisations with error."""
        mock_client.list_organisations.side_effect = AdminClientError("Server error")

        service = OrganisationService(mock_client)
        result = await service.list_organisations()

        assert result.success is False
        assert "Server error" in result.error

    @pytest.mark.asyncio
    async def test_list_organisations_generic_exception(self, mock_client):
        """Test listing organisations with generic exception."""
        mock_client.list_organisations.side_effect = Exception("Unexpected error")

        service = OrganisationService(mock_client)
        result = await service.list_organisations()

        assert result.success is False
        assert "Unexpected error" in result.error


class TestOrganisationServiceCRUD:
    """Tests for OrganisationService CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_organisation_success(self, mock_client):
        """Test getting an organisation."""
        mock_client.get_organisation.return_value = {
            "organisation_id": "org-123",
            "name": "Test Org",
            "organisation_type": "customer",
        }

        service = OrganisationService(mock_client)
        result = await service.get_organisation("org-123")

        assert result.success is True
        assert isinstance(result.data, OrganisationDTO)
        assert result.data.name == "Test Org"

    @pytest.mark.asyncio
    async def test_get_organisation_not_found(self, mock_client):
        """Test getting non-existent organisation."""
        mock_client.get_organisation.side_effect = NotFoundError("Not found", 404)

        service = OrganisationService(mock_client)
        result = await service.get_organisation("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_organisation_client_error(self, mock_client):
        """Test getting organisation with AdminClientError."""
        mock_client.get_organisation.side_effect = AdminClientError("Server error")

        service = OrganisationService(mock_client)
        result = await service.get_organisation("org-123")

        assert result.success is False
        assert "Server error" in result.error

    @pytest.mark.asyncio
    async def test_get_organisation_generic_exception(self, mock_client):
        """Test getting organisation with generic exception."""
        mock_client.get_organisation.side_effect = Exception("Unexpected error")

        service = OrganisationService(mock_client)
        result = await service.get_organisation("org-123")

        assert result.success is False
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_create_organisation_success(self, mock_client):
        """Test creating an organisation."""
        mock_client.create_organisation.return_value = {
            "organisation_id": "org-new",
            "name": "New Org",
            "organisation_type": "customer",
        }

        service = OrganisationService(mock_client)
        result = await service.create_organisation(
            name="New Org",
            organisation_type="customer",
            sector="Technology",
        )

        assert result.success is True
        assert result.data.organisation_id == "org-new"

    @pytest.mark.asyncio
    async def test_create_organisation_empty_name(self, mock_client):
        """Test creating organisation with empty name."""
        service = OrganisationService(mock_client)
        result = await service.create_organisation(name="", organisation_type="customer")

        assert result.success is False
        assert "required" in result.error.lower()
        mock_client.create_organisation.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_organisation_invalid_type(self, mock_client):
        """Test creating organisation with invalid type."""
        service = OrganisationService(mock_client)
        result = await service.create_organisation(name="Test", organisation_type="invalid")

        assert result.success is False
        assert "invalid" in result.error.lower()
        mock_client.create_organisation.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_organisation_conflict(self, mock_client):
        """Test creating duplicate organisation."""
        mock_client.create_organisation.side_effect = ConflictError("Already exists", 409)

        service = OrganisationService(mock_client)
        result = await service.create_organisation(name="Existing", organisation_type="customer")

        assert result.success is False
        assert "already exists" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_organisation_with_region(self, mock_client):
        """Test creating organisation with region."""
        mock_client.create_organisation.return_value = {
            "organisation_id": "org-new",
            "name": "New Org",
            "organisation_type": "customer",
            "region": "Europe",
        }

        service = OrganisationService(mock_client)
        result = await service.create_organisation(
            name="New Org",
            organisation_type="customer",
            region="Europe",
        )

        assert result.success is True
        # Verify region was passed
        call_args = mock_client.create_organisation.call_args[0][0]
        assert call_args["region"] == "Europe"

    @pytest.mark.asyncio
    async def test_create_organisation_client_error(self, mock_client):
        """Test creating organisation with AdminClientError."""
        mock_client.create_organisation.side_effect = AdminClientError("Server error")

        service = OrganisationService(mock_client)
        result = await service.create_organisation(name="Test", organisation_type="customer")

        assert result.success is False
        assert "Server error" in result.error

    @pytest.mark.asyncio
    async def test_create_organisation_generic_exception(self, mock_client):
        """Test creating organisation with generic exception."""
        mock_client.create_organisation.side_effect = Exception("Unexpected error")

        service = OrganisationService(mock_client)
        result = await service.create_organisation(name="Test", organisation_type="customer")

        assert result.success is False
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_update_organisation_success(self, mock_client):
        """Test updating an organisation."""
        mock_client.update_organisation.return_value = {
            "organisation_id": "org-123",
            "name": "Updated Name",
            "organisation_type": "customer",
        }

        service = OrganisationService(mock_client)
        result = await service.update_organisation("org-123", name="Updated Name")

        assert result.success is True
        assert result.data.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_organisation_no_fields(self, mock_client):
        """Test updating with no fields."""
        service = OrganisationService(mock_client)
        result = await service.update_organisation("org-123")

        assert result.success is False
        assert "no fields" in result.error.lower()
        mock_client.update_organisation.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_organisation_invalid_type(self, mock_client):
        """Test updating with invalid type."""
        service = OrganisationService(mock_client)
        result = await service.update_organisation("org-123", organisation_type="invalid")

        assert result.success is False
        assert "invalid" in result.error.lower()

    @pytest.mark.asyncio
    async def test_update_organisation_not_found(self, mock_client):
        """Test updating non-existent organisation."""
        mock_client.update_organisation.side_effect = NotFoundError("Not found", 404)

        service = OrganisationService(mock_client)
        result = await service.update_organisation("nonexistent", name="New Name")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_update_organisation_with_all_fields(self, mock_client):
        """Test updating organisation with all optional fields."""
        mock_client.update_organisation.return_value = {
            "organisation_id": "org-123",
            "name": "Updated",
            "organisation_type": "cyber_partner",
            "sector": "Finance",
            "region": "Asia",
        }

        service = OrganisationService(mock_client)
        result = await service.update_organisation(
            "org-123",
            name="Updated",
            organisation_type="cyber_partner",
            sector="Finance",
            region="Asia",
        )

        assert result.success is True
        # Verify all fields were passed
        call_args = mock_client.update_organisation.call_args[0][1]
        assert call_args["organisation_type"] == "cyber_partner"
        assert call_args["sector"] == "Finance"
        assert call_args["region"] == "Asia"

    @pytest.mark.asyncio
    async def test_update_organisation_client_error(self, mock_client):
        """Test updating organisation with AdminClientError."""
        mock_client.update_organisation.side_effect = AdminClientError("Server error")

        service = OrganisationService(mock_client)
        result = await service.update_organisation("org-123", name="New Name")

        assert result.success is False
        assert "Server error" in result.error

    @pytest.mark.asyncio
    async def test_update_organisation_generic_exception(self, mock_client):
        """Test updating organisation with generic exception."""
        mock_client.update_organisation.side_effect = Exception("Unexpected error")

        service = OrganisationService(mock_client)
        result = await service.update_organisation("org-123", name="New Name")

        assert result.success is False
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_delete_organisation_success(self, mock_client):
        """Test deleting an organisation."""
        mock_client.delete_organisation.return_value = None

        service = OrganisationService(mock_client)
        result = await service.delete_organisation("org-123")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_delete_organisation_not_found(self, mock_client):
        """Test deleting non-existent organisation."""
        mock_client.delete_organisation.side_effect = NotFoundError("Not found", 404)

        service = OrganisationService(mock_client)
        result = await service.delete_organisation("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_delete_organisation_client_error(self, mock_client):
        """Test deleting organisation with AdminClientError."""
        mock_client.delete_organisation.side_effect = AdminClientError("Server error")

        service = OrganisationService(mock_client)
        result = await service.delete_organisation("org-123")

        assert result.success is False
        assert "Server error" in result.error

    @pytest.mark.asyncio
    async def test_delete_organisation_generic_exception(self, mock_client):
        """Test deleting organisation with generic exception."""
        mock_client.delete_organisation.side_effect = Exception("Unexpected error")

        service = OrganisationService(mock_client)
        result = await service.delete_organisation("org-123")

        assert result.success is False
        assert "Unexpected error" in result.error


class TestOrganisationServiceMembers:
    """Tests for OrganisationService member operations."""

    @pytest.mark.asyncio
    async def test_list_members_success(self, mock_client):
        """Test listing members."""
        mock_client.list_members.return_value = {
            "members": [
                {"username": "user1", "role": "admin"},
                {"username": "user2", "role": "member"},
            ],
            "total": 2,
        }

        service = OrganisationService(mock_client)
        result = await service.list_members("org-123")

        assert result.success is True
        assert isinstance(result.data, MemberListResult)
        assert len(result.data.members) == 2

    @pytest.mark.asyncio
    async def test_list_members_with_role_filter(self, mock_client):
        """Test listing members with role filter."""
        mock_client.list_members.return_value = {"members": [], "total": 0}

        service = OrganisationService(mock_client)
        await service.list_members("org-123", role="admin")

        mock_client.list_members.assert_called_once_with("org-123", role="admin")

    @pytest.mark.asyncio
    async def test_list_members_org_not_found(self, mock_client):
        """Test listing members for non-existent organisation."""
        mock_client.list_members.side_effect = NotFoundError("Not found", 404)

        service = OrganisationService(mock_client)
        result = await service.list_members("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_list_members_client_error(self, mock_client):
        """Test listing members with AdminClientError."""
        mock_client.list_members.side_effect = AdminClientError("Server error")

        service = OrganisationService(mock_client)
        result = await service.list_members("org-123")

        assert result.success is False
        assert "Server error" in result.error

    @pytest.mark.asyncio
    async def test_list_members_generic_exception(self, mock_client):
        """Test listing members with generic exception."""
        mock_client.list_members.side_effect = Exception("Unexpected error")

        service = OrganisationService(mock_client)
        result = await service.list_members("org-123")

        assert result.success is False
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_add_member_success(self, mock_client):
        """Test adding a member."""
        mock_client.add_member.return_value = {
            "username": "newuser",
            "role": "member",
        }

        service = OrganisationService(mock_client)
        result = await service.add_member("org-123", "newuser", role="member")

        assert result.success is True
        assert result.data.username == "newuser"

    @pytest.mark.asyncio
    async def test_add_member_empty_username(self, mock_client):
        """Test adding member with empty username."""
        service = OrganisationService(mock_client)
        result = await service.add_member("org-123", "", role="member")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_add_member_invalid_role(self, mock_client):
        """Test adding member with invalid role."""
        service = OrganisationService(mock_client)
        result = await service.add_member("org-123", "user", role="superadmin")

        assert result.success is False
        assert "invalid role" in result.error.lower()

    @pytest.mark.asyncio
    async def test_add_member_already_exists(self, mock_client):
        """Test adding existing member."""
        mock_client.add_member.side_effect = ConflictError("Already a member", 409)

        service = OrganisationService(mock_client)
        result = await service.add_member("org-123", "existing_user")

        assert result.success is False
        assert "already" in result.error.lower()

    @pytest.mark.asyncio
    async def test_add_member_not_found(self, mock_client):
        """Test adding member when org or user not found."""
        mock_client.add_member.side_effect = NotFoundError("Not found", 404)

        service = OrganisationService(mock_client)
        result = await service.add_member("org-123", "user1")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_add_member_client_error(self, mock_client):
        """Test adding member with AdminClientError."""
        mock_client.add_member.side_effect = AdminClientError("Server error")

        service = OrganisationService(mock_client)
        result = await service.add_member("org-123", "user1")

        assert result.success is False
        assert "Server error" in result.error

    @pytest.mark.asyncio
    async def test_add_member_generic_exception(self, mock_client):
        """Test adding member with generic exception."""
        mock_client.add_member.side_effect = Exception("Unexpected error")

        service = OrganisationService(mock_client)
        result = await service.add_member("org-123", "user1")

        assert result.success is False
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_remove_member_success(self, mock_client):
        """Test removing a member."""
        mock_client.remove_member.return_value = None

        service = OrganisationService(mock_client)
        result = await service.remove_member("org-123", "user1")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_remove_member_not_found(self, mock_client):
        """Test removing non-existent member."""
        mock_client.remove_member.side_effect = NotFoundError("Not found", 404)

        service = OrganisationService(mock_client)
        result = await service.remove_member("org-123", "nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_remove_member_client_error(self, mock_client):
        """Test removing member with AdminClientError."""
        mock_client.remove_member.side_effect = AdminClientError("Server error")

        service = OrganisationService(mock_client)
        result = await service.remove_member("org-123", "user1")

        assert result.success is False
        assert "Server error" in result.error

    @pytest.mark.asyncio
    async def test_remove_member_generic_exception(self, mock_client):
        """Test removing member with generic exception."""
        mock_client.remove_member.side_effect = Exception("Unexpected error")

        service = OrganisationService(mock_client)
        result = await service.remove_member("org-123", "user1")

        assert result.success is False
        assert "Unexpected error" in result.error
