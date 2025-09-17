#!/usr/bin/env python3
"""
FRANK Platform - FastAPI Spike Solution

A working prototype API server implementing the FRANK threat intelligence platform
using FastAPI and the MySQL database backend.

This is inspired by spikes/005_server.py

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Query, Body, Request
from pydantic import BaseModel, field_validator, ConfigDict
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# Import enums from FRANK core
from frank.core.enum import ObservableType, TLPLevel, AccessTier
from frank.core.models import Submission

# Import our FRANK database
from frank.storage.dynamodb import create_dynamodb_database

# Utilities
from frank.util.sample_builder import SampleDataSeeder
from frank.util import create_server, create_error_response
from frank.util.requests import SubmissionRequest, SubmissionResponse, SightingSearchResponse, ObservationsResponse
from frank.util.http_exceptions import UnauthorizedException, BadRequestException, TooManyRequestsException, NotFoundException, UnauthenticatedException
from frank import __version__

# Configure logging
# logger = logging.getLogger(__name__)
logger = logging.getLogger("uvicorn.error")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# curl -H "Authorization: Bearer observer_test_token" "http://localhost:8000/v1/sighting?observable=185.220.102.45"
# curl -H "Authorization: Bearer contributor_test_token" "http://localhost:8000/v1/sighting?observable=185.220.102.45"
# curl -H "Authorization: Bearer partner_test_token" "http://localhost:8000/v1/sighting?observable=185.220.102.45"
# curl -H "Authorization: Bearer core_test_token" "http://localhost:8000/v1/sighting?observable=185.220.102.45"

#  jq '.sightings[0] | length'

# ================================
# CONFIGURATION MANAGEMENT
# ================================

# Security
security = HTTPBearer(auto_error=False)  # Don't auto-raise errors


class FrankConfig:
    """Environment-based configuration management"""

    def __init__(self, environment: str = None):
        self.environment = environment or os.getenv("FRANK_ENVIRONMENT", "localstack")
        self.setup_config()

    def setup_config(self):
        """Setup configuration based on environment"""
        self.table_name = os.getenv("DYNAMODB_TABLE", "frank_table")

        if self.environment in ["localstack", "aws"]:
            self.database_type = "dynamodb"
            self.localstack_endpoint = os.getenv("LOCALSTACK_ENDPOINT", "http://localstack:4566")

            # AWS Credentials (for LocalStack)
            self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "test")
            self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
            self.aws_region = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")
        else:
            raise ValueError(f"Unknown environment: {self.environment}")

# ================================
# FASTAPI APPLICATION
# ================================

# Initialize configuration and database
config = FrankConfig()
frank_dynamodb = create_dynamodb_database(
    table_name=config.table_name,
    region=config.aws_region,
    endpoint=config.localstack_endpoint,
    aws_access_key_id=config.aws_access_key,
    aws_secret_access_key=config.aws_secret_key,
)
frank_server = create_server(db=frank_dynamodb, logger=logger)

# Initialize system once server is setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup"""
    logger.info(f"Starting FRANK Platform Stage 2 - Environment: {config.environment}")
    # load_database with sample data
    frank_server.seed_database(SampleDataSeeder())
    logger.info(f"Database Initialization complete")
    yield


