#!/usr/bin/env python3
"""
FRANK Platform - FastAPI Testability Spike - Simple API Implementation
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module implements a function-based FastAPI application with four endpoint types
for validating testability patterns across the FRANK platform:

1. Public endpoint (no authentication required)
2. Protected endpoint (Bearer token authentication using FastAPI security)
3. Exception endpoint (controlled 500 error with proper exception handling)
4. Custom error endpoint (custom HTTPException extension demonstration)

The implementation demonstrates:
- Function-based FastAPI app creation for better testability and modularity
- Dependency injection for configuration management
- Bearer token authentication patterns using FastAPI Depends() dependency injection
- Comprehensive exception handling with both standard and custom HTTP exceptions
- Request/response logging middleware for development and debugging
- Uvicorn integration with argparse for flexible development server configuration
- Global exception handlers that convert Python exceptions to proper HTTP responses

This spike validates the testability foundations for all FRANK API development
and establishes reusable patterns for authentication, error handling, and testing.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import argparse
from functools import lru_cache
import os
from pathlib import Path
import time
from typing import Dict, Any


from fastapi import FastAPI, Body, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import frank
from frank.core import gen_stix_id
from frank.core.enum import AccessTier, TLPLevel
from frank.core.models import Submission
from frank.storage import create_dynamodb_database
from frank.util import create_server
from frank.util.requests import SubmissionRequest, ObservationsSearchQuery
from frank.util.requests import SubmissionResponse, SightingSearchResponse
from frank.util.stix import sighting_to_stix_bundle
from frank.util.http_exceptions import UnauthorizedException, NotFoundException
from frank.util.auth import CognitoValidator
from frank.util.logger import setup_logging, get_module_logger, configure_frank_logging

# ===================================
# Configuration
# ===================================
@lru_cache()
def get_config():
    """Get application configuration from environment"""
    endpoint = os.environ.get("ENDPOINT", None)
    # Convert empty string to None for AWS
    if endpoint == "":
        endpoint = None

    environment = os.environ.get("FRANK_ENVIRONMENT", "aws")  # "aws" or "localstack"
    profile = os.environ.get("AWS_PROFILE", None) 
    region = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", None)
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", None)
    table_name = os.environ.get("DYNAMODB_TABLE", "frank-data")
    audit_table_name = os.environ.get("DYNAMODB_AUDIT_TABLE", "frank-audit-table")
    cognito_url = os.environ.get("COGNITO_URL", "http://localhost:8100/")

    if environment == "aws":
        cognito_url = f"https://cognito-idp.{region}.amazonaws.com/"
    elif not cognito_url.endswith("/"):
        cognito_url += "/"

    return {
        "endpoint": endpoint,  # None for AWS, set for LocalStack
        "environment": environment,  
        "profile": profile,
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
        "region": region,
        "table_name": table_name,
        "audit_table_name": audit_table_name,
        "validation_strategy": os.environ.get("VALIDATION_STRATEGY", "local_only"),
        "cognito_url": cognito_url,
        "user_pool_id": os.environ.get("USER_POOL_ID", "eu-west-1_MOCKPOOL"),
        "jwt_algorithm": os.environ.get("JWT_ALGORITHM", "RS256"),
        "jwt_secret": os.environ.get("JWT_SECRET", "mock-cognito-secret-key")
    }
  
@lru_cache()
def get_server():
    """Return server"""
    config = get_config()
    logger = get_module_logger("frank.server")
    db = create_dynamodb_database(config=config, logger=logger)
    server = create_server(db=db, config=config, logger=logger)
    return server


# ====================================
# Fastapi Application Factory
# ====================================

def create_app() -> FastAPI:
    """
    Create and configure FastAPI application
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """

    validator = CognitoValidator(config=get_config())

    app = FastAPI(
        title="FRANK FastAPI Testability Spike",
        description="Spike for validating FastAPI testability patterns",
        version=frank.__version__,
        docs_url="/docs",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Don't setup logging at module level - let main() handle it
    logger = get_module_logger("frank.app")

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
               
        response = await call_next(request)
        
        process_time = time.time() - start_time
        logger.info(
            f"Time: {process_time:.4f}s"
        )
        
        return response
    
    # 1. Public endpoint - no authentication required
    @app.get("/")
    def public_endpoint() -> Dict[str, Any]:
        """
        Public endpoint accessible without authentication
        
        Returns:
            Dict containing success message and endpoint info
        """
        logger.info("Public endpoint accessed")
        return {
            "message": "FRANK Root Public Endpoint",
            "version": frank.__version__,
            "timestamp": time.time()
        }
    
    # 2. Protected endpoint - Bearer token authentication required
    @app.get("/protected")
    async def protected_endpoint(user: Dict[str, Any] = Depends(validator.get_current_user)) -> Dict[str, Any]:
        """
        Protected endpoint requiring Bearer token authentication
        
        Args:
            user: Validated user from get_current_user dependency
            
        Returns:
            Dict containing success message and user info
        """
        required_tier = AccessTier.CORE_MEMBER
        
        if not user["access_level"].check_access_level(required_tier):
            raise UnauthorizedException(
                detail=f"Insufficient access level. Required: {required_tier.value}, User has: {user['access_level'].value}"
            )
        logger.info("Protected endpoint accessed with valid token")
        return {
            "message": "Protected endpoint accessed successfully",
            "endpoint": "protected",
            "authenticated": True,
            "user": user,
            "timestamp": time.time()
        }

    @app.get('/v1/submission/{submission_id}', response_model=Submission, response_model_exclude_none=True)
    async def get_submission(
        submission_id: str,
        user: Dict[str, Any] = Depends(validator.get_current_user),
    ):
        """
        Retrieve a specific submission by its ID.
        Only Submitters can access the submission.
        """
        # Check permissions
        required_tier = AccessTier.CORE_MEMBER
        
        if not user["access_level"].check_access_level(required_tier):
            raise UnauthorizedException(
                detail=f"Insufficient access level. Required: {required_tier.value}, User has: {user['access_level'].value}"
            )

        submission = get_server().get_submission_by_id(user, submission_id)

        if not submission:
            raise NotFoundException(f"Submission {submission_id} not found")

        return submission


    @app.get("/v1/sightings", response_model=SightingSearchResponse, response_model_exclude_none=True)
    async def get_sightings(
        request: Request,
        user: Dict[str, Any] = Depends(validator.get_current_user),
        query: ObservationsSearchQuery = Depends()
    ):
        """
        Get observable statistics and details for the platform.
        """
        # Check permissions
        required_tier = AccessTier.CORE_MEMBER
        if not user["access_level"].check_access_level(required_tier):
            raise UnauthorizedException(
                detail=f"Insufficient access level. Required: {required_tier.value}, User has: {user['access_level'].value}"
            )

        # Build query parameters from model_dict
        query_params = query.to_dict()
        sightings = get_server().get_sightings_from_observations(
            user=user, **query_params
        )

        # If STIX requested, return a single bundle with translated sightings
        accept = request.headers.get("accept", "")
        if "application/stix+json" in accept:
            bundles = [sighting_to_stix_bundle(s) for s in sightings]
            # transpose a list of bundles into a single bundle
            combined_bundle = {
                "type": "bundle",
                "id": gen_stix_id("bundle"),
                "objects": [obj for bundle in bundles for obj in bundle["objects"]]
            }
            return JSONResponse(content=combined_bundle, media_type="application/stix+json")

        return SightingSearchResponse(
            total_results=len(sightings),
            sightings=sightings
        )


    # 3. Post Submission endpoint - submit threat intelligence
    @app.post("/v1/submission", response_model=SubmissionResponse)
    async def post_threat_submission(
        request: Request,
        submission_request: SubmissionRequest = Body(...),
        user: Dict[str, Any] = Depends(validator.get_current_user),
    ):
        """
        Submit threat intelligence sighting to the platform.
        Requires Contributor, Partner, or Core Member access level.
        """
        submission = submission_request.submission

        # Check permissions
        if not AccessTier.can_submit(user["access_level"]):
            raise UnauthorizedException(f"Insufficient access level {user['access_level']} for submission")

        if submission.tlp_level == TLPLevel.RED:
            raise UnauthorizedException("TLP RED submissions are not (yet) allowed via this endpoint")

        # Submit submission
        get_server().submit_threat_intelligence(user, submission)

        return SubmissionResponse(
            status="accepted",
            timestamp=submission.timestamp,
            submission_id=submission.submission_id,
            submitter_id=submission.submitter.organisation_id if submission.submitter else None,
            request_id=user["request_id"],
            tlp_level=submission.tlp_level,
            submission_level=submission.calc_submission_level(),
            processing_status="processed",
            estimated_processing_time="0 minutes",
        )
   
    # 4. Custom error endpoint - raises custom HTTPException extension
    @app.get("/v1/deep-health")
    def database_health() -> Dict[str, Any]:
        """
        Database connection endpoint

        Returns:
            Dict containing deep health check information
        """
        return get_server().deep_health_check()

    # Health check endpoint for monitoring
    @app.get("/v1/health")
    def health_check() -> Dict[str, Any]:
        """
        Health check endpoint for monitoring and load balancing
        
        Returns:
            Dict containing health status information
        """
        return get_server().health_check()

    # Global exception handler for unhandled exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Global exception handler for unhandled exceptions
        
        Args:
            request: The request that caused the exception
            exc: The exception that was raised
            
        Returns:
            JSONResponse with error details
        """
        # Don't handle HTTPExceptions - let FastAPI handle those
        if isinstance(exc, HTTPException):
            raise exc
            
        logger.error(f"Unhandled exception: {str(exc)}")
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "timestamp": time.time()
            }
        )
    
    return app


