#!/usr/bin/env python3
"""
FRANK Platform - Web GUI Configuration

Configuration management for the web GUI.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass
class WebConfig:
    """
    Configuration for the FRANK Web GUI.

    Follows singleton pattern similar to AdminConfig and AuthConfig.
    """

    management_api_url: str
    cognito_url: str
    session_secret_key: str
    session_cookie_name: str
    session_max_age: int  # seconds
    timeout: float  # HTTP request timeout in seconds
    template_auto_reload: bool  # Auto-reload templates in development

    _instance: Optional["WebConfig"] = None

    def __post_init__(self):
        """Validate and normalize configuration."""
        # Validate Management API URL
        parsed = urlparse(self.management_api_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid Management API URL: {self.management_api_url}")

        # Validate Cognito URL
        parsed = urlparse(self.cognito_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid Cognito URL: {self.cognito_url}")

        # Ensure no trailing slashes
        self.management_api_url = self.management_api_url.rstrip("/")
        self.cognito_url = self.cognito_url.rstrip("/")

        # Validate session secret key
        if len(self.session_secret_key) < 32:
            raise ValueError("Session secret key must be at least 32 characters")

    @classmethod
    def configure(
        cls,
        management_api_url: Optional[str] = None,
        cognito_url: Optional[str] = None,
        session_secret_key: Optional[str] = None,
        session_cookie_name: Optional[str] = None,
        session_max_age: Optional[int] = None,
        timeout: Optional[float] = None,
        template_auto_reload: Optional[bool] = None,
    ) -> "WebConfig":
        """
        Configure the web GUI settings.

        Args:
            management_api_url: Management API URL (default: FRANK_MANAGEMENT_API_URL or http://localhost:8001)
            cognito_url: Cognito service URL (default: COGNITO_URL or http://localhost:8100)
            session_secret_key: Secret key for session encryption (default: FRANK_SESSION_SECRET or generated)
            session_cookie_name: Name of session cookie (default: frank_session)
            session_max_age: Session cookie max age in seconds (default: 3600 = 1 hour)
            timeout: HTTP request timeout in seconds (default: 30.0)
            template_auto_reload: Auto-reload templates for development (default: False or TEMPLATE_AUTO_RELOAD)

        Returns:
            Configured WebConfig instance
        """
        # Generate default session secret if not provided
        default_secret = os.getenv("FRANK_SESSION_SECRET")
        if not default_secret:
            # In production, this should be set explicitly
            # For development, generate a random key
            import secrets
            default_secret = secrets.token_urlsafe(32)

        cls._instance = cls(
            management_api_url=management_api_url or os.getenv("FRANK_MANAGEMENT_API_URL", "http://localhost:8001"),
            cognito_url=cognito_url or os.getenv("COGNITO_URL", "http://localhost:8100"),
            session_secret_key=session_secret_key or default_secret,
            session_cookie_name=session_cookie_name or os.getenv("FRANK_SESSION_COOKIE_NAME", "frank_session"),
            session_max_age=session_max_age or int(os.getenv("FRANK_SESSION_MAX_AGE", "3600")),
            timeout=timeout or float(os.getenv("FRANK_API_TIMEOUT", "30.0")),
            template_auto_reload=template_auto_reload if template_auto_reload is not None
                else os.getenv("TEMPLATE_AUTO_RELOAD", "false").lower() in ("true", "1", "yes"),
        )
        return cls._instance

    @classmethod
    def get(cls) -> "WebConfig":
        """
        Get the current configuration.

        Creates default configuration if not already configured.

        Returns:
            WebConfig instance
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
            f"WebConfig(management_api_url='{self.management_api_url}', "
            f"cognito_url='{self.cognito_url}', "
            f"session_cookie_name='{self.session_cookie_name}', "
            f"session_max_age={self.session_max_age}s, "
            f"timeout={self.timeout}s, "
            f"template_auto_reload={self.template_auto_reload})"
        )
