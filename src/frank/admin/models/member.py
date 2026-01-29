#!/usr/bin/env python3
"""
FRANK Platform - Member data models.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from frank.admin.models.base import parse_datetime


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
            joined_at=parse_datetime(data.get("joined_at")),
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
