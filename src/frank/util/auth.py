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
        return {"user_id": user["sub"], "organisation": user.get("custom:organisation")}

Dependencies:
- FastAPI for dependency injection and HTTP exception handling
- httpx for asynchronous HTTP requests to authentication services
- PyJWT for local JWT token validation and decoding
- boto3/aioboto3 for AWS Cognito integration

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Any, Dict, Optional, List
import time
import hashlib

import httpx
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient

from frank.core import gen_stix_id
from frank.core.enum import AccessTier
from frank.util.http_exceptions import ServiceUnavailableException, GatewayTimeoutException
from frank.util.http_exceptions import UnauthorizedException
from frank.util.logger import get_module_logger


AWS_COGNITO_TIMEOUT = 10.0  # seconds
SERVER_VALIDATION_CACHE_TTL = 300  # 5 minutes cache for server validation results



# Security scheme for Bearer token authentication
security = HTTPBearer()


class CognitoValidator:
    """
    Cognito token validator supporting multiple validation strategies.
    
    Performance optimization: The PyJWKClient is cached as an instance variable
    to avoid creating a new client on every request. PyJWKClient internally
    caches the JWKS keys with a configurable TTL (default: 5 minutes).
    """ 

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config
        
        # Use the utility function to get a properly configured DEBUG logger
        self.logger = get_module_logger("frank.auth")
            
        self.cognito_url = self.config.get("cognito_url", "http://localhost:8100/")
        self.user_pool_id = self.config.get("user_pool_id", "eu-west-1_MOCKPOOL")
        self.jwks_url = f"{self.cognito_url}{self.user_pool_id}/.well-known/jwks.json"
        
        # Cache PyJWKClient instance to avoid creating new client on every request
        # PyJWKClient internally caches keys with TTL (default: 300 seconds)
        # This reduces network calls and improves performance
        self._jwks_client: Optional[PyJWKClient] = None
        
        # Cache for server validation results to avoid repeated Cognito GetUser API calls
        # Key: token hash, Value: (result dict, expiration timestamp)
        self._server_validation_cache: Dict[str, tuple[Dict[str, Any], float]] = {}
        self._cache_ttl = config.get('server_validation_cache_ttl', SERVER_VALIDATION_CACHE_TTL)
        
        self.logger.debug(f"Initialized CognitoValidator with JWKS URL: {self.jwks_url}")
        self.logger.debug(f"Server validation cache TTL: {self._cache_ttl} seconds")

    def _get_token_hash(self, token: str) -> str:
        """Generate a hash of the token for cache key"""
        return hashlib.sha256(token.encode()).hexdigest()[:16]

    def _get_from_cache(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Get validation result from cache if not expired"""
        if token_hash in self._server_validation_cache:
            result, expiration = self._server_validation_cache[token_hash]
            if time.time() < expiration:
                self.logger.debug(f"Server validation cache hit for token hash: {token_hash}")
                return result.copy()  # Return a copy to prevent mutation
            else:
                # Expired, remove from cache
                del self._server_validation_cache[token_hash]
                self.logger.debug(f"Server validation cache expired for token hash: {token_hash}")
        return None

    def _set_in_cache(self, token_hash: str, result: Dict[str, Any]) -> None:
        """Store validation result in cache with TTL"""
        expiration = time.time() + self._cache_ttl
        self._server_validation_cache[token_hash] = (result.copy(), expiration)
        self.logger.debug(f"Stored server validation result in cache for token hash: {token_hash}")
        
        # Clean up expired entries periodically (every 100 insertions)
        if len(self._server_validation_cache) % 100 == 0:
            self._cleanup_expired_cache()

    def _cleanup_expired_cache(self) -> None:
        """Remove expired entries from cache"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, expiration) in self._server_validation_cache.items()
            if expiration < current_time
        ]
        for key in expired_keys:
            del self._server_validation_cache[key]
        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def invalidate_server_validation_cache(self) -> None:
        """Manually invalidate all server validation cache entries"""
        count = len(self._server_validation_cache)
        self._server_validation_cache.clear()
        self.logger.info(f"Manually invalidated {count} server validation cache entries")

    def invalidate_jwks_cache(self) -> None:
        """
        Manually invalidate the JWKS client cache.
        
        This forces the next token validation to create a new PyJWKClient instance
        and fetch fresh keys from the JWKS endpoint. Useful when:
        - Key rotation is detected
        - Connection to JWKS endpoint was temporarily unavailable
        - Testing or troubleshooting authentication issues
        
        Note: PyJWKClient already handles automatic cache expiration based on
        the configured lifespan (default: 300 seconds), so manual invalidation
        is typically not needed during normal operation.
        """
        if self._jwks_client is not None:
            self.logger.info("Manually invalidating JWKS client cache")
            self._jwks_client = None

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
                    
                    # Merge server data with local data
                    # Server provides: username, organisation, user_attributes (authoritative source)
                    # Local provides: groups, access_level (not available from GetUser API)
                    local_data["validation_source"] = server_data["validation_source"]

                    # Use server organisation if available (more authoritative than JWT)
                    if server_data.get("organisation"):
                        local_data["organisation"] = server_data["organisation"]
                        local_data["organisation_id"] = server_data["organisation_id"]
                        self.logger.debug(f"Using organisation from server: {server_data['organisation']}")

                    # Include user attributes from server for potential future use
                    if server_data.get("user_attributes"):
                        local_data["user_attributes"] = server_data["user_attributes"]
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
                # Use cached JWKS client to avoid creating new client on every request
                # This significantly improves performance by reducing network calls
                if self._jwks_client is None:
                    # Initialize client on first use with configurable cache TTL
                    # Default TTL is 300 seconds (5 minutes) for JWKS key caching
                    self._jwks_client = PyJWKClient(
                        self.jwks_url,
                        cache_keys=True,  # Enable key caching
                        lifespan=300      # Cache keys for 5 minutes
                    )
                    self.logger.debug(f"Created new PyJWKClient for {self.jwks_url}")
                
                signing_key = self._jwks_client.get_signing_key_from_jwt(token)
                self.logger.debug(f"Using cached JWKS client for local JWT validation")
                
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
        # Extract organisation from custom attribute
        organisation = payload.get("custom:organisation") or payload.get("organisation")

        if not username:
            raise UnauthorizedException(detail="Invalid token: missing username")

        access_tier = AccessTier.get_access_tier_from_groups(groups)
        
        return {
            "username": username,
            "user_id": gen_stix_id("user", username),
            "groups": groups,
            "access_level": access_tier,
            "organisation": organisation,
            "organisation_id": gen_stix_id("org", organisation),
            "request_id": gen_stix_id("req"),
            "token_valid": True,
            "validation_source": "local_jwt"
        }
        
    async def validate_token_with_server(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate token with Cognito server (mock or AWS) and extract user attributes.
        
        Performance optimization: Results are cached with TTL to avoid repeated API calls
        for the same token. Cache TTL defaults to 5 minutes but can be configured.
        """
        
        # Check cache first
        token_hash = self._get_token_hash(token)
        cached_result = self._get_from_cache(token_hash)
        if cached_result is not None:
            cached_result["validation_source"] = f"{self.config['environment']}-cognito-getuser-cached"
            return cached_result

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

                    # Extract user attributes from the UserAttributes array
                    user_attributes = {}
                    for attr in user_info.get("UserAttributes", []):
                        user_attributes[attr["Name"]] = attr["Value"]

                    # Extract organisation from custom:organisation attribute
                    organisation = user_attributes.get("custom:organisation") or user_attributes.get("organisation")

                    self.logger.debug(f"Extracted attributes from GetUser: {user_attributes.keys()}")
                    if organisation:
                        self.logger.debug(f"Found organisation from GetUser: {organisation}")

                    result = {
                        "username": username,
                        "user_id": gen_stix_id("user", username),
                        "organisation": organisation,
                        "organisation_id": gen_stix_id("org", organisation) if organisation else None,
                        "token_valid": True,
                        "validation_source": f"{self.config['environment']}-cognito-getuser",
                        "user_attributes": user_attributes  # Include all attributes for potential future use
                    }
                    
                    # Store in cache for future requests
                    self._set_in_cache(token_hash, result)
                    
                    return result

            self.logger.warning(f"{self.config['environment']} Cognito GetUser failed with status {response.status_code}")
            raise UnauthorizedException(detail="Token validation failed: Could not validate with Cognito server")
