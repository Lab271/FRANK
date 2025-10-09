#!/usr/bin/env python3
"""
FRANK Platform - Cognito Authentication Spike - Unified Simple API

Demonstrates FastAPI with JWT authentication supporting both:
- Mock Cognito service (for local development)
- AWS Cognito service (for production/staging)

Shows how to implement role-based access control with AccessTier enum.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
import sys
import json
import argparse
import boto3
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import jwt
from jwt import PyJWKClient
import requests

# Add FRANK core to path for enum imports
from frank.core.enum import AccessTier

# Configuration
USE_AWS_COGNITO = os.getenv("USE_AWS_COGNITO", "false").lower() == "true"

# AWS Cognito Configuration
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
USER_POOL_ID = os.getenv("USER_POOL_ID", "")
APP_CLIENT_ID = os.getenv("APP_CLIENT_ID", "")
COGNITO_ENDPOINT = os.getenv("COGNITO_ENDPOINT", f"https://cognito-idp.{AWS_REGION}.amazonaws.com/")

# Mock Cognito Configuration
MOCK_COGNITO_URL = os.getenv("MOCK_COGNITO_URL", "http://localhost:8100")
JWT_SECRET = "test-secret-key-for-mock-cognito"  # In production, get from secure storage
JWT_ALGORITHM = "HS256"

# Setup logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("frank-simple-api")

# FastAPI app with OpenAPI documentation
app = FastAPI(
    title="FRANK Simple API - Unified",
    description=f"Simple API demonstrating role-based access control with {'AWS' if USE_AWS_COGNITO else 'Mock'} Cognito authentication",
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

# Initialize authentication components based on configuration
security = HTTPBearer()

# Authentication configuration variables
if USE_AWS_COGNITO:
    # AWS Cognito setup
    if not USER_POOL_ID or not APP_CLIENT_ID:
        logger.error("AWS Cognito mode requires USER_POOL_ID and APP_CLIENT_ID environment variables")
        sys.exit(1)
    
    JWKS_URL = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
    JWKS_CLIENT = PyJWKClient(JWKS_URL)
    PROVIDER_NAME = "aws_cognito"
    
    logger.info(f"🔧 Initialized AWS Cognito authentication:")
    logger.info(f"   Region: {AWS_REGION}")
    logger.info(f"   User Pool ID: {USER_POOL_ID}")
    logger.info(f"   App Client ID: {APP_CLIENT_ID}")
    logger.info(f"   JWKS URL: {JWKS_URL}")
else:
    # Mock Cognito setup
    PROVIDER_NAME = "mock_cognito"
    
    logger.info(f"🔧 Initialized Mock Cognito authentication:")
    logger.info(f"   Mock Cognito URL: {MOCK_COGNITO_URL}")
    logger.info(f"   JWT Algorithm: {JWT_ALGORITHM}")


def get_access_tier_from_groups(groups: List[str]) -> AccessTier:
    """Convert user groups to AccessTier using from_string method"""
    if not groups:
        return AccessTier.PUBLIC
    
    # Use the first group and convert it using the from_string method
    primary_group = groups[0]
    return AccessTier.from_string(primary_group, default=True)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Unified user authentication that handles both AWS Cognito and Mock Cognito.
    The authentication method is determined by the USE_AWS_COGNITO configuration.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        if USE_AWS_COGNITO:
            # AWS Cognito JWT validation
            signing_key = JWKS_CLIENT.get_signing_key_from_jwt(token)
            
            # Decode and verify JWT token with AWS Cognito settings
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}"
            )
            
            # Verify client_id manually since AWS Cognito access tokens don't have "aud" claim
            token_client_id = payload.get("client_id")
            if token_client_id != APP_CLIENT_ID:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token: client_id mismatch. Expected {APP_CLIENT_ID}, got {token_client_id}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            username = payload.get("username") or payload.get("cognito:username")
        else:
            # Mock Cognito JWT validation
            payload = jwt.decode(
                token, 
                JWT_SECRET, 
                algorithms=[JWT_ALGORITHM], 
                options={"verify_aud": False}
            )
            
            username = payload.get("username")
        
        # Common processing for both providers
        groups = payload.get("cognito:groups", [])
        
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing username",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Convert groups to access tier using enhanced enum method
        access_tier = get_access_tier_from_groups(groups)

        return {
            "username": username,
            "groups": groups,
            "access_tier": access_tier,
            "organisation_id": f"org-{username}",
            "token_valid": True,
            "provider": PROVIDER_NAME
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with basic service information"""
    return {
        "message": "FRANK Simple API - Unified Authentication",
        "provider": "AWS Cognito" if USE_AWS_COGNITO else "Mock Cognito",
        "version": "1.0.0",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": {
            "public": "/public",
            "observer": "/observer",
            "contributor": "/contributor",
            "partner": "/partner", 
            "core_member": "/core_member",
            "user_info": "/user-info",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "FRANK Simple API - Unified",
        "version": "1.0.0",
        "authentication": {
            "provider": "AWS Cognito" if USE_AWS_COGNITO else "Mock Cognito",
            "aws_region": AWS_REGION if USE_AWS_COGNITO else None,
            "user_pool_id": USER_POOL_ID if USE_AWS_COGNITO else None,
            "mock_cognito_url": MOCK_COGNITO_URL if not USE_AWS_COGNITO else None
        },
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
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/public")
async def public_endpoint():
    """Public endpoint accessible without authentication"""
    return {
        "message": "Welcome to the public endpoint",
        "access_level": "public",
        "description": "This endpoint is accessible without authentication",
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
    
    if not current_user["access_tier"].check_access_level(required_tier):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient access level. Required: {required_tier.value}, User has: {current_user['access_tier'].value}"
        )
    
    return {
        "message": "Observer access granted",
        "user": current_user["username"],
        "access_tier": current_user["access_tier"].value,
        "provider": current_user["provider"],
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
    
    if not current_user["access_tier"].check_access_level(required_tier):
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
            "organisation_id": current_user["organisation_id"],
            "provider": current_user["provider"]
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
    
    if not current_user["access_tier"].check_access_level(required_tier):
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
            "organisation_id": current_user["organisation_id"],
            "provider": current_user["provider"]
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
    
    if not current_user["access_tier"].check_access_level(required_tier):
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
            "organisation_id": current_user["organisation_id"],
            "provider": current_user["provider"]
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
        "message": "User information retrieved successfully",
        "user_info": {
            "username": current_user["username"],
            "access_tier": current_user["access_tier"].value,
            "groups": current_user["groups"],
            "organisation_id": current_user["organisation_id"],
            "provider": current_user["provider"],
            "token_valid": current_user["token_valid"]
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def parse_arguments():
    """Parse command line arguments for configuration"""
    parser = argparse.ArgumentParser(description="FRANK Simple API - Unified Authentication")
    parser.add_argument("--use-aws", action="store_true", 
                       help="Use AWS Cognito instead of Mock Cognito")
    parser.add_argument("--user-pool-id", type=str, 
                       help="AWS Cognito User Pool ID")
    parser.add_argument("--app-client-id", type=str, 
                       help="AWS Cognito App Client ID")
    parser.add_argument("--aws-region", type=str, default="eu-central-1",
                       help="AWS Region (default: eu-central-1)")
    parser.add_argument("--mock-cognito-url", type=str, default="http://localhost:8100",
                       help="Mock Cognito URL (default: http://localhost:8100)")
    parser.add_argument("--port", type=int, default=8000,
                       help="Port to run the API server (default: 8000)")
    
    return parser.parse_args()


if __name__ == "__main__":
    import uvicorn
    
    args = parse_arguments()
    
    # Override environment variables with command line arguments
    if args.use_aws:
        os.environ["USE_AWS_COGNITO"] = "true"
    if args.user_pool_id:
        os.environ["USER_POOL_ID"] = args.user_pool_id
    if args.app_client_id:
        os.environ["APP_CLIENT_ID"] = args.app_client_id
    if args.aws_region:
        os.environ["AWS_REGION"] = args.aws_region
    if args.mock_cognito_url:
        os.environ["MOCK_COGNITO_URL"] = args.mock_cognito_url
    
    # Re-read configuration after potential override
    USE_AWS_COGNITO = os.getenv("USE_AWS_COGNITO", "false").lower() == "true"
    
    print(f"🚀 Starting FRANK Simple API - Unified")
    print(f"   Authentication Provider: {'AWS Cognito' if USE_AWS_COGNITO else 'Mock Cognito'}")
    print(f"   Port: {args.port}")
    print(f"   Documentation: http://localhost:{args.port}/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=args.port)