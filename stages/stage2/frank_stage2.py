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
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# Import enums from FRANK core
from frank.core.enum import ObservableType, TLPLevel, AccessTier

# Import our FRANK database
from frank.storage.dynamodb import create_dynamodb_database

# Utilities
from frank.util.sample_builder import SampleDataSeeder
from frank.util import create_client
from frank.util.requests import SubmissionRequest, SubmissionResponse, SightingSearchResponse, ObservationsResponse
from frank import __version__

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

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

        if self.environment == "local":
            self.setup_local_config()
        elif self.environment in ["mysql"]:
            # Direct MySQL connection
            self.database_type = "mysql"
            self.rds_host = os.getenv("RDS_HOST", "localhost")
            self.rds_port = int(os.getenv("RDS_PORT", "3306"))
            self.rds_database = os.getenv("RDS_DATABASE", "frank")
            self.rds_username = os.getenv("RDS_USERNAME", "frank_user")
            self.rds_password = os.getenv("RDS_PASSWORD", "frank_pass")
        elif self.environment == "hybrid":
            self.setup_localstack_hybrid_config()
        elif self.environment == "localstack":
            self.setup_localstack_config()
        elif self.environment == "aws":
            self.setup_aws_config()
        else:
            raise ValueError(f"Unknown environment: {self.environment}")

    def setup_local_config(self):
        """Local SQLite configuration (fallback)"""
        self.database_type = "sqlite"
        self.db_path = os.getenv("SQLITE_PATH", "/tmp/frank_local.db")

    def setup_localstack_hybrid_config(self):
        """Hybrid LocalStack with external MySQL configuration"""
        self.database_type = "mysql"
        self.localstack_endpoint = os.getenv("LOCALSTACK_ENDPOINT", "http://localstack:4566")

        # MySQL Configuration (external)
        self.rds_host = os.getenv("RDS_HOST", "mysql")
        self.rds_port = int(os.getenv("RDS_PORT", "3306"))
        self.rds_database = os.getenv("RDS_DATABASE", "frank")
        self.rds_username = os.getenv("RDS_USERNAME", "frank_user")
        self.rds_password = os.getenv("RDS_PASSWORD", "frank_pass")

        # AWS Credentials (for LocalStack)
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "test")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
        self.aws_region = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")

    def setup_localstack_config(self):
        """LocalStack RDS configuration"""
        self.database_type = "rds"
        self.localstack_endpoint = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")

        # RDS Configuration (via LocalStack)
        self.rds_host = os.getenv("RDS_HOST", "localhost")
        self.rds_port = int(os.getenv("RDS_PORT", "4566"))
        self.rds_database = os.getenv("RDS_DATABASE", "frank")
        self.rds_username = os.getenv("RDS_USERNAME", "frank_user")
        self.rds_password = os.getenv("RDS_PASSWORD", "frank_pass")

        # AWS Credentials (for LocalStack)
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "test")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
        self.aws_region = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")

    def setup_aws_config(self):
        """Real AWS RDS configuration"""
        self.database_type = "rds"
        self.rds_host = os.getenv("RDS_HOST")
        self.rds_port = int(os.getenv("RDS_PORT", "3306"))
        self.rds_database = os.getenv("RDS_DATABASE", "frank")
        self.rds_username = os.getenv("RDS_USERNAME")
        self.rds_password = os.getenv("RDS_PASSWORD")
        self.aws_region = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")


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
frank_client = create_client(db=frank_dynamodb, logger=logger)

# Initialize system once server is setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup"""
    logger.info(f"Starting FRANK Platform Stage 2 - Environment: {config.environment}")
    # load_database with sample data
    frank_client.seed_database(SampleDataSeeder())
    logger.info(f"Database Initialization complete")
    yield


