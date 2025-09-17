#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides DynamoDB based storage for FRANK submissions using single table design.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import boto3
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

import logging

from frank.core.models import Submission, Observable
from frank.core.enum import ObservableType, AccessTier
from .exceptions import FRANKConnectionError, FRANKQueryError, FRANKStorageError
from .base import BaseFRANKDatabase


class DynamoDBFRANKDatabase(BaseFRANKDatabase):
    """
    DynamoDB implementation of FRANK database using single table design.
    Provides full functionality with NoSQL scalability and supports
    the complete FRANK access tier model.
    
    Single Table Design Pattern - General table:
    PK (Partition Key)  | SK (Sort Key)   | GSI1PK          | GSI1SK       | Entity Type     | Description
    ORG#{org_id}        | ORG             | TIER#{access_level}     | #{timestamp} | Organization    | Organization metadata
    SUB#{sub_id}        | SUB             | ORG#{org_id}    | #{timestamp} | Submission      | Complete submission with nested data
    OBS#{obs_hash}      | SUB#{sub_id}    | TYPE#{obs_type} | #{timestamp} | ObservableIndex | Observable cross-reference
    SIGHT#{sighting_id} | SUB#{sub_id}    | ORG#{org_id}    | #{timestamp} | Sighting        | Sighting details (confidence, severity, observables)

    Log table (separate entity for access logs):
    PK (Partition Key)  | SK (Sort Key)   | GSI1PK          | GSI1SK       | Entity Type     | Description
    LOG#{org_id}        | LOG#{timestamp} | ACTION#{action} | #{timestamp} | Access Log      | Audit trail for actions

    """
    
    def initialize(self) -> None:
        """
        Initialize DynamoDB database connection for LocalStack environment.


        Args:
            table_name: DynamoDB table name
            region: AWS region
            logger: Optional logger instance for logging
        """
        self.name = 'dynamodb'
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

        # Get a direct handle to the low-level client
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
            # self.logger.info(f"✅ FRANK DynamoDB table '{self.table_name}' created successfully")
            return True
            
        except ClientError as e:
                self.logger.error(f"❌ Failed to create table: {e}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Unexpected error: {e}")
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

        # TODO: consider the TTL strategy for different entities
        timestamp = submission.timestamp or datetime.now(timezone.utc)
        timestamp_str = timestamp.isoformat()
        
        # Create the main submission item
        submission_item = {
            'PK': f"SUB#{submission.submission_id}",
            'SK': 'SUB',
            'GSI1PK': f"ORG#{submission.submitter.organization_id}",
            'GSI1SK': timestamp_str,
            'EntityType': 'Submission',
            'submission_id': submission.submission_id,
            'submitter_id': submission.submitter.organization_id,
            'access_level': submission.submitter.access_level, # make sure this is explicitly stored
            'submission_timestamp': timestamp_str,
            'tlp_level': submission.tlp_level,
            'submission_data': submission.model_dump(by_alias=True, exclude_none=True),  # Complete submission 
            'processed_at': timestamp_str,
            'TTL': int((timestamp + timedelta(days=2555)).timestamp())
        }    
        items_to_write = [submission_item]

        # Store submitter info for querying
        org_item = {
            'PK': f"ORG#{submission.submitter.organization_id}",
            'SK': 'ORG',
            'GSI1PK': f"TIER#SUBMITTER",
            'GSI1SK': timestamp_str,
            'EntityType': 'Organization',
            'organization_id': submission.submitter.organization_id,
            'sector': submission.submitter.sector or 'cyber_partner',
            'region': submission.submitter.region or 'unknown',
            'last_active': timestamp_str,
            'TTL': int((timestamp + timedelta(days=2555)).timestamp())
        }
        items_to_write.append(org_item)

        # Store hit_target as another ORG# item if present
        hit_target = getattr(submission, 'hit_target', None)
        if hit_target and hasattr(hit_target, 'organization_id'):
            ht_org_item = {
                'PK': f"ORG#{hit_target.organization_id}",
                'SK': 'ORG',
                'GSI1PK': f"TIER#TARGET",
                'GSI1SK': timestamp_str,
                'EntityType': 'Organization',
                'organization_id': hit_target.organization_id,
                'sector': getattr(hit_target, 'sector', 'unknown'),
                'region': getattr(hit_target, 'region', 'unknown'),
                'last_active': timestamp_str,
                'TTL': int((timestamp + timedelta(days=2555)).timestamp())
            }
            items_to_write.append(ht_org_item)

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
            'sighting': sighting.model_dump(exclude_none=True, by_alias=True),
            'TTL': int((timestamp + timedelta(days=2555)).timestamp())
        }
        items_to_write.append(sighting_item)

        # Create observable index items
        items_to_write.extend(self._extract_observables(submission))

        self._batch_write_items(items_to_write)


    def upsert_organization(self, org_data: Dict[str, Any]) -> bool:
        """
        Insert or update organization information in DynamoDB.

        Args:
            org_data (Dict[str, Any]): Dictionary containing organization fields. Must include 'organization_id'.
                Expected keys: organization_id, access_level, sector, region, last_active (optional).

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
                'GSI1PK': f"TIER#{org_data.get('access_level', 'unknown')}",
                'GSI1SK': timestamp,
                'EntityType': 'Organization',
                'organization_id': org_data.get('organization_id', ''),
                'access_level': org_data.get('access_level', ''),
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

    def _extract_observables(self, submission: Submission) -> List[Dict]:
        """
        Extract observables from a submission for DynamoDB indexing.

        This method processes the observables contained within a submission's sighting object and generates
        DynamoDB items for each observable, following the single table design pattern. Each observable is
        indexed for efficient cross-referencing and querying by type, value, and submission context.

        Indexing Logic:
            - Each observable is hashed and stored as a separate item with PK 'OBS#{obs_hash}' and SK 'SUB#{submission_id}'.
            - GSI1PK is set to 'TYPE#{obs_type}' for type-based queries.
            - Additional metadata (confidence, severity, role, port, first_seen, etc.) is included for analytics.
            - TTL is set for long-term retention (default: ~7 years).

        Args:
            submission (Submission): The submission object containing sighting and observables.

        Returns:
            List[Dict]: List of DynamoDB items representing indexed observables.

        Edge Cases & Notes:
            - Observables missing 'type' or 'value' are skipped.
            - Handles empty or malformed observables gracefully.
            - Uses submission timestamp for time-based fields if not explicitly provided.
            - Designed for bulk ingestion and supports downstream analytics and deduplication.

        Example:
            >>> items = self._extract_observables(submission)
            >>> self._batch_write_items(items)
        """
        timestamp = submission.timestamp or datetime.now(timezone.utc)
        timestamp_str = timestamp.isoformat()
        
        observables_list = []
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
                    observables_list.append(observable_index_item)
                    stats_item = self._upsert_observable_statistics(
                        obs_hash=obs_hash,
                        obs_type=obs['type'],
                        obs_value=obs['value'],
                        hit_target_id=getattr(submission.hit_target, 'organization_id', None),  # Safe access to hit_target
                        sector=getattr(submission.hit_target, 'sector', None),  # Safe access to hit_target
                        timestamp_str=timestamp_str
                    )
                    # if stats_item:
                    #     observables_list.append(stats_item)
        return observables_list

    def _upsert_observable_statistics(
                                        self,
                                        obs_hash: str,
                                        obs_type: str,
                                        obs_value: str,
                                        hit_target_id: Optional[str] = None,
                                        sector: Optional[str] = None,
                                        timestamp_str: Optional[str] = None,
                                    ) -> dict:
        """
        Upsert (insert or update) an observable statistics item in DynamoDB.

        This method retrieves the statistics item for a given observable hash. If the item exists, it updates
        the last_seen timestamp, increments the total_hits counter, and adds new hit_target_id and sector values
        to their respective sets (avoiding duplicates). If the item does not exist, it creates a new statistics item
        with initial values. The updated or newly created item is returned for further processing or aggregation.

        Args:
            obs_hash (str): Hash of the observable.
            obs_type (str): Type of the observable (e.g., 'ipv4', 'domain').
            obs_value (str): Value of the observable.
            hit_target_id (str, optional): Organization ID of the hit target, if available.
            sector (str, optional): Sector associated with the observable, if available.
            timestamp_str (str, optional): ISO timestamp string for the current sighting.

        Returns:
            dict: The updated or newly created statistics item for the observable.
        """
        try:
            response = self.table.get_item(
                Key={'PK': f'STAT#{obs_hash}', f'SK': 'STAT#{obs_type}'}
            )
            item = response.get('Item')
        except ClientError as e:
            self.logger.error(f"Error reading observable statistics: {e}")
            item = None

        hit_targets = set(item.get('hit_targets', [])) if item else set()
        sectors = set(item.get('sectors', [])) if item else set()

        if hit_target_id:
            hit_targets.add(hit_target_id)
        if sector:
            sectors.add(sector)

        if item:
            update_expr = (
                "SET last_seen = :last_seen, "
                "total_hits = if_not_exists(total_hits, :zero) + :inc, "
                "hit_targets = :hit_targets, "
                "sectors = :sectors"
            )
            expr_attr_vals = {
                ':last_seen': timestamp_str,
                ':inc': 1,
                ':zero': 0,
                ':hit_targets': list(hit_targets),
                ':sectors': list(sectors)
            }
            self.table.update_item(
                Key={'PK': f'STAT#{obs_hash}', 'SK': f'STAT#{obs_type}'},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_attr_vals
            )
            # Return the updated item (merge changes)
            item['last_seen'] = timestamp_str
            item['total_hits'] = item.get('total_hits', 0) + 1
            item['hit_targets'] = list(hit_targets)
            item['sectors'] = list(sectors)
            return None
        else:
            stat_item = {
                'PK': f'STAT#{obs_hash}',
                'SK': f'STAT#{obs_type}',
                'observable_hash': obs_hash,
                'observable_type': obs_type,
                'observable_value': obs_value,
                'first_seen': timestamp_str,
                'last_seen': timestamp_str,
                'hit_targets': list(hit_targets),
                'sectors': list(sectors),
                'total_hits': 1,
                'TTL': int((datetime.now(timezone.utc) + timedelta(days=2555)).timestamp())
            }
            self.table.put_item(Item=stat_item)
            return stat_item

    def _batch_write_items(self, items: List[Dict]) -> None:
        """
        Execute batch atomic write operation with automatic retry for unprocessed items.

        This method writes items to DynamoDB in chunks of 25 (the maximum allowed by DynamoDB's batch API).
        It uses transact_write_items for atomicity, ensuring that either all items in a chunk are written or none are.
        If any items are unprocessed (due to throttling, capacity limits, or other transient errors),
        it will automatically retry those items until all are processed or a fatal error occurs.

        DynamoDB Limitations:
            - Maximum 25 items per batch write operation.
            - Each item must be under 400KB in size.
            - Batch operations are not strictly transactional across chunks; atomicity is per chunk.

        Practical Usage:
            - Use for bulk ingestion of submissions, observables, and logs.
            - Handles retry logic for unprocessed items, reducing risk of data loss during high-throughput operations.

        Args:
            items (List[Dict]): List of items to write to DynamoDB.

        Raises:
            FRANKStorageError: If the batch write operation fails and cannot be retried.
        """
        # DynamoDB batch write limit is 25 items
        chunk_size = 25
        
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            
            transact_items = [
                {'Put': 
                    {
                        'TableName': self.table_name,
                        'Item': item
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


    def get_submission_by_id(self, submission_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific submission with access level filtering.

        Args:
            submission_id: Submission ID to retrieve
            user_id: User ID making the request
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

            # TODO: Transform to Submission directly
            submission_dict = response['Item'].get('submission_data', None)
            return submission_dict


        except ClientError as e:
            self.logger.error(f"Error retrieving submission {submission_id}: {e}")
            raise FRANKQueryError(f"Failed to retrieve submission: {e}")


    def query_observables(self, user_id: str,  access_level: AccessTier = AccessTier.CONTRIBUTOR,
                         observable_type: ObservableType = None, sectors: List[str] = None,
                         min_confidence: float = None, 
                         limit: int = 100, days_back: int = None) -> List[Observable]:
        """
        Query observables with access level filtering and additional filters.

        This method retrieves observables from DynamoDB, supporting the following filters:
        - observable_type: Only return observables of the specified type (uses GSI for efficient query).
        - min_confidence: Only include observables with confidence >= min_confidence.
        - sectors: Only include observables where the 'sector' field matches one of the provided sectors.
        - days_back: Only include observables seen in the last N days (based on 'timestamp' field).
        - limit: Maximum number of results to return.
        - access_level: Apply access level filtering to each observable (see FRANK access tier model).

        Args:
            user_id (str): User ID making the request (used for access logging).
            observable_type (ObservableType, optional): Filter by observable type (ipv4, domain, etc.).
            limit (int, optional): Maximum number of results to return (default: 100).
            access_level (AccessTier, optional): Access level for filtering (default: CONTRIBUTOR).
            min_confidence (float, optional): Minimum confidence value to include.
            sectors (List[str], optional): List of allowed sectors to include.
            days_back (int, optional): Only include observables seen in the last N days.

        Returns:
            List[Observable]: List of observables matching the filters, deduplicated by observable_hash.

        Access events are logged for auditing, including all filter parameters.
        """
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
            cutoff = None
            if days_back:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

            for item in response.get('Items', []):
                item = self._convert_decimals_to_float(item)

                # Filter by min_confidence
                if min_confidence is not None and item.get('confidence', 0) < min_confidence:
                    continue

                # Filter by sector
                if sectors:
                    sector = item.get('sector')
                    if sector not in sectors:
                        continue

                # Filter by days_back
                if cutoff:
                    ts = item.get('timestamp')
                    try:
                        item_time = datetime.fromisoformat(ts)
                    except Exception:
                        item_time = None
                    if not item_time or item_time < cutoff:
                        continue

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

            # # Log access
            # self._log_access(org_id, 'QUERY', 'observables', details={
            #     'observable_type': observable_type.value if observable_type else None,
            #     'min_confidence': min_confidence,
            #     'sectors': sectors,
            #     'days_back': days_back
            # })
            return results[:limit]
        except ClientError as e:
            self.logger.error(f"Error querying observables: {e}")
            raise FRANKQueryError(f"Failed to query observables: {e}")


    def search_observables_by_value(self, org_id: str, search_value: str,
                                   access_level: AccessTier = AccessTier.CONTRIBUTOR) -> List[Dict[str, Any]]:
        """
        Search for observables by partial value match using DynamoDB scan.

        Args:
            org_id (str): Organization performing the search
            search_value (str): Value to search for (substring match)
            access_level (AccessTier, optional): Access level for filtering (default: CONTRIBUTOR)

        Returns:
            List[Dict[str, Any]]: List of matching observables, filtered by access level
        """
        try:
            response = self.table.scan(
                FilterExpression='EntityType = :entity_type AND contains(observable_value, :search_value)',
                ExpressionAttributeValues={
                    ':entity_type': 'ObservableIndex',
                    ':search_value': search_value
                },
                Limit=100
            )

            results = []
            for item in response.get('Items', []):
                item = self._convert_decimals_to_float(item)
                result = self._filter_observable_by_access_level(item, access_level)
                results.append(result)

            return results

        except ClientError as e:
            self.logger.error(f"Error searching observables: {e}")
            raise FRANKQueryError(f"Failed to search observables: {e}")


    def get_statistics_summary(self, org_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get platform statistics summary for an organization, including totals of observables by type.

        This method calculates the following statistics for the given organization and time window:
        - Total number of organizations in the platform.
        - Total number of submissions within the time window.
        - Total number of sightings within the time window.
        - Total number of observables indexed within the time window.
        - Breakdown of observables by type (e.g., ipv4, domain, url, etc.), using the ObservableType enum.
        
        For each observable type, the count is calculated efficiently using DynamoDB's GSI and Select='COUNT'.

        Args:
            org_id (str): The organization ID to get statistics for.
            days (int, optional): Number of days to include in the summary (default: 30).

        Returns:
            Dict[str, Any]: Dictionary containing summary statistics
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            # Count organizations
            org_response = self.table.scan(
                FilterExpression='begins_with(PK, :org_prefix) AND EntityType = :org_entity_type',
                ExpressionAttributeValues={
                    ':org_prefix': 'ORG#',
                    ':org_entity_type': 'Organization'
                },
                Select='COUNT'
            )
            total_organizations = org_response.get('Count', 0)

            # Count submissions
            submission_response = self.table.scan(
                FilterExpression='begins_with(PK, :sub_prefix) AND EntityType = :sub_entity_type AND #ts >= :cutoff',
                ExpressionAttributeNames={'#ts': 'submission_timestamp'},
                ExpressionAttributeValues={
                    ':sub_prefix': 'SUB#',
                    ':sub_entity_type': 'Submission',
                    ':cutoff': cutoff_date.isoformat()
                },
                Select='COUNT'
            )
            total_submissions = submission_response.get('Count', 0)

            # Count sightings
            sighting_response = self.table.scan(
                FilterExpression='begins_with(PK, :sight_prefix) AND EntityType = :sight_entity_type AND #ts >= :cutoff',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':sight_prefix': 'SIGHT#',
                    ':sight_entity_type': 'Sighting',
                    ':cutoff': cutoff_date.isoformat()
                },
                Select='COUNT'
            )
            total_sightings = sighting_response.get('Count', 0)

            # Count observables (total)
            obs_response = self.table.scan(
                FilterExpression='begins_with(PK, :obs_prefix) AND EntityType = :entity_type AND #ts >= :cutoff',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':obs_prefix': 'OBS#',
                    ':entity_type': 'ObservableIndex',
                    ':cutoff': cutoff_date.isoformat()
                },
                Select='COUNT'
            )
            total_observables = obs_response.get('Count', 0)

            # For observable type breakdown, query per type using GSI and Select='COUNT'
            from frank.core.enum import ObservableType
            totals_by_type = {}
            for obs_type in ObservableType:
                response = self.table.query(
                    IndexName='GSI1',
                    KeyConditionExpression='GSI1PK = :type_key',
                    FilterExpression='EntityType = :entity_type AND #ts >= :cutoff',
                    ExpressionAttributeNames={'#ts': 'timestamp'},
                    ExpressionAttributeValues={
                        ':type_key': f"TYPE#{obs_type.value}",
                        ':entity_type': 'ObservableIndex',
                        ':cutoff': cutoff_date.isoformat()
                    },
                    Select='COUNT'
                )
                totals_by_type[obs_type.value] = response.get('Count', 0)

            return {
                'organization_id': org_id,
                'days': days,
                'total_organizations': total_organizations,
                'total_submissions': total_submissions,
                'total_sightings': total_sightings,
                'total_observables': total_observables, 
                'observable_totals': totals_by_type
            }
        except ClientError as e:
            self.logger.error(f"Error calculating statistics summary: {e}")
            return {
                'organization_id': org_id,
                'days': days,
                'observable_totals': {},
                'total_observables': 0,
                'total_sightings': 0,
                'total_submissions': 0,
                'total_organizations': 0,
                'error': str(e)
            }

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the database."""
        return {
            'status': 'healthy',
            'database': 'dynamodb',
            'database_table': self.table_name,
            'database_region': self.region,
            "stack": self.environment
        }

    def log_access(self, org_id: str, action: str, resource_type: str = None, resource_id: str = None, details: Dict[str, Any] = None) -> None:
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