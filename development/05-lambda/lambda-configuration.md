# AWS Lambda Configuration

## Overview
Lambda functions provide serverless compute for FRANK's core processing logic, handling sighting ingestion, data persistence, statistics queries, and SIGMA rule updates.

## Function Architecture

### 1. ingest_sightings Function
- **Name**: `frank-ingest-sightings-{env}`
- **Runtime**: Python 3.11
- **Memory**: 512 MB
- **Timeout**: 30 seconds
- **Purpose**: Validate, normalize, and deduplicate incoming sightings

#### Handler: `lambda_function.lambda_handler`
```python
import json
import boto3
import hashlib
import hmac
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.idempotency import idempotent

logger = Logger()
tracer = Tracer()
metrics = Metrics()

@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics
def lambda_handler(event, context):
    """Process incoming security sightings"""
    
    # Extract sighting data from API Gateway event
    api_event = APIGatewayProxyEvent(event)
    sighting_data = json.loads(api_event.body)
    
    # Get tenant info from JWT claims
    tenant_id = api_event.request_context.authorizer.claims.get('custom:tenant_id')
    
    # Validate schema
    validated_sighting = validate_sighting_schema(sighting_data)
    
    # Pseudonymize identifiers
    pseudonymized_sighting = pseudonymize_sighting(validated_sighting, tenant_id)
    
    # Check for duplicates (idempotency)
    if is_duplicate(pseudonymized_sighting):
        return create_response(200, {'message': 'Duplicate sighting ignored'})
    
    # Send to processing queue
    send_to_processing(pseudonymized_sighting, tenant_id)
    
    metrics.add_metric(name="SightingsIngested", unit="Count", value=1)
    
    return create_response(201, {'message': 'Sighting accepted', 'id': pseudonymized_sighting['id']})
```

#### Environment Variables
```bash
FRANK_TENANTS_TABLE=frank-tenants-{env}
FRANK_IDEMPOTENCY_TABLE=frank-idempotency-{env}
FRANK_APP_KEY_ARN=arn:aws:kms:eu-west-1:{account}:key/{key-id}
PROCESSING_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/{account}/frank-processing-{env}
```

### 2. write_persistence Function
- **Name**: `frank-write-persistence-{env}`
- **Runtime**: Python 3.11
- **Memory**: 1024 MB
- **Timeout**: 5 minutes
- **Purpose**: Write data to S3, update DynamoDB aggregates, index in OpenSearch

#### Trigger: S3 Event (from ingest_sightings) or SQS Queue
```python
import json
import boto3
from datetime import datetime
from aws_lambda_powertools import Logger, Tracer, Metrics

logger = Logger()
tracer = Tracer()
metrics = Metrics()

@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics
def lambda_handler(event, context):
    """Persist sighting data across storage systems"""
    
    for record in event.get('Records', []):
        if 'sqs' in record:
            # Process from SQS queue
            message = json.loads(record['body'])
            sighting_data = message['sighting']
            tenant_id = message['tenant_id']
        else:
            # Process from S3 event
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            sighting_data = get_s3_object(bucket, key)
            tenant_id = extract_tenant_from_key(key)
        
        # Write to S3 raw storage
        s3_key = write_to_s3_raw(sighting_data, tenant_id)
        
        # Update DynamoDB aggregates
        update_aggregates(sighting_data, tenant_id)
        
        # Index in OpenSearch
        index_in_opensearch(sighting_data, tenant_id)
        
        metrics.add_metric(name="SightingsPersisted", unit="Count", value=1)
    
    return {'statusCode': 200, 'processed': len(event.get('Records', []))}
```

### 3. query_stats Function
- **Name**: `frank-query-stats-{env}`
- **Runtime**: Python 3.11
- **Memory**: 256 MB
- **Timeout**: 30 seconds
- **Purpose**: Query aggregated statistics for API responses

