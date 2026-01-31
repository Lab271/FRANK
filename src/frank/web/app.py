#!/usr/bin/env python3
"""
FRANK Platform - Web GUI Application

FastAPI application factory for the web GUI.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
from pathlib import Path
from typing import Dict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import frank
from frank.web.config import WebConfig
from frank.web.dependencies import get_current_session
from frank.web.middleware.session import SessionData, SessionManager
from frank.web.routes.auth import create_auth_routes
from frank.web.routes.organisations import create_organisation_routes
from frank.web.routes.service_accounts import create_service_account_routes
from frank.web.routes.users import create_user_routes

logger = logging.getLogger(__name__)


def create_web_app(config: WebConfig = None) -> FastAPI:
    """
    Create and configure the Web GUI FastAPI application.

    Args:
        config: Web configuration instance

    Returns:
        Configured FastAPI application
    """
    if config is None:
        config = WebConfig.get()

    app = FastAPI(
        title="FRANK Web GUI",
        description="Web-based user interface for FRANK platform management",
        version=frank.__version__,
        docs_url=None,  # Disable API docs for web GUI
        redoc_url=None,
    )

    # Store config in app state
    app.state.config = config

    # Setup session manager
    session_manager = SessionManager(config)
    app.state.session_manager = session_manager

    # Exception handler for authentication failures
    @app.exception_handler(HTTPException)
    async def auth_exception_handler(request: Request, exc: HTTPException):
        """Handle 401 errors by redirecting to login for browser requests."""
        if exc.status_code == 401:
            # Redirect to login for browser requests
            return RedirectResponse(url="/login", status_code=303)
        # Re-raise other HTTP exceptions
        raise exc

    # Setup Jinja2 templates
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(
        directory=str(templates_dir),
        auto_reload=config.template_auto_reload
    )
    app.state.templates = templates

    # Mount static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Register routes
    auth_router = create_auth_routes(config, session_manager, templates)
    app.include_router(auth_router)

    org_router = create_organisation_routes(config, templates)
    app.include_router(org_router)

    user_router = create_user_routes(config, templates)
    app.include_router(user_router)

    service_account_router = create_service_account_routes(config, templates)
    app.include_router(service_account_router)

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> Dict[str, str]:
        """
        Health check endpoint.

        Returns:
            Status information
        """
        return {
            "status": "healthy",
            "service": "frank-web",
            "version": frank.__version__,
        }

    # Root endpoint - redirect based on authentication
    @app.get("/")
    async def root(request: Request):
        """
        Root endpoint - redirects to dashboard if authenticated, login otherwise.

        Args:
            request: FastAPI request object

        Returns:
            Redirect response
        """
        session = session_manager.get_session(request)
        if session and not session.is_expired():
            return RedirectResponse(url="/dashboard", status_code=303)
        else:
            return RedirectResponse(url="/login", status_code=303)

    # Dashboard - protected route
    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(
        request: Request,
        session: SessionData = Depends(get_current_session),
    ):
        """
        Dashboard page - requires authentication.

        Args:
            request: FastAPI request object
            session: Current authenticated session

        Returns:
            Rendered dashboard page
        """
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "username": session.username,
                "version": frank.__version__,
            }
        )

    logger.info(f"FRANK Web GUI application created (v{frank.__version__})")
    logger.info(f"Management API: {config.management_api_url}")
    logger.info(f"Cognito URL: {config.cognito_url}")
    logger.info(f"Template auto-reload: {config.template_auto_reload}")

    return app
