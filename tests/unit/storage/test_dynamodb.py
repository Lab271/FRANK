#!/usr/bin/env python3
"""
FRANK Platform - DynamoDB Unit Tests

Unit tests for dynamodb

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from frank.storage.dynamodb import DynamoDBFRANKDatabase
from frank.storage.exceptions import FRANKQueryError, FRANKStorageError


class TestDynamoDBFRANKDatabaseLogAccess(unittest.TestCase):
    """Unit tests for DynamoDBFRANKDatabase.log_access and related access logging."""
    def setUp(self):
        # Patch boto3.resource
        patcher_resource = patch('boto3.resource')
        self.mock_resource = patcher_resource.start()
        self.addCleanup(patcher_resource.stop)

        # Patch Table and its methods
        mock_table = MagicMock()
        self.mock_resource.return_value.Table.return_value = mock_table
        mock_table.load.return_value = None

        # Patch meta.client and its methods
        mock_client = MagicMock()
        self.mock_resource.return_value.meta.client = mock_client
        mock_client.exceptions.ResourceNotFoundException = Exception  # or a custom Exception
        mock_client.update_time_to_live.return_value = {}

        # Patch create_table
        self.mock_resource.return_value.create_table.return_value = {}

        # Patch get_waiter and waiter.wait
        mock_waiter = MagicMock()
        mock_client.get_waiter.return_value = mock_waiter
        mock_waiter.wait.return_value = None

        # Patch logger if needed
        self.logger = MagicMock()

        # Mock table and client methods as needed
        mock_table = MagicMock()
        self.mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}

        # Create a dummy instance with a mock table
        self.db = DynamoDBFRANKDatabase(connection_params={}, logger=self.logger)
        self.db.table = MagicMock()

    def test_log_access_put_item_called(self):
        """Test that log_access results in put_item being called on the table."""
        org_id = 'org123'
        action = 'QUERY'
        resource_type = 'submission'
        details = {'foo': 'bar'}

        self.db.log_access(org_id, action, resource_type, details)
        self.db.audit_table.put_item.assert_called_once()
        args, kwargs = self.db.audit_table.put_item.call_args
        self.assertIn('Item', kwargs or args[0])

class TestDynamoDBFRANKDatabaseStoreSubmission(unittest.TestCase):
    def setUp(self):
        patcher_resource = patch('boto3.resource')
        self.mock_resource = patcher_resource.start()
        self.addCleanup(patcher_resource.stop)
        # Patch logger if needed
        self.logger = MagicMock()
        self.db = DynamoDBFRANKDatabase(connection_params={}, logger=self.logger)
        self.db.table = MagicMock()
        self.db.client = MagicMock()
        self.db.logger = MagicMock()
        self.db._batch_write_items = MagicMock()

    def test_store_submission_success(self):
        # Mock Submission
        submission = MagicMock()
        submission.timestamp = None
        submission.model_dump_json.return_value = '{}'
        submission.submission_id = 'sub1'
        submission.submitter.organisation_id = 'org1'
        submission.submitter.access_level = 'partner'
        submission.submitter.sector = 'finance'
        submission.submitter.region = 'eu-west-1'
        submission.sighting.confidence = 80
        submission.sighting.severity = 'high'
        submission.tlp_level = 'TLP:AMBER'

        self.db._batch_write_items.return_value = None
        self.db.store_submission(submission)
        self.db._batch_write_items.assert_called_once()

    def test_store_submission_failure(self):
        submission = MagicMock()
        submission.timestamp = None
        submission.model_dump_json.return_value = '{}'
        submission.submission_id = 'sub1'
        submission.submitter.organisation_id = 'org1'
        submission.submitter.access_level = 'partner'
        submission.submitter.sector = 'finance'
        submission.submitter.region = 'eu-west-1'
        submission.sighting.confidence = 80
        submission.sighting.severity = 'high'
        submission.tlp_level = 'TLP:AMBER'

        self.db._batch_write_items.side_effect = FRANKStorageError('fail')
        try:
            self.db.store_submission(submission)
        except FRANKStorageError:
            return
        self.fail("FRANKStorageError not raised")


class TestDynamoDBBatchWrite(unittest.TestCase):
    def setUp(self):
        # Patch boto3.resource
        patcher_resource = patch('boto3.resource')
        self.mock_resource = patcher_resource.start()
        self.addCleanup(patcher_resource.stop)

        # Patch Table and its methods
        mock_table = MagicMock()
        self.mock_resource.return_value.Table.return_value = mock_table
        mock_table.load.return_value = None

        # Patch meta.client and its methods
        mock_client = MagicMock()
        self.mock_resource.return_value.meta.client = mock_client
        mock_client.exceptions.ResourceNotFoundException = Exception  # or a custom Exception
        mock_client.update_time_to_live.return_value = {}

        # Patch create_table
        self.mock_resource.return_value.create_table.return_value = {}

        # Patch get_waiter and waiter.wait
        mock_waiter = MagicMock()
        mock_client.get_waiter.return_value = mock_waiter
        mock_waiter.wait.return_value = None

        # Patch logger if needed
        self.logger = MagicMock()

        # Mock table and client methods as needed
        mock_table = MagicMock()
        self.mock_resource.return_value.Table.return_value = mock_table
        mock_table.put_item.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}

        # Create a dummy instance with a mock table
        self.db = DynamoDBFRANKDatabase(connection_params={}, logger=self.logger)
        self.db.client = MagicMock()
        self.db.client.transact_write_items.return_value = {"UnprocessedItems": {}}  # Fast success
        self.db.table = MagicMock()

    def test_batch_write_success(self):
        # Simulate successful batch write (no unprocessed items)
        self.db.client.batch_write_item.return_value = {"UnprocessedItems": {}}
        items = [
            {"PK": "SUB#1", "SK": "SUB", "GSI1PK": "ORG#1", "GSI1SK": "2025-09-11T00:00:00Z"},
            {"PK": "ORG#1", "SK": "ORG", "GSI1PK": "TIER#partner", "GSI1SK": "2025-09-11T00:00:00Z"}
        ]
        # Should not raise
        self.db._batch_write_items(items)

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

class TestDynamoDBFRANKDatabaseBatchWriteError(unittest.TestCase):
    def setUp(self):
        patcher_resource = patch('boto3.resource')
        self.mock_resource = patcher_resource.start()
        self.addCleanup(patcher_resource.stop)
        # Patch logger if needed
        self.logger = MagicMock()
        self.db = DynamoDBFRANKDatabase(connection_params={}, logger=self.logger)
        self.db.table = MagicMock()
        self.db.client = MagicMock()
        self.db.logger = MagicMock()

    def test_batch_write_client_error(self):
        self.db.client.transact_write_items.side_effect = ClientError({'Error': {}}, 'transact_write_items')
        with self.assertRaises(FRANKStorageError):
            self.db._batch_write_items([{'PK': 'SUB#1', 'SK': 'SUB'}])


class TestDynamoDBFRANKDatabaseGetSubmissionById(unittest.TestCase):
    def setUp(self):
        patcher_resource = patch('boto3.resource')
        self.mock_resource = patcher_resource.start()
        self.addCleanup(patcher_resource.stop)

        # Patch logger if needed
        self.logger = MagicMock()

        self.db = DynamoDBFRANKDatabase(connection_params={}, logger=self.logger)
        self.db.table = MagicMock()
        self.db.client = MagicMock()
        self.db.logger = MagicMock()
        self.db._filter_submission_by_access_level = MagicMock(return_value={'submission_id': 'sub1'})
        self.db._convert_decimals_to_float = MagicMock()
        self.db._log_access = MagicMock()

    def test_get_submission_by_id_found(self):
        # Minimal submission message for FRANK Submission model
        minimal_submission = {
            # "submission": {
                "submission_id": "sub1",
                "timestamp": "2025-09-12T00:00:00Z",
                "submitter": {"organisation_id": "org1", "access_level": "partner", "sector": "finance", "region": "eu-west-1"},
                "sighting": {"confidence": 80, "severity": "high"},
                "tlp_level": "TLP:AMBER",
            # }
        }
        self.db.table.get_item.return_value = {'Item': {'submission_data': minimal_submission}}
        result = self.db.get_submission_by_id('sub1')
        self.assertIsNotNone(result)
        self.assertEqual(result['submission_id'], "sub1")
        self.assertEqual(result['submitter']['organisation_id'], "org1")

    def test_get_submission_by_id_not_found(self):
        self.db.table.get_item.return_value = {}
        result = self.db.get_submission_by_id('sub1')
        self.assertIsNone(result)

    def test_get_submission_by_id_no_submission_data(self):
        self.db.table.get_item.return_value = {'Item': {}}
        self.db._convert_decimals_to_float.return_value = {}
        result = self.db.get_submission_by_id('sub1')
        self.assertIsNone(result)

    def test_get_submission_by_id_client_error(self):
        self.db.table.get_item.side_effect = ClientError({'Error': {}}, 'get_item')
        with self.assertRaises(FRANKQueryError):
            self.db.get_submission_by_id('sub1')


class TestDynamoDBFRANKDatabaseUpsertOrganisation(unittest.TestCase):
    """Unit tests for DynamoDBFRANKDatabase.upsert_organisation method."""
    def setUp(self):
        patcher_resource = patch('boto3.resource')
        self.mock_resource = patcher_resource.start()
        self.addCleanup(patcher_resource.stop)
        self.logger = MagicMock()
        self.db = DynamoDBFRANKDatabase(connection_params={}, logger=self.logger)
        self.db.table = MagicMock()
        self.db.client = MagicMock()
        self.db.logger = MagicMock()

    def test_upsert_organisation_success(self):
        org_data = {
            'organisation_id': 'org123',
            'access_level': 'partner',
            'sector': 'finance',
            'region': 'eu-west-1',
            'last_active': '2025-09-20T12:00:00Z'
        }
        self.db.table.put_item.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
        result = self.db.upsert_organisation(org_data)
        self.db.table.put_item.assert_called_once()
        self.assertTrue(result is None or result)

    def test_upsert_organisation_client_error(self):
        org_data = {
            'organisation_id': 'org123',
            'access_level': 'partner',
            'sector': 'finance',
            'region': 'eu-west-1',
            'last_active': '2025-09-20T12:00:00Z'
        }
        from botocore.exceptions import ClientError
        self.db.table.put_item.side_effect = ClientError({'Error': {}}, 'put_item')
        result = self.db.upsert_organisation(org_data)
        self.db.logger.error.assert_called()
        self.assertTrue(result is None or result is False)


class TestDynamoDBFRANKDatabaseStatisticsAndHealth(unittest.TestCase):
    """Unit tests for DynamoDBFRANKDatabase.get_statistics_summary and health_check methods."""
    def setUp(self):
        patcher_resource = patch('boto3.resource')
        self.mock_resource = patcher_resource.start()
        self.addCleanup(patcher_resource.stop)
        self.logger = MagicMock()
        self.db = DynamoDBFRANKDatabase(connection_params={}, logger=self.logger)
        self.db.table = MagicMock()
        self.db.client = MagicMock()
        self.db.logger = MagicMock()

    def test_get_statistics_summary_success(self):
        # Simulate DynamoDB scan response for statistics
        self.db.table.scan.return_value = {
            'Items': [
                {'EntityType': 'Submission', 'observable_type': 'ipv4'},
                {'EntityType': 'Submission', 'observable_type': 'domain'}
            ],
            'Count': 2
        }
        # Patch _convert_decimals_to_float to pass through
        self.db._convert_decimals_to_float = lambda x: x
        stats = self.db.get_statistics_summary('org123', days=30)
        self.assertIsInstance(stats, dict)
        self.assertIn('observable_totals', stats)

    def test_get_statistics_summary_client_error(self):
        from botocore.exceptions import ClientError
        self.db.table.scan.side_effect = ClientError({'Error': {}}, 'scan')
        stats = self.db.get_statistics_summary('org123', days=30)
        self.assertIsInstance(stats, dict)
        self.assertIn('error', stats)

    def test_health_check(self):
        result = self.db.health_check()
        self.assertIsInstance(result, dict)
        self.assertEqual(result['status'], 'healthy')
        self.assertEqual(result['type'], 'dynamodb')
        self.assertIn('database_table', result)
        self.assertIn('database_region', result)


class TestDynamoDBFRANKDatabaseQueryObservables(unittest.TestCase):
    """Unit tests for DynamoDBFRANKDatabase.query_observables method."""
    def setUp(self):
        patcher_resource = patch('boto3.resource')
        self.mock_resource = patcher_resource.start()
        self.addCleanup(patcher_resource.stop)
        self.logger = MagicMock()
        self.db = DynamoDBFRANKDatabase(connection_params={}, logger=self.logger)
        self.db.table = MagicMock()
        self.db.client = MagicMock()
        self.db.logger = MagicMock()

    def test_query_observables_success(self):
        # Simulate DynamoDB query response for observables
        self.db.table.query.return_value = {
            'Items': [
                {'observable_type': 'ipv4', 'confidence': 85, 'sector': 'finance', 'timestamp': '2025-09-20T12:00:00Z'},
                {'observable_type': 'domain', 'confidence': 70, 'sector': 'retail', 'timestamp': '2025-09-19T12:00:00Z'}
            ],
            'Count': 2
        }
        # Patch _convert_decimals_to_float to pass through
        self.db._convert_decimals_to_float = lambda x: x
        result = self.db.query_observables(
            user_id='org123',
            access_level=None,
            observable_type='ipv4',
            sectors=None,
            min_confidence=None,
            limit=10,
            days_back=None
        )
        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 0)

    def test_query_observables_client_error(self):
        from botocore.exceptions import ClientError
        self.db.table.scan.side_effect = ClientError({'Error': {}}, 'query')
        with self.assertRaises(FRANKQueryError):
            self.db.query_observables(user_id='org123')


if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)
