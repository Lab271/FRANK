#!/usr/bin/env python3
"""
Tests for FRANK Admin API client.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from frank.admin.client import (
    AdminClient,
    AdminClientError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
)
from frank.admin.config import AdminConfig


@pytest.fixture(autouse=True)
def reset_config():
    """Reset AdminConfig singleton before each test."""
    AdminConfig.reset()
    yield
    AdminConfig.reset()


@pytest.fixture
def mock_keyring():
    """Mock keyring for token storage."""
    storage = {}

    with patch("frank.admin.auth.keyring") as mock:
        mock.set_password.side_effect = lambda svc, key, val: storage.update({f"{svc}:{key}": val})
        mock.get_password.side_effect = lambda svc, key: storage.get(f"{svc}:{key}")
        mock.delete_password.side_effect = lambda svc, key: storage.pop(f"{svc}:{key}", None)
        mock.errors = MagicMock()
        mock.errors.PasswordDeleteError = Exception

        yield mock, storage


class TestAdminClientErrors:
    """Tests for admin client exceptions."""

    def test_admin_client_error(self):
        """Test AdminClientError creation."""
        error = AdminClientError("Test error", 500)
        assert error.message == "Test error"
        assert error.status_code == 500

    def test_authentication_error(self):
        """Test AuthenticationError creation."""
        error = AuthenticationError("Invalid credentials", 401)
        assert "Invalid credentials" in str(error)
        assert error.status_code == 401

    def test_not_found_error(self):
        """Test NotFoundError creation."""
        error = NotFoundError("Resource not found", 404)
        assert error.status_code == 404

    def test_conflict_error(self):
        """Test ConflictError creation."""
        error = ConflictError("Already exists", 409)
        assert error.status_code == 409


class TestAdminClient:
    """Tests for AdminClient class."""

    @pytest.fixture
    def client(self, mock_keyring):
        """Create AdminClient with mocked dependencies."""
        config = AdminConfig.configure(api_endpoint="http://localhost:8001")
        return AdminClient(config=config)

    def test_init_with_config(self, mock_keyring):
        """Test client initialization with config."""
        config = AdminConfig.configure(api_endpoint="http://custom:9000")
        client = AdminClient(config=config)

        assert client.api_endpoint == "http://custom:9000"

    def test_init_with_endpoint_override(self, mock_keyring):
        """Test client initialization with endpoint override."""
        config = AdminConfig.configure(api_endpoint="http://config:8001")
        client = AdminClient(api_endpoint="http://override:9000", config=config)

        assert client.api_endpoint == "http://override:9000"

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test async context manager."""
        async with client as c:
            assert c._client is not None

        # Client should be closed after exit
        # Note: _client may still exist but is closed

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy", "database": "healthy"}

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            result = await client.health_check()

            assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_list_organisations_success(self, client):
        """Test listing organisations."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organisations": [
                {"organisation_id": "org-1", "name": "Org 1"},
                {"organisation_id": "org-2", "name": "Org 2"},
            ],
            "total": 2,
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            result = await client.list_organisations()

            assert len(result["organisations"]) == 2

    @pytest.mark.asyncio
    async def test_get_organisation_success(self, client):
        """Test getting an organisation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organisation_id": "org-123",
            "name": "Test Org",
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            result = await client.get_organisation("org-123")

            assert result["organisation_id"] == "org-123"

    @pytest.mark.asyncio
    async def test_get_organisation_not_found(self, client):
        """Test getting non-existent organisation."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            with pytest.raises(NotFoundError):
                await client.get_organisation("nonexistent")

    @pytest.mark.asyncio
    async def test_create_organisation_success(self, client):
        """Test creating an organisation."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "organisation_id": "org-new",
            "name": "New Org",
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            result = await client.create_organisation({"name": "New Org"})

            assert result["organisation_id"] == "org-new"

    @pytest.mark.asyncio
    async def test_create_organisation_conflict(self, client):
        """Test creating organisation that already exists."""
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.json.return_value = {"detail": "Organisation already exists"}

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            with pytest.raises(ConflictError):
                await client.create_organisation({"name": "Existing Org"})

    @pytest.mark.asyncio
    async def test_update_organisation_success(self, client):
        """Test updating an organisation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organisation_id": "org-123",
            "name": "Updated Org",
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            result = await client.update_organisation("org-123", {"name": "Updated Org"})

            assert result["name"] == "Updated Org"

    @pytest.mark.asyncio
    async def test_delete_organisation_success(self, client):
        """Test deleting an organisation."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            # Should not raise
            await client.delete_organisation("org-123")

    @pytest.mark.asyncio
    async def test_authentication_required(self, client):
        """Test 401 raises AuthenticationError."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            with pytest.raises(AuthenticationError):
                await client.list_organisations()

    @pytest.mark.asyncio
    async def test_access_denied(self, client):
        """Test 403 raises AuthenticationError."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            with pytest.raises(AuthenticationError):
                await client.list_organisations()

    @pytest.mark.asyncio
    async def test_connection_error(self, client):
        """Test connection error handling."""
        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(AdminClientError) as exc_info:
                await client.list_organisations()

            assert "Connection error" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_user_success(self, client):
        """Test getting a user."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "groups": ["FRANK_OBSERVER"],
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            result = await client.get_user("testuser")

            assert result["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_create_user_success(self, client):
        """Test creating a user."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "username": "newuser",
            "email": "new@example.com",
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            result = await client.create_user(
                organisation_id="org-123",
                username="newuser",
                email="new@example.com",
                password="SecurePass123!",
            )

            assert result["username"] == "newuser"

    @pytest.mark.asyncio
    async def test_update_user_success(self, client):
        """Test updating a user."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "username": "testuser",
            "email": "updated@example.com",
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            result = await client.update_user(
                username="testuser",
                email="updated@example.com",
            )

            assert result["email"] == "updated@example.com"

    @pytest.mark.asyncio
    async def test_delete_user_success(self, client):
        """Test deleting a user."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(client, "_client") as mock_client:
            mock_client.request = AsyncMock(return_value=mock_response)

            # Should not raise
            await client.delete_user("testuser")

    @pytest.mark.asyncio
    async def test_logout_clears_tokens(self, client, mock_keyring):
        """Test logout clears stored tokens."""
        mock, storage = mock_keyring

        # Store some tokens first
        client.token_manager.store_tokens(
            access_token="test-token",
            username="testuser",
            expires_in=3600,
        )

        await client.logout()

        assert client.token_manager.get_access_token() is None
