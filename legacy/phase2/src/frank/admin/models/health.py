#!/usr/bin/env python3
"""
FRANK Platform - Health data models.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from dataclasses import dataclass
from typing import Optional


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
