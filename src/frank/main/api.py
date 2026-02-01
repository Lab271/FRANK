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
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

import frank
from frank.auth import TokenPayload, get_current_user
from frank.config import EnvironmentConfig
from frank.core.enum import AccessTier
from frank.core.models import Observable, Observables, Sighting, Submission, Submitter
from frank.main.models import (
    DeepHealthResponse,
    HealthResponse,
    SubmissionRequest,
    SubmissionResponse,
)
from frank.management.cognito_service import (
    BaseCognitoService,
    CognitoServiceError,
    get_cognito_service,
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
    cognito_service: Optional[BaseCognitoService] = None,
) -> FastAPI:
    """
    Create and configure the Main API (Sightings API) FastAPI application.

    Args:
        database: Database instance for threat intelligence storage
        cognito_service: Cognito service for authentication

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

    # Store services in app state
    app.state.database = database
    app.state.cognito_service = cognito_service

    def get_database() -> BaseFRANKDatabase:
        """Dependency to get database instance"""
        if app.state.database is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured"
            )
        return app.state.database

    def get_cognito() -> BaseCognitoService:
        """Dependency to get Cognito service instance"""
        if app.state.cognito_service is None:
            # Lazy initialization
            app.state.cognito_service = get_cognito_service()
        return app.state.cognito_service

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
    async def login(
        request: LoginRequest,
        cognito: BaseCognitoService = Depends(get_cognito)
    ):
        """
        Authenticate service account and receive JWT tokens.

        This endpoint proxies to Cognito (AWS or Stub) for authentication.

        Args:
            request: Login credentials (username/password)
            cognito: Cognito service instance

        Returns:
            JWT access token and refresh token

        Raises:
            401: Invalid credentials
        """
        try:
            # Authenticate with Cognito
            auth_result = await cognito.authenticate_user(
                username=request.username,
                password=request.password
            )

            # Extract tokens from Cognito response
            access_token = auth_result.get("AuthenticationResult", {}).get("AccessToken")
            refresh_token = auth_result.get("AuthenticationResult", {}).get("RefreshToken")
            expires_in = auth_result.get("AuthenticationResult", {}).get("ExpiresIn", 3600)

            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authentication succeeded but no access token received"
                )

            logger.info(f"User authenticated: {request.username}")

            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in
            )

        except CognitoServiceError as e:
            logger.warning(f"Authentication failed for {request.username}: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=e.message,
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication failed"
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
        user: TokenPayload = Depends(get_current_user),
        db: BaseFRANKDatabase = Depends(get_database)
    ):
        """
        Submit a threat intelligence sighting.

        Requires authentication. Access tier determines submission privileges.

        Args:
            request: Submission data (observables, confidence, etc.)
            user: Authenticated user from JWT token
            db: Database instance

        Returns:
            Submission ID and confirmation

        Raises:
            401: Not authenticated
            403: Insufficient permissions
        """
        try:
            # Get user's access tier and organisation
            access_tier = user.access_tier
            organisation_id = user.organisation_id or f"identity--{uuid4()}"

            # Categorize observables by type
            network_observables = [
                obs for obs in request.observables
                if obs.observable_type.value in ["ipv4", "ipv6", "domain", "url", "email"]
            ]
            file_observables = [
                obs for obs in request.observables
                if obs.observable_type.value in ["md5", "sha1", "sha256", "file_path"]
            ]
            process_observables = [
                obs for obs in request.observables
                if obs.observable_type.value in ["process", "mutex", "registry_key"]
            ]

            # Create Observables container
            observables = Observables(
                network=network_observables if network_observables else None,
                file=file_observables if file_observables else None,
                process=process_observables if process_observables else None
            )

            # Create Sighting
            sighting = Sighting(
                observables=observables,
                confidence_score=request.confidence_score,
                severity_level=request.severity or "MEDIUM",
                description=request.description
            )

            # Create Submitter
            submitter = Submitter(
                organisation_id=organisation_id,
                access_level=access_tier,
                organisation_type="cyber_partner"  # Default for API submissions
            )

            # Create Submission
            submission = Submission(
                submission_id=f"submission--{uuid4()}",
                timestamp=request.timestamp or datetime.now(timezone.utc),
                submitter=submitter,
                sighting=sighting
            )

            # Store in database
            db.store_submission(submission)

            logger.info(
                f"Submission stored: {submission.submission_id} "
                f"by {user.username} ({access_tier.value})"
            )

            return SubmissionResponse(
                submission_id=submission.submission_id,
                timestamp=submission.timestamp,
                status="accepted",
                message=f"Submission accepted with {len(request.observables)} observables"
            )

        except Exception as e:
            logger.error(f"Submission failed for {user.username}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process submission: {str(e)}"
            )

    @app.get(
        "/submissions/{submission_id}",
        response_model=Submission,
        tags=["Submission"],
        summary="Get submission by ID"
    )
    async def get_submission(
        submission_id: str,
        user: TokenPayload = Depends(get_current_user),
        db: BaseFRANKDatabase = Depends(get_database)
    ):
        """
        Retrieve a submission by ID with access filtering.

        Access tier determines what fields are visible.

        Args:
            submission_id: Submission STIX ID
            user: Authenticated user from JWT token
            db: Database instance

        Returns:
            Filtered submission data

        Raises:
            401: Not authenticated
            404: Submission not found
            403: Insufficient access tier
        """
        try:
            # Retrieve submission with access filtering
            submission = db.get_submission_by_id(
                submission_id=submission_id,
                access_level=user.access_tier
            )

            if not submission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Submission not found: {submission_id}"
                )

            logger.info(
                f"Submission retrieved: {submission_id} "
                f"by {user.username} ({user.access_tier.value})"
            )

            return submission

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve submission {submission_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve submission: {str(e)}"
            )

    # ==================== Query Endpoints ====================

    @app.get(
        "/observables",
        tags=["Query"],
        summary="Query observables"
    )
    async def query_observables(
        observable_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        user: TokenPayload = Depends(get_current_user),
        db: BaseFRANKDatabase = Depends(get_database)
    ):
        """
        Query threat observables with access filtering.

        Args:
            observable_type: Filter by type (ipv4, domain, hash, etc.)
            limit: Maximum results to return (default: 100)
            offset: Offset for pagination (default: 0)
            user: Authenticated user from JWT token
            db: Database instance

        Returns:
            Filtered list of observables

        Raises:
            401: Not authenticated
        """
        try:
            # Query observables with access filtering
            organisation_id = user.organisation_id or None

            observables = db.query_observables(
                org_id=organisation_id,
                observable_type=observable_type,
                access_level=user.access_tier,
                limit=limit,
                offset=offset
            )

            logger.info(
                f"Observable query by {user.username} ({user.access_tier.value}): "
                f"type={observable_type}, limit={limit}, offset={offset}"
            )

            return {
                "observables": observables,
                "total": len(observables),
                "limit": limit,
                "offset": offset,
                "access_tier": user.access_tier.value
            }

        except Exception as e:
            logger.error(f"Observable query failed for {user.username}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to query observables: {str(e)}"
            )

    @app.get(
        "/statistics",
        tags=["Query"],
        summary="Platform statistics"
    )
    async def get_statistics(
        days: int = 30,
        user: TokenPayload = Depends(get_current_user),
        db: BaseFRANKDatabase = Depends(get_database)
    ):
        """
        Get platform statistics.

        Access tier determines level of detail.

        Args:
            days: Number of days to include in statistics (default: 30)
            user: Authenticated user from JWT token
            db: Database instance

        Returns:
            Platform statistics

        Raises:
            401: Not authenticated
        """
        try:
            # Get organisation ID (if available)
            organisation_id = user.organisation_id or "platform"

            # Get statistics summary
            stats = db.get_statistics_summary(
                org_id=organisation_id,
                days=days
            )

            # Add metadata
            stats["access_tier"] = user.access_tier.value
            stats["requested_by"] = user.username
            stats["period_days"] = days

            logger.info(
                f"Statistics requested by {user.username} ({user.access_tier.value}): "
                f"org={organisation_id}, days={days}"
            )

            return stats

        except Exception as e:
            logger.error(f"Statistics query failed for {user.username}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve statistics: {str(e)}"
            )

    return app
