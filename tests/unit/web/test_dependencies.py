#!/usr/bin/env python3
"""
Unit tests for frank.web.dependencies module.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from frank.web.app import create_web_app
from frank.web.config import WebConfig
from frank.web.dependencies import get_current_session


@pytest.fixture
def web_config():
    """Create test web configuration."""
    WebConfig.reset()
    config = WebConfig.configure(
        management_api_url="http://test-api.example.com",
        cognito_url="http://test-cognito.example.com",
        session_secret_key="test-secret-key-" + ("x" * 32),
    )
    yield config
    WebConfig.reset()


@pytest.fixture
def app(web_config):
    """Create test FastAPI app."""
    return create_web_app(config=web_config)


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestGetCurrentSession:
    """Test get_current_session dependency."""

    def test_valid_session_allows_access(self, app, web_config):
        """Test that valid session allows access to protected endpoints."""
        from frank.web.middleware.session import SessionManager
        from fastapi import Response

        session_manager = SessionManager(web_config)
        client = TestClient(app)

        # Create a valid session
        mock_response = Response()
        session_manager.create_session(
            response=mock_response,
            access_token="test-token-123",
            username="testuser",
            expires_in=3600,
        )

        # Extract and set the cookie
        if "set-cookie" in mock_response.headers:
            cookie_header = mock_response.headers["set-cookie"]
            cookie_parts = cookie_header.split(";")
            cookie_value = cookie_parts[0]
            client.cookies.set(
                web_config.session_cookie_name,
                cookie_value.split("=", 1)[1] if "=" in cookie_value else cookie_value,
            )

        # Access protected endpoint should work
        response = client.get("/dashboard", follow_redirects=False)

        assert response.status_code == 200
        assert "testuser" in response.text
