#!/usr/bin/env python3
"""
Tests for FRANK Cognito Service abstraction.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from frank.management.cognito_service import (
    AWSCognitoService,
    BaseCognitoService,
    CognitoServiceError,
    MFASetupError,
    MFAVerificationError,
    MockCognitoService,
    UserAlreadyExistsError,
    UserNotFoundError,
    get_cognito_service,
)


class TestCognitoServiceErrors:
    """Tests for Cognito service exceptions."""

    def test_cognito_service_error_creation(self):
        """Test CognitoServiceError creation."""
        error = CognitoServiceError("Test error", "TestCode", 400)

        assert error.message == "Test error"
        assert error.error_code == "TestCode"
        assert error.status_code == 400
        assert str(error) == "Test error"

    def test_cognito_service_error_defaults(self):
        """Test CognitoServiceError with default values."""
        error = CognitoServiceError("Test error")

        assert error.message == "Test error"
        assert error.error_code is None
        assert error.status_code == 500

    def test_user_not_found_error(self):
        """Test UserNotFoundError creation."""
        error = UserNotFoundError("testuser")

        assert "testuser" in error.message
        assert error.error_code == "UserNotFound"
        assert error.status_code == 404

    def test_user_already_exists_error(self):
        """Test UserAlreadyExistsError creation."""
        error = UserAlreadyExistsError("existinguser")

        assert "existinguser" in error.message
        assert error.error_code == "UsernameExistsException"
        assert error.status_code == 409

    def test_mfa_setup_error(self):
        """Test MFASetupError creation."""
        error = MFASetupError("Failed to generate secret")

        assert "MFA setup failed" in error.message
        assert "Failed to generate secret" in error.message
        assert error.error_code == "MFASetupError"
        assert error.status_code == 400

    def test_mfa_verification_error(self):
        """Test MFAVerificationError creation."""
        error = MFAVerificationError("Invalid TOTP code")

        assert "MFA verification failed" in error.message
        assert "Invalid TOTP code" in error.message
        assert error.error_code == "MFAVerificationError"
        assert error.status_code == 400


class TestMockCognitoService:
    """Tests for MockCognitoService."""

    @pytest.fixture
    def mock_service(self):
        """Create MockCognitoService instance."""
        return MockCognitoService("http://localhost:8100")

    @pytest.fixture
    def mock_service_with_trailing_slash(self):
        """Create MockCognitoService with trailing slash in URL."""
        return MockCognitoService("http://localhost:8100/")

    def test_init_with_url(self, mock_service):
        """Test initialization with explicit URL."""
        assert mock_service.base_url == "http://localhost:8100"

    def test_init_with_trailing_slash(self, mock_service_with_trailing_slash):
        """Test trailing slash is removed from URL."""
        assert mock_service_with_trailing_slash.base_url == "http://localhost:8100"

    def test_init_from_environment(self):
        """Test initialization from environment variable."""
        with patch.dict(os.environ, {"COGNITO_URL": "http://env-cognito:9000"}):
            service = MockCognitoService()
            assert service.base_url == "http://env-cognito:9000"

    def test_init_default_url(self):
        """Test initialization with default URL."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove COGNITO_URL if present
            env = dict(os.environ)
            env.pop("COGNITO_URL", None)
            with patch.dict(os.environ, env, clear=True):
                service = MockCognitoService()
                assert service.base_url == "http://localhost:8100"

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_service):
        """Test successful user creation."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "username": "newuser",
                "email": "new@example.com",
                "groups": ["FRANK_OBSERVER"],
                "enabled": True
            }
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await mock_service.create_user(
                username="newuser",
                email="new@example.com",
                password="SecurePass123!",
                groups=["FRANK_OBSERVER"]
            )

            assert result["username"] == "newuser"
            assert result["email"] == "new@example.com"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_already_exists(self, mock_service):
        """Test user creation when user already exists."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 409
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(UserAlreadyExistsError):
                await mock_service.create_user(
                    username="existinguser",
                    email="existing@example.com"
                )

    @pytest.mark.asyncio
    async def test_create_user_other_error(self, mock_service):
        """Test user creation with server error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.content = b'{"message": "Server error"}'
            mock_response.json.return_value = {"message": "Server error", "__type": "InternalError"}
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(CognitoServiceError) as exc_info:
                await mock_service.create_user(
                    username="user",
                    email="user@example.com"
                )

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_create_user_connection_error(self, mock_service):
        """Test user creation with connection error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(CognitoServiceError) as exc_info:
                await mock_service.create_user(
                    username="user",
                    email="user@example.com"
                )

            assert "Could not connect" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_user_success(self, mock_service):
        """Test successful user retrieval."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "username": "testuser",
                "email": "test@example.com",
                "groups": ["FRANK_OBSERVER"],
                "enabled": True
            }
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await mock_service.get_user("testuser")

            assert result["username"] == "testuser"
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, mock_service):
        """Test user retrieval when user doesn't exist."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.get = AsyncMock(return_value=mock_response)

            with pytest.raises(UserNotFoundError):
                await mock_service.get_user("nonexistent")

    @pytest.mark.asyncio
    async def test_get_user_connection_error(self, mock_service):
        """Test user retrieval with connection error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(CognitoServiceError):
                await mock_service.get_user("testuser")

    @pytest.mark.asyncio
    async def test_update_user_success(self, mock_service):
        """Test successful user update."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "username": "testuser",
                "email": "newemail@example.com",
                "enabled": False
            }
            mock_client.put = AsyncMock(return_value=mock_response)

            result = await mock_service.update_user(
                "testuser",
                email="newemail@example.com",
                enabled=False
            )

            assert result["email"] == "newemail@example.com"

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, mock_service):
        """Test user update when user doesn't exist."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.put = AsyncMock(return_value=mock_response)

            with pytest.raises(UserNotFoundError):
                await mock_service.update_user("nonexistent", email="new@example.com")

    @pytest.mark.asyncio
    async def test_update_user_connection_error(self, mock_service):
        """Test user update with connection error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_client.put = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(CognitoServiceError):
                await mock_service.update_user("testuser", email="new@example.com")

    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_service):
        """Test successful user deletion."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_client.delete = AsyncMock(return_value=mock_response)

            result = await mock_service.delete_user("testuser")

            assert result is True

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, mock_service):
        """Test user deletion when user doesn't exist."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.delete = AsyncMock(return_value=mock_response)

            with pytest.raises(UserNotFoundError):
                await mock_service.delete_user("nonexistent")

    @pytest.mark.asyncio
    async def test_delete_user_connection_error(self, mock_service):
        """Test user deletion with connection error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_client.delete = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(CognitoServiceError):
                await mock_service.delete_user("testuser")

    @pytest.mark.asyncio
    async def test_list_users_success(self, mock_service):
        """Test listing users."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "users": [
                    {"username": "user1", "email": "user1@example.com"},
                    {"username": "user2", "email": "user2@example.com"}
                ]
            }
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await mock_service.list_users(limit=10)

            assert len(result["users"]) == 2
            assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_list_users_with_limit(self, mock_service):
        """Test listing users respects limit."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "users": [
                    {"username": f"user{i}", "email": f"user{i}@example.com"}
                    for i in range(10)
                ]
            }
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await mock_service.list_users(limit=5)

            assert len(result["users"]) == 5

    @pytest.mark.asyncio
    async def test_list_users_connection_error(self, mock_service):
        """Test listing users with connection error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(CognitoServiceError):
                await mock_service.list_users()

    @pytest.mark.asyncio
    async def test_add_user_to_group_success(self, mock_service):
        """Test adding user to group."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await mock_service.add_user_to_group("testuser", "FRANK_ADMIN")

            assert result is True

    @pytest.mark.asyncio
    async def test_add_user_to_group_not_found(self, mock_service):
        """Test adding non-existent user to group."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(UserNotFoundError):
                await mock_service.add_user_to_group("nonexistent", "FRANK_ADMIN")

    @pytest.mark.asyncio
    async def test_add_user_to_group_connection_error(self, mock_service):
        """Test adding user to group with connection error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(CognitoServiceError):
                await mock_service.add_user_to_group("testuser", "FRANK_ADMIN")

    @pytest.mark.asyncio
    async def test_remove_user_from_group_success(self, mock_service):
        """Test removing user from group."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.delete = AsyncMock(return_value=mock_response)

            result = await mock_service.remove_user_from_group("testuser", "FRANK_ADMIN")

            assert result is True

    @pytest.mark.asyncio
    async def test_remove_user_from_group_not_found(self, mock_service):
        """Test removing non-existent user from group."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.delete = AsyncMock(return_value=mock_response)

            with pytest.raises(UserNotFoundError):
                await mock_service.remove_user_from_group("nonexistent", "FRANK_ADMIN")

    @pytest.mark.asyncio
    async def test_remove_user_from_group_connection_error(self, mock_service):
        """Test removing user from group with connection error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_client.delete = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(CognitoServiceError):
                await mock_service.remove_user_from_group("testuser", "FRANK_ADMIN")

    @pytest.mark.asyncio
    async def test_get_user_groups(self, mock_service):
        """Test getting user groups."""
        with patch.object(mock_service, "get_user") as mock_get_user:
            mock_get_user.return_value = {
                "username": "testuser",
                "groups": ["FRANK_OBSERVER", "FRANK_ADMIN"]
            }

            result = await mock_service.get_user_groups("testuser")

            assert result == ["FRANK_OBSERVER", "FRANK_ADMIN"]

    @pytest.mark.asyncio
    async def test_close(self, mock_service):
        """Test closing the HTTP client."""
        with patch.object(mock_service._client, "aclose") as mock_close:
            mock_close.return_value = None
            await mock_service.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_default_password(self, mock_service):
        """Test user creation uses default password when not provided."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "username": "newuser",
                "email": "new@example.com",
                "groups": [],
                "enabled": True
            }
            mock_client.post = AsyncMock(return_value=mock_response)

            await mock_service.create_user(
                username="newuser",
                email="new@example.com"
                # No password provided
            )

            # Check that default password was used
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["password"] == "TempPass123!"

    # ========== MFA Tests ==========

    @pytest.mark.asyncio
    async def test_setup_mfa_success(self, mock_service):
        """Test successful MFA setup."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "secret": "JBSWY3DPEHPK3PXP",
                "qr_code_uri": "otpauth://totp/FRANK:testuser?secret=JBSWY3DPEHPK3PXP&issuer=FRANK",
                "issuer": "FRANK"
            }
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await mock_service.setup_mfa("testuser")

            assert result["secret"] == "JBSWY3DPEHPK3PXP"
            assert "qr_code_uri" in result
            assert result["issuer"] == "FRANK"

    @pytest.mark.asyncio
    async def test_setup_mfa_user_not_found(self, mock_service):
        """Test MFA setup for non-existent user."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(UserNotFoundError):
                await mock_service.setup_mfa("nonexistent")

    @pytest.mark.asyncio
    async def test_setup_mfa_error(self, mock_service):
        """Test MFA setup failure."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.content = b'{"message": "MFA already enabled"}'
            mock_response.json.return_value = {"message": "MFA already enabled"}
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(MFASetupError):
                await mock_service.setup_mfa("testuser")

    @pytest.mark.asyncio
    async def test_setup_mfa_connection_error(self, mock_service):
        """Test MFA setup with connection error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(CognitoServiceError):
                await mock_service.setup_mfa("testuser")

    @pytest.mark.asyncio
    async def test_verify_mfa_setup_success(self, mock_service):
        """Test successful MFA verification."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await mock_service.verify_mfa_setup("testuser", "123456")

            assert result is True

    @pytest.mark.asyncio
    async def test_verify_mfa_user_not_found(self, mock_service):
        """Test MFA verification for non-existent user."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(UserNotFoundError):
                await mock_service.verify_mfa_setup("nonexistent", "123456")

    @pytest.mark.asyncio
    async def test_verify_mfa_invalid_code(self, mock_service):
        """Test MFA verification with invalid code."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.content = b'{"message": "Invalid TOTP code"}'
            mock_response.json.return_value = {"message": "Invalid TOTP code"}
            mock_client.post = AsyncMock(return_value=mock_response)

            with pytest.raises(MFAVerificationError):
                await mock_service.verify_mfa_setup("testuser", "000000")

    @pytest.mark.asyncio
    async def test_verify_mfa_connection_error(self, mock_service):
        """Test MFA verification with connection error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(CognitoServiceError):
                await mock_service.verify_mfa_setup("testuser", "123456")

    @pytest.mark.asyncio
    async def test_disable_mfa_success(self, mock_service):
        """Test successful MFA disable."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.delete = AsyncMock(return_value=mock_response)

            result = await mock_service.disable_mfa("testuser")

            assert result is True

    @pytest.mark.asyncio
    async def test_disable_mfa_user_not_found(self, mock_service):
        """Test disabling MFA for non-existent user."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.delete = AsyncMock(return_value=mock_response)

            with pytest.raises(UserNotFoundError):
                await mock_service.disable_mfa("nonexistent")

    @pytest.mark.asyncio
    async def test_disable_mfa_connection_error(self, mock_service):
        """Test disabling MFA with connection error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_client.delete = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(CognitoServiceError):
                await mock_service.disable_mfa("testuser")

    @pytest.mark.asyncio
    async def test_get_mfa_status_enabled(self, mock_service):
        """Test getting MFA status when enabled."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "enabled": True,
                "mfa_type": "TOTP"
            }
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await mock_service.get_mfa_status("testuser")

            assert result["enabled"] is True
            assert result["mfa_type"] == "TOTP"

    @pytest.mark.asyncio
    async def test_get_mfa_status_disabled(self, mock_service):
        """Test getting MFA status when disabled."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "enabled": False,
                "mfa_type": None
            }
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await mock_service.get_mfa_status("testuser")

            assert result["enabled"] is False
            assert result["mfa_type"] is None

    @pytest.mark.asyncio
    async def test_get_mfa_status_user_not_found(self, mock_service):
        """Test getting MFA status for non-existent user."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.get = AsyncMock(return_value=mock_response)

            with pytest.raises(UserNotFoundError):
                await mock_service.get_mfa_status("nonexistent")

    @pytest.mark.asyncio
    async def test_get_mfa_status_connection_error(self, mock_service):
        """Test getting MFA status with connection error."""
        with patch.object(mock_service, "_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

            with pytest.raises(CognitoServiceError):
                await mock_service.get_mfa_status("testuser")


class TestAWSCognitoService:
    """Tests for AWSCognitoService."""

    @pytest.fixture
    def mock_boto3_client(self):
        """Mock boto3 client for AWS Cognito tests."""
        mock_client = MagicMock()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Store original boto3 if present
        original = sys.modules.get("boto3")

        # Install mock
        sys.modules["boto3"] = mock_boto3

        yield mock_client, mock_boto3

        # Restore original
        if original is not None:
            sys.modules["boto3"] = original
        else:
            sys.modules.pop("boto3", None)

    def test_init_with_parameters(self, mock_boto3_client):
        """Test initialization with explicit parameters."""
        mock_client, _ = mock_boto3_client

        service = AWSCognitoService(
            user_pool_id="us-east-1_TESTPOOL",
            region="us-east-1"
        )

        assert service.user_pool_id == "us-east-1_TESTPOOL"
        assert service.region == "us-east-1"

    def test_init_from_environment(self, mock_boto3_client):
        """Test initialization from environment variables."""
        with patch.dict(os.environ, {
            "USER_POOL_ID": "eu-west-1_ENVPOOL",
            "AWS_REGION": "eu-west-1"
        }):
            service = AWSCognitoService()
            assert service.user_pool_id == "eu-west-1_ENVPOOL"
            assert service.region == "eu-west-1"

    def test_init_missing_user_pool_id(self, mock_boto3_client):
        """Test initialization fails without user pool ID."""
        with patch.dict(os.environ, {}, clear=True):
            env = dict(os.environ)
            env.pop("USER_POOL_ID", None)
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(ValueError, match="USER_POOL_ID"):
                    AWSCognitoService()

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_boto3_client):
        """Test successful user creation in AWS Cognito."""
        mock_client, _ = mock_boto3_client
        mock_client.admin_create_user.return_value = {
            "User": {
                "Username": "newuser",
                "Attributes": [
                    {"Name": "email", "Value": "new@example.com"}
                ],
                "Enabled": True,
                "UserStatus": "FORCE_CHANGE_PASSWORD"
            }
        }

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.create_user(
            username="newuser",
            email="new@example.com",
            groups=["FRANK_OBSERVER"]
        )

        assert result["username"] == "newuser"
        mock_client.admin_add_user_to_group.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_already_exists(self, mock_boto3_client):
        """Test user creation when user already exists."""
        mock_client, _ = mock_boto3_client
        mock_client.exceptions.UsernameExistsException = type("UsernameExistsException", (Exception,), {})
        mock_client.admin_create_user.side_effect = mock_client.exceptions.UsernameExistsException()

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")

        with pytest.raises(UserAlreadyExistsError):
            await service.create_user(username="existing", email="existing@example.com")

    @pytest.mark.asyncio
    async def test_get_user_success(self, mock_boto3_client):
        """Test successful user retrieval from AWS Cognito."""
        mock_client, _ = mock_boto3_client
        mock_client.admin_get_user.return_value = {
            "Username": "testuser",
            "UserAttributes": [
                {"Name": "email", "Value": "test@example.com"}
            ],
            "Enabled": True
        }
        mock_client.admin_list_groups_for_user.return_value = {
            "Groups": [{"GroupName": "FRANK_OBSERVER"}]
        }

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.get_user("testuser")

        assert result["username"] == "testuser"
        assert result["groups"] == ["FRANK_OBSERVER"]

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, mock_boto3_client):
        """Test user retrieval when user doesn't exist."""
        mock_client, _ = mock_boto3_client
        mock_client.exceptions.UserNotFoundException = type("UserNotFoundException", (Exception,), {})
        mock_client.admin_get_user.side_effect = mock_client.exceptions.UserNotFoundException()

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")

        with pytest.raises(UserNotFoundError):
            await service.get_user("nonexistent")

    @pytest.mark.asyncio
    async def test_update_user_success(self, mock_boto3_client):
        """Test successful user update."""
        mock_client, _ = mock_boto3_client
        mock_client.admin_get_user.return_value = {
            "Username": "testuser",
            "UserAttributes": [{"Name": "email", "Value": "new@example.com"}],
            "Enabled": False
        }
        mock_client.admin_list_groups_for_user.return_value = {"Groups": []}

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.update_user("testuser", email="new@example.com", enabled=False)

        mock_client.admin_update_user_attributes.assert_called_once()
        mock_client.admin_disable_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_enable(self, mock_boto3_client):
        """Test enabling a user."""
        mock_client, _ = mock_boto3_client
        mock_client.admin_get_user.return_value = {
            "Username": "testuser",
            "UserAttributes": [],
            "Enabled": True
        }
        mock_client.admin_list_groups_for_user.return_value = {"Groups": []}

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        await service.update_user("testuser", enabled=True)

        mock_client.admin_enable_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_boto3_client):
        """Test successful user deletion."""
        mock_client, _ = mock_boto3_client

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.delete_user("testuser")

        assert result is True
        mock_client.admin_delete_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_users_success(self, mock_boto3_client):
        """Test listing users."""
        mock_client, _ = mock_boto3_client
        mock_client.list_users.return_value = {
            "Users": [
                {
                    "Username": "user1",
                    "Attributes": [{"Name": "email", "Value": "user1@example.com"}],
                    "Enabled": True
                }
            ]
        }
        mock_client.admin_list_groups_for_user.return_value = {"Groups": []}

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.list_users(limit=10)

        assert len(result["users"]) == 1

    @pytest.mark.asyncio
    async def test_list_users_with_pagination(self, mock_boto3_client):
        """Test listing users with pagination token."""
        mock_client, _ = mock_boto3_client
        mock_client.list_users.return_value = {
            "Users": [],
            "PaginationToken": "next-page-token"
        }

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.list_users(pagination_token="prev-token")

        assert "pagination_token" in result

    @pytest.mark.asyncio
    async def test_add_user_to_group_success(self, mock_boto3_client):
        """Test adding user to group."""
        mock_client, _ = mock_boto3_client

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.add_user_to_group("testuser", "FRANK_ADMIN")

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_user_from_group_success(self, mock_boto3_client):
        """Test removing user from group."""
        mock_client, _ = mock_boto3_client

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.remove_user_from_group("testuser", "FRANK_ADMIN")

        assert result is True

    @pytest.mark.asyncio
    async def test_get_user_groups_success(self, mock_boto3_client):
        """Test getting user groups."""
        mock_client, _ = mock_boto3_client
        mock_client.admin_list_groups_for_user.return_value = {
            "Groups": [
                {"GroupName": "FRANK_OBSERVER"},
                {"GroupName": "FRANK_ADMIN"}
            ]
        }

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.get_user_groups("testuser")

        assert result == ["FRANK_OBSERVER", "FRANK_ADMIN"]

    def test_format_user_response(self, mock_boto3_client):
        """Test user response formatting."""
        mock_client, _ = mock_boto3_client

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")

        user_data = {
            "Username": "testuser",
            "Attributes": [
                {"Name": "email", "Value": "test@example.com"}
            ],
            "Enabled": True,
            "UserStatus": "CONFIRMED"
        }

        result = service._format_user_response(user_data, ["FRANK_ADMIN"])

        assert result["username"] == "testuser"
        assert result["email"] == "test@example.com"
        assert result["groups"] == ["FRANK_ADMIN"]
        assert result["enabled"] is True

    # ========== AWS MFA Tests ==========

    @pytest.mark.asyncio
    async def test_setup_mfa_success(self, mock_boto3_client):
        """Test MFA setup in AWS Cognito."""
        mock_client, _ = mock_boto3_client
        mock_client.admin_get_user.return_value = {
            "Username": "testuser",
            "UserAttributes": []
        }
        mock_client.admin_list_groups_for_user.return_value = {"Groups": []}

        # pyotp is imported locally inside setup_mfa, so we use builtins.__import__
        import pyotp
        with patch.object(pyotp, "random_base32", return_value="JBSWY3DPEHPK3PXP"):
            service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
            result = await service.setup_mfa("testuser")

            assert result["secret"] == "JBSWY3DPEHPK3PXP"
            assert "qr_code_uri" in result
            assert result["issuer"] == "FRANK"
            mock_client.admin_update_user_attributes.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_mfa_user_not_found(self, mock_boto3_client):
        """Test MFA setup for non-existent user."""
        mock_client, _ = mock_boto3_client
        mock_client.exceptions.UserNotFoundException = type("UserNotFoundException", (Exception,), {})
        mock_client.admin_get_user.side_effect = mock_client.exceptions.UserNotFoundException()
        mock_client.admin_list_groups_for_user.side_effect = mock_client.exceptions.UserNotFoundException()

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")

        # setup_mfa catches UserNotFoundError and re-raises as MFASetupError
        with pytest.raises(MFASetupError):
            await service.setup_mfa("nonexistent")

    @pytest.mark.asyncio
    async def test_verify_mfa_setup_success(self, mock_boto3_client):
        """Test successful MFA verification in AWS Cognito."""
        mock_client, _ = mock_boto3_client
        mock_client.admin_get_user.return_value = {
            "Username": "testuser",
            "UserAttributes": [
                {"Name": "custom:mfa_secret_pending", "Value": "JBSWY3DPEHPK3PXP"}
            ]
        }

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        # Use real pyotp with a valid code for the test secret
        import pyotp
        totp = pyotp.TOTP("JBSWY3DPEHPK3PXP")
        valid_code = totp.now()

        result = await service.verify_mfa_setup("testuser", valid_code)

        assert result is True
        mock_client.admin_update_user_attributes.assert_called()
        mock_client.admin_set_user_mfa_preference.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_mfa_no_pending_secret(self, mock_boto3_client):
        """Test MFA verification when no pending secret exists."""
        mock_client, _ = mock_boto3_client
        mock_client.admin_get_user.return_value = {
            "Username": "testuser",
            "UserAttributes": []  # No pending secret
        }
        # Set up exception class for the mock client
        mock_client.exceptions.UserNotFoundException = type("UserNotFoundException", (Exception,), {})

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")

        with pytest.raises(MFAVerificationError, match="No pending MFA setup"):
            await service.verify_mfa_setup("testuser", "123456")

    @pytest.mark.asyncio
    async def test_verify_mfa_invalid_code(self, mock_boto3_client):
        """Test MFA verification with invalid TOTP code."""
        mock_client, _ = mock_boto3_client
        mock_client.admin_get_user.return_value = {
            "Username": "testuser",
            "UserAttributes": [
                {"Name": "custom:mfa_secret_pending", "Value": "JBSWY3DPEHPK3PXP"}
            ]
        }
        # Set up exception class for the mock client
        mock_client.exceptions.UserNotFoundException = type("UserNotFoundException", (Exception,), {})

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")

        with pytest.raises(MFAVerificationError, match="Invalid TOTP code"):
            await service.verify_mfa_setup("testuser", "000000")

    @pytest.mark.asyncio
    async def test_disable_mfa_success(self, mock_boto3_client):
        """Test disabling MFA in AWS Cognito."""
        mock_client, _ = mock_boto3_client

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.disable_mfa("testuser")

        assert result is True
        mock_client.admin_update_user_attributes.assert_called_once()
        mock_client.admin_set_user_mfa_preference.assert_called_once()

    @pytest.mark.asyncio
    async def test_disable_mfa_user_not_found(self, mock_boto3_client):
        """Test disabling MFA for non-existent user."""
        mock_client, _ = mock_boto3_client
        mock_client.exceptions.UserNotFoundException = type("UserNotFoundException", (Exception,), {})
        mock_client.admin_update_user_attributes.side_effect = mock_client.exceptions.UserNotFoundException()

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")

        with pytest.raises(UserNotFoundError):
            await service.disable_mfa("nonexistent")

    @pytest.mark.asyncio
    async def test_get_mfa_status_enabled(self, mock_boto3_client):
        """Test getting MFA status when enabled."""
        mock_client, _ = mock_boto3_client
        mock_client.admin_get_user.return_value = {
            "Username": "testuser",
            "UserAttributes": [
                {"Name": "custom:mfa_enabled", "Value": "true"}
            ]
        }

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.get_mfa_status("testuser")

        assert result["enabled"] is True
        assert result["mfa_type"] == "TOTP"

    @pytest.mark.asyncio
    async def test_get_mfa_status_disabled(self, mock_boto3_client):
        """Test getting MFA status when disabled."""
        mock_client, _ = mock_boto3_client
        mock_client.admin_get_user.return_value = {
            "Username": "testuser",
            "UserAttributes": []  # No MFA enabled attribute
        }

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")
        result = await service.get_mfa_status("testuser")

        assert result["enabled"] is False
        assert result["mfa_type"] is None

    @pytest.mark.asyncio
    async def test_get_mfa_status_user_not_found(self, mock_boto3_client):
        """Test getting MFA status for non-existent user."""
        mock_client, _ = mock_boto3_client
        mock_client.exceptions.UserNotFoundException = type("UserNotFoundException", (Exception,), {})
        mock_client.admin_get_user.side_effect = mock_client.exceptions.UserNotFoundException()

        service = AWSCognitoService(user_pool_id="test-pool", region="eu-west-1")

        with pytest.raises(UserNotFoundError):
            await service.get_mfa_status("nonexistent")


