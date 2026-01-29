#!/usr/bin/env python3
"""
FRANK Platform - Admin Data Transfer Objects

Dataclasses representing domain objects for the admin module.
These provide typed interfaces between services and views.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class OrganisationDTO:
    """Organisation data transfer object."""

    organisation_id: str
    name: str
    organisation_type: str
    sector: Optional[str] = None
    region: Optional[str] = None
    client_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "OrganisationDTO":
        """Create DTO from API response dict."""
        return cls(
            organisation_id=data.get("organisation_id", ""),
            name=data.get("name", ""),
            organisation_type=data.get("organisation_type", ""),
            sector=data.get("sector"),
            region=data.get("region"),
            client_count=data.get("client_count", 0),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )

    def to_dict(self) -> dict:
        """Convert to dict for API requests."""
        result = {
            "name": self.name,
            "organisation_type": self.organisation_type,
        }
        if self.sector:
            result["sector"] = self.sector
        if self.region:
            result["region"] = self.region
        return result


@dataclass
class OrganisationListResult:
    """Result of listing organisations."""

    organisations: List[OrganisationDTO]
    total: int

    @classmethod
    def from_dict(cls, data: dict) -> "OrganisationListResult":
        """Create from API response dict."""
        orgs = [OrganisationDTO.from_dict(o) for o in data.get("organisations", [])]
        return cls(organisations=orgs, total=data.get("total", len(orgs)))


@dataclass
class MemberDTO:
    """Organisation member data transfer object."""

    username: str
    role: str
    joined_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "MemberDTO":
        """Create DTO from API response dict."""
        return cls(
            username=data.get("username", ""),
            role=data.get("role", "member"),
            joined_at=_parse_datetime(data.get("joined_at")),
        )


@dataclass
class MemberListResult:
    """Result of listing members."""

    members: List[MemberDTO]
    total: int

    @classmethod
    def from_dict(cls, data: dict) -> "MemberListResult":
        """Create from API response dict."""
        members = [MemberDTO.from_dict(m) for m in data.get("members", [])]
        return cls(members=members, total=data.get("total", len(members)))


@dataclass
class UserDTO:
    """User data transfer object."""

    username: str
    email: str
    groups: List[str] = field(default_factory=list)
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "UserDTO":
        """Create DTO from API response dict."""
        return cls(
            username=data.get("username", ""),
            email=data.get("email", ""),
            groups=data.get("groups", []),
            enabled=data.get("enabled", True),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )

    @property
    def groups_display(self) -> str:
        """Get groups as comma-separated string for display."""
        return ", ".join(self.groups) if self.groups else "-"

    @property
    def status_display(self) -> str:
        """Get status as display string."""
        return "Active" if self.enabled else "Disabled"


@dataclass
class UserListResult:
    """Result of listing users."""

    users: List[UserDTO]
    total: int

    @classmethod
    def from_dict(cls, data: dict) -> "UserListResult":
        """Create from API response dict."""
        users = [UserDTO.from_dict(u) for u in data.get("users", [])]
        return cls(users=users, total=data.get("total", len(users)))


@dataclass
class HealthStatus:
    """API health status."""

    status: str
    database: str
    message: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "HealthStatus":
        """Create from API response dict."""
        return cls(
            status=data.get("status", "unknown"),
            database=data.get("database", "unknown"),
            message=data.get("message"),
        )

    @property
    def is_healthy(self) -> bool:
        """Check if all systems are healthy."""
        return self.status == "healthy" and self.database == "healthy"

    @property
    def display(self) -> str:
        """Get display string."""
        return f"API: {self.status} | DB: {self.database}"


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string."""
    if not value:
        return None
    try:
        # Handle ISO format with and without microseconds
        if "." in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
