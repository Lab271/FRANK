#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides DynamoDB based storage for FRANK submissions using single table design.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from copy import deepcopy
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, Any, List, Optional

import boto3
from botocore.exceptions import ClientError

from frank.core.models import Submission, Observable, Sighting
from frank.core.enum import ObservableType, AccessTier
from .exceptions import FRANKQueryError, FRANKStorageError
from .base import BaseFRANKDatabase


class DynamoDBFRANKDatabase(BaseFRANKDatabase):
    """
    DynamoDB implementation of FRANK database using single table design in NoSQL.
    We have two tables to separate main data and audit concerns. Details can be found in the messages.
    The design is optimized for analyst-focused threat intelligence queries across sectors and regions.

    Single Table Design Pattern - Main data table (frank-data):
    PK (Partition Key)  | SK (Sort Key)   | GSI1PK          | GSI1SK                          | GSI2PK          | GSI2SK                               | Entity Type  | Description
    SUB#{sub_id}        | SUB             | ORG#{org_id}    | TS#{timestamp}                  | -               | -                                    | submission   | Complete submission with nested data
    ORG#{org_id}        | ORG             | OT#{type}       | TS#{timestamp}                  | -               | -                                    | organisation | Organisation metadata
    SIGHT#{sighting_id} | SUB#{sub_id}    | ORG#{org_id}    | TS#{timestamp}                  | -               | -                                    | sighting     | Sighting details (confidence, severity, observables)
    OBS#{obs_hash}      | SUB#{sub_id}    | TYPE#{obs_type} | TS#{timestamp}                  | SECTOR#{sector} | REGION#{region}#ORG#{org_id}#TS#{ts} | observable   | Observable occurrence (using GSI2)
    OBS#{obs_hash}      | STATS           | TYPE#{obs_type} | COUNT#{padded_count}#TS#{last}  | -               | -                                    | stats        | Observable statistics 

    Key Design Decisions:
    - GSI1: Type-based queries (observables by type, trending stats sorted by count)
    - GSI2: Sector/region analysis (SPARSE - only observables, optimized for cross-org threat intelligence)
    - Stats use GSI1SK with COUNT prefix for trending queries (top N observables)
    - Observables use GSI1SK with TS prefix for time-based queries (recent activity)

    GSI1SK Format Examples:
    - Observable: TS#2025-10-19T10:30:00Z (for time range queries)
    - Stats: COUNT#0000000042#TS#2025-10-19T10:30:00Z (padded for lexicographic sort)

    GSI2SK Format (Observables only - Sparse Index):
    - REGION#{region}#ORG#{org_id}#TS#{timestamp} (enables sector + region queries)

    Primary Access Patterns (Main Table):
    ✅ Get submission: PK = SUB#{sub_id}, SK = META
    ✅ Get observable stats: PK = OBS#{hash}, SK = STATS
    ✅ Get all submissions with observable: PK = OBS#{hash}, begins_with(SK, 'SUB#')
    ✅ Get observables by type: GSI1PK = TYPE#{type}
    ✅ Get trending observables: GSI1PK = TYPE#{type}, sorted by COUNT (descending)
    ✅ Get recent observables: GSI1PK = TYPE#{type}, GSI1SK > TS#{cutoff}
    ✅ Get observables by sector: GSI2PK = SECTOR#{sector}
    ✅ Get observables by sector+region: GSI2PK = SECTOR#{sector}, begins_with(GSI2SK, 'REGION#{region}')
    ⚠️  Get observables by org: FilterExpression on hit_target_org_id (less frequent, acceptable)

    Audit Log Table (frank-audit-logs) - Org-centric with user/action GSIs:
    PK (Partition Key)  | SK (Sort Key)                   | GSI1PK       | GSI1SK         | GSI2PK          | GSI2SK         | Entity Type
    LOG#{org_id}        | TS#{timestamp}#USER#{user_id}   | USER#{user}  | TS#{timestamp} | ACTION#{action} | TS#{timestamp} | audit_log

    Access Patterns (Audit Logs):
    ✅ Org's logs: PK = LOG#{org_id}, time filter on SK
    ✅ User's logs: GSI1PK = USER#{user_id}, time filter on GSI1SK
    ✅ Action logs: GSI2PK = ACTION#{action}, time filter on GSI2SK
    ✅ Last N days (specific org): PK = LOG#{org_id}, SK > TS#{7_days_ago}
    ✅ User + action: GSI1PK = USER#{user_id}, FilterExpression='action = :action'
    """
    
    def initialize(self) -> None:
        """
        Initialize DynamoDB database connection for LocalStack environment.

        Args:
            table_name: DynamoDB table name
            region: AWS region
            logger: Optional logger instance for logging
        """
        if self.config["environment"] == "aws":
            session = boto3.Session()
            # Test credentials by calling STS to see what identity we're using
            # sts_client = session.client('sts', region_name=region)
            # identity = sts_client.get_caller_identity()
            # AWS environment - explicitly use default credential chain
            # This ensures we use ECS Task Role when available
            # Force using default credentials (ECS Task Role, EC2 Instance Profile, etc.)
            self.client = session.client('dynamodb', region_name=self.config["region"])
            self.resource = session.resource('dynamodb', region_name=self.config["region"])
        elif self.config["profile"]:
            # LocalStack with AWS profile
            session = boto3.Session(profile_name=self.config["profile"])
            self.client = session.client("dynamodb", endpoint_url=self.config["endpoint"], region_name=self.config["region"])
            self.resource = session.resource("dynamodb", endpoint_url=self.config["endpoint"], region_name=self.config["region"])
        else:
            # LocalStack with explicit credentials
            self.client = boto3.client(
                'dynamodb',
                endpoint_url=self.config["endpoint"],
                region_name=self.config["region"],
                aws_access_key_id=self.config["aws_access_key_id"] or "test",
                aws_secret_access_key=self.config["aws_secret_access_key"] or "test"
            )
            self.resource = boto3.resource(
                'dynamodb',
                endpoint_url=self.config["endpoint"],
                region_name=self.config["region"],
                aws_access_key_id=self.config["aws_access_key_id"] or "test",
                aws_secret_access_key=self.config["aws_secret_access_key"] or "test"
            )

        self.table = self.resource.Table(self.config["table_name"])
        self.audit_table = self.resource.Table(self.config["audit_table_name"])


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

    def _ensure_table_exists(self, table_name):
        """
        Create the FRANK DynamoDB table with proper indexes and TTL configuration.
        
        Args:
            table_name -> str: Name for the DynamoDB table 
            
        Returns:
            table -> DynamoDB.Table: The DynamoDB Table resource
        """
                # Create table with single table design
        table_definition = {
            'TableName': table_name,
            'KeySchema': [
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1SK', 'AttributeType': 'S'}
            ],
            'GlobalSecondaryIndexes': [
                {
                    'IndexName': 'GSI1',
                    'KeySchema': [
                        {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'},
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
        td = deepcopy(table_definition)
        # Table existence check and creation
        try:
            self.client.describe_table(TableName=table_name)
            table = self.dynamodb.Table(table_name)
            table.load()  # Ensure table is loaded
            self.logger.info(f"✅ Table '{table_name}' exists")
        except self.client.exceptions.ResourceNotFoundException:
            self.logger.info(f"🔨 Creating table '{table_name}'...")
            try:
                table = self.dynamodb.create_table(**td)
                self.logger.info(f"✅ Table '{table_name}' created")
            except self.client.exceptions.ResourceInUseException:
                self.logger.info(f"⚠️ Table '{table_name}' already exists (race condition)")
                table = self.dynamodb.Table(table_name)

        table.meta.client.get_waiter('table_exists').wait(TableName=table_name)

        # Enable TTL on the TTL attribute for audit table
        if self.endpoint:
            try:
                self.dynamodb.meta.client.update_time_to_live(
                    TableName=table_name, TimeToLiveSpecification={"AttributeName": "TTL", "Enabled": True}
                )
            except Exception as e:
                self.logger.warning(f"Could not enable TTL for '{table_name}': {e}")
        return table

    def store_submission(self, user: Dict[str, Any], submission: Submission) -> None:
        """
        Store a complete submission in the DynamoDB database.

        Args:
            user (Dict[str, Any]): User information performing the operation
            submission (Submission): Submission object containing all required fields and nested data.

        Returns:
            None

        Raises:
            Logs error and returns False if batch write fails.
        """
        timestamp = submission.timestamp or datetime.now(timezone.utc)
        timestamp_str = timestamp.isoformat()
        
        # Create the main submission item
        submission_item = {
            'PK': f"SUB#{submission.submission_id}",
            'SK': 'SUB',
            'GSI1PK': f"SUBMITTER#{submission.submitter.organisation_id}",
            'GSI1SK': f"TS#{timestamp_str}",
            'entity_type': 'submission',
            'msg': submission.model_dump(by_alias=True, exclude_none=True),  # Complete submission 
            'request_id': user["request_id"],
            'TTL': int((timestamp + timedelta(days=2555)).timestamp())
        }    
        items_to_write = [submission_item]

        # Store submitter info for querying
        org_item = {
            'PK': f"ORG#{submission.submitter.organisation_id}",
            'SK': 'ORG',
            'GSI1PK': "OT#SUBMITTER",
            'GSI1SK': f"TS#{timestamp_str}",
            'entity_type': 'organisation',
            'msg': submission.submitter.model_dump(exclude_none=True, by_alias=True),
            'last_active': timestamp_str,
            'request_id': user["request_id"],
            'TTL': int((timestamp + timedelta(days=2555)).timestamp())
        }
        items_to_write.append(org_item)

        # Store sighting info as a separate item
        sighting = submission.sighting
        sighting_item = {
            'PK': f"SIGHT#{sighting.sighting_id}",
            'SK': f"SUB#{submission.submission_id}",
            'GSI1PK': f"ORG#{submission.submitter.organisation_id}",
            'GSI1SK': f"TS#{timestamp_str}",
            'entity_type': 'sighting',
            'msg': sighting.model_dump(exclude_none=True, by_alias=True),
            'request_id': user["request_id"],
            'TTL': int((timestamp + timedelta(days=2555)).timestamp())
        }
        items_to_write.append(sighting_item)

        # Store hit_target as another ORG# item if present
        hit_target = getattr(sighting, 'hit_target', None)
        if hit_target and getattr(hit_target, 'organisation_id', None) is not None:
            ht_org_item = {
                'PK': f"ORG#{hit_target.organisation_id}",
                'SK': 'ORG',
                'GSI1PK': "OT#TARGET",
                'GSI1SK': f"TS#{timestamp_str}",
                'entity_type': 'organisation',
                'msg': hit_target.model_dump(exclude_none=True, by_alias=True),
                'last_active': timestamp_str,
                'request_id': user["request_id"],
                'TTL': int((timestamp + timedelta(days=2555)).timestamp())
            }
            items_to_write.append(ht_org_item)

        # Create observable index items
        items_to_write.extend(self._extract_observables(user, submission))

        self._batch_write_items(items_to_write)


    def upsert_organisation(self, user: Dict[str, Any], org_data: Dict[str, Any]) -> None:
        """
        Insert or update organisation information in DynamoDB.

        Args:
            user (Dict[str, Any]): User information performing the operation
            org_data (Dict[str, Any]): Dictionary containing organisation fields. 
        Returns:
            None

        Raises:
            ClientError: If DynamoDB put_item fails.
        """
        timestamp = org_data.get('last_active', None) or datetime.now(timezone.utc)
        timestamp_str = timestamp.isoformat()
        org_item = {
            'PK': f"ORG#{org_data['organisation_id']}",
            'SK': 'ORG',
            'GSI1PK': f"OT#TARGET",
            'GSI1SK': f"TS#{timestamp_str}",
            'entity_type': 'organisation',
            'msg': {k: v for k, v in org_data.items() if v is not None},
            'last_active': timestamp_str,
            'request_id': user["request_id"],
            'TTL': int((datetime.now(timezone.utc) + timedelta(days=2555)).timestamp())
        }
        self.table.put_item(Item=org_item)
        

    def _extract_observables(self, user: Dict[str, Any], submission: Submission) -> List[Dict]:
        """
        Extract observables from a submission for DynamoDB indexing.

        This method processes the observables contained within a submission's sighting object and generates
        DynamoDB items for each observable, following the single table design pattern. Each observable is
        indexed for efficient cross-referencing and querying by type, value, and submission context.

        Indexing Logic:
            - Each observable is hashed and stored as a separate item with PK 'OBS#{obs_hash}' and SK 'SUB#{submission_id}'.
            - GSI1PK is set to 'TYPE#{obs_type}' for type-based queries (all observables).
            - GSI1SK is set to 'TS#{timestamp}' for time-range queries.
            - GSI2PK is set to 'SECTOR#{sector}' for sector-based analyst queries (SPARSE - only if hit_target exists).
            - GSI2SK is set to 'REGION#{region}#ORG#{org_id}#TS#{timestamp}' for hierarchical filtering.
            - Additional metadata (confidence, severity, sector, region) is flattened for efficient filtering.
            - TTL is set for long-term retention (default: ~7 years).

        Args:
            user (Dict[str, Any]): User information including request_id.
            submission (Submission): The submission object containing sighting and observables.

        Returns:
            List[Dict]: List of DynamoDB items representing indexed observables.

        Edge Cases & Notes:
            - Observables missing 'type' or 'value' are skipped.
            - GSI2 is only populated if hit_target exists (sparse index pattern).
            - If hit_target lacks sector/region, defaults to 'UNKNOWN'.
            - Handles empty or malformed observables gracefully.
            - Uses submission timestamp for time-based fields if not explicitly provided.
            - Designed for bulk ingestion and supports downstream analytics and deduplication.

        Example:
            >>> items = self._extract_observables(user, submission)
            >>> self._batch_write_items(items)
        """
        timestamp = submission.timestamp or datetime.now(timezone.utc)
        timestamp_str = timestamp.isoformat()

        observables_list = []
        sighting = submission.sighting.model_dump(exclude_none=True, by_alias=True)
        observables = sighting.get("observables", {})
        hit_target = getattr(submission.sighting, 'hit_target', None)

        # Extract hit_target metadata for GSI2 (sector/region analysis)
        hit_target_org_id = getattr(hit_target, 'organisation_id', None) if hit_target else None
        hit_target_sector = getattr(hit_target, 'sector', 'UNKNOWN') if hit_target else 'UNKNOWN'
        hit_target_region = getattr(hit_target, 'region', 'UNKNOWN') if hit_target else 'UNKNOWN'

        for obs_category, obs_list in observables.items():
            if isinstance(obs_list, list):
                for obs in obs_list:
                    if 'type' not in obs or 'value' not in obs:
                        continue

                    obs_hash = self.hash_observable(obs['type'], obs['value'])

                    # Create observable index item with analyst-focused GSI2
                    observable_index_item = {
                        "PK": f"OBS#{obs_hash}",
                        "SK": f"SUB#{submission.submission_id}",
                        # GSI1: Type-based queries with time sorting
                        "GSI1PK": f"TYPE#{obs['type']}",
                        "GSI1SK": f"TS#{timestamp_str}",
                        # Entity metadata
                        "entity_type": "observable",
                        "observable_value": obs["value"],
                        "submitter_id": f"SUBMITTER#{submission.submitter.organisation_id}",
                        "msg": sighting,
                        "request_id": user["request_id"],
                        "TTL": int((timestamp + timedelta(days=2555)).timestamp()),
                    }

                    # GSI2: Sector/region analysis (SPARSE - only if hit_target exists)
                    if hit_target and hit_target_org_id:
                        observable_index_item['GSI2PK'] = f"SECTOR#{hit_target_sector}"
                        observable_index_item['GSI2SK'] = f"REGION#{hit_target_region}#ORG#{hit_target_org_id}#TS#{timestamp_str}"

                        # Flatten hit_target metadata for filtering
                        observable_index_item['hit_target_org_id'] = hit_target_org_id
                        observable_index_item['hit_target_region'] = hit_target_region

                    observables_list.append(observable_index_item)

                    # Update statistics item for this observable
                    # 1. Read current count
                    response = self.table.get_item(Key={'PK': f'OBS#{obs_hash}', 'SK': 'STATS'})
                    stats = response.get('Item', {})

                    if stats:
                        current_count = stats.get('count', 0)

                        # 2. Update with new count-based GSI1SK
                        new_count = current_count + 1
                        self.table.update_item(
                            Key={'PK': f'OBS#{obs_hash}', 'SK': 'STATS'},
                            UpdateExpression='SET #count = :new_count, last_seen = :now, GSI1SK = :gsi1sk',
                            ExpressionAttributeNames={
                                '#count': 'count'
                            },
                            ExpressionAttributeValues={
                                ':new_count': new_count,
                                ':now': timestamp_str,
                                ':gsi1sk': f'COUNT#{int(new_count):010d}#TS#{timestamp_str}'
                            }
                        )
                    else:
                        stats_item = {
                            'PK': f'OBS#{obs_hash}',
                            'SK': 'STATS',
                            'GSI1PK': f'TYPE#{obs["type"]}',
                            'GSI1SK': f'COUNT#0000000001#TS#{timestamp_str}',
                            'entity_type': 'stats',
                            'observable_value': obs["value"],
                            'first_seen': timestamp_str,
                            'last_seen': timestamp_str,
                            'count': 1,
                            'TTL': int((datetime.now(timezone.utc) + timedelta(days=2555)).timestamp())
                        }
                        if stats_item:
                          observables_list.append(stats_item)
                        # self.table.put_item(Item=stats_item)
                    # stats_item = self._upsert_observable_statistics(
                    #     obs_hash=obs_hash,
                    #     obs_type=obs['type'],
                    #     obs_value=obs['value'],
                    #     hit_target_id=getattr(submission.hit_target, 'organisation_id', None),  # Safe access to hit_target
                    #     sector=getattr(submission.hit_target, 'sector', None),  # Safe access to hit_target
                    #     timestamp_str=timestamp_str
                    # )
                    # # if stats_item:
                    # #     observables_list.append(stats_item)
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
            hit_target_id (str, optional): organisation ID of the hit target, if available.
            sector (str, optional): Sector associated with the observable, if available.
            timestamp_str (str, optional): ISO timestamp string for the current sighting.

        Returns:
            dict: The updated or newly created statistics item for the observable.
        """
        try:
            response = self.table.get_item(
                Key={'PK': f'STAT#{obs_hash}', 'SK': f'STAT#{obs_type}'}
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
        Execute batch write operation with automatic retry for unprocessed items.

        This method writes items to DynamoDB using the high-level batch_writer context manager
        which automatically handles DynamoDB attribute formatting and retry logic for unprocessed items.

        DynamoDB Limitations:
            - Maximum 25 items per batch write operation.
            - Each item must be under 400KB in size.

        Practical Usage:
            - Use for bulk ingestion of submissions, observables, and logs.
            - Handles retry logic for unprocessed items, reducing risk of data loss during high-throughput operations.

        Args:
            items (List[Dict]): List of items to write to DynamoDB.

        Raises:
            FRANKStorageError: If the batch write operation fails and cannot be retried.
        """
        try:
            # Use batch_writer for proper item formatting and retry handling
            with self.table.batch_writer() as batch:
                for item in items:
                    batch.put_item(Item=item)
                    
            self.logger.debug(f"Successfully wrote {len(items)} items to DynamoDB")
                    
        except ClientError as e:
            self.logger.error(f"Batch write failed: {e}")
            raise FRANKStorageError(f"Batch write operation failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in batch write: {e}")
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
            submission_dict = response['Item'].get('msg', None)
            return submission_dict


        except ClientError as e:
            self.logger.error(f"Error retrieving submission {submission_id}: {e}")
            raise FRANKQueryError(f"Failed to retrieve submission: {e}")


    def list_sightings_from_observations(
        self,
        observable_value: Optional[str],
        observable_type: Optional[ObservableType],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        limit: int
    ) -> List[Observable]:
        """
        List observables by value and type within a date range.
        Args:
            observable_value (str): Observable value to search for (exact match).
            observable_type (ObservableType): Type of the observable (e.g., ipv4, domain).
            start_date (datetime): Start date for the search range.
            end_date (datetime): End date for the search range.
            limit (int): Maximum number of results to return.
        Returns:
            List[Observable]: List of observables matching the criteria.
        """
        from boto3.dynamodb.conditions import Key, Attr
        try:
            key_expr = None
            filter_expr = Attr('entity_type').eq('observable')

            # Build KeyConditionExpression for GSI1
            if observable_type:
                gsi1pk = f"TYPE#{observable_type.value if hasattr(observable_type, 'value') else str(observable_type)}"
                key_expr = Key('GSI1PK').eq(gsi1pk)
                if start_date or end_date:
                    # GSI1SK is TS#YYYY-MM-DDTHH:MM
                    if start_date and end_date:
                        key_expr = key_expr & Key('GSI1SK').between(
                            f"TS#{start_date.isoformat()}", f"TS#{end_date.isoformat()}"
                        )
                    elif start_date:
                        key_expr = key_expr & Key('GSI1SK').gte(f"TS#{start_date.isoformat()}")
                    elif end_date:
                        key_expr = key_expr & Key('GSI1SK').lte(f"TS#{end_date.isoformat()}")

            # Add observable_value filter if set
            if observable_value:
                filter_expr = filter_expr & Attr('observable_value').eq(observable_value)

            # Build ExpressionAttributeValues only for used values
            expr_attr_vals = {}
            filter_expr_str = str(filter_expr)
            if 'entity_type' in filter_expr_str:
                expr_attr_vals[':entity_type'] = 'observable'
            if observable_value and ':observable_value' in filter_expr_str:
                expr_attr_vals[':observable_value'] = observable_value

            # Query if we have a key_expr (GSI1), else scan
            if key_expr:
                query_args = dict(
                    IndexName='GSI1',
                    KeyConditionExpression=key_expr,
                    FilterExpression=filter_expr,
                    Limit=limit,
                    ScanIndexForward=False
                )
                if expr_attr_vals:
                    query_args['ExpressionAttributeValues'] = expr_attr_vals
                response = self.table.query(**query_args)
            else:
                # Fallback: scan with filters (less efficient)
                scan_args = dict(
                    FilterExpression=filter_expr,
                    Limit=limit
                )
                if expr_attr_vals:
                    scan_args['ExpressionAttributeValues'] = expr_attr_vals
                response = self.table.scan(**scan_args)
        except ClientError as e:
            self.logger.error(f"Error querying observables: {e}")
            raise FRANKQueryError(f"Failed to query observables: {e}")
        sightings = []
        for item in response.get('Items', []):
            sightings.append(Sighting(**item.get('msg', {})))
        return sightings

    # def query_observables(self, user_id: str,  access_level: AccessTier = AccessTier.CONTRIBUTOR,
    #                      observable_type: ObservableType = None, sectors: List[str] = None,
    #                      min_confidence: float = None, 
    #                      limit: int = 100, days_back: int = None) -> List[Observable]:
    #     """
    #     Query observables with access level filtering and additional filters.

    #     This method retrieves observables from DynamoDB, supporting the following filters:
    #     - observable_type: Only return observables of the specified type (uses GSI for efficient query).
    #     - min_confidence: Only include observables with confidence >= min_confidence.
    #     - sectors: Only include observables where the 'sector' field matches one of the provided sectors.
    #     - days_back: Only include observables seen in the last N days (based on 'timestamp' field).
    #     - limit: Maximum number of results to return.
    #     - access_level: Apply access level filtering to each observable (see FRANK access tier model).

    #     Args:
    #         user_id (str): User ID making the request (used for access logging).
    #         access_level (AccessTier, optional): Access level for filtering (default: CONTRIBUTOR).
    #         observable_type (ObservableType, optional): Filter by observable type (ipv4, domain, etc.).
    #         min_confidence (float, optional): Minimum confidence value to include.
    #         limit (int, optional): Maximum number of results to return (default: 100).
    #         sectors (List[str], optional): List of allowed sectors to include.
    #         days_back (int, optional): Only include observables seen in the last N days.

    #     Returns:
    #         List[Observable]: List of observables matching the filters, deduplicated by observable_hash.

    #     Access events are logged for auditing, including all filter parameters.
    #     """
    #     try:
    #         # Query by observable_type using GSI1 if provided, else scan all ObservableIndex
    #         if observable_type:
    #             response = self.table.query(
    #                 IndexName='GSI1',
    #                 KeyConditionExpression='GSI1PK = :type_key',
    #                 FilterExpression='EntityType = :entity_type',
    #                 ExpressionAttributeValues={
    #                     ':type_key': f"TYPE#{observable_type.value if hasattr(observable_type, 'value') else str(observable_type)}",
    #                     ':entity_type': 'ObservableIndex'
    #                 },
    #                 Limit=limit,
    #                 ScanIndexForward=False
    #             )
    #         else:
    #             response = self.table.scan(
    #                 FilterExpression='EntityType = :entity_type',
    #                 ExpressionAttributeValues={':entity_type': 'ObservableIndex'},
    #                 Limit=limit
    #             )

    #         # Aggregate and deduplicate by observable_hash
    #         observables_map = {}
    #         cutoff = None
    #         if days_back:
    #             cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    #         for item in response.get('Items', []):
    #             item = self._convert_decimals_to_float(item)

    #             # Filter by min_confidence
    #             if min_confidence is not None and item.get('confidence', 0) < min_confidence:
    #                 continue

    #             # Filter by sector
    #             if sectors:
    #                 sector = item.get('sector')
    #                 if sector not in sectors:
    #                     continue

    #             # Filter by days_back
    #             if cutoff:
    #                 ts = item.get('timestamp')
    #                 try:
    #                     item_time = datetime.fromisoformat(ts)
    #                 except Exception:
    #                     item_time = None
    #                 if not item_time or item_time < cutoff:
    #                     continue

    #             obs_hash = item.get('observable_hash')
    #             if not obs_hash:
    #                 continue

    #             # Initialize aggregation entry
    #             if obs_hash not in observables_map:
    #                 observables_map[obs_hash] = {
    #                     'observable_hash': obs_hash,
    #                     'observable_type': item.get('observable_type'),
    #                     'observable_value': item.get('observable_value'),
    #                     'total_sightings': 0,
    #                     'first_seen': item.get('timestamp'),
    #                     'last_seen': item.get('timestamp'),
    #                     'unique_organisations': set(),
    #                     'confidence_values': []
    #                 }

    #             obs_entry = observables_map[obs_hash]
    #             obs_entry['total_sightings'] += 1
    #             org_id_val = item.get('submitter_org_id')
    #             if org_id_val:
    #                 obs_entry['unique_organisations'].add(org_id_val)
    #             obs_entry['confidence_values'].append(item.get('confidence', 0))

    #             # Update time bounds
    #             ts = item.get('timestamp')
    #             if ts:
    #                 if obs_entry['first_seen'] is None or ts < obs_entry['first_seen']:
    #                     obs_entry['first_seen'] = ts
    #                 if obs_entry['last_seen'] is None or ts > obs_entry['last_seen']:
    #                     obs_entry['last_seen'] = ts

    #         # Convert to final format
    #         results = []
    #         for obs_hash, obs_data in observables_map.items():
    #             obs_data['unique_organisations'] = len(obs_data['unique_organisations'])
    #             obs_data['avg_confidence'] = (
    #                 sum(obs_data['confidence_values']) / len(obs_data['confidence_values'])
    #                 if obs_data['confidence_values'] else 0
    #             )
    #             del obs_data['confidence_values']

    #             # Apply access level filtering if needed
    #             filtered_obs = self._filter_observable_by_access_level(obs_data, access_level)
    #             results.append(filtered_obs)

    #         return results[:limit]
    #     except ClientError as e:
    #         self.logger.error(f"Error querying observables: {e}")
    #         raise FRANKQueryError(f"Failed to query observables: {e}")


    def search_observables_by_value(self, org_id: str, search_value: str,
                                   access_level: AccessTier = AccessTier.CONTRIBUTOR) -> List[Dict[str, Any]]:
        """
        Search for observables by partial value match using DynamoDB scan.

        Args:
            org_id (str): organisation performing the search
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
        Get platform statistics summary for an organisation, including totals of observables by type.

        This method calculates the following statistics for the given organisation and time window:
        - Total number of organisations in the platform.
        - Total number of submissions within the time window.
        - Total number of sightings within the time window.
        - Total number of observables indexed within the time window.
        - Breakdown of observables by type (e.g., ipv4, domain, url, etc.), using the ObservableType enum.
        
        For each observable type, the count is calculated efficiently using DynamoDB's GSI and Select='COUNT'.

        Args:
            org_id (str): The organisation ID to get statistics for.
            days (int, optional): Number of days to include in the summary (default: 30).

        Returns:
            Dict[str, Any]: Dictionary containing summary statistics
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            # Count organisations
            org_response = self.table.scan(
                FilterExpression='begins_with(PK, :org_prefix) AND EntityType = :org_entity_type',
                ExpressionAttributeValues={
                    ':org_prefix': 'ORG#',
                    ':org_entity_type': 'organisation'
                },
                Select='COUNT'
            )
            total_organisations = org_response.get('Count', 0)

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
                'organisation_id': org_id,
                'days': days,
                'total_organisations': total_organisations,
                'total_submissions': total_submissions,
                'total_sightings': total_sightings,
                'total_observables': total_observables, 
                'observable_totals': totals_by_type
            }
        except ClientError as e:
            self.logger.error(f"Error calculating statistics summary: {e}")
            return {
                'organisation_id': org_id,
                'days': days,
                'observable_totals': {},
                'total_observables': 0,
                'total_sightings': 0,
                'total_submissions': 0,
                'total_organisations': 0,
                'error': str(e)
            }

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on DynamoDB tables"""

        # List all tables
        response = self.client.list_tables()
        table_names = response.get('TableNames', [])
                

        # Get item counts from both tables
        main_response = self.resource.Table(self.config["table_name"]).scan(Select='COUNT')
        main_count = main_response.get('Count', 0)
        main_status = "accessible"

        audit_response = self.resource.Table(self.config["audit_table_name"]).scan(Select='COUNT')
        audit_count = audit_response.get('Count', 0)
        audit_status = "accessible"
            
        status = {
            "status": "ok" if main_status == "accessible" and audit_status == "accessible" else "degraded", 
            "database_type": "dynamodb",
            "tables": {
                "available_tables": table_names,
                "main": {
                    "name": self.config["table_name"],
                    "status": main_status,
                    "item_count": main_count
                },
                "audit": {
                    "name": self.config["audit_table_name"],
                    "status": audit_status,
                    "item_count": audit_count
                }
            },
            "database_cfg":{                
                "DYNAMODB_TABLE": self.config["table_name"],
                "AUDIT_TABLE": self.config["audit_table_name"],
                "AWS_REGION": self.config.get("aws_region")
            }
        }
        if self.config.get("environment") != 'aws':
            status["database_cfg"]["endpoint"] = self.config.get("endpoint")
            if self.config.get("profile"):
                status["database_cfg"]["profile"] = self.config.get("profile")
        return status

    def log_access(
        self,
        user: Dict[str, Any],
        org_id: str,
        action: str,
        msg_key: str,
        status: str = "success",
        details: Dict[str, Any] = None,
    ) -> None:
        """
        Internal method to log access in DynamoDB single table design.
        Args:
            user (Dict[str, Any]): User information including user_id and request_id.
            org_id (str): Organization ID (for PK - org-centric partitioning).
            action (str): Action performed (e.g., 'SUBMIT', 'QUERY', 'DELETE').
            msg_key (str): Message key for logging.
            status (str): Status of the action ('success' or 'failure').
            details (Dict[str, Any], optional): Additional audit details.

        Table Design:
            PK: ACTION#{action}#TS#{timestamp} - Partition by action
            SK: ID#{msg_key} - Unique identifier for the log entry
            GSI1: USER-based queries (user activity across orgs)
            GSI2: ORGANISATION-based queries (action monitoring across orgs)
        """

        timestamp = datetime.now(timezone.utc).isoformat()
        log_item = {
            "PK": f"ACTION#{action}#TS#{timestamp}",
            "SK": f"TS#{timestamp}#ID#{msg_key}",
            "GSI1PK": f"USER#{user['user_id']}",
            "GSI1SK": f"TS#{timestamp}",
            "GSI2PK": f"ORG#{org_id}",
            "GSI2SK": f"TS#{timestamp}",
            "request_id": user["request_id"],
            "status": status,
        }
        if details:
            log_item["details"] = details

        self.audit_table.put_item(Item=log_item)


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
#                 UpdateExpression='ADD total_sightings :inc, unique_organisations :inc SET last_seen = :timestamp',
#                 ExpressionAttributeValues={
#                     ':inc': increment_count,
#                     ':timestamp': datetime.now(timezone.utc).isoformat()
#                 }
#             )
#         except ClientError as e:
#             self.logger.warning(f"Failed to update observable statistics: {e}")

# Factory function for easy instantiation
def create_dynamodb_database(config: Dict[str, Any] = None,
                            logger: Optional[logging.Logger] = None) -> DynamoDBFRANKDatabase:
    """
    Factory function to create a DynamoDBFRANKDatabase instance.
    
    Args:
        config: Configuration dictionary with keys
        logger: provide external logger
    Returns:
        Configured DynamoDBFRANKDatabase instance
    """
    # Set up logging
    if not logger:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)

    return DynamoDBFRANKDatabase(config=config, logger=logger)