"""
FRANK Platform - Environment Configuration

Provides environment-based configuration system with explicit environment enum
and singleton configuration class.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Environment(str, Enum):
    """
    FRANK deployment environments.

    Each environment represents a distinct deployment target with its own
    infrastructure characteristics and configuration requirements.

    Values:
        LOCAL_PYTHON: Native Python execution on macOS/Linux (development)
        LOCAL_DOCKER: Docker Compose stack (development/testing)
        AWS_DEV: AWS development account (testing/staging)
        AWS_PREPROD: AWS pre-production environment (staging)
        AWS_PROD: AWS production environment (live)

    Usage:
        >>> env = Environment.LOCAL_DOCKER
        >>> env.value
        'local-docker'
        >>> Environment("aws-prod")
        <Environment.AWS_PROD: 'aws-prod'>
    """

    LOCAL_PYTHON = "local-python"
    LOCAL_DOCKER = "local-docker"
    AWS_DEV = "aws-dev"
    AWS_PREPROD = "aws-preprod"
    AWS_PROD = "aws-prod"

    @classmethod
    def from_string(cls, value: str) -> "Environment":
        """
        Create Environment from string value.

        Args:
            value: Environment name (case-insensitive, accepts underscores or hyphens)

        Returns:
            Environment enum member

        Raises:
            ValueError: If value is not a valid environment

        Examples:
            >>> Environment.from_string("local-docker")
            <Environment.LOCAL_DOCKER: 'local-docker'>
            >>> Environment.from_string("LOCAL_DOCKER")
            <Environment.LOCAL_DOCKER: 'local-docker'>
            >>> Environment.from_string("local_docker")
            <Environment.LOCAL_DOCKER: 'local-docker'>
        """
        # Normalize: lowercase and replace underscores with hyphens
        normalized = value.lower().replace("_", "-")

        try:
            return cls(normalized)
        except ValueError:
            valid_values = ", ".join([e.value for e in cls])
            raise ValueError(
                f"Invalid environment: '{value}'. "
                f"Must be one of: {valid_values}"
            )


@dataclass
class EnvironmentConfig:
    """
    Singleton configuration for FRANK environment and stage.

    Manages environment detection and provides environment-specific behavior flags.
    Follows the singleton pattern used by AuthConfig, WebConfig, and AdminConfig.

    Attributes:
        environment: The deployment environment (LOCAL_PYTHON, LOCAL_DOCKER, AWS_*, etc.)
        stage: Infrastructure complexity stage (1-4)

    Class Methods:
        configure: Initialize singleton with explicit or environment-derived values
        get: Retrieve singleton instance (initializes if needed)
        reset: Clear singleton (primarily for testing)

    Properties:
        is_local: True if running in local environment (Python or Docker)
        is_aws: True if running in AWS environment
        is_production: True if running in AWS production
        is_docker: True if running in Docker environment
        is_python: True if running in native Python environment

    Usage:
        >>> # Initialize from environment variables
        >>> config = EnvironmentConfig.configure()
        >>> config.environment
        <Environment.LOCAL_DOCKER: 'local-docker'>

        >>> # Initialize explicitly
        >>> config = EnvironmentConfig.configure(
        ...     environment="aws-prod",
        ...     stage=3
        ... )

        >>> # Get singleton instance
        >>> config = EnvironmentConfig.get()
        >>> config.is_production
        True

        >>> # Check environment type
        >>> if config.is_local:
        ...     print("Development mode")

    Environment Variables:
        FRANK_ENVIRONMENT: Environment name (default: "local-python")
        FRANK_STAGE: Infrastructure stage 1-4 (default: "1")
    """

    environment: Environment
    stage: int

    # Singleton instance
    _instance: Optional["EnvironmentConfig"] = None

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not isinstance(self.environment, Environment):
            raise TypeError(
                f"environment must be Environment enum, got {type(self.environment)}"
            )

        if not isinstance(self.stage, int):
            raise TypeError(f"stage must be int, got {type(self.stage)}")

        if self.stage not in (1, 2, 3, 4):
            raise ValueError(f"stage must be 1-4, got {self.stage}")

    @classmethod
    def configure(
        cls,
        environment: Optional[str] = None,
        stage: Optional[int] = None
    ) -> "EnvironmentConfig":
        """
        Configure singleton instance from explicit values or environment variables.

        If a singleton instance already exists, returns the existing instance without
        modification. Call reset() first if you need to reconfigure.

        Args:
            environment: Environment name (defaults to FRANK_ENVIRONMENT env var)
            stage: Stage number 1-4 (defaults to FRANK_STAGE env var)

        Returns:
            Configured singleton instance

        Raises:
            ValueError: If environment or stage values are invalid

        Examples:
            >>> # From environment variables
            >>> config = EnvironmentConfig.configure()

            >>> # Explicit configuration
            >>> config = EnvironmentConfig.configure(
            ...     environment="local-docker",
            ...     stage=3
            ... )
        """
        # Return existing instance if already configured (singleton pattern)
        if cls._instance is not None:
            return cls._instance

        # Get environment from parameter or environment variable
        env_str = environment or os.getenv("FRANK_ENVIRONMENT", "local-python")
        env = Environment.from_string(env_str)

        # Get stage from parameter or environment variable
        stage_str = stage if stage is not None else os.getenv("FRANK_STAGE", "1")
        try:
            stage_int = int(stage_str)
        except (ValueError, TypeError):
            raise ValueError(
                f"FRANK_STAGE must be an integer 1-4, got '{stage_str}'"
            )

        # Create and store singleton instance
        cls._instance = cls(environment=env, stage=stage_int)
        return cls._instance

    @classmethod
    def get(cls) -> "EnvironmentConfig":
        """
        Get singleton instance, initializing if needed.

        Returns:
            Singleton instance

        Examples:
            >>> config = EnvironmentConfig.get()
            >>> config.environment
            <Environment.LOCAL_PYTHON: 'local-python'>
        """
        if cls._instance is None:
            cls.configure()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """
        Reset singleton instance (primarily for testing).

        Examples:
            >>> EnvironmentConfig.reset()
            >>> # Instance is cleared, next get() will reconfigure
        """
        cls._instance = None

    # Environment type properties

    @property
    def is_local(self) -> bool:
        """
        Check if running in local environment (Python or Docker).

        Returns:
            True if LOCAL_PYTHON or LOCAL_DOCKER

        Examples:
            >>> config = EnvironmentConfig.configure(environment="local-docker")
            >>> config.is_local
            True
            >>> config = EnvironmentConfig.configure(environment="aws-prod")
            >>> config.is_local
            False
        """
        return self.environment in (Environment.LOCAL_PYTHON, Environment.LOCAL_DOCKER)

    @property
    def is_aws(self) -> bool:
        """
        Check if running in AWS environment.

        Returns:
            True if AWS_DEV, AWS_PREPROD, or AWS_PROD

        Examples:
            >>> config = EnvironmentConfig.configure(environment="aws-dev")
            >>> config.is_aws
            True
        """
        return self.environment in (
            Environment.AWS_DEV,
            Environment.AWS_PREPROD,
            Environment.AWS_PROD
        )

    @property
    def is_production(self) -> bool:
        """
        Check if running in production environment.

        Returns:
            True if AWS_PROD

        Examples:
            >>> config = EnvironmentConfig.configure(environment="aws-prod")
            >>> config.is_production
            True
        """
        return self.environment == Environment.AWS_PROD

    @property
    def is_docker(self) -> bool:
        """
        Check if running in Docker environment.

        Returns:
            True if LOCAL_DOCKER

        Examples:
            >>> config = EnvironmentConfig.configure(environment="local-docker")
            >>> config.is_docker
            True
        """
        return self.environment == Environment.LOCAL_DOCKER

    @property
    def is_python(self) -> bool:
        """
        Check if running in native Python environment.

        Returns:
            True if LOCAL_PYTHON

        Examples:
            >>> config = EnvironmentConfig.configure(environment="local-python")
            >>> config.is_python
            True
        """
        return self.environment == Environment.LOCAL_PYTHON

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"EnvironmentConfig(environment={self.environment.value}, "
            f"stage={self.stage})"
        )
