#!/usr/bin/env python3
"""
FRANK Platform - Organisation Routes

Organisation CRUD operations for web GUI.

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

router = APIRouter(prefix="/organisations", tags=["organisations"])


async def fetch_organisations(
    management_api_url: str,
    access_token: str,
) -> list:
    """
    Fetch organisations from Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token

    Returns:
        List of organisation dictionaries
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{management_api_url}/v1/organisations",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("organisations", [])
            else:
                logger.warning(f"Failed to fetch organisations: {response.status_code}")
                return []

        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return []


async def fetch_organisation(
    management_api_url: str,
    access_token: str,
    organisation_id: str,
) -> Optional[dict]:
    """
    Fetch single organisation from Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token
        organisation_id: Organisation ID

    Returns:
        Organisation dictionary or None if not found
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{management_api_url}/v1/organisations/{organisation_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to fetch organisation {organisation_id}: {response.status_code}")
                return None

        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            return None


async def create_organisation(
    management_api_url: str,
    access_token: str,
    org_data: dict,
) -> tuple[bool, Optional[str]]:
    """
    Create organisation via Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token
        org_data: Organisation data dictionary

    Returns:
        Tuple of (success, error_message)
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{management_api_url}/v1/organisations",
                json=org_data,
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


async def update_organisation(
    management_api_url: str,
    access_token: str,
    organisation_id: str,
    org_data: dict,
) -> tuple[bool, Optional[str]]:
    """
    Update organisation via Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token
        organisation_id: Organisation ID
        org_data: Organisation data dictionary

    Returns:
        Tuple of (success, error_message)
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(
                f"{management_api_url}/v1/organisations/{organisation_id}",
                json=org_data,
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


async def delete_organisation(
    management_api_url: str,
    access_token: str,
    organisation_id: str,
) -> tuple[bool, Optional[str]]:
    """
    Delete organisation via Management API.

    Args:
        management_api_url: Management API base URL
        access_token: JWT access token
        organisation_id: Organisation ID

    Returns:
        Tuple of (success, error_message)
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(
                f"{management_api_url}/v1/organisations/{organisation_id}",
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


def create_organisation_routes(config: WebConfig, templates) -> APIRouter:
    """
    Create organisation routes with dependencies.

    Args:
        config: Web configuration
        templates: Jinja2Templates instance

    Returns:
        Configured router
    """

    @router.get("", response_class=HTMLResponse)
    async def list_organisations(
        request: Request,
        session: SessionData = Depends(get_current_session),
    ):
        """
        List all organisations.

        Args:
            request: FastAPI request
            session: Current session

        Returns:
            Rendered organisations list page
        """
        # Fetch organisations from API
        organisations = await fetch_organisations(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
        )

        return templates.TemplateResponse(
            "organisations/list.html",
            {
                "request": request,
                "username": session.username,
                "organisations": organisations,
            },
        )

    @router.get("/new", response_class=HTMLResponse)
    async def new_organisation_form(
        request: Request,
        session: SessionData = Depends(get_current_session),
        error: Optional[str] = None,
    ):
        """
        Display new organisation form.

        Args:
            request: FastAPI request
            session: Current session
            error: Optional error message

        Returns:
            Rendered new organisation form
        """
        return templates.TemplateResponse(
            "organisations/new.html",
            {
                "request": request,
                "username": session.username,
                "error": error,
            },
        )

    @router.post("/new")
    async def create_organisation_submit(
        request: Request,
        session: SessionData = Depends(get_current_session),
        name: str = Form(...),
        tier: str = Form(...),
    ):
        """
        Handle new organisation form submission.

        Args:
            request: FastAPI request
            session: Current session
            name: Organisation name
            tier: Access tier (PUBLIC, OBSERVER, CONTRIBUTOR, PARTNER, CORE_MEMBER)

        Returns:
            Redirect to list or form with error
        """
        # Validate inputs
        if not name or len(name.strip()) == 0:
            return RedirectResponse(
                url="/organisations/new?error=Organisation+name+is+required",
                status_code=303,
            )

        # Create organisation
        org_data = {
            "name": name.strip(),
            "access_level": tier.lower(),
        }

        success, error = await create_organisation(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
            org_data=org_data,
        )

        if success:
            logger.info(f"Organisation '{name}' created by {session.username}")
            return RedirectResponse(url="/organisations", status_code=303)
        else:
            logger.warning(f"Failed to create organisation: {error}")
            return RedirectResponse(
                url=f"/organisations/new?error={error}",
                status_code=303,
            )

    @router.get("/{organisation_id}", response_class=HTMLResponse)
    async def view_organisation(
        request: Request,
        organisation_id: str,
        session: SessionData = Depends(get_current_session),
    ):
        """
        View organisation details.

        Args:
            request: FastAPI request
            organisation_id: Organisation ID
            session: Current session

        Returns:
            Rendered organisation view page
        """
        organisation = await fetch_organisation(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
            organisation_id=organisation_id,
        )

        if not organisation:
            return RedirectResponse(url="/organisations?error=Organisation+not+found", status_code=303)

        return templates.TemplateResponse(
            "organisations/view.html",
            {
                "request": request,
                "username": session.username,
                "organisation": organisation,
            },
        )

    @router.get("/{organisation_id}/edit", response_class=HTMLResponse)
    async def edit_organisation_form(
        request: Request,
        organisation_id: str,
        session: SessionData = Depends(get_current_session),
        error: Optional[str] = None,
    ):
        """
        Display edit organisation form.

        Args:
            request: FastAPI request
            organisation_id: Organisation ID
            session: Current session
            error: Optional error message

        Returns:
            Rendered edit organisation form
        """
        organisation = await fetch_organisation(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
            organisation_id=organisation_id,
        )

        if not organisation:
            return RedirectResponse(url="/organisations?error=Organisation+not+found", status_code=303)

        return templates.TemplateResponse(
            "organisations/edit.html",
            {
                "request": request,
                "username": session.username,
                "organisation": organisation,
                "error": error,
            },
        )

    @router.post("/{organisation_id}/edit")
    async def update_organisation_submit(
        request: Request,
        organisation_id: str,
        session: SessionData = Depends(get_current_session),
        name: str = Form(...),
        tier: str = Form(...),
    ):
        """
        Handle edit organisation form submission.

        Args:
            request: FastAPI request
            organisation_id: Organisation ID
            session: Current session
            name: Organisation name
            tier: Access tier

        Returns:
            Redirect to view or form with error
        """
        # Validate inputs
        if not name or len(name.strip()) == 0:
            return RedirectResponse(
                url=f"/organisations/{organisation_id}/edit?error=Organisation+name+is+required",
                status_code=303,
            )

        # Update organisation
        org_data = {
            "name": name.strip(),
            "access_level": tier.lower(),
        }

        success, error = await update_organisation(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
            organisation_id=organisation_id,
            org_data=org_data,
        )

        if success:
            logger.info(f"Organisation '{organisation_id}' updated by {session.username}")
            return RedirectResponse(url=f"/organisations/{organisation_id}", status_code=303)
        else:
            logger.warning(f"Failed to update organisation: {error}")
            return RedirectResponse(
                url=f"/organisations/{organisation_id}/edit?error={error}",
                status_code=303,
            )

    @router.post("/{organisation_id}/delete")
    async def delete_organisation_submit(
        request: Request,
        organisation_id: str,
        session: SessionData = Depends(get_current_session),
    ):
        """
        Handle organisation deletion.

        Args:
            request: FastAPI request
            organisation_id: Organisation ID
            session: Current session

        Returns:
            Redirect to list
        """
        success, error = await delete_organisation(
            management_api_url=config.management_api_url,
            access_token=session.access_token,
            organisation_id=organisation_id,
        )

        if success:
            logger.info(f"Organisation '{organisation_id}' deleted by {session.username}")
            return RedirectResponse(url="/organisations", status_code=303)
        else:
            logger.warning(f"Failed to delete organisation: {error}")
            return RedirectResponse(
                url=f"/organisations?error={error}",
                status_code=303,
            )

    return router
