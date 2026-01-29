#!/usr/bin/env python3
"""
FRANK Platform - Cognito Service Abstraction

Provides an abstraction layer for user management via Cognito.
Supports both Mock Cognito (local development) and AWS Cognito (production).

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class CognitoServiceError(Exception):
    """Base exception for Cognito service errors"""

    def __init__(self, message: str, error_code: str = None, status_code: int = 500):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


class UserNotFoundError(CognitoServiceError):
    """Raised when a user is not found"""

    def __init__(self, username: str):
        super().__init__(f"User not found: {username}", "UserNotFound", 404)


class UserAlreadyExistsError(CognitoServiceError):
    """Raised when trying to create a user that already exists"""

    def __init__(self, username: str):
        super().__init__(f"User already exists: {username}", "UsernameExistsException", 409)


class MFASetupError(CognitoServiceError):
    """Raised when MFA setup fails"""

    def __init__(self, message: str):
        super().__init__(f"MFA setup failed: {message}", "MFASetupError", 400)


class MFAVerificationError(CognitoServiceError):
    """Raised when MFA verification fails"""

    def __init__(self, message: str):
        super().__init__(f"MFA verification failed: {message}", "MFAVerificationError", 400)


class BaseCognitoService(ABC):
    """
    Abstract base class for Cognito user management.

    Defines the interface for user CRUD operations that can be implemented
    by Mock Cognito (for local dev) or AWS Cognito (for production).
    """

    @abstractmethod
    async def create_user(
        self,
        username: str,
        email: str,
        password: Optional[str] = None,
        groups: List[str] = None,
        temporary_password: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new user in Cognito.

        Args:
            username: Unique username
            email: User email address
            password: Initial password (optional, auto-generated if not provided)
            groups: List of groups to add user to
            temporary_password: If True, user must change password on first login

        Returns:
            Dict containing user data

        Raises:
            UserAlreadyExistsError: If username already exists
            CognitoServiceError: For other errors
        """
        pass

    @abstractmethod
    async def get_user(self, username: str) -> Dict[str, Any]:
        """
        Get user information from Cognito.

        Args:
            username: Username to look up

        Returns:
            Dict containing user data

        Raises:
            UserNotFoundError: If user doesn't exist
            CognitoServiceError: For other errors
        """
        pass

    @abstractmethod
    async def update_user(
        self,
        username: str,
        email: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update user attributes in Cognito.

        Args:
            username: Username to update
            email: New email address (optional)
            enabled: Enable/disable user (optional)

        Returns:
            Dict containing updated user data

        Raises:
            UserNotFoundError: If user doesn't exist
            CognitoServiceError: For other errors
        """
        pass

    @abstractmethod
    async def delete_user(self, username: str) -> bool:
        """
        Delete a user from Cognito.

        Args:
            username: Username to delete

        Returns:
            True if deleted successfully

        Raises:
            UserNotFoundError: If user doesn't exist
            CognitoServiceError: For other errors
        """
        pass

    @abstractmethod
    async def list_users(
        self,
        limit: int = 60,
        pagination_token: str = None
    ) -> Dict[str, Any]:
        """
        List users in Cognito user pool.

        Args:
            limit: Maximum number of users to return
            pagination_token: Token for pagination

        Returns:
            Dict containing users list and optional pagination token
        """
        pass

    @abstractmethod
    async def add_user_to_group(self, username: str, group_name: str) -> bool:
        """
        Add a user to a Cognito group.

        Args:
            username: Username to add
            group_name: Group to add user to

        Returns:
            True if successful

        Raises:
            UserNotFoundError: If user doesn't exist
            CognitoServiceError: For other errors
        """
        pass

    @abstractmethod
    async def remove_user_from_group(self, username: str, group_name: str) -> bool:
        """
        Remove a user from a Cognito group.

        Args:
            username: Username to remove
            group_name: Group to remove user from

        Returns:
            True if successful

        Raises:
            UserNotFoundError: If user doesn't exist
            CognitoServiceError: For other errors
        """
        pass

    @abstractmethod
    async def get_user_groups(self, username: str) -> List[str]:
        """
        Get list of groups a user belongs to.

        Args:
            username: Username to look up

        Returns:
            List of group names

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        pass

    # ========== MFA Methods ==========

    @abstractmethod
    async def setup_mfa(self, username: str) -> Dict[str, Any]:
        """
        Start MFA enrollment for a user.

        Generates a TOTP secret and returns data needed for QR code.

        Args:
            username: Username to set up MFA for

        Returns:
            Dict containing:
                - secret: TOTP secret key
                - qr_code_uri: otpauth:// URI for QR code generation
                - issuer: App name for authenticator

        Raises:
            UserNotFoundError: If user doesn't exist
            MFASetupError: If MFA setup fails
        """
        pass

    @abstractmethod
    async def verify_mfa_setup(self, username: str, totp_code: str) -> bool:
        """
        Verify MFA setup with a TOTP code.

        Called after user scans QR code and enters verification code.

        Args:
            username: Username verifying MFA
            totp_code: 6-digit TOTP code from authenticator app

        Returns:
            True if verification successful and MFA is now enabled

        Raises:
            UserNotFoundError: If user doesn't exist
            MFAVerificationError: If code is invalid
        """
        pass

    @abstractmethod
    async def disable_mfa(self, username: str) -> bool:
        """
        Disable MFA for a user.

        Args:
            username: Username to disable MFA for

        Returns:
            True if MFA was disabled

        Raises:
            UserNotFoundError: If user doesn't exist
            CognitoServiceError: If operation fails
        """
        pass

    @abstractmethod
    async def get_mfa_status(self, username: str) -> Dict[str, Any]:
        """
        Get MFA status for a user.

        Args:
            username: Username to check

        Returns:
            Dict containing:
                - enabled: Whether MFA is enabled
                - mfa_type: Type of MFA (e.g., "TOTP") or None

        Raises:
            UserNotFoundError: If user doesn't exist
        """
        pass

    @abstractmethod
    async def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate a user with username and password.

        Args:
            username: Username to authenticate
            password: User's password

        Returns:
            Dict containing authentication result with tokens

        Raises:
            UserNotFoundError: If user doesn't exist
            CognitoServiceError: For authentication failures (wrong password, etc.)
        """
        pass

class MockCognitoService(BaseCognitoService):
    """
    Mock Cognito service that communicates with the Mock Cognito server.

    Used for local development and testing.
    """

    def __init__(self, base_url: str = None):
        """
        Initialize Mock Cognito service.

        Args:
            base_url: URL of Mock Cognito server (default from env or localhost:8100)
        """
        self.base_url = base_url or os.getenv("COGNITO_URL", "http://localhost:8100")
        if self.base_url.endswith("/"):
            self.base_url = self.base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=10.0)

    async def create_user(
        self,
        username: str,
        email: str,
        password: Optional[str] = None,
        groups: List[str] = None,
        temporary_password: bool = True
    ) -> Dict[str, Any]:
        """Create user via Mock Cognito admin API"""
        try:
            response = await self._client.post(
                f"{self.base_url}/admin/users",
                json={
                    "username": username,
                    "email": email,
                    "password": password or "TempPass123!",
                    "groups": groups or [],
                    "temporary_password": temporary_password
                }
            )

            if response.status_code == 409:
                raise UserAlreadyExistsError(username)
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CognitoServiceError(
                    error_data.get("message", "Failed to create user"),
                    error_data.get("__type", "UnknownError"),
                    response.status_code
                )

            return response.json()

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def get_user(self, username: str) -> Dict[str, Any]:
        """Get user via Mock Cognito admin API"""
        try:
            response = await self._client.get(
                f"{self.base_url}/admin/users/{username}"
            )

            if response.status_code == 404:
                raise UserNotFoundError(username)
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CognitoServiceError(
                    error_data.get("message", "Failed to get user"),
                    error_data.get("__type", "UnknownError"),
                    response.status_code
                )

            return response.json()

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def update_user(
        self,
        username: str,
        email: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update user via Mock Cognito admin API"""
        try:
            update_data = {}
            if email is not None:
                update_data["email"] = email
            if enabled is not None:
                update_data["enabled"] = enabled

            response = await self._client.put(
                f"{self.base_url}/admin/users/{username}",
                json=update_data
            )

            if response.status_code == 404:
                raise UserNotFoundError(username)
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CognitoServiceError(
                    error_data.get("message", "Failed to update user"),
                    error_data.get("__type", "UnknownError"),
                    response.status_code
                )

            return response.json()

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def delete_user(self, username: str) -> bool:
        """Delete user via Mock Cognito admin API"""
        try:
            response = await self._client.delete(
                f"{self.base_url}/admin/users/{username}"
            )

            if response.status_code == 404:
                raise UserNotFoundError(username)
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CognitoServiceError(
                    error_data.get("message", "Failed to delete user"),
                    error_data.get("__type", "UnknownError"),
                    response.status_code
                )

            return True

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def list_users(
        self,
        limit: int = 60,
        pagination_token: str = None
    ) -> Dict[str, Any]:
        """List users via Mock Cognito API"""
        try:
            # Mock Cognito provides a simple user list endpoint
            response = await self._client.get(f"{self.base_url}/auth/users")

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CognitoServiceError(
                    error_data.get("message", "Failed to list users"),
                    error_data.get("__type", "UnknownError"),
                    response.status_code
                )

            data = response.json()
            users = data.get("users", [])

            return {
                "users": users[:limit],
                "total": len(users)
            }

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def add_user_to_group(self, username: str, group_name: str) -> bool:
        """Add user to group via Mock Cognito admin API"""
        try:
            response = await self._client.post(
                f"{self.base_url}/admin/users/{username}/groups",
                json={"group": group_name}
            )

            if response.status_code == 404:
                raise UserNotFoundError(username)
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CognitoServiceError(
                    error_data.get("message", "Failed to add user to group"),
                    error_data.get("__type", "UnknownError"),
                    response.status_code
                )

            return True

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def remove_user_from_group(self, username: str, group_name: str) -> bool:
        """Remove user from group via Mock Cognito admin API"""
        try:
            response = await self._client.delete(
                f"{self.base_url}/admin/users/{username}/groups/{group_name}"
            )

            if response.status_code == 404:
                raise UserNotFoundError(username)
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CognitoServiceError(
                    error_data.get("message", "Failed to remove user from group"),
                    error_data.get("__type", "UnknownError"),
                    response.status_code
                )

            return True

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def get_user_groups(self, username: str) -> List[str]:
        """Get user groups from Mock Cognito"""
        user = await self.get_user(username)
        return user.get("groups", [])

    async def setup_mfa(self, username: str) -> Dict[str, Any]:
        """Start MFA enrollment via Mock Cognito"""
        try:
            response = await self._client.post(
                f"{self.base_url}/admin/users/{username}/mfa/setup"
            )

            if response.status_code == 404:
                raise UserNotFoundError(username)
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise MFASetupError(error_data.get("message", "Failed to setup MFA"))

            return response.json()

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def verify_mfa_setup(self, username: str, totp_code: str) -> bool:
        """Verify MFA setup via Mock Cognito"""
        try:
            response = await self._client.post(
                f"{self.base_url}/admin/users/{username}/mfa/verify",
                json={"totp_code": totp_code}
            )

            if response.status_code == 404:
                raise UserNotFoundError(username)
            elif response.status_code == 400:
                error_data = response.json() if response.content else {}
                raise MFAVerificationError(error_data.get("message", "Invalid TOTP code"))
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CognitoServiceError(
                    error_data.get("message", "Failed to verify MFA"),
                    error_data.get("__type", "UnknownError"),
                    response.status_code
                )

            return True

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def disable_mfa(self, username: str) -> bool:
        """Disable MFA via Mock Cognito"""
        try:
            response = await self._client.delete(
                f"{self.base_url}/admin/users/{username}/mfa"
            )

            if response.status_code == 404:
                raise UserNotFoundError(username)
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CognitoServiceError(
                    error_data.get("message", "Failed to disable MFA"),
                    error_data.get("__type", "UnknownError"),
                    response.status_code
                )

            return True

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def get_mfa_status(self, username: str) -> Dict[str, Any]:
        """Get MFA status via Mock Cognito"""
        try:
            response = await self._client.get(
                f"{self.base_url}/admin/users/{username}/mfa/status"
            )

            if response.status_code == 404:
                raise UserNotFoundError(username)
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CognitoServiceError(
                    error_data.get("message", "Failed to get MFA status"),
                    error_data.get("__type", "UnknownError"),
                    response.status_code
                )

            return response.json()

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user via Mock Cognito"""
        try:
            # Mock Cognito uses the standard Cognito InitiateAuth API
            response = await self._client.post(
                f"{self.base_url}/",
                headers={
                    "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
                    "Content-Type": "application/x-amz-json-1.1",
                },
                json={
                    "AuthFlow": "USER_PASSWORD_AUTH",
                    "AuthParameters": {
                        "USERNAME": username,
                        "PASSWORD": password
                    },
                    "ClientId": "mock-client-id"
                }
            )

            if response.status_code == 400:
                error_data = response.json() if response.content else {}
                error_type = error_data.get("__type", "")
                if "NotAuthorizedException" in error_type:
                    raise CognitoServiceError(
                        "Incorrect username or password",
                        "NotAuthorizedException",
                        401
                    )
                elif "UserNotFoundException" in error_type:
                    raise UserNotFoundError(username)
                raise CognitoServiceError(
                    error_data.get("message", "Authentication failed"),
                    error_type,
                    response.status_code
                )
            elif response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise CognitoServiceError(
                    error_data.get("message", "Authentication failed"),
                    error_data.get("__type", "UnknownError"),
                    response.status_code
                )

            return response.json()

        except httpx.RequestError as e:
            logger.error(f"Error connecting to Mock Cognito: {e}")
            raise CognitoServiceError(f"Could not connect to Cognito service: {e}")

    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()


class AWSCognitoService(BaseCognitoService):
    """
    AWS Cognito service using boto3.

    Used for production deployments.
    """

    def __init__(
        self,
        user_pool_id: str = None,
        region: str = None
    ):
        """
        Initialize AWS Cognito service.

        Args:
            user_pool_id: Cognito User Pool ID (default from env)
            region: AWS region (default from env)
        """
        import boto3

        self.user_pool_id = user_pool_id or os.getenv("USER_POOL_ID")
        self.region = region or os.getenv("AWS_REGION", os.getenv("REGION", "eu-west-1"))

        if not self.user_pool_id:
            raise ValueError("USER_POOL_ID environment variable or parameter required")

        self.client = boto3.client("cognito-idp", region_name=self.region)

    async def create_user(
        self,
        username: str,
        email: str,
        password: Optional[str] = None,
        groups: List[str] = None,
        temporary_password: bool = True
    ) -> Dict[str, Any]:
        """Create user in AWS Cognito"""
        try:
            # Create user with AdminCreateUser
            create_params = {
                "UserPoolId": self.user_pool_id,
                "Username": username,
                "UserAttributes": [
                    {"Name": "email", "Value": email},
                    {"Name": "email_verified", "Value": "true"}
                ],
                "MessageAction": "SUPPRESS"  # Don't send welcome email
            }

            if password:
                create_params["TemporaryPassword"] = password

            response = self.client.admin_create_user(**create_params)

            # Add user to groups
            if groups:
                for group in groups:
                    try:
                        self.client.admin_add_user_to_group(
                            UserPoolId=self.user_pool_id,
                            Username=username,
                            GroupName=group
                        )
                    except Exception as e:
                        logger.warning(f"Failed to add user to group {group}: {e}")

            user_data = response.get("User", {})
            return self._format_user_response(user_data, groups or [])

        except self.client.exceptions.UsernameExistsException:
            raise UserAlreadyExistsError(username)
        except Exception as e:
            logger.error(f"Error creating user in Cognito: {e}")
            raise CognitoServiceError(f"Failed to create user: {e}")

    async def get_user(self, username: str) -> Dict[str, Any]:
        """Get user from AWS Cognito"""
        try:
            response = self.client.admin_get_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )

            # Get user's groups
            groups_response = self.client.admin_list_groups_for_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )
            groups = [g["GroupName"] for g in groups_response.get("Groups", [])]

            return self._format_user_response(response, groups)

        except self.client.exceptions.UserNotFoundException:
            raise UserNotFoundError(username)
        except Exception as e:
            logger.error(f"Error getting user from Cognito: {e}")
            raise CognitoServiceError(f"Failed to get user: {e}")

    async def update_user(
        self,
        username: str,
        email: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update user in AWS Cognito"""
        try:
            # Update attributes if provided
            if email:
                self.client.admin_update_user_attributes(
                    UserPoolId=self.user_pool_id,
                    Username=username,
                    UserAttributes=[
                        {"Name": "email", "Value": email}
                    ]
                )

            # Enable/disable user if specified
            if enabled is not None:
                if enabled:
                    self.client.admin_enable_user(
                        UserPoolId=self.user_pool_id,
                        Username=username
                    )
                else:
                    self.client.admin_disable_user(
                        UserPoolId=self.user_pool_id,
                        Username=username
                    )

            # Return updated user data
            return await self.get_user(username)

        except self.client.exceptions.UserNotFoundException:
            raise UserNotFoundError(username)
        except Exception as e:
            logger.error(f"Error updating user in Cognito: {e}")
            raise CognitoServiceError(f"Failed to update user: {e}")

    async def delete_user(self, username: str) -> bool:
        """Delete user from AWS Cognito"""
        try:
            self.client.admin_delete_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )
            return True

        except self.client.exceptions.UserNotFoundException:
            raise UserNotFoundError(username)
        except Exception as e:
            logger.error(f"Error deleting user from Cognito: {e}")
            raise CognitoServiceError(f"Failed to delete user: {e}")

    async def list_users(
        self,
        limit: int = 60,
        pagination_token: str = None
    ) -> Dict[str, Any]:
        """List users from AWS Cognito"""
        try:
            params = {
                "UserPoolId": self.user_pool_id,
                "Limit": min(limit, 60)  # Cognito max is 60
            }
            if pagination_token:
                params["PaginationToken"] = pagination_token

            response = self.client.list_users(**params)

            users = []
            for user in response.get("Users", []):
                # Get groups for each user
                try:
                    groups_response = self.client.admin_list_groups_for_user(
                        UserPoolId=self.user_pool_id,
                        Username=user["Username"]
                    )
                    groups = [g["GroupName"] for g in groups_response.get("Groups", [])]
                except Exception:
                    groups = []

                users.append(self._format_user_response(user, groups))

            result = {
                "users": users,
                "total": len(users)
            }

            if "PaginationToken" in response:
                result["pagination_token"] = response["PaginationToken"]

            return result

        except Exception as e:
            logger.error(f"Error listing users from Cognito: {e}")
            raise CognitoServiceError(f"Failed to list users: {e}")

    async def add_user_to_group(self, username: str, group_name: str) -> bool:
        """Add user to group in AWS Cognito"""
        try:
            self.client.admin_add_user_to_group(
                UserPoolId=self.user_pool_id,
                Username=username,
                GroupName=group_name
            )
            return True

        except self.client.exceptions.UserNotFoundException:
            raise UserNotFoundError(username)
        except Exception as e:
            logger.error(f"Error adding user to group: {e}")
            raise CognitoServiceError(f"Failed to add user to group: {e}")

    async def remove_user_from_group(self, username: str, group_name: str) -> bool:
        """Remove user from group in AWS Cognito"""
        try:
            self.client.admin_remove_user_from_group(
                UserPoolId=self.user_pool_id,
                Username=username,
                GroupName=group_name
            )
            return True

        except self.client.exceptions.UserNotFoundException:
            raise UserNotFoundError(username)
        except Exception as e:
            logger.error(f"Error removing user from group: {e}")
            raise CognitoServiceError(f"Failed to remove user from group: {e}")

    async def get_user_groups(self, username: str) -> List[str]:
        """Get user groups from AWS Cognito"""
        try:
            response = self.client.admin_list_groups_for_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )
            return [g["GroupName"] for g in response.get("Groups", [])]

        except self.client.exceptions.UserNotFoundException:
            raise UserNotFoundError(username)
        except Exception as e:
            logger.error(f"Error getting user groups: {e}")
            raise CognitoServiceError(f"Failed to get user groups: {e}")

    async def setup_mfa(self, username: str) -> Dict[str, Any]:
        """
        Start MFA enrollment in AWS Cognito.

        Associates a software token (TOTP) with the user.
        """
        try:
            # First, get an access token for the user via admin auth
            # For TOTP setup, we use associate_software_token
            # This requires getting a session first via admin_initiate_auth

            # Get user to verify they exist
            await self.get_user(username)

            # For AWS Cognito, TOTP setup requires a user session
            # We'll generate a secret locally and store it as a custom attribute
            # then verify it when the user submits a code
            import pyotp

            # Generate a new TOTP secret
            secret = pyotp.random_base32()

            # Store the secret temporarily as a custom attribute (pending verification)
            self.client.admin_update_user_attributes(
                UserPoolId=self.user_pool_id,
                Username=username,
                UserAttributes=[
                    {"Name": "custom:mfa_secret_pending", "Value": secret}
                ]
            )

            # Create the otpauth URI for QR code
            totp = pyotp.TOTP(secret)
            issuer = "FRANK"
            qr_code_uri = totp.provisioning_uri(name=username, issuer_name=issuer)

            return {
                "secret": secret,
                "qr_code_uri": qr_code_uri,
                "issuer": issuer
            }

        except self.client.exceptions.UserNotFoundException:
            raise UserNotFoundError(username)
        except Exception as e:
            logger.error(f"Error setting up MFA: {e}")
            raise MFASetupError(str(e))

    async def verify_mfa_setup(self, username: str, totp_code: str) -> bool:
        """
        Verify MFA setup with a TOTP code in AWS Cognito.

        Validates the code against the pending secret and enables MFA.
        """
        try:
            import pyotp

            # Get the pending secret from user attributes
            response = self.client.admin_get_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )

            # Find the pending MFA secret
            secret = None
            for attr in response.get("UserAttributes", []):
                if attr["Name"] == "custom:mfa_secret_pending":
                    secret = attr["Value"]
                    break

            if not secret:
                raise MFAVerificationError("No pending MFA setup found")

            # Verify the TOTP code
            totp = pyotp.TOTP(secret)
            if not totp.verify(totp_code):
                raise MFAVerificationError("Invalid TOTP code")

            # Move secret from pending to active and enable MFA
            self.client.admin_update_user_attributes(
                UserPoolId=self.user_pool_id,
                Username=username,
                UserAttributes=[
                    {"Name": "custom:mfa_secret", "Value": secret},
                    {"Name": "custom:mfa_enabled", "Value": "true"},
                    {"Name": "custom:mfa_secret_pending", "Value": ""}  # Clear pending
                ]
            )

            # Set MFA preference to SOFTWARE_TOKEN_MFA
            self.client.admin_set_user_mfa_preference(
                UserPoolId=self.user_pool_id,
                Username=username,
                SoftwareTokenMfaSettings={
                    "Enabled": True,
                    "PreferredMfa": True
                }
            )

            logger.info(f"MFA enabled for user: {username}")
            return True

        except self.client.exceptions.UserNotFoundException:
            raise UserNotFoundError(username)
        except MFAVerificationError:
            raise
        except Exception as e:
            logger.error(f"Error verifying MFA: {e}")
            raise MFAVerificationError(str(e))

    async def disable_mfa(self, username: str) -> bool:
        """Disable MFA for a user in AWS Cognito"""
        try:
            # Clear MFA attributes
            self.client.admin_update_user_attributes(
                UserPoolId=self.user_pool_id,
                Username=username,
                UserAttributes=[
                    {"Name": "custom:mfa_secret", "Value": ""},
                    {"Name": "custom:mfa_enabled", "Value": "false"},
                    {"Name": "custom:mfa_secret_pending", "Value": ""}
                ]
            )

            # Disable MFA preference
            self.client.admin_set_user_mfa_preference(
                UserPoolId=self.user_pool_id,
                Username=username,
                SoftwareTokenMfaSettings={
                    "Enabled": False,
                    "PreferredMfa": False
                }
            )

            logger.info(f"MFA disabled for user: {username}")
            return True

        except self.client.exceptions.UserNotFoundException:
            raise UserNotFoundError(username)
        except Exception as e:
            logger.error(f"Error disabling MFA: {e}")
            raise CognitoServiceError(f"Failed to disable MFA: {e}")

    async def get_mfa_status(self, username: str) -> Dict[str, Any]:
        """Get MFA status for a user in AWS Cognito"""
        try:
            response = self.client.admin_get_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )

            # Check for MFA enabled attribute
            mfa_enabled = False
            for attr in response.get("UserAttributes", []):
                if attr["Name"] == "custom:mfa_enabled" and attr["Value"] == "true":
                    mfa_enabled = True
                    break

            return {
                "enabled": mfa_enabled,
                "mfa_type": "TOTP" if mfa_enabled else None
            }

        except self.client.exceptions.UserNotFoundException:
            raise UserNotFoundError(username)
        except Exception as e:
            logger.error(f"Error getting MFA status: {e}")
            raise CognitoServiceError(f"Failed to get MFA status: {e}")

    async def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user via AWS Cognito"""
        try:
            response = self.client.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=os.getenv("COGNITO_CLIENT_ID", ""),
                AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": username,
                    "PASSWORD": password
                }
            )

            auth_result = response.get("AuthenticationResult", {})
            return {
                "access_token": auth_result.get("AccessToken"),
                "refresh_token": auth_result.get("RefreshToken"),
                "id_token": auth_result.get("IdToken"),
                "token_type": auth_result.get("TokenType", "Bearer"),
                "expires_in": auth_result.get("ExpiresIn", 3600)
            }

        except self.client.exceptions.UserNotFoundException:
            raise UserNotFoundError(username)
        except self.client.exceptions.NotAuthorizedException:
            raise CognitoServiceError(
                "Incorrect username or password",
                "NotAuthorizedException",
                401
            )
        except self.client.exceptions.UserNotConfirmedException:
            raise CognitoServiceError(
                "User account not confirmed",
                "UserNotConfirmedException",
                401
            )
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            raise CognitoServiceError(f"Authentication failed: {e}")

    def _format_user_response(self, user_data: Dict[str, Any], groups: List[str]) -> Dict[str, Any]:
        """Format Cognito user data to standard response format"""
        # Extract attributes from Cognito format
        attributes = {}
        for attr in user_data.get("Attributes", user_data.get("UserAttributes", [])):
            attributes[attr["Name"]] = attr["Value"]

        return {
            "username": user_data.get("Username"),
            "email": attributes.get("email", ""),
            "groups": groups,
            "enabled": user_data.get("Enabled", True),
            "user_status": user_data.get("UserStatus"),
            "created_at": user_data.get("UserCreateDate"),
            "last_modified": user_data.get("UserLastModifiedDate")
        }


def get_cognito_service() -> BaseCognitoService:
    """
    Factory function to get appropriate Cognito service based on environment.

    Uses FRANK_AUTH_MODE environment variable:
    - "mock": Returns MockCognitoService (default)
    - "aws": Returns AWSCognitoService

    Returns:
        BaseCognitoService implementation
    """
    auth_mode = os.getenv("FRANK_AUTH_MODE", "mock").lower()

    if auth_mode == "aws":
        logger.info("Using AWS Cognito service")
        return AWSCognitoService()
    else:
        logger.info("Using Mock Cognito service")
        return MockCognitoService()
