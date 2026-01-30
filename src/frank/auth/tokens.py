#!/usr/bin/env python3
"""
FRANK Platform - Token Generation and Management

Utilities for generating and validating access tokens, refresh tokens, and API keys.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

# Token lifetimes (configurable via environment in production)
ACCESS_TOKEN_LIFETIME_HOURS = 1
REFRESH_TOKEN_LIFETIME_DAYS = 30
API_KEY_LIFETIME_DAYS = 365


def generate_token_id() -> str:
    """Generate a unique token identifier."""
    return secrets.token_urlsafe(16)


def generate_api_key() -> str:
    """
    Generate a secure API key.

    Returns a 32-byte (256-bit) random key encoded as URL-safe base64.
    Format: frank_<random_string> for easy identification.
    """
    random_part = secrets.token_urlsafe(32)
    return f"frank_{random_part}"


def hash_token(token: str) -> str:
    """
    Hash a token for secure storage.

    Uses SHA-256 for fast, secure hashing. The hash is stored in the database,
    not the original token.

    Args:
        token: The plain token to hash

    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_hash(token: str, stored_hash: str) -> bool:
    """
    Verify a token against its stored hash using constant-time comparison.

    Args:
        token: The plain token to verify
        stored_hash: The stored hash to compare against

    Returns:
        True if the token matches the hash
    """
    computed_hash = hash_token(token)
    return hmac.compare_digest(computed_hash, stored_hash)


def generate_access_token(
    username: str,
    groups: list[str],
    secret: str,
    algorithm: str = "HS256",
    expires_in_hours: int = ACCESS_TOKEN_LIFETIME_HOURS,
    issuer: str = "frank-auth",
    audience: str = "frank-api",
) -> str:
    """
    Generate a short-lived access token (JWT).

    Args:
        username: User identifier
        groups: List of user groups for access control
        secret: Signing secret (or private key for RS256)
        algorithm: JWT algorithm (HS256 or RS256)
        expires_in_hours: Token lifetime in hours
        issuer: Token issuer
        audience: Token audience

    Returns:
        Encoded JWT string
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "username": username,
        "cognito:groups": groups,
        "token_use": "access",
        "iat": now,
        "exp": now + timedelta(hours=expires_in_hours),
        "iss": issuer,
        "aud": audience,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def generate_refresh_token(
    username: str,
    secret: str,
    algorithm: str = "HS256",
    expires_in_days: int = REFRESH_TOKEN_LIFETIME_DAYS,
    issuer: str = "frank-auth",
) -> str:
    """
    Generate a long-lived refresh token (JWT).

    Args:
        username: User identifier
        secret: Signing secret
        algorithm: JWT algorithm
        expires_in_days: Token lifetime in days
        issuer: Token issuer

    Returns:
        Encoded JWT string
    """
    now = datetime.now(timezone.utc)
    token_id = generate_token_id()
    payload = {
        "sub": username,
        "username": username,
        "token_use": "refresh",
        "jti": token_id,  # Unique token ID for revocation
        "iat": now,
        "exp": now + timedelta(days=expires_in_days),
        "iss": issuer,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_refresh_token(
    token: str,
    secret: str,
    algorithm: str = "HS256",
    issuer: str = "frank-auth",
) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a refresh token.

    Args:
        token: The refresh token JWT
        secret: Signing secret for verification
        algorithm: JWT algorithm
        issuer: Expected issuer

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            issuer=issuer,
            options={"require": ["sub", "exp", "iat", "jti"]}
        )
        if payload.get("token_use") != "refresh":
            return None
        return payload
    except jwt.PyJWTError:
        return None


def create_api_key_response(
    key_id: str,
    user_id: str,
    name: str,
    plain_key: str,
    expires_at: Optional[datetime],
    created_at: datetime,
) -> Dict[str, Any]:
    """
    Create a response dict for a newly created API key.

    Note: The plain key is only returned once at creation time.

    Args:
        key_id: Unique key identifier
        user_id: Owner's user ID
        name: Human-readable key name
        plain_key: The actual API key (shown only once)
        expires_at: Expiration datetime or None for no expiry
        created_at: Creation timestamp

    Returns:
        Dict with key details including the plain key
    """
    return {
        "key_id": key_id,
        "user_id": user_id,
        "name": name,
        "key": plain_key,  # Only returned at creation!
        "key_prefix": plain_key[:12] + "...",  # For display later
        "expires_at": expires_at.isoformat() if expires_at else None,
        "created_at": created_at.isoformat(),
    }


def get_expiry_datetime(days: int) -> datetime:
    """
    Calculate expiry datetime from now.

    Args:
        days: Number of days until expiry

    Returns:
        UTC datetime of expiry
    """
    return datetime.now(timezone.utc) + timedelta(days=days)


def is_expired(expires_at: Optional[datetime]) -> bool:
    """
    Check if a datetime is in the past (expired).

    Args:
        expires_at: The expiry datetime or None

    Returns:
        True if expired, False if still valid or no expiry
    """
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        # Assume UTC if no timezone
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires_at
