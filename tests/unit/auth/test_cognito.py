#!/usr/bin/env python3
"""
Tests for FRANK Cognito validation module.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from frank.auth.cognito import (
    CognitoConnectionError,
    CognitoTimeoutError,
    CognitoUserInfo,
    CognitoValidationError,
    validate_token_with_cognito,
    validate_token_with_cognito_sync,
)
from frank.auth.config import AuthConfig


@pytest.fixture(autouse=True)
def reset_config():
    """Reset AuthConfig singleton before each test."""
    AuthConfig.reset()
    yield
    AuthConfig.reset()


@pytest.fixture
def mock_config():
    """Create config for testing."""
    return AuthConfig.configure(
        cognito_url="http://localhost:8100",
        environment="mock",
        validation_strategy="server_first",
    )


class TestCognitoUserInfo:
    """Tests for CognitoUserInfo dataclass."""

    def test_creation(self):
        """Test CognitoUserInfo creation."""
        info = CognitoUserInfo(
            username="testuser",
            validation_source="mock-cognito-getuser",
        )
        assert info.username == "testuser"
        assert info.validation_source == "mock-cognito-getuser"


class TestValidateTokenWithCognito:
    """Tests for async validate_token_with_cognito function."""

    def test_successful_validation(self, mock_config):
        """Test successful token validation with Cognito."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"Username": "testuser"}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post.return_value = mock_response

        with patch("frank.auth.cognito.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(validate_token_with_cognito("test-token", mock_config))

            assert result.username == "testuser"
            assert result.validation_source == "mock-cognito-getuser"

    def test_validation_failure(self, mock_config):
        """Test token validation failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post.return_value = mock_response

        with patch("frank.auth.cognito.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(CognitoValidationError, match="status 401"):
                asyncio.run(validate_token_with_cognito("test-token", mock_config))

    def test_connection_error(self, mock_config):
        """Test handling of connection errors."""
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post.side_effect = httpx.ConnectError("Connection refused")

        with patch("frank.auth.cognito.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(CognitoConnectionError, match="Could not connect"):
                asyncio.run(validate_token_with_cognito("test-token", mock_config))

    def test_timeout_error(self, mock_config):
        """Test handling of timeout errors."""
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post.side_effect = httpx.TimeoutException("Timeout")

        with patch("frank.auth.cognito.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(CognitoTimeoutError, match="timed out"):
                asyncio.run(validate_token_with_cognito("test-token", mock_config))

    def test_uses_correct_headers(self, mock_config):
        """Test that correct AWS headers are sent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"Username": "testuser"}

        mock_post = AsyncMock(return_value=mock_response)
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = mock_post

        with patch("frank.auth.cognito.httpx.AsyncClient", return_value=mock_client):
            asyncio.run(validate_token_with_cognito("test-token", mock_config))

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["headers"]["X-Amz-Target"] == "AWSCognitoIdentityProviderService.GetUser"
            assert call_kwargs["headers"]["Content-Type"] == "application/x-amz-json-1.1"
            assert call_kwargs["json"] == {"AccessToken": "test-token"}

    def test_uses_singleton_config_when_not_provided(self, mock_config):
        """Test that singleton config is used when config not provided."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"Username": "testuser"}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post.return_value = mock_response

        with patch("frank.auth.cognito.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(validate_token_with_cognito("test-token"))

            assert result.username == "testuser"

    def test_aws_environment_validation_source(self):
        """Test that AWS environment shows correct validation source."""
        config = AuthConfig.configure(
            environment="aws",
            region="eu-west-1",
            user_pool_id="test-pool",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"Username": "testuser"}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post.return_value = mock_response

        with patch("frank.auth.cognito.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(validate_token_with_cognito("test-token", config))

            assert result.validation_source == "aws-cognito-getuser"


class TestValidateTokenWithCognitoSync:
    """Tests for sync validate_token_with_cognito_sync function."""

    def test_successful_validation(self, mock_config):
        """Test successful sync token validation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"Username": "testuser"}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response

        with patch("frank.auth.cognito.httpx.Client", return_value=mock_client):
            result = validate_token_with_cognito_sync("test-token", mock_config)

            assert result.username == "testuser"
            assert result.validation_source == "mock-cognito-getuser"

    def test_connection_error(self, mock_config):
        """Test handling of connection errors in sync version."""
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.side_effect = httpx.ConnectError("Connection refused")

        with patch("frank.auth.cognito.httpx.Client", return_value=mock_client):
            with pytest.raises(CognitoConnectionError, match="Could not connect"):
                validate_token_with_cognito_sync("test-token", mock_config)

    def test_timeout_error(self, mock_config):
        """Test handling of timeout errors in sync version."""
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.side_effect = httpx.TimeoutException("Timeout")

        with patch("frank.auth.cognito.httpx.Client", return_value=mock_client):
            with pytest.raises(CognitoTimeoutError, match="timed out"):
                validate_token_with_cognito_sync("test-token", mock_config)

    def test_validation_failure(self, mock_config):
        """Test token validation failure in sync version."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response

        with patch("frank.auth.cognito.httpx.Client", return_value=mock_client):
            with pytest.raises(CognitoValidationError, match="status 403"):
                validate_token_with_cognito_sync("test-token", mock_config)
