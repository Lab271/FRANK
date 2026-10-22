#!/usr/bin/env python3
"""
FRANK Platform - Admin Token Management

Secure token storage and refresh handling for the admin TUI.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import keyring

from frank.admin.config import AdminConfig

logger = logging.getLogger(__name__)

# Keyring key names
ACCESS_TOKEN_KEY = "access_token"
REFRESH_TOKEN_KEY = "refresh_token"
TOKEN_EXPIRY_KEY = "token_expiry"
USERNAME_KEY = "username"


@dataclass
class TokenInfo:
    """Token information with expiry."""

    access_token: str
    refresh_token: Optional[str]
    expires_at: float  # Unix timestamp
    username: str

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        return time.time() >= self.expires_at

    @property
    def needs_refresh(self) -> bool:
        """Check if the token should be refreshed (within buffer period)."""
        config = AdminConfig.get()
        buffer_seconds = config.token_refresh_buffer * 60
        return time.time() >= (self.expires_at - buffer_seconds)

    @property
    def expires_in_seconds(self) -> int:
        """Seconds until token expires."""
        return max(0, int(self.expires_at - time.time()))


class TokenManager:
    """
    Manages token storage and retrieval using system keyring.

    Provides secure storage for access and refresh tokens.
    """

    def __init__(self, config: Optional[AdminConfig] = None):
        """
        Initialize token manager.

        Args:
            config: Admin configuration (uses singleton if not provided)
        """
        self.config = config or AdminConfig.get()
        self._service = self.config.keyring_service

    def store_tokens(
        self,
        access_token: str,
        username: str,
        expires_in: int,
        refresh_token: Optional[str] = None,
    ) -> TokenInfo:
        """
        Store tokens securely in system keyring.

        Args:
            access_token: JWT access token
            username: Authenticated username
            expires_in: Token lifetime in seconds
            refresh_token: Optional refresh token

        Returns:
            TokenInfo with stored token details
        """
        expires_at = time.time() + expires_in

        # Store tokens
        keyring.set_password(self._service, ACCESS_TOKEN_KEY, access_token)
        keyring.set_password(self._service, USERNAME_KEY, username)
        keyring.set_password(self._service, TOKEN_EXPIRY_KEY, str(expires_at))

        if refresh_token:
            keyring.set_password(self._service, REFRESH_TOKEN_KEY, refresh_token)

        logger.info(f"Stored tokens for user {username}, expires in {expires_in}s")

        return TokenInfo(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            username=username,
        )

    def get_tokens(self) -> Optional[TokenInfo]:
        """
        Retrieve stored tokens from keyring.

        Returns:
            TokenInfo if tokens exist, None otherwise
        """
        access_token = keyring.get_password(self._service, ACCESS_TOKEN_KEY)
        if not access_token:
            return None

        username = keyring.get_password(self._service, USERNAME_KEY) or "unknown"
        expiry_str = keyring.get_password(self._service, TOKEN_EXPIRY_KEY)
        refresh_token = keyring.get_password(self._service, REFRESH_TOKEN_KEY)

        expires_at = float(expiry_str) if expiry_str else 0

        return TokenInfo(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            username=username,
        )

    def get_access_token(self) -> Optional[str]:
        """Get just the access token."""
        return keyring.get_password(self._service, ACCESS_TOKEN_KEY)

    def get_refresh_token(self) -> Optional[str]:
        """Get just the refresh token."""
        return keyring.get_password(self._service, REFRESH_TOKEN_KEY)

    def clear_tokens(self) -> None:
        """Remove all stored tokens from keyring."""
        for key in [ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, TOKEN_EXPIRY_KEY, USERNAME_KEY]:
            try:
                keyring.delete_password(self._service, key)
            except keyring.errors.PasswordDeleteError:
                pass  # Key doesn't exist

        logger.info("Cleared all stored tokens")

    def has_valid_tokens(self) -> bool:
        """Check if valid (non-expired) tokens are stored."""
        tokens = self.get_tokens()
        return tokens is not None and not tokens.is_expired

    def update_access_token(self, access_token: str, expires_in: int) -> Optional[TokenInfo]:
        """
        Update access token after refresh.

        Args:
            access_token: New access token
            expires_in: New token lifetime in seconds

        Returns:
            Updated TokenInfo or None if no existing tokens
        """
        tokens = self.get_tokens()
        if not tokens:
            return None

        return self.store_tokens(
            access_token=access_token,
            username=tokens.username,
            expires_in=expires_in,
            refresh_token=tokens.refresh_token,
        )
