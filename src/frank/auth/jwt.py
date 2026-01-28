#!/usr/bin/env python3
"""
FRANK Platform - JWT Token Validation

Local JWT token validation supporting both RS256 (AWS Cognito) and
HS256 (Mock Cognito) algorithms.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from dataclasses import dataclass
from typing import List

import jwt
from jwt import PyJWKClient

from frank.auth.config import AuthConfig
from frank.core.enum import AccessTier


class TokenValidationError(Exception):
    """Base exception for token validation errors."""

    pass


class TokenExpiredError(TokenValidationError):
    """Token has expired."""

    pass


class InvalidTokenError(TokenValidationError):
    """Token is invalid or malformed."""

    pass


@dataclass
class TokenPayload:
    """Validated token payload with user information."""

    username: str
    groups: List[str]
    access_tier: AccessTier
    organisation_id: str
    validation_source: str = "local_jwt"

    @property
    def token_valid(self) -> bool:
        """Token is valid if we have a username."""
        return bool(self.username)


def get_access_tier_from_groups(groups: List[str]) -> AccessTier:
    """
    Convert Cognito user groups to AccessTier.

    Uses the first group and maps it via AccessTier.from_string().
    Returns PUBLIC if no groups are present.

    Args:
        groups: List of Cognito group names

    Returns:
        AccessTier enum value
    """
    if not groups:
        return AccessTier.PUBLIC

    # Use the first group and convert using from_string method
    primary_group = groups[0]
    return AccessTier.from_string(primary_group, default=True)


def validate_token_locally(token: str, config: AuthConfig | None = None) -> TokenPayload:
    """
    Validate JWT token locally using JWKS (RS256) or shared secret (HS256).

    Args:
        token: JWT token string
        config: Optional AuthConfig, uses singleton if not provided

    Returns:
        TokenPayload with validated user information

    Raises:
        TokenExpiredError: If the token has expired
        InvalidTokenError: If the token is invalid or malformed
    """
    if config is None:
        config = AuthConfig.get()

    try:
        if config.jwt_algorithm == "RS256":
            # Use JWKS for RS256 tokens (AWS Cognito style)
            jwks_client = PyJWKClient(config.jwks_url)
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False},  # Skip audience verification for flexibility
                issuer=f"https://cognito-idp.{config.region}.amazonaws.com/{config.user_pool_id}",
            )
        else:
            # HS256 for Mock Cognito or backwards compatibility
            payload = jwt.decode(
                token,
                config.jwt_secret,
                algorithms=[config.jwt_algorithm],
                options={"verify_aud": False},
            )

    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired") from e
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {e}") from e

    username = payload.get("username")
    if not username:
        raise InvalidTokenError("Invalid token: missing username")

    groups = payload.get("cognito:groups", [])
    access_tier = get_access_tier_from_groups(groups)

    return TokenPayload(
        username=username,
        groups=groups,
        access_tier=access_tier,
        organisation_id=f"org-{username}",
        validation_source="local_jwt",
    )
