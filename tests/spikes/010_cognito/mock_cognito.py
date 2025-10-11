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
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone

import uvicorn
import jwt
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# Custom AWS-style exception for Cognito API compatibility
class AWSCognitoException(Exception):
    def __init__(self, error_type: str, message: str, status_code: int = 400):
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

# JWT Secret for signing tokens (in production, use proper key management)
JWT_SECRET = "mock-cognito-secret-key"
JWT_ALGORITHM = "HS256"

# AWS Cognito configuration for AWS CLI compatibility
USER_POOL_ID = "eu-west-1_MOCKPOOL"
CLIENT_ID = "mock-client-id-123456"
REGION = "eu-west-1"

# Security scheme for Bearer token authentication
security = HTTPBearer()

# In-memory user store (simulates Cognito User Pool)
USERS_DB = {
    "testuser_observer": {
        "username": "testuser_observer",
        "password": "TempPass123!",
        "email": "observer@example.com",
        "groups": ["observer"],
        "enabled": True,
        "user_status": "CONFIRMED"
    },
    "testuser_contributor": {
        "username": "testuser_contributor", 
        "password": "TempPass123!",
        "email": "contributor@example.com",
        "groups": ["contributor"],
        "enabled": True,
        "user_status": "CONFIRMED"
    },
    "testuser_partner": {
        "username": "testuser_partner", 
        "password": "TempPass123!",
        "email": "partner@example.com",
        "groups": ["partner"],
        "enabled": True,
        "user_status": "CONFIRMED"
    },
    "testuser_core_member": {
        "username": "testuser_core_member", 
        "password": "TempPass123!",
        "email": "core_member@example.com",
        "groups": ["core_member"],
        "enabled": True,
        "user_status": "CONFIRMED"
    }
}

# Request/Response Models
class AuthRequest(BaseModel):
    username: str
    password: str

class TokenValidationRequest(BaseModel):
    token: str

class AuthResponse(BaseModel):
    access_token: str
    id_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600

class TokenValidationResponse(BaseModel):
    valid: bool
    username: Optional[str] = None
    groups: Optional[List[str]] = None
    error: Optional[str] = None

class UserInfo(BaseModel):
    username: str
    email: str
    groups: List[str]


def create_jwt_token(username: str, groups: List[str], token_type: str = "access") -> str:
    """Create a JWT token with user information matching Cognito format"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,  # Cognito uses 'sub' for user identifier
        "cognito:groups": groups,
        "token_use": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "client_id": CLIENT_ID,
        "username": username,
        "iss": f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
    }
    
    # Add additional claims for ID tokens
    if token_type == "id":
        user = USERS_DB[username]
        payload["email"] = user["email"]
        payload["email_verified"] = True
        payload["aud"] = CLIENT_ID
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict:
    """Verify and decode JWT token"""
    try:
        # Decode without audience verification for mock service simplicity
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_aud": False})
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = verify_jwt_token(token)
    username = payload.get("username")
    
    if not username or username not in USERS_DB:
        raise HTTPException(status_code=401, detail="Invalid user")
    
    return USERS_DB[username]


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
    
    if not access_token:
        raise AWSCognitoException(
            "InvalidParameterException",
            "AccessToken required"
        )
    
    try:
        payload = jwt.decode(
            access_token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
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
        
        return {
            "Username": username,
            "UserAttributes": [
                {"Name": "sub", "Value": username},
                {"Name": "email", "Value": user["email"]},
                {"Name": "email_verified", "Value": "true"}
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
        version="1.0.0"
    )

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

    @app.get("/health")
    async def health_check() -> Dict[str, Any]:
        """Health check endpoint"""
        logger.info("Health check endpoint accessed")
        return {
            "status": "healthy", 
            "service": "mock-cognito", 
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_pool_id": USER_POOL_ID,
            "region": REGION
        }

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
            raise HTTPException(status_code=401, detail="User not found")
        
        user = USERS_DB[username]
        if not user["enabled"]:
            logger.warning(f"Login failed: User account disabled: {username}")
            raise HTTPException(status_code=401, detail="User account is disabled")
        
        if user["password"] != password:
            logger.warning(f"Login failed: Invalid password for user: {username}")
            raise HTTPException(status_code=401, detail="Invalid password")
        
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

    @app.post("/auth/validate", response_model=TokenValidationResponse)
    async def validate_token(request: TokenValidationRequest) -> TokenValidationResponse:
        """
        Validate JWT token and return user information
        """
        try:
            payload = verify_jwt_token(request.token)
            username = payload.get("username")
            groups = payload.get("cognito:groups", [])
            
            logger.info(f"Token validation successful for user: {username}")
            
            return TokenValidationResponse(
                valid=True,
                username=username,
                groups=groups
            )
        except HTTPException as e:
            logger.warning(f"Token validation failed: {e.detail}")
            return TokenValidationResponse(
                valid=False,
                error=e.detail
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
            "mock_cognito_endpoint": "http://localhost:8100",
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

    @app.get("/")
    async def root() -> Dict[str, Any]:
        """Root endpoint with service information"""
        logger.info("Root endpoint accessed")
        return {
            "service": "Mock Cognito Service",
            "version": "1.0.0",
            "user_pool_id": USER_POOL_ID,
            "client_id": CLIENT_ID,
            "region": REGION,
            "endpoints": {
                "aws_api": "/",
                "login": "/auth/login", 
                "validate": "/auth/validate",
                "userinfo": "/auth/userinfo",
                "users": "/auth/users",
                "config": "/config",
                "health": "/health"
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
                "initiate_auth": f"aws cognito-idp initiate-auth --endpoint-url http://localhost:8100 --auth-flow USER_PASSWORD_AUTH --client-id {CLIENT_ID} --auth-parameters USERNAME=testuser_observer,PASSWORD=TempPass123!",
                "get_user": "aws cognito-idp get-user --endpoint-url http://localhost:8100 --access-token <access_token_from_login>"
            }
        }

    logger.info("Mock Cognito FastAPI application created successfully")
    return app


# Create module-level app instance for ASGI servers
app = create_app()


def main():
    """
    Main function with argparse for uvicorn configuration
    """
    parser = argparse.ArgumentParser(description="Mock Cognito Service Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=os.environ.get("PORT", 8100), help="Port to bind the server to (default: 8100)")
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
    
    logger.info(f"Starting Mock Cognito server on {args.host}:{args.port}")
    logger.info(f"Reload enabled: {args.reload}")
    logger.info(f"Log level: {args.log_level}")
    logger.info("Available test users:")
    for username, user in USERS_DB.items():
        logger.info(f"  - {username} (groups: {user['groups']})")
    
    # Run uvicorn server
    uvicorn.run(
        "mock_cognito:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,  # Indicates create_app is a factory function
        log_level=args.log_level
    )


if __name__ == "__main__":  # pragma: no cover
    main()