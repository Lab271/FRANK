#!/usr/bin/env python3
"""
FRANK Platform - Models Unit Tests

Unit tests for frank/core/models.py

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest

from frank.core.models import example_usage

class TestExampleUsage(unittest.TestCase):
    """Unit tests for example_usage logic in models.py"""
    
    def test_example_usage(self):
        """Test minimal submission creation via factory method."""
        example_usage()
        self.assertTrue(True, "example_usage")  # If no exceptions, test passes

if __name__ == "__main__":
	unittest.main()