```python
import json
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent

logger = Logger()
tracer = Tracer()
metrics = Metrics()

@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics
def lambda_handler(event, context):
    """Query aggregated statistics"""
    
    api_event = APIGatewayProxyEvent(event)
    
    # Extract query parameters
    ioc_type = api_event.query_string_parameters.get('ioc_type')
    sector = api_event.query_string_parameters.get('sector')
    time_range = api_event.query_string_parameters.get('time_range', '24h')
    
    # Validate access permissions
    tenant_id = api_event.request_context.authorizer.claims.get('custom:tenant_id')
    if not can_access_stats(tenant_id, sector):
        return create_response(403, {'error': 'Access denied'})
    
    # Query aggregated data
    stats = query_aggregated_stats(ioc_type, sector, time_range)
    
    # Anonymize results
    anonymized_stats = anonymize_statistics(stats)
    
    metrics.add_metric(name="StatsQueries", unit="Count", value=1)
    
    return create_response(200, anonymized_stats)
```

### 4. sigma_update_job Function
- **Name**: `frank-sigma-update-{env}`
- **Runtime**: Python 3.11
- **Memory**: 512 MB
- **Timeout**: 2 minutes
- **Purpose**: Process SIGMA rule updates and trigger validation

```python
import json
import boto3
import yaml
from aws_lambda_powertools import Logger, Tracer, Metrics

logger = Logger()
tracer = Tracer()
metrics = Metrics()

@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics
def lambda_handler(event, context):
    """Process SIGMA rule updates"""
    
    for record in event.get('Records', []):
        # Extract S3 event details
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        # Download SIGMA rule
        sigma_content = get_s3_object(bucket, key)
        
        # Parse and validate SIGMA rule
        try:
            sigma_rule = yaml.safe_load(sigma_content)
            validation_result = validate_sigma_rule(sigma_rule)
            
            if validation_result['valid']:
                # Trigger Step Function for processing
                trigger_sigma_workflow(bucket, key, sigma_rule)
                metrics.add_metric(name="ValidSigmaRules", unit="Count", value=1)
            else:
                logger.error(f"Invalid SIGMA rule: {validation_result['errors']}")
                metrics.add_metric(name="InvalidSigmaRules", unit="Count", value=1)
                
        except Exception as e:
            logger.error(f"Error processing SIGMA rule: {str(e)}")
            metrics.add_metric(name="SigmaProcessingErrors", unit="Count", value=1)
    
    return {'statusCode': 200}
```

## IAM Roles and Policies

### Base Lambda Execution Role
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    }
  ]
}
```

### Function-Specific Policies

#### ingest_sightings Policy
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/frank-tenants-*",
        "arn:aws:dynamodb:*:*:table/frank-idempotency-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:aws:kms:*:*:key/*",
      "Condition": {
        "StringEquals": {
          "kms:EncryptionContext:Project": "frank"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage"
      ],
      "Resource": "arn:aws:sqs:*:*:frank-processing-*"
    }
  ]
}
```

## Lambda Layer Configuration

### AWS Powertools Layer
- **ARN**: `arn:aws:lambda:eu-west-1:017000801446:layer:AWSLambdaPowertoolsPythonV2:59`
- **Purpose**: Logging, tracing, metrics, and utilities

### Custom Dependencies Layer
```python
# requirements.txt
pydantic==2.4.2
sigma-cli==1.0.3
requests==2.31.0
jsonschema==4.19.1
cryptography==41.0.7
```

## Environment Configuration

