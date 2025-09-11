#!/usr/bin/env python3
"""
FRANK Platform

Unit tests for src/frank/core/exceptions.py

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
from frank.core.exceptions import FRANKError

class TestFRANKError(unittest.TestCase):
    def test_frank_error_message(self):
        """Test FRANKError with a custom message."""
        exc = FRANKError("Test error message")
        self.assertIn("Test error message", str(exc))
        self.assertIn("Code: FRANKError", str(exc))

    def test_frank_error_with_code_and_details(self):
        """Test FRANKError with custom error_code and details."""
        exc = FRANKError("Something went wrong", error_code="E123", details={"foo": "bar"})
        self.assertIn("Something went wrong", str(exc))
        self.assertIn("Code: E123", str(exc))
        self.assertIn("Details: {'foo': 'bar'}", str(exc))

    def test_frank_error_default_code(self):
        """Test FRANKError default error_code is class name."""
        exc = FRANKError("msg")
        self.assertEqual(exc.error_code, "FRANKError")

    def test_frank_error_details_empty(self):
        """Test FRANKError details default to empty dict."""
        exc = FRANKError("msg")
        self.assertEqual(exc.details, {})

if __name__ == "__main__":
    unittest.main()
