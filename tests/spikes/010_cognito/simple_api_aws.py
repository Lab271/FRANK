#!/usr/bin/env python3
"""
FRANK Platform - Cognito Authentication Spike - Simple API with AWS Cognito Integration

Demonstrates FastAPI with JWT authentication using real AWS Cognito service.
Shows how to implement role-based access control with AWS Cognito User Pool.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
import sys
import json
import argparse
import boto3
from typing import Dict, Any, Optional
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

# Configuration - can be overridden by command line arguments or environment variables
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
USER_POOL_ID = os.getenv("USER_POOL_ID", "")
APP_CLIENT_ID = os.getenv("APP_CLIENT_ID", "")
COGNITO_ENDPOINT = os.getenv("COGNITO_ENDPOINT", f"https://cognito-idp.{AWS_REGION}.amazonaws.com/")

# FastAPI app with OpenAPI documentation
app = FastAPI(
    title="FRANK Simple API - AWS Cognito",
    description="Simple API demonstrating role-based access control with AWS Cognito authentication",
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

# Security
security = HTTPBearer()

# Global variables for AWS Cognito configuration
JWKS_CLIENT = None
COGNITO_CLIENT = None

def init_cognito_client():
    """Initialize AWS Cognito client and JWKS client for JWT verification"""
    global JWKS_CLIENT, COGNITO_CLIENT
    
    if not USER_POOL_ID or not APP_CLIENT_ID:
        raise ValueError("USER_POOL_ID and APP_CLIENT_ID must be configured")
    
    # Initialize JWKS client for JWT token verification
    jwks_url = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
    JWKS_CLIENT = PyJWKClient(jwks_url)
    
    # Initialize Cognito client for authentication
    COGNITO_CLIENT = boto3.client('cognito-idp', region_name=AWS_REGION)
    
    print(f"✅ Cognito client initialized:")
    print(f"   Region: {AWS_REGION}")
    print(f"   User Pool ID: {USER_POOL_ID}")
    print(f"   App Client ID: {APP_CLIENT_ID}")
    print(f"   JWKS URL: {jwks_url}")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Extract user information from AWS Cognito JWT token.
    Validates the token against AWS Cognito JWKS and extracts user claims.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        # Get signing key from JWKS
        signing_key = JWKS_CLIENT.get_signing_key_from_jwt(token)
        
        # Decode and verify JWT token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            # AWS Cognito access tokens don't have "aud" claim, skip audience validation
            # audience=APP_CLIENT_ID,
            issuer=f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}"
        )
        
        # Verify client_id manually since access tokens don't have "aud" claim
        token_client_id = payload.get("client_id")
        if token_client_id != APP_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: client_id mismatch. Expected {APP_CLIENT_ID}, got {token_client_id}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        username = payload.get("username") or payload.get("cognito:username")
        groups = payload.get("cognito:groups", [])
        email = payload.get("email", "")
        
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing username",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Map first group to access tier
        primary_group = groups[0] if groups else "public"
        access_tier = AccessTier.from_string(primary_group, default=True)

        return {
            "username": username,
            "email": email,
            "groups": groups,
            "access_tier": access_tier,
            "organisation_id": f"org-{username}",
            "token_valid": True,
            "token_type": payload.get("token_use", "access"),
            "client_id": payload.get("client_id"),  # AWS Cognito uses "client_id" not "aud"
            "issued_at": payload.get("iat"),
            "expires_at": payload.get("exp")
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "FRANK Simple API - AWS Cognito",
        "version": "1.0.0",
        "authentication": "AWS Cognito JWT",
        "endpoints": {
            "public": "/public",
            "observer": "/observer",
            "contributor": "/contributor",
            "partner": "/partner",
            "core_member": "/core_member",
            "auth_test": "/auth/test",
            "docs": "/docs",
            "health": "/health"
        },
        "aws_cognito": {
            "region": AWS_REGION,
            "user_pool_id": USER_POOL_ID,
            "app_client_id": APP_CLIENT_ID
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "frank-simple-api-aws-cognito",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aws_cognito": {
            "region": AWS_REGION,
            "user_pool_id": USER_POOL_ID,
            "configured": bool(USER_POOL_ID and APP_CLIENT_ID)
        }
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
    
    if not current_user["access_tier"].check_access_level(required_tier):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient access level. Required: {required_tier.value}, User has: {current_user['access_tier'].value}"
        )
    
    return {
        "message": "Welcome to the OBSERVER level endpoint",
        "access_level": "observer",
        "description": "This endpoint requires OBSERVER or higher access tier",
        "user_info": {
            "username": current_user["username"],
            "email": current_user["email"],
            "access_tier": current_user["access_tier"].value,
            "groups": current_user["groups"],
            "organisation_id": current_user["organisation_id"]
        },
        "data": {
            "observer_data": "This is basic threat intelligence for observers and above",
            "permissions": ["read_public_intel"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
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
            "email": current_user["email"],
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
            "email": current_user["email"],
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
            "email": current_user["email"],
            "access_tier": current_user["access_tier"].value,
            "groups": current_user["groups"],
            "organisation_id": current_user["organisation_id"]
        },
        "data": {
            "core_member_data": "This is the most sensitive information for core members only",
            "permissions": ["read_threat_intel", "submit_indicators", "access_iocs", "manage_feeds", "admin_access", "platform_management"],
            "exclusive_features": ["advanced_analytics", "custom_reports", "api_integrations", "user_management", "system_configuration"],
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
            "email": current_user["email"],
            "access_tier": current_user["access_tier"].value,
            "groups": current_user["groups"],
            "organisation_id": current_user["organisation_id"],
            "token_info": {
                "token_type": current_user["token_type"],
                "client_id": current_user["client_id"],
                "issued_at": current_user["issued_at"],
                "expires_at": current_user["expires_at"]
            },
            "permissions": {
                "can_access_public": True,
                "can_access_observer": current_user["access_tier"].check_access_level(AccessTier.OBSERVER),
                "can_access_contributor": current_user["access_tier"].check_access_level(AccessTier.CONTRIBUTOR),
                "can_access_partner": current_user["access_tier"].check_access_level(AccessTier.PARTNER),
                "can_access_core_member": current_user["access_tier"].check_access_level(AccessTier.CORE_MEMBER)
            }
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/auth/test")
async def test_auth():
    """
    Test authentication endpoint - demonstrates how to get tokens from AWS Cognito
    """
    return {
        "message": "Authentication test endpoint",
        "description": "Use this endpoint to test AWS Cognito authentication",
        "instructions": {
            "step_1": "Get a token using AWS CLI or boto3",
            "step_2": "Use the access_token in Authorization header",
            "aws_cli_example": f"aws cognito-idp admin-initiate-auth --user-pool-id {USER_POOL_ID} --client-id {APP_CLIENT_ID} --auth-flow ADMIN_USER_PASSWORD_AUTH --auth-parameters USERNAME=testuser_contributor,PASSWORD=YourPassword --region {AWS_REGION}",
            "header_format": "Authorization: Bearer <access_token>"
        },
        "aws_cognito_config": {
            "region": AWS_REGION,
            "user_pool_id": USER_POOL_ID,
            "app_client_id": APP_CLIENT_ID
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def load_config_from_file(config_file: str = "cognito-config.json"):
    """Load configuration from deployment output file"""
    global AWS_REGION, USER_POOL_ID, APP_CLIENT_ID, COGNITO_ENDPOINT
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        AWS_REGION = config.get("region", AWS_REGION)
        USER_POOL_ID = config.get("user_pool_id", "")
        APP_CLIENT_ID = config.get("app_client_id", "")
        COGNITO_ENDPOINT = config.get("cognito_endpoint", COGNITO_ENDPOINT)
        
        print(f"✅ Configuration loaded from {config_file}")
        return True
    except FileNotFoundError:
        print(f"⚠️  Configuration file {config_file} not found")
        return False
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in configuration file {config_file}")
        return False

def main():
    """Main function with command line argument support"""
    parser = argparse.ArgumentParser(description="FRANK Simple API with AWS Cognito")
    parser.add_argument("--endpoint", help="Cognito endpoint URL")
    parser.add_argument("--user-pool-id", help="Cognito User Pool ID")
    parser.add_argument("--app-client-id", help="Cognito App Client ID")
    parser.add_argument("--region", help="AWS Region", default="eu-central-1")
    parser.add_argument("--port", type=int, help="Port to run on", default=8001)
    parser.add_argument("--config", help="Configuration file", default="cognito-config.json")
    parser.add_argument("--token", help="Test with provided JWT token (for testing)")
    
    args = parser.parse_args()
    
    global AWS_REGION, USER_POOL_ID, APP_CLIENT_ID, COGNITO_ENDPOINT
    
    # Load configuration from file first
    load_config_from_file(args.config)
    
    # Override with command line arguments
    if args.region:
        AWS_REGION = args.region
    if args.user_pool_id:
        USER_POOL_ID = args.user_pool_id
    if args.app_client_id:
        APP_CLIENT_ID = args.app_client_id
    if args.endpoint:
        COGNITO_ENDPOINT = args.endpoint
    
    print(f"🚀 Starting FRANK Simple API with AWS Cognito")
    print(f"   Port: {args.port}")
    print(f"   Region: {AWS_REGION}")
    print(f"   User Pool ID: {USER_POOL_ID}")
    print(f"   App Client ID: {APP_CLIENT_ID}")
    
    if not USER_POOL_ID or not APP_CLIENT_ID:
        print("❌ Missing required configuration:")
        print("   - USER_POOL_ID")
        print("   - APP_CLIENT_ID")
        print("")
        print("Options:")
        print(f"1. Create {args.config} by running: ./deploy-cognito.sh")
        print("2. Set environment variables: USER_POOL_ID, APP_CLIENT_ID")
        print("3. Use command line arguments: --user-pool-id, --app-client-id")
        sys.exit(1)
    
    try:
        init_cognito_client()
    except Exception as e:
        print(f"❌ Failed to initialize Cognito client: {e}")
        sys.exit(1)
    
    if args.token:
        print(f"\n🧪 Testing with provided token: {args.token[:50]}...")
        # Simple token test could be added here
    
    print(f"\n📖 API Documentation: http://localhost:{args.port}/docs")
    print(f"🔗 Test endpoints:")
    print(f"   Public: http://localhost:{args.port}/public")
    print(f"   Auth Test: http://localhost:{args.port}/auth/test")
    print("")
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=args.port)

if __name__ == "__main__":
    main()