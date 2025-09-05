# Amazon S3 Configuration

## Overview
S3 provides the data lake foundation for FRANK, storing raw sightings, and generated reports with strong security and lifecycle management.

## Bucket Architecture

### 1. Raw Data Bucket
- **Name**: `frank-raw-{account}-{env}`
- **Purpose**: Store raw sighting data from participants
- **Partitioning**: `tenant_id={tenant}/date=YYYY/MM/DD/`
- **Format**: JSON Lines (JSONL)


### 2. Exports Bucket
- **Name**: `frank-exports-{account}-{env}`
- **Purpose**: Store generated reports and query results
- **Structure**:
  ```
  reports/
  ├── tenant={tenant}/
  │   └── date=YYYY-MM-DD/report.pdf
  athena-results/
  ├── query-id/
  └── workgroup/
  ```

## Security Configuration

### Bucket Policies
All buckets implement:
- **Block Public Access**: Enabled for all settings
- **Bucket Policy**: Restrict access to specific IAM roles and VPC endpoints
- **Access Control**: Bucket owner enforced

### Encryption
- **Default Encryption**: SSE-KMS with customer-managed keys
- **Bucket Key**: Enabled to reduce KMS costs
- **In-transit**: HTTPS only via bucket policy

### Versioning and Protection
- **Versioning**: Enabled on all buckets
- **MFA Delete**: Enabled for production environments
- **Object Lock**: Consider for compliance requirements

## Lifecycle Management

### Raw Data Lifecycle
```yaml
Rules:
  - Id: RawDataLifecycle
    Status: Enabled
    Filter:
      Prefix: "submitter_id="
    Transitions:
      - Days: 30
        StorageClass: STANDARD_IA
      - Days: 90
        StorageClass: GLACIER
      - Days: 2555  # 7 years
        StorageClass: DEEP_ARCHIVE
    Expiration:
      Days: 3653  # 10 years
```

### Exports Lifecycle
```yaml
Rules:
  - Id: ExportsLifecycle
    Status: Enabled
    Transitions:
      - Days: 7
        StorageClass: STANDARD_IA
      - Days: 30
        StorageClass: GLACIER
    Expiration:
      Days: 90
```

## Event Notifications

### S3 Event Configuration
- **Artifact Updates**: S3 → EventBridge → Step Functions
- **Raw Data Ingestion**: S3 → Lambda (write_persistence)
- **Failed Uploads**: S3 → SNS → CloudWatch Alarms


## Access Patterns

### Lambda Function Access
```python
# Example: Writing raw sighting data
s3_client.put_object(
    Bucket=os.environ['FRANK_RAW_BUCKET'],
    Key=f"tenant_id={tenant_id}/date={date}/sighting_{uuid}.json",
    Body=json.dumps(sighting_data),
    ServerSideEncryption='aws:kms',
    SSEKMSKeyId=os.environ['FRANK_S3_KEY_ARN'],
    Metadata={
        'tenant_id': tenant_id,
        'ingestion_time': timestamp,
        'schema_version': '1.0'
    }
)
```

### Cross-Region Replication
For disaster recovery:
```yaml
ReplicationConfiguration:
  Role: arn:aws:iam::account:role/frank-s3-replication-role
  Rules:
    - Id: ReplicateToSecondaryRegion
      Status: Enabled
      Priority: 1
      Filter:
        Prefix: "tenant_id="
      Destination:
        Bucket: arn:aws:s3:::frank-raw-backup-region
        StorageClass: STANDARD_IA
        EncryptionConfiguration:
          ReplicaKmsKeyID: arn:aws:kms:backup-region:account:key/backup-key-id
```

## Monitoring and Metrics

### CloudWatch Metrics
- **Bucket Size**: Monitor storage usage per bucket
- **Request Metrics**: GET, PUT, DELETE operations
- **Error Rates**: 4xx and 5xx errors
- **Data Retrieval**: Glacier retrieval metrics

### Alarms
```yaml
Alarms:
  - Name: S3HighErrorRate
    MetricName: 4xxErrors
    Threshold: 10
    ComparisonOperator: GreaterThanThreshold
    EvaluationPeriods: 2
    
  - Name: S3UnusualDataVolume
    MetricName: BucketSizeBytes
    Threshold: 1TB
    ComparisonOperator: GreaterThanThreshold
```

## Performance Optimization

### Request Patterns
- **Prefix Distribution**: Use random prefixes to avoid hot partitions
- **Multipart Uploads**: For files > 100MB
- **Transfer Acceleration**: Enable for global users

### Cost Optimization
- **Intelligent Tiering**: For unpredictable access patterns
- **Lifecycle Policies**: Automatic transition to cheaper storage classes
- **Incomplete Multipart Upload Cleanup**: Remove abandoned uploads after 7 days

## Backup and Disaster Recovery

### Cross-Region Backup
- **Primary Region**: eu-west-1
- **Backup Region**: eu-central-1
- **Replication**: Automated for critical data
- **Recovery Time**: 4 hours for full restoration

### Data Integrity
- **Checksums**: SHA-256 for all objects
- **Versioning**: Protect against accidental deletion
- **MFA Delete**: Additional protection for critical buckets

## Compliance and Governance

### Data Classification
- **Public**: Aggregated statistics (exports bucket)
- **Internal**: SIGMA rules and IoC feeds (artifacts bucket)
- **Confidential**: Raw sighting data (raw bucket)

### Retention Policies
- **Legal Hold**: Capability for litigation holds
- **Data Sovereignty**: Ensure data remains in required jurisdictions
- **Right to Deletion**: Support for GDPR erasure requests

## Environment Variables
```bash
# S3 Bucket Names
FRANK_RAW_BUCKET=frank-raw-{account}-{env}
FRANK_EXPORTS_BUCKET=frank-exports-{account}-{env}

# KMS Keys
FRANK_S3_KEY_ARN=arn:aws:kms:eu-west-1:{account}:key/{key-id}

# Access
S3_ENDPOINT_URL=https://s3.eu-west-1.amazonaws.com
AWS_DEFAULT_REGION=eu-west-1
```

## Implementation Checklist
- [ ] Create raw data bucket with partitioning
- [ ] Create artifacts bucket with structure
- [ ] Create exports bucket
- [ ] Configure bucket policies and encryption
- [ ] Set up lifecycle rules
- [ ] Configure event notifications
- [ ] Set up cross-region replication
- [ ] Create CloudWatch alarms
- [ ] Test access patterns from Lambda
- [ ] Validate encryption and decryption
- [ ] Set up monitoring dashboards
