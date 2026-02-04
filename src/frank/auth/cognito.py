#!/usr/bin/env python3
"""
FRANK Platform - Cognito Server Validation

Server-side token validation using AWS Cognito GetUser API.
Works with both Mock Cognito and AWS Cognito.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
from dataclasses import dataclass

import httpx

from frank.auth.config import AuthConfig

logger = logging.getLogger(__name__)

# Timeout for Cognito API calls
COGNITO_TIMEOUT = 10.0  # seconds


class CognitoError(Exception):
    """Base exception for Cognito-related errors."""

    pass


class CognitoConnectionError(CognitoError):
    """Could not connect to Cognito service."""

    pass


class CognitoTimeoutError(CognitoError):
    """Cognito request timed out."""

    pass


class CognitoValidationError(CognitoError):
    """Token validation failed with Cognito."""

    pass


@dataclass
class CognitoUserInfo:
    """User information returned from Cognito GetUser API."""

    username: str
    validation_source: str


async def validate_token_with_cognito(
    token: str,
    config: AuthConfig | None = None,
) -> CognitoUserInfo:
    """
    Validate token with Cognito server using GetUser API.

    This makes a real call to either Mock Cognito or AWS Cognito
    for token validation. Note that GetUser API doesn't return
    group memberships - those must be extracted from the JWT.

    Args:
        token: Access token to validate
        config: Optional AuthConfig, uses singleton if not provided

    Returns:
        CognitoUserInfo with username and validation source

    Raises:
        CognitoConnectionError: Could not connect to Cognito
        CognitoTimeoutError: Request timed out
        CognitoValidationError: Token validation failed
    """
    if config is None:
        config = AuthConfig.get()

    logger.debug(f"Validating token with {config.environment} Cognito at {config.cognito_url}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.cognito_url,
                headers={
                    "X-Amz-Target": "AWSCognitoIdentityProviderService.GetUser",
                    "Content-Type": "application/x-amz-json-1.1",
                },
                json={"AccessToken": token},
                timeout=COGNITO_TIMEOUT,
            )

            if response.status_code == 200:
                user_info = response.json()
                username = user_info.get("Username")

                if username:
                    logger.info(f"Token validated via {config.environment} Cognito for user: {username}")
                    return CognitoUserInfo(
                        username=username,
                        validation_source=f"{config.environment}-cognito-getuser",
                    )

            logger.warning(f"{config.environment} Cognito GetUser failed with status {response.status_code}")
            raise CognitoValidationError(
                f"Token validation failed: Cognito returned status {response.status_code}"
            )

    except httpx.ConnectError as e:
        raise CognitoConnectionError("Could not connect to Cognito service") from e
    except httpx.TimeoutException as e:
        raise CognitoTimeoutError("Cognito GetUser request timed out") from e


def validate_token_with_cognito_sync(
    token: str,
    config: AuthConfig | None = None,
) -> CognitoUserInfo:
    """
    Synchronous version of validate_token_with_cognito.

    For use in non-async contexts.

    Args:
        token: Access token to validate
        config: Optional AuthConfig, uses singleton if not provided

    Returns:
        CognitoUserInfo with username and validation source

    Raises:
        CognitoConnectionError: Could not connect to Cognito
        CognitoTimeoutError: Request timed out
        CognitoValidationError: Token validation failed
    """
    if config is None:
        config = AuthConfig.get()

    logger.debug(f"Validating token with {config.environment} Cognito at {config.cognito_url}")

    try:
        with httpx.Client() as client:
            response = client.post(
                config.cognito_url,
                headers={
                    "X-Amz-Target": "AWSCognitoIdentityProviderService.GetUser",
                    "Content-Type": "application/x-amz-json-1.1",
                },
                json={"AccessToken": token},
                timeout=COGNITO_TIMEOUT,
            )

            if response.status_code == 200:
                user_info = response.json()
                username = user_info.get("Username")

                if username:
                    logger.info(f"Token validated via {config.environment} Cognito for user: {username}")
                    return CognitoUserInfo(
                        username=username,
                        validation_source=f"{config.environment}-cognito-getuser",
                    )

            logger.warning(f"{config.environment} Cognito GetUser failed with status {response.status_code}")
            raise CognitoValidationError(
                f"Token validation failed: Cognito returned status {response.status_code}"
            )

    except httpx.ConnectError as e:
        raise CognitoConnectionError("Could not connect to Cognito service") from e
    except httpx.TimeoutException as e:
        raise CognitoTimeoutError("Cognito GetUser request timed out") from e
