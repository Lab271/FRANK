# Step Functions Configuration

## Overview

AWS Step Functions provides serverless orchestration for the FRANK platform, managing complex workflows for threat intelligence processing, data validation, and multi-tenant operations. This configuration includes state machines for SIGMA rule processing, tenant management, and data pipeline orchestration.

## Components

### 1. State Machines

#### SIGMA Processing Workflow
- **Purpose**: Orchestrates SIGMA rule execution against threat data
- **Triggers**: S3 events, scheduled processing, manual execution
- **Flow**: Data validation → Rule execution → Result aggregation → Notification

#### Tenant Management Workflow  
- **Purpose**: Manages tenant lifecycle operations
- **Triggers**: API Gateway requests, scheduled maintenance
- **Flow**: Tenant validation → Resource provisioning → Configuration → Verification

#### Data Pipeline Orchestration
- **Purpose**: Coordinates data ingestion and processing
- **Triggers**: Data upload events, scheduled batches
- **Flow**: Data validation → Transformation → Enrichment → Storage → Indexing

### 2. IAM Roles and Policies

#### Step Functions Execution Role
```yaml
Role: frank-stepfunctions-execution-role-{environment}
Policies:
  - Lambda function invocation
  - DynamoDB read/write access
  - S3 bucket access
  - SNS/SQS messaging
  - CloudWatch logging
```

#### State Machine Specific Roles
```yaml
SIGMA Processing Role:
  - Lambda: sigma-executor, result-aggregator
  - DynamoDB: sightings, indicators tables
  - S3: raw-data, processed-data buckets

Tenant Management Role:
  - Lambda: tenant-manager, resource-provisioner
  - DynamoDB: tenants table
  - S3: tenant-specific buckets
```

### 3. State Machine Definitions

#### SIGMA Processing State Machine
```json
{
  "Comment": "SIGMA rule processing workflow",
  "StartAt": "ValidateInput",
  "States": {
    "ValidateInput": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:{region}:{account}:function:frank-validate-input-{env}",
      "Next": "CheckRuleType"
    },
    "CheckRuleType": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.ruleType",
          "StringEquals": "sigma",
          "Next": "ProcessSigmaRule"
        },
        {
          "Variable": "$.ruleType",
          "StringEquals": "yara",
          "Next": "ProcessYaraRule"
        }
      ],
      "Default": "UnsupportedRule"
    },
    "ProcessSigmaRule": {
      "Type": "Parallel",
      "Branches": [
        {
          "StartAt": "ExecuteSigmaRule",
          "States": {
            "ExecuteSigmaRule": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:{region}:{account}:function:frank-sigma-executor-{env}",
              "End": true
            }
          }
        },
        {
          "StartAt": "AggregateResults",
          "States": {
            "AggregateResults": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:{region}:{account}:function:frank-result-aggregator-{env}",
              "End": true
            }
          }
        }
      ],
      "Next": "StoreResults"
    },
    "StoreResults": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:{region}:{account}:function:frank-store-results-{env}",
      "Next": "SendNotification"
    },
    "SendNotification": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:{region}:{account}:frank-notifications-{env}",
        "Message.$": "$.notificationMessage"
      },
      "End": true
    },
    "UnsupportedRule": {
      "Type": "Fail",
      "Error": "UnsupportedRuleType",
      "Cause": "The specified rule type is not supported"
    }
  }
}
```

### 4. Event Integration

#### CloudWatch Events Rules
```yaml
ScheduledProcessing:
  ScheduleExpression: "rate(1 hour)"
  Target: SIGMA Processing State Machine
  Input: { "trigger": "scheduled", "batchSize": 1000 }

S3DataUpload:
  EventPattern:
    source: ["aws.s3"]
    detail:
      eventSource: ["s3.amazonaws.com"]
      eventName: ["PutObject"]
  Target: Data Pipeline State Machine
```

#### API Gateway Integration
```yaml
Endpoints:
  /workflows/sigma/execute:
    Method: POST
    Integration: StartExecution
    StateMachine: SIGMA Processing
    
  /workflows/tenant/provision:
    Method: POST
    Integration: StartExecution
    StateMachine: Tenant Management
```

