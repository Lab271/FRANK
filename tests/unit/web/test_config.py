#!/usr/bin/env python3
"""
Unit tests for frank.web.config module.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
import pytest

from frank.web.config import WebConfig


@pytest.fixture(autouse=True)
def reset_config():
    """Reset WebConfig singleton before each test."""
    WebConfig.reset()
    yield
    WebConfig.reset()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Clean environment variables before each test."""
    env_vars = [
        "FRANK_MANAGEMENT_API_URL",
        "COGNITO_URL",
        "FRANK_SESSION_SECRET",
        "FRANK_SESSION_COOKIE_NAME",
        "FRANK_SESSION_MAX_AGE",
        "FRANK_API_TIMEOUT",
        "TEMPLATE_AUTO_RELOAD",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


class TestWebConfig:
    """Test WebConfig class."""

    def test_default_configuration(self):
        """Test default configuration values."""
        config = WebConfig.configure()

        assert config.management_api_url == "http://localhost:8001"
        assert config.cognito_url == "http://localhost:8100"
        assert config.session_cookie_name == "frank_session"
        assert config.session_max_age == 3600
        assert config.timeout == 30.0
        assert config.template_auto_reload is False
        assert len(config.session_secret_key) >= 32

    def test_custom_configuration(self):
        """Test configuration with custom values."""
        config = WebConfig.configure(
            management_api_url="http://api.example.com",
            cognito_url="http://cognito.example.com",
            session_secret_key="a" * 32,
            session_cookie_name="my_session",
            session_max_age=7200,
            timeout=60.0,
            template_auto_reload=True,
        )

        assert config.management_api_url == "http://api.example.com"
        assert config.cognito_url == "http://cognito.example.com"
        assert config.session_secret_key == "a" * 32
        assert config.session_cookie_name == "my_session"
        assert config.session_max_age == 7200
        assert config.timeout == 60.0
        assert config.template_auto_reload is True

    def test_environment_variables(self, monkeypatch):
        """Test configuration from environment variables."""
        monkeypatch.setenv("FRANK_MANAGEMENT_API_URL", "http://env-api.example.com")
        monkeypatch.setenv("COGNITO_URL", "http://env-cognito.example.com")
        monkeypatch.setenv("FRANK_SESSION_SECRET", "b" * 32)
        monkeypatch.setenv("FRANK_SESSION_COOKIE_NAME", "env_session")
        monkeypatch.setenv("FRANK_SESSION_MAX_AGE", "1800")
        monkeypatch.setenv("FRANK_API_TIMEOUT", "45.0")
        monkeypatch.setenv("TEMPLATE_AUTO_RELOAD", "true")

        config = WebConfig.configure()

        assert config.management_api_url == "http://env-api.example.com"
        assert config.cognito_url == "http://env-cognito.example.com"
        assert config.session_secret_key == "b" * 32
        assert config.session_cookie_name == "env_session"
        assert config.session_max_age == 1800
        assert config.timeout == 45.0
        assert config.template_auto_reload is True

    def test_url_normalization(self):
        """Test that trailing slashes are removed from URLs."""
        config = WebConfig.configure(
            management_api_url="http://api.example.com/",
            cognito_url="http://cognito.example.com/",
            session_secret_key="c" * 32,
        )

        assert config.management_api_url == "http://api.example.com"
        assert config.cognito_url == "http://cognito.example.com"

    def test_invalid_management_api_url(self):
        """Test validation of invalid Management API URL."""
        with pytest.raises(ValueError, match="Invalid Management API URL"):
            WebConfig.configure(
                management_api_url="not-a-url",
                session_secret_key="d" * 32,
            )

    def test_invalid_cognito_url(self):
        """Test validation of invalid Cognito URL."""
        with pytest.raises(ValueError, match="Invalid Cognito URL"):
            WebConfig.configure(
                cognito_url="not-a-url",
                session_secret_key="e" * 32,
            )

    def test_short_session_secret(self):
        """Test validation of session secret key length."""
        with pytest.raises(ValueError, match="Session secret key must be at least 32 characters"):
            WebConfig.configure(session_secret_key="short")

    def test_singleton_pattern(self):
        """Test that WebConfig follows singleton pattern."""
        config1 = WebConfig.configure(session_secret_key="f" * 32)
        config2 = WebConfig.get()

        assert config1 is config2
        assert WebConfig._instance is config1

    def test_get_before_configure(self):
        """Test that get() creates default config if not configured."""
        config = WebConfig.get()

        assert config is not None
        assert config.management_api_url == "http://localhost:8001"

    def test_reset(self):
        """Test configuration reset."""
        config1 = WebConfig.configure(session_secret_key="g" * 32)
        WebConfig.reset()
        config2 = WebConfig.get()

        assert config1 is not config2
        assert WebConfig._instance is config2

    def test_repr(self):
        """Test string representation."""
        config = WebConfig.configure(
            management_api_url="http://api.example.com",
            session_secret_key="h" * 32,
        )

        repr_str = repr(config)

        assert "WebConfig" in repr_str
        assert "http://api.example.com" in repr_str
        assert "frank_session" in repr_str
        assert "3600s" in repr_str
