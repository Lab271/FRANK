#!/usr/bin/env python3
"""
FRANK Platform - User data models.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from frank.admin.models.base import parse_datetime


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
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
        )


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
