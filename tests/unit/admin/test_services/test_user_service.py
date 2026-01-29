#!/usr/bin/env python3
"""
Tests for FRANK Admin UserService.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from frank.admin.client import AdminClientError, ConflictError, NotFoundError
from frank.admin.config import AdminConfig
from frank.admin.services.dto import UserDTO, UserListResult
from frank.admin.services.user_service import UserService


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
    client.list_users = AsyncMock()
    client.get_user = AsyncMock()
    client.create_user = AsyncMock()
    client.update_user = AsyncMock()
    client.delete_user = AsyncMock()
    return client


class TestUserServiceList:
    """Tests for UserService list operations."""

    @pytest.mark.asyncio
    async def test_list_users_success(self, mock_client):
        """Test listing users."""
        mock_client.list_users.return_value = {
            "users": [
                {"username": "user1", "email": "user1@example.com", "groups": ["FRANK_OBSERVER"]},
                {"username": "user2", "email": "user2@example.com", "groups": ["FRANK_CONTRIBUTOR"]},
            ],
            "total": 2,
        }

        service = UserService(mock_client)
        result = await service.list_users("org-123")

        assert result.success is True
        assert isinstance(result.data, UserListResult)
        assert len(result.data.users) == 2

    @pytest.mark.asyncio
    async def test_list_users_empty_org_id(self, mock_client):
        """Test listing users with empty org ID."""
        service = UserService(mock_client)
        result = await service.list_users("")

        assert result.success is False
        assert "required" in result.error.lower()
        mock_client.list_users.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_users_org_not_found(self, mock_client):
        """Test listing users for non-existent org."""
        mock_client.list_users.side_effect = NotFoundError("Not found", 404)

        service = UserService(mock_client)
        result = await service.list_users("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()


class TestUserServiceGet:
    """Tests for UserService get operations."""

    @pytest.mark.asyncio
    async def test_get_user_success(self, mock_client):
        """Test getting a user."""
        mock_client.get_user.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "groups": ["FRANK_OBSERVER"],
            "enabled": True,
        }

        service = UserService(mock_client)
        result = await service.get_user("testuser")

        assert result.success is True
        assert isinstance(result.data, UserDTO)
        assert result.data.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_empty_username(self, mock_client):
        """Test getting user with empty username."""
        service = UserService(mock_client)
        result = await service.get_user("")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, mock_client):
        """Test getting non-existent user."""
        mock_client.get_user.side_effect = NotFoundError("Not found", 404)

        service = UserService(mock_client)
        result = await service.get_user("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()


class TestUserServiceCreate:
    """Tests for UserService create operations."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_client):
        """Test creating a user."""
        mock_client.create_user.return_value = {
            "username": "newuser",
            "email": "new@example.com",
            "groups": ["FRANK_OBSERVER"],
        }

        service = UserService(mock_client)
        result = await service.create_user(
            organisation_id="org-123",
            username="newuser",
            email="new@example.com",
            password="SecurePass123!",
            groups=["FRANK_OBSERVER"],
        )

        assert result.success is True
        assert result.data.username == "newuser"

    @pytest.mark.asyncio
    async def test_create_user_empty_org_id(self, mock_client):
        """Test creating user with empty org ID."""
        service = UserService(mock_client)
        result = await service.create_user(
            organisation_id="",
            username="newuser",
            email="new@example.com",
        )

        assert result.success is False
        assert "organisation" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_user_empty_username(self, mock_client):
        """Test creating user with empty username."""
        service = UserService(mock_client)
        result = await service.create_user(
            organisation_id="org-123",
            username="",
            email="new@example.com",
        )

        assert result.success is False
        assert "username" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_user_empty_email(self, mock_client):
        """Test creating user with empty email."""
        service = UserService(mock_client)
        result = await service.create_user(
            organisation_id="org-123",
            username="newuser",
            email="",
        )

        assert result.success is False
        assert "email" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_user_invalid_email(self, mock_client):
        """Test creating user with invalid email."""
        service = UserService(mock_client)
        result = await service.create_user(
            organisation_id="org-123",
            username="newuser",
            email="not-an-email",
        )

        assert result.success is False
        assert "email" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_user_invalid_groups(self, mock_client):
        """Test creating user with invalid groups."""
        service = UserService(mock_client)
        result = await service.create_user(
            organisation_id="org-123",
            username="newuser",
            email="new@example.com",
            groups=["INVALID_GROUP"],
        )

        assert result.success is False
        assert "invalid groups" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_user_conflict(self, mock_client):
        """Test creating duplicate user."""
        mock_client.create_user.side_effect = ConflictError("Already exists", 409)

        service = UserService(mock_client)
        result = await service.create_user(
            organisation_id="org-123",
            username="existing",
            email="existing@example.com",
        )

        assert result.success is False
        assert "already exists" in result.error.lower()


