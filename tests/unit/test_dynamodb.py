#!/usr/bin/env python3
"""
FRANK Platform - DynamoDB Unit Tests
Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
from unittest.mock import patch, MagicMock
from frank.db.dynamodb import DynamoDBFRANKDatabase


class TestDynamoDBFRANKDatabaseLogAccess(unittest.TestCase):
    """Unit tests for DynamoDBFRANKDatabase.log_access and related access logging."""
    def setUp(self):
        # Create a dummy instance with a mock table
        self.db = DynamoDBFRANKDatabase(connection_params={}, logger=None)
        self.db.table = MagicMock()

    @patch.object(DynamoDBFRANKDatabase, '_log_access')
    def test_log_access_calls_put_item(self, mock_log_access):
        """Test that log_access calls _log_access with correct arguments."""
        org_id = 'org123'
        action = 'QUERY'
        resource_type = 'submission'
        resource_id = 'sub456'
        details = {'foo': 'bar'}

        self.db.log_access(org_id, action, resource_type, resource_id, details)
        mock_log_access.assert_called_once_with(org_id, action, resource_type, resource_id, details)

    def test_log_access_put_item_called(self):
        """Test that log_access results in put_item being called on the table."""
        org_id = 'org123'
        action = 'QUERY'
        resource_type = 'submission'
        resource_id = 'sub456'
        details = {'foo': 'bar'}

        self.db.log_access(org_id, action, resource_type, resource_id, details)
        self.db.table.put_item.assert_called_once()
        args, kwargs = self.db.table.put_item.call_args
        self.assertIn('Item', kwargs or args[0])

if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)