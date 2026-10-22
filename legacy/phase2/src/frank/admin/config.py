#!/usr/bin/env python3
"""
FRANK Platform - Admin Configuration

Configuration management for the admin TUI.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass
class AdminConfig:
    """
    Configuration for the FRANK Admin TUI.

    Follows singleton pattern similar to AuthConfig.
    """

    api_endpoint: str
    keyring_service: str
    token_refresh_buffer: int  # minutes before expiry to refresh
    timeout: float  # HTTP request timeout in seconds

    _instance: Optional["AdminConfig"] = None

    def __post_init__(self):
        """Validate and normalize configuration."""
        # Validate API endpoint URL
        parsed = urlparse(self.api_endpoint)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid API endpoint URL: {self.api_endpoint}")

        # Ensure no trailing slash
        self.api_endpoint = self.api_endpoint.rstrip("/")

    @classmethod
    def configure(
        cls,
        api_endpoint: Optional[str] = None,
        keyring_service: Optional[str] = None,
        token_refresh_buffer: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> "AdminConfig":
        """
        Configure the admin settings.

        Args:
            api_endpoint: Management API URL (default: FRANK_API_ENDPOINT or http://localhost:8001)
            keyring_service: Keyring service name for token storage (default: frank-admin)
            token_refresh_buffer: Minutes before token expiry to refresh (default: 5)
            timeout: HTTP request timeout in seconds (default: 30.0)

        Returns:
            Configured AdminConfig instance
        """
        cls._instance = cls(
            api_endpoint=api_endpoint or os.getenv("FRANK_API_ENDPOINT", "http://localhost:8001"),
            keyring_service=keyring_service or os.getenv("FRANK_KEYRING_SERVICE", "frank-admin"),
            token_refresh_buffer=token_refresh_buffer or int(os.getenv("FRANK_TOKEN_REFRESH_BUFFER", "5")),
            timeout=timeout or float(os.getenv("FRANK_API_TIMEOUT", "30.0")),
        )
        return cls._instance

    @classmethod
    def get(cls) -> "AdminConfig":
        """
        Get the current configuration.

        Creates default configuration if not already configured.

        Returns:
            AdminConfig instance
        """
        if cls._instance is None:
            cls.configure()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset configuration (mainly for testing)."""
        cls._instance = None

    def __repr__(self) -> str:
        return (
            f"AdminConfig(api_endpoint='{self.api_endpoint}', "
            f"keyring_service='{self.keyring_service}', "
            f"token_refresh_buffer={self.token_refresh_buffer}m, "
            f"timeout={self.timeout}s)"
        )