# Create FastAPI app
app = FastAPI(
    title="FRANK Platform - Stage 2",
    description="Dynamodb Implementation with LocalStack",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication and authorization functions
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Extract user information from JWT token.
    In a real implementation, this would validate the JWT and extract claims.
    For this spike, we'll mock the user data.
    """
    # Check if credentials were provided
    from frank.util.http_exceptions import UnauthenticatedException
    if credentials is None:
        raise UnauthenticatedException("Authentication required")

    # Mock user data for spike - in production, decode and validate JWT
    token = credentials.credentials

    # Simple mock based on token prefix for demonstration
    if token.startswith("observer_"):
        return {"organization_id": "demo-observer-org", "access_level": AccessTier.OBSERVER, "sector": "technology"}
    elif token.startswith("contributor_"):
        return {"organization_id": "demo-contributor-org", "access_level": AccessTier.CONTRIBUTOR, "sector": "financial"}
    elif token.startswith("partner_"):
        return {"organization_id": "demo-partner-org", "access_level": AccessTier.PARTNER, "sector": "cybersecurity_services"}
    elif token.startswith("core_"):
        return {"organization_id": "demo-core-org", "access_level": AccessTier.CORE_MEMBER, "sector": "government"}
    else:
        raise UnauthenticatedException("Invalid authentication token")



# Rate limiting (simplified for spike)
class RateLimiter:
    def __init__(self):
        self.requests = {}

    def check_rate_limit(self, user_id: str, access_level: str) -> bool:
        # Simplified rate limiting - in production use Redis or similar
        # For spike, we'll just return True
        return True


rate_limiter = RateLimiter()

# ================================
# API Endpoints
# ================================

@app.post("/v1/submission", response_model=SubmissionResponse)
async def submit_threat_intelligence(
    request: Request,
    submission_request: SubmissionRequest = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Submit threat intelligence sighting to the platform.
    Requires Contributor, Partner, or Core Member access level.
    """
    submission = submission_request.submission

    # Check permissions
    if not AccessTier.can_submit(current_user["access_level"]):
        raise UnauthorizedException("Insufficient access level for submission")

    # Check rate limiting
    if not rate_limiter.check_rate_limit(current_user["organization_id"], current_user["access_level"]):
        raise BadRequestException("Rate limit exceeded")

    # Store in database
    score_impact = frank_server.submit_threat_intelligence(current_user["organization_id"], submission)

    return SubmissionResponse(
        status="accepted",
        submission_id=submission.submission_id,
        contribution_score_impact=score_impact,
        processing_status="queued",
        validation_required=False,
        estimated_processing_time="2-5 minutes",
    )


@app.get('/v1/submission/{submission_id}', response_model=Submission, response_model_exclude_none=True)
async def get_submission(
    submission_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieve a specific submission by its ID.
    Only Submitters can access the submission.
    """
    # Check permissions
    if not AccessTier.can_submit(current_user["access_level"]):
        raise UnauthorizedException("Insufficient access level for submission retrieval")

    submission = frank_server.get_submission_by_id(current_user["organization_id"], current_user["access_level"], submission_id)
    if not submission:
        raise NotFoundException(f"Submission {submission_id} not found")

    return submission


class SightingSearchQuery(BaseModel):
    """Model for sighting search query parameters"""

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
        populate_by_name=True,  # Allow both field name and alias
    )


    observable: Optional[str] = Query(None, description="Specific IoC to search for")
    observable_type: Optional[ObservableType] = Query(None, alias="type", description="Observable type filter")
    start_date: Optional[datetime] = Query(None, description="Search start date")
    end_date: Optional[datetime] = Query(None, description="Search end date")
    sector: Optional[str] = Query(None, description="Target sector filter")
    confidence_min: Optional[int] = Query(None, ge=0, le=100, description="Minimum confidence score")
    tlp_level: Optional[TLPLevel] = Query(None, description="Traffic Light Protocol level")
    campaign: Optional[str] = Query(None, description="Threat campaign identifier")
    limit: Optional[int] = Query(50, ge=1, le=1000, description="Maximum results to return")
    offset: Optional[int] = Query(0, ge=0, description="Pagination offset")
    format: Optional[str] = Query("summary", description="Response format")

    @field_validator("end_date")
    def validate_date_range(cls, end_date, info):
        start_date = info.data.get("start_date")
        if start_date and end_date and start_date >= end_date:
            raise BadRequestException(
                "Invalid date range: start_date must be before end_date"
            )
        return end_date

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dict excluding None values"""
        query_params = self.model_dump()
        # Add sector as list if present
        if query_params.get("sector"):
            query_params["sectors"] = [query_params.pop("sector")]

        # Calculate days_back if start_date is present
        if query_params.get("start_date"):
            days_back = (datetime.now(timezone.utc) - query_params["start_date"]).days
            query_params["days_back"] = max(1, days_back)

        return query_params


@app.get("/v1/sighting", response_model=SightingSearchResponse)
async def search_threat_sightings(
    current_user: Dict[str, Any] = Depends(get_current_user),
    query: SightingSearchQuery = Depends()
):
    """
    Retrieve threat intelligence sightings based on search criteria.
    Available to Observer, Contributor, Partner, and Core Member tiers.
    """
    # Check rate limiting
    if not rate_limiter.check_rate_limit(current_user["organization_id"], current_user["access_level"]):
        raise TooManyRequestsException("Rate limit exceeded")

    # Build query parameters from model_dict
    query_params = query.to_dict()
    # Remove keys not needed for frank_server.query_threats
    observable = query_params.pop("observable", None)
    offset = query_params.pop("offset", 0)
    limit = query_params.pop("limit", 50)


    total_results, sightings, aggregations, threat_context = frank_server.query_threats(
        user_id=current_user["organization_id"], access_level=current_user["access_level"],
        offset=offset, limit=limit,
        observable=observable, **query_params
    )

    response = SightingSearchResponse(
        total_results=total_results,
        returned_results=len(sightings),
        sightings=sightings,
        aggregations=aggregations,
        threat_context=threat_context,
        pagination=None
    )

    # Add pagination info
    if total_results > offset + limit:
        response.pagination = {
            "has_next": True,
            "next_offset": offset + limit,
            "has_previous": offset > 0,
            "previous_offset": max(0, offset - limit),
        }

    return response


@app.get("/v1/observations", response_model=ObservationsResponse)
def get_observations(
    org_id: str = Query(..., description="Organization ID"),
    days: int = Query(30, description="Number of days to include in stats"),
    observable_type: str = Query(None, description="Filter by observable type"),
    limit: int = Query(100, description="Max number of results")
):
    """
    Get observable statistics and details for the platform.
    """
    observations, stats = frank_server.get_observations(
            org_id=org_id,
            days=days,
            observable_type=observable_type,
            limit=limit
    )

    return ObservationsResponse(
        total_results=len(observations),
        returned_results=len(observations),
        observations=observations,
        stats=stats,
        observable_types=list(stats.get('observable_totals', {}).keys()),
        pagination=None
    )

# Health and status endpoints
@app.get("/v1/health")
async def health_check():
    """Health check endpoint"""
    return frank_server.health_check()


@app.get("/v1/statistics")
async def get_platform_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
):
    """Get platform usage statistics"""
    if not current_user["access_level"].check_access_level(AccessTier.OBSERVER):
        raise UnauthorizedException("Insufficient access level")

    stats = frank_server.get_platform_statistics(
        user_id=current_user["organization_id"],
        access_level=current_user["access_level"],
        days=days,
    )  
    return stats

# ===============================
# Error handlers
# ===============================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
	"""Custom HTTP exception handler"""
	return JSONResponse(
		status_code=exc.status_code,
		content=create_error_response(
			exc.status_code,
			"HTTP_ERROR",
			exc.detail
		),
	)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=create_error_response(
            422,
            "VALIDATION_ERROR",
            "Request validation failed",
            details={"validation_errors": exc.errors()}
        )
    )

@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
    """Dedicated exception handler for generic exceptions."""
    return JSONResponse(
        status_code=500,
        content=create_error_response(
            500,
            "INTERNAL_ERROR",
            str(exc)
        ),
    )

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FRANK Platform Stage 2 Server")
    parser.add_argument(
        "--environment", choices=["localstack", "aws"], default="localstack", help="Environment to run in"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    # Set environment
    os.environ["FRANK_ENVIRONMENT"] = args.environment

    logger.info("Starting FRANK Platform Stage 2")
    logger.info(f"Environment: {args.environment}")
    logger.info(f"Database type: {config.database_type}")

    # Run the server
    uvicorn.run("frank_stage2:app", host=args.host, port=args.port, reload=args.reload, log_level="info")
