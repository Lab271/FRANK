# DynamoDB Single Table Design for FRANK Platform

## Overview

This document describes the implementation of DynamoDB single table design pattern for the FRANK (Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling) threat intelligence platform. The single table design consolidates multiple entity types into one DynamoDB table while maintaining efficient query patterns and optimal performance.

## Single Table Design Pattern

The FRANK platform uses a single DynamoDB table to store three primary entity types, leveraging partition keys (PK), sort keys (SK), and Global Secondary Index (GSI) for different access patterns.

### Entity Design Pattern

| PK (Partition Key) | SK (Sort Key) | GSI1PK | GSI1SK | Entity Type | Description |
|-------------------|---------------|---------|---------|-------------|-------------|
| `ORG#{org_id}` | `ORG` | `access_level#{access_level}` | `#{timestamp}` | Organization | Organization metadata and access control |
| `SUB#{submission_id}` | `SUB` | `ORG#{org_id}` | `#{timestamp}` | Submission | Complete threat intelligence submission |
| `LOG#{org_id}` | `LOG#{timestamp}#{uuid}` | `ACTION#{action}` | `#{timestamp}` | AccessLog | Audit trail for compliance and monitoring |

### Supported Query Patterns

1. **Get Organization by ID**: `PK = ORG#{org_id}, SK = ORG`
2. **Get Submission by ID**: `PK = SUB#{submission_id}, SK = SUB`
3. **List Submissions by Organization**: `GSI1: GSI1PK = ORG#{org_id}`
4. **List Organizations by access_level**: `GSI1: GSI1PK = access_level#{access_level}`
5. **Get Access Logs for Organization**: `PK = LOG#{org_id}, SK begins_with LOG#`
6. **Query Access Logs by Action**: `GSI1: GSI1PK = ACTION#{action}`

## Rationale for Three Entity Design

### Organizational Simplicity

The three-entity design represents the minimum viable data model for a threat intelligence platform:

- **Organizations**: Essential for access control, tier-based permissions, and partnership management
- **Submissions**: Core business objects containing threat intelligence data
- **Access Logs**: Required for audit compliance and security monitoring

### Reduced Complexity

Traditional relational approaches would decompose submissions into multiple tables (sightings, observables, campaigns, SIGMA rules). This single table design stores the complete submission as a nested document, eliminating:

- Complex join operations
- Transaction coordination across multiple tables
- Referential integrity maintenance
- Query performance degradation from table joins

### Query Efficiency

The design optimizes for the most common access patterns:

- Organizations queried by ID for authentication/authorization
- Submissions queried by ID for retrieval or by organization for filtering
- Access logs queried by organization for audit or by action for monitoring

### Scalability Benefits

Single table design provides:

- **Consistent Performance**: O(1) lookups regardless of data volume
- **Horizontal Scaling**: Automatic partitioning based on access patterns
- **Cost Optimization**: Reduced RCU/WCU consumption through efficient queries
- **Operational Simplicity**: Single table to monitor, backup, and maintain

## Data Structure Details

### Organization Entity

```json
{
  "PK": "ORG#identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
  "SK": "ORG",
  "GSI1PK": "TIER#partner",
  "GSI1SK": "2025-01-15T10:30:00Z",
  "EntityType": "Organization",
  "organization_id": "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
  "access_level": "partner",
  "sector": "financial_services",
  "region": "nl_north_holland",
  "last_active": "2025-01-15T10:30:00Z",
  "TTL": 1767193800
}
```

### Submission Entity

```json
{
  "PK": "SUB#submission-abc123",
  "SK": "SUB",
  "GSI1PK": "ORG#identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
  "GSI1SK": "2025-01-15T10:30:00Z",
  "EntityType": "Submission",
  "submission_id": "submission-abc123",
  "submitter_org_id": "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
  "confidence": 87,
  "severity": "high",
  "tlp_level": "AMBER",
  "submission_data": {
    "submitter": { "organization_id": "...", "access_level": "partner" },
    "sighting": { "observables": {...}, "impact": {...} },
    "threat_context": {...}
  },
  "TTL": 1767193800
}
```

### Access Log Entity

```json
{
  "PK": "LOG#identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
  "SK": "LOG#2025-01-15T10:30:00Z#uuid-123",
  "GSI1PK": "ACTION#SUBMIT",
  "GSI1SK": "2025-01-15T10:30:00Z",
  "EntityType": "AccessLog",
  "organization_id": "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
  "action": "SUBMIT",
  "resource_type": "submission",
  "resource_id": "submission-abc123",
  "timestamp": "2025-01-15T10:30:00Z",
  "success": true,
  "TTL": 1759593800
}
```

## Upsert Operations

DynamoDB provides several mechanisms for upsert (update or insert) operations in single table design:

### Method 1: PutItem with Conditional Checks

```python
def upsert_organization(self, org_data: dict) -> bool:
    """Upsert organization using PutItem."""
    try:
        self.table.put_item(
            Item={
                'PK': f"ORG#{org_data['organization_id']}",
                'SK': 'ORG',
                'GSI1PK': f"TIER#{org_data['access_level']}",
                'GSI1SK': datetime.now(timezone.utc).isoformat(),
                **org_data,
                'EntityType': 'Organization',
                'last_active': datetime.now(timezone.utc).isoformat()
            },
            # Optional: Add condition to prevent overwrites
            # ConditionExpression='attribute_not_exists(PK)'
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            # Handle case where item already exists
            return self.update_organization(org_data)
        raise
```

