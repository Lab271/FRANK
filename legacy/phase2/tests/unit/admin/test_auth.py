#!/usr/bin/env python3
"""
Tests for FRANK Admin token management.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from frank.admin.auth import TokenInfo, TokenManager
from frank.admin.config import AdminConfig


@pytest.fixture(autouse=True)
def reset_config():
    """Reset AdminConfig singleton before each test."""
    AdminConfig.reset()
    yield
    AdminConfig.reset()


@pytest.fixture
def mock_keyring():
    """Mock keyring for token storage tests."""
    storage = {}

    with patch("frank.admin.auth.keyring") as mock:
        mock.set_password.side_effect = lambda svc, key, val: storage.update({f"{svc}:{key}": val})
        mock.get_password.side_effect = lambda svc, key: storage.get(f"{svc}:{key}")
        mock.delete_password.side_effect = lambda svc, key: storage.pop(f"{svc}:{key}", None)
        mock.errors = MagicMock()
        mock.errors.PasswordDeleteError = Exception

        yield mock, storage


class TestTokenInfo:
    """Tests for TokenInfo dataclass."""

    def test_creation(self):
        """Test TokenInfo creation."""
        info = TokenInfo(
            access_token="test-token",
            refresh_token="refresh-token",
            expires_at=time.time() + 3600,
            username="testuser",
        )

        assert info.access_token == "test-token"
        assert info.refresh_token == "refresh-token"
        assert info.username == "testuser"

    def test_is_expired_false(self):
        """Test is_expired returns False for valid token."""
        info = TokenInfo(
            access_token="test-token",
            refresh_token=None,
            expires_at=time.time() + 3600,
            username="testuser",
        )

        assert not info.is_expired

    def test_is_expired_true(self):
        """Test is_expired returns True for expired token."""
        info = TokenInfo(
            access_token="test-token",
            refresh_token=None,
            expires_at=time.time() - 60,
            username="testuser",
        )

        assert info.is_expired

    def test_needs_refresh_within_buffer(self):
        """Test needs_refresh returns True within buffer period."""
        AdminConfig.configure(token_refresh_buffer=5)

        info = TokenInfo(
            access_token="test-token",
            refresh_token=None,
            expires_at=time.time() + 120,  # 2 minutes until expiry (within 5 min buffer)
            username="testuser",
        )

        assert info.needs_refresh

    def test_needs_refresh_outside_buffer(self):
        """Test needs_refresh returns False outside buffer period."""
        AdminConfig.configure(token_refresh_buffer=5)

        info = TokenInfo(
            access_token="test-token",
            refresh_token=None,
            expires_at=time.time() + 600,  # 10 minutes until expiry (outside 5 min buffer)
            username="testuser",
        )

        assert not info.needs_refresh

    def test_expires_in_seconds(self):
        """Test expires_in_seconds calculation."""
        info = TokenInfo(
            access_token="test-token",
            refresh_token=None,
            expires_at=time.time() + 300,
            username="testuser",
        )

        # Should be approximately 300 seconds
        assert 298 <= info.expires_in_seconds <= 302

    def test_expires_in_seconds_expired(self):
        """Test expires_in_seconds returns 0 for expired token."""
        info = TokenInfo(
            access_token="test-token",
            refresh_token=None,
            expires_at=time.time() - 60,
            username="testuser",
        )

        assert info.expires_in_seconds == 0


class TestTokenManager:
    """Tests for TokenManager class."""

    def test_store_tokens(self, mock_keyring):
        """Test storing tokens."""
        mock, storage = mock_keyring

        manager = TokenManager()
        info = manager.store_tokens(
            access_token="access-123",
            username="testuser",
            expires_in=3600,
            refresh_token="refresh-456",
        )

        assert info.access_token == "access-123"
        assert info.username == "testuser"
        assert info.refresh_token == "refresh-456"

        # Verify stored in keyring
        assert "frank-admin:access_token" in storage
        assert storage["frank-admin:access_token"] == "access-123"

    def test_get_tokens(self, mock_keyring):
        """Test retrieving tokens."""
        mock, storage = mock_keyring

        manager = TokenManager()
        manager.store_tokens(
            access_token="access-123",
            username="testuser",
            expires_in=3600,
            refresh_token="refresh-456",
        )

        info = manager.get_tokens()

        assert info is not None
        assert info.access_token == "access-123"
        assert info.username == "testuser"
        assert info.refresh_token == "refresh-456"

    def test_get_tokens_none_when_empty(self, mock_keyring):
        """Test get_tokens returns None when no tokens stored."""
        mock, storage = mock_keyring

        manager = TokenManager()
        info = manager.get_tokens()

        assert info is None

    def test_get_access_token(self, mock_keyring):
        """Test getting just access token."""
        mock, storage = mock_keyring

        manager = TokenManager()
        manager.store_tokens(
            access_token="access-123",
            username="testuser",
            expires_in=3600,
        )

        assert manager.get_access_token() == "access-123"

    def test_get_refresh_token(self, mock_keyring):
        """Test getting just refresh token."""
        mock, storage = mock_keyring

        manager = TokenManager()
        manager.store_tokens(
            access_token="access-123",
            username="testuser",
            expires_in=3600,
            refresh_token="refresh-456",
        )

        assert manager.get_refresh_token() == "refresh-456"

    def test_clear_tokens(self, mock_keyring):
        """Test clearing tokens."""
        mock, storage = mock_keyring

        manager = TokenManager()
        manager.store_tokens(
            access_token="access-123",
            username="testuser",
            expires_in=3600,
            refresh_token="refresh-456",
        )

        manager.clear_tokens()

        assert manager.get_access_token() is None
        assert manager.get_tokens() is None

    def test_has_valid_tokens_true(self, mock_keyring):
        """Test has_valid_tokens returns True for valid tokens."""
        mock, storage = mock_keyring

        manager = TokenManager()
        manager.store_tokens(
            access_token="access-123",
            username="testuser",
            expires_in=3600,
        )

        assert manager.has_valid_tokens()

    def test_has_valid_tokens_false_expired(self, mock_keyring):
        """Test has_valid_tokens returns False for expired tokens."""
        mock, storage = mock_keyring

        manager = TokenManager()
        # Store with negative expires_in to simulate expired token
        manager.store_tokens(
            access_token="access-123",
            username="testuser",
            expires_in=-60,  # Already expired
        )

        assert not manager.has_valid_tokens()

    def test_has_valid_tokens_false_empty(self, mock_keyring):
        """Test has_valid_tokens returns False when no tokens."""
        mock, storage = mock_keyring

        manager = TokenManager()

        assert not manager.has_valid_tokens()

    def test_update_access_token(self, mock_keyring):
        """Test updating access token after refresh."""
        mock, storage = mock_keyring

        manager = TokenManager()
        manager.store_tokens(
            access_token="old-token",
            username="testuser",
            expires_in=3600,
            refresh_token="refresh-456",
        )

        info = manager.update_access_token("new-token", 7200)

        assert info.access_token == "new-token"
        assert info.refresh_token == "refresh-456"
        assert info.username == "testuser"

    def test_update_access_token_no_existing(self, mock_keyring):
        """Test update_access_token returns None when no existing tokens."""
        mock, storage = mock_keyring

        manager = TokenManager()
        info = manager.update_access_token("new-token", 3600)

        assert info is None
