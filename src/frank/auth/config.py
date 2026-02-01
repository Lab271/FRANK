#!/usr/bin/env python3
"""
FRANK Platform - Authentication Configuration

Singleton configuration for authentication settings supporting both
Mock Cognito (local development) and AWS Cognito (cloud deployment).

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
from typing import Literal, Optional


ValidationStrategy = Literal["server_first", "local_only", "server_only"]
JWTAlgorithm = Literal["RS256", "HS256"]
Environment = Literal["mock", "aws"]


class AuthConfig:
    """
    Singleton configuration class for authentication settings.

    Supports three validation strategies:
    - server_first: Attempt server-side validation with Cognito first,
      then fall back to local JWT validation if unavailable.
    - local_only: Only perform local JWT validation, no Cognito server contact.
    - server_only: Only accept tokens validated by Cognito server.

    Configuration priority: passed parameters > environment variables > defaults
    """

    _instance: Optional["AuthConfig"] = None

    def __init__(
        self,
        cognito_url: str,
        jwt_secret: str,
        jwt_algorithm: JWTAlgorithm,
        validation_strategy: ValidationStrategy,
        region: str,
        user_pool_id: str,
        environment: Environment,
    ):
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.validation_strategy = validation_strategy
        self.region = region
        self.user_pool_id = user_pool_id
        self.environment = environment

        # Construct Cognito URL based on environment
        if self.environment == "aws":
            self.cognito_url = f"https://cognito-idp.{self.region}.amazonaws.com/"
        else:
            self.cognito_url = cognito_url if cognito_url.endswith("/") else f"{cognito_url}/"

        # Construct JWKS URL for local validation
        self.jwks_url = f"{self.cognito_url}{self.user_pool_id}/.well-known/jwks.json"

        # Validate configuration
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values."""
        if not self.cognito_url.startswith("http"):
            raise ValueError(f"Invalid Cognito URL: {self.cognito_url}")
        if self.validation_strategy not in ("server_first", "local_only", "server_only"):
            raise ValueError(f"Invalid validation strategy: {self.validation_strategy}")
        if self.jwt_algorithm not in ("RS256", "HS256"):
            raise ValueError(f"Unsupported JWT algorithm: {self.jwt_algorithm}")

    @classmethod
    def configure(
        cls,
        cognito_url: Optional[str] = None,
        jwt_secret: Optional[str] = None,
        jwt_algorithm: Optional[JWTAlgorithm] = None,
        validation_strategy: Optional[ValidationStrategy] = None,
        region: Optional[str] = None,
        user_pool_id: Optional[str] = None,
        environment: Optional[Environment] = None,
    ) -> "AuthConfig":
        """
        Configure and set the singleton AuthConfig instance.

        Priority: passed parameters > environment variables > defaults

        Returns:
            AuthConfig: The configured singleton instance
        """
        cls._instance = cls(
            cognito_url=cognito_url or os.getenv("COGNITO_URL", "http://localhost:8100"),
            jwt_secret=jwt_secret or os.getenv("JWT_SECRET", "mock-cognito-secret-key"),
            jwt_algorithm=jwt_algorithm or os.getenv("JWT_ALGORITHM", "HS256"),  # type: ignore[arg-type]
            validation_strategy=validation_strategy or os.getenv("VALIDATION_STRATEGY", "local_only"),  # type: ignore[arg-type]
            region=region or os.getenv("AWS_REGION", os.getenv("REGION", "eu-west-1")),
            user_pool_id=user_pool_id or os.getenv("USER_POOL_ID", "eu-west-1_MOCKPOOL"),
            environment=environment or os.getenv("ENVIRONMENT", "mock"),  # type: ignore[arg-type]
        )
        return cls._instance

    @classmethod
    def get(cls) -> "AuthConfig":
        """
        Get the singleton AuthConfig instance.

        Creates instance with defaults/environment if not configured.

        Returns:
            AuthConfig: The singleton instance
        """
        if cls._instance is None:
            cls.configure()
        return cls._instance  # type: ignore[return-value]

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance. Useful for testing."""
        cls._instance = None

    def __repr__(self) -> str:
        return (
            f"AuthConfig(environment={self.environment!r}, "
            f"validation_strategy={self.validation_strategy!r}, "
            f"jwt_algorithm={self.jwt_algorithm!r}, "
            f"region={self.region!r})"
        )
