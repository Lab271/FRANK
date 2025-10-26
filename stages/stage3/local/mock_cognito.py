#!/usr/bin/env python3
"""
FRANK Platform - Cognito Authentication Spike - Mock Cognito Service

Simulates AWS Cognito authentication flows for local development.
This enables rapid authentication pattern development without AWS dependencies.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0

COMPARISON WITH COGNITO-LOCAL (https://github.com/jagregory/cognito-local):
==========================================================================

Our Mock Cognito implements a MINIMAL subset focused on authentication patterns:

✅ IMPLEMENTED IN OUR MOCK:
- Basic user authentication (username/password)
- JWT token generation (access, id, refresh tokens)
- JWT token validation and verification  
- User info retrieval from tokens
- Role-based group membership (observer, contributor, partner, core_member)
- Health check endpoint
- AWS CLI compatibility via InitiateAuth and AdminInitiateAuth
- AWS Cognito API action-based routing with X-Amz-Target header

❌ NOT IMPLEMENTED (Available in cognito-local):
- User Pool management (CreateUserPool, DeleteUserPool, DescribeUserPool)
- App Client management (CreateUserPoolClient, DeleteUserPoolClient)
- User management (AdminCreateUser, AdminDeleteUser, SignUp, ConfirmSignUp)
- Password operations (ForgotPassword, ChangePassword, AdminSetUserPassword)
- Group management (CreateGroup, DeleteGroup, AdminAddUserToGroup)
- User attribute operations (UpdateUserAttributes, GetUserAttributeVerificationCode)
- Lambda triggers (CustomMessage, PostAuthentication, PreSignUp, etc.)
- MFA support (SMS, TOTP, Software Token)
- OAuth flows and OIDC support
- Advanced token operations (RevokeToken, RespondToAuthChallenge)
- User pool configuration and policies
- Email verification and confirmation codes

AUTHENTICATION FLOW COMPARISON:
- cognito-local: Full AWS Cognito API compatibility (AdminInitiateAuth, etc.)
- Our Mock: Both simplified REST endpoints (/auth/login) AND AWS API compatibility (InitiateAuth)

JWT TOKEN CLAIMS COMPATIBILITY:
✅ Our tokens include standard claims that match Cognito patterns:
- username: User identifier
- cognito:groups: User role groups
- token_use: Token type (access/id/refresh)
- iat/exp: Issued at / expiration timestamps
- aud/iss: Audience / issuer claims

DEVELOPMENT FOCUS:
Our mock prioritizes learning core authentication concepts over full API compatibility:
- Simple authentication flow testing
- JWT token handling patterns
- Role-based access control validation
- Easy integration with FastAPI applications

For production or advanced testing, consider using:
- Real AWS Cognito for cloud deployments
- cognito-local for comprehensive local testing (requires more setup)
- Our mock for rapid authentication pattern development and learning
"""

import argparse
import logging
import time
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone

import uvicorn
import jwt
import base64
import json
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from fastapi import FastAPI, HTTPException, Depends, Request, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import frank

