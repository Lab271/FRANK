#!/usr/bin/env python3
"""
FRANK Platform - DynamoDB Unit Tests

Unit tests for dynamodb

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
from unittest.mock import patch, MagicMock

import uuid

from botocore.exceptions import ClientError

from frank.storage.dynamodb import DynamoDBFRANKDatabase
from frank.storage.exceptions import FRANKStorageError

class TestConfiguration(unittest.TestCase):
    """Unit tests for DynamoDBFRANKDatabase configuration and initialization."""

    def setUp(self):
        patcher_session = patch('boto3.Session')
        self.mock_boto3_session = patcher_session.start()
        self.addCleanup(patcher_session.stop)

    def _setup_mocks(self):
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_resource = MagicMock()
        mock_table = MagicMock()
        mock_resource.Table.return_value = mock_table
        mock_session.client.return_value = mock_client
        mock_session.resource.return_value = mock_resource
        self.mock_boto3_session.return_value = mock_session
        return mock_session, mock_resource


    def test_empty_initialization(self):
        """Test initialization with empty configuration."""
        with self.assertRaises(KeyError):
            DynamoDBFRANKDatabase(config={})

    def test_initialize_called(self):
        """Test that initialize method is called during __init__."""
        with patch.object(DynamoDBFRANKDatabase, 'initialize') as mock_initialize:
            DynamoDBFRANKDatabase(config={
                'environment': 'aws',
                'region': 'eu-west-1',
                'table_name': 'frank_table',
                'audit_table_name': 'frank_audit_table'
            })
            mock_initialize.assert_called_once()

    def test_initialization_with_aws_config(self):
        """Test initialization with a valid aws configuration."""
        config = {
            'environment': 'aws',
            'region': 'eu-west-1',
            'table_name': 'frank_table',
            'audit_table_name': 'frank_audit_table'
        }
        mock_session, mock_resource = self._setup_mocks()
        db = DynamoDBFRANKDatabase(config=config)
        self.assertIsInstance(db, DynamoDBFRANKDatabase)
        self.mock_boto3_session.assert_called_once()
        mock_session.client.assert_called_with('dynamodb', region_name='eu-west-1')
        mock_session.resource.assert_called_with('dynamodb', region_name='eu-west-1')
        mock_resource.Table.assert_any_call('frank_table')
        mock_resource.Table.assert_any_call('frank_audit_table')


    def test_initialization_with_profile_config(self):
        """Test initialization with a valid profile configuration."""
        config = {
            'environment': 'localstack',
            'profile': 'test-profile',
            'endpoint': 'http://localhost:8000',
            'region': 'eu-west-1',
            'table_name': 'frank_table',
            'audit_table_name': 'frank_audit_table'
        }
        mock_session, mock_resource = self._setup_mocks()
        db = DynamoDBFRANKDatabase(config=config)
        self.assertIsInstance(db, DynamoDBFRANKDatabase)
        self.mock_boto3_session.assert_called_once_with(profile_name='test-profile')
        mock_session.client.assert_called_with('dynamodb', endpoint_url='http://localhost:8000', region_name='eu-west-1')
        mock_session.resource.assert_called_with('dynamodb', endpoint_url='http://localhost:8000', region_name='eu-west-1')
        mock_resource.Table.assert_any_call('frank_table')
        mock_resource.Table.assert_any_call('frank_audit_table')


    def test_initialization_with_aws_credentials_config(self):
        """Test initialization with a valid aws credentials configuration."""
        config = {
            'environment': 'localstack',
            'profile': None,
            'aws_access_key_id': 'test-access-key',
            'aws_secret_access_key': 'test-secret-key',
            'endpoint': 'http://localhost:8000',
            'region': 'eu-west-1',
            'table_name': 'frank_table',
            'audit_table_name': 'frank_audit_table'
        }
        mock_session, mock_resource = self._setup_mocks()
        db = DynamoDBFRANKDatabase(config=config)
        self.assertIsInstance(db, DynamoDBFRANKDatabase)
        self.mock_boto3_session.assert_called_once()
        mock_session.client.assert_called_with('dynamodb', endpoint_url='http://localhost:8000', region_name='eu-west-1', aws_access_key_id='test-access-key', aws_secret_access_key='test-secret-key')
        mock_session.resource.assert_called_with('dynamodb', endpoint_url='http://localhost:8000', region_name='eu-west-1', aws_access_key_id='test-access-key', aws_secret_access_key='test-secret-key')
        mock_resource.Table.assert_any_call('frank_table')
        mock_resource.Table.assert_any_call('frank_audit_table')

    def test_missing_region_key(self):
        """Test initialization with config missing 'region' key."""
        config = {
            'environment': 'aws',
            'table_name': 'frank_table',
            'audit_table_name': 'frank_audit_table'
        }
        with self.assertRaises(KeyError):
            DynamoDBFRANKDatabase(config=config)

    def test_missing_table_name_key(self):
        """Test initialization with config missing 'table_name' key."""
        config = {
            'environment': 'aws',
            'region': 'eu-west-1',
            'audit_table_name': 'frank_audit_table'
        }
        with self.assertRaises(KeyError):
            DynamoDBFRANKDatabase(config=config)

    def test_none_region(self):
        """Test initialization with region set to None."""
        config = {
            'environment': 'aws',
            'table_name': 'frank_table',
            'audit_table_name': 'frank_audit_table'
        }
        with self.assertRaises(Exception):
            DynamoDBFRANKDatabase(config=config)

    def test_extra_unused_keys(self):
        """Test initialization with extra unused keys in config."""
        config = {
            'environment': 'aws',
            'region': 'eu-west-1',
            'table_name': 'frank_table',
            'audit_table_name': 'frank_audit_table',
            'extra_key': 'should_be_ignored'
        }
        mock_session, mock_resource = self._setup_mocks()
        db = DynamoDBFRANKDatabase(config=config)
        self.assertIsInstance(db, DynamoDBFRANKDatabase)

class TestSupportMethods(unittest.TestCase):
    """Unit tests for basic DynamoDBFRANKDatabase methods."""

    # patch initialization to avoid real AWS calls and setup DynamoDBFRANKDatabase instance
    @patch('frank.storage.dynamodb.DynamoDBFRANKDatabase.initialize')
    def setUp(self, mock_initialize):
        self.valid_user = {
            'user_id': 'user1',
            'name': 'Test User',
            'email': 'testuser@example.com',
            'request_id': f'request--{uuid.uuid4()}'
        }

        self.valid_config = {
            'environment': 'aws',
            'region': 'eu-west-1',
            'table_name': 'frank_table',
            'audit_table_name': 'frank_audit_table'
        }
        self.mock_initialize = mock_initialize
        self.mock_initialize.return_value = None
        self.db = DynamoDBFRANKDatabase(config=self.valid_config)
        self.db.table = MagicMock()
        self.db.audit_table = MagicMock()
        self.db.logger = MagicMock()

    def test_batch_write_items_success(self):
        # Mock the batch_writer context manager
        mock_batch = MagicMock()
        mock_table = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch
        self.db.table = mock_table
        items = [
            {"PK": "SUB#1", "SK": "SUB"},
            {"PK": "ORG#1", "SK": "ORG"}
        ]
        # Should not raise
        self.db._batch_write_items(items)
        # Ensure put_item called for each item
        self.assertEqual(mock_batch.put_item.call_count, len(items))

    def test_batch_write_items_client_error(self):
        mock_table = MagicMock()
        # Simulate ClientError on put_item
        mock_batch = MagicMock()
        mock_batch.put_item.side_effect = ClientError({'Error': {'Code': 'ProvisionedThroughputExceededException'}}, 'PutItem')
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch
        self.db.table = mock_table
        items = [{"PK": "SUB#1", "SK": "SUB"}]
        with self.assertRaises(FRANKStorageError):
            self.db._batch_write_items(items)

    def test_batch_write_items_generic_exception(self):
        mock_table = MagicMock()
        # Simulate generic Exception on put_item
        mock_batch = MagicMock()
        mock_batch.put_item.side_effect = Exception("Unexpected error")
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch
        self.db.table = mock_table
        items = [{"PK": "SUB#1", "SK": "SUB"}]
        with self.assertRaises(FRANKStorageError):
            self.db._batch_write_items(items)


class TestBaseMethods(unittest.TestCase):
    """Unit tests for basic DynamoDBFRANKDatabase methods."""

    # patch initialization to avoid real AWS calls and setup DynamoDBFRANKDatabase instance
    @patch('frank.storage.dynamodb.DynamoDBFRANKDatabase.initialize')
    def setUp(self, mock_initialize):
        self.valid_user = {
            'user_id': 'user1',
            'name': 'Test User',
            'email': 'testuser@example.com',
            'request_id': f'request--{uuid.uuid4()}'
        }

        self.valid_config = {
            'environment': 'aws',
            'region': 'eu-west-1',
            'table_name': 'frank_table',
            'audit_table_name': 'frank_audit_table'
        }
        self.mock_initialize = mock_initialize
        self.mock_initialize.return_value = None
        self.db = DynamoDBFRANKDatabase(config=self.valid_config)
        self.db._batch_write_items = MagicMock()
        self.db.table = MagicMock()
        self.db.audit_table = MagicMock()

    # def test_batch_write_items_success(self):
    #     # Mock the batch_writer context manager
    #     mock_batch = MagicMock()
    #     mock_table = MagicMock()
    #     mock_table.batch_writer.return_value.__enter__.return_value = mock_batch
    #     self.db.table = mock_table
    #     items = [
    #         {"PK": "SUB#1", "SK": "SUB"},
    #         {"PK": "ORG#1", "SK": "ORG"}
    #     ]
    #     # Should not raise
    #     self.db._batch_write_items(items)
    #     # Ensure put_item called for each item
    #     self.assertEqual(mock_batch.put_item.call_count, len(items))

    # def test_batch_write_items_client_error(self):
    #     mock_table = MagicMock()
    #     # Simulate ClientError on put_item
    #     mock_batch = MagicMock()
    #     mock_batch.put_item.side_effect = ClientError({'Error': {'Code': 'ProvisionedThroughputExceededException'}}, 'PutItem')
    #     mock_table.batch_writer.return_value.__enter__.return_value = mock_batch
    #     self.db.table = mock_table
    #     items = [{"PK": "SUB#1", "SK": "SUB"}]
    #     with self.assertRaises(FRANKStorageError):
    #         self.db._batch_write_items(items)

    # def test_batch_write_items_generic_exception(self):
    #     mock_table = MagicMock()
    #     # Simulate generic Exception on put_item
    #     mock_batch = MagicMock()
    #     mock_batch.put_item.side_effect = Exception("Unexpected error")
    #     mock_table.batch_writer.return_value.__enter__.return_value = mock_batch
    #     self.db.table = mock_table
    #     items = [{"PK": "SUB#1", "SK": "SUB"}]
    #     with self.assertRaises(FRANKStorageError):
    #         self.db._batch_write_items(items)

    # def test_batch_write_success(self):
    #     # Simulate successful batch write (no unprocessed items)
    #     items = [
    #         {"PK": "SUB#1", "SK": "SUB", "GSI1PK": "ORG#1", "GSI1SK": "2025-09-11T00:00:00Z"},
    #         {"PK": "ORG#1", "SK": "ORG", "GSI1PK": "TIER#partner", "GSI1SK": "2025-09-11T00:00:00Z"}
    #     ]
    #     # Should not raise
    #     self.db._batch_write_items(items)

    # def test_batch_write_retry(self):
    #     # Simulate unprocessed items requiring retry
    #     first_response = {"UnprocessedItems": {"frank_table": [{"PutRequest": {"Item": {"PK": "SUB#1"}}}]}}
    #     second_response = {"UnprocessedItems": {}}
    #     self.db.client.batch_write_item.side_effect = [first_response, second_response]
    #     items = [
    #         {"PK": "SUB#1", "SK": "SUB", "GSI1PK": "ORG#1", "GSI1SK": "2025-09-11T00:00:00Z"}
    #     ]
    #     # Should not raise, should call batch_write_item twice
    #     self.db._batch_write_items(items)


    def test_health_check(self):
        self.db.client = MagicMock()
        self.db.resource = MagicMock()
        self.db.client.list_tables.return_value = {"TableNames": ["frank_table", "frank_audit_table"]}
        self.db.resource.Table.return_value.table_name = "frank_table"
        result = self.db.health_check()
        self.assertIsInstance(result, dict)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['database_type'], 'dynamodb')
        self.assertIn('tables', result)
        self.assertIn('available_tables', result['tables'])

    def test_log_access_basic(self):
        org_id = 'org456'
        action = 'QUERY'
        msg_key = 'msg789'
        status = 'success'
        details = {'foo': 'bar'}
        self.db.log_access(self.valid_user, org_id, action, msg_key, status, details)
        # Check that put_item was called with expected keys
        self.db.audit_table.put_item.assert_called_once()
        args, kwargs = self.db.audit_table.put_item.call_args
        log_item = kwargs['Item'] if 'Item' in kwargs else args[0]['Item']
        self.assertEqual(log_item['PK'].split('#')[1], action)
        self.assertEqual(log_item['GSI1PK'], f'USER#{self.valid_user["user_id"]}')
        self.assertEqual(log_item['GSI2PK'], f'ORG#{org_id}')
        self.assertEqual(log_item['status'], status)
        self.assertEqual(log_item['details'], details)

    def test_log_access_no_details(self):
        org_id = 'org456'
        action = 'SUBMIT'
        msg_key = 'msg000'
        # No details provided
        self.db.log_access(self.valid_user, org_id, action, msg_key)
        self.db.audit_table.put_item.assert_called_once()
        args, kwargs = self.db.audit_table.put_item.call_args
        log_item = kwargs['Item'] if 'Item' in kwargs else args[0]['Item']
        self.assertEqual(log_item['PK'].split('#')[1], action)
        self.assertEqual(log_item['GSI1PK'], f'USER#{self.valid_user["user_id"]}')
        self.assertEqual(log_item['GSI2PK'], f'ORG#{org_id}')
        self.assertEqual(log_item['status'], 'success')
        self.assertNotIn('details', log_item)

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
        submission.tlp_level = 'TLP:AMBER'

        self.db._batch_write_items = MagicMock(return_value=None)
        self.db.store_submission(self.valid_user, submission)
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

        self.db._batch_write_items = MagicMock(side_effect=FRANKStorageError('fail'))
        with self.assertRaises(FRANKStorageError):
            self.db.store_submission(self.valid_user, submission)


# class TestDynamoDBBatchWrite(unittest.TestCase):
#     def setUp(self):
#         # Patch boto3.resource
#         patcher_resource = patch('boto3.resource')
#         self.mock_resource = patcher_resource.start()
#         self.addCleanup(patcher_resource.stop)

#         # Patch Table and its methods
#         mock_table = MagicMock()
#         self.mock_resource.return_value.Table.return_value = mock_table
#         mock_table.load.return_value = None

#         # Patch meta.client and its methods
#         mock_client = MagicMock()
#         self.mock_resource.return_value.meta.client = mock_client
#         mock_client.exceptions.ResourceNotFoundException = Exception  # or a custom Exception
#         mock_client.update_time_to_live.return_value = {}

#         # Patch create_table
#         self.mock_resource.return_value.create_table.return_value = {}

#         # Patch get_waiter and waiter.wait
#         mock_waiter = MagicMock()
#         mock_client.get_waiter.return_value = mock_waiter
#         mock_waiter.wait.return_value = None

#         # Patch logger if needed
#         self.logger = MagicMock()

#         # Mock table and client methods as needed
#         mock_table = MagicMock()
#         self.mock_resource.return_value.Table.return_value = mock_table
#         mock_table.put_item.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}

#         self.default_config = {''
#             'environment': 'aws',
#             'region': 'us-west-1',
#             'table_name': 'frank_table',
#             'audit_table_name': 'frank_audit_table'
#         }

#         # Create a dummy instance with a mock table
#         self.db = DynamoDBFRANKDatabase(config=self.default_config, logger=self.logger)
#         self.db.client = MagicMock()
#         self.db.client.transact_write_items.return_value = {"UnprocessedItems": {}}  # Fast success
#         self.db.table = MagicMock()



# class TestDynamoDBFRANKDatabaseGetSubmissionById(unittest.TestCase):
#     def setUp(self):
#         patcher_resource = patch('boto3.resource')
#         self.mock_resource = patcher_resource.start()
#         self.addCleanup(patcher_resource.stop)

#         # Patch logger if needed
#         self.logger = MagicMock()

#         self.db = DynamoDBFRANKDatabase(config={}, logger=self.logger)
#         self.db.table = MagicMock()
#         self.db.client = MagicMock()
#         self.db.logger = MagicMock()
#         self.db._filter_submission_by_access_level = MagicMock(return_value={'submission_id': 'sub1'})
#         self.db._convert_decimals_to_float = MagicMock()
#         self.db._log_access = MagicMock()

#     def test_get_submission_by_id_found(self):
#         # Minimal submission message for FRANK Submission model
#         minimal_submission = {
#             # "submission": {
#                 "submission_id": "sub1",
#                 "timestamp": "2025-09-12T00:00:00Z",
#                 "submitter": {"organisation_id": "org1", "access_level": "partner", "sector": "finance", "region": "eu-west-1"},
#                 "sighting": {"confidence": 80, "severity": "high"},
#                 "tlp_level": "TLP:AMBER",
#             # }
#         }
#         import json
#         self.db.table.get_item.return_value = {'Item': {'submission_data': minimal_submission}}
#         result = self.db.get_submission_by_id('sub1')
#         self.assertIsNotNone(result)
#         self.assertEqual(result['submission_id'], "sub1")
#         self.assertEqual(result['submitter']['organisation_id'], "org1")

#     def test_get_submission_by_id_not_found(self):
#         self.db.table.get_item.return_value = {}
#         result = self.db.get_submission_by_id('sub1')
#         self.assertIsNone(result)

#     def test_get_submission_by_id_no_submission_data(self):
#         self.db.table.get_item.return_value = {'Item': {}}
#         self.db._convert_decimals_to_float.return_value = {}
#         result = self.db.get_submission_by_id('sub1')
#         self.assertIsNone(result)

#     def test_get_submission_by_id_client_error(self):
#         self.db.table.get_item.side_effect = ClientError({'Error': {}}, 'get_item')
#         with self.assertRaises(FRANKQueryError):
#             self.db.get_submission_by_id('sub1')


# class TestDynamoDBFRANKDatabaseUpsertOrganisation(unittest.TestCase):
#     """Unit tests for DynamoDBFRANKDatabase.upsert_organisation method."""
#     def setUp(self):
#         patcher_resource = patch('boto3.resource')
#         self.mock_resource = patcher_resource.start()
#         self.addCleanup(patcher_resource.stop)
#         self.logger = MagicMock()
#         self.db = DynamoDBFRANKDatabase(config={}, logger=self.logger)
#         self.db.table = MagicMock()
#         self.db.client = MagicMock()
#         self.db.logger = MagicMock()

#     def test_upsert_organisation_success(self):
#         org_data = {
#             'organisation_id': 'org123',
#             'access_level': 'partner',
#             'sector': 'finance',
#             'region': 'eu-west-1',
#             'last_active': '2025-09-20T12:00:00Z'
#         }
#         self.db.table.put_item.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
#         result = self.db.upsert_organisation(org_data)
#         self.db.table.put_item.assert_called_once()
#         self.assertTrue(result is None or result)

#     def test_upsert_organisation_client_error(self):
#         org_data = {
#             'organisation_id': 'org123',
#             'access_level': 'partner',
#             'sector': 'finance',
#             'region': 'eu-west-1',
#             'last_active': '2025-09-20T12:00:00Z'
#         }
#         from botocore.exceptions import ClientError
#         self.db.table.put_item.side_effect = ClientError({'Error': {}}, 'put_item')
#         result = self.db.upsert_organisation(org_data)
#         self.db.logger.error.assert_called()
#         self.assertTrue(result is None or result is False)


# class TestDynamoDBFRANKDatabaseStatisticsAndHealth(unittest.TestCase):
#     """Unit tests for DynamoDBFRANKDatabase.get_statistics_summary and health_check methods."""
#     def setUp(self):
#         patcher_resource = patch('boto3.resource')
#         self.mock_resource = patcher_resource.start()
#         self.addCleanup(patcher_resource.stop)
#         self.logger = MagicMock()
#         self.db = DynamoDBFRANKDatabase(config={}, logger=self.logger)
#         self.db.table = MagicMock()
#         self.db.client = MagicMock()
#         self.db.logger = MagicMock()

#     def test_get_statistics_summary_success(self):
#         # Simulate DynamoDB scan response for statistics
#         self.db.table.scan.return_value = {
#             'Items': [
#                 {'EntityType': 'Submission', 'observable_type': 'ipv4'},
#                 {'EntityType': 'Submission', 'observable_type': 'domain'}
#             ],
#             'Count': 2
#         }
#         # Patch _convert_decimals_to_float to pass through
#         self.db._convert_decimals_to_float = lambda x: x
#         stats = self.db.get_statistics_summary('org123', days=30)
#         self.assertIsInstance(stats, dict)
#         self.assertIn('observable_totals', stats)

#     def test_get_statistics_summary_client_error(self):
#         from botocore.exceptions import ClientError
#         self.db.table.scan.side_effect = ClientError({'Error': {}}, 'scan')
#         stats = self.db.get_statistics_summary('org123', days=30)
#         self.assertIsInstance(stats, dict)
#         self.assertIn('error', stats)




# class TestDynamoDBFRANKDatabaseQueryObservables(unittest.TestCase):
#     """Unit tests for DynamoDBFRANKDatabase.query_observables method."""
#     def setUp(self):
#         patcher_resource = patch('boto3.resource')
#         self.mock_resource = patcher_resource.start()
#         self.addCleanup(patcher_resource.stop)
#         self.logger = MagicMock()
#         self.db = DynamoDBFRANKDatabase(config={}, logger=self.logger)
#         self.db.table = MagicMock()
#         self.db.client = MagicMock()
#         self.db.logger = MagicMock()

#     def test_query_observables_success(self):
#         # Simulate DynamoDB query response for observables
#         self.db.table.query.return_value = {
#             'Items': [
#                 {'observable_type': 'ipv4', 'confidence': 85, 'sector': 'finance', 'timestamp': '2025-09-20T12:00:00Z'},
#                 {'observable_type': 'domain', 'confidence': 70, 'sector': 'retail', 'timestamp': '2025-09-19T12:00:00Z'}
#             ],
#             'Count': 2
#         }
#         # Patch _convert_decimals_to_float to pass through
#         self.db._convert_decimals_to_float = lambda x: x
#         result = self.db.query_observables(
#             user_id='org123',
#             access_level=None,
#             observable_type='ipv4',
#             sectors=None,
#             min_confidence=None,
#             limit=10,
#             days_back=None
#         )
#         self.assertIsInstance(result, list)
#         self.assertGreaterEqual(len(result), 0)

#     def test_query_observables_client_error(self):
#         from botocore.exceptions import ClientError
#         self.db.table.scan.side_effect = ClientError({'Error': {}}, 'query')
#         with self.assertRaises(FRANKQueryError):
#             self.db.query_observables(user_id='org123')


if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)