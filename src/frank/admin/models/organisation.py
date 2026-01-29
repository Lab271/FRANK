#!/usr/bin/env python3
"""
FRANK Platform - Organisation data models.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from frank.admin.models.base import parse_datetime


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
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
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
