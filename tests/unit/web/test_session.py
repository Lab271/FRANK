#!/usr/bin/env python3
"""
Unit tests for frank.web.middleware.session module.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import pytest
from datetime import datetime, timedelta
from fastapi import Response
from unittest.mock import MagicMock

from frank.web.config import WebConfig
from frank.web.middleware.session import SessionManager, SessionData


@pytest.fixture
def web_config():
    """Create test web configuration."""
    WebConfig.reset()
    config = WebConfig.configure(
        management_api_url="http://test-api.example.com",
        cognito_url="http://test-cognito.example.com",
        session_secret_key="test-secret-key-" + ("x" * 32),
        session_cookie_name="test_session",
        session_max_age=3600,
    )
    yield config
    WebConfig.reset()


@pytest.fixture
def session_manager(web_config):
    """Create session manager."""
    return SessionManager(web_config)


class TestSessionData:
    """Test SessionData class."""

    def test_session_data_creation(self):
        """Test creating SessionData."""
        expires_at = datetime.now() + timedelta(hours=1)
        session = SessionData(
            access_token="test-token",
            username="testuser",
            expires_at=expires_at,
        )

        assert session.access_token == "test-token"
        assert session.username == "testuser"
        assert session.expires_at == expires_at
        assert session.refresh_token is None

    def test_session_data_with_refresh_token(self):
        """Test SessionData with refresh token."""
        expires_at = datetime.now() + timedelta(hours=1)
        session = SessionData(
            access_token="test-token",
            username="testuser",
            expires_at=expires_at,
            refresh_token="refresh-token-123",
        )

        assert session.refresh_token == "refresh-token-123"

    def test_session_is_not_expired(self):
        """Test that valid session is not expired."""
        from datetime import timezone
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        session = SessionData(
            access_token="test-token",
            username="testuser",
            expires_at=expires_at,
        )

        assert not session.is_expired()

    def test_session_is_expired(self):
        """Test that expired session is detected."""
        from datetime import timezone
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session = SessionData(
            access_token="test-token",
            username="testuser",
            expires_at=expires_at,
        )

        assert session.is_expired()

    def test_session_to_dict(self):
        """Test converting SessionData to dict."""
        expires_at = datetime.now() + timedelta(hours=1)
        session = SessionData(
            access_token="test-token",
            username="testuser",
            expires_at=expires_at,
            refresh_token="refresh-123",
        )

        data = session.to_dict()

        assert data["access_token"] == "test-token"
        assert data["username"] == "testuser"
        assert data["refresh_token"] == "refresh-123"
        assert "expires_at" in data
        assert isinstance(data["expires_at"], str)  # Should be ISO format

    def test_session_from_dict(self):
        """Test creating SessionData from dict."""
        expires_at = datetime.now() + timedelta(hours=1)
        data = {
            "access_token": "test-token",
            "username": "testuser",
            "expires_at": expires_at.isoformat(),
            "refresh_token": "refresh-123",
        }

        session = SessionData.from_dict(data)

        assert session.access_token == "test-token"
        assert session.username == "testuser"
        assert session.refresh_token == "refresh-123"
        assert isinstance(session.expires_at, datetime)

    def test_session_from_dict_without_refresh_token(self):
        """Test creating SessionData from dict without refresh token."""
        expires_at = datetime.now() + timedelta(hours=1)
        data = {
            "access_token": "test-token",
            "username": "testuser",
            "expires_at": expires_at.isoformat(),
        }

        session = SessionData.from_dict(data)

        assert session.access_token == "test-token"
        assert session.username == "testuser"
        assert session.refresh_token is None


class TestSessionManager:
    """Test SessionManager class."""

    def test_create_session(self, session_manager, web_config):
        """Test creating a session."""
        response = Response()

        session_manager.create_session(
            response=response,
            access_token="test-token",
            username="testuser",
            expires_in=3600,
        )

        # Check that cookie was set
        assert "set-cookie" in response.headers
        cookie_header = response.headers["set-cookie"]
        assert web_config.session_cookie_name in cookie_header
        assert "HttpOnly" in cookie_header
        assert "SameSite=lax" in cookie_header

    def test_create_session_with_refresh_token(self, session_manager, web_config):
        """Test creating a session with refresh token."""
        response = Response()

        session_manager.create_session(
            response=response,
            access_token="test-token",
            username="testuser",
            expires_in=3600,
            refresh_token="refresh-token-123",
        )

        # Cookie should be set
        assert "set-cookie" in response.headers

    def test_get_session_no_cookie(self, session_manager):
        """Test getting session when no cookie is present."""
        mock_request = MagicMock()
        mock_request.cookies = {}

        session = session_manager.get_session(mock_request)

        assert session is None

    def test_get_session_invalid_cookie(self, session_manager, web_config):
        """Test getting session with invalid encrypted cookie."""
        mock_request = MagicMock()
        mock_request.cookies = {web_config.session_cookie_name: "invalid-data"}

        session = session_manager.get_session(mock_request)

        assert session is None

    def test_get_session_valid_cookie(self, session_manager, web_config):
        """Test getting session with valid encrypted cookie."""
        # First create a session
        response = Response()
        session_manager.create_session(
            response=response,
            access_token="test-token-123",
            username="testuser",
            expires_in=3600,
        )

        # Extract the cookie value
        cookie_header = response.headers["set-cookie"]
        cookie_parts = cookie_header.split(";")
        cookie_value = cookie_parts[0].split("=", 1)[1]

        # Create mock request with the cookie
        mock_request = MagicMock()
        mock_request.cookies = {web_config.session_cookie_name: cookie_value}

        # Get the session
        session = session_manager.get_session(mock_request)

        assert session is not None
        assert session.access_token == "test-token-123"
        assert session.username == "testuser"
        assert not session.is_expired()

    def test_clear_session(self, session_manager, web_config):
        """Test clearing a session."""
        response = Response()

        session_manager.clear_session(response)

        # Check that cookie was cleared
        assert "set-cookie" in response.headers
        cookie_header = response.headers["set-cookie"]
        assert web_config.session_cookie_name in cookie_header
        assert "Max-Age=0" in cookie_header

    def test_update_session(self, session_manager, web_config):
        """Test updating a session."""
        from datetime import timezone

        # Create a session data object with new token
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        updated_session = SessionData(
            access_token="new-token",
            username="testuser",
            expires_at=expires_at,
            refresh_token="new-refresh",
        )

        # Update the session
        response = Response()
        session_manager.update_session(
            response=response,
            session=updated_session,
        )

        # Check that cookie was set
        assert "set-cookie" in response.headers

        # Verify the updated session
        cookie_header = response.headers["set-cookie"]
        cookie_parts = cookie_header.split(";")
        cookie_value = cookie_parts[0].split("=", 1)[1]

        mock_request = MagicMock()
        mock_request.cookies = {web_config.session_cookie_name: cookie_value}

        session = session_manager.get_session(mock_request)
        assert session.access_token == "new-token"
        assert session.username == "testuser"
        assert session.refresh_token == "new-refresh"
