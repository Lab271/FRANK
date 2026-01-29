#!/usr/bin/env python3
"""
Tests for FRANK Admin AuthService.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from frank.admin.client import AdminClientError, AuthenticationError
from frank.admin.config import AdminConfig
from frank.admin.services.auth_service import AuthResult, AuthService


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
    client.login = AsyncMock()
    client.logout = AsyncMock()
    client.token_manager = MagicMock()
    return client


class TestAuthResult:
    """Tests for AuthResult dataclass."""

    def test_success_result(self):
        """Test creating success result."""
        result = AuthResult.success_result(username="testuser", expires_in=3600)

        assert result.success is True
        assert result.username == "testuser"
        assert result.expires_in == 3600
        assert result.error is None

    def test_failure_result(self):
        """Test creating failure result."""
        result = AuthResult.failure_result(error="Invalid credentials")

        assert result.success is False
        assert result.error == "Invalid credentials"
        assert result.username is None


class TestAuthService:
    """Tests for AuthService."""

    def test_init(self, mock_client):
        """Test service initialization."""
        service = AuthService(mock_client)
        assert service.client is mock_client

    @pytest.mark.asyncio
    async def test_login_success(self, mock_client):
        """Test successful login."""
        mock_client.login.return_value = {
            "access_token": "test-token",
            "expires_in": 3600,
        }

        service = AuthService(mock_client)
        result = await service.login("testuser", "password123")

        assert result.success is True
        assert result.username == "testuser"
        assert result.expires_in == 3600
        mock_client.login.assert_called_once_with("testuser", "password123")

    @pytest.mark.asyncio
    async def test_login_empty_username(self, mock_client):
        """Test login with empty username."""
        service = AuthService(mock_client)
        result = await service.login("", "password123")

        assert result.success is False
        assert "required" in result.error.lower()
        mock_client.login.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_empty_password(self, mock_client):
        """Test login with empty password."""
        service = AuthService(mock_client)
        result = await service.login("testuser", "")

        assert result.success is False
        assert "required" in result.error.lower()
        mock_client.login.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_authentication_error(self, mock_client):
        """Test login with invalid credentials."""
        mock_client.login.side_effect = AuthenticationError("Invalid credentials", 401)

        service = AuthService(mock_client)
        result = await service.login("testuser", "wrongpassword")

        assert result.success is False
        assert "invalid" in result.error.lower()

    @pytest.mark.asyncio
    async def test_login_connection_error(self, mock_client):
        """Test login with connection error."""
        mock_client.login.side_effect = AdminClientError("Connection refused")

        service = AuthService(mock_client)
        result = await service.login("testuser", "password123")

        assert result.success is False
        assert "connection" in result.error.lower()

    @pytest.mark.asyncio
    async def test_login_unexpected_error(self, mock_client):
        """Test login with unexpected error."""
        mock_client.login.side_effect = Exception("Unexpected error")

        service = AuthService(mock_client)
        result = await service.login("testuser", "password123")

        assert result.success is False
        assert "unexpected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_logout(self, mock_client):
        """Test logout."""
        service = AuthService(mock_client)
        await service.logout()

        mock_client.logout.assert_called_once()

    def test_is_authenticated_true(self, mock_client):
        """Test is_authenticated when tokens valid."""
        mock_client.token_manager.has_valid_tokens.return_value = True

        service = AuthService(mock_client)
        assert service.is_authenticated() is True

    def test_is_authenticated_false(self, mock_client):
        """Test is_authenticated when no tokens."""
        mock_client.token_manager.has_valid_tokens.return_value = False

        service = AuthService(mock_client)
        assert service.is_authenticated() is False

    def test_get_current_user_authenticated(self, mock_client):
        """Test get_current_user when authenticated."""
        mock_tokens = MagicMock()
        mock_tokens.username = "testuser"
        mock_client.token_manager.get_tokens.return_value = mock_tokens

        service = AuthService(mock_client)
        assert service.get_current_user() == "testuser"

    def test_get_current_user_not_authenticated(self, mock_client):
        """Test get_current_user when not authenticated."""
        mock_client.token_manager.get_tokens.return_value = None

        service = AuthService(mock_client)
        assert service.get_current_user() is None

    def test_token_needs_refresh_true(self, mock_client):
        """Test token_needs_refresh when refresh needed."""
        mock_tokens = MagicMock()
        mock_tokens.needs_refresh = True
        mock_client.token_manager.get_tokens.return_value = mock_tokens

        service = AuthService(mock_client)
        assert service.token_needs_refresh() is True

    def test_token_needs_refresh_false(self, mock_client):
        """Test token_needs_refresh when no refresh needed."""
        mock_tokens = MagicMock()
        mock_tokens.needs_refresh = False
        mock_client.token_manager.get_tokens.return_value = mock_tokens

        service = AuthService(mock_client)
        assert service.token_needs_refresh() is False

    def test_token_needs_refresh_no_tokens(self, mock_client):
        """Test token_needs_refresh when no tokens."""
        mock_client.token_manager.get_tokens.return_value = None

        service = AuthService(mock_client)
        assert service.token_needs_refresh() is False
