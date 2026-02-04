"""
AWS Cognito stub service for local development and testing.

This stub provides a minimal FastAPI-based implementation of AWS Cognito
for authentication testing without requiring AWS credentials or costs.
"""
from tests.stubs.cognito.stub_cognito import (
    USERS_DB,
    AWSCognitoException,
    create_app,
    create_jwt_token,
    get_config,
    handle_admin_initiate_auth,
    handle_cognito_action,
    handle_get_user,
    handle_initiate_auth,
    verify_jwt_token,
)

__all__ = [
    "create_app",
    "create_jwt_token",
    "verify_jwt_token",
    "handle_cognito_action",
    "handle_initiate_auth",
    "handle_admin_initiate_auth",
    "handle_get_user",
    "get_config",
    "USERS_DB",
    "AWSCognitoException",
]
