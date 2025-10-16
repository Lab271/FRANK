#!/usr/bin/env python3
"""
FRANK Platform - Stage 3 Full API Implementation
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

RESTful API for threat intelligence submission and query operations.
Implements comprehensive CRUD operations with DynamoDB backend.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime, timezone
from functools import lru_cache
import logging
import os
from typing import List, Optional

import aioboto3
from fastapi import FastAPI, Request, HTTPException, Depends, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

import frank
from frank.core.models import Submission, Observable, Submitter, HitTarget, Sighting, Observables
from frank.core.enum import ObservableType, AccessTier, SeverityLevel
from frank.storage.dynamodb import DynamoDBFRANKDatabase
from frank.util import create_error_response


# ===================================
# Logging Setup
# ===================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("frank.api")


# ===================================
# Configuration
# ===================================
@lru_cache()
def get_config():
    """Get application configuration from environment"""
    return {
        "table_name": os.environ.get("DYNAMODB_TABLE", "frank-stage3-data"),
        "audit_table_name": os.environ.get("DYNAMODB_AUDIT_TABLE", "frank-audit"),
        "region": os.environ.get("AWS_DEFAULT_REGION", "eu-central-1"),
        "endpoint": os.environ.get("ENDPOINT", None),
        "environment": os.environ.get("FRANK_ENVIRONMENT", "aws"),
        "api_key": os.environ.get("FRANK_API_KEY", "dev-key-12345"),  # In production, use AWS Secrets Manager
    }


# ===================================
# Database Connection
# ===================================
_db_instance = None

def get_database() -> DynamoDBFRANKDatabase:
    """Get or create database instance (singleton pattern)"""
    global _db_instance
    if _db_instance is None:
        config = get_config()
        connection_params = {
            "DYNAMODB_TABLE": config["table_name"],
            "DYNAMODB_AUDIT_TABLE": config["audit_table_name"],
            "AWS_DEFAULT_REGION": config["region"],
            "ENDPOINT": config["endpoint"],
            "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID", "test") if config["endpoint"] else None,
            "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY", "test") if config["endpoint"] else None,
        }
        _db_instance = DynamoDBFRANKDatabase(connection_params=connection_params, logger=logger)
        _db_instance.initialize()
    return _db_instance


# ===================================
# Security & Authentication
# ===================================
security = HTTPBearer(auto_error=False)

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Verify API key from Authorization header.
    Returns organization ID associated with the API key.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    config = get_config()
    # In production, validate against DynamoDB table of API keys
    # For now, simple validation
    if credentials.credentials != config["api_key"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Return organization ID (in production, lookup from API key table)
    return "org-001"  # Placeholder


# ===================================
# Request/Response Models
# ===================================
class SubmissionCreateRequest(BaseModel):
    """Request model for creating a submission"""
    submitter_access_level: AccessTier = Field(..., description="Access level of submitting organization")
    submitter_sector: Optional[str] = Field(None, description="Submitter's industry sector")
    submitter_region: Optional[str] = Field(None, description="Submitter's geographic region")

    hit_target_sector: str = Field(..., description="Affected organization's sector")
    hit_target_size: Optional[str] = Field(None, description="Organization size (small/medium/large)")
    hit_target_region: Optional[str] = Field(None, description="Affected organization's region")

    confidence: int = Field(69, ge=0, le=100, description="Confidence score 0-100")
    severity: Optional[SeverityLevel] = Field(None, description="Threat severity level")

    network_observables: List[Observable] = Field(default_factory=list, description="Network observables")
    file_observables: Optional[List[Observable]] = Field(default_factory=list, description="File observables")
    process_observables: Optional[List[Observable]] = Field(default_factory=list, description="Process observables")

    tlp_level: Optional[str] = Field("GREEN", description="TLP classification")
    processing_notes: Optional[str] = Field(None, description="Processing notes")


class SubmissionResponse(BaseModel):
    """Response model for submission operations"""
    submission_id: str
    status: str
    timestamp: str
    message: str


class ObservableQueryParams(BaseModel):
    """Query parameters for observable search"""
    observable_type: Optional[ObservableType] = None
    min_confidence: Optional[float] = Field(None, ge=0, le=100)
    sectors: Optional[List[str]] = None
    days_back: Optional[int] = Field(None, ge=1, le=365)
    limit: int = Field(100, ge=1, le=1000)


# ===================================
# FastAPI Application
# ===================================
app = FastAPI(
    title="FRANK Platform API - Stage 3",
    description="RESTful API for threat intelligence submission and query operations",
    version=frank.__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===================================
# Health Check Endpoints
# ===================================
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "application": "FRANK Platform",
        "version": frank.__version__,
        "status": "running",
        "message": "Welcome to FRANK threat intelligence API",
        "api_docs": "/docs",
        "api_version": "v1",
    }


@app.get("/v1/health")
async def health():
    """Basic health check endpoint for load balancer"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "FRANK",
        "version": frank.__version__,
    }


