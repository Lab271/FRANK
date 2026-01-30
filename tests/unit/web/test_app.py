#!/usr/bin/env python3
"""
Unit tests for frank.web.app module.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import pytest
from fastapi.testclient import TestClient

from frank.web.app import create_web_app
from frank.web.config import WebConfig


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


class TestCreateWebApp:
    """Test create_web_app factory function."""

    def test_app_creation(self, app):
        """Test that app is created successfully."""
        assert app is not None
        assert app.title == "FRANK Web GUI"
        assert "Web-based user interface" in app.description

    def test_app_stores_config(self, app, web_config):
        """Test that config is stored in app state."""
        assert app.state.config is web_config

    def test_app_has_templates(self, app):
        """Test that templates are configured."""
        assert hasattr(app.state, "templates")
        assert app.state.templates is not None

    def test_docs_disabled(self, app):
        """Test that API docs are disabled for web GUI."""
        assert app.docs_url is None
        assert app.redoc_url is None


class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_check(self, client):
        """Test health check returns 200 and correct data."""
        response = client.get("/health")

        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "frank-web"
        assert "version" in data


class TestRootEndpoint:
    """Test root / endpoint."""

    def test_root_redirects_to_login_when_not_authenticated(self, client):
        """Test that root redirects to login when no session."""
        response = client.get("/", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_root_redirects_to_dashboard_when_authenticated(self, app, web_config):
        """Test that root redirects to dashboard with valid session."""
        from frank.web.middleware.session import SessionManager

        # Create session manager and authenticated session
        session_manager = SessionManager(web_config)

        # Create test client and mock response to set session cookie
        client = TestClient(app)

        # Get initial response to trigger session creation
        response = client.get("/login")

        # Manually create a session cookie
        from fastapi import Response
        mock_response = Response()
        session_manager.create_session(
            response=mock_response,
            access_token="test-token-123",
            username="testuser",
            expires_in=3600,
        )

        # Extract the session cookie from mock response
        if "set-cookie" in mock_response.headers:
            cookie_header = mock_response.headers["set-cookie"]
            # Extract just the cookie value
            cookie_parts = cookie_header.split(";")
            cookie_value = cookie_parts[0]

            # Set the cookie on the test client
            client.cookies.set(
                web_config.session_cookie_name,
                cookie_value.split("=", 1)[1] if "=" in cookie_value else cookie_value,
            )

        # Now test the root endpoint with authenticated session
        response = client.get("/", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"