class TestGetCognitoService:
    """Tests for get_cognito_service factory function."""

    def test_returns_mock_by_default(self):
        """Test factory returns Mock service by default."""
        with patch.dict(os.environ, {"FRANK_AUTH_MODE": "mock"}):
            service = get_cognito_service()
            assert isinstance(service, MockCognitoService)

    def test_returns_mock_when_not_set(self):
        """Test factory returns Mock service when env not set."""
        with patch.dict(os.environ, {}, clear=True):
            env = dict(os.environ)
            env.pop("FRANK_AUTH_MODE", None)
            with patch.dict(os.environ, env, clear=True):
                service = get_cognito_service()
                assert isinstance(service, MockCognitoService)

    def test_returns_aws_when_configured(self):
        """Test factory returns AWS service when configured."""
        # Install mock boto3 in sys.modules
        mock_boto3 = MagicMock()
        original = sys.modules.get("boto3")
        sys.modules["boto3"] = mock_boto3

        try:
            with patch.dict(os.environ, {
                "FRANK_AUTH_MODE": "aws",
                "USER_POOL_ID": "eu-west-1_TEST"
            }):
                service = get_cognito_service()
                assert isinstance(service, AWSCognitoService)
        finally:
            if original is not None:
                sys.modules["boto3"] = original
            else:
                sys.modules.pop("boto3", None)

    def test_case_insensitive_mode(self):
        """Test auth mode is case insensitive."""
        # Install mock boto3 in sys.modules
        mock_boto3 = MagicMock()
        original = sys.modules.get("boto3")
        sys.modules["boto3"] = mock_boto3

        try:
            with patch.dict(os.environ, {
                "FRANK_AUTH_MODE": "AWS",
                "USER_POOL_ID": "eu-west-1_TEST"
            }):
                service = get_cognito_service()
                assert isinstance(service, AWSCognitoService)
        finally:
            if original is not None:
                sys.modules["boto3"] = original
            else:
                sys.modules.pop("boto3", None)
