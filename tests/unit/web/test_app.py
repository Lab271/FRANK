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

    def test_root_returns_html(self, client):
        """Test that root endpoint returns HTML."""
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_root_contains_title(self, client):
        """Test that root page contains expected title."""
        response = client.get("/")

        assert "FRANK Web GUI" in response.text

    def test_root_contains_version(self, client):
        """Test that root page contains version info."""
        response = client.get("/")

        assert "0.9.3" in response.text or "version" in response.text.lower()

    def test_root_contains_features(self, client):
        """Test that root page lists key features."""
        response = client.get("/")

        assert "Organisation Management" in response.text
        assert "User Management" in response.text
        assert "API Key Management" in response.text
        assert "MFA Security" in response.text
