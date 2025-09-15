"""
FRANK Platform - Utility Logger
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides a NullLogger class that can be used to disable logging
by discarding all log messages. 

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

class NullLogger:
    """Null logger that discards all log messages"""
    def debug(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def critical(self, *args, **kwargs): pass
    def exception(self, *args, **kwargs): pass