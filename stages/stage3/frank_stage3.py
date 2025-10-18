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
from logging import config
import os
from pathlib import Path
import time
from typing import Dict, Any, Optional

import boto3
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import uvicorn


import frank
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
    region = os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", None)
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", None)
    table_name = os.environ.get("DYNAMODB_TABLE", "frank-stage3-data")
    audit_table_name = os.environ.get("DYNAMODB_AUDIT_TABLE", "frank-audit-table")

        # Use configuration from db_config
    if environment == "aws":
        session = boto3.Session()
        # Test credentials by calling STS to see what identity we're using
        # sts_client = session.client('sts', region_name=region)
        # identity = sts_client.get_caller_identity()
        # AWS environment - explicitly use default credential chain
        # This ensures we use ECS Task Role when available
        # Force using default credentials (ECS Task Role, EC2 Instance Profile, etc.)
        client = session.client('dynamodb', region_name=region)
        resource = session.resource('dynamodb', region_name=region)       
    elif profile:
        # LocalStack with AWS profile
        session = boto3.Session(profile_name=profile)
        client = session.client(
            'dynamodb',
            endpoint_url=endpoint,
            region_name=region
        )
        resource = session.resource(
            'dynamodb',
            endpoint_url=endpoint,
            region_name=region
        )
    else:
        # LocalStack with explicit credentials
        client = boto3.client(
            'dynamodb',
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=aws_access_key_id or "test",
            aws_secret_access_key=aws_secret_access_key or "test"
        )
        resource = boto3.resource(
            'dynamodb',
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=aws_access_key_id or "test",
            aws_secret_access_key=aws_secret_access_key or "test"
        )


    return {
        "endpoint": endpoint,  # None for AWS, set for LocalStack
        "environment": environment,  
        "profile": profile,
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
        "region": region,
        "table_name": table_name,
        "audit_table_name": audit_table_name,
        "client": client,
        "resource": resource,
        "table": resource.Table(table_name),
        "audit_table": resource.Table(audit_table_name) 
    }
  

