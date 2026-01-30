#!/usr/bin/env python3
"""
FRANK Platform - Session Management

HTTP session management with secure cookie storage.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request, Response

from frank.web.config import WebConfig


class SessionData:
    """Session data container."""

    def __init__(
        self,
        access_token: str,
        username: str,
        expires_at: datetime,
        refresh_token: Optional[str] = None,
    ):
        self.access_token = access_token
        self.username = username
        self.expires_at = expires_at
        self.refresh_token = refresh_token

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "access_token": self.access_token,
            "username": self.username,
            "expires_at": self.expires_at.isoformat(),
            "refresh_token": self.refresh_token,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionData":
        """Create from dictionary."""
        return cls(
            access_token=data["access_token"],
            username=data["username"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            refresh_token=data.get("refresh_token"),
        )

    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now(timezone.utc) >= self.expires_at

    def needs_refresh(self, buffer_seconds: int = 300) -> bool:
        """Check if token should be refreshed soon."""
        refresh_time = self.expires_at - timedelta(seconds=buffer_seconds)
        return datetime.now(timezone.utc) >= refresh_time


class SessionManager:
    """
    Session manager for web GUI.

    Handles secure session storage in HTTP-only cookies with encryption.
    """

    def __init__(self, config: WebConfig):
        """
        Initialize session manager.

        Args:
            config: Web configuration with session settings
        """
        self.config = config
        # Derive encryption key from session secret
        self._fernet = Fernet(self._derive_key(config.session_secret_key))

    def _derive_key(self, secret: str) -> bytes:
        """
        Derive a Fernet key from the session secret.

        Args:
            secret: Session secret string

        Returns:
            Base64-encoded Fernet key
        """
        from base64 import urlsafe_b64encode
        from hashlib import sha256

        # Hash the secret to get 32 bytes, then base64 encode for Fernet
        key_bytes = sha256(secret.encode()).digest()
        return urlsafe_b64encode(key_bytes)

    def _encrypt(self, data: str) -> str:
        """Encrypt session data."""
        return self._fernet.encrypt(data.encode()).decode()

    def _decrypt(self, encrypted: str) -> str:
        """Decrypt session data."""
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except InvalidToken:
            raise ValueError("Invalid or corrupted session data")

    def create_session(
        self,
        response: Response,
        access_token: str,
        username: str,
        expires_in: int,
        refresh_token: Optional[str] = None,
    ) -> None:
        """
        Create a new session and set cookie.

        Args:
            response: FastAPI response object
            access_token: JWT access token
            username: Authenticated username
            expires_in: Token expiration time in seconds
            refresh_token: Optional refresh token
        """
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        session_data = SessionData(
            access_token=access_token,
            username=username,
            expires_at=expires_at,
            refresh_token=refresh_token,
        )

        # Serialize and encrypt session data
        session_json = json.dumps(session_data.to_dict())
        encrypted = self._encrypt(session_json)

        # Set HTTP-only secure cookie
        response.set_cookie(
            key=self.config.session_cookie_name,
            value=encrypted,
            max_age=self.config.session_max_age,
            httponly=True,  # Prevent JavaScript access
            secure=True,  # HTTPS only (set False for local development)
            samesite="lax",  # CSRF protection
        )

    def get_session(self, request: Request) -> Optional[SessionData]:
        """
        Retrieve session from cookie.

        Args:
            request: FastAPI request object

        Returns:
            SessionData if valid session exists, None otherwise
        """
        cookie_value = request.cookies.get(self.config.session_cookie_name)
        if not cookie_value:
            return None

        try:
            # Decrypt and deserialize session data
            session_json = self._decrypt(cookie_value)
            session_dict = json.loads(session_json)
            session = SessionData.from_dict(session_dict)

            # Check if session is expired
            if session.is_expired():
                return None

            return session

        except (ValueError, KeyError, json.JSONDecodeError):
            # Invalid session data
            return None

    def clear_session(self, response: Response) -> None:
        """
        Clear session cookie.

        Args:
            response: FastAPI response object
        """
        response.delete_cookie(key=self.config.session_cookie_name)

    def update_session(
        self,
        response: Response,
        session: SessionData,
    ) -> None:
        """
        Update existing session (e.g., after token refresh).

        Args:
            response: FastAPI response object
            session: Updated session data
        """
        # Re-encrypt and update cookie
        session_json = json.dumps(session.to_dict())
        encrypted = self._encrypt(session_json)

        response.set_cookie(
            key=self.config.session_cookie_name,
            value=encrypted,
            max_age=self.config.session_max_age,
            httponly=True,
            secure=True,
            samesite="lax",
        )
