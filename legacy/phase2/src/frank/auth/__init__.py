#!/usr/bin/env python3
"""
FRANK Platform - Authentication Module

Provides JWT authentication with AWS Cognito integration for FastAPI applications.
Supports both Mock Cognito (local development) and AWS Cognito (cloud deployment).

Usage:
    from frank.auth import AuthConfig, get_current_user, require_access_tier
    from frank.core.enum import AccessTier

    # Configure authentication (optional - uses environment variables by default)
    AuthConfig.configure(
        environment="mock",
        validation_strategy="local_only",
    )

    # Use in FastAPI endpoints
    @app.get("/protected")
    async def protected_endpoint(user: TokenPayload = Depends(get_current_user)):
        return {"username": user.username, "tier": user.access_tier.value}

    @app.get("/partner")
    async def partner_endpoint(user: TokenPayload = Depends(require_access_tier(AccessTier.PARTNER))):
        return {"message": "Partner access granted"}

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from frank.auth.cognito import (
    CognitoConnectionError,
    CognitoError,
    CognitoTimeoutError,
    CognitoUserInfo,
    CognitoValidationError,
    validate_token_with_cognito,
    validate_token_with_cognito_sync,
)
from frank.auth.config import AuthConfig
from frank.auth.dependencies import get_current_user, require_access_tier, security
from frank.auth.jwt import (
    InvalidTokenError,
    TokenExpiredError,
    TokenPayload,
    TokenValidationError,
    get_access_tier_from_groups,
    validate_token_locally,
)

__all__ = [
    # Config
    "AuthConfig",
    # JWT validation
    "validate_token_locally",
    "get_access_tier_from_groups",
    "TokenPayload",
    "TokenValidationError",
    "TokenExpiredError",
    "InvalidTokenError",
    # Cognito validation
    "validate_token_with_cognito",
    "validate_token_with_cognito_sync",
    "CognitoUserInfo",
    "CognitoError",
    "CognitoConnectionError",
    "CognitoTimeoutError",
    "CognitoValidationError",
    # FastAPI dependencies
    "get_current_user",
    "require_access_tier",
    "security",
]
