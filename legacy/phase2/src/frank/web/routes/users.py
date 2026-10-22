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
from frank.web.routes.organisations import fetch_organisations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


async def fetch_users(
    management_api_url: str,
    access_token: str,
) -> list:
    """
    Fetch users from Management API by aggregating from all organisations.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token

    Returns:
        List of user dictionaries with organisation information
    """
    # First fetch all organisations
    organisations = await fetch_organisations(management_api_url, access_token)

    if not organisations:
        return []

    all_users = []
    async with httpx.AsyncClient() as client:
        # Fetch users from each organisation
        for org in organisations:
            org_id = org.get("organisation_id")
            org_name = org.get("name", "Unknown")

            try:
                response = await client.get(
                    f"{management_api_url}/v1/organisations/{org_id}/users",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    org_users = data.get("users", [])
                    # Add organisation context to each user
                    for user in org_users:
                        user["organisation_name"] = org_name
                        user["organisation_id"] = org_id
                    all_users.extend(org_users)
                else:
                    logger.warning(f"Failed to fetch users for org {org_id}: {response.status_code}")

            except httpx.RequestError as e:
                logger.error(f"Request failed for org {org_id}: {e}")
                continue

    return all_users


async def fetch_user(
    management_api_url: str,
    access_token: str,
    username: str,
) -> Optional[dict]:
    """
    Fetch single user from Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token
        username: Username

    Returns:
        User dictionary or None if not found
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{management_api_url}/v1/users/{username}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to fetch user {username}: {response.status_code}")
                return None

        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return None


async def create_user(
    management_api_url: str,
    access_token: str,
    organisation_id: str,
    user_data: dict,
) -> tuple[bool, Optional[str]]:
    """
    Create user via Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token
        organisation_id: Organisation ID to add user to
        user_data: User data dictionary

    Returns:
        Tuple of (success, error_message)
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{management_api_url}/v1/organisations/{organisation_id}/users",
                json=user_data,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 201:
                return True, None
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("detail", f"Failed with status {response.status_code}")
                except Exception:
                    error_msg = f"Failed with status {response.status_code}"
                return False, error_msg

        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return False, f"Connection error: {str(e)}"


async def update_user(
    management_api_url: str,
    access_token: str,
    username: str,
    user_data: dict,
) -> tuple[bool, Optional[str]]:
    """
    Update user via Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token
        username: Username
        user_data: User data dictionary

    Returns:
        Tuple of (success, error_message)
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(
                f"{management_api_url}/v1/users/{username}",
                json=user_data,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                return True, None
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("detail", f"Failed with status {response.status_code}")
                except Exception:
                    error_msg = f"Failed with status {response.status_code}"
                return False, error_msg

        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return False, f"Connection error: {str(e)}"


async def delete_user(
    management_api_url: str,
    access_token: str,
    username: str,
) -> tuple[bool, Optional[str]]:
    """
    Delete user via Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token
        username: Username

    Returns:
        Tuple of (success, error_message)
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(
                f"{management_api_url}/v1/users/{username}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code in (200, 204):
                return True, None
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("detail", f"Failed with status {response.status_code}")
                except Exception:
                    error_msg = f"Failed with status {response.status_code}"
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
            request,
            "users/list.html",
            {
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
        # Fetch organisations for the dropdown
        organisations = await fetch_organisations(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
        )

        return templates.TemplateResponse(
            request,
            "users/new.html",
            {
                "username": session.username,
                "error": error,
                "organisations": organisations,
            },
        )

    @router.post("/new")
    async def create_user_submit(
        request: Request,
        session: SessionData = Depends(get_current_session),
        username: str = Form(...),
        email: str = Form(...),
        organisation_id: str = Form(...),
        password: str = Form(...),
    ):
        """
        Handle new user form submission.

        Args:
            request: FastAPI request
            session: Current session
            username: Username for new user
            email: Email address
            organisation_id: Organisation to add user to
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

        if not organisation_id:
            return RedirectResponse(
                url="/users/new?error=Organisation+is+required",
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
            organisation_id=organisation_id,
            user_data=user_data,
        )

        if success:
            logger.info(f"User '{username}' created in organisation {organisation_id} by {session.username}")
            return RedirectResponse(url="/users", status_code=303)
        else:
            logger.warning(f"Failed to create user: {error}")
            return RedirectResponse(
                url=f"/users/new?error={error}",
                status_code=303,
            )

    @router.get("/{username}", response_class=HTMLResponse)
    async def view_user(
        request: Request,
        username: str,
        session: SessionData = Depends(get_current_session),
    ):
        """
        View user details.

        Args:
            request: FastAPI request
            username: Username
            session: Current session

        Returns:
            Rendered user view page
        """
        user = await fetch_user(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
            username=username,
        )

        if not user:
            return RedirectResponse(url="/users?error=User+not+found", status_code=303)

        return templates.TemplateResponse(
            request,
            "users/view.html",
            {
                "username": session.username,
                "user": user,
            },
        )

    @router.get("/{username}/edit", response_class=HTMLResponse)
    async def edit_user_form(
        request: Request,
        username: str,
        session: SessionData = Depends(get_current_session),
        error: Optional[str] = None,
    ):
        """
        Display edit user form.

        Args:
            request: FastAPI request
            username: Username
            session: Current session
            error: Optional error message

        Returns:
            Rendered edit user form
        """
        user = await fetch_user(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
            username=username,
        )

        if not user:
            return RedirectResponse(url="/users?error=User+not+found", status_code=303)

        return templates.TemplateResponse(
            request,
            "users/edit.html",
            {
                "username": session.username,
                "user": user,
                "error": error,
            },
        )

    @router.post("/{username}/edit")
    async def update_user_submit(
        request: Request,
        username: str,
        session: SessionData = Depends(get_current_session),
        email: str = Form(...),
    ):
        """
        Handle edit user form submission.

        Args:
            request: FastAPI request
            username: Username
            session: Current session
            email: Email address

        Returns:
            Redirect to view or form with error
        """
        # Validate inputs
        if not email or "@" not in email:
            return RedirectResponse(
                url=f"/users/{username}/edit?error=Valid+email+is+required",
                status_code=303,
            )

        # Update user
        user_data = {
            "email": email.strip(),
        }

        success, error = await update_user(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
            username=username,
            user_data=user_data,
        )

        if success:
            logger.info(f"User '{username}' updated by {session.username}")
            return RedirectResponse(url=f"/users/{username}", status_code=303)
        else:
            logger.warning(f"Failed to update user: {error}")
            return RedirectResponse(
                url=f"/users/{username}/edit?error={error}",
                status_code=303,
            )

    @router.post("/{username}/delete")
    async def delete_user_submit(
        request: Request,
        username: str,
        session: SessionData = Depends(get_current_session),
    ):
        """
        Handle user deletion.

        Args:
            request: FastAPI request
            username: Username
            session: Current session

        Returns:
            Redirect to list
        """
        success, error = await delete_user(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
            username=username,
        )

        if success:
            logger.info(f"User '{username}' deleted by {session.username}")
            return RedirectResponse(url="/users", status_code=303)
        else:
            logger.warning(f"Failed to delete user: {error}")
            return RedirectResponse(
                url=f"/users?error={error}",
                status_code=303,
            )

    return router
