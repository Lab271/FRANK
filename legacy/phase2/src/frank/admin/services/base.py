#!/usr/bin/env python3
"""
FRANK Platform - Service base classes.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ServiceResult:
    """Generic service operation result."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, data: Any = None) -> "ServiceResult":
        """Create successful result."""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "ServiceResult":
        """Create failed result."""
        return cls(success=False, error=error)
