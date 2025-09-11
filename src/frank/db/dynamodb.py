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

from frank.db.exceptions import FRANKConnectionError, FRANKQueryError
from frank.db.base import BaseFRANKDatabase
from frank.core.models import Submission, Observable
from frank.core.enum import ObservableType, TierLevel


class DynamoDBFRANKDatabase(BaseFRANKDatabase):
    """
    DynamoDB implementation of FRANK database using single table design.
    Provides full functionality with NoSQL scalability and supports
    the complete FRANK access tier model.
    
    Single Table Design Pattern:
    PK (Partition Key) | SK (Sort Key) | GSI1PK | GSI1SK | Entity Type | Description
    ORG#{org_id}      | ORG           | TIER#{tier} | #{timestamp} | Organization | Organization metadata
    SUB#{sub_id}      | SUB           | ORG#{org_id} | #{timestamp} | Submission | Complete submission with nested data
    LOG#{org_id}      | LOG#{timestamp} | ACTION#{action} | #{timestamp} | Access Log | Audit trail for actions
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
                response = self.dynamodb.create_table(**table_definition)
                
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
        """Insert or update organization information."""
        pass
    
    def store_submission(self, submission: Submission) -> bool:
        """Store a complete submission in the database."""
        pass
    
    def get_submission_by_id(self, submission_id: str, org_id: str, access_level: TierLevel = TierLevel.CONTRIBUTOR) -> Optional[Submission]:
        """Retrieve a specific submission with access level filtering."""
        pass
    
    def query_observables(self, org_id: str, observable_type: ObservableType = None, 
                         limit: int = 100, access_level: TierLevel = TierLevel.CONTRIBUTOR) -> List[Observable]:
        """Query observables with access level filtering."""
        pass
    
    def get_statistics_summary(self, org_id: str, days: int = 30) -> Dict[str, Any]:
        """Get platform statistics summary."""
        pass

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
    
# def store_submission(self, submission: Submission) -> bool:
#     """
#     Store a complete submission directly as a dict in DynamoDB using single table design.
    
#     Args:
#         submission: Complete FRANK submission object
        
#     Returns:
#         True if stored successfully, False otherwise
#     """
#     self.logger.info(f"Storing submission: {submission.submission_id}")
    
#     try:
#         timestamp = datetime.now(timezone.utc)
#         timestamp_str = timestamp.isoformat()
        
#         # Convert submission to dict and handle float->Decimal conversion for DynamoDB
#         submission_dict = submission.model_dump(by_alias=True, exclude_none=True)
#         submission_data = self._convert_floats_to_decimal(submission_dict)
        
#         # Create the main submission item
#         submission_item = {
#             'PK': f"SUB#{submission.submission_id}",
#             'SK': 'SUB',
#             'GSI1PK': f"ORG#{submission.submitter.organization_id}",
#             'GSI1SK': submission.timestamp or timestamp_str,
#             'EntityType': 'Submission',
#             'submission_id': submission.submission_id,
#             'submitter_org_id': submission.submitter.organization_id,
#             'submission_timestamp': submission.timestamp or timestamp_str,
#             'confidence': submission.sighting.confidence,
#             'severity': submission.sighting.severity,
#             'tlp_level': submission.tlp_level,
#             'submission_data': submission_data,  # Complete submission as native DynamoDB dict
#             'processed_at': timestamp_str,
#             'TTL': int((timestamp + timedelta(days=2555)).timestamp())
#         }
        
#         # Store organization info for querying
#         org_item = {
#             'PK': f"ORG#{submission.submitter.organization_id}",
#             'SK': 'ORG',
#             'GSI1PK': f"TIER#{submission.submitter.tier}",
#             'GSI1SK': timestamp_str,
#             'EntityType': 'Organization',
#             'organization_id': submission.submitter.organization_id,
#             'tier': submission.submitter.tier,
#             'sector': submission.submitter.sector,
#             'region': submission.submitter.region,
#             'last_active': timestamp_str,
#             'TTL': int((timestamp + timedelta(days=2555)).timestamp())
#         }
        
#         # Store access log
#         access_log_item = {
#             'PK': f"LOG#{submission.submitter.organization_id}",
#             'SK': f"LOG#{timestamp_str}#{uuid.uuid4()}",
#             'GSI1PK': 'ACTION#SUBMIT',
#             'GSI1SK': timestamp_str,
#             'EntityType': 'AccessLog',
#             'organization_id': submission.submitter.organization_id,
#             'action': 'SUBMIT',
#             'resource_type': 'submission',
#             'resource_id': submission.submission_id,
#             'timestamp': timestamp_str,
#             'success': True,
#             'TTL': int((timestamp + timedelta(days=90)).timestamp())
#         }
        
#         # Batch write all items
#         items_to_write = [submission_item, org_item, access_log_item]

#         # Additionally create observable index entries
#         observable_items = self._create_observable_index_items(submission)
#         items_to_write.extend(observable_items)

#         self._batch_write_items(items_to_write)
        
#         self.logger.info(f"Successfully stored submission {submission.submission_id}")
#         return True
        
#     except Exception as e:
#         self.logger.error(f"Error storing submission: {e}")
#         if isinstance(e, (FRANKStorageError, FRANKConnectionError)):
#             raise
#         raise FRANKStorageError(f"Failed to store submission: {e}")


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

#     def _filter_submission_by_access_level(self, submission: Dict[str, Any], access_level: str) -> Dict[str, Any]:
#         """Filter submission data based on access level."""
#         if access_level == 'public':
#             return {
#                 'submission_id': submission.get('submission_id'),
#                 'timestamp': submission.get('timestamp'),
#                 'sighting': {
#                     'confidence': submission.get('sighting', {}).get('confidence'),
#                     'timestamp': submission.get('sighting', {}).get('timestamp'),
#                     'observation_count': submission.get('sighting', {}).get('observation_count')
#                 }
#             }
#         elif access_level == 'observer':
#             filtered = self._deep_copy(submission)
#             # Apply observer-level filtering
#             if 'hit_target' in filtered:
#                 filtered.pop('hit_target', None)
#             if 'tlp_level' in filtered:
#                 filtered.pop('tlp_level', None)
#             return filtered
#         elif access_level == 'contributor':
#             filtered = self._deep_copy(submission)
#             # Apply contributor-level filtering
#             if 'hit_target' in filtered:
#                 hit_target = filtered['hit_target']
#                 hit_target.pop('organization_id', None)
#             return filtered
        
#         # Partner and core_member get full access
#         return submission

#     def _filter_observable_by_access_level(self, observable: Dict[str, Any], access_level: str) -> Dict[str, Any]:
#         """Filter observable data based on access level."""
#         if access_level == 'public':
#             return {
#                 'observable_type': observable.get('observable_type'),
#                 'total_sightings': observable.get('total_sightings'),
#                 'last_seen': observable.get('last_seen')
#             }
#         elif access_level == 'observer':
#             filtered = dict(observable)
#             # Mask observable value
#             if 'observable_value' in filtered:
#                 value = filtered['observable_value']
#                 filtered['observable_value'] = value[:10] + "..." if len(value) > 10 else value
#             return filtered
        
#         # Contributor and above get full access
#         return observable
    
#     def _deep_copy(self, obj: Any) -> Any:
#         """Create a deep copy of an object."""
#         if isinstance(obj, dict):
#             return {k: self._deep_copy(v) for k, v in obj.items()}
#         elif isinstance(obj, list):
#             return [self._deep_copy(item) for item in obj]
#         else:
#             return obj

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