# Custom AWS-style exception for Cognito API compatibility
class AWSCognitoException(Exception):
    def __init__(self, error_type: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.error_type = error_type
        self.message = message
        self.status_code = status_code
        super().__init__(message)


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
logger = logging.getLogger("mock_cognito")

class AppConfig:
    """Configuration class for Simple API settings"""
    _instance: Optional['AppConfig'] = None

    def __init__(self,
        jwt_secret: str,
        jwt_algorithm: str,
        user_pool_id: str,
        client_id: str,
        region: str
    ):
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.region = region
        
        # Generate RSA key pair for RS256 if needed
        if jwt_algorithm == "RS256":
            self._generate_rsa_keys()
        else:
            self.private_key = None
            self.public_key = None
            self.jwks = None
    
    def _generate_rsa_keys(self):
        """Generate RSA key pair for JWT signing"""
        # Generate private key
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Get public key
        self.public_key = self.private_key.public_key()
        
        # Generate JWKS (JSON Web Key Set)
        public_numbers = self.public_key.public_numbers()
        
        # Convert to base64url-encoded strings
        def int_to_base64url(value):
            """Convert integer to base64url string"""
            # Convert to bytes (big endian)
            byte_length = (value.bit_length() + 7) // 8
            value_bytes = value.to_bytes(byte_length, 'big')
            # Base64url encode (no padding)
            return base64.urlsafe_b64encode(value_bytes).rstrip(b'=').decode('ascii')
        
        n = int_to_base64url(public_numbers.n)
        e = int_to_base64url(public_numbers.e)
        
        # Create JWKS
        self.jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "kid": "mock-cognito-key-1",
                    "alg": "RS256",
                    "n": n,
                    "e": e
                }
            ]
        }
    
    def get_signing_key(self):
        """Get the key for JWT signing"""
        if self.jwt_algorithm == "RS256":
            return self.private_key
        else:
            return self.jwt_secret
    
    def get_verification_key(self):
        """Get the key for JWT verification"""
        if self.jwt_algorithm == "RS256":
            return self.public_key
        else:
            return self.jwt_secret

    @classmethod
    def set_config(cls, 
                   jwt_secret: str = None, 
                   jwt_algorithm: str = None,
                   user_pool_id: str = None,
                   client_id: str = None,
                   region: str = None) -> "AppConfig":
        """Set singleton AppConfig instance, creating it from environment if needed"""
        cls._instance = cls(
            jwt_secret=jwt_secret or os.getenv("JWT_SECRET", "mock-cognito-secret-key"),
            jwt_algorithm=jwt_algorithm or os.getenv("JWT_ALGORITHM", "RS256"),
            user_pool_id=user_pool_id or os.getenv("USER_POOL_ID", "eu-west-1_MOCKPOOL"),
            client_id=client_id or os.getenv("CLIENT_ID", "mock-client-id-123456"),
            region=region or os.getenv("REGION", "eu-west-1")
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



# In-memory user store (simulates Cognito User Pool)
USERS_DB = {
    "testuser_observer": {
        "username": "testuser_observer",
        "password": "TempPass123!",
        "email": "observer@example.com",
        "groups": ["observer"],
        "organisation": "acme-corp",
        "enabled": True,
        "user_status": "CONFIRMED"
    },
    "testuser_contributor": {
        "username": "testuser_contributor", 
        "password": "TempPass123!",
        "email": "contributor@example.com",
        "groups": ["contributor"],
        "organisation": "cyber-security-inc",
        "enabled": True,
        "user_status": "CONFIRMED"
    },
    "testuser_partner": {
        "username": "testuser_partner", 
        "password": "TempPass123!",
        "email": "partner@example.com",
        "groups": ["partner"],
        "organisation": "threat-intel-partners",
        "enabled": True,
        "user_status": "CONFIRMED"
    },
    "testuser_core_member": {
        "username": "testuser_core_member", 
        "password": "TempPass123!",
        "email": "core_member@example.com",
        "groups": ["core_member"],
        "organisation": "frank-platform",
        "enabled": True,
        "user_status": "CONFIRMED"
    }
}

# Request/Response Models
class AuthRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    id_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600

class UserInfo(BaseModel):
    username: str
    email: str
    groups: List[str]


def create_jwt_token(username: str, groups: List[str], token_type: str = "access") -> str:
    """Create a JWT token with user information matching Cognito format"""
    now = datetime.now(timezone.utc)
    current_config = AppConfig.get_config()

    payload = {
        "sub": username,  # Cognito uses 'sub' for user identifier
        "cognito:groups": groups,
        "token_use": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "client_id": current_config.client_id,
        "username": username,
        "iss": f"https://cognito-idp.{current_config.region}.amazonaws.com/{current_config.user_pool_id}"
    }
    
    # Add additional claims for ID tokens
    if token_type == "id":
        user = USERS_DB[username]
        payload["email"] = user["email"]
        payload["email_verified"] = True
        payload["organisation"] = user["organisation"]
        payload["aud"] = current_config.client_id
    
    # Add kid (key ID) for RS256
    if current_config.jwt_algorithm == "RS256":
        headers = {"kid": "mock-cognito-key-1"}
        return jwt.encode(payload, current_config.get_signing_key(), algorithm=current_config.jwt_algorithm, headers=headers)
    else:
        return jwt.encode(payload, current_config.get_signing_key(), algorithm=current_config.jwt_algorithm)


def verify_jwt_token(token: str) -> dict:
    """Verify and decode JWT token"""
    current_config = AppConfig.get_config()

    try:
        # Decode without audience verification for mock service simplicity
        payload = jwt.decode(
            token, 
            current_config.get_verification_key(), 
            algorithms=[current_config.jwt_algorithm], 
            options={"verify_aud": False}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def handle_cognito_action(action: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Route requests based on AWS Cognito action"""
    logger.info(f"Handling Cognito action: {action}")
    
    if action == "InitiateAuth":
        return handle_initiate_auth(body)
    elif action == "AdminInitiateAuth":
        return handle_admin_initiate_auth(body)
    elif action == "GetUser":
        return handle_get_user(body)
    elif action == "RespondToAuthChallenge":
        return handle_respond_to_auth_challenge(body)
    elif action == "GlobalSignOut":
        return handle_global_sign_out(body)
    else:
        raise AWSCognitoException(
            "InvalidParameterException",
            f"Unknown operation: {action}"
        )


def handle_initiate_auth(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle InitiateAuth request"""
    auth_flow = body.get("AuthFlow")
    auth_parameters = body.get("AuthParameters", {})
    client_id = body.get("ClientId")
    
    logger.info(f"InitiateAuth: AuthFlow={auth_flow}, ClientId={client_id}")
    
    if auth_flow != "USER_PASSWORD_AUTH":
        raise AWSCognitoException(
            "InvalidParameterException",
            f"Unsupported auth flow: {auth_flow}"
        )
    
    username = auth_parameters.get("USERNAME")
    password = auth_parameters.get("PASSWORD")
    
    if not username or not password:
        raise AWSCognitoException(
            "InvalidParameterException",
            "USERNAME and PASSWORD required in AuthParameters"
        )
    
    # Validate credentials
    if username not in USERS_DB:
        logger.warning(f"InitiateAuth failed: User not found: {username}")
        raise AWSCognitoException(
            "UserNotFoundException", 
            "User does not exist"
        )
    
    user = USERS_DB[username]
    
    if not user["enabled"]:
        logger.warning(f"InitiateAuth failed: User account disabled: {username}")
        raise AWSCognitoException(
            "NotAuthorizedException",
            "User is disabled"
        )
    
    if user["password"] != password:
        logger.warning(f"InitiateAuth failed: Invalid password for user: {username}")
        # AWS Cognito returns NotAuthorizedException for invalid passwords
        raise AWSCognitoException(
            "NotAuthorizedException",
            "Incorrect username or password"
        )
    
    # Generate tokens
    groups = user["groups"]
    access_token = create_jwt_token(username, groups, "access")
    id_token = create_jwt_token(username, groups, "id")
    refresh_token = create_jwt_token(username, groups, "refresh")
    
    logger.info(f"InitiateAuth successful for user: {username} with groups: {groups}")
    
    return {
        "AuthenticationResult": {
            "AccessToken": access_token,
            "IdToken": id_token,
            "RefreshToken": refresh_token,
            "TokenType": "Bearer",
            "ExpiresIn": 3600
        },
        "ChallengeParameters": {}
    }


def handle_admin_initiate_auth(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle AdminInitiateAuth request (same logic as InitiateAuth for mock)"""
    logger.info("AdminInitiateAuth called - delegating to InitiateAuth logic")
    return handle_initiate_auth(body)


def handle_get_user(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GetUser request"""
    access_token = body.get("AccessToken")
    current_config = AppConfig.get_config()
    
    if not access_token:
        raise AWSCognitoException(
            "InvalidParameterException",
            "AccessToken required"
        )
    
    try:
        payload = jwt.decode(
            access_token,
            current_config.get_verification_key(),
            algorithms=[current_config.jwt_algorithm],
            options={"verify_aud": False}
        )
        username = payload.get("username") or payload.get("sub")
        
        if username not in USERS_DB:
            raise AWSCognitoException(
                "UserNotFoundException",
                "User not found"
            )
        
        user = USERS_DB[username]
        
        logger.info(f"GetUser successful for user: {username}")
        
        # Convert groups list to comma-separated string for AWS compatibility
        groups_str = ",".join(user["groups"])
        
        return {
            "Username": username,
            "UserAttributes": [
                {"Name": "sub", "Value": username},
                {"Name": "email", "Value": user["email"]},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "custom:groups", "Value": groups_str}
            ]
        }
    except jwt.ExpiredSignatureError:
        raise AWSCognitoException(
            "NotAuthorizedException",
            "Token expired"
        )
    except jwt.InvalidTokenError:
        raise AWSCognitoException(
            "NotAuthorizedException", 
            "Invalid token"
        )


def handle_respond_to_auth_challenge(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle RespondToAuthChallenge (not implemented in mock)"""
    raise AWSCognitoException(
        "InvalidParameterException",
        "No auth challenges in mock service"
    )


def handle_global_sign_out(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GlobalSignOut"""
    logger.info("GlobalSignOut called - returning success")
    # In mock, just return success
    return {}


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    app = FastAPI(
        title="Mock Cognito Service",
        description="Simulates AWS Cognito authentication flows for local development",
        version=frank.__version__
    )

    current_config = AppConfig.get_config()
    # Security scheme for Bearer token authentication
    security = HTTPBearer()

    # Custom exception handler for AWS-style errors
    @app.exception_handler(AWSCognitoException)
    async def aws_cognito_exception_handler(request: Request, exc: AWSCognitoException):
        """Handle AWS Cognito exceptions with proper AWS error format"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "__type": exc.error_type,
                "message": exc.message
            }
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

    def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
        """Get current user from JWT token"""
        token = credentials.credentials
        payload = verify_jwt_token(token)
        username = payload.get("username")
        
        if not username or username not in USERS_DB:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        return USERS_DB[username]

    @app.get("/health")
    async def health_check() -> Dict[str, Any]:
        """Health check endpoint"""
        logger.info("Health check endpoint accessed")
        return {
            "status": "healthy", 
            "service": "mock-cognito", 
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_pool_id": current_config.user_pool_id,
            "region": current_config.region
        }

    @app.get("/{user_pool_id}/.well-known/jwks.json")
    async def jwks_endpoint(user_pool_id: str) -> Dict[str, Any]:
        """
        AWS Cognito compatible JWKS (JSON Web Key Set) endpoint
        This provides the public keys needed for JWT token verification
        """
        logger.info(f"JWKS endpoint accessed for user pool: {user_pool_id}")
        
        # Validate user pool ID
        if user_pool_id != current_config.user_pool_id:
            raise HTTPException(
                status_code=404, 
                detail=f"User pool {user_pool_id} not found"
            )
        
        if current_config.jwt_algorithm != "RS256":
            raise HTTPException(
                status_code=400,
                detail="JWKS endpoint only available when using RS256 algorithm"
            )
        
        if not current_config.jwks:
            raise HTTPException(
                status_code=500,
                detail="JWKS not available - RSA keys not generated"
            )
        
        return current_config.jwks

    # AWS Cognito API Endpoint (for AWS CLI compatibility)
    @app.post("/")
    async def cognito_api_endpoint(
        request: Request,
        x_amz_target: Optional[str] = Header(None, alias="X-Amz-Target")
    ) -> Dict[str, Any]:
        """
        Main AWS Cognito API endpoint for AWS CLI compatibility
        AWS CLI sends requests to / with X-Amz-Target header
        """
        
        if not x_amz_target:
            raise AWSCognitoException(
                "InvalidParameterException",
                "Missing X-Amz-Target header"
            )
        
        # Extract action from target header
        # Format: AWSCognitoIdentityProviderService.InitiateAuth
        try:
            action = x_amz_target.split(".")[-1]
        except Exception:
            raise AWSCognitoException(
                "InvalidParameterException",
                "Invalid X-Amz-Target format"
            )
        
        # Parse request body
        try:
            body = await request.json()
        except Exception:
            body = {}
        
        logger.info(f"AWS Cognito API call - Action: {action}")
        logger.debug(f"Request body: {body}")
        
        # Handle the action
        response = handle_cognito_action(action, body)
        
        logger.debug(f"Response: {response}")
        return response

    @app.post("/auth/login", response_model=AuthResponse)
    async def login(auth_request: AuthRequest) -> AuthResponse:
        """
        Authenticate user and return tokens
        Simulates AWS Cognito AdminInitiateAuth
        """
        username = auth_request.username
        password = auth_request.password
        
        logger.info(f"Login attempt for user: {username}")
        
        # Validate user exists and password is correct
        if username not in USERS_DB:
            logger.warning(f"Login failed: User not found: {username}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        user = USERS_DB[username]
        if not user["enabled"]:
            logger.warning(f"Login failed: User account disabled: {username}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is disabled")
        
        if user["password"] != password:
            logger.warning(f"Login failed: Invalid password for user: {username}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
        
        # Generate tokens
        groups = user["groups"]
        access_token = create_jwt_token(username, groups, "access")
        id_token = create_jwt_token(username, groups, "id")
        refresh_token = create_jwt_token(username, groups, "refresh")
        
        logger.info(f"Login successful for user: {username} with groups: {groups}")
        
        return AuthResponse(
            access_token=access_token,
            id_token=id_token,
            refresh_token=refresh_token
        )

    @app.get("/auth/userinfo", response_model=UserInfo)
    async def get_user_info(current_user: dict = Depends(get_current_user)) -> UserInfo:
        """
        Get current user information from valid token
        """
        username = current_user["username"]
        logger.info(f"User info requested for: {username}")
        
        return UserInfo(
            username=current_user["username"],
            email=current_user["email"],
            groups=current_user["groups"]
        )

    @app.get("/auth/users")
    async def list_users() -> Dict[str, Any]:
        """
        List all users in the mock user pool (for testing)
        """
        logger.info("User list requested")
        return {
            "users": [
                {
                    "username": user["username"],
                    "email": user["email"],
                    "groups": user["groups"],
                    "enabled": user["enabled"]
                }
                for user in USERS_DB.values()
            ]
        }

    @app.get("/config")
    async def get_config() -> Dict[str, Any]:
        """
        Get mock service configuration for test scripts
        Replaces the need for external cognito-config.json file
        """
        logger.info("Configuration requested")
        return {
            "cognito_endpoint": "http://localhost:8100",
            "service_type": "mock",
            "test_users": [
                {
                    "username": user["username"],
                    "password": user["password"],  # In real Cognito, passwords wouldn't be exposed
                    "group": user["groups"][0] if user["groups"] else None,
                    "email": user["email"]
                }
                for user in USERS_DB.values()
            ]
        }

    @app.get("/debug/private-key")
    async def get_private_key() -> Dict[str, Any]:
        """
        TESTING ONLY: Get the current RSA private key in PEM format
        
        ⚠️ WARNING: This endpoint exposes the private key and should NEVER be used in production.
        It exists solely for testing purposes to allow test scripts to:
        1. Download the current private key used by the mock service
        2. Sign test tokens with the same key for validation testing
        3. Test JWT signature verification flows
        
        This endpoint is only available when using RS256 algorithm.
        """
        logger.warning("⚠️ Private key endpoint accessed - THIS IS FOR TESTING ONLY")
        
        if current_config.jwt_algorithm != "RS256":
            raise HTTPException(
                status_code=400,
                detail="Private key endpoint only available when using RS256 algorithm"
            )
        
        if not current_config.private_key:
            raise HTTPException(
                status_code=500,
                detail="Private key not available"
            )
        
        # Export private key in PEM format
        pem = current_config.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        logger.info("Private key exported in PEM format for testing")
        
        return {
            "private_key_pem": pem.decode('utf-8'),
            "algorithm": current_config.jwt_algorithm,
            "kid": "mock-cognito-key-1",
            "warning": "⚠️ THIS IS FOR TESTING ONLY - NEVER EXPOSE PRIVATE KEYS IN PRODUCTION"
        }

    @app.get("/")
    async def root() -> Dict[str, Any]:
        """Root endpoint with service information"""
        logger.info("Root endpoint accessed")
        return {
            "service": "Mock Cognito Service",
            "version": frank.__version__,
            "user_pool_id": current_config.user_pool_id,
            "client_id": current_config.client_id,
            "region": current_config.region,
            "endpoints": {
                "aws_api": "/",
                "login": "/auth/login", 
                "jwks": f"/{current_config.user_pool_id}/.well-known/jwks.json",
                "userinfo": "/auth/userinfo",
                "users": "/auth/users",
                "config": "/config",
                "health": "/health",
                "debug_private_key": "/debug/private-key (TESTING ONLY)"
            },
            "supported_aws_operations": [
                "InitiateAuth",
                "AdminInitiateAuth", 
                "GetUser",
                "GlobalSignOut"
            ],
            "test_users": list(USERS_DB.keys()),
            "aws_cli_usage": {
                "setup": "export AWS_ACCESS_KEY_ID=test && export AWS_SECRET_ACCESS_KEY=test",
                "initiate_auth": f"aws cognito-idp initiate-auth --endpoint-url http://localhost:8100 --auth-flow USER_PASSWORD_AUTH --client-id {current_config.client_id} --auth-parameters USERNAME=testuser_observer,PASSWORD=TempPass123!",
                "get_user": "aws cognito-idp get-user --endpoint-url http://localhost:8100 --access-token <access_token_from_login>"
            }
        }

    logger.info("Mock Cognito FastAPI application created successfully")
    return app

def main():
    """
    Main function with argparse for uvicorn configuration
    """
    CURRENT_MODULE = Path(__file__).stem  # Filename without extension: "simple_api_011"

    parser = argparse.ArgumentParser(description="Mock Cognito Service Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=os.environ.get("PORT", 8100), help="Port to bind the server to (default: 8100)")
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
        help="Logging level (default: debug)",
    )
    
    # Configuration options
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
        "--client-id",
        type=str,
        default=os.getenv("CLIENT_ID", "mock-client-id-123456"),
        help="Cognito client ID (default: mock-client-id-123456 or CLIENT_ID)"
    )
    parser.add_argument(
        "--user-pool-id",
        type=str,
        default=os.getenv("USER_POOL_ID", "eu-west-1_MOCKPOOL"),
        help="Cognito user pool ID (default: eu-west-1_MOCKPOOL or USER_POOL_ID)"
    )

    args = parser.parse_args()
    
    # Set environment variables for uvicorn worker processes
    # This ensures configuration survives process restarts and reloads
    os.environ["JWT_SECRET"] = args.jwt_secret
    os.environ["JWT_ALGORITHM"] = args.jwt_algorithm
    os.environ["REGION"] = args.region
    os.environ["USER_POOL_ID"] = args.user_pool_id
    os.environ["CLIENT_ID"] = args.client_id

    # Create configuration from command line arguments and set as singleton
    config = AppConfig.get_config()
    
    # Configure logging level
    setup_logging()
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
       
    logger.info(f"Starting Mock Cognito server on {args.host}:{args.port}")
    logger.info(f"Version: {frank.__version__}")
    logger.info(f"Reload enabled: {args.reload}")
    logger.info(f"Log level: {args.log_level}")
    logger.info(f"Client ID: {config.client_id}")
    logger.info(f"User Pool ID: {config.user_pool_id}")
    logger.info(f"Region: {config.region}")
    logger.info(f"JWT Algorithm: {config.jwt_algorithm}")
    logger.info(f"JWT Secret: {config.jwt_secret[:4]}... (length: {len(config.jwt_secret)})")
    logger.info("Available test users:")
    for username, user in USERS_DB.items():
        logger.info(f"  - {username} (groups: {user['groups']})")
    
    # Run uvicorn server
    uvicorn.run(
        f"{CURRENT_MODULE}:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,  # Indicates create_app is a factory function
        log_level=args.log_level
    )


if __name__ == "__main__":  # pragma: no cover
    main()