### 5. Error Handling and Retry Logic

#### Retry Configuration
```yaml
RetryPolicy:
  ErrorEquals: ["Lambda.ServiceException", "Lambda.AWSLambdaException"]
  IntervalSeconds: 2
  MaxAttempts: 3
  BackoffRate: 2.0

CatchBlocks:
  ErrorEquals: ["States.ALL"]
  Next: "ErrorHandler"
  ResultPath: "$.error"
```

#### Dead Letter Queues
```yaml
DLQConfiguration:
  SQSQueue: frank-stepfunctions-dlq-{environment}
  MaxReceiveCount: 3
  MessageRetentionPeriod: 1209600  # 14 days
```

### 6. Monitoring and Observability

#### CloudWatch Metrics
- Execution success/failure rates
- Execution duration
- State transition counts
- Error rates by state

#### X-Ray Tracing
```yaml
TracingConfiguration:
  Enabled: true
  DistributedTracing: true
  SamplingRate: 0.1  # 10% sampling for production
```

#### CloudWatch Alarms
```yaml
Alarms:
  - Name: "High Execution Failure Rate"
    MetricName: "ExecutionsFailed"
    Threshold: 5
    ComparisonOperator: "GreaterThanThreshold"
    
  - Name: "Long Execution Duration"
    MetricName: "ExecutionTime"
    Threshold: 300000  # 5 minutes
    ComparisonOperator: "GreaterThanThreshold"
```

### 7. Security Configuration

#### Encryption
- State machine definition encryption using customer-managed KMS key
- Execution history encryption
- Input/output data encryption

#### Access Control
```yaml
ResourcePolicy:
  Effect: "Allow"
  Principal:
    AWS: "arn:aws:iam::{account}:role/frank-api-gateway-role-{env}"
  Action: "states:StartExecution"
  Resource: "arn:aws:states:{region}:{account}:stateMachine:frank-*"
  
VPCConfiguration:
  SubnetIds: [private-subnet-1, private-subnet-2]
  SecurityGroupIds: [stepfunctions-sg]
```

### 8. Cost Optimization

#### Express vs Standard Workflows
```yaml
WorkflowTypes:
  SIGMA Processing: "STANDARD"  # Long-running, complex logic
  Data Validation: "EXPRESS"    # Short, frequent executions
  Notifications: "EXPRESS"      # Simple, fast operations
```

#### Execution Limits
```yaml
Limits:
  MaxConcurrentExecutions: 100
  ExecutionTimeout: 3600  # 1 hour
  HistoryRetention: 90    # days
```

## Deployment

### Prerequisites
1. Lambda functions deployed
2. DynamoDB tables created
3. S3 buckets configured
4. SNS topics provisioned

### CloudFormation Deployment
```bash
aws cloudformation deploy \
  --template-file stepfunctions-template.yaml \
  --stack-name frank-stepfunctions-{environment} \
  --parameter-overrides \
    Environment={environment} \
    ProjectName=frank \
    LambdaRoleArn={lambda-role-arn} \
  --capabilities CAPABILITY_IAM
```

### Testing
```bash
# Start execution
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:{region}:{account}:stateMachine:frank-sigma-processing-{env} \
  --input '{"ruleType": "sigma", "ruleId": "test-rule", "dataSource": "s3://frank-raw-data/test/"}'

# Check execution status
aws stepfunctions describe-execution \
  --execution-arn {execution-arn}
```

## Operational Procedures

### Monitoring Workflows
1. Check CloudWatch dashboard for execution metrics
2. Review X-Ray traces for performance bottlenecks
3. Monitor DLQ for failed executions
4. Analyze execution history for patterns

### Troubleshooting
1. Check state machine definition for syntax errors
2. Verify IAM permissions for state transitions
3. Review Lambda function logs for task failures
4. Validate input/output data format

### Scaling Considerations
1. Monitor concurrent execution limits
2. Optimize state machine design for parallel processing
3. Consider Express workflows for high-frequency operations
4. Implement circuit breakers for external dependencies

### Backup and Recovery
1. Version control state machine definitions
2. Export execution history periodically
3. Maintain rollback procedures for deployments
4. Document recovery procedures for critical workflows
