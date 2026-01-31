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
        # Use fixed RSA key for development to prevent signature verification errors
        # when containers restart. In production, use proper key management/persistence.

        # Fixed development private key (2048-bit RSA)
        fixed_private_key_pem = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCk/cQZlb04L9Ls
HwSer25j8paOdUFfk3p8OLxLC1PV0V7hvQOHeYww3ncZH+8OWoTAFDepCTTrUtUz
rDioeaQ8GommrNR1OLLeWf0JzQwlBiqSglOagSDjxE4mvwckq+zMOiaX2aOuTroR
lM0BHXtg3XBZpxtWeYdgIMSsjviSnkv29hTqFC9MsMBZGL5HHPnbOnGTiDhYOTO8
vlzgC368qDH90nOpI3ivSZcZIsY4renXbbpJsW0ichECA1Qfu61Jsb+lyIwf87pd
/z3WW+2Xh5u7LfDCxMWc6raaqYcwmXRDjIJ/q4Ukou/Wfedo75b3fLvYhciE+6aq
i3khWxClAgMBAAECggEAD/VMOdieBX4OrcWZmfWdkkTno14bqsW7c6ITMu5PYgok
XhDSSLtiFWShwAgy2ZW6FaVUSuENQXObaSo6Yq/n9Djxi8cCAlfaaR+Va2oYnMjP
ZlNSXcp+kWPZK+3kdXtm5cv8E/Tk3C+uLJQoDfhkM2wc+UxB8dJtsce0Q30ioB+l
YeCRjpz20d2scRphib0rHrFdX2AYzLYeq2QcrX7CKWIgsthZzRU2fslYeN/FcClR
5ox0EjGm2MTJBKw4AkvPKwjCqvAt0W5sPhehoXFnyhavcP+0qOhkpTyI3hZ2FfAR
gORTZPDeLU9QD8vBWcuMKcTon0KfHhpNZg+/+o48owKBgQDOS751VfJZK8468OYJ
48kd3HDGrgg4M5BoVdZGo1qVOJRHdBJ+VD7tU5skiFmvN2CMx+WdihAe2N/7Tm55
x78mPFKdX+ldj2ujDCKqrvjPFoZDWznf2I1aP86lqzlo+k/74eUBIrF6lwmuFHwl
HOflMzZluP6K6uSvMNHg+pKKLwKBgQDMvl5zTTF+1ZQnNYHh5DRRHsYqMKxKSUCX
DfjWaNC5J5vwh57v14AdX6i+Hm3z+RR4ezhWosrQcO9WfupQ1edfm7HXywz/BOMp
Q5ViscSuqy0MYZOLPU1AqexYjg3YXltslyHbR05IGBwJ4SNtoDEa7PzWnG6p+bF7
wHY1bdjhawKBgGU5Gzn9sw14Bhg7rdQ6dat2R8vlBtl0y622OI6uhrrjaTZqSMy9
z6apuF1DniXwWSqaxxr27JQGPFjWEjUlArDjNnJL5njm75ywTq5LboBGgBi6wXoJ
iso2ttHpYyEUeXyRScm12TnatIA7QvL+7PY0m8Nr81H8kbs4jDMFIDQ3AoGBAI1F
fZ5JUTGW5Rb40JmxAHhIp6tM0lSfnrWbqmsm/34CWpLowT30kC20Z5ZnIK8K2pkX
TJRa115jzoD8KWmFbpSFtXyUWm9MTAGY5GapCnELI5Y7bbbRoZBQrwebXOpCkQqo
bXAED3unRxF6CxwFQFy30O20Gpel9lTRQ78yAEfpAoGBAIug+AS8so1rrN46MEY2
vz2EFF29FoVNwu4aI8sJ4gTPPo+tAmt9tJqyOw/h7uk+ppyPRPY+j+UvdBM8yQoE
LSYraOIRCY6sXKZY1z+/RI6xBeQi4qi4BkMPbDc7fPC1F/GMRI1jPfs1RlboVW5t
bHHufNA4TcOb6n+tmU5//nXB
-----END PRIVATE KEY-----"""

        from cryptography.hazmat.primitives import serialization

        # Load the fixed private key
        self.private_key = serialization.load_pem_private_key(
            fixed_private_key_pem.encode(),
            password=None,
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
# Organisation IDs for reference
ORG_SCHUBERG_PHILIS = "identity--schuberg-philis"
ORG_S_UNIT = "identity--s-unit"
ORG_RABOBANK = "identity--rabobank"
ORG_ING = "identity--ing"
ORG_GEMEENTE_AMSTERDAM = "identity--gemeente-amsterdam"
ORG_KPN = "identity--kpn"

USERS_DB = {
    # Schuberg Philis - Core Member (us) - 2 users including admin
    "admin": {
        "username": "admin",
        "password": "admin123",
        "email": "admin@schubergphilis.com",
        "groups": ["core_member"],
        "organisation_id": ORG_SCHUBERG_PHILIS,
        "enabled": True,
        "user_status": "CONFIRMED"
    },
    "ijsbrand": {
        "username": "ijsbrand",
        "password": "TempPass123!",
        "email": "ijsbrand.heitlager@schubergphilis.com",
        "groups": ["core_member"],
        "organisation_id": ORG_SCHUBERG_PHILIS,
        "enabled": True,
        "user_status": "CONFIRMED"
    },

    # S-Unit - Partner - 1 user
    "s_unit_analyst": {
        "username": "s_unit_analyst",
        "password": "TempPass123!",
        "email": "analyst@s-unit.nl",
        "groups": ["partner"],
        "organisation_id": ORG_S_UNIT,
        "enabled": True,
        "user_status": "CONFIRMED"
    },

    # Rabobank - Contributor - 1 user
    "rabobank_security": {
        "username": "rabobank_security",
        "password": "TempPass123!",
        "email": "security@rabobank.nl",
        "groups": ["contributor"],
        "organisation_id": ORG_RABOBANK,
        "enabled": True,
        "user_status": "CONFIRMED"
    },

    # ING - Contributor - 1 user
    "ing_soc": {
        "username": "ing_soc",
        "password": "TempPass123!",
        "email": "soc@ing.nl",
        "groups": ["contributor"],
        "organisation_id": ORG_ING,
        "enabled": True,
        "user_status": "CONFIRMED"
    },

    # Gemeente Amsterdam - Observer - 1 user
    "amsterdam_monitor": {
        "username": "amsterdam_monitor",
        "password": "TempPass123!",
        "email": "monitor@amsterdam.nl",
        "groups": ["observer"],
        "organisation_id": ORG_GEMEENTE_AMSTERDAM,
        "enabled": True,
        "user_status": "CONFIRMED"
    },

    # KPN - Observer - 1 user
    "kpn_observer": {
        "username": "kpn_observer",
        "password": "TempPass123!",
        "email": "security@kpn.com",
        "groups": ["observer"],
        "organisation_id": ORG_KPN,
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

    # ========== Admin User Management Endpoints ==========

    @app.post("/admin/users", status_code=201)
    async def admin_create_user(request: Request) -> Dict[str, Any]:
        """
        Create a new user in the mock user pool (admin API).
        Used by Management API for user creation.
        """
        body = await request.json()
        username = body.get("username")
        email = body.get("email")
        password = body.get("password", "TempPass123!")
        groups = body.get("groups", [])
        temporary_password = body.get("temporary_password", True)

        if not username:
            raise HTTPException(status_code=400, detail="username is required")
        if not email:
            raise HTTPException(status_code=400, detail="email is required")

        if username in USERS_DB:
            raise HTTPException(status_code=409, detail=f"User {username} already exists")

        # Create the user
        USERS_DB[username] = {
            "username": username,
            "password": password,
            "email": email,
            "groups": groups,
            "enabled": True,
            "user_status": "FORCE_CHANGE_PASSWORD" if temporary_password else "CONFIRMED"
        }

        logger.info(f"Admin created user: {username} with groups: {groups}")

        return {
            "username": username,
            "email": email,
            "groups": groups,
            "enabled": True,
            "user_status": USERS_DB[username]["user_status"],
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    @app.get("/admin/users/{username}")
    async def admin_get_user(username: str) -> Dict[str, Any]:
        """
        Get user details from the mock user pool (admin API).
        """
        if username not in USERS_DB:
            raise HTTPException(status_code=404, detail=f"User {username} not found")

        user = USERS_DB[username]
        logger.info(f"Admin retrieved user: {username}")

        return {
            "username": user["username"],
            "email": user["email"],
            "groups": user["groups"],
            "enabled": user["enabled"],
            "user_status": user["user_status"]
        }

    @app.put("/admin/users/{username}")
    async def admin_update_user(username: str, request: Request) -> Dict[str, Any]:
        """
        Update user in the mock user pool (admin API).
        """
        if username not in USERS_DB:
            raise HTTPException(status_code=404, detail=f"User {username} not found")

        body = await request.json()
        user = USERS_DB[username]

        # Update allowed fields
        if "email" in body:
            user["email"] = body["email"]
        if "enabled" in body:
            user["enabled"] = body["enabled"]
        if "groups" in body:
            user["groups"] = body["groups"]
        if "password" in body:
            user["password"] = body["password"]

        logger.info(f"Admin updated user: {username}")

        return {
            "username": user["username"],
            "email": user["email"],
            "groups": user["groups"],
            "enabled": user["enabled"],
            "user_status": user["user_status"]
        }

    @app.delete("/admin/users/{username}", status_code=200)
    async def admin_delete_user(username: str) -> Dict[str, Any]:
        """
        Delete user from the mock user pool (admin API).
        """
        if username not in USERS_DB:
            raise HTTPException(status_code=404, detail=f"User {username} not found")

        del USERS_DB[username]
        logger.info(f"Admin deleted user: {username}")

        return {"message": f"User {username} deleted"}

    @app.post("/admin/users/{username}/groups")
    async def admin_add_user_to_group(username: str, request: Request) -> Dict[str, Any]:
        """
        Add user to a group in the mock user pool (admin API).
        """
        if username not in USERS_DB:
            raise HTTPException(status_code=404, detail=f"User {username} not found")

        body = await request.json()
        group = body.get("group")

        if not group:
            raise HTTPException(status_code=400, detail="group is required")

        user = USERS_DB[username]
        if group not in user["groups"]:
            user["groups"].append(group)

        logger.info(f"Admin added user {username} to group: {group}")

        return {"message": f"User {username} added to group {group}"}

    @app.delete("/admin/users/{username}/groups/{group_name}")
    async def admin_remove_user_from_group(username: str, group_name: str) -> Dict[str, Any]:
        """
        Remove user from a group in the mock user pool (admin API).
        """
        if username not in USERS_DB:
            raise HTTPException(status_code=404, detail=f"User {username} not found")

        user = USERS_DB[username]
        if group_name in user["groups"]:
            user["groups"].remove(group_name)

        logger.info(f"Admin removed user {username} from group: {group_name}")

        return {"message": f"User {username} removed from group {group_name}"}

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

    @app.get("/")
    async def root() -> Dict[str, Any]:
        """Root endpoint with service information"""
        logger.info("Root endpoint accessed")
        return {
            "service": "Mock Cognito Service",
            "version": "1.0.0",
            "user_pool_id": current_config.user_pool_id,
            "client_id": current_config.client_id,
            "region": current_config.region,
            "endpoints": {
                "aws_api": "/",
                "login": "/auth/login", 
                "jwks": "/{user_pool_id}/.well-known/jwks.json",
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
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
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
    logger.info(f"Region: {config.region}")
    logger.info(f"JWT Algorithm: {config.jwt_algorithm}")
    logger.info(f"JWT Secret: {config.jwt_secret[:4]}... (length: {len(config.jwt_secret)})")

    # Log organizations
    logger.info("=== Organisations ===")
    orgs_by_tier = {}
    for username, user in USERS_DB.items():
        org_id = user.get("organisation_id", "unknown")
        tier = user["groups"][0] if user["groups"] else "unknown"
        if org_id not in orgs_by_tier:
            orgs_by_tier[org_id] = {"tier": tier, "users": []}
        orgs_by_tier[org_id]["users"].append(username)

    # Display organizations grouped by tier
    tier_order = ["core_member", "partner", "contributor", "observer"]
    for tier in tier_order:
        tier_orgs = {org_id: data for org_id, data in orgs_by_tier.items() if data["tier"] == tier}
        if tier_orgs:
            logger.info(f"\n{tier.upper().replace('_', ' ')}:")
            for org_id, data in tier_orgs.items():
                org_name = org_id.replace("identity--", "").replace("-", " ").title()
                logger.info(f"  {org_name} ({org_id})")
                logger.info(f"    Users: {', '.join(data['users'])}")

    # Log users summary
    logger.info("\n=== Users Summary ===")
    logger.info(f"Total users: {len(USERS_DB)}")
    for username, user in USERS_DB.items():
        org_id = user.get("organisation_id", "unknown")
        org_name = org_id.replace("identity--", "").replace("-", " ").title()
        logger.info(f"  {username:20} | {user['email']:35} | {user['groups'][0]:15} | {org_name}")
    
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