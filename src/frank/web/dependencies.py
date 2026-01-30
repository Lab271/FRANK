#!/usr/bin/env python3
"""
FRANK Platform - Web GUI Dependencies

FastAPI dependencies for authentication and authorization.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from fastapi import Depends, HTTPException, Request

from frank.web.middleware.session import SessionData, SessionManager


def get_session_manager(request: Request) -> SessionManager:
    """
    Dependency to get session manager from app state.

    Args:
        request: FastAPI request

    Returns:
        SessionManager instance
    """
    return request.app.state.session_manager


def get_current_session(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
) -> SessionData:
    """
    Dependency to get current authenticated session.

    Redirects to login if not authenticated.

    Args:
        request: FastAPI request
        session_manager: Session manager instance

    Returns:
        Current session data

    Raises:
        HTTPException: 401 if not authenticated
    """
    session = session_manager.get_session(request)

    if not session or session.is_expired():
        # Not authenticated - raise 401
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"Location": "/login"},
        )

    return session


def get_optional_session(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
) -> SessionData | None:
    """
    Dependency to get current session if authenticated, None otherwise.

    Does not redirect if not authenticated.

    Args:
        request: FastAPI request
        session_manager: Session manager instance

    Returns:
        Current session data or None
    """
    session = session_manager.get_session(request)

    if not session or session.is_expired():
        return None

    return session
