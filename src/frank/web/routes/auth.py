#!/usr/bin/env python3
"""
FRANK Platform - Authentication Routes

Login, logout, and session management routes.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from frank.web.config import WebConfig
from frank.web.middleware.session import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["authentication"])


async def authenticate_user(
    username: str,
    password: str,
    cognito_url: str,
) -> Optional[dict]:
    """
    Authenticate user with Cognito service.

    Args:
        username: Username
        password: Password
        cognito_url: Cognito service URL

    Returns:
        Token response dict or None if authentication failed
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{cognito_url}/auth/login",
                json={"username": username, "password": password},
                timeout=10.0,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Auth failed for {username}: {response.status_code}")
                return None

        except httpx.RequestError as e:
            logger.error(f"Auth request failed: {e}")
            return None


def create_auth_routes(
    config: WebConfig,
    session_manager: SessionManager,
    templates,
) -> APIRouter:
    """
    Create authentication routes with dependencies.

    Args:
        config: Web configuration
        session_manager: Session manager instance
        templates: Jinja2Templates instance

    Returns:
        Configured router
    """

    @router.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request, error: Optional[str] = None):
        """
        Display login page.

        Args:
            request: FastAPI request
            error: Optional error message to display

        Returns:
            Rendered login page
        """
        # Check if already logged in
        session = session_manager.get_session(request)
        if session and not session.is_expired():
            return RedirectResponse(url="/dashboard", status_code=303)

        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": error,
            },
        )

    @router.post("/login")
    async def login_submit(
        request: Request,
        response: Response,
        username: str = Form(...),
        password: str = Form(...),
    ):
        """
        Process login form submission.

        Args:
            request: FastAPI request
            response: FastAPI response
            username: Username from form
            password: Password from form

        Returns:
            Redirect to dashboard or login page with error
        """
        # Authenticate with Cognito
        token_data = await authenticate_user(
            username=username,
            password=password,
            cognito_url=config.cognito_url,
        )

        if not token_data:
            # Authentication failed - redirect back to login with error
            return RedirectResponse(
                url="/login?error=Invalid+username+or+password",
                status_code=303,
            )

        # Create redirect response
        redirect = RedirectResponse(url="/dashboard", status_code=303)

        # Create session on the redirect response
        session_manager.create_session(
            response=redirect,
            access_token=token_data["access_token"],
            username=username,
            expires_in=token_data.get("expires_in", 3600),
            refresh_token=token_data.get("refresh_token"),
        )

        logger.info(f"User {username} logged in successfully")

        return redirect

    @router.get("/logout")
    @router.post("/logout")
    async def logout(request: Request, response: Response):
        """
        Logout and clear session.

        Args:
            request: FastAPI request
            response: FastAPI response

        Returns:
            Redirect to login page
        """
        session = session_manager.get_session(request)
        if session:
            logger.info(f"User {session.username} logged out")

        # Create redirect response first
        redirect = RedirectResponse(url="/login", status_code=303)

        # Clear session cookie on the redirect response
        session_manager.clear_session(redirect)

        return redirect

    return router
