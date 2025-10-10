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
import logging
import time
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse


# Configure logging to match Uvicorn's colored format
def setup_logging():
    """Setup logging to match Uvicorn's colored output, a bit over the top but nice for dev"""
    import logging
    
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
        
    except ImportError:
        # Fallback to basic colored format if Uvicorn formatter not available
        logging.basicConfig(
            level=logging.INFO,
            format="\033[32mINFO\033[0m:     %(message)s",  # Green INFO text
            handlers=[logging.StreamHandler()]
        )

setup_logging()
logger = logging.getLogger("fastapi_spike")


# Security scheme for Bearer token authentication
security = HTTPBearer()


class UnauthenticatedError(HTTPException):
    """Custom HTTPException extension for authentication errors"""
    
    def __init__(self, detail: str = "Custom unauthorized error"):
        super().__init__(
            status_code=401,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Verify Bearer token authentication
    
    For testing purposes, accepts 'valid-token' as a valid token.
    In production, this would validate against a real authentication system.
    """
    if credentials.credentials != "valid-token":
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return credentials.credentials


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    app = FastAPI(
        title="FRANK FastAPI Testability Spike",
        description="Spike for validating FastAPI testability patterns",
        version="0.1.0"
    )
    
    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        
        logger.info(f"Request: {request.method} {request.url}")
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        logger.info(
            f"Response: {response.status_code} "
            f"Time: {process_time:.4f}s"
        )
        
        return response
    
    # 1. Public endpoint - no authentication required
    @app.get("/")
    async def public_endpoint() -> Dict[str, Any]:
        """
        Public endpoint accessible without authentication
        
        Returns:
            Dict containing success message and endpoint info
        """
        logger.info("Public endpoint accessed")
        return {
            "message": "Public endpoint accessed successfully",
            "endpoint": "public",
            "authenticated": False,
            "timestamp": time.time()
        }
    
    # 2. Protected endpoint - Bearer token authentication required
    @app.get("/protected")
    async def protected_endpoint(token: str = Depends(verify_token)) -> Dict[str, Any]:
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
    async def exception_endpoint() -> Dict[str, Any]:
        """
        Exception endpoint that raises a controlled exception
        
        Raises:
            HTTPException: HTTP 500 exception for testing purposes
        """
        logger.error("Exception endpoint accessed - raising controlled exception")
        # Use HTTPException instead of generic Exception for proper handling
        raise HTTPException(
            status_code=500,
            detail="This is a controlled exception for testing purposes"
        )
    
    # 3b. Python exception endpoint - raises Python exception that gets handled
    @app.get("/python-error")
    async def python_exception_endpoint() -> Dict[str, Any]:
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
    async def custom_error_endpoint() -> Dict[str, Any]:
        """
        Custom error endpoint that raises UnauthenticatedError
        
        Raises:
            UnauthenticatedError: Custom HTTPException extension
        """
        logger.warning("Custom error endpoint accessed - raising UnauthenticatedError")
        raise UnauthenticatedError("Custom unauthorized error from endpoint")
    
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
        if isinstance(exc, HTTPException):  # pragma: no cover
            raise exc
            
        logger.error(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc),
                "endpoint": str(request.url),
                "method": request.method,
                "timestamp": time.time()
            }
        )
    
    # Health check endpoint for monitoring
    @app.get("/health")
    async def health_check() -> Dict[str, Any]:
        """
        Health check endpoint for monitoring and load balancing
        
        Returns:
            Dict containing health status information
        """
        return {
            "status": "healthy",
            "service": "fastapi-spike",
            "version": "0.1.0",
            "timestamp": time.time()
        }
    
    logger.info("FastAPI application created successfully")
    return app


def main():
    """
    Main function with argparse for uvicorn configuration
    """
    parser = argparse.ArgumentParser(description="FastAPI Testability Spike Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind the server to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Logging level (default: info)",
    )

    args = parser.parse_args()
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    logger.info(f"Starting FastAPI server on {args.host}:{args.port}")
    logger.info(f"Reload enabled: {args.reload}")
    logger.info(f"Log level: {args.log_level}")
    
    # Run uvicorn server
    uvicorn.run(
        "simple_api_011:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True, # Indicates create_app is a factory function
        log_level=args.log_level
    )


if __name__ == "__main__":  # pragma: no cover
    main()