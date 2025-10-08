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
- Role-based group membership (user_role_a, user_role_b)
- Health check endpoint

❌ NOT IMPLEMENTED (Available in cognito-local):
- AdminInitiateAuth / InitiateAuth (we use simplified /auth/login)
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
- Our Mock: Simplified REST endpoints (/auth/login, /auth/validate, /auth/userinfo)

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

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
import json
from typing import Optional, List
from datetime import datetime, timedelta

app = FastAPI(title="Mock Cognito Service", version="1.0.0")
security = HTTPBearer()

# JWT Secret for signing tokens (in production, use proper key management)
JWT_SECRET = "mock-cognito-secret-key"
JWT_ALGORITHM = "HS256"

# In-memory user store (simulates Cognito User Pool)
USERS_DB = {
    "testuser_a": {
        "username": "testuser_a",
        "password": "TempPass123!",
        "email": "usera@example.com",
        "groups": ["user_role_a"],
        "enabled": True
    },
    "testuser_b": {
        "username": "testuser_b", 
        "password": "TempPass123!",
        "email": "userb@example.com",
        "groups": ["user_role_b"],
        "enabled": True
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
    """Create a JWT token with user information"""
    now = datetime.utcnow()
    payload = {
        "username": username,
        "cognito:groups": groups,
        "token_use": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "aud": "mock-cognito-client",
        "iss": "mock-cognito"
    }
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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mock-cognito", "timestamp": datetime.utcnow().isoformat()}

@app.post("/auth/login", response_model=AuthResponse)
async def login(auth_request: AuthRequest):
    """
    Authenticate user and return tokens
    Simulates AWS Cognito AdminInitiateAuth
    """
    username = auth_request.username
    password = auth_request.password
    
    # Validate user exists and password is correct
    if username not in USERS_DB:
        raise HTTPException(status_code=401, detail="User not found")
    
    user = USERS_DB[username]
    if not user["enabled"]:
        raise HTTPException(status_code=401, detail="User account is disabled")
    
    if user["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Generate tokens
    groups = user["groups"]
    access_token = create_jwt_token(username, groups, "access")
    id_token = create_jwt_token(username, groups, "id")
    refresh_token = create_jwt_token(username, groups, "refresh")
    
    return AuthResponse(
        access_token=access_token,
        id_token=id_token,
        refresh_token=refresh_token
    )

@app.post("/auth/validate", response_model=TokenValidationResponse)
async def validate_token(request: TokenValidationRequest):
    """
    Validate JWT token and return user information
    """
    try:
        payload = verify_jwt_token(request.token)
        return TokenValidationResponse(
            valid=True,
            username=payload.get("username"),
            groups=payload.get("cognito:groups", [])
        )
    except HTTPException as e:
        return TokenValidationResponse(
            valid=False,
            error=e.detail
        )

@app.get("/auth/userinfo", response_model=UserInfo)
async def get_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current user information from valid token
    """
    return UserInfo(
        username=current_user["username"],
        email=current_user["email"],
        groups=current_user["groups"]
    )

@app.get("/auth/users")
async def list_users():
    """
    List all users in the mock user pool (for testing)
    """
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
async def get_config():
    """
    Get mock service configuration for test scripts
    Replaces the need for external cognito_config.json file
    """
    return {
        "mock_cognito_endpoint": "http://localhost:8080",
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
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Mock Cognito Service",
        "version": "1.0.0",
        "endpoints": {
            "login": "/auth/login",
            "validate": "/auth/validate",
            "userinfo": "/auth/userinfo",
            "users": "/auth/users",
            "config": "/config",
            "health": "/health"
        },
        "test_users": list(USERS_DB.keys())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)