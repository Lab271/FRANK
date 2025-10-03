"""
FRANK Platform - Unit Tests for Storage Exceptions

Unit tests for FRANK custom exception classes in frank.storage.exceptions.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest

from frank.storage.exceptions import FRANKStorageError, FRANKConnectionError, FRANKQueryError

class TestFRANKStorageExceptions(unittest.TestCase):
    """Unit tests for FRANK storage exception classes."""

    def test_storage_error_message(self):
        """Test FRANKStorageError message."""
        err = FRANKStorageError("storage failed")
        self.assertIsInstance(err, FRANKStorageError)
        self.assertEqual(str(err), "storage failed")

    def test_connection_error_message(self):
        """Test FRANKConnectionError message."""
        err = FRANKConnectionError("connection failed")
        self.assertIsInstance(err, FRANKConnectionError)
        self.assertEqual(str(err), "connection failed")

    def test_query_error_message(self):
        """Test FRANKQueryError message."""
        err = FRANKQueryError("query failed")
        self.assertIsInstance(err, FRANKQueryError)
        self.assertEqual(str(err), "query failed")

    def test_inheritance(self):
        """Test exception inheritance from Exception."""
        self.assertTrue(issubclass(FRANKStorageError, Exception))
        self.assertTrue(issubclass(FRANKConnectionError, Exception))
        self.assertTrue(issubclass(FRANKQueryError, Exception))

if __name__ == "__main__":
    unittest.main()
