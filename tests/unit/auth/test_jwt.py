#!/usr/bin/env python3
"""
Tests for FRANK JWT validation module.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest

from frank.auth.config import AuthConfig
from frank.auth.jwt import (
    InvalidTokenError,
    TokenExpiredError,
    TokenPayload,
    get_access_tier_from_groups,
    validate_token_locally,
)
from frank.core.enum import AccessTier


@pytest.fixture(autouse=True)
def reset_config():
    """Reset AuthConfig singleton before each test."""
    AuthConfig.reset()
    yield
    AuthConfig.reset()


@pytest.fixture
def hs256_config():
    """Create config for HS256 testing."""
    return AuthConfig.configure(
        jwt_algorithm="HS256",
        jwt_secret="test-secret-key",
        validation_strategy="local_only",
    )


def create_hs256_token(
    username: str,
    groups: list[str] | None = None,
    secret: str = "test-secret-key",
    expired: bool = False,
) -> str:
    """Create a test HS256 JWT token."""
    now = datetime.now(timezone.utc)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=1)

    payload = {
        "username": username,
        "cognito:groups": groups or [],
        "iat": now,
        "exp": exp,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


class TestGetAccessTierFromGroups:
    """Tests for get_access_tier_from_groups function."""

    def test_empty_groups_returns_public(self):
        """Empty groups list should return PUBLIC tier."""
        assert get_access_tier_from_groups([]) == AccessTier.PUBLIC

    def test_none_groups_returns_public(self):
        """None groups should return PUBLIC tier."""
        assert get_access_tier_from_groups(None) == AccessTier.PUBLIC  # type: ignore[arg-type]

    def test_observer_group(self):
        """Observer group should return OBSERVER tier."""
        assert get_access_tier_from_groups(["observer"]) == AccessTier.OBSERVER

    def test_contributor_group(self):
        """Contributor group should return CONTRIBUTOR tier."""
        assert get_access_tier_from_groups(["contributor"]) == AccessTier.CONTRIBUTOR

    def test_partner_group(self):
        """Partner group should return PARTNER tier."""
        assert get_access_tier_from_groups(["partner"]) == AccessTier.PARTNER

    def test_core_member_group(self):
        """Core member group should return CORE_MEMBER tier."""
        assert get_access_tier_from_groups(["core_member"]) == AccessTier.CORE_MEMBER

    def test_first_group_takes_precedence(self):
        """First group in list should determine tier."""
        assert get_access_tier_from_groups(["partner", "observer"]) == AccessTier.PARTNER

    def test_unknown_group_returns_public(self):
        """Unknown group should return PUBLIC tier (default behavior)."""
        assert get_access_tier_from_groups(["unknown_group"]) == AccessTier.PUBLIC

    def test_case_insensitive_matching(self):
        """Group matching should be case-insensitive."""
        assert get_access_tier_from_groups(["CONTRIBUTOR"]) == AccessTier.CONTRIBUTOR
        assert get_access_tier_from_groups(["Partner"]) == AccessTier.PARTNER


class TestTokenPayload:
    """Tests for TokenPayload dataclass."""

    def test_token_valid_property(self):
        """Test token_valid property returns True when username exists."""
        payload = TokenPayload(
            username="testuser",
            groups=["observer"],
            access_tier=AccessTier.OBSERVER,
            organisation_id="org-testuser",
        )
        assert payload.token_valid is True

    def test_token_invalid_when_no_username(self):
        """Test token_valid returns False when username is empty."""
        payload = TokenPayload(
            username="",
            groups=[],
            access_tier=AccessTier.PUBLIC,
            organisation_id="",
        )
        assert payload.token_valid is False

    def test_default_validation_source(self):
        """Test default validation source is local_jwt."""
        payload = TokenPayload(
            username="testuser",
            groups=[],
            access_tier=AccessTier.PUBLIC,
            organisation_id="org-testuser",
        )
        assert payload.validation_source == "local_jwt"


class TestValidateTokenLocallyHS256:
    """Tests for validate_token_locally with HS256 algorithm."""

    def test_valid_token(self, hs256_config):
        """Test validation of valid HS256 token."""
        token = create_hs256_token("testuser", ["contributor"])

        result = validate_token_locally(token, hs256_config)

        assert result.username == "testuser"
        assert result.groups == ["contributor"]
        assert result.access_tier == AccessTier.CONTRIBUTOR
        assert result.organisation_id == "org-testuser"
        assert result.validation_source == "local_jwt"

    def test_expired_token_raises_error(self, hs256_config):
        """Test that expired token raises TokenExpiredError."""
        token = create_hs256_token("testuser", expired=True)

        with pytest.raises(TokenExpiredError, match="Token has expired"):
            validate_token_locally(token, hs256_config)

    def test_invalid_signature_raises_error(self, hs256_config):
        """Test that invalid signature raises InvalidTokenError."""
        token = create_hs256_token("testuser", secret="wrong-secret")

        with pytest.raises(InvalidTokenError, match="Invalid token"):
            validate_token_locally(token, hs256_config)

    def test_malformed_token_raises_error(self, hs256_config):
        """Test that malformed token raises InvalidTokenError."""
        with pytest.raises(InvalidTokenError, match="Invalid token"):
            validate_token_locally("not-a-valid-token", hs256_config)

    def test_missing_username_raises_error(self, hs256_config):
        """Test that token without username raises InvalidTokenError."""
        payload = {
            "cognito:groups": ["observer"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = pyjwt.encode(payload, "test-secret-key", algorithm="HS256")

        with pytest.raises(InvalidTokenError, match="missing username"):
            validate_token_locally(token, hs256_config)

    def test_uses_singleton_config_when_not_provided(self, hs256_config):
        """Test that singleton config is used when config not provided."""
        token = create_hs256_token("testuser", ["observer"])

        # Should use the configured singleton
        result = validate_token_locally(token)

        assert result.username == "testuser"

    def test_empty_groups_gives_public_tier(self, hs256_config):
        """Test that token with no groups gets PUBLIC tier."""
        token = create_hs256_token("testuser", groups=[])

        result = validate_token_locally(token, hs256_config)

        assert result.access_tier == AccessTier.PUBLIC


class TestValidateTokenLocallyRS256:
    """Tests for validate_token_locally with RS256 algorithm."""

    def test_rs256_uses_jwks_client(self):
        """Test that RS256 validation uses JWKS client."""
        config = AuthConfig.configure(
            jwt_algorithm="RS256",
            cognito_url="http://localhost:8100",
            user_pool_id="test-pool",
            region="eu-west-1",
        )

        # Create a mock for PyJWKClient
        mock_jwks_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "mock-key"
        mock_jwks_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key

        # Mock jwt.decode to return valid payload
        mock_payload = {
            "username": "testuser",
            "cognito:groups": ["observer"],
        }

        with (
            patch("frank.auth.jwt.PyJWKClient", mock_jwks_client),
            patch("frank.auth.jwt.jwt.decode", return_value=mock_payload),
        ):
            result = validate_token_locally("fake-token", config)

            assert result.username == "testuser"
            mock_jwks_client.assert_called_once_with(config.jwks_url)
