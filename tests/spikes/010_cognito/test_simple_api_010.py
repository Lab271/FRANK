#!/usr/bin/env python3
"""
FRANK Platform - Simple API Test Suite with Mocked Cognito

Comprehensive test suite for simple_api.py that mocks JWT token validation
instead of requiring the actual mock_cognito service to be running.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest
import jwt
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

# Import the module under test
from simple_api_010 import (
    create_app,
    get_access_tier_from_groups,
    AppConfig
)
from frank.core.enum import AccessTier


class TestSimpleAPIApp(unittest.TestCase):
    """Test cases for the Simple API FastAPI application"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        # Create test configuration for consistent testing
        self.test_config = AppConfig(
            cognito_url="http://localhost:8100",
            jwt_secret="test-secret-key",
            jwt_algorithm="HS256",
            validation_strategy="local_only"  # Use local validation for testing
        )
        
        self.app = create_app(self.test_config)
        self.client = TestClient(self.app)
        
        # Create test JWT tokens for different user types
        self.observer_token = self._create_test_token("testuser_observer", ["observer"])
        self.contributor_token = self._create_test_token("testuser_contributor", ["contributor"])
        self.partner_token = self._create_test_token("testuser_partner", ["partner"])
        self.core_member_token = self._create_test_token("testuser_core_member", ["core_member"])
        self.invalid_token = "invalid.jwt.token"
    
    def _create_test_token(self, username: str, groups: list, token_type: str = "access") -> str:
        """Create a test JWT token"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": username,
            "username": username,
            "cognito:groups": groups,
            "token_use": token_type,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "client_id": "mock-client-id-123456",
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_MOCKPOOL"
        }
        return jwt.encode(payload, self.test_config.jwt_secret, algorithm=self.test_config.jwt_algorithm)
    
    def _create_expired_token(self, username: str, groups: list) -> str:
        """Create an expired JWT token for testing"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": username,
            "username": username,
            "cognito:groups": groups,
            "token_use": "access",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),  # Expired 1 hour ago
            "client_id": "mock-client-id-123456",
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_MOCKPOOL"
        }
        return jwt.encode(payload, self.test_config.jwt_secret, algorithm=self.test_config.jwt_algorithm)
    
    def test_root_endpoint(self):
        """Test the root endpoint"""
        response = self.client.get("/")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["service"], "FRANK Simple API")
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["authentication"], "Mock Cognito JWT")
        self.assertIn("endpoints", data)
        self.assertEqual(data["mock_cognito"], self.test_config.cognito_url)
        self.assertIn("timestamp", data)
    
    def test_health_endpoint(self):
        """Test the health check endpoint"""
        response = self.client.get("/health")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "frank-simple-api")
        self.assertEqual(data["cognito_url"], self.test_config.cognito_url)
        self.assertIn("timestamp", data)
    
    def test_public_endpoint(self):
        """Test the public endpoint (no authentication required)"""
        response = self.client.get("/public")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["message"], "This is a public endpoint")
        self.assertEqual(data["access_level"], "public")
        self.assertIn("data", data)
        self.assertIn("public_info", data["data"])
    
    def test_observer_endpoint_with_observer_token(self):
        """Test observer endpoint with valid observer token"""
        headers = {"Authorization": f"Bearer {self.observer_token}"}
        response = self.client.get("/observer", headers=headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["message"], "Observer access granted")
        self.assertEqual(data["user"], "testuser_observer")
        self.assertEqual(data["access_tier"], "observer")
        self.assertIn("observer_data", data)
    
    def test_observer_endpoint_with_contributor_token(self):
        """Test observer endpoint with contributor token (should work - higher privilege)"""
        headers = {"Authorization": f"Bearer {self.contributor_token}"}
        response = self.client.get("/observer", headers=headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["user"], "testuser_contributor")
        self.assertEqual(data["access_tier"], "contributor")
    
    def test_observer_endpoint_no_auth(self):
        """Test observer endpoint without authentication"""
        response = self.client.get("/observer")
        self.assertEqual(response.status_code, 403)  # FastAPI HTTPBearer returns 403 for missing auth
    
    def test_observer_endpoint_invalid_token(self):
        """Test observer endpoint with invalid token"""
        headers = {"Authorization": f"Bearer {self.invalid_token}"}
        response = self.client.get("/observer", headers=headers)
        
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn("Invalid token", data["detail"])
    
    def test_observer_endpoint_expired_token(self):
        """Test observer endpoint with expired token"""
        expired_token = self._create_expired_token("testuser_observer", ["observer"])
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = self.client.get("/observer", headers=headers)
        
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn("Token has expired", data["detail"])
    
    def test_contributor_endpoint_with_contributor_token(self):
        """Test contributor endpoint with valid contributor token"""
        headers = {"Authorization": f"Bearer {self.contributor_token}"}
        response = self.client.get("/contributor", headers=headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["message"], "Welcome to the CONTRIBUTOR level endpoint")
        self.assertEqual(data["access_level"], "contributor")
        self.assertIn("user_info", data)
        self.assertEqual(data["user_info"]["username"], "testuser_contributor")
        self.assertEqual(data["user_info"]["access_tier"], "contributor")
        self.assertIn("data", data)
        self.assertIn("contributor_data", data["data"])
    
    def test_contributor_endpoint_with_observer_token(self):
        """Test contributor endpoint with observer token (should fail - insufficient privilege)"""
        headers = {"Authorization": f"Bearer {self.observer_token}"}
        response = self.client.get("/contributor", headers=headers)
        
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("Insufficient access level", data["detail"])
        self.assertIn("Required: contributor", data["detail"])
        self.assertIn("User has: observer", data["detail"])
    
    def test_contributor_endpoint_with_partner_token(self):
        """Test contributor endpoint with partner token (should work - higher privilege)"""
        headers = {"Authorization": f"Bearer {self.partner_token}"}
        response = self.client.get("/contributor", headers=headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user_info"]["username"], "testuser_partner")
        self.assertEqual(data["user_info"]["access_tier"], "partner")
    
    def test_partner_endpoint_with_partner_token(self):
        """Test partner endpoint with valid partner token"""
        headers = {"Authorization": f"Bearer {self.partner_token}"}
        response = self.client.get("/partner", headers=headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["message"], "Welcome to the PARTNER level endpoint")
        self.assertEqual(data["access_level"], "partner")
        self.assertIn("user_info", data)
        self.assertEqual(data["user_info"]["username"], "testuser_partner")
        self.assertIn("data", data)
        self.assertIn("partner_data", data["data"])
        self.assertIn("exclusive_features", data["data"])
    
    def test_partner_endpoint_with_contributor_token(self):
        """Test partner endpoint with contributor token (should fail - insufficient privilege)"""
        headers = {"Authorization": f"Bearer {self.contributor_token}"}
        response = self.client.get("/partner", headers=headers)
        
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("Insufficient access level", data["detail"])
        self.assertIn("Required: partner", data["detail"])
    
    def test_core_member_endpoint_with_core_member_token(self):
        """Test core member endpoint with valid core member token"""
        headers = {"Authorization": f"Bearer {self.core_member_token}"}
        response = self.client.get("/core_member", headers=headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["message"], "Welcome to the CORE_MEMBER level endpoint")
        self.assertEqual(data["access_level"], "core_member")
        self.assertIn("user_info", data)
        self.assertEqual(data["user_info"]["username"], "testuser_core_member")
        self.assertIn("data", data)
        self.assertIn("core_member_data", data["data"])
        self.assertIn("admin_features", data["data"])
    
    def test_core_member_endpoint_with_partner_token(self):
        """Test core member endpoint with partner token (should fail - insufficient privilege)"""
        headers = {"Authorization": f"Bearer {self.partner_token}"}
        response = self.client.get("/core_member", headers=headers)
        
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("Insufficient access level", data["detail"])
        self.assertIn("Required: core_member", data["detail"])
    
    def test_user_info_endpoint(self):
        """Test user info endpoint with valid token"""
        headers = {"Authorization": f"Bearer {self.contributor_token}"}
        response = self.client.get("/user-info", headers=headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["message"], "Current user information")
        self.assertIn("user", data)
        
        user_info = data["user"]
        self.assertEqual(user_info["username"], "testuser_contributor")
        self.assertEqual(user_info["access_tier"], "contributor")
        self.assertEqual(user_info["groups"], ["contributor"])
        self.assertEqual(user_info["organisation_id"], "org-testuser_contributor")
        
        # Test permissions
        permissions = user_info["permissions"]
        self.assertTrue(permissions["can_access_public"])
        self.assertTrue(permissions["can_access_contributor"])
        self.assertFalse(permissions["can_access_partner"])
        self.assertFalse(permissions["can_access_core"])
    
    def test_user_info_endpoint_partner_permissions(self):
        """Test user info endpoint permissions for partner user"""
        headers = {"Authorization": f"Bearer {self.partner_token}"}
        response = self.client.get("/user-info", headers=headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        permissions = data["user"]["permissions"]
        self.assertTrue(permissions["can_access_public"])
        self.assertTrue(permissions["can_access_contributor"])
        self.assertTrue(permissions["can_access_partner"])
        self.assertFalse(permissions["can_access_core"])
    
    def test_user_info_endpoint_core_member_permissions(self):
        """Test user info endpoint permissions for core member user"""
        headers = {"Authorization": f"Bearer {self.core_member_token}"}
        response = self.client.get("/user-info", headers=headers)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        permissions = data["user"]["permissions"]
        self.assertTrue(permissions["can_access_public"])
        self.assertTrue(permissions["can_access_contributor"])
        self.assertTrue(permissions["can_access_partner"])
        self.assertTrue(permissions["can_access_core"])
    
    def test_token_without_username(self):
        """Test token that's missing username field"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "testuser_observer",
            # Missing "username" field
            "cognito:groups": ["observer"],
            "token_use": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "client_id": "mock-client-id-123456",
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_MOCKPOOL"
        }
        token = jwt.encode(payload, self.test_config.jwt_secret, algorithm=self.test_config.jwt_algorithm)
        
        headers = {"Authorization": f"Bearer {token}"}
        response = self.client.get("/observer", headers=headers)
        
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn("Invalid token: missing username", data["detail"])


class TestAccessTierMapping(unittest.TestCase):
    """Test cases for access tier mapping functions"""
    
    def test_get_access_tier_from_groups_observer(self):
        """Test mapping observer group to AccessTier"""
        tier = get_access_tier_from_groups(["observer"])
        self.assertEqual(tier, AccessTier.OBSERVER)
    
    def test_get_access_tier_from_groups_contributor(self):
        """Test mapping contributor group to AccessTier"""
        tier = get_access_tier_from_groups(["contributor"])
        self.assertEqual(tier, AccessTier.CONTRIBUTOR)
    
    def test_get_access_tier_from_groups_partner(self):
        """Test mapping partner group to AccessTier"""
        tier = get_access_tier_from_groups(["partner"])
        self.assertEqual(tier, AccessTier.PARTNER)
    
    def test_get_access_tier_from_groups_core_member(self):
        """Test mapping core_member group to AccessTier"""
        tier = get_access_tier_from_groups(["core_member"])
        self.assertEqual(tier, AccessTier.CORE_MEMBER)
    
    def test_get_access_tier_from_groups_empty(self):
        """Test mapping empty groups to PUBLIC"""
        tier = get_access_tier_from_groups([])
        self.assertEqual(tier, AccessTier.PUBLIC)
    
    def test_get_access_tier_from_groups_multiple(self):
        """Test mapping multiple groups (should use first one)"""
        tier = get_access_tier_from_groups(["partner", "contributor"])
        self.assertEqual(tier, AccessTier.PARTNER)
    
    def test_get_access_tier_from_groups_unknown(self):
        """Test mapping unknown group (should use default)"""
        tier = get_access_tier_from_groups(["unknown_group"])
        # AccessTier.from_string with default=True should return PUBLIC for unknown values
        self.assertEqual(tier, AccessTier.PUBLIC)


class TestEndpointIntegration(unittest.TestCase):
    """Integration tests for complete endpoint workflows"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create test configuration for consistent testing
        self.test_config = AppConfig(
            cognito_url="http://localhost:8100",
            jwt_secret="test-secret-key",
            jwt_algorithm="HS256",
            validation_strategy="local_only"  # Use local validation for testing
        )
        
        self.app = create_app(self.test_config)
        self.client = TestClient(self.app)
        
        # Create tokens for different users
        self.tokens = {
            "observer": self._create_test_token("testuser_observer", ["observer"]),
            "contributor": self._create_test_token("testuser_contributor", ["contributor"]),
            "partner": self._create_test_token("testuser_partner", ["partner"]),
            "core_member": self._create_test_token("testuser_core_member", ["core_member"])
        }
    
    def _create_test_token(self, username: str, groups: list) -> str:
        """Create a test JWT token"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": username,
            "username": username,
            "cognito:groups": groups,
            "token_use": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "client_id": "mock-client-id-123456",
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_MOCKPOOL"
        }
        return jwt.encode(payload, self.test_config.jwt_secret, algorithm=self.test_config.jwt_algorithm)
    
    def test_access_matrix(self):
        """Test complete access matrix for all users and endpoints"""
        # Define expected access matrix: user_type -> endpoint -> should_succeed
        access_matrix = {
            "observer": {
                "/public": True,
                "/observer": True,
                "/contributor": False,
                "/partner": False,
                "/core_member": False,
                "/user-info": True
            },
            "contributor": {
                "/public": True,
                "/observer": True,
                "/contributor": True,
                "/partner": False,
                "/core_member": False,
                "/user-info": True
            },
            "partner": {
                "/public": True,
                "/observer": True,
                "/contributor": True,
                "/partner": True,
                "/core_member": False,
                "/user-info": True
            },
            "core_member": {
                "/public": True,
                "/observer": True,
                "/contributor": True,
                "/partner": True,
                "/core_member": True,
                "/user-info": True
            }
        }
        
        for user_type, token in self.tokens.items():
            for endpoint, should_succeed in access_matrix[user_type].items():
                with self.subTest(user=user_type, endpoint=endpoint):
                    headers = {"Authorization": f"Bearer {token}"}
                    response = self.client.get(endpoint, headers=headers)
                    
                    if should_succeed:
                        self.assertEqual(response.status_code, 200, 
                                       f"{user_type} should have access to {endpoint}")
                    else:
                        self.assertEqual(response.status_code, 403, 
                                       f"{user_type} should NOT have access to {endpoint}")
    
    def test_endpoint_without_auth_matrix(self):
        """Test that protected endpoints properly require authentication"""
        protected_endpoints = ["/observer", "/contributor", "/partner", "/core_member", "/user-info"]
        
        for endpoint in protected_endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 403, 
                               f"{endpoint} should require authentication")


if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)