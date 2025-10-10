#!/usr/bin/env python3
"""
FRANK Platform - Cognito Authentication Spike - Simple API with Mock Cognito

Demonstrates FastAPI with JWT authentication using Mock Cognito service.
Shows how to implement role-based access control with different access tiers.

This is the Mock Cognito variant - use simple_api_unified.py for both Mock and AWS Cognito support.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
import argparse
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import jwt

from frank.core.enum import AccessTier


# Configure logging to match Uvicorn's colored format
def setup_logging():
    """Setup logging to match Uvicorn's colored output"""
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
logger = logging.getLogger("simple_api")

# Security
security = HTTPBearer()

# Mock Cognito configuration
MOCK_COGNITO_URL = os.getenv("MOCK_COGNITO_URL", "http://localhost:8100")
JWT_SECRET = "mock-cognito-secret-key"  # Should match mock_cognito.py
JWT_ALGORITHM = "HS256"

# Role mapping now uses AccessTier.from_string() method for flexible group handling
# This maps Mock Cognito groups to FRANK AccessTier enum values
def get_access_tier_from_groups(groups: List[str]) -> AccessTier:
    """Convert user groups to AccessTier using from_string method"""
    if not groups:
        return AccessTier.PUBLIC
    
    # Use the first group and convert it using the from_string method
    primary_group = groups[0]
    return AccessTier.from_string(primary_group, default=True)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Extract user information from JWT token and validate with Mock Cognito.
    Returns user info with access tier for authorization decisions.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        # Decode JWT token (matching mock_cognito.py verification)
        payload = jwt.decode(
            token, 
            JWT_SECRET, 
            algorithms=[JWT_ALGORITHM], 
            options={"verify_aud": False}
        )
        
        username = payload.get("username")
        groups = payload.get("cognito:groups", [])
        
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing username",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Map first group to access tier
        # Use AccessTier.from_string() method to convert user groups
        access_tier = get_access_tier_from_groups(groups)

        return {
            "username": username,
            "groups": groups,
            "access_tier": access_tier,
            "organisation_id": f"org-{username}",
            "token_valid": True
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def check_access_level(user_access_tier: AccessTier, required_tier: AccessTier) -> bool:
    """Check if user access tier meets required level using enum hierarchy"""
    tier_hierarchy = {
        AccessTier.PUBLIC: 0,
        AccessTier.OBSERVER: 1,
        AccessTier.CONTRIBUTOR: 2,
        AccessTier.PARTNER: 3,
        AccessTier.CORE_MEMBER: 4,
    }
    
    user_level = tier_hierarchy.get(user_access_tier, 0)
    required_level = tier_hierarchy.get(required_tier, 0)
    
    return user_level >= required_level


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    # FastAPI app with OpenAPI documentation
    app = FastAPI(
        title="FRANK Simple API",
        description="Simple API demonstrating role-based access control with Mock Cognito authentication",
        version="1.0.0",
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

    # API Endpoints
    @app.get("/")
    async def root():
        """Root endpoint with API information"""
        return {
            "service": "FRANK Simple API",
            "version": "1.0.0",
            "authentication": "Mock Cognito JWT",
            "endpoints": {
                "public": "/public",
                "observer": "/observer",
                "contributor": "/contributor", 
                "partner": "/partner",
                "core_member": "/core_member",
                "user_info": "/user-info",
                "docs": "/docs",
                "health": "/health"
            },
            "mock_cognito": MOCK_COGNITO_URL,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "service": "frank-simple-api",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mock_cognito_url": MOCK_COGNITO_URL
        }

    @app.get("/public")
    async def public_endpoint():
        """
        Public endpoint - no authentication required
        """
        return {
            "message": "This is a public endpoint",
            "access_level": "public",
            "description": "Anyone can access this endpoint without authentication",
            "data": {
                "public_info": "This information is available to everyone",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service_version": "1.0.0"
            }
        }

    @app.get("/observer")
    async def observer_endpoint(current_user: Dict[str, Any] = Depends(get_current_user)):
        """
        Endpoint requiring OBSERVER access tier
        Throws 403 if user doesn't have sufficient access level
        """
        required_tier = AccessTier.OBSERVER
        
        if not check_access_level(current_user["access_tier"], required_tier):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient access level. Required: {required_tier.value}, User has: {current_user['access_tier'].value}"
            )
        
        return {
            "message": "Observer access granted",
            "user": current_user["username"],
            "access_tier": current_user["access_tier"].value,
            "observer_data": "Data accessible to observer level and above",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @app.get("/contributor")
    async def contributor_endpoint(current_user: Dict[str, Any] = Depends(get_current_user)):
        """
        Endpoint requiring CONTRIBUTOR access tier
        Throws 403 if user doesn't have sufficient access level
        """
        required_tier = AccessTier.CONTRIBUTOR
        
        if not check_access_level(current_user["access_tier"], required_tier):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient access level. Required: {required_tier.value}, User has: {current_user['access_tier'].value}"
            )
        
        return {
            "message": "Welcome to the CONTRIBUTOR level endpoint",
            "access_level": "contributor",
            "description": "This endpoint requires CONTRIBUTOR or higher access tier",
            "user_info": {
                "username": current_user["username"],
                "access_tier": current_user["access_tier"].value,
                "groups": current_user["groups"],
                "organisation_id": current_user["organisation_id"]
            },
            "data": {
                "contributor_data": "This is sensitive information for contributors and above",
                "permissions": ["read_threat_intel", "submit_indicators"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

    @app.get("/partner")
    async def partner_endpoint(current_user: Dict[str, Any] = Depends(get_current_user)):
        """
        Endpoint requiring PARTNER access tier
        Throws 403 if user doesn't have sufficient access level
        """
        required_tier = AccessTier.PARTNER
        
        if not check_access_level(current_user["access_tier"], required_tier):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient access level. Required: {required_tier.value}, User has: {current_user['access_tier'].value}"
            )
        
        return {
            "message": "Welcome to the PARTNER level endpoint",
            "access_level": "partner",
            "description": "This endpoint requires PARTNER or higher access tier",
            "user_info": {
                "username": current_user["username"],
                "access_tier": current_user["access_tier"].value,
                "groups": current_user["groups"],
                "organisation_id": current_user["organisation_id"]
            },
            "data": {
                "partner_data": "This is highly sensitive information for partners and core members only",
                "permissions": ["read_threat_intel", "submit_indicators", "access_iocs", "manage_feeds"],
                "exclusive_features": ["advanced_analytics", "custom_reports", "api_integrations"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

    @app.get("/core_member")
    async def core_member_endpoint(current_user: Dict[str, Any] = Depends(get_current_user)):
        """
        Endpoint requiring CORE_MEMBER access tier
        Throws 403 if user doesn't have sufficient access level
        """
        required_tier = AccessTier.CORE_MEMBER
        
        if not check_access_level(current_user["access_tier"], required_tier):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient access level. Required: {required_tier.value}, User has: {current_user['access_tier'].value}"
            )
        
        return {
            "message": "Welcome to the CORE_MEMBER level endpoint",
            "access_level": "core_member",
            "description": "This endpoint requires CORE_MEMBER access tier - highest level",
            "user_info": {
                "username": current_user["username"],
                "access_tier": current_user["access_tier"].value,
                "groups": current_user["groups"],
                "organisation_id": current_user["organisation_id"]
            },
            "data": {
                "core_member_data": "This is the most sensitive information for core members only",
                "permissions": ["read_threat_intel", "submit_indicators", "access_iocs", "manage_feeds", "admin_access", "system_config"],
                "admin_features": ["user_management", "system_monitoring", "full_api_access", "data_export"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

    @app.get("/user-info")
    async def get_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
        """
        Get current user information - requires authentication but no specific tier
        """
        return {
            "message": "Current user information",
            "user": {
                "username": current_user["username"],
                "access_tier": current_user["access_tier"].value,
                "groups": current_user["groups"],
                "organisation_id": current_user["organisation_id"],
                "permissions": {
                    "can_access_public": True,
                    "can_access_contributor": check_access_level(current_user["access_tier"], AccessTier.CONTRIBUTOR),
                    "can_access_partner": check_access_level(current_user["access_tier"], AccessTier.PARTNER),
                    "can_access_core": check_access_level(current_user["access_tier"], AccessTier.CORE_MEMBER)
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    logger.info("FRANK Simple API application created successfully")
    return app


# Create module-level app instance for ASGI servers
app = create_app()


def main():
    """
    Main function with argparse for uvicorn configuration
    """
    parser = argparse.ArgumentParser(description="Run FRANK Simple API with Mock Cognito authentication")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Port to run the Simple API on (default: 8000)")
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
    
    logger.info(f"Starting FRANK Simple API on {args.host}:{args.port}")
    logger.info(f"Reload enabled: {args.reload}")
    logger.info(f"Log level: {args.log_level}")
    logger.info(f"Mock Cognito URL: {MOCK_COGNITO_URL}")
    
    # Run uvicorn server
    uvicorn.run(
        "simple_api:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,  # Indicates create_app is a factory function
        log_level=args.log_level
    )


if __name__ == "__main__":  # pragma: no cover
    main()