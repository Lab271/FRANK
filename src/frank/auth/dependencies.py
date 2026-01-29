#!/usr/bin/env python3
"""
FRANK Platform - FastAPI Authentication Dependencies

FastAPI dependencies for JWT authentication with Cognito.
Provides get_current_user dependency for protected endpoints.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from frank.auth.cognito import (
    CognitoConnectionError,
    CognitoTimeoutError,
    CognitoValidationError,
    validate_token_with_cognito,
)
from frank.auth.config import AuthConfig
from frank.auth.jwt import InvalidTokenError, TokenExpiredError, TokenPayload, validate_token_locally
from frank.core.enum import AccessTier


logger = logging.getLogger(__name__)

# Security scheme for Bearer token authentication
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    """
    FastAPI dependency to extract and validate user from JWT token.

    Validates the token according to the configured validation strategy:
    - server_first: Try Cognito server first, fall back to local JWT
    - local_only: Only local JWT validation
    - server_only: Only accept Cognito server validation

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        TokenPayload with validated user information

    Raises:
        HTTPException 401: Authentication failed
        HTTPException 503: Cognito service unavailable
        HTTPException 504: Cognito request timed out
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    config = AuthConfig.get()

    try:
        # Server validation for server_first and server_only strategies
        if config.validation_strategy != "local_only":
            try:
                cognito_result = await validate_token_with_cognito(token, config)

                # Server validated, but we still need groups from JWT
                # because GetUser API doesn't return group memberships
                local_result = validate_token_locally(token, config)
                local_result.validation_source = cognito_result.validation_source
                return local_result

            except CognitoValidationError:
                if config.validation_strategy == "server_only":
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token validation failed: Could not validate with Cognito server",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                # For server_first, fall through to local validation
                logger.debug("Cognito validation failed, falling back to local validation")

        # Local validation for local_only or server_first fallback
        return validate_token_locally(token, config)

    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except CognitoConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Cognito service",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except CognitoTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Cognito GetUser request timed out",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_access_tier(required_tier: AccessTier) -> Callable[[TokenPayload], TokenPayload]:
    """
    Create a dependency that requires a minimum access tier.

    Usage:
        @app.get("/partner")
        async def partner_endpoint(
            user: TokenPayload = Depends(require_access_tier(AccessTier.PARTNER))
        ):
            ...

    Args:
        required_tier: Minimum AccessTier required

    Returns:
        FastAPI dependency function
    """

    async def check_tier(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if not current_user.access_tier.check_access_level(required_tier):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient access level. Required: {required_tier.value}, "
                f"User has: {current_user.access_tier.value}",
            )
        return current_user

    return check_tier
