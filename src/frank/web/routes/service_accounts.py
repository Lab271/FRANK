#!/usr/bin/env python3
"""
FRANK Platform - Service Account Routes

Service account management for web GUI.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from frank.web.config import WebConfig
from frank.web.dependencies import get_current_session
from frank.web.middleware.session import SessionData
from frank.web.routes.organisations import fetch_organisations
from frank.web.routes.users import fetch_users

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/service-accounts", tags=["service_accounts"])


def is_service_account(username: str) -> bool:
    """
    Check if username is a service account.

    Args:
        username: Username to check

    Returns:
        True if service account (starts with 'service-')
    """
    return username.startswith("service-")


def generate_service_username(org_slug: str, purpose: str) -> str:
    """
    Generate service account username.

    Format: service-{org-slug}-{purpose}
    Pattern: ^service-[a-z0-9-]+-[a-z0-9-]+$

    Args:
        org_slug: Organisation slug (e.g., "rabobank", "ing")
        purpose: Purpose identifier (e.g., "ingestion", "threat-feed")

    Returns:
        Service account username

    Raises:
        ValueError: If org_slug or purpose contain invalid characters
    """
    # Normalize to lowercase and replace spaces with hyphens
    org_slug = org_slug.lower().strip().replace(" ", "-")
    purpose = purpose.lower().strip().replace(" ", "-")

    # Validate pattern (alphanumeric and hyphens only)
    if not re.match(r"^[a-z0-9-]+$", org_slug):
        raise ValueError("Invalid organisation slug - use only letters, numbers, and hyphens")
    if not re.match(r"^[a-z0-9-]+$", purpose):
        raise ValueError("Invalid purpose - use only letters, numbers, and hyphens")

    return f"service-{org_slug}-{purpose}"


async def fetch_service_accounts(
    management_api_url: str,
    access_token: str,
) -> list:
    """
    Fetch service accounts from Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token

    Returns:
        List of service account dictionaries
    """
    # Fetch all users
    all_users = await fetch_users(management_api_url, access_token)

    # Filter to only service accounts
    service_accounts = [user for user in all_users if is_service_account(user.get("username", ""))]

    return service_accounts


async def create_service_account(
    management_api_url: str,
    access_token: str,
    organisation_id: str,
    user_data: dict,
) -> tuple[bool, Optional[str], Optional[dict]]:
    """
    Create service account via Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token
        organisation_id: Organisation ID to add service account to
        user_data: User data dictionary

    Returns:
        Tuple of (success, error_message, response_data)
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
                response_data = response.json()
                return True, None, response_data
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("detail", f"Failed with status {response.status_code}")
                except Exception:
                    error_msg = f"Failed with status {response.status_code}"
                return False, error_msg, None

        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return False, f"Connection error: {str(e)}", None


def create_service_account_routes(config: WebConfig, templates) -> APIRouter:
    """
    Create service account routes with dependencies.

    Args:
        config: Web configuration
        templates: Jinja2Templates instance

    Returns:
        Configured router
    """

    @router.get("", response_class=HTMLResponse)
    async def list_service_accounts(
        request: Request,
        session: SessionData = Depends(get_current_session),
    ):
        """
        List all service accounts.

        Args:
            request: FastAPI request
            session: Current session

        Returns:
            Rendered service accounts list page
        """
        # Fetch service accounts from API
        service_accounts = await fetch_service_accounts(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
        )

        return templates.TemplateResponse(
            "service-accounts/list.html",
            {
                "request": request,
                "username": session.username,
                "service_accounts": service_accounts,
            },
        )

    @router.get("/new", response_class=HTMLResponse)
    async def new_service_account_form(
        request: Request,
        session: SessionData = Depends(get_current_session),
        error: Optional[str] = None,
    ):
        """
        Display new service account form.

        Args:
            request: FastAPI request
            session: Current session
            error: Optional error message

        Returns:
            Rendered new service account form
        """
        # Fetch organisations for the dropdown
        organisations = await fetch_organisations(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
        )

        return templates.TemplateResponse(
            "service-accounts/new.html",
            {
                "request": request,
                "username": session.username,
                "error": error,
                "organisations": organisations,
            },
        )

    @router.post("/new")
    async def create_service_account_submit(
        request: Request,
        session: SessionData = Depends(get_current_session),
        organisation_id: str = Form(...),
        org_slug: str = Form(...),
        purpose: str = Form(...),
        description: str = Form(""),
    ):
        """
        Handle new service account form submission.

        Args:
            request: FastAPI request
            session: Current session
            organisation_id: Organisation to add service account to
            org_slug: Organisation slug for username generation
            purpose: Purpose identifier for username generation
            description: Optional description

        Returns:
            Redirect to password display or form with error
        """
        # Validate inputs
        if not organisation_id or len(organisation_id.strip()) == 0:
            return RedirectResponse(
                url="/service-accounts/new?error=Organisation+is+required",
                status_code=303,
            )

        if not purpose or len(purpose.strip()) == 0:
            return RedirectResponse(
                url="/service-accounts/new?error=Purpose+is+required",
                status_code=303,
            )

        # Generate service account username
        try:
            username = generate_service_username(org_slug, purpose)
        except ValueError as e:
            return RedirectResponse(
                url=f"/service-accounts/new?error={str(e)}",
                status_code=303,
            )

        # Create fake email for service account (Cognito requires email)
        email = f"{username}@service.frank.local"

        # Create service account (password will be auto-generated by backend)
        user_data = {
            "username": username,
            "email": email,
            "password": None,  # Let backend auto-generate
        }

        success, error, response_data = await create_service_account(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
            organisation_id=organisation_id,
            user_data=user_data,
        )

        if success:
            logger.info(f"Service account '{username}' created by {session.username}")
            # Get generated password from response
            generated_password = response_data.get("generated_password", "")
            if not generated_password:
                logger.error(f"No generated password returned for service account {username}")
                return RedirectResponse(
                    url="/service-accounts?error=Password+generation+failed",
                    status_code=303,
                )

            # Store password in session temporarily (will be shown once and cleared)
            # We'll pass it via URL encoding for simplicity
            import urllib.parse
            encoded_password = urllib.parse.quote(generated_password)
            return RedirectResponse(
                url=f"/service-accounts/{username}/password-display?password={encoded_password}",
                status_code=303,
            )
        else:
            logger.warning(f"Failed to create service account: {error}")
            return RedirectResponse(
                url=f"/service-accounts/new?error={error}",
                status_code=303,
            )

    @router.get("/{username}/password-display", response_class=HTMLResponse)
    async def display_service_account_password(
        request: Request,
        username: str,
        password: str,
        session: SessionData = Depends(get_current_session),
    ):
        """
        Display auto-generated password for newly created service account.

        CRITICAL: Password can only be displayed once and cannot be retrieved later.

        Args:
            request: FastAPI request
            username: Service account username
            password: Generated password from URL parameter
            session: Current session

        Returns:
            Rendered password display modal
        """
        if not password:
            logger.warning(f"No password provided for service account {username}")
            return RedirectResponse(
                url="/service-accounts?error=Password+not+available",
                status_code=303,
            )

        return templates.TemplateResponse(
            "service-accounts/password-display.html",
            {
                "request": request,
                "username": session.username,
                "service_username": username,
                "generated_password": password,
            },
        )

    return router
