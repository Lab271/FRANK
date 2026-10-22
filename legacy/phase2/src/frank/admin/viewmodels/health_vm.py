#!/usr/bin/env python3
"""
FRANK Platform - Health view model.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from dataclasses import dataclass

from frank.admin.models import HealthStatus


@dataclass
class HealthViewModel:
    """View model for health status display."""

    dto: HealthStatus

    @property
    def status_display(self) -> str:
        """Full status line for display."""
        return f"API: {self.dto.status} | DB: {self.dto.database}"

    @property
    def api_status(self) -> str:
        """API status."""
        return self.dto.status

    @property
    def db_status(self) -> str:
        """Database status."""
        return self.dto.database

    @property
    def is_healthy(self) -> bool:
        """Whether all systems healthy."""
        return self.dto.is_healthy

    @property
    def error_message(self) -> str:
        """Error message if any."""
        return self.dto.message or ""

    @classmethod
    def from_dto(cls, dto: HealthStatus) -> "HealthViewModel":
        """Create view model from DTO."""
        return cls(dto=dto)

    @classmethod
    def error(cls, message: str) -> "HealthViewModel":
        """Create error view model."""
        dto = HealthStatus(status="error", database="unknown", message=message)
        return cls(dto=dto)
