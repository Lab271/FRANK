#!/usr/bin/env python3
"""
FRANK Platform - User and Member view models.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from dataclasses import dataclass
from typing import List, Tuple

from frank.admin.models import MemberDTO, MemberListResult, UserDTO, UserListResult


@dataclass
class UserViewModel:
    """View model for user display."""

    dto: UserDTO

    @property
    def username(self) -> str:
        """Username."""
        return self.dto.username

    @property
    def email(self) -> str:
        """Email address."""
        return self.dto.email

    @property
    def groups_display(self) -> str:
        """Groups as comma-separated string."""
        return ", ".join(self.dto.groups) if self.dto.groups else "-"

    @property
    def status_display(self) -> str:
        """Status as human-readable string."""
        return "Active" if self.dto.enabled else "Disabled"

    @property
    def is_active(self) -> bool:
        """Whether user is active."""
        return self.dto.enabled

    def to_table_row(self) -> Tuple[str, str, str, str]:
        """Convert to DataTable row tuple."""
        return (
            self.username,
            self.email,
            self.groups_display,
            self.status_display,
        )

    @classmethod
    def from_dto(cls, dto: UserDTO) -> "UserViewModel":
        """Create view model from DTO."""
        return cls(dto=dto)

    @classmethod
    def from_list_result(cls, result: UserListResult) -> List["UserViewModel"]:
        """Create list of view models from list result."""
        return [cls.from_dto(dto) for dto in result.users]


@dataclass
class MemberViewModel:
    """View model for member display."""

    dto: MemberDTO

    @property
    def username(self) -> str:
        """Username."""
        return self.dto.username

    @property
    def role_display(self) -> str:
        """Role as human-readable string."""
        role_map = {
            "member": "Member",
            "admin": "Admin",
            "owner": "Owner",
        }
        return role_map.get(self.dto.role, self.dto.role)

    @property
    def joined_display(self) -> str:
        """Joined date formatted for display."""
        if self.dto.joined_at:
            return self.dto.joined_at.strftime("%Y-%m-%d")
        return "-"

    def to_table_row(self) -> Tuple[str, str, str]:
        """Convert to DataTable row tuple."""
        return (
            self.username,
            self.role_display,
            self.joined_display,
        )

    @classmethod
    def from_dto(cls, dto: MemberDTO) -> "MemberViewModel":
        """Create view model from DTO."""
        return cls(dto=dto)

    @classmethod
    def from_list_result(cls, result: MemberListResult) -> List["MemberViewModel"]:
        """Create list of view models from list result."""
        return [cls.from_dto(dto) for dto in result.members]
