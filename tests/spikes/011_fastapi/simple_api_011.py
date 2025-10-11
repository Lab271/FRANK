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
import logging
import os
from pathlib import Path
import time
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

class AppConfig:
    """Configuration class for Simple API settings"""
    _instance: "AppConfig" = None

    def __init__(self,
        setting_a: str,
        setting_n: str
    ):
        self.setting_a = setting_a
        self.setting_n = setting_n
    
    @classmethod
    def get_config(cls) -> "AppConfig":
        """Get singleton AppConfig instance, creating it from environment if needed"""
        if cls._instance is None:
            cls._instance = cls(
                setting_a=os.getenv("SETTING_A", "default_value_a"),
                setting_n=os.getenv("SETTING_N", "default_value_n")
            )
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance"""
        cls._instance = None

    @classmethod
    def update(cls, **kwargs) -> None:
        """Update configuration values"""
        config = cls.get_config()
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

def get_config() -> AppConfig:
    """Dependency to get AppConfig instance"""
    return AppConfig.get_config()   

# Configure logging to match Uvicorn's colored format
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
        version="0.1.0"
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
        raise InternalError(detail="This is a controlled exception for testing purposes")
    
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
    @app.get("/health")
    async def health_check() -> Dict[str, Any]:
        """
        Health check endpoint for monitoring and load balancing
        
        Returns:
            Dict containing health status information
        """
        current_config = get_config()

        return {
            "status": "healthy",
            "service": "fastapi-spike",
            "version": "0.1.0",
            "timestamp": time.time(),
            "setting_a": current_config.setting_a,
            "setting_n": current_config.setting_n,
            "filename": Path(__file__).name, # "simple_api_011.py"
        }
    
    return app


def main():
    """
    Main function with argparse for uvicorn configuration
    """
    # Get current filename dynamically
    CURRENT_MODULE = Path(__file__).stem  # Filename without extension: "simple_api_011"

    parser = argparse.ArgumentParser(description="FastAPI Testability Spike Server")
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
    parser.add_argument("--setting_a", type=str, default=os.getenv("SETTING_A", "default_value_a"), help="Configuration setting A (default: SETTING_A or 'default_value_a')")
    parser.add_argument("--setting_n", type=str, default=os.getenv("SETTING_N", "default_value_n"), help="Configuration setting N (default: SETTING_N or 'default_value_n')")   

    args = parser.parse_args()
    
    # Set environment variables with command-line overrides
    # This way get_config() will pick them up when called
    os.environ["SETTING_A"] = args.setting_a
    os.environ["SETTING_N"] = args.setting_n
    
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