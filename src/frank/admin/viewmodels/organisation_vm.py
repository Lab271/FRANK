#!/usr/bin/env python3
"""
FRANK Platform - Organisation view model.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from dataclasses import dataclass
from typing import List, Tuple

from frank.admin.models import OrganisationDTO, OrganisationListResult


@dataclass
class OrganisationViewModel:
    """View model for organisation display."""

    dto: OrganisationDTO

    @property
    def id(self) -> str:
        """Organisation ID."""
        return self.dto.organisation_id

    @property
    def name(self) -> str:
        """Organisation name."""
        return self.dto.name

    @property
    def type_display(self) -> str:
        """Human-readable organisation type."""
        type_map = {
            "customer": "Customer",
            "cyber_partner": "Cyber Partner",
        }
        return type_map.get(self.dto.organisation_type, self.dto.organisation_type)

    @property
    def sector_display(self) -> str:
        """Sector or placeholder."""
        return self.dto.sector or "-"

    @property
    def region_display(self) -> str:
        """Region or placeholder."""
        return self.dto.region or "-"

    @property
    def member_count_display(self) -> str:
        """Member count as string."""
        return str(self.dto.client_count)

    def to_table_row(self) -> Tuple[str, str, str, str, str]:
        """Convert to DataTable row tuple."""
        return (
            self.id,
            self.name,
            self.type_display,
            self.sector_display,
            self.member_count_display,
        )

    @classmethod
    def from_dto(cls, dto: OrganisationDTO) -> "OrganisationViewModel":
        """Create view model from DTO."""
        return cls(dto=dto)

    @classmethod
    def from_list_result(cls, result: OrganisationListResult) -> List["OrganisationViewModel"]:
        """Create list of view models from list result."""
        return [cls.from_dto(dto) for dto in result.organisations]