# Create FastAPI app
app = FastAPI(
    title="FRANK Platform - Stage 2",
    description="RDS/MariaDB Implementation with LocalStack",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.logger = logger  # Attach our external logger

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
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Mock user data for spike - in production, decode and validate JWT
    token = credentials.credentials

    # Simple mock based on token prefix for demonstration
    if token.startswith("observer_"):
        return {"organization_id": "demo-observer-org", "tier": AccessTier.OBSERVER, "sector": "technology"}
    elif token.startswith("contributor_"):
        return {"organization_id": "demo-contributor-org", "tier": AccessTier.CONTRIBUTOR, "sector": "financial"}
    elif token.startswith("partner_"):
        return {"organization_id": "demo-partner-org", "tier": AccessTier.PARTNER, "sector": "cybersecurity_services"}
    elif token.startswith("core_"):
        return {"organization_id": "demo-core-org", "tier": AccessTier.CORE_MEMBER, "sector": "government"}
    else:
        raise HTTPException(status_code=401, detail="Invalid authentication token")



# Rate limiting (simplified for spike)
class RateLimiter:
    def __init__(self):
        self.requests = {}

    def check_rate_limit(self, user_id: str, tier: str) -> bool:
        # Simplified rate limiting - in production use Redis or similar
        # For spike, we'll just return True
        return True


rate_limiter = RateLimiter()

# API Endpoints


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
    if not AccessTier.can_submit(current_user["tier"]):
        raise HTTPException(status_code=403, detail="Insufficient access level for submission")

    # Check rate limiting
    if not rate_limiter.check_rate_limit(current_user["organization_id"], current_user["tier"]):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    try:
        # Store in database
<<<<<<< HEAD
        success, score_impact = frank_client.submit_threat_intelligence(current_user["organization_id"], submission)

        # TODO: simplify error handling in client, propagate Exceptions, not status flags
=======
        success, score_impact = frank_client.submit_threat_intelligence(current_user["organization_id"], ubmission)

        # TODO: simplify error handling in client, propage Exceptions, not status flags
>>>>>>> ad17d2e ( some cleanup)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store submission")

        return SubmissionResponse(
            status="accepted",
            submission_id=submission.submission_id,
            contribution_score_impact=score_impact,
            processing_status="queued",
            validation_required=False,
            estimated_processing_time="2-5 minutes",
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Submission validation failed: {str(e)}")


@app.get("/v1/sighting", response_model=SightingSearchResponse)
async def search_threat_sightings(
    current_user: Dict[str, Any] = Depends(get_current_user),
    observable: Optional[str] = Query(None, description="Specific IoC to search for"),
    type: Optional[ObservableType] = Query(None, description="Observable type filter"),
    start_date: Optional[datetime] = Query(None, description="Search start date"),
    end_date: Optional[datetime] = Query(None, description="Search end date"),
    sector: Optional[str] = Query(None, description="Target sector filter"),
    confidence_min: Optional[int] = Query(None, ge=0, le=100, description="Minimum confidence score"),
    tlp_level: Optional[TLPLevel] = Query(None, description="Traffic Light Protocol level"),
    campaign: Optional[str] = Query(None, description="Threat campaign identifier"),
    limit: Optional[int] = Query(50, ge=1, le=1000, description="Maximum results to return"),
    offset: Optional[int] = Query(0, ge=0, description="Pagination offset"),
    format: Optional[str] = Query("summary", description="Response format"),
):
    """
    Retrieve threat intelligence sightings based on search criteria.
    Available to Observer, Contributor, Partner, and Core Member tiers.
    """

    # Check rate limiting
    if not rate_limiter.check_rate_limit(current_user["organization_id"], current_user["tier"]):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    try:
        # Validate date range
        if start_date and end_date and start_date >= end_date:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_QUERY_PARAMETERS",
                        "message": "Invalid date range: start_date must be before end_date",
                        "details": {
                            "start_date": start_date.isoformat() if start_date else None,
                            "end_date": end_date.isoformat() if end_date else None,
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "request_id": f"req-{uuid.uuid4()}",
                    }
                },
            )

        # Build query parameters
        query_params = {"org_id": current_user["organization_id"], "access_level": current_user["tier"], "limit": limit}

        # Add filters if provided
        if type:
            query_params["observable_type"] = type.value
        if confidence_min:
            query_params["min_confidence"] = confidence_min
        if sector:
            query_params["sectors"] = [sector]
        if start_date or end_date:
            # Calculate days back from start_date if provided
            if start_date:
                days_back = (datetime.now(timezone.utc) - start_date).days
                query_params["days_back"] = max(1, days_back)


        total_results, sightings, aggregations, threat_context = frank_client.query_threats(
            org_id=current_user["organization_id"], tier=current_user["tier"], 
            format=format, offset=offset, limit=limit,
            observable=observable, **query_params
        )

        response = SightingSearchResponse(
            total_results=total_results, returned_results=len(sightings), sightings=sightings, aggregations=aggregations, threat_context=threat_context, pagination=None
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


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
    observations, stats = frank_client.get_observations(
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
    return frank_client.health_check()


@app.get("/v1/statistics")
async def get_platform_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
):
    """Get platform usage statistics"""
    if not current_user["tier"].check_access_level(AccessTier.OBSERVER):
        raise HTTPException(status_code=403, detail="Insufficient access level")

    stats = frank_client.get_platform_statistics(
        org_id=current_user["organization_id"],
        days=days,
        tier=current_user["tier"]
    )  
    return stats

# ===============================
# Helper functions
# ===============================


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": f"req-{uuid.uuid4()}",
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": f"req-{uuid.uuid4()}",
            }
        },
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FRANK Platform Stage 2 Server")
    parser.add_argument(
        "--environment", choices=["hybrid", "localstack", "aws"], default="hybrid", help="Environment to run in"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    # Set environment
    os.environ["FRANK_ENVIRONMENT"] = args.environment

    logger.info(f"Starting FRANK Platform Stage 2")
    logger.info(f"Environment: {args.environment}")
    logger.info(f"Database type: {config.database_type}")

    # Run the server
    uvicorn.run("frank_stage2:app", host=args.host, port=args.port, reload=args.reload, log_level="info")
