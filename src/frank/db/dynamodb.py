#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides DynamoDB based storage for FRANK submissions using single table design.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import boto3
import uuid
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

import logging

from frank.db.exceptions import FRANKConnectionError, FRANKQueryError, FRANKStorageError
from frank.db.base import BaseFRANKDatabase
from frank.core.models import Submission, Observable
from frank.core.enum import ObservableType, TierLevel


class DynamoDBFRANKDatabase(BaseFRANKDatabase):
    """
    DynamoDB implementation of FRANK database using single table design.
    Provides full functionality with NoSQL scalability and supports
    the complete FRANK access tier model.
    
    Single Table Design Pattern:
    PK (Partition Key)  | SK (Sort Key)   | GSI1PK          | GSI1SK       | Entity Type     | Description
    ORG#{org_id}        | ORG             | TIER#{tier}     | #{timestamp} | Organization    | Organization metadata
    SUB#{sub_id}        | SUB             | ORG#{org_id}    | #{timestamp} | Submission      | Complete submission with nested data
    LOG#{org_id}        | LOG#{timestamp} | ACTION#{action} | #{timestamp} | Access Log      | Audit trail for actions
    OBS#{obs_hash}      | SUB#{sub_id}    | TYPE#{obs_type} | #{timestamp} | ObservableIndex | Observable cross-reference
    SIGHT#{sighting_id} | SUB#{sub_id}    | ORG#{org_id}    | #{timestamp} | Sighting        | Sighting details (confidence, severity, observables)

        """
    
    def initialize(self) -> None:
        """
        Initialize DynamoDB database connection for LocalStack environment.

        Args:
            table_name: DynamoDB table name
            region: AWS region
            logger: Optional logger instance for logging
        """
        aws_access_key_id=self.connection_params.get("AWS_ACCESS_KEY_ID", "test")
        aws_secret_access_key=self.connection_params.get("AWS_SECRET_ACCESS_KEY", "test")

        self.table_name = self.connection_params.get("DYNAMODB_TABLE", "frank_table")
        self.region = self.connection_params.get("AWS_DEFAULT_REGION", "eu-west-1")
        self.environment = self.connection_params.get("FRANK_ENVIRONMENT", "localstack")

        # Initialize AWS DynamoDB client
        try:
            if self.environment == "localstack":
                # LocalStack configuration with dummy credentials
                self.dynamodb = boto3.resource(
                    "dynamodb",
                    endpoint_url=self.connection_params.get("LOCALSTACK_ENDPOINT", "http://localstack:4566"),
                    region_name=self.region,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key
                )
            else:
                # Production AWS environment (uses actual credentials)
                self.dynamodb = boto3.resource(
                    "dynamodb",
                    endpoint_url=self.connection_params.get("LOCALSTACK_ENDPOINT", "http://localhost:4566"),
                    region_name=self.region,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key
                )
            
        except Exception as e:
            self.logger.error(f"Failed to initialize DynamoDB: {e}")
            raise FRANKConnectionError(f"DynamoDB connection failed: {e}")

        self.client = self.dynamodb.meta.client

        # Verify connection and create table if needed (LocalStack only)
        if self.environment == 'localstack':
            self._ensure_table_exists()


    def _convert_floats_to_decimal(self, obj: Any) -> Any:
        """Convert float values to Decimal for DynamoDB compatibility."""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(item) for item in obj]
        return obj
    
    def _convert_decimals_to_float(self, obj: Any) -> Any:
        """Convert Decimal values back to float for JSON serialization."""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_decimals_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimals_to_float(item) for item in obj]
        return obj
    
    def _ensure_table_exists(self) -> bool:
        """
        Create the FRANK DynamoDB table with proper indexes and TTL configuration.
        
        Args:
            table_name: Name for the DynamoDB table
            region: AWS region
            
        Returns:
            True if table created successfully
        """
        try:       
            # Create table with single table design
            table_definition = {
                'TableName': self.table_name,
                'KeySchema': [
                    {'AttributeName': 'PK', 'KeyType': 'HASH'},
                    {'AttributeName': 'SK', 'KeyType': 'RANGE'}
                ],
                'AttributeDefinitions': [
                    {'AttributeName': 'PK', 'AttributeType': 'S'},
                    {'AttributeName': 'SK', 'AttributeType': 'S'},
                    {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
                    {'AttributeName': 'GSI1SK', 'AttributeType': 'S'}
                ],
                'GlobalSecondaryIndexes': [
                    {
                        'IndexName': 'GSI1',
                        'KeySchema': [
                            {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                            {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                    }
                ],
                'BillingMode': 'PAY_PER_REQUEST',
                'SSESpecification': {
                    'Enabled': True,
                    'SSEType': 'KMS'
                },
                'Tags': [
                    {'Key': 'Application', 'Value': 'FRANK'},
                    {'Key': 'Environment', 'Value': 'development'},
                    {'Key': 'DataClassification', 'Value': 'confidential'}
                ]
            }

            try:
                # Try to get table
                self.table = self.dynamodb.Table(self.table_name)
                self.table.load()
                self.logger.info(f"✅ Table '{self.table_name}' already exists")
            except self.dynamodb.meta.client.exceptions.ResourceNotFoundException:

                # Create the table
                _ = self.dynamodb.create_table(**table_definition)
                self.table = self.dynamodb.Table(self.table_name)

                # Wait for table to be created
                waiter = self.table.meta.client.get_waiter('table_exists')
                waiter.wait(TableName=self.table_name)
                self.logger.info(f"✅ Table '{self.table_name}' created successfully")

            
            # Enable TTL on the TTL attribute
            self.dynamodb.meta.client.update_time_to_live(
                TableName=self.table_name,
                TimeToLiveSpecification={
                    'AttributeName': 'TTL',
                    'Enabled': True
                }
            )
            self.logger.info(f"✅ FRANK DynamoDB table '{self.table_name}' created successfully")
            return True
            
        except ClientError as e:
                self.logger.error(f"❌ Failed to create table: {e}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Unexpected error: {e}")
            return False

    def upsert_organization(self, org_data: Dict[str, Any]) -> bool:
        """
        Insert or update organization information in DynamoDB.

        Args:
            org_data (Dict[str, Any]): Dictionary containing organization fields. Must include 'organization_id'.
                Expected keys: organization_id, tier, sector, region, last_active (optional).

        Returns:
            bool: True if the operation succeeded, False if there was a ClientError.

        Raises:
            Logs error and returns False if DynamoDB put_item fails.
        """
        try:
            timestamp = org_data.get('last_active') or datetime.now(timezone.utc).isoformat()
            org_item = {
                'PK': f"ORG#{org_data['organization_id']}",
                'SK': 'ORG',
                'GSI1PK': f"TIER#{org_data.get('tier', 'unknown')}",
                'GSI1SK': timestamp,
                'EntityType': 'Organization',
                'organization_id': org_data.get('organization_id', ''),
                'tier': org_data.get('tier', ''),
                'sector': org_data.get('sector', ''),
                'region': org_data.get('region', ''),
                'last_active': timestamp,
                'TTL': int((datetime.now(timezone.utc) + timedelta(days=2555)).timestamp())
            }
            self.table.put_item(Item=org_item)
            return True
        except ClientError as e:
            self.logger.error(f"Error upserting organization: {e}")
            return False
    
    def store_submission(self, submission: Submission) -> bool:
        """
        Store a complete submission in the DynamoDB database.

        Args:
            submission (Submission): Submission object containing all required fields and nested data.

        Returns:
            bool: True if the operation succeeded, False if there was a FRANKStorageError.

        Raises:
            Logs error and returns False if batch write fails.
        """

        timestamp = submission.timestamp or datetime.now(timezone.utc)
        timestamp_str = timestamp.isoformat()
        
        # Serialize the complete submission to JSON
        submission_json = submission.model_dump_json(by_alias=True, exclude_none=True)
        
        # Create the main submission item
        submission_item = {
            'PK': f"SUB#{submission.submission_id}",
            'SK': 'SUB',
            'GSI1PK': f"ORG#{submission.submitter.organization_id}",
            'GSI1SK': timestamp_str,
            'EntityType': 'Submission',
            'submission_id': submission.submission_id,
            'submitter_id': submission.submitter.organization_id,
            'submission_timestamp': timestamp_str,
            'confidence': submission.sighting.confidence,
            'severity': submission.sighting.severity,
            'tlp_level': submission.tlp_level,
            'submission_data': submission_json,  # Complete submission as JSON
            'processed_at': timestamp_str,
            'TTL': int((timestamp + timedelta(days=2555)).timestamp())
        }
        
        items_to_write = [submission_item]

        # Store organization info for querying
        org_item = {
            'PK': f"ORG#{submission.submitter.organization_id}",
            'SK': 'ORG',
            'GSI1PK': f"TIER#{submission.submitter.tier}",
            'GSI1SK': timestamp_str,
            'EntityType': 'Organization',
            'organization_id': submission.submitter.organization_id,
            'tier': submission.submitter.tier,
            'sector': submission.submitter.sector,
            'region': submission.submitter.region,
            'last_active': timestamp_str,
            'TTL': int((timestamp + timedelta(days=2555)).timestamp())
        }

        items_to_write.append(org_item)

        # Store sighting info as a separate item
        sighting = submission.sighting
        sighting_item = {
            'PK': f"SIGHT#{sighting.sighting_id}",
            'SK': f"SUB#{submission.submission_id}",
            'GSI1PK': f"ORG#{submission.submitter.organization_id}",
            'GSI1SK': timestamp_str,
            'EntityType': 'Sighting',
            'sighting_id': sighting.sighting_id,
            'submission_id': submission.submission_id,
            'submitter_id': submission.submitter.organization_id,
            'confidence': sighting.confidence,
            'severity': sighting.severity,
            'timestamp': timestamp_str,
            'observables': sighting.observables.model_dump(exclude_none=True, by_alias=True),
            'TTL': int((timestamp + timedelta(days=2555)).timestamp())
        }
        
        items_to_write.append(sighting_item)

        # Store access log
        access_log_item = {
            'PK': f"LOG#{submission.submitter.organization_id}",
            'SK': f"LOG#{timestamp_str}#{uuid.uuid4()}",
            'GSI1PK': 'ACTION#SUBMIT',
            'GSI1SK': timestamp_str,
            'EntityType': 'AccessLog',
            'organization_id': submission.submitter.organization_id,
            'action': 'SUBMIT',
            'resource_type': 'submission',
            'resource_id': submission.submission_id,
            'timestamp': timestamp_str,
            'success': True,
            'TTL': int((timestamp + timedelta(days=90)).timestamp())
        }
        
        # Batch write all items
        items_to_write.append(access_log_item)

        observables = submission.sighting.observables.model_dump(exclude_none=True, by_alias=True)
        
        for obs_category, obs_list in observables.items():
            if isinstance(obs_list, list):
                for obs in obs_list:
                    if 'type' not in obs or 'value' not in obs:
                        continue
                    
                    obs_hash = self.hash_observable(obs['type'], obs['value'])
                    
                    # Create observable index item
                    observable_index_item = {
                        'PK': f"OBS#{obs_hash}",
                        'SK': f"SUB#{submission.submission_id}",
                        'GSI1PK': f"TYPE#{obs['type']}",
                        'GSI1SK': timestamp_str,
                        'EntityType': 'ObservableIndex',
                        'observable_hash': obs_hash,
                        'observable_type': obs['type'],
                        'observable_value': obs['value'],
                        'submission_id': submission.submission_id,
                        'submitter_id': submission.submitter.organization_id,
                        'sighting_id': submission.sighting.sighting_id,
                        'confidence': submission.sighting.confidence,
                        'severity': submission.sighting.severity,
                        'role': obs.get('role'),
                        'port': obs.get('port'),
                        'first_seen': obs.get('first_seen', timestamp).isoformat(),
                        'timestamp': timestamp_str,
                        'TTL': int((timestamp + timedelta(days=2555)).timestamp())
                    }
                    items_to_write.append(observable_index_item)

        try:
            self._batch_write_items(items_to_write)
            return True
        except FRANKStorageError:
            return False
    

    def _batch_write_items(self, items: List[Dict]) -> None:
        """Execute batch atomic write operation with automatic retry for unprocessed items."""
        # DynamoDB batch write limit is 25 items
        chunk_size = 25
        
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            
            transact_items = [
                {'Put': 
                    {
                        'TableName': self.table_name,
                        'Item': self._convert_floats_to_decimal(item)
                    }
                }
                for item in chunk
            ]
            
            try:
                response = self.client.transact_write_items(TransactItems=transact_items)
                
                # Handle unprocessed items
                unprocessed_items = response.get('UnprocessedItems', {})
                while unprocessed_items:
                    self.logger.warning(f"Retrying {len(unprocessed_items)} unprocessed items")
                    response = self.client.transact_write_items(TransactItems=unprocessed_items)
                    unprocessed_items = response.get('UnprocessedItems', {})
                    
            except ClientError as e:
                self.logger.error(f"Batch write failed: {e}")
                raise FRANKStorageError(f"Batch write operation failed: {e}")


    def get_submission_by_id(self, submission_id: str, org_id: str, access_level: TierLevel = TierLevel.CONTRIBUTOR) -> Optional[Submission]:
        """
        Retrieve a specific submission with access level filtering.

        Args:
            submission_id: Submission ID to retrieve
            org_id: Organization ID making the request
            access_level: Access level for filtering

        Returns:
            Filtered Submission or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    'PK': f"SUB#{submission_id}",
                    'SK': 'SUB'
                }
            )
            if 'Item' not in response:
                return None

            # Deserialize and filter
            item = self._convert_decimals_to_float(response['Item'])
            submission_json = item.get('submission_data')
            if not submission_json:
                return None

            # If stored as JSON string, parse it
            if isinstance(submission_json, str):
                import json
                submission_dict = json.loads(submission_json)
            else:
                submission_dict = submission_json

            filtered_submission = self._filter_submission_by_access_level(submission_dict, access_level)

            # Log access
            self._log_access(org_id, 'READ', 'submission', submission_id)

            return Submission(**filtered_submission)
        except ClientError as e:
            self.logger.error(f"Error retrieving submission {submission_id}: {e}")
            raise FRANKQueryError(f"Failed to retrieve submission: {e}")
    
    def query_observables(self, org_id: str, observable_type: ObservableType = None, 
                         limit: int = 100, access_level: TierLevel = TierLevel.CONTRIBUTOR) -> List[Observable]:
        """Query observables with access level filtering."""
        try:
            # Query by observable_type using GSI1 if provided, else scan all ObservableIndex
            if observable_type:
                response = self.table.query(
                    IndexName='GSI1',
                    KeyConditionExpression='GSI1PK = :type_key',
                    FilterExpression='EntityType = :entity_type',
                    ExpressionAttributeValues={
                        ':type_key': f"TYPE#{observable_type.value if hasattr(observable_type, 'value') else str(observable_type)}",
                        ':entity_type': 'ObservableIndex'
                    },
                    Limit=limit,
                    ScanIndexForward=False
                )
            else:
                response = self.table.scan(
                    FilterExpression='EntityType = :entity_type',
                    ExpressionAttributeValues={':entity_type': 'ObservableIndex'},
                    Limit=limit
                )

            # Aggregate and deduplicate by observable_hash
            observables_map = {}
            for item in response.get('Items', []):
                item = self._convert_decimals_to_float(item)
                obs_hash = item.get('observable_hash')
                if not obs_hash:
                    continue

                # Initialize aggregation entry
                if obs_hash not in observables_map:
                    observables_map[obs_hash] = {
                        'observable_hash': obs_hash,
                        'observable_type': item.get('observable_type'),
                        'observable_value': item.get('observable_value'),
                        'total_sightings': 0,
                        'first_seen': item.get('timestamp'),
                        'last_seen': item.get('timestamp'),
                        'unique_organizations': set(),
                        'confidence_values': []
                    }

                obs_entry = observables_map[obs_hash]
                obs_entry['total_sightings'] += 1
                org_id_val = item.get('submitter_org_id')
                if org_id_val:
                    obs_entry['unique_organizations'].add(org_id_val)
                obs_entry['confidence_values'].append(item.get('confidence', 0))

                # Update time bounds
                ts = item.get('timestamp')
                if ts:
                    if obs_entry['first_seen'] is None or ts < obs_entry['first_seen']:
                        obs_entry['first_seen'] = ts
                    if obs_entry['last_seen'] is None or ts > obs_entry['last_seen']:
                        obs_entry['last_seen'] = ts

            # Convert to final format
            results = []
            for obs_hash, obs_data in observables_map.items():
                obs_data['unique_organizations'] = len(obs_data['unique_organizations'])
                obs_data['avg_confidence'] = (
                    sum(obs_data['confidence_values']) / len(obs_data['confidence_values'])
                    if obs_data['confidence_values'] else 0
                )
                del obs_data['confidence_values']

                # Apply access level filtering if needed
                filtered_obs = self._filter_observable_by_access_level(obs_data, access_level)
                results.append(filtered_obs)

            # Log access
            self._log_access(org_id, 'QUERY', 'observables')
            return results[:limit]
        except ClientError as e:
            self.logger.error(f"Error querying observables: {e}")
            raise FRANKQueryError(f"Failed to query observables: {e}")
    
    def get_statistics_summary(self, org_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get platform statistics summary for an organization, including totals of observables by type.

        Args:
            org_id (str): The organization ID to get statistics for.
            days (int, optional): Number of days to include in the summary (default: 30).

        Returns:
            Dict[str, Any]: Dictionary containing summary statistics.
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            # Scan for ObservableIndex items (OBS#)
            response = self.table.scan(
                FilterExpression='begins_with(PK, :obs_prefix) AND EntityType = :entity_type AND #ts >= :cutoff',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':obs_prefix': 'OBS#',
                    ':entity_type': 'ObservableIndex',
                    ':cutoff': cutoff_date.isoformat()
                }
            )
            totals_by_type = {}
            for item in response.get('Items', []):
                item = self._convert_decimals_to_float(item)
                obs_type = item.get('observable_type', 'unknown')
                totals_by_type[obs_type] = totals_by_type.get(obs_type, 0) + 1

            return {
                'organization_id': org_id,
                'days': days,
                'observable_totals': totals_by_type,
                'total_observables': sum(totals_by_type.values())
            }
        except ClientError as e:
            self.logger.error(f"Error calculating statistics summary: {e}")
            return {
                'organization_id': org_id,
                'days': days,
                'observable_totals': {},
                'total_observables': 0,
                'error': str(e)
            }

    def _log_access(self, org_id: str, action: str, resource_type: str = None, resource_id: str = None, details: Dict[str, Any] = None) -> None:
        """Internal method to log access in DynamoDB single table design."""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_item = {
            'PK': f"LOG#{org_id}",
            'SK': f"LOG#{timestamp}",
            'GSI1PK': f"ACTION#{action}",
            'GSI1SK': timestamp,
            'EntityType': 'AccessLog',
            'organization_id': org_id,
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'timestamp': timestamp,
            'success': True,
            'TTL': int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())
        }
        if details:
            log_item['details'] = details
        try:
            self.table.put_item(Item=log_item)
        except ClientError as e:
            self.logger.error(f"Error logging access: {e}")
            raise FRANKQueryError(f"Failed to log access: {e}")

    def log_access(self, org_id: str, action: str, resource_type: str = None, resource_id: str = None, details: Dict[str, Any] = None) -> bool:
        """Log an access event for auditing purposes in DynamoDB."""
        try:
            self._log_access(org_id, action, resource_type, resource_id, details)
            self.logger.info(f"Access stored for {org_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error logging access: {e}")
            return False

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the database."""
        return {
            'status': 'healthy',
            'database_table': self.table_name,
            'database_region': self.region,
            "stack": self.environment
        }
    
# def _create_observable_index_items(self, submission: Submission) -> List[Dict]:
#     """Create separate index items for observables."""
#     items = []
#     timestamp = datetime.now(timezone.utc)
    
#     observables = submission.sighting.observables.model_dump(exclude_none=True, by_alias=True)
    
#     for obs_category, obs_list in observables.items():
#         if isinstance(obs_list, list):
#             for obs in obs_list:
#                 if 'type' not in obs or 'value' not in obs:
#                     continue
                
#                 obs_hash = self.hash_observable(obs['type'], obs['value'])
                
#                 # Create observable index item
#                 obs_item = {
#                     'PK': f"OBSIDX#{obs_hash}",
#                     'SK': f"SUB#{submission.submission_id}",
#                     'GSI1PK': f"TYPE#{obs['type']}",
#                     'GSI1SK': submission.timestamp or timestamp.isoformat(),
#                     'EntityType': 'ObservableIndex',
#                     'observable_hash': obs_hash,
#                     'observable_type': obs['type'],
#                     'observable_value': obs['value'],
#                     'submission_id': submission.submission_id,
#                     'submitter_org_id': submission.submitter.organization_id,
#                     'confidence': submission.sighting.confidence,
#                     'severity': submission.sighting.severity,
#                     'first_seen': obs.get('first_seen'),
#                     'timestamp': submission.timestamp or timestamp.isoformat(),
#                     'TTL': int((timestamp + timedelta(days=2555)).timestamp())
#                 }
#                 items.append(obs_item)
    
#     return items

# def query_observables(self, org_id: str, observable_type: str = None, 
#                      limit: int = 100, access_level: str = 'contributor',
#                      min_confidence: int = None, sectors: List[str] = None,
#                      days_back: int = None) -> List[Dict[str, Any]]:
#     """Query observables using the observable index."""
#     try:
#         if observable_type:
#             # Query by type using GSI1
#             response = self.table.query(
#                 IndexName='GSI1',
#                 KeyConditionExpression='GSI1PK = :type_key',
#                 FilterExpression='EntityType = :entity_type',
#                 ExpressionAttributeValues={
#                     ':type_key': f"TYPE#{observable_type}",
#                     ':entity_type': 'ObservableIndex'
#                 },
#                 Limit=limit,
#                 ScanIndexForward=False
#             )
#         else:
#             # Scan for all observable indexes
#             response = self.table.scan(
#                 FilterExpression='EntityType = :entity_type',
#                 ExpressionAttributeValues={':entity_type': 'ObservableIndex'},
#                 Limit=limit
#             )
        
#         # Process and deduplicate results
#         observables_map = {}
        
#         for item in response.get('Items', []):
#             item = self._convert_decimals_to_float(item)
            
#             # Apply filters
#             if min_confidence and item.get('confidence', 0) < min_confidence:
#                 continue
                
#             if days_back:
#                 item_time = datetime.fromisoformat(item.get('timestamp', '1970-01-01'))
#                 cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
#                 if item_time < cutoff:
#                     continue
            
#             obs_hash = item['observable_hash']
            
#             # Aggregate by hash (deduplication)
#             if obs_hash not in observables_map:
#                 observables_map[obs_hash] = {
#                     'observable_hash': obs_hash,
#                     'observable_type': item['observable_type'],
#                     'observable_value': item['observable_value'],
#                     'total_sightings': 0,
#                     'first_seen': item.get('timestamp'),
#                     'last_seen': item.get('timestamp'),
#                     'unique_organizations': set(),
#                     'confidence_values': []
#                 }
            
#             obs_entry = observables_map[obs_hash]
#             obs_entry['total_sightings'] += 1
#             obs_entry['unique_organizations'].add(item.get('submitter_org_id'))
#             obs_entry['confidence_values'].append(item.get('confidence', 0))
            
#             # Update time bounds
#             if item.get('timestamp') < obs_entry['first_seen']:
#                 obs_entry['first_seen'] = item.get('timestamp')
#             if item.get('timestamp') > obs_entry['last_seen']:
#                 obs_entry['last_seen'] = item.get('timestamp')
        
#         # Convert to final format
#         results = []
#         for obs_hash, obs_data in observables_map.items():
#             obs_data['unique_organizations'] = len(obs_data['unique_organizations'])
#             obs_data['avg_confidence'] = (
#                 sum(obs_data['confidence_values']) / len(obs_data['confidence_values'])
#                 if obs_data['confidence_values'] else 0
#             )
#             del obs_data['confidence_values']
            
#             # Apply access level filtering
#             filtered_obs = self._filter_observable_by_access_level(obs_data, access_level)
#             results.append(filtered_obs)
        
#         # Log access
#         self._log_access_async(org_id, 'QUERY', 'observables')
        
#         return results[:limit]
        
#     except ClientError as e:
#         self.logger.error(f"Error querying observables: {e}")
#         raise FRANKQueryError(f"Failed to query observables: {e}")

#     def get_access_logs(self, org_id: str, days: int = 7, 
#                        actions: List[str] = None) -> List[Dict[str, Any]]:
#         """
#         Get access logs for auditing using DynamoDB query.
        
#         Args:
#             org_id: Organization to get logs for
#             days: Number of days to look back
#             actions: Filter by specific actions
            
#         Returns:
#             List of access log entries
#         """
#         try:
#             cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
#             response = self.table.query(
#                 KeyConditionExpression='PK = :org_key AND SK >= :cutoff_sk',
#                 ExpressionAttributeValues={
#                     ':org_key': f"LOG#{org_id}",
#                     ':cutoff_sk': f"LOG#{cutoff_date.isoformat()}"
#                 },
#                 ScanIndexForward=False,  # Most recent first
#                 Limit=1000
#             )
            
#             results = []
#             for item in response.get('Items', []):
#                 item = self._convert_decimals_to_float(item)
                
#                 # Filter by actions if specified
#                 if actions and item.get('action') not in actions:
#                     continue
                
#                 # Parse details JSON if present
#                 if 'details_json' in item:
#                     try:
#                         item['details'] = json.loads(item['details_json'])
#                         del item['details_json']
#                     except:
#                         item['details'] = {}
#                         del item['details_json']
                
#                 # Remove DynamoDB-specific fields
#                 log_data = {k: v for k, v in item.items() 
#                           if k not in ['PK', 'SK', 'GSI1PK', 'GSI1SK', 'EntityType', 'TTL']}
#                 results.append(log_data)
            
#             return results
            
#         except ClientError as e:
#             self.logger.error(f"Error getting access logs: {e}")
#             raise FRANKQueryError(f"Failed to get access logs: {e}")


#     def search_observables_by_value(self, org_id: str, search_value: str, 
#                                    access_level: str = 'contributor') -> List[Dict[str, Any]]:
#         """
#         Search for observables by partial value match using DynamoDB scan.
        
#         Args:
#             org_id: Organization performing the search
#             search_value: Value to search for
#             access_level: Access level for filtering
            
#         Returns:
#             List of matching observables
#         """
#         try:
#             response = self.table.scan(
#                 FilterExpression='EntityType = :entity_type AND contains(observable_value, :search_value)',
#                 ExpressionAttributeValues={
#                     ':entity_type': 'ObservableStatistics',
#                     ':search_value': search_value
#                 },
#                 Limit=100
#             )
            
#             results = []
#             for item in response.get('Items', []):
#                 item = self._convert_decimals_to_float(item)
#                 result = self._filter_observable_by_access_level(item, access_level)
#                 results.append(result)
            
#             # Log access
#             self._log_access_async(org_id, 'SEARCH', 'observables', details={'search_value': search_value})
            
#             return results
            
#         except ClientError as e:
#             self.logger.error(f"Error searching observables: {e}")
#             raise FRANKQueryError(f"Failed to search observables: {e}")

#     def get_organization_info(self, org_id: str) -> Optional[Dict[str, Any]]:
#         """
#         Get organization information using DynamoDB query.
        
#         Args:
#             org_id: Organization ID to look up
            
#         Returns:
#             Organization data or None if not found
#         """
#         try:
#             response = self.table.get_item(
#                 Key={
#                     'PK': f"ORG#{org_id}",
#                     'SK': 'ORG'
#                 }
#             )
            
#             if 'Item' not in response:
#                 return None
            
#             item = self._convert_decimals_to_float(response['Item'])
            
#             # Remove DynamoDB-specific fields
#             org_data = {k: v for k, v in item.items() 
#                        if k not in ['PK', 'SK', 'GSI1PK', 'GSI1SK', 'EntityType', 'TTL']}
            
#             return org_data
            
#         except ClientError as e:
#             self.logger.error(f"Error getting organization info: {e}")
#             return None

#     def cleanup_old_data(self, days: int = 90) -> int:
#         """
#         Clean up old data using TTL (Time To Live) feature.
#         DynamoDB automatically handles cleanup based on TTL values.
        
#         Args:
#             days: This parameter is maintained for API compatibility but 
#                   actual cleanup is handled by DynamoDB TTL
            
#         Returns:
#             Number of records that would be eligible for cleanup
#         """
#         try:
#             cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
#             # Count items that would be eligible for cleanup
#             # In production, DynamoDB TTL handles actual deletion
#             response = self.table.scan(
#                 FilterExpression='EntityType IN (:sub, :log) AND #ts < :cutoff',
#                 ExpressionAttributeNames={
#                     '#ts': 'timestamp'
#                 },
#                 ExpressionAttributeValues={
#                     ':sub': 'Submission',
#                     ':log': 'AccessLog',
#                     ':cutoff': cutoff_date.isoformat()
#                 },
#                 Select='COUNT'
#             )
            
#             count = response.get('Count', 0)
#             self.logger.info(f"Found {count} items eligible for cleanup (handled by DynamoDB TTL)")
#             return count
            
#         except ClientError as e:
#             self.logger.error(f"Error during cleanup check: {e}")
#             return 0


#     def update_observable_statistics(self, obs_hash: str, increment_count: int = 1) -> None:
#         """
#         Update observable statistics using DynamoDB atomic counters.
        
#         Args:
#             obs_hash: Observable hash to update
#             increment_count: Amount to increment counters by
#         """
#         try:
#             self.table.update_item(
#                 Key={
#                     'PK': f"STAT#{obs_hash}",
#                     'SK': 'STAT'
#                 },
#                 UpdateExpression='ADD total_sightings :inc, unique_organizations :inc SET last_seen = :timestamp',
#                 ExpressionAttributeValues={
#                     ':inc': increment_count,
#                     ':timestamp': datetime.now(timezone.utc).isoformat()
#                 }
#             )
#         except ClientError as e:
#             self.logger.warning(f"Failed to update observable statistics: {e}")

# Factory function for easy instantiation
def create_dynamodb_database(table_name: str = "frank-platform", 
                            region: str = "eu-west-1",
                            endpoint: str = "http://localstack:4566",
                            aws_access_key_id = "test",
                            aws_secret_access_key = "test",
                            logger: Optional[logging.Logger] = None) -> DynamoDBFRANKDatabase:
    """
    Factory function to create a DynamoDBFRANKDatabase instance.
    
    Args:
        table_name: DynamoDB table name
        region: AWS region
        logger: provide external logger
    Returns:
        Configured DynamoDBFRANKDatabase instance
    """
    # Set up logging
    if not logger:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)

    config = {
        "DYNAMODB_TABLE": table_name,
        "LOCALSTACK_ENDPOINT": endpoint,
        "AWS_ACCESS_KEY_ID": aws_access_key_id, 
        "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
        "AWS_DEFAULT_REGION": region
    }
    return DynamoDBFRANKDatabase(connection_params=config, logger=logger)

if __name__ == "__main__":
    # Example usage and table creation
    import sys
    
    create_dynamodb_database(table_name='frank_table', region="eu-west-1")
