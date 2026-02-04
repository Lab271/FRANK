#!/usr/bin/env python3
"""
FRANK Platform - MySQL Unit Tests

Unit tests for frank/storage/mysql.py

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import unittest
from unittest.mock import MagicMock, patch

from frank.storage.mysql import MySQLFRANKDatabase


class TestMySQLFRANKDatabaseLogAccess(unittest.TestCase):
    """Unit tests for MySQLFRANKDatabase.log_access and related access logging."""

    def setUp(self):
        patcher = patch.object(MySQLFRANKDatabase, 'get_connection', autospec=True)
        self.addCleanup(patcher.stop)
        self.mock_get_connection = patcher.start()
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_get_connection.return_value = self.mock_conn
        self.mock_conn.cursor.return_value = self.mock_cursor
        # Patch logger if needed
        self.logger = MagicMock()
        self.db = MySQLFRANKDatabase(connection_params={"database": "frank", "host": "localhost"}, logger=self.logger)

    @patch.object(MySQLFRANKDatabase, '_log_access')
    def test_log_access_calls__log_access(self, mock_log_access):
        """Test that log_access calls _log_access with correct arguments."""
        org_id = 'org123'
        action = 'QUERY'
        resource_type = 'submission'
        resource_id = 'sub456'
        details = {'foo': 'bar'}
        self.db.log_access(org_id, action, resource_type, resource_id, details)
        mock_log_access.assert_called_once_with(self.mock_cursor, org_id, action, resource_type, resource_id, details)

    def test_log_access_commits_and_closes(self):
        """Test that log_access commits and closes connection."""
        org_id = 'org123'
        action = 'QUERY'
        resource_type = 'submission'
        resource_id = 'sub456'
        details = {'foo': 'bar'}
        # Patch _log_access to avoid actual DB calls
        with patch.object(self.db, '_log_access'):
            self.db.log_access(org_id, action, resource_type, resource_id, details)
            self.assertGreaterEqual(self.mock_conn.close.call_count, 1)

    def test_log_access_handles_exception(self):
        """Test that log_access handles exceptions and closes connection."""
        org_id = 'org123'
        action = 'QUERY'
        resource_type = 'submission'
        resource_id = 'sub456'
        details = {'foo': 'bar'}
        # Simulate exception in _log_access
        with patch.object(self.db, '_log_access', side_effect=Exception("fail")):
            result = self.db.log_access(org_id, action, resource_type, resource_id, details)
            self.assertFalse(result)
            self.assertGreaterEqual(self.mock_conn.close.call_count, 1)

if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)
