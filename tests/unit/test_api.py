#!/usr/bin/env python3
"""
FRANK Platform - API Unit Tests

Unit tests for frank/utils/api.py

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
import types
from frank.utils import api

class TestAPIUtils(unittest.TestCase):
    def test_module_exists(self):
        """Test that the api module is imported and is a module."""
        self.assertTrue(isinstance(api, types.ModuleType))

    # Add more specific tests below if api.py exposes functions/classes
    # Example:
    # def test_some_function(self):
    #     result = api.some_function(args)
    #     self.assertEqual(result, expected)

if __name__ == "__main__":
    unittest.main()
