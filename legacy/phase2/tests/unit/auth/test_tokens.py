#!/usr/bin/env python3
"""
FRANK Platform - Token Generation Tests

Unit tests for token generation and management utilities.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime, timedelta, timezone

import jwt

from frank.auth.tokens import (
    ACCESS_TOKEN_LIFETIME_HOURS,
    API_KEY_LIFETIME_DAYS,
    REFRESH_TOKEN_LIFETIME_DAYS,
    create_api_key_response,
    decode_refresh_token,
    generate_access_token,
    generate_api_key,
    generate_refresh_token,
    generate_token_id,
    get_expiry_datetime,
    hash_token,
    is_expired,
    verify_token_hash,
)


class TestTokenIdGeneration:
    """Tests for token ID generation."""

    def test_generate_token_id_returns_string(self):
        """Token ID should be a string."""
        token_id = generate_token_id()
        assert isinstance(token_id, str)

    def test_generate_token_id_uniqueness(self):
        """Each generated token ID should be unique."""
        ids = [generate_token_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generate_token_id_length(self):
        """Token ID should have reasonable length."""
        token_id = generate_token_id()
        # URL-safe base64 of 16 bytes is about 22 characters
        assert len(token_id) >= 20


class TestApiKeyGeneration:
    """Tests for API key generation."""

    def test_generate_api_key_format(self):
        """API key should start with 'frank_' prefix."""
        api_key = generate_api_key()
        assert api_key.startswith("frank_")

    def test_generate_api_key_length(self):
        """API key should have sufficient length for security."""
        api_key = generate_api_key()
        # frank_ prefix (6) + URL-safe base64 of 32 bytes (~43 chars)
        assert len(api_key) > 40

    def test_generate_api_key_uniqueness(self):
        """Each generated API key should be unique."""
        keys = [generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100


class TestTokenHashing:
    """Tests for token hashing functions."""

    def test_hash_token_returns_string(self):
        """Hash should be a hex string."""
        token = "test_token_123"
        hashed = hash_token(token)
        assert isinstance(hashed, str)
        # SHA-256 produces 64 hex characters
        assert len(hashed) == 64

    def test_hash_token_consistency(self):
        """Same input should produce same hash."""
        token = "consistent_token"
        hash1 = hash_token(token)
        hash2 = hash_token(token)
        assert hash1 == hash2

    def test_hash_token_different_inputs(self):
        """Different inputs should produce different hashes."""
        hash1 = hash_token("token1")
        hash2 = hash_token("token2")
        assert hash1 != hash2

    def test_verify_token_hash_valid(self):
        """Verification should return True for matching token."""
        token = "my_secret_token"
        stored_hash = hash_token(token)
        assert verify_token_hash(token, stored_hash) is True

    def test_verify_token_hash_invalid(self):
        """Verification should return False for non-matching token."""
        stored_hash = hash_token("correct_token")
        assert verify_token_hash("wrong_token", stored_hash) is False


class TestAccessTokenGeneration:
    """Tests for access token (JWT) generation."""

    def test_generate_access_token_returns_string(self):
        """Access token should be a JWT string."""
        token = generate_access_token(
            username="testuser",
            groups=["admin"],
            secret="test_secret"
        )
        assert isinstance(token, str)
        # JWT has three parts separated by dots
        assert token.count(".") == 2

    def test_generate_access_token_claims(self):
        """Access token should contain expected claims."""
        secret = "test_secret"
        token = generate_access_token(
            username="testuser",
            groups=["admin", "users"],
            secret=secret
        )
        payload = jwt.decode(token, secret, algorithms=["HS256"], audience="frank-api")

        assert payload["sub"] == "testuser"
        assert payload["username"] == "testuser"
        assert payload["cognito:groups"] == ["admin", "users"]
        assert payload["token_use"] == "access"
        assert payload["iss"] == "frank-auth"
        assert payload["aud"] == "frank-api"

    def test_generate_access_token_expiry(self):
        """Access token should have proper expiration."""
        secret = "test_secret"
        token = generate_access_token(
            username="testuser",
            groups=[],
            secret=secret,
            expires_in_hours=2
        )
        payload = jwt.decode(token, secret, algorithms=["HS256"], audience="frank-api")

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        # Should expire in approximately 2 hours
        diff = exp - now
        assert timedelta(hours=1, minutes=50) < diff < timedelta(hours=2, minutes=10)

    def test_generate_access_token_default_lifetime(self):
        """Access token should use default lifetime."""
        # Verify the constant is what we expect
        assert ACCESS_TOKEN_LIFETIME_HOURS == 1


class TestRefreshTokenGeneration:
    """Tests for refresh token (JWT) generation."""

    def test_generate_refresh_token_returns_string(self):
        """Refresh token should be a JWT string."""
        token = generate_refresh_token(
            username="testuser",
            secret="test_secret"
        )
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_generate_refresh_token_claims(self):
        """Refresh token should contain expected claims."""
        secret = "test_secret"
        token = generate_refresh_token(
            username="testuser",
            secret=secret
        )
        payload = jwt.decode(token, secret, algorithms=["HS256"])

        assert payload["sub"] == "testuser"
        assert payload["username"] == "testuser"
        assert payload["token_use"] == "refresh"
        assert "jti" in payload  # Unique token ID
        assert payload["iss"] == "frank-auth"

    def test_generate_refresh_token_expiry(self):
        """Refresh token should have proper expiration."""
        secret = "test_secret"
        token = generate_refresh_token(
            username="testuser",
            secret=secret,
            expires_in_days=7
        )
        payload = jwt.decode(token, secret, algorithms=["HS256"])

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        # Should expire in approximately 7 days
        diff = exp - now
        assert timedelta(days=6, hours=23) < diff < timedelta(days=7, hours=1)

    def test_generate_refresh_token_default_lifetime(self):
        """Refresh token should use default lifetime."""
        assert REFRESH_TOKEN_LIFETIME_DAYS == 30


class TestDecodeRefreshToken:
    """Tests for refresh token decoding."""

    def test_decode_refresh_token_valid(self):
        """Should decode valid refresh token."""
        secret = "test_secret"
        token = generate_refresh_token(username="testuser", secret=secret)

        payload = decode_refresh_token(token, secret)

        assert payload is not None
        assert payload["username"] == "testuser"
        assert payload["token_use"] == "refresh"

    def test_decode_refresh_token_expired(self):
        """Should return None for expired token."""
        secret = "test_secret"
        # Create an already-expired token
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "testuser",
            "username": "testuser",
            "token_use": "refresh",
            "jti": "test-id",
            "iat": now - timedelta(days=2),
            "exp": now - timedelta(days=1),  # Expired yesterday
            "iss": "frank-auth",
        }
        token = jwt.encode(payload, secret, algorithm="HS256")

        result = decode_refresh_token(token, secret)
        assert result is None

    def test_decode_refresh_token_wrong_secret(self):
        """Should return None for wrong secret."""
        token = generate_refresh_token(username="testuser", secret="correct_secret")

        result = decode_refresh_token(token, "wrong_secret")
        assert result is None

    def test_decode_refresh_token_wrong_type(self):
        """Should return None if token_use is not 'refresh'."""
        secret = "test_secret"
        # Create an access token (not refresh)
        token = generate_access_token(
            username="testuser",
            groups=[],
            secret=secret
        )

        result = decode_refresh_token(token, secret)
        assert result is None

    def test_decode_refresh_token_missing_claims(self):
        """Should return None if required claims are missing."""
        secret = "test_secret"
        now = datetime.now(timezone.utc)
        # Missing 'jti' claim
        payload = {
            "sub": "testuser",
            "token_use": "refresh",
            "iat": now,
            "exp": now + timedelta(days=1),
            "iss": "frank-auth",
        }
        token = jwt.encode(payload, secret, algorithm="HS256")

        result = decode_refresh_token(token, secret)
        assert result is None


class TestApiKeyResponse:
    """Tests for API key response creation."""

    def test_create_api_key_response(self):
        """Should create proper response dict."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=365)

        response = create_api_key_response(
            key_id="key-123",
            user_id="user-456",
            name="My API Key",
            plain_key="frank_abcdefghijklmnop",
            expires_at=expires,
            created_at=now
        )

        assert response["key_id"] == "key-123"
        assert response["user_id"] == "user-456"
        assert response["name"] == "My API Key"
        assert response["key"] == "frank_abcdefghijklmnop"
        assert response["key_prefix"] == "frank_abcdef..."
        assert response["expires_at"] == expires.isoformat()
        assert response["created_at"] == now.isoformat()

    def test_create_api_key_response_no_expiry(self):
        """Should handle None expires_at."""
        now = datetime.now(timezone.utc)

        response = create_api_key_response(
            key_id="key-123",
            user_id="user-456",
            name="My API Key",
            plain_key="frank_abcdefghijklmnop",
            expires_at=None,
            created_at=now
        )

        assert response["expires_at"] is None


class TestExpiryHelpers:
    """Tests for expiry datetime helpers."""

    def test_get_expiry_datetime(self):
        """Should calculate correct expiry datetime."""
        before = datetime.now(timezone.utc)
        expiry = get_expiry_datetime(days=30)
        after = datetime.now(timezone.utc)

        # Should be approximately 30 days from now
        assert before + timedelta(days=30) <= expiry <= after + timedelta(days=30)

    def test_is_expired_past(self):
        """Should return True for past datetime."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        assert is_expired(past) is True

    def test_is_expired_future(self):
        """Should return False for future datetime."""
        future = datetime.now(timezone.utc) + timedelta(days=1)
        assert is_expired(future) is False

    def test_is_expired_none(self):
        """Should return False for None (no expiry)."""
        assert is_expired(None) is False

    def test_is_expired_naive_datetime(self):
        """Should handle naive datetime (assumes UTC)."""
        past = datetime.now() - timedelta(days=1)  # Naive datetime
        assert is_expired(past) is True

    def test_api_key_default_lifetime(self):
        """API key should use default lifetime."""
        assert API_KEY_LIFETIME_DAYS == 365
