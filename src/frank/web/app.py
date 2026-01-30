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

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import frank
from frank.web.config import WebConfig

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

    # Root endpoint - temporary landing page
    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        """
        Root endpoint - renders landing page.

        Args:
            request: FastAPI request object

        Returns:
            Rendered HTML page
        """
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "title": "FRANK Web GUI",
                "version": frank.__version__,
            }
        )

    logger.info(f"FRANK Web GUI application created (v{frank.__version__})")
    logger.info(f"Management API: {config.management_api_url}")
    logger.info(f"Cognito URL: {config.cognito_url}")
    logger.info(f"Template auto-reload: {config.template_auto_reload}")

    return app
