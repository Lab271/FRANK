#!/usr/bin/env python3
"""
FRANK Platform - User Service

Service layer for user operations.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from typing import TYPE_CHECKING, List, Optional

from frank.admin.client import AdminClientError, ConflictError, NotFoundError
from frank.admin.models import UserDTO, UserListResult
from frank.admin.services.base import ServiceResult

if TYPE_CHECKING:
    from frank.admin.client import AdminClient


class UserService:
    """
    User service.

    Handles CRUD operations for users.
    Provides a clean interface between views and the client.
    """

    def __init__(self, client: "AdminClient"):
        """
        Initialize user service.

        Args:
            client: Admin API client instance
        """
        self.client = client

    async def list_users(self, organisation_id: str) -> ServiceResult:
        """
        List users in an organisation.

        Args:
            organisation_id: Organisation ID

        Returns:
            ServiceResult with UserListResult on success
        """
        if not organisation_id:
            return ServiceResult.fail("Organisation ID is required")

        try:
            data = await self.client.list_users(organisation_id)
            return ServiceResult.ok(UserListResult.from_dict(data))
        except NotFoundError:
            return ServiceResult.fail(f"Organisation not found: {organisation_id}")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    async def get_user(self, username: str) -> ServiceResult:
        """
        Get a specific user.

        Args:
            username: Username

        Returns:
            ServiceResult with UserDTO on success
        """
        if not username:
            return ServiceResult.fail("Username is required")

        try:
            data = await self.client.get_user(username)
            return ServiceResult.ok(UserDTO.from_dict(data))
        except NotFoundError:
            return ServiceResult.fail(f"User not found: {username}")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    async def create_user(
        self,
        organisation_id: str,
        username: str,
        email: str,
        password: Optional[str] = None,
        groups: Optional[List[str]] = None,
    ) -> ServiceResult:
        """
        Create a new user in an organisation.

        Args:
            organisation_id: Organisation ID
            username: Username
            email: Email address
            password: Initial password (optional)
            groups: Groups to assign (optional)

        Returns:
            ServiceResult with UserDTO on success
        """
        if not organisation_id:
            return ServiceResult.fail("Organisation ID is required")
        if not username:
            return ServiceResult.fail("Username is required")
        if not email:
            return ServiceResult.fail("Email is required")

        # Validate email format (basic check)
        if "@" not in email:
            return ServiceResult.fail("Invalid email format")

        # Validate groups if provided
        valid_groups = {
            "FRANK_OBSERVER",
            "FRANK_CONTRIBUTOR",
            "FRANK_PARTNER",
            "FRANK_CORE_MEMBER",
        }
        if groups:
            invalid = set(groups) - valid_groups
            if invalid:
                return ServiceResult.fail(f"Invalid groups: {', '.join(invalid)}")

        try:
            data = await self.client.create_user(
                organisation_id=organisation_id,
                username=username,
                email=email,
                password=password,
                groups=groups,
            )
            return ServiceResult.ok(UserDTO.from_dict(data))
        except ConflictError:
            return ServiceResult.fail(f"User already exists: {username}")
        except NotFoundError:
            return ServiceResult.fail(f"Organisation not found: {organisation_id}")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    async def update_user(
        self,
        username: str,
        email: Optional[str] = None,
        enabled: Optional[bool] = None,
        groups: Optional[List[str]] = None,
    ) -> ServiceResult:
        """
        Update a user.

        Args:
            username: Username
            email: New email (optional)
            enabled: New enabled status (optional)
            groups: New groups (optional)

        Returns:
            ServiceResult with UserDTO on success
        """
        if not username:
            return ServiceResult.fail("Username is required")

        # Validate email format if provided
        if email is not None and "@" not in email:
            return ServiceResult.fail("Invalid email format")

        # Validate groups if provided
        valid_groups = {
            "FRANK_OBSERVER",
            "FRANK_CONTRIBUTOR",
            "FRANK_PARTNER",
            "FRANK_CORE_MEMBER",
        }
        if groups:
            invalid = set(groups) - valid_groups
            if invalid:
                return ServiceResult.fail(f"Invalid groups: {', '.join(invalid)}")

        # Check if there's anything to update
        if email is None and enabled is None and groups is None:
            return ServiceResult.fail("No fields to update")

        try:
            data = await self.client.update_user(
                username=username,
                email=email,
                enabled=enabled,
                groups=groups,
            )
            return ServiceResult.ok(UserDTO.from_dict(data))
        except NotFoundError:
            return ServiceResult.fail(f"User not found: {username}")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    async def delete_user(self, username: str) -> ServiceResult:
        """
        Delete a user.

        Args:
            username: Username

        Returns:
            ServiceResult with success/failure
        """
        if not username:
            return ServiceResult.fail("Username is required")

        try:
            await self.client.delete_user(username)
            return ServiceResult.ok()
        except NotFoundError:
            return ServiceResult.fail(f"User not found: {username}")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    async def disable_user(self, username: str) -> ServiceResult:
        """
        Disable a user.

        Args:
            username: Username

        Returns:
            ServiceResult with UserDTO on success
        """
        return await self.update_user(username, enabled=False)

    async def enable_user(self, username: str) -> ServiceResult:
        """
        Enable a user.

        Args:
            username: Username

        Returns:
            ServiceResult with UserDTO on success
        """
        return await self.update_user(username, enabled=True)

    def parse_groups(self, groups_str: str) -> List[str]:
        """
        Parse comma-separated groups string.

        Args:
            groups_str: Comma-separated groups string

        Returns:
            List of group names
        """
        if not groups_str:
            return []
        return [g.strip() for g in groups_str.split(",") if g.strip()]
