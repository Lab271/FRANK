"""
FRANK Platform - Authentication Module
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

Generic authentication module providing JWT token validation and user management
for the FRANK platform. Supports multiple validation strategies and authentication
backends including AWS Cognito and local JWT validation.

Key Features:
- JWT token validation with configurable strategies (local_only, server_first, server_only)
- AWS Cognito integration for server-side token validation
- User information extraction from JWT claims
- Group membership and role-based access control
- Flexible authentication backends for different deployment environments
- Comprehensive error handling with proper HTTP status codes

Authentication Strategies:
- local_only: Validate JWT tokens locally using public keys
- server_first: Try server validation first, fallback to local validation
- server_only: Only accept server-validated tokens (strict mode)

Supported Backends:
- AWS Cognito User Pools
- LocalStack Cognito emulation for development
- Custom JWT providers (extensible)

Usage:
    from frank.util.auth import get_current_user
    
    @app.get("/protected")
    async def protected_endpoint(user: dict = Depends(get_current_user)):
        return {"user_id": user["sub"], "organization": user.get("custom:organization")}

Dependencies:
- FastAPI for dependency injection and HTTP exception handling
- httpx for asynchronous HTTP requests to authentication services
- PyJWT for local JWT token validation and decoding
- boto3/aioboto3 for AWS Cognito integration

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Any, Dict, Optional, List

import httpx
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient

from frank.core import gen_stix_id
from frank.core.enum import AccessTier
from frank.util.http_exceptions import ServiceUnavailableException, GatewayTimeoutException
from frank.util.http_exceptions import UnauthorizedException, UnauthenticatedException
from frank.util.logger import get_module_logger


AWS_COGNITO_TIMEOUT = 10.0  # seconds



# Security scheme for Bearer token authentication
security = HTTPBearer()


class CognitoValidator:
    """
    Cognito token validator supporting multiple validation strategies.
    """ 

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config
        
        # Use the utility function to get a properly configured DEBUG logger
        self.logger = get_module_logger("frank.auth")
            
        self.cognito_url = self.config.get("cognito_url", "http://localhost:8100/")
        self.user_pool_id = self.config.get("user_pool_id", "eu-west-1_MOCKPOOL")
        self.jwks_url = f"{self.cognito_url}{self.user_pool_id}/.well-known/jwks.json"
        self.logger.debug(f"Initialized CognitoValidator with JWKS URL: {self.jwks_url}")


    def verify_token(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
        """
        Verify Bearer token authentication
        
        For testing purposes, accepts 'valid-token' as a valid token.
        In production, this would validate against a real authentication system.
        """
        if credentials.credentials != "valid-token":
            raise UnauthenticatedException(detail="Invalid authentication token")
        return {
            "username": credentials.credentials,
            "token_valid": True,
            "validation_source": "mock"
        }

    # Role mapping now uses AccessTier.from_string() method for flexible group handling
    # This maps Mock Cognito groups to FRANK AccessTier enum values
    def get_access_tier_from_groups(self, groups: List[str]) -> AccessTier:
        """Convert user groups to AccessTier using from_string method"""
        if not groups:
            return AccessTier.PUBLIC
    
        # Use the first group and convert it using the from_string method
        primary_group = groups[0]
        return AccessTier.from_string(primary_group, default=True)

    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
        """
        Extract user information from JWT token by calling the Cognito server for validation.
        This makes a real call to either mock Cognito or AWS Cognito for token validation.
        """
        if credentials is None:
            raise UnauthorizedException(detail="Authentication required")

        token = credentials.credentials

        try:
            local_data = await self.validate_token_locally(token)
            # Try server-side validation first (for server_first and server_only strategies)
            if self.config['validation_strategy'] != "local_only":
                server_data = await self.validate_token_with_server(token)
                if server_data:
                    if server_data["username"] != local_data["username"]:
                        raise UnauthorizedException(detail="Token validation failed: Username mismatch between local and server validation")    
                    # For server validation, we still need to get groups from JWT
                    # because GetUser API doesn't return group memberships
                    local_data["validation_source"] = server_data["validation_source"]
                    # Combine server validation with local group extraction
                else:
                    raise UnauthorizedException(detail="Token validation failed: Could not validate with Cognito server")
            return local_data
        except httpx.ConnectError:
            raise ServiceUnavailableException(detail="Could not connect to Cognito service")
        except httpx.TimeoutException:
            raise GatewayTimeoutException(detail="Cognito GetUser request timed out")   
            
    async def validate_token_locally(self, token: str) -> Dict[str, Any]:
        """Validate JWT token locally using JWKS (AWS Cognito compatible)"""
       
        try:
            if self.config['jwt_algorithm'] == "RS256":
                # Use JWKS for RS256 tokens (AWS Cognito style)
                jwks_client = PyJWKClient(self.jwks_url)
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                self.logger.debug(f"Using JWKS from {self.jwks_url} for local JWT validation")
                
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256"],
                    options={"verify_aud": False},  # Skip audience verification for mock
                    issuer=f"https://cognito-idp.{self.config['region']}.amazonaws.com/{self.config['user_pool_id']}"
                )
                self.logger.debug(f"JWT payload successfully decoded with RS256: {payload}")
            else:
                # Fallback to HS256 for backwards compatibility
                payload = jwt.decode(
                    token,
                    self.config['jwt_secret'],
                    algorithms=[self.config['jwt_algorithm']],
                    options={"verify_aud": False}
                )

        except jwt.ExpiredSignatureError:
            raise UnauthorizedException(detail="Token has expired")
        except jwt.InvalidTokenError as e:
            raise UnauthorizedException(detail=f"Invalid token: {str(e)}")
        
        username = payload.get("username")
        groups = payload.get("cognito:groups", [])
        # Extract organization from custom attribute
        organization = payload.get("custom:organization") or payload.get("organization")
        
        if not username:
            raise UnauthorizedException(detail="Invalid token: missing username")

        access_tier = self.get_access_tier_from_groups(groups)
        
        return {
            "username": username,
            "user_id": gen_stix_id("user", username),
            "groups": groups,
            "access_level": access_tier,
            "organization": organization,
            "organisation_id": gen_stix_id("org", organization),
            "request_id": gen_stix_id("req"),
            "token_valid": True,
            "validation_source": "local_jwt"
        }
        
    async def validate_token_with_server(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate token with Cognito server (mock or AWS)"""

        self.logger.debug(f"Using {self.config['environment']} Cognito GetUser API at {self.config['cognito_url']}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.config['cognito_url'],
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
                    self.logger.info(f"Token validated via {self.config['environment']} Cognito GetUser API for user: {username}")

                    return {
                        "username": username,
                        "user_id": gen_stix_id("user", username),
                        "token_valid": True,
                        "validation_source": f"{self.config['environment']}-cognito-getuser"
                    }

            self.logger.warning(f"{self.config['environment']} Cognito GetUser failed with status {response.status_code}")
            raise UnauthorizedException(detail="Token validation failed: Could not validate with Cognito server")
