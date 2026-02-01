#!/usr/bin/env python3
"""
FRANK Platform - Main API (Sightings API)

FastAPI application for threat intelligence submission and queries.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

import frank
from frank.auth import TokenPayload, get_current_user
from frank.config import EnvironmentConfig
from frank.core.models import Submission
from frank.main.models import (
    DeepHealthResponse,
    HealthResponse,
    SubmissionRequest,
    SubmissionResponse,
)
from frank.management.models import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from frank.storage.base import BaseFRANKDatabase

logger = logging.getLogger(__name__)


def create_main_app(
    database: Optional[BaseFRANKDatabase] = None,
) -> FastAPI:
    """
    Create and configure the Main API (Sightings API) FastAPI application.

    Args:
        database: Database instance for threat intelligence storage

    Returns:
        Configured FastAPI application
    """

    app = FastAPI(
        title="FRANK Main API",
        description="Threat intelligence submission and query API for the FRANK platform",
        version=frank.__version__,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store database in app state
    app.state.database = database

    # Get environment configuration
    env_config = EnvironmentConfig.get()
    logger.info(
        f"Main API configured for {env_config.environment.value} "
        f"(Stage {env_config.stage})"
    )

    # ==================== Health Endpoints ====================

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Basic health check"
    )
    async def health_check():
        """
        Basic health check endpoint.

        Returns service status and version information.
        """
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(timezone.utc),
            version=frank.__version__
        )

    @app.get(
        "/health/deep",
        response_model=DeepHealthResponse,
        tags=["Health"],
        summary="Deep health check"
    )
    async def deep_health_check():
        """
        Deep health check with component validation.

        Checks:
        - Database connectivity (DynamoDB/SQLite)
        - Authentication service availability
        """
        components = {}
        overall_status = "healthy"

        # Check database connectivity
        if app.state.database:
            try:
                db_health = await app.state.database.health_check()
                components["database"] = {
                    "status": "healthy" if db_health else "unhealthy",
                    "type": app.state.database.name if hasattr(app.state.database, 'name') else "unknown"
                }
                if not db_health:
                    overall_status = "degraded"
            except Exception as e:
                components["database"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                overall_status = "unhealthy"
        else:
            components["database"] = {
                "status": "not_configured"
            }
            overall_status = "degraded"

        # Check authentication
        components["authentication"] = {
            "status": "healthy",
            "type": "cognito",
            "environment": env_config.environment.value
        }

        return DeepHealthResponse(
            status=overall_status,
            timestamp=datetime.now(timezone.utc),
            version=frank.__version__,
            components=components
        )

    # ==================== Authentication Endpoints ====================

    @app.post(
        "/auth/login",
        response_model=LoginResponse,
        tags=["Authentication"],
        summary="Service account login"
    )
    async def login(request: LoginRequest):
        """
        Authenticate service account and receive JWT tokens.

        This endpoint proxies to Cognito (AWS or Stub) for authentication.

        Args:
            request: Login credentials (username/password)

        Returns:
            JWT access token and refresh token

        Raises:
            401: Invalid credentials
        """
        # TODO: Implement Cognito authentication proxy
        # For now, return a placeholder
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Authentication endpoint not yet implemented"
        )

    @app.post(
        "/auth/refresh",
        response_model=RefreshTokenResponse,
        tags=["Authentication"],
        summary="Refresh access token"
    )
    async def refresh_token(request: RefreshTokenRequest):
        """
        Refresh access token using refresh token.

        This endpoint proxies to Cognito for token refresh.

        Args:
            request: Refresh token

        Returns:
            New JWT access token

        Raises:
            401: Invalid or expired refresh token
        """
        # TODO: Implement Cognito token refresh proxy
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Token refresh endpoint not yet implemented"
        )

    # ==================== Submission Endpoints ====================

    @app.post(
        "/submit",
        response_model=SubmissionResponse,
        tags=["Submission"],
        summary="Submit threat intelligence",
        status_code=status.HTTP_201_CREATED
    )
    async def submit_sighting(
        request: SubmissionRequest,
        user: TokenPayload = Depends(get_current_user)
    ):
        """
        Submit a threat intelligence sighting.

        Requires authentication. Access tier determines submission privileges.

        Args:
            request: Submission data (observables, confidence, etc.)
            user: Authenticated user from JWT token

        Returns:
            Submission ID and confirmation

        Raises:
            401: Not authenticated
            403: Insufficient permissions
        """
        # TODO: Implement submission logic
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Submission endpoint not yet implemented"
        )

    @app.get(
        "/submissions/{submission_id}",
        response_model=Submission,
        tags=["Submission"],
        summary="Get submission by ID"
    )
    async def get_submission(
        submission_id: str,
        user: TokenPayload = Depends(get_current_user)
    ):
        """
        Retrieve a submission by ID with access filtering.

        Access tier determines what fields are visible.

        Args:
            submission_id: Submission STIX ID
            user: Authenticated user from JWT token

        Returns:
            Filtered submission data

        Raises:
            401: Not authenticated
            404: Submission not found
            403: Insufficient access tier
        """
        # TODO: Implement submission retrieval
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Submission retrieval not yet implemented"
        )

    # ==================== Query Endpoints ====================

    @app.get(
        "/observables",
        tags=["Query"],
        summary="Query observables"
    )
    async def query_observables(
        user: TokenPayload = Depends(get_current_user)
    ):
        """
        Query threat observables with access filtering.

        Args:
            user: Authenticated user from JWT token

        Returns:
            Filtered list of observables

        Raises:
            401: Not authenticated
        """
        # TODO: Implement observable query
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Observable query not yet implemented"
        )

    @app.get(
        "/statistics",
        tags=["Query"],
        summary="Platform statistics"
    )
    async def get_statistics(
        user: TokenPayload = Depends(get_current_user)
    ):
        """
        Get platform statistics.

        Access tier determines level of detail.

        Args:
            user: Authenticated user from JWT token

        Returns:
            Platform statistics

        Raises:
            401: Not authenticated
        """
        # TODO: Implement statistics
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Statistics endpoint not yet implemented"
        )

    return app
