#!/usr/bin/env python3
"""
FRANK Platform - Unit Tests for Authentication Module

Unit tests for JWT token validation, JWKS client caching, and authentication utilities.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPAuthorizationCredentials

from frank.util.auth import CognitoValidator, security
from frank.core.enum import AccessTier
from frank.util.http_exceptions import UnauthorizedException


class TestCognitoValidatorInitialization(unittest.TestCase):
    """Test CognitoValidator initialization and configuration."""
    
    def setUp(self):
        """Set up test configuration."""
        self.config = {
            "cognito_url": "http://localhost:8100/",
            "user_pool_id": "eu-west-1_TESTPOOL",
            "region": "eu-west-1",
            "jwt_algorithm": "RS256",
            "jwt_secret": "test-secret",
            "validation_strategy": "local_only",
            "environment": "localstack"
        }
    
    def test_initialization_with_config(self):
        """CognitoValidator initializes with provided config."""
        validator = CognitoValidator(self.config)
        
        self.assertEqual(validator.cognito_url, "http://localhost:8100/")
        self.assertEqual(validator.user_pool_id, "eu-west-1_TESTPOOL")
        self.assertEqual(validator.jwks_url, "http://localhost:8100/eu-west-1_TESTPOOL/.well-known/jwks.json")
        self.assertIsNone(validator._jwks_client)
    
    def test_jwks_client_starts_as_none(self):
        """JWKS client should be None on initialization (lazy loading)."""
        validator = CognitoValidator(self.config)
        self.assertIsNone(validator._jwks_client)



class TestJWKSClientCaching(unittest.TestCase):
    """Test JWKS client caching functionality (Issue #4 fix)."""
    
    def setUp(self):
        """Set up test configuration."""
        self.config = {
            "cognito_url": "http://localhost:8100/",
            "user_pool_id": "eu-west-1_TESTPOOL",
            "region": "eu-west-1",
            "jwt_algorithm": "RS256",
            "jwt_secret": "test-secret",
            "validation_strategy": "local_only",
            "environment": "localstack"
        }
        self.validator = CognitoValidator(self.config)
        
        # Create a test JWT token
        self.test_payload = {
            "username": "testuser",
            "cognito:groups": ["core_member"],
            "custom:organisation": "test-org",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iss": f"https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_TESTPOOL"
        }
    
    @patch('frank.util.auth.PyJWKClient')
    def test_jwks_client_created_on_first_use(self, mock_jwks_client_class):
        """JWKS client should be created on first token validation."""
        # Setup mock
        mock_client_instance = Mock()
        mock_jwks_client_class.return_value = mock_client_instance
        mock_signing_key = Mock()
        mock_signing_key.key = "mock-key"
        mock_client_instance.get_signing_key_from_jwt.return_value = mock_signing_key
        
        # Create a simple token (won't be validated, we're just testing client creation)
        token = jwt.encode(self.test_payload, "secret", algorithm="HS256")
        
        # Mock jwt.decode to avoid actual validation
        with patch('frank.util.auth.jwt.decode') as mock_decode:
            mock_decode.return_value = self.test_payload
            
            # Run the validation (async function needs to be run)
            import asyncio
            try:
                asyncio.run(self.validator.validate_token_locally(token))
            except:
                pass  # We don't care if it fails, we're testing client creation
        
        # Verify PyJWKClient was created with correct parameters
        mock_jwks_client_class.assert_called_once_with(
            "http://localhost:8100/eu-west-1_TESTPOOL/.well-known/jwks.json",
            cache_keys=True,
            lifespan=300
        )
        
        # Verify client instance is cached
        self.assertIsNotNone(self.validator._jwks_client)
    
    @patch('frank.util.auth.PyJWKClient')
    def test_jwks_client_reused_on_subsequent_calls(self, mock_jwks_client_class):
        """JWKS client should be reused on subsequent token validations."""
        # Setup mock
        mock_client_instance = Mock()
        mock_jwks_client_class.return_value = mock_client_instance
        mock_signing_key = Mock()
        mock_signing_key.key = "mock-key"
        mock_client_instance.get_signing_key_from_jwt.return_value = mock_signing_key
        
        token = jwt.encode(self.test_payload, "secret", algorithm="HS256")
        
        with patch('frank.util.auth.jwt.decode') as mock_decode:
            mock_decode.return_value = self.test_payload
            
            import asyncio
            # First call
            try:
                asyncio.run(self.validator.validate_token_locally(token))
            except:
                pass
            
            # Reset mock to check second call
            mock_jwks_client_class.reset_mock()
            
            # Second call
            try:
                asyncio.run(self.validator.validate_token_locally(token))
            except:
                pass
        
        # PyJWKClient should NOT be created again on second call
        mock_jwks_client_class.assert_not_called()


class TestCacheInvalidation(unittest.TestCase):
    """Test JWKS cache invalidation functionality."""
    
    def setUp(self):
        """Set up test configuration."""
        self.config = {
            "cognito_url": "http://localhost:8100/",
            "user_pool_id": "eu-west-1_TESTPOOL",
            "region": "eu-west-1",
            "jwt_algorithm": "RS256",
            "jwt_secret": "test-secret",
            "validation_strategy": "local_only",
            "environment": "localstack"
        }
        self.validator = CognitoValidator(self.config)
    
    def test_invalidate_cache_when_client_is_none(self):
        """Cache invalidation should handle None client gracefully."""
        self.assertIsNone(self.validator._jwks_client)
        self.validator.invalidate_jwks_cache()
        self.assertIsNone(self.validator._jwks_client)
    
    def test_invalidate_cache_clears_client(self):
        """Cache invalidation should set client to None."""
        # Simulate a cached client
        self.validator._jwks_client = Mock()
        self.assertIsNotNone(self.validator._jwks_client)
        
        # Invalidate
        self.validator.invalidate_jwks_cache()
        
        # Verify client is cleared
        self.assertIsNone(self.validator._jwks_client)


class TestTokenValidationHS256(unittest.TestCase):
    """Test token validation with HS256 algorithm."""
    
    def setUp(self):
        """Set up test configuration."""
        self.secret = "test-secret-key-for-hs256"
        self.config = {
            "cognito_url": "http://localhost:8100/",
            "user_pool_id": "eu-west-1_TESTPOOL",
            "region": "eu-west-1",
            "jwt_algorithm": "HS256",
            "jwt_secret": self.secret,
            "validation_strategy": "local_only",
            "environment": "localstack"
        }
        self.validator = CognitoValidator(self.config)
        
        self.test_payload = {
            "username": "testuser",
            "cognito:groups": ["core_member"],
            "custom:organisation": "test-org",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
    
    def test_validate_valid_hs256_token(self):
        """Valid HS256 token should be validated successfully."""
        token = jwt.encode(self.test_payload, self.secret, algorithm="HS256")
        
        import asyncio
        result = asyncio.run(self.validator.validate_token_locally(token))
        
        self.assertEqual(result["username"], "testuser")
        self.assertEqual(result["access_level"], AccessTier.CORE_MEMBER)
        self.assertEqual(result["organisation"], "test-org")
        self.assertTrue(result["token_valid"])
        self.assertEqual(result["validation_source"], "local_jwt")
    
    def test_validate_expired_token(self):
        """Expired token should raise UnauthorizedException."""
        expired_payload = self.test_payload.copy()
        expired_payload["exp"] = datetime.now(timezone.utc) - timedelta(hours=1)
        token = jwt.encode(expired_payload, self.secret, algorithm="HS256")
        
        import asyncio
        with self.assertRaises(UnauthorizedException) as context:
            asyncio.run(self.validator.validate_token_locally(token))
        
        self.assertIn("expired", str(context.exception.detail).lower())
    
    def test_validate_invalid_signature(self):
        """Token with invalid signature should raise UnauthorizedException."""
        token = jwt.encode(self.test_payload, "wrong-secret", algorithm="HS256")
        
        import asyncio
        with self.assertRaises(UnauthorizedException) as context:
            asyncio.run(self.validator.validate_token_locally(token))
        
        self.assertIn("invalid token", str(context.exception.detail).lower())
    
    def test_validate_token_missing_username(self):
        """Token without username should raise UnauthorizedException."""
        payload_no_username = {
            "cognito:groups": ["core_member"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        token = jwt.encode(payload_no_username, self.secret, algorithm="HS256")
        
        import asyncio
        with self.assertRaises(UnauthorizedException) as context:
            asyncio.run(self.validator.validate_token_locally(token))
        
        self.assertIn("missing username", str(context.exception.detail).lower())


class TestGetCurrentUser(unittest.TestCase):
    """Test get_current_user endpoint dependency."""
    
    def setUp(self):
        """Set up test configuration."""
        self.config = {
            "cognito_url": "http://localhost:8100/",
            "user_pool_id": "eu-west-1_TESTPOOL",
            "region": "eu-west-1",
            "jwt_algorithm": "HS256",
            "jwt_secret": "test-secret",
            "validation_strategy": "local_only",
            "environment": "localstack"
        }
        self.validator = CognitoValidator(self.config)
    
    def test_get_current_user_with_none_credentials(self):
        """get_current_user should raise UnauthorizedException if credentials are None."""
        import asyncio
        with self.assertRaises(UnauthorizedException) as context:
            asyncio.run(self.validator.get_current_user(None))
        
        self.assertIn("authentication required", str(context.exception.detail).lower())
    
    @patch('frank.util.auth.CognitoValidator.validate_token_locally')
    def test_get_current_user_local_only_strategy(self, mock_validate_local):
        """get_current_user should use only local validation for local_only strategy."""
        mock_validate_local.return_value = {
            "username": "testuser",
            "access_level": AccessTier.CORE_MEMBER,
            "token_valid": True,
            "validation_source": "local_jwt"
        }
        
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")
        
        import asyncio
        result = asyncio.run(self.validator.get_current_user(credentials))
        
        mock_validate_local.assert_called_once_with("test-token")
        self.assertEqual(result["username"], "testuser")
        self.assertEqual(result["validation_source"], "local_jwt")


class TestPerformanceOptimization(unittest.TestCase):
    """Test performance optimization through caching."""
    
    def setUp(self):
        """Set up test configuration."""
        self.config = {
            "cognito_url": "http://localhost:8100/",
            "user_pool_id": "eu-west-1_TESTPOOL",
            "region": "eu-west-1",
            "jwt_algorithm": "RS256",
            "jwt_secret": "test-secret",
            "validation_strategy": "local_only",
            "environment": "localstack"
        }
    
    @patch('frank.util.auth.PyJWKClient')
    def test_single_client_instance_for_multiple_validations(self, mock_jwks_client_class):
        """Single PyJWKClient instance should handle multiple token validations."""
        validator = CognitoValidator(self.config)
        
        # Setup mock
        mock_client_instance = Mock()
        mock_jwks_client_class.return_value = mock_client_instance
        mock_signing_key = Mock()
        mock_signing_key.key = "mock-key"
        mock_client_instance.get_signing_key_from_jwt.return_value = mock_signing_key
        
        test_payload = {
            "username": "testuser",
            "cognito:groups": ["core_member"],
            "custom:organisation": "test-org",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iss": f"https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_TESTPOOL"
        }
        
        token = jwt.encode(test_payload, "secret", algorithm="HS256")
        
        with patch('frank.util.auth.jwt.decode') as mock_decode:
            mock_decode.return_value = test_payload
            
            import asyncio
            # Simulate 5 requests
            for i in range(5):
                try:
                    asyncio.run(validator.validate_token_locally(token))
                except:
                    pass
        
        # PyJWKClient should be created only once
        self.assertEqual(mock_jwks_client_class.call_count, 1)
        
        # get_signing_key_from_jwt should be called 5 times (once per request)
        self.assertEqual(mock_client_instance.get_signing_key_from_jwt.call_count, 5)


if __name__ == "__main__":
    """Run all unit tests for authentication module."""
    unittest.main()
