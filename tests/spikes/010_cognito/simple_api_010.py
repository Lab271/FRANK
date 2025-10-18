#!/usr/bin/env python3
"""
FRANK Platform - Cognito Authentication Spike - Simple API with Mock Cognito

Demonstrates FastAPI with JWT authentication using Mock Cognito service.
Shows how to implement role-based access control with different access tiers.

Three token validation [VALIDATION_STRATEGY] strategies are supported:
1. "server_first": Attempt server-side validation with Cognito first, then fall back to local JWT validation if the server is unavailable.
2. "local_only": Only perform local JWT validation, without contacting any Cognito server.
3. "server_only": Only accept tokens validated by the Cognito server; reject tokens if the server cannot be reached.

Key Features:
- AppConfig that can be configured via environment variables or command line arguments.
- FastAPI endpoints protected by access tier (OBSERVER, CONTRIBUTOR, PARTNER, CORE_MEMBER).
- External Cognito server validation (mock or AWS) with local JWT validation.
- Role mapping from Cognito groups to FRANK AccessTier enum.
- Health check and public endpoints.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import argparse
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import httpx
import jwt
from jwt import PyJWKClient
import uvicorn

import frank
from frank.core.enum import AccessTier

AWS_COGNITO_TIMEOUT = 10.0  # seconds

class AppConfig:
    """Configuration class for Simple API settings"""
    _instance: Optional['AppConfig'] = None
    
    def __init__(
        self,
        cognito_url: str,
        jwt_secret: str,
        jwt_algorithm: str,
        validation_strategy: str,
        region: str,
        environment: str,
        user_pool_id: str
    ):
        self.cognito_url = cognito_url
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.validation_strategy = validation_strategy
        self.region = region
        self.user_pool_id = user_pool_id
        self.environment = environment
        
        # Construct JWKS URL for local validation
        if self.environment == "aws":
            self.cognito_url = f"https://cognito-idp.{self.region}.amazonaws.com/"
        elif not self.cognito_url.endswith("/"):
            self.cognito_url += "/"
        self.jwks_url = f"{self.cognito_url}{self.user_pool_id}/.well-known/jwks.json"

        # Validate configuration
        if not self.cognito_url.startswith("http"): 
            raise ValueError(f"Invalid Cognito URL: {self.cognito_url}")    
        if self.validation_strategy not in ["server_first", "local_only", "server_only"]:
            raise ValueError(f"Invalid validation strategy: {self.validation_strategy}")
        if self.jwt_algorithm not in ["RS256", "HS256"]:
            raise ValueError(f"Unsupported JWT algorithm: {self.jwt_algorithm}")

    
    @classmethod
    def set_config(cls,
                   cognito_url: str = None,
                   jwt_secret: str = None,
                   jwt_algorithm: str = None,
                   validation_strategy: str = None,
                   region: str = None,
                   user_pool_id: str = None,
                   environment: str = None) -> "AppConfig":
        """Set singleton AppConfig instance, creating it from environment if needed"""
        
        # Priority order: passed parameters > environment variables > defaults
        cls._instance = cls(
            cognito_url=cognito_url or os.getenv("COGNITO_URL", "http://localhost:8100"),
            jwt_secret=jwt_secret or os.getenv("JWT_SECRET", "mock-cognito-secret-key"),
            jwt_algorithm=jwt_algorithm or os.getenv("JWT_ALGORITHM", "RS256"),
            validation_strategy=validation_strategy or os.getenv("VALIDATION_STRATEGY", "local_only"),
            region=region or os.getenv("REGION", "eu-west-1"),
            user_pool_id=user_pool_id or os.getenv("USER_POOL_ID", "eu-west-1_MOCKPOOL"),
            environment=environment or os.getenv("ENVIRONMENT", "mock")
        )
        return cls._instance

    @classmethod
    def get_config(cls) -> "AppConfig":
        """Get the singleton AppConfig instance"""
        if cls._instance is None:
            cls.set_config()
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
    return logging.getLogger("uvicorn")


# Role mapping now uses AccessTier.from_string() method for flexible group handling
# This maps Mock Cognito groups to FRANK AccessTier enum values
def get_access_tier_from_groups(groups: List[str]) -> AccessTier:
    """Convert user groups to AccessTier using from_string method"""
    if not groups:
        return AccessTier.PUBLIC
    
    # Use the first group and convert it using the from_string method
    primary_group = groups[0]
    return AccessTier.from_string(primary_group, default=True)

async def validate_token_locally(token: str) -> Dict[str, Any]:
    """Validate JWT token locally using JWKS (AWS Cognito compatible)"""
    current_config = get_config()
    
    try:
        if current_config.jwt_algorithm == "RS256":
            # Use JWKS for RS256 tokens (AWS Cognito style)
            jwks_client = PyJWKClient(current_config.jwks_url)
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False},  # Skip audience verification for mock
                issuer=f"https://cognito-idp.{current_config.region}.amazonaws.com/{current_config.user_pool_id}"
            )
        else:
            # Fallback to HS256 for backwards compatibility
            payload = jwt.decode(
                token,
                current_config.jwt_secret,
                algorithms=[current_config.jwt_algorithm],
                options={"verify_aud": False}
            )
            
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
    
    username = payload.get("username")
    groups = payload.get("cognito:groups", [])
    # Extract organization from custom attribute
    organization = payload.get("custom:organization") or payload.get("organization")
    
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing username",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_tier = get_access_tier_from_groups(groups)
    
    return {
        "username": username,
        "groups": groups,
        "access_tier": access_tier,
        "organization": organization,
        "organisation_id": organization or f"org-{username}",  # Use organization if available, fallback to username-based
        "token_valid": True,
        "validation_source": "local_jwt"
    }

async def validate_token_with_server(token: str) -> Optional[Dict[str, Any]]:
    """Validate token with Cognito server (mock or AWS)"""
    current_config = get_config()
    logger = logging.getLogger("uvicorn")

    logger.debug(f"Using {current_config.environment} Cognito GetUser API at {current_config.cognito_url}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            current_config.cognito_url,
            headers={
                "X-Amz-Target": "AWSCognitoIdentityProviderService.GetUser",
                "Content-Type": "application/x-amz-json-1.1"
            },
            json={"AccessToken": token},
            timeout=AWS_COGNITO_TIMEOUT
        )
        
        if response.status_code == 200:
            user_info = response.json()
            username = user_info.get("Username")
            
            if username:             
                logger.info(f"Token validated via {current_config.environment} Cognito GetUser API for user: {username}")

                return {
                    "username": username,
                    "token_valid": True,
                    "validation_source": f"{current_config.environment}-cognito-getuser"
                }

        logger.warning(f"{current_config.environment} Cognito GetUser failed with status {response.status_code}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed: Could not validate with Cognito server",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application
    
    Args:
        config: Application configuration. If None, will use singleton instance.
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    logger = logging.getLogger("uvicorn")

    # Security scheme for this app instance
    security = HTTPBearer()
    
    async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
        """
        Extract user information from JWT token by calling the Cognito server for validation.
        This makes a real call to either mock Cognito or AWS Cognito for token validation.
        """
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = credentials.credentials
        current_config = get_config() 

        try:
            # Try server-side validation first (for server_first and server_only strategies)
            if current_config.validation_strategy != "local_only":
                server_data = await validate_token_with_server(token)
                if server_data:
                    # For server validation, we still need to get groups from JWT
                    # because GetUser API doesn't return group memberships
                    local_data = await validate_token_locally(token)
                    local_data["validation_source"] = server_data["validation_source"]
                    # Combine server validation with local group extraction
                    return local_data

                # If server validation fails, handle based on strategy
                if current_config.validation_strategy == "server_only":
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token validation failed: Could not validate with Cognito server",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            
            # Local validation for local_only strategy or server_first fallback
            return await validate_token_locally(token)
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not connect to Cognito service",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Cognito GetUser request timed out",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # FastAPI app with OpenAPI documentation
    app = FastAPI(
        title="FRANK Simple API",
        description="Simple API demonstrating role-based access control with Mock Cognito authentication",
        version=frank.__version__,
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
    
    logger = logging.getLogger("uvicorn")

    # API Endpoints
    @app.get("/")
    async def root():
        """Root endpoint with API information"""
        current_config = get_config()
        return {
            "service": "FRANK Simple API",
            "version": frank.__version__,
            "authentication": "Cognito JWT",
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
            "cognito_url": current_config.cognito_url,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        current_config = get_config()
        return {
            "status": "healthy",
            "service": "frank-simple-api",
            "version": frank.__version__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cognito_url": current_config.cognito_url
        }

    @app.get("/config")
    async def get_current_config():
        """Get current configuration (for debugging)"""
        current_config = get_config()
        return {
            "environment": current_config.environment,
            "region": current_config.region,
            "user_pool_id": current_config.user_pool_id,
            "cognito_url": current_config.cognito_url,
            "jwt_algorithm": current_config.jwt_algorithm,
            "validation_strategy": current_config.validation_strategy,
            "jwt_secret_length": len(current_config.jwt_secret),  # Don't expose the actual secret
            "timestamp": datetime.now(timezone.utc).isoformat()
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
                "service_version": frank.__version__
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
            "access_level": "observer",
            "description": "This endpoint requires OBSERVER or higher access tier",
            "user_info": {
                "username": current_user["username"],
                "access_tier": current_user["access_tier"].value,
                "groups": current_user["groups"],
                "organization": current_user.get("organization"),
                "organisation_id": current_user["organisation_id"]
            },
            "data": {
                "observer_data": "Data accessible to observer level and above",
                "permissions": ["read_threat_intel"],
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
                "access_tier": current_user["access_tier"].value,
                "groups": current_user["groups"],
                "organization": current_user.get("organization"),
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
                "access_tier": current_user["access_tier"].value,
                "groups": current_user["groups"],
                "organization": current_user.get("organization"),
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
                "access_tier": current_user["access_tier"].value,
                "groups": current_user["groups"],
                "organization": current_user.get("organization"),
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
            "user_info": {
                "username": current_user["username"],
                "access_tier": current_user["access_tier"].value,
                "groups": current_user["groups"],
                "organization": current_user.get("organization"),
                "organisation_id": current_user["organisation_id"],
                "permissions": {
                    "can_access_public": True,
                    "can_access_contributor": current_user["access_tier"].check_access_level(AccessTier.CONTRIBUTOR),
                    "can_access_partner": current_user["access_tier"].check_access_level(AccessTier.PARTNER),
                    "can_access_core": current_user["access_tier"].check_access_level(AccessTier.CORE_MEMBER)
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    logger.debug("FRANK Simple API application created successfully")
    return app


def main():
    """
    Main function with argparse for uvicorn configuration
    """
    CURRENT_MODULE = Path(__file__).stem  # Filename without extension: "simple_api_011"

    parser = argparse.ArgumentParser(description="FRANK Simple API with Cognito authentication")
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
    
    # Configuration options
    parser.add_argument(
        "--cognito-url",
        type=str,
        default=os.getenv("COGNITO_URL", "http://localhost:8100"),
        help="Cognito service URL (default: http://localhost:8100 [mock] or COGNITO_URL)"
    )
    parser.add_argument(
        "--jwt-secret",
        type=str,
        default=os.getenv("JWT_SECRET", "mock-cognito-secret-key"),
        help="JWT secret key for token validation (default: mock-cognito-secret-key or JWT_SECRET)"
    )
    parser.add_argument(
        "--jwt-algorithm",
        type=str,
        default=os.getenv("JWT_ALGORITHM", "RS256"),
        help="JWT algorithm for token validation (default: RS256 or JWT_ALGORITHM)"
    )
    parser.add_argument(
        "--region",
        type=str,
        default=os.getenv("REGION", "eu-west-1"),
        help="AWS region (default: eu-west-1 or REGION)"
    )
    parser.add_argument(
        "--user-pool-id",
        type=str,
        default=os.getenv("USER_POOL_ID", "eu-west-1_MOCKPOOL"),
        help="Cognito User Pool ID (default: eu-west-1_MOCKPOOL or USER_POOL_ID)"
    )
    parser.add_argument(
        "--environment",
        type=str,
        default=os.getenv("ENVIRONMENT", "mock"),
        choices=["mock", "aws"],
        help="Environment (default: mock or ENVIRONMENT)"
    )
    parser.add_argument(
        "--validation-strategy",
        type=str,
        choices=["server_first", "local_only"],
        default=os.getenv("VALIDATION_STRATEGY", "local_only"),
        help="Token validation strategy (default: local_only or VALIDATION_STRATEGY)"
    )

    args = parser.parse_args()
    
    # Set environment variables for uvicorn worker processes
    # This ensures configuration survives process restarts and reloads
    os.environ["COGNITO_URL"] = args.cognito_url
    os.environ["JWT_SECRET"] = args.jwt_secret
    os.environ["JWT_ALGORITHM"] = args.jwt_algorithm
    os.environ["VALIDATION_STRATEGY"] = args.validation_strategy
    os.environ["REGION"] = args.region
    os.environ["ENVIRONMENT"] = args.environment
    os.environ["USER_POOL_ID"] = args.user_pool_id
    
    # Create configuration from command line arguments and set as singleton
    config = AppConfig.get_config()
    
    # Configure logging level
    logger = setup_logging()
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    logger.info(f"Starting FRANK Simple API on {args.host}:{args.port}")
    logger.info(f"Version: {frank.__version__}")
    logger.info(f"Reload enabled: {args.reload}")
    logger.info(f"Log level: {args.log_level}")
    logger.info(f"Environment: {config.environment}")
    logger.info(f"Validation strategy: {config.validation_strategy}")
    logger.info(f"JWT Algorithm: {config.jwt_algorithm}")
    logger.info(f"JWT Secret: {config.jwt_secret[:4]}... (length: {len(config.jwt_secret)})")
    if config.validation_strategy != "local_only": 
        logger.info(f"User Pool ID: {config.user_pool_id}")
        logger.info(f"Cognito URL: {config.cognito_url}")
        logger.info(f"JWKS URL: {config.jwks_url}")
        logger.info(f"Region: {config.region}")

    # Run uvicorn server
    uvicorn.run(
        f"{CURRENT_MODULE}:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
        log_level=args.log_level
    )


if __name__ == "__main__":  # pragma: no cover
    main()