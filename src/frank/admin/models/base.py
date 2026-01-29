#!/usr/bin/env python3
"""
FRANK Platform - Base model utilities.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime
from typing import Optional


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string."""
    if not value:
        return None
    try:
        # Handle ISO format with and without microseconds/timezone
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