class TestUserServiceUpdate:
    """Tests for UserService update operations."""

    @pytest.mark.asyncio
    async def test_update_user_success(self, mock_client):
        """Test updating a user."""
        mock_client.update_user.return_value = {
            "username": "testuser",
            "email": "updated@example.com",
            "enabled": True,
        }

        service = UserService(mock_client)
        result = await service.update_user("testuser", email="updated@example.com")

        assert result.success is True
        assert result.data.email == "updated@example.com"

    @pytest.mark.asyncio
    async def test_update_user_empty_username(self, mock_client):
        """Test updating with empty username."""
        service = UserService(mock_client)
        result = await service.update_user("", email="new@example.com")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_update_user_no_fields(self, mock_client):
        """Test updating with no fields."""
        service = UserService(mock_client)
        result = await service.update_user("testuser")

        assert result.success is False
        assert "no fields" in result.error.lower()

    @pytest.mark.asyncio
    async def test_update_user_invalid_email(self, mock_client):
        """Test updating with invalid email."""
        service = UserService(mock_client)
        result = await service.update_user("testuser", email="not-an-email")

        assert result.success is False
        assert "email" in result.error.lower()

    @pytest.mark.asyncio
    async def test_update_user_invalid_groups(self, mock_client):
        """Test updating with invalid groups."""
        service = UserService(mock_client)
        result = await service.update_user("testuser", groups=["INVALID"])

        assert result.success is False
        assert "invalid groups" in result.error.lower()

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, mock_client):
        """Test updating non-existent user."""
        mock_client.update_user.side_effect = NotFoundError("Not found", 404)

        service = UserService(mock_client)
        result = await service.update_user("nonexistent", email="new@example.com")

        assert result.success is False
        assert "not found" in result.error.lower()


class TestUserServiceDelete:
    """Tests for UserService delete operations."""

    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_client):
        """Test deleting a user."""
        mock_client.delete_user.return_value = None

        service = UserService(mock_client)
        result = await service.delete_user("testuser")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_delete_user_empty_username(self, mock_client):
        """Test deleting with empty username."""
        service = UserService(mock_client)
        result = await service.delete_user("")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, mock_client):
        """Test deleting non-existent user."""
        mock_client.delete_user.side_effect = NotFoundError("Not found", 404)

        service = UserService(mock_client)
        result = await service.delete_user("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()


class TestUserServiceHelpers:
    """Tests for UserService helper methods."""

    @pytest.mark.asyncio
    async def test_disable_user(self, mock_client):
        """Test disabling a user."""
        mock_client.update_user.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "enabled": False,
        }

        service = UserService(mock_client)
        result = await service.disable_user("testuser")

        assert result.success is True
        mock_client.update_user.assert_called_once_with(
            username="testuser",
            email=None,
            enabled=False,
            groups=None,
        )

    @pytest.mark.asyncio
    async def test_enable_user(self, mock_client):
        """Test enabling a user."""
        mock_client.update_user.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "enabled": True,
        }

        service = UserService(mock_client)
        result = await service.enable_user("testuser")

        assert result.success is True
        mock_client.update_user.assert_called_once_with(
            username="testuser",
            email=None,
            enabled=True,
            groups=None,
        )

    def test_parse_groups(self, mock_client):
        """Test parsing groups string."""
        service = UserService(mock_client)

        assert service.parse_groups("FRANK_OBSERVER, FRANK_CONTRIBUTOR") == [
            "FRANK_OBSERVER",
            "FRANK_CONTRIBUTOR",
        ]

    def test_parse_groups_empty(self, mock_client):
        """Test parsing empty groups string."""
        service = UserService(mock_client)

        assert service.parse_groups("") == []

    def test_parse_groups_with_whitespace(self, mock_client):
        """Test parsing groups with extra whitespace."""
        service = UserService(mock_client)

        assert service.parse_groups("  FRANK_OBSERVER  ,  FRANK_CONTRIBUTOR  ") == [
            "FRANK_OBSERVER",
            "FRANK_CONTRIBUTOR",
        ]
