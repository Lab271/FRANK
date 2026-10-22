#!/usr/bin/env python3
"""
FRANK Platform - Web GUI Module

Web-based user interface for FRANK platform management.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from frank.web.app import create_web_app
from frank.web.config import WebConfig

__all__ = ["create_web_app", "WebConfig"]
