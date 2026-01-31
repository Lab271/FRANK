#!/usr/bin/env python3
"""
Tests for FRANK auth configuration module.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
from unittest.mock import patch

import pytest

from frank.auth.config import AuthConfig


@pytest.fixture(autouse=True)
def reset_config():
    """Reset AuthConfig singleton before each test."""
    AuthConfig.reset()
    yield
    AuthConfig.reset()


class TestAuthConfig:
    """Tests for AuthConfig class."""

    def test_configure_with_defaults(self):
        """Test configuration with default values."""
        config = AuthConfig.configure()

        assert config.cognito_url == "http://localhost:8100/"
        assert config.jwt_secret == "mock-cognito-secret-key"
        assert config.jwt_algorithm == "HS256"
        assert config.validation_strategy == "local_only"
        assert config.region == "eu-west-1"
        assert config.user_pool_id == "eu-west-1_MOCKPOOL"
        assert config.environment == "mock"

    def test_configure_with_explicit_values(self):
        """Test configuration with explicit values."""
        config = AuthConfig.configure(
            cognito_url="http://custom:9000",
            jwt_secret="custom-secret",
            jwt_algorithm="HS256",
            validation_strategy="server_first",
            region="us-east-1",
            user_pool_id="us-east-1_TESTPOOL",
            environment="mock",
        )

        assert config.cognito_url == "http://custom:9000/"
        assert config.jwt_secret == "custom-secret"
        assert config.jwt_algorithm == "HS256"
        assert config.validation_strategy == "server_first"
        assert config.region == "us-east-1"
        assert config.user_pool_id == "us-east-1_TESTPOOL"

    def test_configure_from_environment(self):
        """Test configuration from environment variables."""
        env_vars = {
            "COGNITO_URL": "http://env-cognito:8200",
            "JWT_SECRET": "env-secret",
            "JWT_ALGORITHM": "HS256",
            "VALIDATION_STRATEGY": "server_only",
            "REGION": "eu-central-1",
            "USER_POOL_ID": "eu-central-1_ENVPOOL",
            "ENVIRONMENT": "mock",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            AuthConfig.reset()
            config = AuthConfig.configure()

            assert config.cognito_url == "http://env-cognito:8200/"
            assert config.jwt_secret == "env-secret"
            assert config.jwt_algorithm == "HS256"
            assert config.validation_strategy == "server_only"
            assert config.region == "eu-central-1"
            assert config.user_pool_id == "eu-central-1_ENVPOOL"

    def test_aws_environment_constructs_cognito_url(self):
        """Test that AWS environment constructs proper Cognito URL."""
        config = AuthConfig.configure(
            environment="aws",
            region="eu-west-1",
            user_pool_id="eu-west-1_TESTPOOL",
        )

        assert config.cognito_url == "https://cognito-idp.eu-west-1.amazonaws.com/"
        assert config.jwks_url == "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_TESTPOOL/.well-known/jwks.json"

    def test_jwks_url_construction(self):
        """Test JWKS URL is properly constructed."""
        config = AuthConfig.configure(
            cognito_url="http://localhost:8100",
            user_pool_id="test-pool",
        )

        assert config.jwks_url == "http://localhost:8100/test-pool/.well-known/jwks.json"

    def test_singleton_pattern(self):
        """Test that AuthConfig follows singleton pattern."""
        config1 = AuthConfig.configure(jwt_secret="first")
        config2 = AuthConfig.get()

        assert config1 is config2
        assert config1.jwt_secret == "first"

    def test_get_creates_instance_if_needed(self):
        """Test that get() creates instance with defaults if not configured."""
        config = AuthConfig.get()

        assert config is not None
        assert config.environment == "mock"

    def test_reset_clears_instance(self):
        """Test that reset() clears the singleton."""
        AuthConfig.configure(jwt_secret="test")
        AuthConfig.reset()

        # Should create new instance with defaults
        config = AuthConfig.get()
        assert config.jwt_secret == "mock-cognito-secret-key"

    def test_invalid_cognito_url_raises_error(self):
        """Test that invalid Cognito URL raises ValueError."""
        with pytest.raises(ValueError, match="Invalid Cognito URL"):
            AuthConfig.configure(cognito_url="not-a-url")

    def test_invalid_validation_strategy_raises_error(self):
        """Test that invalid validation strategy raises ValueError."""
        with pytest.raises(ValueError, match="Invalid validation strategy"):
            AuthConfig(
                cognito_url="http://localhost:8100",
                jwt_secret="secret",
                jwt_algorithm="RS256",
                validation_strategy="invalid",  # type: ignore[arg-type]
                region="eu-west-1",
                user_pool_id="pool",
                environment="mock",
            )

    def test_invalid_jwt_algorithm_raises_error(self):
        """Test that invalid JWT algorithm raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported JWT algorithm"):
            AuthConfig(
                cognito_url="http://localhost:8100",
                jwt_secret="secret",
                jwt_algorithm="RS512",  # type: ignore[arg-type]
                validation_strategy="local_only",
                region="eu-west-1",
                user_pool_id="pool",
                environment="mock",
            )

    def test_repr(self):
        """Test string representation."""
        config = AuthConfig.configure(
            environment="aws",
            validation_strategy="server_first",
            jwt_algorithm="RS256",
            region="eu-west-1",
        )

        repr_str = repr(config)
        assert "aws" in repr_str
        assert "server_first" in repr_str
        assert "RS256" in repr_str
        assert "eu-west-1" in repr_str

    def test_cognito_url_trailing_slash_handling(self):
        """Test that URLs are normalized with trailing slash."""
        config1 = AuthConfig.configure(cognito_url="http://localhost:8100")
        assert config1.cognito_url == "http://localhost:8100/"

        AuthConfig.reset()
        config2 = AuthConfig.configure(cognito_url="http://localhost:8100/")
        assert config2.cognito_url == "http://localhost:8100/"

    def test_aws_region_env_var_fallback(self):
        """Test that AWS_REGION takes precedence over REGION."""
        with patch.dict(os.environ, {"AWS_REGION": "us-west-2", "REGION": "eu-west-1"}, clear=False):
            AuthConfig.reset()
            config = AuthConfig.configure()
            assert config.region == "us-west-2"
