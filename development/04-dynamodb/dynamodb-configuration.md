# Amazon DynamoDB Configuration

## Overview
DynamoDB provides hot storage for aggregated data, tenant metadata, and idempotency tracking with single-digit millisecond latency and automatic scaling.

## Table Architecture

### 1. Aggregates Table
- **Name**: `frank-aggregates-{env}`
- **Purpose**: Store real-time aggregated statistics for fast querying
- **Access Pattern**: Query by IoC type, sector, time bucket

#### Schema Design
```json
{
  "TableName": "frank-aggregates-{env}",
  "KeySchema": [
    {
      "AttributeName": "pk",
      "KeyType": "HASH"
    },
    {
      "AttributeName": "sk",
      "KeyType": "RANGE"
    }
  ],
  "AttributeDefinitions": [
    {
      "AttributeName": "pk",
      "AttributeType": "S"
    },
    {
      "AttributeName": "sk", 
      "AttributeType": "S"
    },
    {
      "AttributeName": "gsi1_pk",
      "AttributeType": "S"
    },
    {
      "AttributeName": "gsi1_sk",
      "AttributeType": "S"
    }
  ]
}
```

#### Key Structure
- **PK**: `ioc#{ioc_type}` (e.g., `ioc#ip`, `ioc#domain`, `ioc#hash`)
- **SK**: `{time_bucket}#{sector}#{aggregation_level}` (e.g., `2025-08-12#finance#daily`)
- **GSI1_PK**: `sector#{sector}` (e.g., `sector#finance`)
- **GSI1_SK**: `{time_bucket}#{ioc_type}` (e.g., `2025-08-12#ip`)

#### Item Structure
```json
{
  "pk": "ioc#ip",
  "sk": "2025-08-12#finance#daily",
  "gsi1_pk": "sector#finance",
  "gsi1_sk": "2025-08-12#ip",
  "count": 1547,
  "unique_sources": 23,
  "severity_distribution": {
    "high": 234,
    "medium": 891,
    "low": 422
  },
  "top_indicators": ["192.168.1.1", "10.0.0.1"],
  "last_updated": "2025-08-12T14:30:00Z",
  "ttl": 1756492800
}
```

### 2. Tenants Table
- **Name**: `frank-tenants-{env}`
- **Purpose**: Store tenant metadata and configuration
- **Access Pattern**: Lookup by tenant_id

#### Schema Design
```json
{
  "TableName": "frank-tenants-{env}",
  "KeySchema": [
    {
      "AttributeName": "tenant_id",
      "KeyType": "HASH"
    }
  ],
  "AttributeDefinitions": [
    {
      "AttributeName": "tenant_id",
      "AttributeType": "S"
    }
  ]
}
```

#### Item Structure
```json
{
  "tenant_id": "org-123",
  "organization_name": "Example Security Org",
  "sector": "finance",
  "contact_email": "admin@example.com",
  "status": "active",
  "created_date": "2025-01-15T10:00:00Z",
  "retention_policy": {
    "raw_data_days": 2555,
    "aggregates_days": 365
  },
  "data_sharing": {
    "allow_aggregation": true,
    "allow_sector_sharing": true,
    "anonymization_level": "high"
  },
  "hmac_seed_encrypted": "encrypted_base64_seed",
  "api_quotas": {
    "daily_sightings": 10000,
    "daily_queries": 1000
  },
  "last_activity": "2025-08-12T14:25:00Z"
}
```

### 3. Idempotency Table
- **Name**: `frank-idempotency-{env}`
- **Purpose**: Prevent duplicate processing of requests
- **Access Pattern**: Check/set by request signature

#### Schema Design
```json
{
  "TableName": "frank-idempotency-{env}",
  "KeySchema": [
    {
      "AttributeName": "request_key",
      "KeyType": "HASH"
    }
  ],
  "AttributeDefinitions": [
    {
      "AttributeName": "request_key",
      "AttributeType": "S"
    }
  ]
}
```

#### Item Structure
```json
{
  "request_key": "sha256_hash_of_request",
  "tenant_id": "org-123",
  "processed_at": "2025-08-12T14:30:00Z",
  "response_data": {
    "status": "success",
    "message": "Sighting processed",
    "sighting_id": "sight-456"
  },
  "ttl": 1723550400
}
```

## Global Secondary Indexes (GSIs)

### Aggregates Table GSIs