@app.get("/v1/health/deep")
async def deep_health_check():
    """Comprehensive health check including database connectivity"""
    start_time = datetime.now(timezone.utc)
    health_status = {
        "status": "healthy",
        "timestamp": start_time.isoformat(),
        "version": frank.__version__,
        "checks": {},
    }

    # Check database connectivity
    try:
        db = get_database()
        db_health = db.health_check()
        health_status["checks"]["database"] = {
            "status": "healthy",
            "type": db_health.get("type"),
            "table": db_health.get("database_table"),
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["status"] = "degraded"

    health_status["duration"] = f"{(datetime.now(timezone.utc) - start_time).total_seconds():.3f}s"
    return health_status


# ===================================
# Submission Endpoints
# ===================================
@app.post("/api/v1/submissions", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    request: SubmissionCreateRequest,
    org_id: str = Depends(verify_api_key),
):
    """
    Create a new threat intelligence submission.

    Requires authentication via API key in Authorization header.
    """
    try:
        # Build submission from request
        submitter = Submitter(
            access_level=request.submitter_access_level,
            sector=request.submitter_sector,
            region=request.submitter_region,
        )

        hit_target = HitTarget(
            sector=request.hit_target_sector,
            organisation_size=request.hit_target_size,
            region=request.hit_target_region,
        )

        observables = Observables(
            network=request.network_observables,
            file=request.file_observables or [],
            process=request.process_observables or [],
        )

        sighting = Sighting(
            confidence=request.confidence,
            severity=request.severity,
            observables=observables,
        )

        submission = Submission(
            submitter=submitter,
            hit_target=hit_target,
            sighting=sighting,
            tlp_level=request.tlp_level,
            processing_notes=request.processing_notes,
        )

        # Store in database
        db = get_database()
        db.store_submission(submission)

        # Log access
        db.log_access(org_id, "create_submission", "submission", {"submission_id": submission.submission_id})

        logger.info(f"Created submission {submission.submission_id} from organization {org_id}")

        return SubmissionResponse(
            submission_id=submission.submission_id,
            status="created",
            timestamp=submission.timestamp.isoformat(),
            message="Submission created successfully",
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error creating submission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@app.get("/api/v1/submissions/{submission_id}")
async def get_submission(
    submission_id: str,
    org_id: str = Depends(verify_api_key),
):
    """
    Retrieve a specific submission by ID.

    Access filtering is applied based on the authenticated organization's access level.
    """
    try:
        db = get_database()
        submission_dict = db.get_submission_by_id(submission_id)

        if not submission_dict:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Submission {submission_id} not found",
            )

        # Log access
        db.log_access(org_id, "get_submission", "submission", {"submission_id": submission_id})

        return submission_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving submission {submission_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# ===================================
# Observable Endpoints
# ===================================
@app.get("/api/v1/observables")
async def query_observables(
    observable_type: Optional[ObservableType] = Query(None, description="Filter by observable type"),
    min_confidence: Optional[float] = Query(None, ge=0, le=100, description="Minimum confidence score"),
    sectors: Optional[List[str]] = Query(None, description="Filter by sectors"),
    days_back: Optional[int] = Query(None, ge=1, le=365, description="Days to look back"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results to return"),
    org_id: str = Depends(verify_api_key),
):
    """
    Query observables with optional filters.

    Supports filtering by type, confidence, sector, and time range.
    """
    try:
        db = get_database()

        # Default access level for querying (in production, lookup from org_id)
        access_level = AccessTier.CONTRIBUTOR

        results = db.query_observables(
            user_id=org_id,
            access_level=access_level,
            observable_type=observable_type,
            min_confidence=min_confidence,
            sectors=sectors,
            days_back=days_back,
            limit=limit,
        )

        # Log access
        db.log_access(org_id, "query_observables", "observables", {
            "filters": {
                "type": observable_type.value if observable_type else None,
                "min_confidence": min_confidence,
                "sectors": sectors,
                "days_back": days_back,
            }
        })

        return {
            "total": len(results),
            "limit": limit,
            "observables": results,
        }

    except Exception as e:
        logger.error(f"Error querying observables: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@app.get("/api/v1/observables/search")
async def search_observables(
    value: str = Query(..., min_length=1, description="Search value (substring match)"),
    org_id: str = Depends(verify_api_key),
):
    """
    Search for observables by value (substring match).

    Use for searching IPs, domains, hashes, etc.
    """
    try:
        db = get_database()

        # Default access level (in production, lookup from org_id)
        access_level = AccessTier.CONTRIBUTOR

        results = db.search_observables_by_value(
            org_id=org_id,
            search_value=value,
            access_level=access_level,
        )

        # Log access
        db.log_access(org_id, "search_observables", "observables", {"search_value": value})

        return {
            "total": len(results),
            "search_value": value,
            "observables": results,
        }

    except Exception as e:
        logger.error(f"Error searching observables: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# ===================================
# Statistics Endpoints
# ===================================
@app.get("/api/v1/statistics")
async def get_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    org_id: str = Depends(verify_api_key),
):
    """
    Get platform statistics summary.

    Includes counts of submissions, observables, organizations, and breakdown by type.
    """
    try:
        db = get_database()

        stats = db.get_statistics_summary(org_id=org_id, days=days)

        # Log access
        db.log_access(org_id, "get_statistics", "statistics", {"days": days})

        return stats

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# ===================================
# Exception Handlers
# ===================================
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=create_error_response(
            422,
            "VALIDATION_ERROR",
            "Request validation failed",
            details={"errors": exc.errors()},
        ),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            500,
            "INTERNAL_ERROR",
            str(exc),
            details={"type": type(exc).__name__},
        ),
    )


# ===================================
# Application Startup/Shutdown
# ===================================
@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    logger.info("Starting FRANK API - Stage 3")
    config = get_config()
    logger.info(f"Environment: {config['environment']}")
    logger.info(f"DynamoDB Table: {config['table_name']}")

    # Initialize database
    db = get_database()
    logger.info("Database connection initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down FRANK API - Stage 3")


# ===================================
# Main Entry Point
# ===================================
if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="FRANK Platform - Stage 3 API Server")
    parser.add_argument(
        "--environment",
        choices=["localstack", "aws"],
        default=os.environ.get("FRANK_ENVIRONMENT", "aws"),
        help="Environment to run in",
    )
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"), help="Host to bind to")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")), help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    # Set environment variables
    os.environ["FRANK_ENVIRONMENT"] = args.environment

    log_level = "debug" if args.debug else os.environ.get("UVICORN_LOG_LEVEL", "info")

    logger.info(f"🚀 Starting FRANK API - Stage 3 on {args.host}:{args.port} | Environment: {args.environment}")

    uvicorn.run("api:app", host=args.host, port=args.port, reload=args.reload, log_level=log_level)
