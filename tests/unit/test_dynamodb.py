#!/usr/bin/env python3
"""
FRANK Platform - DynamoDB Unit Tests

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
import types
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


class TestDynamoDBBatchWrite(unittest.TestCase):
    def setUp(self):
        # Create a dummy database instance
        self.db = DynamoDBFRANKDatabase(connection_params={"DYNAMODB_TABLE": "frank_table"}, logger=None)
        self.db.table_name = "frank_table"
        self.db.client = MagicMock()

    def test_batch_write_success(self):
        # Simulate successful batch write (no unprocessed items)
        self.db.client.batch_write_item.return_value = {"UnprocessedItems": {}}
        items = [
            {"PK": "SUB#1", "SK": "SUB", "GSI1PK": "ORG#1", "GSI1SK": "2025-09-11T00:00:00Z"},
            {"PK": "ORG#1", "SK": "ORG", "GSI1PK": "TIER#partner", "GSI1SK": "2025-09-11T00:00:00Z"}
        ]
        # Should not raise
        self.db._batch_write_items(items)
        self.db.client.batch_write_item.assert_called()

    def test_batch_write_retry(self):
        # Simulate unprocessed items requiring retry
        first_response = {"UnprocessedItems": {"frank_table": [{"PutRequest": {"Item": {"PK": "SUB#1"}}}]}}
        second_response = {"UnprocessedItems": {}}
        self.db.client.batch_write_item.side_effect = [first_response, second_response]
        items = [
            {"PK": "SUB#1", "SK": "SUB", "GSI1PK": "ORG#1", "GSI1SK": "2025-09-11T00:00:00Z"}
        ]
        # Should not raise, should call batch_write_item twice
        self.db._batch_write_items(items)
        self.assertEqual(self.db.client.batch_write_item.call_count, 2)

if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)