#### GSI1 - Sector-based queries
- **Purpose**: Query aggregates by sector and time
- **PK**: `gsi1_pk` (sector#{sector})
- **SK**: `gsi1_sk` ({time_bucket}#{ioc_type})

#### GSI2 - Time-based queries
- **Purpose**: Query aggregates across all sectors by time
- **PK**: `time_bucket`
- **SK**: `ioc_type#{sector}`

### Tenants Table GSIs

#### GSI1 - Sector lookup
- **Purpose**: Find all tenants in a specific sector
- **PK**: `sector`
- **SK**: `tenant_id`

## Capacity and Scaling

### Billing Mode
- **Development**: On-Demand
- **Production**: Provisioned with Auto Scaling

### Auto Scaling Configuration
```json
{
  "TargetTrackingScalingPolicies": [
    {
      "TargetValue": 70.0,
      "ScaleInCooldown": 60,
      "ScaleOutCooldown": 60,
      "MetricType": "DynamoDBReadCapacityUtilization"
    },
    {
      "TargetValue": 70.0,
      "ScaleInCooldown": 60,
      "ScaleOutCooldown": 60,
      "MetricType": "DynamoDBWriteCapacityUtilization"
    }
  ]
}
```

### Capacity Limits
- **Min Read Capacity**: 5 RCU
- **Max Read Capacity**: 1000 RCU
- **Min Write Capacity**: 5 WCU
- **Max Write Capacity**: 500 WCU

## TTL Configuration

### Aggregates TTL
- **Attribute**: `ttl`
- **Purpose**: Automatic cleanup of old aggregated data
- **Default**: 1 year for daily aggregates, 3 months for hourly

### Idempotency TTL
- **Attribute**: `ttl`
- **Purpose**: Cleanup processed requests
- **Default**: 24 hours

## Encryption and Security

### Encryption at Rest
- **Type**: Customer-managed KMS key
- **Key**: `frank-ddb-key-{env}`
- **Key Rotation**: Enabled

### Encryption in Transit
- **Protocol**: TLS 1.2
- **Verification**: Certificate pinning in applications

### Access Control
- **IAM Policies**: Function-specific access
- **Condition Keys**: Restrict by leading keys
- **VPC Endpoints**: Private network access

## Backup and Recovery

### Point-in-Time Recovery
- **Status**: Enabled
- **Retention**: 35 days
- **Granularity**: Second-level recovery

### On-Demand Backups
- **Schedule**: Daily via AWS Backup
- **Retention**: 30 days local, 90 days cross-region
- **Encryption**: Same KMS key as table

### Cross-Region Replication
- **Purpose**: Disaster recovery
- **Target Region**: eu-central-1
- **Replication**: Global Tables (if needed)

## Performance Optimization

### Hot Partition Prevention
- **Key Design**: Use high-cardinality partition keys
- **Distribution**: Even spread across partitions
- **Monitoring**: Watch for throttling events

### Query Patterns
```python
# Query aggregates for a specific IoC type and date range
response = dynamodb.query(
    TableName='frank-aggregates-prod',
    KeyConditionExpression='pk = :pk AND begins_with(sk, :sk_prefix)',
    ExpressionAttributeValues={
        ':pk': 'ioc#ip',
        ':sk_prefix': '2025-08-12'
    }
)

# Query by sector using GSI
response = dynamodb.query(
    TableName='frank-aggregates-prod',
    IndexName='GSI1',
    KeyConditionExpression='gsi1_pk = :gsi1_pk',
    ExpressionAttributeValues={
        ':gsi1_pk': 'sector#finance'
    }
)
```

### Batch Operations
- **BatchGetItem**: Retrieve multiple items efficiently
- **BatchWriteItem**: Write multiple items in single request
- **TransactWriteItems**: Atomic multi-item operations

## Monitoring and Alarms

### CloudWatch Metrics
- **Read/Write Capacity**: Monitor utilization
- **Throttled Requests**: Alert on throttling
- **Item Count**: Track table growth
- **Hot Partitions**: Identify uneven access

### Alarms Configuration
```yaml
Alarms:
  - AlarmName: DynamoDB-HighReadThrottles
    MetricName: ReadThrottleEvents
    Threshold: 5
    ComparisonOperator: GreaterThanThreshold
    EvaluationPeriods: 2
    
  - AlarmName: DynamoDB-HighWriteThrottles
    MetricName: WriteThrottleEvents
    Threshold: 5
    ComparisonOperator: GreaterThanThreshold
    EvaluationPeriods: 2
```

### Custom Metrics
- **Aggregate Update Latency**: Time to update aggregates
- **Query Response Time**: End-to-end query performance
- **Cache Hit Rate**: If using DAX

## Data Access Patterns

### Write Patterns
1. **Sighting Ingestion** → Update aggregates
2. **Tenant Registration** → Create tenant record
3. **Idempotency Check** → Create/update request record

### Read Patterns
1. **Statistics Query** → Read aggregates by IoC/sector/time
2. **Tenant Lookup** → Get tenant configuration
3. **Duplicate Check** → Check idempotency record

## Environment Variables
```bash
# Table Names
FRANK_AGGREGATES_TABLE=frank-aggregates-{env}
FRANK_TENANTS_TABLE=frank-tenants-{env}
FRANK_IDEMPOTENCY_TABLE=frank-idempotency-{env}

# KMS Key
FRANK_DDB_KEY_ARN=arn:aws:kms:eu-west-1:{account}:key/{key-id}

# Region
AWS_DEFAULT_REGION=eu-west-1
```

## Implementation Checklist
- [ ] Create aggregates table with GSIs
- [ ] Create tenants table
- [ ] Create idempotency table
- [ ] Configure TTL on appropriate tables
- [ ] Set up auto-scaling policies
- [ ] Configure encryption with KMS
- [ ] Enable Point-in-Time Recovery
- [ ] Set up backup schedules
- [ ] Create CloudWatch alarms
- [ ] Test access patterns and performance
- [ ] Implement batch operations where applicable
- [ ] Set up monitoring dashboards
