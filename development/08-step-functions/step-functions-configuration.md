# Step Functions Configuration

## Overview

AWS Step Functions provides serverless orchestration for the FRANK platform, managing complex workflows for threat intelligence processing, data validation. This configuration includes state machines for submitter management, and data pipeline orchestration.

## Components

### 1. State Machines

#### Submitter Management Workflow  
- **Purpose**: Manages submitter lifecycle operations
- **Triggers**: API Gateway requests, scheduled maintenance
- **Flow**: Submitter validation → Resource provisioning → Configuration → Verification

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
Submitter Management Role:
  - Lambda: submitter-manager, resource-provisioner
  - DynamoDB: submitters table
  - S3: submitter-specific buckets
```

### 3. State Machine Definitions



### 4. Event Integration

#### CloudWatch Events Rules
```yaml
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
  /workflows/submitter/provision:
    Method: POST
    Integration: StartExecution
    StateMachine: Submitter Management
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