# ===================================
# Logging Setup
# ===================================
def setup_logging(silent=False):
    """Setup logging to match Uvicorn's colored output, a bit over the top but nice for dev"""
    
    if silent:
        # Silent mode - disable ALL logging
       
        # Specifically silence known loggers
        for logger_name in ['uvicorn', 'uvicorn.access', 'uvicorn.error', 'fastapi', 'root']:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.CRITICAL)
            logger.disabled = True
            # Remove all handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
        
        return logging.getLogger("uvicorn")  # Return a silenced logger
    
    # Try to use Uvicorn's colored formatter
    try:
        from uvicorn.logging import DefaultFormatter
        
        # Create a colored formatter like Uvicorn uses
        formatter = DefaultFormatter(fmt="%(levelprefix)s %(message)s")
        
        # Setup root logger with the colored formatter
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Add new handler with colored formatter
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        
        # Also setup uvicorn logger specifically
        uvicorn_logger = logging.getLogger("uvicorn")
        uvicorn_logger.setLevel(logging.INFO)
        return uvicorn_logger
        
    except ImportError:
        # Fallback to basic colored format if Uvicorn formatter not available
        logging.basicConfig(
            level=logging.INFO,
            format="\033[32mINFO\033[0m:     %(message)s",  # Green INFO text
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger("uvicorn")


# ====================================
# Container Metadata
# ====================================
def get_container_info():
    """Get container and runtime information for autoscaling identification"""
    try:
        # Get basic system info
        import socket
        import platform
        hostname = socket.gethostname()
        platform_info = platform.platform()
        
        # Try to get ECS task metadata (if running in Fargate)
        ecs_metadata = {}
        metadata_uri = os.environ.get('ECS_CONTAINER_METADATA_URI_V4')
        if metadata_uri:
            try:
                # Get container metadata via HTTP request
                response = requests.get(metadata_uri, timeout=2)
                container_data = response.json()
                ecs_metadata = {
                    "metadata_uri_available": True,
                    "container_name": container_data.get('Name', 'unknown'),
                    "docker_id": container_data.get('DockerId', 'unknown')[:12]  # Short format
                }
            except Exception:
                ecs_metadata = {"metadata_uri_available": False, "container_name": "unknown", "docker_id": "unknown"}
        else:
            ecs_metadata = {"metadata_uri_available": False, "container_name": "unknown", "docker_id": "unknown"}
        
        # Get process ID for uniqueness  
        pid = os.getpid()
        
        return {
            "hostname": hostname,
            "platform": platform_info,
            "pid": pid,
            "ecs_metadata": ecs_metadata,
            "container_id": ecs_metadata.get("docker_id", "unknown")
        }
    except Exception as e:
        return {
            "hostname": "unknown",
            "platform": "unknown", 
            "pid": os.getpid(),
            "ecs_metadata": {"error": str(e)},
            "container_id": "unknown"
        }

# ====================================
# Database handler
# ====================================
def log_access(org_id: str, action: str, resource_type: str = None, details: Dict[str, Any] = None) -> None:
    """Internal method to log access in DynamoDB single table design."""
    timestamp = datetime.now(timezone.utc).isoformat()
    cfg = get_config()
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

    cfg["audit_table"].put_item(Item=log_item)



# ====================================
# Error handlers and Custom Exceptions
# ====================================

class UnauthenticatedError(HTTPException):
    """Custom HTTPException extension for authentication errors"""
    
    def __init__(self, detail: str = "Custom unauthorized error"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

class InternalError(HTTPException):
    """Custom HTTPException extension for internal server errors"""

    def __init__(self, detail: str = "Custom internal server error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail   
        )

# ====================================
# Fastapi Application Factory
# ====================================

def create_app() -> FastAPI:
    """
    Create and configure FastAPI application
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """

    # Security scheme for Bearer token authentication
    security = HTTPBearer()

    def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
        """
        Verify Bearer token authentication
        
        For testing purposes, accepts 'valid-token' as a valid token.
        In production, this would validate against a real authentication system.
        """
        if credentials.credentials != "valid-token":
            raise UnauthenticatedError(detail="Invalid authentication token")
        return credentials.credentials

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
        log_access("123", "root access")

        logger.info("Public endpoint accessed")
        return {
            "message": "Public endpoint accessed successfully",
            "endpoint": "public",
            "authenticated": False,
            "timestamp": time.time()
        }
    
    # 2. Protected endpoint - Bearer token authentication required
    @app.get("/protected")
    def protected_endpoint(token: str = Depends(verify_token)) -> Dict[str, Any]:
        """
        Protected endpoint requiring Bearer token authentication
        
        Args:
            token: Validated Bearer token from verify_token dependency
            
        Returns:
            Dict containing success message and user info
        """
        logger.info("Protected endpoint accessed with valid token")
        return {
            "message": "Protected endpoint accessed successfully",
            "endpoint": "protected",
            "authenticated": True,
            "token": token,
            "user_id": "test-user",
            "timestamp": time.time()
        }
    
    # 3. Exception endpoint - raises standard exception leading to 500
    @app.get("/error")
    def exception_endpoint() -> Dict[str, Any]:
        """
        Exception endpoint that raises a controlled exception
        
        Raises:
            HTTPException: HTTP 500 exception for testing purposes
        """
        logger.error("Exception endpoint accessed - raising controlled exception")
        # Use HTTPException instead of generic Exception for proper handling
        raise InternalError(detail="This is a controlled exception for testing purposes")
    
    # 3b. Python exception endpoint - raises Python exception that gets handled
    @app.get("/python-error")
    def python_exception_endpoint() -> Dict[str, Any]:
        """
        Python exception endpoint that raises a raw Python exception
        
        This demonstrates how the global exception handler converts Python
        exceptions into proper HTTP 500 responses.
        
        Raises:
            ValueError: Python exception that gets caught by global handler
        """
        logger.error("Python exception endpoint accessed - raising ValueError")
        # This will be caught by the global exception handler
        raise ValueError("This is a Python exception converted to HTTP 500")
    
    # 4. Custom error endpoint - raises custom HTTPException extension
    @app.get("/unauthorized")
    def custom_error_endpoint() -> Dict[str, Any]:
        """
        Custom error endpoint that raises UnauthenticatedError
        
        Raises:
            UnauthenticatedError: Custom HTTPException extension
        """
        logger.warning("Custom error endpoint accessed - raising UnauthenticatedError")
        raise UnauthenticatedError("Custom unauthorized error from endpoint")
    
    # 4. Custom error endpoint - raises custom HTTPException extension
    @app.get("/database")
    def database():
        """Database connection endpoint"""
        cfg = get_config()
        container_info = get_container_info()
        
        log_access("123", "database_check")

        try:
            # Get DynamoDB client and resource
            
            # List all tables
            response = cfg["client"].list_tables()
            table_names = response.get('TableNames', [])
                
            # Get table references
            # main_table = cfg["resource"].Table(current_cfg["table_name"])
            # audit_table = cfg["resource"].Table(current_cfg["audit_table_name"])

            # Get item counts from both tables
            main_response = cfg["resource"].Table(cfg["table_name"]).scan(Select='COUNT', Limit=1)
            main_count = main_response.get('Count', 0)
            main_status = "accessible"

            audit_response = cfg["audit_table"].scan(Select='COUNT', Limit=1)
            audit_count = audit_response.get('Count', 0)
            audit_status = "accessible"
            
            return {
                "status": "connected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "async_implementation": "aioboto3",
                "container": container_info,
                "environment": {
                    "DYNAMODB_TABLE": cfg["table_name"],
                    "AUDIT_TABLE": cfg["audit_table_name"],
                    "AWS_DEFAULT_REGION": cfg["region"],
                    "ENDPOINT": cfg["endpoint"] or "AWS (no custom endpoint)",
                    "FRANK_ENVIRONMENT": cfg.get("environment", "default")
                },
                "tables": {
                    "available_tables": table_names,
                    "main": {
                        "name": cfg["table_name"],
                        "status": main_status,
                        "item_count": main_count
                    },
                    "audit": {
                        "name": cfg["audit_table_name"],
                        "status": audit_status,
                        "item_count": audit_count
                    }
                }
            }
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Database connection failed: {str(e)}"
            )

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
    
    # Health check endpoint for monitoring
    @app.get("/v1/health")
    def health_check() -> Dict[str, Any]:
        """
        Health check endpoint for monitoring and load balancing
        
        Returns:
            Dict containing health status information
        """
        current_config = get_config()

        health = {
            "status": "healthy",
            "service": "frank-stage3",
            "version": frank.__version__,
            "timestamp": time.time(),
            "profile": current_config.get("profile", "<not set>"),
            "environment": current_config.get("environment", "<not set>"),
            "region": current_config.get("region", "<not set>"),
            "DYNAMODB_TABLE": current_config.get("table_name", "<not set>"),
            "AUDIT_TABLE": current_config.get("audit_table_name", "<not set>"),
            "ENDPOINT": current_config.get("endpoint", "<not set>"),
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
            print(f"Error getting metadata: {e}")

        return health
    
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
    os.environ["DYNAMODB_TABLE"] = args.table_name  # Default to "frank_table" if not set
    os.environ["DYNAMODB_AUDIT_TABLE"] = args.audit_table_name  # Default to "frank_audit_table" if not set

    # Setup logging based on silent flag
    if args.silent:
        logger = setup_logging(silent=True)
        # Set uvicorn log level to critical+ to silence it completely
        args.log_level = "critical"
        # Also disable uvicorn's own logging       
    else:
        logger = setup_logging(silent=False)
        logger.info(f"Starting FastAPI server on {args.host}:{args.port}")
        logger.info(f"Reload enabled: {args.reload}")
        logger.info(f"Log level: {args.log_level}")
        logger.info(f"Module: {CURRENT_MODULE}")
        
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