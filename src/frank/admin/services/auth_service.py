#!/usr/bin/env python3
"""
FRANK Platform - Authentication Service

Service layer for authentication operations.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from frank.admin.client import AdminClientError, AuthenticationError

if TYPE_CHECKING:
    from frank.admin.client import AdminClient


@dataclass
class AuthResult:
    """Result of authentication operation."""

    success: bool
    username: Optional[str] = None
    error: Optional[str] = None
    expires_in: Optional[int] = None

    @classmethod
    def success_result(cls, username: str, expires_in: int) -> "AuthResult":
        """Create successful auth result."""
        return cls(success=True, username=username, expires_in=expires_in)

    @classmethod
    def failure_result(cls, error: str) -> "AuthResult":
        """Create failed auth result."""
        return cls(success=False, error=error)


class AuthService:
    """
    Authentication service.

    Handles login, logout, and token management operations.
    Provides a clean interface between views and the client.
    """

    def __init__(self, client: "AdminClient"):
        """
        Initialize auth service.

        Args:
            client: Admin API client instance
        """
        self.client = client

    async def login(self, username: str, password: str) -> AuthResult:
        """
        Perform login with username and password.

        Args:
            username: User's username
            password: User's password

        Returns:
            AuthResult with success/failure information
        """
        if not username or not password:
            return AuthResult.failure_result("Username and password are required")

        try:
            data = await self.client.login(username, password)
            return AuthResult.success_result(
                username=username,
                expires_in=data.get("expires_in", 3600),
            )
        except AuthenticationError as e:
            return AuthResult.failure_result("Invalid username or password")
        except AdminClientError as e:
            return AuthResult.failure_result(f"Connection error: {e.message}")
        except Exception as e:
            return AuthResult.failure_result(f"Unexpected error: {str(e)}")

    async def logout(self) -> None:
        """
        Logout and clear stored tokens.
        """
        await self.client.logout()

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated.

        Returns:
            True if valid tokens exist
        """
        return self.client.token_manager.has_valid_tokens()

    def get_current_user(self) -> Optional[str]:
        """
        Get the currently authenticated username.

        Returns:
            Username or None if not authenticated
        """
        tokens = self.client.token_manager.get_tokens()
        return tokens.username if tokens else None

    def token_needs_refresh(self) -> bool:
        """
        Check if the current token needs refreshing.

        Returns:
            True if token should be refreshed soon
        """
        tokens = self.client.token_manager.get_tokens()
        return tokens.needs_refresh if tokens else False
