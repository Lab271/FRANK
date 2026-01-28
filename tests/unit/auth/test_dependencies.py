#!/usr/bin/env python3
"""
Tests for FRANK FastAPI authentication dependencies.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import jwt as pyjwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from frank.auth.config import AuthConfig
from frank.auth.dependencies import get_current_user, require_access_tier
from frank.auth.jwt import TokenPayload
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


@pytest.fixture
def test_app(hs256_config):
    """Create a test FastAPI app with auth dependencies."""
    app = FastAPI()

    @app.get("/protected")
    async def protected_endpoint(user: TokenPayload = pytest.importorskip("fastapi").Depends(get_current_user)):
        return {"username": user.username, "tier": user.access_tier.value}

    @app.get("/contributor")
    async def contributor_endpoint(
        user: TokenPayload = pytest.importorskip("fastapi").Depends(require_access_tier(AccessTier.CONTRIBUTOR))
    ):
        return {"username": user.username, "tier": user.access_tier.value}

    @app.get("/partner")
    async def partner_endpoint(
        user: TokenPayload = pytest.importorskip("fastapi").Depends(require_access_tier(AccessTier.PARTNER))
    ):
        return {"username": user.username, "tier": user.access_tier.value}

    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    def test_valid_token_returns_user(self, client, hs256_config):
        """Test that valid token returns user information."""
        token = create_hs256_token("testuser", ["contributor"])

        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["tier"] == "contributor"

    def test_missing_token_returns_401(self, client, hs256_config):
        """Test that missing token returns 401."""
        response = client.get("/protected")

        # FastAPI HTTPBearer returns 403 when no Authorization header is present
        assert response.status_code in (401, 403)

    def test_invalid_token_returns_401(self, client, hs256_config):
        """Test that invalid token returns 401."""
        response = client.get("/protected", headers={"Authorization": "Bearer invalid-token"})

        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    def test_expired_token_returns_401(self, client, hs256_config):
        """Test that expired token returns 401."""
        token = create_hs256_token("testuser", expired=True)

        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401
        assert "expired" in response.json()["detail"]

    def test_wrong_signature_returns_401(self, client, hs256_config):
        """Test that token with wrong signature returns 401."""
        token = create_hs256_token("testuser", secret="wrong-secret")

        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401


class TestGetCurrentUserServerValidation:
    """Tests for get_current_user with server validation strategies."""

    @pytest.mark.asyncio
    async def test_server_first_falls_back_to_local(self):
        """Test that server_first falls back to local validation."""
        AuthConfig.configure(
            jwt_algorithm="HS256",
            jwt_secret="test-secret-key",
            validation_strategy="server_first",
        )

        from fastapi.security import HTTPAuthorizationCredentials

        from frank.auth.cognito import CognitoValidationError

        token = create_hs256_token("testuser", ["observer"])
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Mock Cognito to fail
        with patch("frank.auth.dependencies.validate_token_with_cognito") as mock_cognito:
            mock_cognito.side_effect = CognitoValidationError("Server error")

            result = await get_current_user(credentials)

            assert result.username == "testuser"
            assert result.validation_source == "local_jwt"

    @pytest.mark.asyncio
    async def test_server_only_fails_without_cognito(self):
        """Test that server_only fails when Cognito unavailable."""
        AuthConfig.configure(
            jwt_algorithm="HS256",
            jwt_secret="test-secret-key",
            validation_strategy="server_only",
        )

        from fastapi.security import HTTPAuthorizationCredentials

        from frank.auth.cognito import CognitoValidationError

        token = create_hs256_token("testuser", ["observer"])
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("frank.auth.dependencies.validate_token_with_cognito") as mock_cognito:
            mock_cognito.side_effect = CognitoValidationError("Server error")

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 401
            assert "Could not validate with Cognito" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_server_success_updates_validation_source(self):
        """Test that successful server validation updates source."""
        AuthConfig.configure(
            jwt_algorithm="HS256",
            jwt_secret="test-secret-key",
            validation_strategy="server_first",
        )

        from fastapi.security import HTTPAuthorizationCredentials

        from frank.auth.cognito import CognitoUserInfo

        token = create_hs256_token("testuser", ["contributor"])
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("frank.auth.dependencies.validate_token_with_cognito") as mock_cognito:
            mock_cognito.return_value = CognitoUserInfo(
                username="testuser",
                validation_source="mock-cognito-getuser",
            )

            result = await get_current_user(credentials)

            assert result.username == "testuser"
            assert result.validation_source == "mock-cognito-getuser"

    @pytest.mark.asyncio
    async def test_cognito_connection_error_returns_503(self):
        """Test that Cognito connection error returns 503."""
        AuthConfig.configure(
            jwt_algorithm="HS256",
            jwt_secret="test-secret-key",
            validation_strategy="server_only",
        )

        from fastapi.security import HTTPAuthorizationCredentials

        from frank.auth.cognito import CognitoConnectionError

        token = create_hs256_token("testuser")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("frank.auth.dependencies.validate_token_with_cognito") as mock_cognito:
            mock_cognito.side_effect = CognitoConnectionError("Connection refused")

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_cognito_timeout_returns_504(self):
        """Test that Cognito timeout returns 504."""
        AuthConfig.configure(
            jwt_algorithm="HS256",
            jwt_secret="test-secret-key",
            validation_strategy="server_only",
        )

        from fastapi.security import HTTPAuthorizationCredentials

        from frank.auth.cognito import CognitoTimeoutError

        token = create_hs256_token("testuser")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("frank.auth.dependencies.validate_token_with_cognito") as mock_cognito:
            mock_cognito.side_effect = CognitoTimeoutError("Timeout")

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 504


class TestRequireAccessTier:
    """Tests for require_access_tier dependency."""

    def test_sufficient_tier_allowed(self, client, hs256_config):
        """Test that users with sufficient tier can access."""
        token = create_hs256_token("testuser", ["partner"])

        response = client.get("/contributor", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["username"] == "testuser"

    def test_exact_tier_allowed(self, client, hs256_config):
        """Test that users with exact tier can access."""
        token = create_hs256_token("testuser", ["contributor"])

        response = client.get("/contributor", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200

    def test_insufficient_tier_returns_403(self, client, hs256_config):
        """Test that users with insufficient tier get 403."""
        token = create_hs256_token("testuser", ["observer"])

        response = client.get("/contributor", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 403
        assert "Insufficient access level" in response.json()["detail"]

    def test_public_user_cannot_access_protected(self, client, hs256_config):
        """Test that public users cannot access tier-protected endpoints."""
        token = create_hs256_token("testuser", [])  # No groups = PUBLIC

        response = client.get("/contributor", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 403

    def test_partner_cannot_access_core_member(self, hs256_config):
        """Test that partner cannot access core_member endpoint."""
        app = FastAPI()

        @app.get("/core_member")
        async def core_member_endpoint(
            user: TokenPayload = pytest.importorskip("fastapi").Depends(require_access_tier(AccessTier.CORE_MEMBER))
        ):
            return {"username": user.username}

        client = TestClient(app)
        token = create_hs256_token("testuser", ["partner"])

        response = client.get("/core_member", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 403
        assert "Required: core_member" in response.json()["detail"]
        assert "User has: partner" in response.json()["detail"]
