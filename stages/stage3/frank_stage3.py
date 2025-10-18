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
from datetime import datetime, timezone, timedelta
from functools import lru_cache
import logging
import os
from pathlib import Path
import time
from typing import Dict, Any

import boto3
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import uvicorn

import frank
from frank.util.http_exceptions import InternalError
from frank.util.auth import CognitoValidator
from frank.util.aws import get_container_info
from frank.util.logger import setup_logging

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

    return {
        "endpoint": endpoint,  # None for AWS, set for LocalStack
        "environment": environment,  
        "profile": profile,
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
        "region": region,
        "table_name": table_name,
        "audit_table_name": audit_table_name
    }
  
@lru_cache()
def get_client():
    """Return client"""
    client = TempClient()
    return client



# ====================================
# Database handler
# ====================================

class TempClient:
    """Client dependency for FastAPI"""
    def __init__(self):
        self.config = get_config()
        self.logger = logging.getLogger("uvicorn")
        self.initialize()

    def initialize(self):
        if self.config["environment"] == "aws":
            session = boto3.Session()
            # Test credentials by calling STS to see what identity we're using
            # sts_client = session.client('sts', region_name=region)
            # identity = sts_client.get_caller_identity()
            # AWS environment - explicitly use default credential chain
            # This ensures we use ECS Task Role when available
            # Force using default credentials (ECS Task Role, EC2 Instance Profile, etc.)
            self.client = session.client('dynamodb', region_name=self.config["region"])
            self.resource = session.resource('dynamodb', region_name=self.config["region"])
        elif self.config["profile"]:
            # LocalStack with AWS profile
            session = boto3.Session(profile_name=self.config["profile"])
            self.client = session.client("dynamodb", endpoint_url=self.config["endpoint"], region_name=self.config["region"])
            self.resource = session.resource("dynamodb", endpoint_url=self.config["endpoint"], region_name=self.config["region"])
        else:
            # LocalStack with explicit credentials
            self.client = boto3.client(
                'dynamodb',
                endpoint_url=self.config["endpoint"],
                region_name=self.config["region"],
                aws_access_key_id=self.config["aws_access_key_id"] or "test",
                aws_secret_access_key=self.config["aws_secret_access_key"] or "test"
            )
            self.resource = boto3.resource(
                'dynamodb',
                endpoint_url=self.config["endpoint"],
                region_name=self.config["region"],
                aws_access_key_id=self.config["aws_access_key_id"] or "test",
                aws_secret_access_key=self.config["aws_secret_access_key"] or "test"
            )

        self.table = self.resource.Table(self.config["table_name"])
        self.audit_table = self.resource.Table(self.config["audit_table_name"])

    def log_access(self, org_id: str, action: str, resource_type: str = None, details: Dict[str, Any] = None) -> None:
        """Internal method to log access in DynamoDB single table design."""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_item = {
            'PK': f"LOG#{org_id}",
            'SK': f"LOG#{timestamp}",
            'GSI1PK': f"ACTION#{action}",
            'GSI1SK': timestamp,
            'EntityType': 'AccessLog',
            'organisation_id': org_id,
            'action': action,
            'resource_type': resource_type,
            'timestamp': timestamp,
            'TTL': int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())
        }
        if details:
            log_item['details'] = details

        self.audit_table.put_item(Item=log_item)

    def deep_health_check(self) -> Dict[str, Any]:
        """Perform a deep health check by querying DynamoDB tables"""
        container_info = get_container_info()
        
        get_client().log_access("123", "database_check")

        try:
            # Get DynamoDB client and resource
            
            # List all tables
            response = self.client.list_tables()
            table_names = response.get('TableNames', [])
                
            # Get table references
            # main_table = cfg["resource"].Table(current_cfg["table_name"])
            # audit_table = cfg["resource"].Table(current_cfg["audit_table_name"])

            # Get item counts from both tables
            main_response = self.resource.Table(self.config["table_name"]).scan(Select='COUNT')
            main_count = main_response.get('Count', 0)
            main_status = "accessible"

            audit_response = self.resource.Table(self.config["audit_table_name"]).scan(Select='COUNT')
            audit_count = audit_response.get('Count', 0)
            audit_status = "accessible"
            
            return {
                "status": "connected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "container": container_info,
                "environment": {
                    "DYNAMODB_TABLE": self.config["table_name"],
                    "AUDIT_TABLE": self.config["audit_table_name"],
                    "AWS_DEFAULT_REGION": self.config["region"],
                    "ENDPOINT": self.config["endpoint"] or "AWS (no custom endpoint)",
                    "FRANK_ENVIRONMENT": self.config.get("environment", "default")
                },
                "tables": {
                    "available_tables": table_names,
                    "main": {
                        "name": self.config["table_name"],
                        "status": main_status,
                        "item_count": main_count
                    },
                    "audit": {
                        "name": self.config["audit_table_name"],
                        "status": audit_status,
                        "item_count": audit_count
                    }
                }
            }
        except Exception as e:
            self.logger.error(f"Database connection error: {str(e)}")
            raise InternalError(detail=f"Database connection failed: {str(e)}")

    def health_check(self) -> Dict[str, Any]:
        """Perform a simple health check by listing tables"""
        health = {
            "status": "healthy",
            "service": "frank-stage3",
            "version": frank.__version__,
            "timestamp": time.time(),
            "profile": self.config.get("profile", "<not set>"),
            "environment": self.config.get("environment", "<not set>"),
            "region": self.config.get("region", "<not set>"),
            "DYNAMODB_TABLE": self.config.get("table_name", "<not set>"),
            "AUDIT_TABLE": self.config.get("audit_table_name", "<not set>"),
            "ENDPOINT": self.config.get("endpoint", "<not set>"),
            "CONTAINER_ID": os.getenv("CONTAINER_ID", "unknown"),
            "filename": Path(__file__).name, # "frank_stage3.py"
        }

        try:
            # ECS provides this environment variable automatically
            metadata_uri = os.environ.get('ECS_CONTAINER_METADATA_URI_V4')
            
            if metadata_uri:
                # Get container metadata
                container_response = requests.get(metadata_uri)
                container_data = container_response.json()
                
                # Get task metadata  
                task_response = requests.get(f"{metadata_uri}/task")
                task_data = task_response.json()
                
                health['container_metadata'] = {
                    "container_id": container_data.get('DockerId', 'unknown'),
                    "container_name": container_data.get('Name'),
                    "task_arn": task_data.get('TaskARN'), 
                    "task_definition": task_data.get('Family'),
                    "cluster": task_data.get('Cluster'),
                    "availability_zone": task_data.get('AvailabilityZone')
                }
        except Exception as e:
            raise InternalError(detail=f"Error getting metadata: {e}")

        return health
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
    logger = logging.getLogger("uvicorn")

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
    def protected_endpoint(user: str = Depends(validator.get_current_user)) -> Dict[str, Any]:
        """
        Protected endpoint requiring Bearer token authentication
        
        Args:
            user: Validated user from get_current_user dependency
            
        Returns:
            Dict containing success message and user info
        """
        logger.info("Protected endpoint accessed with valid token")
        return {
            "message": "Protected endpoint accessed successfully",
            "endpoint": "protected",
            "authenticated": True,
            "user": user,
            "timestamp": time.time()
        }
    
   
    # 4. Custom error endpoint - raises custom HTTPException extension
    @app.get("/v1/deep-health")
    def database() -> Dict[str, Any]:
        """
        Database connection endpoint

        Returns:
            Dict containing deep health check information
        """
        return get_client().deep_health_check()         

    # Health check endpoint for monitoring
    @app.get("/v1/health")
    def health_check() -> Dict[str, Any]:
        """
        Health check endpoint for monitoring and load balancing
        
        Returns:
            Dict containing health status information
        """
        return get_client().health_check()   

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
                "detail": str(exc),
                "endpoint": str(request.url),
                "method": request.method,
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
        default=os.getenv("RELOAD", "False").lower() in ("true", "1", "yes"),
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
    parser.add_argument("--environment", type=str, default=os.getenv("FRANK_ENVIRONMENT", "aws"), help="Configuration environment (default: ENVIRONMENT or 'aws')")
    parser.add_argument("--profile", type=str, default=os.getenv("AWS_PROFILE", None), help="AWS profile (default: AWS_PROFILE or None)")
    parser.add_argument("--aws-access-key-id", type=str, default=os.getenv("AWS_ACCESS_KEY_ID", "test"), help="AWS Access Key ID (default: AWS_ACCESS_KEY_ID or 'test')")
    parser.add_argument("--aws-secret-access-key", type=str, default=os.getenv("AWS_SECRET_ACCESS_KEY", "test"), help="AWS Secret Access Key (default: AWS_SECRET_ACCESS_KEY or 'test')")
    parser.add_argument("--endpoint", type=str, default=os.getenv("ENDPOINT", "http://localhost:4566"), help="DynamoDB Endpoint URL (default: ENDPOINT or LocalStack endpoint)")
    parser.add_argument("--table_name", type=str, default=os.getenv("DYNAMODB_TABLE", "frank_table"), help="DynamoDB Table Name (default: TABLE_NAME or 'frank_table')")
    parser.add_argument("--audit_table_name", type=str, default=os.getenv("DYNAMODB_AUDIT_TABLE", "frank_audit_table"), help="DynamoDB Audit Table Name (default: AUDIT_TABLE_NAME or 'frank_audit_table')")
    parser.add_argument("--region", type=str, default=os.getenv("AWS_DEFAULT_REGION", "eu-west-1"), help="AWS Region (default: REGION or 'eu-west-1')")
    parser.add_argument("--validation-strategy", type=str, default=os.getenv("VALIDATION_STRATEGY", "local_only"), help="JWT validation strategy (default: VALIDATION_STRATEGY or 'local_only')")
    parser.add_argument("--cognito-url", type=str, default=os.getenv("COGNITO_URL", "http://localhost:4566"), help="Cognito URL (default: COGNITO_URL or LocalStack endpoint)")
    parser.add_argument("--user-pool-id", type=str, default=os.getenv("USER_POOL_ID", "localstack_user_pool"), help="Cognito User Pool ID (default: USER_POOL_ID or 'localstack_user_pool')")
    parser.add_argument("--jwt-algorithm", type=str, default=os.getenv("JWT_ALGORITHM", "RS256"), help="JWT Algorithm (default: JWT_ALGORITHM or 'RS256')")     

    args = parser.parse_args()
    
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
        logger.info(f"Cognito User Pool ID: {args.user_pool_id}")
        logger.info(f"JWT Algorithm: {args.jwt_algorithm}")
        logger.info(f"Cognito URL: {args.cognito_url}")

    logging.getLogger('uvicorn').setLevel(getattr(logging, args.log_level.upper()))
    
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