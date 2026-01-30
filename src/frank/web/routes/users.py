#!/usr/bin/env python3
"""
FRANK Platform - User Routes

User CRUD operations for web GUI.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from frank.web.config import WebConfig
from frank.web.dependencies import get_current_session
from frank.web.middleware.session import SessionData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


async def fetch_users(
    management_api_url: str,
    access_token: str,
) -> list:
    """
    Fetch users from Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token

    Returns:
        List of user dictionaries
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{management_api_url}/v1/users",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("users", [])
            else:
                logger.warning(f"Failed to fetch users: {response.status_code}")
                return []

        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return []


async def create_user(
    management_api_url: str,
    access_token: str,
    user_data: dict,
) -> tuple[bool, Optional[str]]:
    """
    Create user via Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token
        user_data: User data dictionary

    Returns:
        Tuple of (success, error_message)
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{management_api_url}/v1/users",
                json=user_data,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 201:
                return True, None
            else:
                error_data = response.json()
                error_msg = error_data.get("detail", f"Failed with status {response.status_code}")
                return False, error_msg

        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return False, f"Connection error: {str(e)}"


def create_user_routes(config: WebConfig, templates) -> APIRouter:
    """
    Create user routes with dependencies.

    Args:
        config: Web configuration
        templates: Jinja2Templates instance

    Returns:
        Configured router
    """

    @router.get("", response_class=HTMLResponse)
    async def list_users(
        request: Request,
        session: SessionData = Depends(get_current_session),
    ):
        """
        List all users.

        Args:
            request: FastAPI request
            session: Current session

        Returns:
            Rendered users list page
        """
        # Fetch users from API
        users = await fetch_users(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
        )

        return templates.TemplateResponse(
            "users/list.html",
            {
                "request": request,
                "username": session.username,
                "users": users,
            },
        )

    @router.get("/new", response_class=HTMLResponse)
    async def new_user_form(
        request: Request,
        session: SessionData = Depends(get_current_session),
        error: Optional[str] = None,
    ):
        """
        Display new user form.

        Args:
            request: FastAPI request
            session: Current session
            error: Optional error message

        Returns:
            Rendered new user form
        """
        return templates.TemplateResponse(
            "users/new.html",
            {
                "request": request,
                "username": session.username,
                "error": error,
            },
        )

    @router.post("/new")
    async def create_user_submit(
        request: Request,
        session: SessionData = Depends(get_current_session),
        username: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
    ):
        """
        Handle new user form submission.

        Args:
            request: FastAPI request
            session: Current session
            username: Username for new user
            email: Email address
            password: Temporary password

        Returns:
            Redirect to list or form with error
        """
        # Validate inputs
        if not username or len(username.strip()) == 0:
            return RedirectResponse(
                url="/users/new?error=Username+is+required",
                status_code=303,
            )

        if not email or "@" not in email:
            return RedirectResponse(
                url="/users/new?error=Valid+email+is+required",
                status_code=303,
            )

        # Create user
        user_data = {
            "username": username.strip(),
            "email": email.strip(),
            "password": password,
        }

        success, error = await create_user(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
            user_data=user_data,
        )

        if success:
            logger.info(f"User '{username}' created by {session.username}")
            return RedirectResponse(url="/users", status_code=303)
        else:
            logger.warning(f"Failed to create user: {error}")
            return RedirectResponse(
                url=f"/users/new?error={error}",
                status_code=303,
            )

    return router
