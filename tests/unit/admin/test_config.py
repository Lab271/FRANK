#!/usr/bin/env python3
"""
Tests for FRANK Admin configuration.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
from unittest.mock import patch

import pytest

from frank.admin.config import AdminConfig


@pytest.fixture(autouse=True)
def reset_config():
    """Reset AdminConfig singleton before each test."""
    AdminConfig.reset()
    yield
    AdminConfig.reset()


class TestAdminConfig:
    """Tests for AdminConfig class."""

    def test_configure_with_defaults(self):
        """Test configuration with default values."""
        config = AdminConfig.configure()

        assert config.api_endpoint == "http://localhost:8001"
        assert config.keyring_service == "frank-admin"
        assert config.token_refresh_buffer == 5
        assert config.timeout == 30.0

    def test_configure_with_explicit_values(self):
        """Test configuration with explicit values."""
        config = AdminConfig.configure(
            api_endpoint="http://custom:9000",
            keyring_service="custom-service",
            token_refresh_buffer=10,
            timeout=60.0,
        )

        assert config.api_endpoint == "http://custom:9000"
        assert config.keyring_service == "custom-service"
        assert config.token_refresh_buffer == 10
        assert config.timeout == 60.0

    def test_configure_from_environment(self):
        """Test configuration from environment variables."""
        env_vars = {
            "FRANK_API_ENDPOINT": "http://env-api:8080",
            "FRANK_KEYRING_SERVICE": "env-service",
            "FRANK_TOKEN_REFRESH_BUFFER": "15",
            "FRANK_API_TIMEOUT": "45.0",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            AdminConfig.reset()
            config = AdminConfig.configure()

            assert config.api_endpoint == "http://env-api:8080"
            assert config.keyring_service == "env-service"
            assert config.token_refresh_buffer == 15
            assert config.timeout == 45.0

    def test_singleton_pattern(self):
        """Test that AdminConfig follows singleton pattern."""
        config1 = AdminConfig.configure(api_endpoint="http://first:8001")
        config2 = AdminConfig.get()

        assert config1 is config2
        assert config1.api_endpoint == "http://first:8001"

    def test_get_creates_instance_if_needed(self):
        """Test that get() creates instance with defaults if not configured."""
        config = AdminConfig.get()

        assert config is not None
        assert config.api_endpoint == "http://localhost:8001"

    def test_reset_clears_instance(self):
        """Test that reset() clears the singleton."""
        AdminConfig.configure(api_endpoint="http://test:8001")
        AdminConfig.reset()

        # Should create new instance with defaults
        config = AdminConfig.get()
        assert config.api_endpoint == "http://localhost:8001"

    def test_invalid_api_endpoint_raises_error(self):
        """Test that invalid API endpoint raises ValueError."""
        with pytest.raises(ValueError, match="Invalid API endpoint"):
            AdminConfig.configure(api_endpoint="not-a-url")

    def test_api_endpoint_trailing_slash_removed(self):
        """Test that trailing slash is removed from API endpoint."""
        config = AdminConfig.configure(api_endpoint="http://localhost:8001/")
        assert config.api_endpoint == "http://localhost:8001"

    def test_repr(self):
        """Test string representation."""
        config = AdminConfig.configure(
            api_endpoint="http://localhost:8001",
            keyring_service="test-service",
            token_refresh_buffer=5,
            timeout=30.0,
        )

        repr_str = repr(config)
        assert "localhost:8001" in repr_str
        assert "test-service" in repr_str
        assert "5m" in repr_str
        assert "30.0s" in repr_str
