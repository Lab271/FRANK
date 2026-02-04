#!/usr/bin/env python3
"""
FRANK Platform - Organisation Service

Service layer for organisation operations.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from typing import TYPE_CHECKING, Optional

from frank.admin.client import AdminClientError, ConflictError, NotFoundError
from frank.admin.models import (
    HealthStatus,
    MemberDTO,
    MemberListResult,
    OrganisationDTO,
    OrganisationListResult,
)
from frank.admin.services.base import ServiceResult

if TYPE_CHECKING:
    from frank.admin.client import AdminClient


class OrganisationService:
    """
    Organisation service.

    Handles CRUD operations for organisations and members.
    Provides a clean interface between views and the client.
    """

    def __init__(self, client: "AdminClient"):
        """
        Initialize organisation service.

        Args:
            client: Admin API client instance
        """
        self.client = client

    async def health_check(self) -> HealthStatus:
        """
        Check API health status.

        Returns:
            HealthStatus object
        """
        try:
            data = await self.client.health_check()
            return HealthStatus.from_dict(data)
        except AdminClientError as e:
            return HealthStatus(status="error", database="unknown", message=e.message)
        except Exception as e:
            return HealthStatus(status="error", database="unknown", message=str(e))

    async def list_organisations(
        self,
        organisation_type: Optional[str] = None,
        sector: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ServiceResult:
        """
        List organisations with optional filtering.

        Args:
            organisation_type: Filter by type (cyber_partner, customer)
            sector: Filter by sector
            limit: Maximum results
            offset: Pagination offset

        Returns:
            ServiceResult with OrganisationListResult on success
        """
        try:
            data = await self.client.list_organisations(
                organisation_type=organisation_type,
                sector=sector,
                limit=limit,
                offset=offset,
            )
            return ServiceResult.ok(OrganisationListResult.from_dict(data))
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    async def get_organisation(self, organisation_id: str) -> ServiceResult:
        """
        Get a specific organisation.

        Args:
            organisation_id: Organisation ID

        Returns:
            ServiceResult with OrganisationDTO on success
        """
        try:
            data = await self.client.get_organisation(organisation_id)
            return ServiceResult.ok(OrganisationDTO.from_dict(data))
        except NotFoundError:
            return ServiceResult.fail(f"Organisation not found: {organisation_id}")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    async def create_organisation(
        self,
        name: str,
        organisation_type: str,
        sector: Optional[str] = None,
        region: Optional[str] = None,
    ) -> ServiceResult:
        """
        Create a new organisation.

        Args:
            name: Organisation name
            organisation_type: Type (cyber_partner, customer)
            sector: Industry sector (optional)
            region: Geographic region (optional)

        Returns:
            ServiceResult with OrganisationDTO on success
        """
        if not name:
            return ServiceResult.fail("Organisation name is required")

        if organisation_type not in ("cyber_partner", "customer"):
            return ServiceResult.fail("Invalid organisation type")

        try:
            data = {
                "name": name,
                "organisation_type": organisation_type,
            }
            if sector:
                data["sector"] = sector
            if region:
                data["region"] = region

            result = await self.client.create_organisation(data)
            return ServiceResult.ok(OrganisationDTO.from_dict(result))
        except ConflictError:
            return ServiceResult.fail(f"Organisation already exists: {name}")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    async def update_organisation(
        self,
        organisation_id: str,
        name: Optional[str] = None,
        organisation_type: Optional[str] = None,
        sector: Optional[str] = None,
        region: Optional[str] = None,
    ) -> ServiceResult:
        """
        Update an organisation.

        Args:
            organisation_id: Organisation ID
            name: New name (optional)
            organisation_type: New type (optional)
            sector: New sector (optional)
            region: New region (optional)

        Returns:
            ServiceResult with OrganisationDTO on success
        """
        if organisation_type and organisation_type not in ("cyber_partner", "customer"):
            return ServiceResult.fail("Invalid organisation type")

        try:
            data = {}
            if name is not None:
                data["name"] = name
            if organisation_type is not None:
                data["organisation_type"] = organisation_type
            if sector is not None:
                data["sector"] = sector
            if region is not None:
                data["region"] = region

            if not data:
                return ServiceResult.fail("No fields to update")

            result = await self.client.update_organisation(organisation_id, data)
            return ServiceResult.ok(OrganisationDTO.from_dict(result))
        except NotFoundError:
            return ServiceResult.fail(f"Organisation not found: {organisation_id}")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    async def delete_organisation(self, organisation_id: str) -> ServiceResult:
        """
        Delete an organisation.

        Args:
            organisation_id: Organisation ID

        Returns:
            ServiceResult with success/failure
        """
        try:
            await self.client.delete_organisation(organisation_id)
            return ServiceResult.ok()
        except NotFoundError:
            return ServiceResult.fail(f"Organisation not found: {organisation_id}")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    # ========== Members ==========

    async def list_members(
        self,
        organisation_id: str,
        role: Optional[str] = None,
    ) -> ServiceResult:
        """
        List members of an organisation.

        Args:
            organisation_id: Organisation ID
            role: Filter by role (optional)

        Returns:
            ServiceResult with MemberListResult on success
        """
        try:
            data = await self.client.list_members(organisation_id, role=role)
            return ServiceResult.ok(MemberListResult.from_dict(data))
        except NotFoundError:
            return ServiceResult.fail(f"Organisation not found: {organisation_id}")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    async def add_member(
        self,
        organisation_id: str,
        username: str,
        role: str = "member",
    ) -> ServiceResult:
        """
        Add a member to an organisation.

        Args:
            organisation_id: Organisation ID
            username: Username to add
            role: Member role (default: member)

        Returns:
            ServiceResult with MemberDTO on success
        """
        if not username:
            return ServiceResult.fail("Username is required")

        if role not in ("member", "admin", "owner"):
            return ServiceResult.fail("Invalid role")

        try:
            data = await self.client.add_member(organisation_id, username, role)
            return ServiceResult.ok(MemberDTO.from_dict(data))
        except NotFoundError:
            return ServiceResult.fail("Organisation or user not found")
        except ConflictError:
            return ServiceResult.fail("User is already a member")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))

    async def remove_member(self, organisation_id: str, username: str) -> ServiceResult:
        """
        Remove a member from an organisation.

        Args:
            organisation_id: Organisation ID
            username: Username to remove

        Returns:
            ServiceResult with success/failure
        """
        try:
            await self.client.remove_member(organisation_id, username)
            return ServiceResult.ok()
        except NotFoundError:
            return ServiceResult.fail("Member not found")
        except AdminClientError as e:
            return ServiceResult.fail(e.message)
        except Exception as e:
            return ServiceResult.fail(str(e))