def main():
    """
    Main function with argparse for uvicorn configuration
    """
    # Get current filename dynamically
    CURRENT_MODULE = Path(__file__).stem  # Filename without extension: "frank_stage3"

    parser = argparse.ArgumentParser(description="FRANK Stage 3 Main Server")
    parser.add_argument("--host", type=str, default=os.getenv("HOST", "0.0.0.0"), help="Host to bind the server to (default: HOST or 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Port to run the Simple API on (default: PORT or 8000)")
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("RELOAD", "True").lower() in ("true", "1", "yes"),
        help="Enable auto-reload for development (default: True or RELOAD)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=os.getenv("LOG_LEVEL", "debug"),
        choices=["debug", "info", "warning", "error"],
        help="Logging level (default: debug or LOG_LEVEL)",
    )
    parser.add_argument(
        "-s", "--silent",
        action="store_true",
        default=os.getenv("SILENT", "False").lower() in ("true", "1", "yes"),
        help="Enable silent mode (default: False or SILENT)"
    )

    ### Example configuration settings for the AppConfig
    parser.add_argument(
        "--environment",
        type=str,
        default=os.getenv("FRANK_ENVIRONMENT", "localstack"),
        choices=["localstack", "aws"],
        help="Configuration environment (default: ENVIRONMENT or 'localstack')",
    )
    parser.add_argument("--profile", type=str, default=os.getenv("AWS_PROFILE", None), help="AWS profile (default: AWS_PROFILE or None)")
    parser.add_argument("--aws-access-key-id", type=str, default=os.getenv("AWS_ACCESS_KEY_ID", "test"), help="AWS Access Key ID (default: AWS_ACCESS_KEY_ID or 'test')")
    parser.add_argument("--aws-secret-access-key", type=str, default=os.getenv("AWS_SECRET_ACCESS_KEY", "test"), help="AWS Secret Access Key (default: AWS_SECRET_ACCESS_KEY or 'test')")
    parser.add_argument("--endpoint", type=str, default=os.getenv("ENDPOINT", "http://localhost:4566"), help="DynamoDB Endpoint URL (default: ENDPOINT or LocalStack endpoint)")
    parser.add_argument("--table_name", type=str, default=os.getenv("DYNAMODB_TABLE", "frank-data"), help="DynamoDB Table Name (default: TABLE_NAME or 'frank_table')")
    parser.add_argument("--audit_table_name", type=str, default=os.getenv("DYNAMODB_AUDIT_TABLE", "frank-audit"), help="DynamoDB Audit Table Name (default: AUDIT_TABLE_NAME or 'frank_audit_table')")
    parser.add_argument("--region", type=str, default=os.getenv("AWS_DEFAULT_REGION", "eu-west-1"), help="AWS Region (default: REGION or 'eu-west-1')")
    parser.add_argument(
        "--validation-strategy",
        type=str,
        default=os.getenv("VALIDATION_STRATEGY", "local_only"),
        choices=["local_only", "server_first"],
        help="JWT validation strategy (default: VALIDATION_STRATEGY or 'local_only')",
    )
    parser.add_argument("--cognito-url", type=str, default=os.getenv("COGNITO_URL", "http://localhost:8100/"), help="Cognito URL (default: COGNITO_URL or LocalStack endpoint)")
    parser.add_argument("--user-pool-id", type=str, default=os.getenv("USER_POOL_ID", "eu-west-1_MOCKPOOL"), help="Cognito User Pool ID (default: USER_POOL_ID or 'eu-west-1_MOCKPOOL')")
    parser.add_argument("--jwt-algorithm", type=str, default=os.getenv("JWT_ALGORITHM", "RS256"), help="JWT Algorithm (default: JWT_ALGORITHM or 'RS256')")
    parser.add_argument(
        "--jwt-secret",
        type=str,
        default=os.getenv("JWT_SECRET", "mock-cognito-secret-key"),
        help="JWT Secret (default: JWT_SECRET or 'mock-cognito-secret-key')",
    )

    args = parser.parse_args()
    # Ensure cognito_url ends with a slash
    args.cognito_url += '/' if not args.cognito_url.endswith("/") else ''

    # Set environment variables with command-line overrides
    # This way get_config() will pick them up when called
    os.environ["FRANK_ENVIRONMENT"] = args.environment  # "aws" or "localstack"
    os.environ["AWS_DEFAULT_REGION"] = args.region  # Default to "eu-west-1" if not set
    if args.environment == "localstack":
        os.environ["ENDPOINT"] = args.endpoint  # Default to LocalStack endpoint if not set
        if args.profile:
            os.environ["AWS_PROFILE"] = args.profile  # Use provided profile or None
        else:
            os.environ["AWS_ACCESS_KEY_ID"] = args.aws_access_key_id  # Default to "test" if not set
            os.environ["AWS_SECRET_ACCESS_KEY"] = args.aws_secret_access_key  # Default to "test" if not set
        os.environ["COGNITO_URL"] = args.cognito_url  # Default to LocalStack endpoint if not set
    elif args.environment == "aws":
        # Clear LocalStack-specific env vars for AWS environment
        os.environ.pop("ENDPOINT", None)
        os.environ.pop("AWS_PROFILE", None)
        os.environ.pop("AWS_ACCESS_KEY_ID", None)
        os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
        os.environ["COGNITO_URL"] = f"https://cognito-idp.{args.region}.amazonaws.com/"

    os.environ["DYNAMODB_TABLE"] = args.table_name  # Default to "frank_table" if not set
    os.environ["DYNAMODB_AUDIT_TABLE"] = args.audit_table_name  # Default to "frank_audit_table" if not set
    os.environ["VALIDATION_STRATEGY"] = args.validation_strategy  # Default to "local_only" if not set
    os.environ["USER_POOL_ID"] = args.user_pool_id  # Default to "localstack_user_pool" if not set
    os.environ["JWT_ALGORITHM"] = args.jwt_algorithm  # Default to "RS256" if not set
    os.environ["JWT_SECRET"] = args.jwt_secret  # Default to "mock-cognito-secret-key" if not set

    # Setup logging based on silent flag
    if args.silent:
        logger = setup_logging(silent=True)
        # Set uvicorn log level to critical+ to silence it completely
        args.log_level = "critical"
        # Also disable uvicorn's own logging       
    else:
        logger = setup_logging(silent=False)
        logger.info(f"Starting FastAPI server on {args.host}:{args.port}")
        logger.info(f"Environment: {args.environment}")
        if args.environment == "localstack":
            if args.profile:
                logger.info(f"Using AWS profile: {args.profile}")
            else:
                logger.info("Using explicit AWS credentials for localstack")
            logger.info(f"Endpoint URL: {args.endpoint}")
        logger.info(f"Reload enabled: {args.reload}")
        logger.info(f"Log level: {args.log_level}")
        logger.info(f"Module: {CURRENT_MODULE}")
        logger.info(f"User Pool ID: {args.user_pool_id}")
        logger.info(f"Validation Strategy: {args.validation_strategy}")
        logger.info(f"JWT Algorithm: {args.jwt_algorithm}")
        logger.info(f"JWT Secret: {args.jwt_secret[:4]}... (length: {len(args.jwt_secret)})")
        logger.info(f"Cognito URL: {args.cognito_url}")
        logger.info(f"DynamoDB Table: {args.table_name}")
        logger.info(f"DynamoDB Audit Table: {args.audit_table_name}")

    # Configure logging levels for all FRANK components
    configure_frank_logging(args.log_level)
    logger.info(f"Set logging level to {args.log_level.upper()} for all FRANK components")
    
    # Run uvicorn server with dynamic module name
    uvicorn.run(
        f"{CURRENT_MODULE}:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,  # Indicates create_app is a factory function
        access_log=not args.silent,  # Disable access logging
        log_level=args.log_level if not args.silent else 'critical'
    )


if __name__ == "__main__":  # pragma: no cover
    main()