#!/usr/bin/env python3
"""
FRANK Platform - Cognito Authentication Spike - Unit Tests for Mock Cognito Service

Comprehensive test suite for mock_cognito.py service validation.
Tests both REST endpoints and AWS API compatibility.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest
import jwt
from datetime import datetime, timezone, timedelta

from fastapi import status
from fastapi.testclient import TestClient

# Import the module under test
from mock_cognito import (
    create_app, 
    create_jwt_token, 
    verify_jwt_token, 
    handle_cognito_action,
    handle_initiate_auth,
    handle_admin_initiate_auth,
    handle_get_user,
    get_config,
    USERS_DB
)


class TestMockCognitoApp(unittest.TestCase):
    """Test cases for the FastAPI application endpoints"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        self.app = create_app()
        self.client = TestClient(self.app)
        
        # Create test tokens for various users
        self.observer_token = create_jwt_token("testuser_observer", ["observer"], "access")
        self.contributor_token = create_jwt_token("testuser_contributor", ["contributor"], "access")
        self.partner_token = create_jwt_token("testuser_partner", ["partner"], "access")
        self.core_member_token = create_jwt_token("testuser_core_member", ["core_member"], "access")
        
        # Invalid token for negative tests
        self.invalid_token = "invalid.jwt.token"
    
    def test_health_endpoint(self):
        """Test the health check endpoint"""
        response = self.client.get("/health")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "mock-cognito")
        self.assertEqual(data["user_pool_id"], get_config().user_pool_id)
        self.assertEqual(data["region"], get_config().region)
        self.assertIn("timestamp", data)
    
    def test_root_endpoint(self):
        """Test the root endpoint with service information"""
        response = self.client.get("/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data["service"], "Mock Cognito Service")
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["user_pool_id"], get_config().user_pool_id)
        self.assertEqual(data["client_id"], get_config().client_id)
        self.assertEqual(data["region"], get_config().region)
        self.assertIn("endpoints", data)
        self.assertIn("supported_aws_operations", data)
        self.assertIn("test_users", data)
        self.assertIn("aws_cli_usage", data)
    
    def test_rest_login_success(self):
        """Test successful login via REST endpoint"""
        login_data = {
            "username": "testuser_observer",
            "password": "TempPass123!"
        }
        
        response = self.client.post("/auth/login", json=login_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn("access_token", data)
        self.assertIn("id_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["token_type"], "Bearer")
        self.assertEqual(data["expires_in"], 3600)
        
        # Verify the access token is valid
        payload = jwt.decode(
            data["access_token"], 
            get_config().get_verification_key(), 
            algorithms=[get_config().jwt_algorithm], 
            options={"verify_aud": False}
        )
        self.assertEqual(payload["username"], "testuser_observer")
        self.assertEqual(payload["cognito:groups"], ["observer"])
    
    def test_rest_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        test_cases = [
            {"username": "nonexistent", "password": "TempPass123!", "status": status.HTTP_404_NOT_FOUND},  # Non-existent user
            {"username": "testuser_observer", "password": "wrongpassword", "status": status.HTTP_401_UNAUTHORIZED},  # Wrong password
        ]
        
        for login_data in test_cases:
            with self.subTest(login_data=login_data):
                response = self.client.post("/auth/login", json=login_data)
                self.assertEqual(response.status_code, login_data["status"])
    
    def test_jwks_endpoint(self):
        """Test JWKS endpoint for public key retrieval"""
        # Test valid user pool ID
        response = self.client.get("/eu-west-1_MOCKPOOL/.well-known/jwks.json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn("keys", data)
        self.assertIsInstance(data["keys"], list)
        self.assertGreater(len(data["keys"]), 0)
        
        # Verify key structure
        key = data["keys"][0]
        self.assertEqual(key["kty"], "RSA")
        self.assertEqual(key["use"], "sig")
        self.assertEqual(key["alg"], "RS256")
        self.assertIn("n", key)  # RSA modulus
        self.assertIn("e", key)  # RSA exponent
        self.assertIn("kid", key)  # Key ID
        
        # Test invalid user pool ID
        response = self.client.get("/invalid-pool/.well-known/jwks.json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_user_info_endpoint(self):
        """Test user info endpoint with authentication"""
        headers = {"Authorization": f"Bearer {self.observer_token}"}
        response = self.client.get("/auth/userinfo", headers=headers)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data["username"], "testuser_observer")
        self.assertEqual(data["email"], "observer@example.com")
        self.assertEqual(data["groups"], ["observer"])
    
    def test_user_info_endpoint_no_auth(self):
        """Test user info endpoint without authentication"""
        response = self.client.get("/auth/userinfo")
        self.assertEqual(response.status_code, 403)  # FastAPI HTTPBearer returns 403 for missing auth
    
    def test_list_users_endpoint(self):
        """Test the list users endpoint"""
        response = self.client.get("/auth/users")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn("users", data)
        self.assertEqual(len(data["users"]), len(USERS_DB))
        
        # Check that all expected users are present
        usernames = [user["username"] for user in data["users"]]
        expected_users = list(USERS_DB.keys())
        self.assertEqual(set(usernames), set(expected_users))
    
    def test_config_endpoint(self):
        """Test the configuration endpoint"""
        response = self.client.get("/config")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data["cognito_endpoint"], "http://localhost:8100")
        self.assertEqual(data["service_type"], "mock")
        self.assertIn("test_users", data)
        self.assertEqual(len(data["test_users"]), len(USERS_DB))


class TestAWSCognitoAPI(unittest.TestCase):
    """Test cases for AWS Cognito API compatibility"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = create_app()
        self.client = TestClient(self.app)
    
    def test_initiate_auth_success(self):
        """Test successful InitiateAuth via AWS API"""
        headers = {
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": get_config().client_id,
            "AuthParameters": {
                "USERNAME": "testuser_observer",
                "PASSWORD": "TempPass123!"
            }
        }
        
        response = self.client.post("/", headers=headers, json=payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertIn("AuthenticationResult", data)
        auth_result = data["AuthenticationResult"]
        
        self.assertIn("AccessToken", auth_result)
        self.assertIn("IdToken", auth_result)
        self.assertIn("RefreshToken", auth_result)
        self.assertEqual(auth_result["TokenType"], "Bearer")
        self.assertEqual(auth_result["ExpiresIn"], 3600)
        
        # Verify token structure
        access_token = auth_result["AccessToken"]
        payload = jwt.decode(
            access_token, 
            get_config().get_verification_key(), 
            algorithms=[get_config().jwt_algorithm], 
            options={"verify_aud": False}
        )
        self.assertEqual(payload["username"], "testuser_observer")
        self.assertEqual(payload["cognito:groups"], ["observer"])
    
    def test_initiate_auth_invalid_credentials(self):
        """Test InitiateAuth with invalid credentials"""
        headers = {
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": get_config().client_id,
            "AuthParameters": {
                "USERNAME": "nonexistent",
                "PASSWORD": "wrongpassword"
            }
        }
        
        response = self.client.post("/", headers=headers, json=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_initiate_auth_unsupported_flow(self):
        """Test InitiateAuth with unsupported auth flow"""
        headers = {
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        payload = {
            "AuthFlow": "SRP_AUTH",  # Unsupported flow
            "ClientId": get_config().client_id,
            "AuthParameters": {
                "USERNAME": "testuser_observer",
                "PASSWORD": "TempPass123!"
            }
        }
        
        response = self.client.post("/", headers=headers, json=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertEqual(response_data["__type"], "InvalidParameterException")
        self.assertIn("Unsupported auth flow", response_data["message"])
    
    def test_admin_initiate_auth(self):
        """Test AdminInitiateAuth (should work same as InitiateAuth)"""
        headers = {
            "X-Amz-Target": "AWSCognitoIdentityProviderService.AdminInitiateAuth",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": get_config().client_id,
            "AuthParameters": {
                "USERNAME": "testuser_contributor",
                "PASSWORD": "TempPass123!"
            }
        }
        
        response = self.client.post("/", headers=headers, json=payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("AuthenticationResult", data)
    
    def test_get_user(self):
        """Test GetUser API call"""
        # First get a token
        access_token = create_jwt_token("testuser_partner", ["partner"], "access")
        
        headers = {
            "X-Amz-Target": "AWSCognitoIdentityProviderService.GetUser",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        payload = {
            "AccessToken": access_token
        }
        
        response = self.client.post("/", headers=headers, json=payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data["Username"], "testuser_partner")
        self.assertIn("UserAttributes", data)
        
        # Check user attributes
        attributes = {attr["Name"]: attr["Value"] for attr in data["UserAttributes"]}
        self.assertEqual(attributes["sub"], "testuser_partner")
        self.assertEqual(attributes["email"], "partner@example.com")
        self.assertEqual(attributes["email_verified"], "true")
    
    def test_get_user_invalid_token(self):
        """Test GetUser with invalid token"""
        headers = {
            "X-Amz-Target": "AWSCognitoIdentityProviderService.GetUser",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        payload = {
            "AccessToken": "invalid.token.here"
        }
        
        response = self.client.post("/", headers=headers, json=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_global_sign_out(self):
        """Test GlobalSignOut API call"""
        headers = {
            "X-Amz-Target": "AWSCognitoIdentityProviderService.GlobalSignOut",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        payload = {}
        
        response = self.client.post("/", headers=headers, json=payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data, {})  # Should return empty dict
    
    def test_respond_to_auth_challenge(self):
        """Test RespondToAuthChallenge (should return error - not implemented)"""
        headers = {
            "X-Amz-Target": "AWSCognitoIdentityProviderService.RespondToAuthChallenge",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        payload = {}
        
        response = self.client.post("/", headers=headers, json=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertEqual(response_data["__type"], "InvalidParameterException")
        self.assertIn("No auth challenges", response_data["message"])
    
    def test_unknown_operation(self):
        """Test unknown AWS operation"""
        headers = {
            "X-Amz-Target": "AWSCognitoIdentityProviderService.UnknownOperation",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        payload = {}
        
        response = self.client.post("/", headers=headers, json=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertEqual(response_data["__type"], "InvalidParameterException")
        self.assertIn("Unknown operation", response_data["message"])
    
    def test_missing_target_header(self):
        """Test AWS API call without X-Amz-Target header"""
        response = self.client.post("/", json={})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertEqual(response_data["__type"], "InvalidParameterException")
        self.assertIn("Missing X-Amz-Target header", response_data["message"])
    
    def test_invalid_target_header(self):
        """Test AWS API call with invalid X-Amz-Target header"""
        headers = {
            "X-Amz-Target": "InvalidTarget",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        response = self.client.post("/", headers=headers, json={})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertEqual(response_data["__type"], "InvalidParameterException")
        # The invalid target "InvalidTarget" becomes action "InvalidTarget" which is unknown
        self.assertIn("Unknown operation: InvalidTarget", response_data["message"])
    
    def test_empty_target_header(self):
        """Test AWS API call with empty X-Amz-Target header"""
        # Empty string is treated as missing header by the `if not x_amz_target:` check
        headers = {
            "X-Amz-Target": "",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        response = self.client.post("/", headers=headers, json={})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertEqual(response_data["__type"], "InvalidParameterException")
        # Empty string triggers the "Missing X-Amz-Target header" check
        self.assertIn("Missing X-Amz-Target header", response_data["message"])
    
    def test_action_only_target_header(self):
        """Test AWS API call with target header that contains only action name"""
        headers = {
            "X-Amz-Target": "SomeAction",
            "Content-Type": "application/x-amz-json-1.1"
        }
        
        response = self.client.post("/", headers=headers, json={})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertEqual(response_data["__type"], "InvalidParameterException")
        # "SomeAction".split(".")[-1] would return "SomeAction", which is unknown
        self.assertIn("Unknown operation: SomeAction", response_data["message"])


class TestJWTTokenFunctions(unittest.TestCase):
    """Test cases for JWT token creation and validation functions"""
    
    def test_create_jwt_token_access(self):
        """Test creating access tokens"""
        username = "testuser_observer"
        groups = ["observer"]
        token = create_jwt_token(username, groups, "access")
        
        # Decode and verify
        payload = jwt.decode(
            token, 
            get_config().get_verification_key(), 
            algorithms=[get_config().jwt_algorithm], 
            options={"verify_aud": False}
        )
        
        self.assertEqual(payload["sub"], username)
        self.assertEqual(payload["username"], username)
        self.assertEqual(payload["cognito:groups"], groups)
        self.assertEqual(payload["token_use"], "access")
        self.assertEqual(payload["client_id"], get_config().client_id)
        self.assertIn("iat", payload)
        self.assertIn("exp", payload)
        self.assertIn("iss", payload)
        
        # Verify expiration is ~1 hour from now
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        duration = exp_time - iat_time
        self.assertAlmostEqual(duration.total_seconds(), 3600, delta=60)  # Allow 1 minute tolerance
    
    def test_create_jwt_token_id(self):
        """Test creating ID tokens"""
        username = "testuser_contributor"
        groups = ["contributor"]
        token = create_jwt_token(username, groups, "id")
        
        # Decode and verify
        payload = jwt.decode(
            token, 
            get_config().get_verification_key(), 
            algorithms=[get_config().jwt_algorithm], 
            options={"verify_aud": False}
        )
        
        self.assertEqual(payload["token_use"], "id")
        self.assertEqual(payload["email"], "contributor@example.com")
        self.assertTrue(payload["email_verified"])
        self.assertEqual(payload["aud"], get_config().client_id)
    
    def test_verify_jwt_token_valid(self):
        """Test verifying valid JWT tokens"""
        username = "testuser_partner"
        groups = ["partner"]
        token = create_jwt_token(username, groups, "access")
        
        payload = verify_jwt_token(token)
        
        self.assertEqual(payload["username"], username)
        self.assertEqual(payload["cognito:groups"], groups)
    
    def test_verify_jwt_token_invalid(self):
        """Test verifying invalid JWT tokens"""
        from fastapi import HTTPException
        
        with self.assertRaises(HTTPException) as context:
            verify_jwt_token("invalid.token.here")
        
        self.assertEqual(context.exception.status_code, 401)
        self.assertIn("Invalid token", context.exception.detail)
    
    def test_verify_jwt_token_expired(self):
        """Test verifying expired JWT tokens"""
        from fastapi import HTTPException
        
        # Create an expired token
        username = "testuser_core_member"
        groups = ["core_member"]
        now = datetime.now(timezone.utc)
        expired_payload = {
            "sub": username,
            "username": username,
            "cognito:groups": groups,
            "token_use": "access",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),  # Expired 1 hour ago
            "client_id": get_config().client_id,
            "iss": f"https://cognito-idp.{get_config().region}.amazonaws.com/{get_config().user_pool_id}"
        }
        
        # Use the proper signing key for the current algorithm
        if get_config().jwt_algorithm == "RS256":
            signing_key = get_config().get_signing_key()
            headers = {"kid": "mock-cognito-key-1"}
            expired_token = jwt.encode(expired_payload, signing_key, algorithm=get_config().jwt_algorithm, headers=headers)
        else:
            expired_token = jwt.encode(expired_payload, get_config().get_signing_key(), algorithm=get_config().jwt_algorithm)

        with self.assertRaises(HTTPException) as context:
            verify_jwt_token(expired_token)
        
        self.assertEqual(context.exception.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Token has expired", context.exception.detail)


class TestCognitoActionHandlers(unittest.TestCase):
    """Test cases for individual Cognito action handler functions"""
    
    def test_handle_initiate_auth_success(self):
        """Test handle_initiate_auth function directly"""
        body = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": get_config().client_id,
            "AuthParameters": {
                "USERNAME": "testuser_observer",
                "PASSWORD": "TempPass123!"
            }
        }
        
        result = handle_initiate_auth(body)
        
        self.assertIn("AuthenticationResult", result)
        self.assertIn("ChallengeParameters", result)
        self.assertEqual(result["ChallengeParameters"], {})
        
        auth_result = result["AuthenticationResult"]
        self.assertIn("AccessToken", auth_result)
        self.assertIn("IdToken", auth_result)
        self.assertIn("RefreshToken", auth_result)
    
    def test_handle_admin_initiate_auth(self):
        """Test handle_admin_initiate_auth function"""
        body = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": get_config().client_id,
            "AuthParameters": {
                "USERNAME": "testuser_contributor",
                "PASSWORD": "TempPass123!"
            }
        }
        
        result = handle_admin_initiate_auth(body)
        
        # Should return same structure as InitiateAuth
        self.assertIn("AuthenticationResult", result)
    
    def test_handle_get_user_function(self):
        """Test handle_get_user function directly"""
        access_token = create_jwt_token("testuser_partner", ["partner"], "access")
        
        body = {
            "AccessToken": access_token
        }
        
        result = handle_get_user(body)
        
        self.assertEqual(result["Username"], "testuser_partner")
        self.assertIn("UserAttributes", result)
    
    def test_handle_cognito_action_routing(self):
        """Test the main action routing function"""
        # Test InitiateAuth routing
        body = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": get_config().client_id,
            "AuthParameters": {
                "USERNAME": "testuser_observer",
                "PASSWORD": "TempPass123!"
            }
        }
        
        result = handle_cognito_action("InitiateAuth", body)
        self.assertIn("AuthenticationResult", result)
        
        # Test unknown action
        from mock_cognito import AWSCognitoException
        with self.assertRaises(AWSCognitoException):
            handle_cognito_action("UnknownAction", {})


class TestUserDatabase(unittest.TestCase):
    """Test cases for user database validation"""
    
    def test_users_db_structure(self):
        """Test that USERS_DB has the expected structure"""
        expected_users = ["testuser_observer", "testuser_contributor", "testuser_partner", "testuser_core_member"]
        
        self.assertEqual(set(USERS_DB.keys()), set(expected_users))
        
        for username, user_data in USERS_DB.items():
            with self.subTest(username=username):
                # Check required fields
                self.assertIn("username", user_data)
                self.assertIn("password", user_data)
                self.assertIn("email", user_data)
                self.assertIn("groups", user_data)
                self.assertIn("enabled", user_data)
                self.assertIn("user_status", user_data)
                
                # Check data types and values
                self.assertEqual(user_data["username"], username)
                self.assertEqual(user_data["password"], "TempPass123!")
                self.assertTrue(user_data["enabled"])
                self.assertEqual(user_data["user_status"], "CONFIRMED")
                self.assertIsInstance(user_data["groups"], list)
                self.assertTrue(len(user_data["groups"]) > 0)
    
    def test_user_group_mappings(self):
        """Test that users have correct group mappings"""
        expected_mappings = {
            "testuser_observer": ["observer"],
            "testuser_contributor": ["contributor"],
            "testuser_partner": ["partner"],
            "testuser_core_member": ["core_member"]
        }
        
        for username, expected_groups in expected_mappings.items():
            with self.subTest(username=username):
                self.assertEqual(USERS_DB[username]["groups"], expected_groups)


if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)