### Method 2: UpdateItem with SET Operations

```python
def upsert_organization_with_update(self, org_data: dict) -> bool:
    """Upsert organization using UpdateItem."""
    try:
        self.table.update_item(
            Key={
                'PK': f"ORG#{org_data['organization_id']}",
                'SK': 'ORG'
            },
            UpdateExpression='SET access_level = :access_level, sector = :sector, last_active = :timestamp, GSI1PK = :gsi1pk, GSI1SK = :gsi1sk',
            ExpressionAttributeValues={
                ':access_level': org_data['access_level'],
                ':sector': org_data.get('sector'),
                ':timestamp': datetime.now(timezone.utc).isoformat(),
                ':gsi1pk': f"TIER#{org_data['access_level']}",
                ':gsi1sk': datetime.now(timezone.utc).isoformat()
            }
        )
        return True
    except ClientError as e:
        self.logger.error(f"Upsert failed: {e}")
        return False
```

### Method 3: Atomic Counters for Statistics

```python
def increment_submission_count(self, org_id: str) -> None:
    """Atomically increment submission count for organization."""
    self.table.update_item(
        Key={
            'PK': f"ORG#{org_id}",
            'SK': 'ORG'
        },
        UpdateExpression='ADD submission_count :inc SET last_active = :timestamp',
        ExpressionAttributeValues={
            ':inc': 1,
            ':timestamp': datetime.now(timezone.utc).isoformat()
        }
    )
```

### Batch Upsert for Multiple Items

```python
def batch_upsert_submissions(self, submissions: List[dict]) -> bool:
    """Batch upsert multiple submissions."""
    chunk_size = 25  # DynamoDB batch write limit
    
    for i in range(0, len(submissions), chunk_size):
        chunk = submissions[i:i + chunk_size]
        
        request_items = {
            self.table_name: [
                {'PutRequest': {'Item': submission}}
                for submission in chunk
            ]
        }
        
        try:
            response = self.client.batch_write_item(RequestItems=request_items)
            
            # Handle unprocessed items
            unprocessed = response.get('UnprocessedItems', {})
            while unprocessed:
                response = self.client.batch_write_item(RequestItems=unprocessed)
                unprocessed = response.get('UnprocessedItems', {})
                
        except ClientError as e:
            self.logger.error(f"Batch upsert failed: {e}")
            return False
    
    return True
```

## Best Practices

### Data Modeling

1. **Design for Access Patterns**: Structure keys based on how data will be queried, not how it's logically related
2. **Use Composite Keys**: Combine multiple attributes in sort keys for hierarchical data access
3. **Leverage GSI Wisely**: Create GSI for alternative query patterns but avoid over-indexing
4. **TTL for Data Lifecycle**: Use Time-To-Live for automatic cleanup of expired data

### Performance Optimization

1. **Hot Partitions**: Distribute writes across multiple partitions using random prefixes if needed
2. **Batch Operations**: Use batch read/write operations to reduce API calls
3. **Projection**: Use GSI projection to minimize data retrieval
4. **Consistent Reads**: Use strongly consistent reads only when necessary

### Cost Management

1. **On-Demand vs Provisioned**: Choose billing mode based on traffic patterns
2. **Item Size**: Keep items under 400KB for optimal performance
3. **Query vs Scan**: Always prefer Query operations over Scan for better performance and cost

## Limitations and Considerations

### Query Limitations

- **No Complex Joins**: Cannot perform SQL-style joins across entity types
- **Limited Filtering**: FilterExpression applied after query, affecting performance
- **Sort Key Constraints**: Sort key comparisons limited to specific operators

### Data Consistency

- **Eventually Consistent GSI**: Global Secondary Indexes are eventually consistent
- **Item Size Limits**: 400KB maximum item size may constrain large submissions
- **Transaction Limits**: DynamoDB transactions limited to 25 items

### Operational Considerations

- **Schema Evolution**: Changes to access patterns may require GSI updates
- **Backup Strategy**: Point-in-time recovery and on-demand backups available
- **Monitoring**: CloudWatch metrics essential for performance monitoring

## References

Amazon Web Services. (2023). *Best practices for designing and using partition keys effectively*. Amazon DynamoDB Developer Guide. https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html

Amazon Web Services. (2023). *Working with tables and data in DynamoDB*. Amazon DynamoDB Developer Guide. https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithTables.html

Houlihan, R. (2018, November). *Advanced design patterns for Amazon DynamoDB* [Conference presentation]. AWS re:Invent 2018, Las Vegas, NV, United States. https://www.youtube.com/watch?v=HaEPXoXVf2k

DeBrie A. (2022, Aug 16). *Single-table vs. multi-table design in Amazon DynamoDB*. AWS Database Blog. https://aws.amazon.com/blogs/database/single-table-vs-multi-table-design-in-amazon-dynamodb/

Bitton, J. (2025). *The Single Table Design Vs Multi-Table Design In DynamoDB. Medium*. https://medium.com/aws-in-plain-english/the-single-table-design-vs-multi-table-design-in-dynamodb-7e6a596a30b0

Note: The single table design pattern is relatively recent (post-2017) and much of the authoritative content comes from AWS engineers and practitioners rather than traditional academic sources. 