### Common Environment Variables
```bash
# AWS Region
AWS_DEFAULT_REGION=eu-west-1

# PowerTools Configuration
POWERTOOLS_SERVICE_NAME=frank
POWERTOOLS_LOG_LEVEL=INFO
POWERTOOLS_METRICS_NAMESPACE=FRANK

# Table Names
FRANK_AGGREGATES_TABLE=frank-aggregates-{env}
FRANK_TENANTS_TABLE=frank-tenants-{env}
FRANK_IDEMPOTENCY_TABLE=frank-idempotency-{env}

# S3 Buckets
FRANK_RAW_BUCKET=frank-raw-{account}-{env}
FRANK_ARTIFACTS_BUCKET=frank-artifacts-{account}-{env}
FRANK_EXPORTS_BUCKET=frank-exports-{account}-{env}

# KMS Keys
FRANK_S3_KEY_ARN=arn:aws:kms:eu-west-1:{account}:key/{s3-key-id}
FRANK_DDB_KEY_ARN=arn:aws:kms:eu-west-1:{account}:key/{ddb-key-id}
FRANK_APP_KEY_ARN=arn:aws:kms:eu-west-1:{account}:key/{app-key-id}

# OpenSearch
OPENSEARCH_ENDPOINT=https://frank-{env}.eu-west-1.es.amazonaws.com
```

## Monitoring and Observability

### CloudWatch Metrics
- **Custom Metrics**: Business metrics via PowerTools
- **Duration**: Function execution time
- **Error Rate**: Failed invocations
- **Throttles**: Concurrent execution limits

### X-Ray Tracing
- **Enabled**: All functions
- **Sampling**: 10% for cost optimization
- **Annotations**: tenant_id, function_type

### Alarms
```yaml
Alarms:
  - AlarmName: Lambda-HighErrorRate
    MetricName: Errors
    Threshold: 5
    ComparisonOperator: GreaterThanThreshold
    EvaluationPeriods: 2
    
  - AlarmName: Lambda-LongDuration
    MetricName: Duration
    Threshold: 25000  # 25 seconds
    ComparisonOperator: GreaterThanThreshold
    EvaluationPeriods: 2
```

## Security Best Practices

### Code Security
- **Secrets**: Use AWS Secrets Manager, not environment variables
- **Input Validation**: Validate all inputs using Pydantic models
- **Output Sanitization**: Remove sensitive data from responses

### Network Security
- **VPC**: Deploy in private subnets for sensitive functions
- **Security Groups**: Restrictive outbound rules
- **VPC Endpoints**: Access AWS services without internet

### Error Handling
```python
try:
    result = process_sighting(data)
except ValidationError as e:
    logger.error(f"Validation error: {str(e)}")
    return create_error_response(400, "Invalid input")
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}")
    return create_error_response(500, "Internal error")
```

## Deployment Configuration

### SAM Template Example
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  IngestSightingsFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub 'frank-ingest-sightings-${Environment}'
      CodeUri: src/ingest_sightings/
      Handler: lambda_function.lambda_handler
      Runtime: python3.11
      MemorySize: 512
      Timeout: 30
      Layers:
        - !Ref PowertoolsLayer
        - !Ref DependenciesLayer
      Environment:
        Variables:
          POWERTOOLS_SERVICE_NAME: frank
          FRANK_TENANTS_TABLE: !Ref TenantsTable
      Events:
        ApiEvent:
          Type: Api
          Properties:
            Path: /v1/sightings
            Method: POST
            Auth:
              Authorizer: CognitoAuthorizer
```

## Performance Optimization

### Cold Start Mitigation
- **Provisioned Concurrency**: For production critical functions
- **Connection Pooling**: Reuse database connections
- **Lazy Loading**: Import modules only when needed

### Memory and Timeout Tuning
- **Profiling**: Use AWS Lambda Power Tuning
- **Right-sizing**: Match memory to CPU requirements
- **Timeout**: Set appropriately for function complexity

## Implementation Checklist
- [ ] Create IAM roles with least privilege policies
- [ ] Deploy Lambda functions with proper configuration
- [ ] Set up environment variables and secrets
- [ ] Configure Lambda layers for dependencies
- [ ] Set up CloudWatch monitoring and alarms
- [ ] Configure X-Ray tracing
- [ ] Test function invocation and error handling
- [ ] Set up VPC configuration if required
- [ ] Configure reserved/provisioned concurrency
- [ ] Implement comprehensive error handling
- [ ] Set up dead letter queues for failed invocations
- [ ] Test idempotency and retry logic
