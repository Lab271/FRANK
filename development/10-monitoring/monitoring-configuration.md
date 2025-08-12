# Monitoring Configuration

## Overview

Comprehensive monitoring and observability for the FRANK platform using Amazon CloudWatch, AWS X-Ray, and custom dashboards. This configuration provides real-time insights into system performance, security events, and operational health across all AWS services.

## Components

### 1. CloudWatch Dashboards

#### Executive Dashboard
- **Purpose**: High-level KPIs and system health overview
- **Audience**: Management and operations teams
- **Update Frequency**: Real-time (1-minute intervals)

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ApiGateway", "Count", "ApiName", "frank-api-prod"],
          ["AWS/Lambda", "Invocations", "FunctionName", "frank-threat-processor-prod"],
          ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "frank-sightings-prod"]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "API and Processing Volume"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Errors", "FunctionName", "frank-threat-processor-prod"],
          ["AWS/ApiGateway", "4XXError", "ApiName", "frank-api-prod"],
          ["AWS/ApiGateway", "5XXError", "ApiName", "frank-api-prod"]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Error Rates"
      }
    }
  ]
}
```

#### Technical Operations Dashboard
- **Purpose**: Detailed technical metrics for troubleshooting
- **Audience**: DevOps and engineering teams
- **Metrics**: Latency, throughput, error rates, resource utilization

#### Security Dashboard
- **Purpose**: Security events and threat detection metrics
- **Audience**: Security operations team
- **Metrics**: Authentication failures, suspicious activities, data access patterns

### 2. CloudWatch Alarms

#### Critical System Alarms
```yaml
HighErrorRate:
  AlarmName: frank-high-error-rate-prod
  MetricName: Errors
  Namespace: AWS/Lambda
  Statistic: Sum
  Period: 300
  EvaluationPeriods: 2
  Threshold: 10
  ComparisonOperator: GreaterThanThreshold
  AlarmActions:
    - arn:aws:sns:us-east-1:123456789012:frank-critical-alerts
  
APIGatewayLatency:
  AlarmName: frank-api-high-latency-prod
  MetricName: Latency
  Namespace: AWS/ApiGateway
  Statistic: Average
  Period: 300
  EvaluationPeriods: 3
  Threshold: 5000
  ComparisonOperator: GreaterThanThreshold
  
DynamoDBThrottling:
  AlarmName: frank-dynamodb-throttling-prod
  MetricName: SystemErrors
  Namespace: AWS/DynamoDB
  Statistic: Sum
  Period: 300
  EvaluationPeriods: 1
  Threshold: 0
  ComparisonOperator: GreaterThanThreshold
```

#### Performance Alarms
```yaml
LambdaColdStarts:
  AlarmName: frank-lambda-cold-starts-prod
  MetricName: Duration
  Namespace: AWS/Lambda
  Statistic: Maximum
  Period: 300
  EvaluationPeriods: 2
  Threshold: 10000
  ComparisonOperator: GreaterThanThreshold

S3RequestLatency:
  AlarmName: frank-s3-high-latency-prod
  MetricName: TotalRequestLatency
  Namespace: AWS/S3
  Statistic: Average
  Period: 300
  EvaluationPeriods: 2
  Threshold: 1000
  ComparisonOperator: GreaterThanThreshold
```

#### Security Alarms
```yaml
AuthenticationFailures:
  AlarmName: frank-auth-failures-prod
  MetricName: SignInFailures
  Namespace: AWS/Cognito
  Statistic: Sum
  Period: 300
  EvaluationPeriods: 1
  Threshold: 20
  ComparisonOperator: GreaterThanThreshold
  TreatMissingData: notBreaching

UnauthorizedAccess:
  AlarmName: frank-unauthorized-access-prod
  MetricName: 4XXError
  Namespace: AWS/ApiGateway
  Statistic: Sum
  Period: 300
  EvaluationPeriods: 2
  Threshold: 50
  ComparisonOperator: GreaterThanThreshold
```

### 3. Custom Metrics

#### Application Metrics
```python
# Lambda function custom metrics
import boto3
import json
from datetime import datetime

cloudwatch = boto3.client('cloudwatch')

def put_custom_metric(metric_name, value, unit='Count', dimensions=None):
    """Send custom metric to CloudWatch"""
    try:
        response = cloudwatch.put_metric_data(
            Namespace='FRANK/Application',
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Dimensions': dimensions or [],
                    'Value': value,
                    'Unit': unit,
                    'Timestamp': datetime.utcnow()
                }
            ]
        )
        return response
    except Exception as e:
        print(f"Error sending metric: {e}")

# Example usage in threat processor
def process_threat_indicators(event, context):
    tenant_id = event.get('tenant_id')
    indicators_processed = 0
    processing_time = 0
    
    start_time = datetime.utcnow()
    
    try:
        # Process indicators
        indicators = event.get('indicators', [])
        for indicator in indicators:
            # Processing logic here
            indicators_processed += 1
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Send custom metrics
        put_custom_metric(
            'IndicatorsProcessed',
            indicators_processed,
            'Count',
            [{'Name': 'TenantId', 'Value': tenant_id}]
        )
        
        put_custom_metric(
            'ProcessingTime',
            processing_time,
            'Seconds',
            [{'Name': 'TenantId', 'Value': tenant_id}]
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'processed': indicators_processed,
                'processing_time': processing_time
            })
        }
        
    except Exception as e:
        put_custom_metric(
            'ProcessingErrors',
            1,
            'Count',
            [{'Name': 'TenantId', 'Value': tenant_id}]
        )
        raise
```

#### Business Metrics
```yaml
TenantMetrics:
  - ActiveTenants: Count of tenants with activity in last 24h
  - TenantUsage: API calls per tenant per hour
  - DataVolume: GB of threat data processed per tenant
  - SigmaRuleExecutions: Number of SIGMA rules executed
  
SecurityMetrics:
  - ThreatDetections: Count of threats detected
  - FalsePositives: Count of false positive alerts
  - MeanTimeToDetection: Average time to detect threats
  - IndicatorMatches: Number of IOC matches found
```

### 4. X-Ray Tracing

#### Service Map Configuration
```yaml
TracingConfig:
  Active: true
  SamplingRate: 0.1  # 10% sampling for production
  
Services:
  - API Gateway
  - Lambda Functions
  - DynamoDB
  - S3
  - OpenSearch
  - Step Functions

AnnotationKeys:
  - tenant_id
  - request_type
  - sigma_rule_id
  - error_type
```

#### Custom Tracing
```python
# Lambda function with X-Ray tracing
import json
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

# Patch AWS SDK calls
patch_all()

@xray_recorder.capture('process_threat_data')
def process_threat_data(event, context):
    """Process threat intelligence data with X-Ray tracing"""
    
    # Add annotations for filtering
    xray_recorder.put_annotation('tenant_id', event.get('tenant_id'))
    xray_recorder.put_annotation('data_type', event.get('data_type'))
    
    # Add metadata for additional context
    xray_recorder.put_metadata('request_details', {
        'source_ip': event.get('source_ip'),
        'user_agent': event.get('user_agent'),
        'request_size': len(json.dumps(event))
    })
    
    try:
        with xray_recorder.in_subsegment('validate_input'):
            # Input validation logic
            validate_threat_data(event.get('data'))
        
        with xray_recorder.in_subsegment('enrich_data'):
            # Data enrichment logic
            enriched_data = enrich_threat_data(event.get('data'))
        
        with xray_recorder.in_subsegment('store_data'):
            # Store to DynamoDB
            store_threat_data(enriched_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'success'})
        }
        
    except Exception as e:
        xray_recorder.put_annotation('error', str(e))
        xray_recorder.put_metadata('error_details', {
            'error_type': type(e).__name__,
            'error_message': str(e)
        })
        raise
```

### 5. Log Aggregation and Analysis

#### Centralized Logging
```yaml
LogGroups:
  ApplicationLogs:
    /aws/lambda/frank-threat-processor-prod:
      RetentionInDays: 30
      FilterPatterns:
        - ErrorFilter: '[timestamp, request_id, level="ERROR", ...]'
        - SecurityFilter: '[timestamp, request_id, event_type="SECURITY", ...]'
    
  AccessLogs:
    /aws/apigateway/frank-api-prod:
      RetentionInDays: 90
      FilterPatterns:
        - UnauthorizedAccess: '[ip, -, user, timestamp, request, status=4*, size]'
    
  AuditLogs:
    /aws/cognito/frank-user-pool-prod:
      RetentionInDays: 365
      FilterPatterns:
        - FailedLogins: '[timestamp, level, message="Authentication failed", ...]'
```

#### Log Insights Queries
```sql
-- Top error messages
fields @timestamp, @message
| filter @message like /ERROR/
| stats count() by @message
| sort count desc
| limit 20

-- API response times by endpoint
fields @timestamp, @duration, @requestId
| filter @type = "REPORT"
| parse @message /Duration: (?<duration>[\d\.]+)/
| filter ispresent(duration)
| stats avg(duration), max(duration), min(duration) by bin(5m)

-- Security events analysis
fields @timestamp, tenant_id, event_type, source_ip
| filter event_type = "SECURITY"
| stats count() by source_ip, tenant_id
| sort count desc
| limit 50

-- Tenant usage patterns
fields @timestamp, tenant_id, operation
| filter ispresent(tenant_id)
| stats count() by tenant_id, operation, bin(1h)
| sort @timestamp desc
```

### 6. Notification and Alerting

#### SNS Topics
```yaml
CriticalAlerts:
  TopicName: frank-critical-alerts-prod
  Subscriptions:
    - Protocol: email
      Endpoint: devops@company.com
    - Protocol: sms
      Endpoint: +1234567890
    - Protocol: https
      Endpoint: https://alerts.company.com/webhook/frank

SecurityAlerts:
  TopicName: frank-security-alerts-prod
  Subscriptions:
    - Protocol: email
      Endpoint: security@company.com
    - Protocol: https
      Endpoint: https://siem.company.com/webhook/frank

OperationalAlerts:
  TopicName: frank-operational-alerts-prod
  Subscriptions:
    - Protocol: email
      Endpoint: operations@company.com
    - Protocol: slack
      Endpoint: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
```

#### Alert Routing Logic
```python
import json
import boto3

def lambda_handler(event, context):
    """Route alerts based on severity and type"""
    
    sns = boto3.client('sns')
    
    # Parse CloudWatch alarm
    message = json.loads(event['Records'][0]['Sns']['Message'])
    alarm_name = message['AlarmName']
    new_state = message['NewStateValue']
    reason = message['NewStateReason']
    
    # Determine severity and routing
    if 'critical' in alarm_name.lower() or 'high-error' in alarm_name.lower():
        topic_arn = 'arn:aws:sns:us-east-1:123456789012:frank-critical-alerts-prod'
        priority = 'P1'
    elif 'security' in alarm_name.lower() or 'auth' in alarm_name.lower():
        topic_arn = 'arn:aws:sns:us-east-1:123456789012:frank-security-alerts-prod'
        priority = 'P2'
    else:
        topic_arn = 'arn:aws:sns:us-east-1:123456789012:frank-operational-alerts-prod'
        priority = 'P3'
    
    # Format alert message
    alert_message = {
        'priority': priority,
        'alarm_name': alarm_name,
        'state': new_state,
        'reason': reason,
        'timestamp': message['StateChangeTime'],
        'dashboard_url': f"https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=FRANK-{priority}"
    }
    
    # Send alert
    response = sns.publish(
        TopicArn=topic_arn,
        Message=json.dumps(alert_message, indent=2),
        Subject=f'FRANK Alert [{priority}]: {alarm_name}'
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({'message_id': response['MessageId']})
    }
```

### 7. Health Checks and Synthetic Monitoring

#### API Health Checks
```python
import json
import boto3
import requests
from datetime import datetime

def lambda_handler(event, context):
    """Synthetic monitoring for FRANK API endpoints"""
    
    cloudwatch = boto3.client('cloudwatch')
    
    endpoints = [
        {'url': 'https://api.frank-prod.com/health', 'name': 'HealthCheck'},
        {'url': 'https://api.frank-prod.com/v1/indicators', 'name': 'IndicatorsAPI'},
        {'url': 'https://api.frank-prod.com/v1/sightings', 'name': 'SightingsAPI'}
    ]
    
    results = []
    
    for endpoint in endpoints:
        start_time = datetime.utcnow()
        
        try:
            response = requests.get(endpoint['url'], timeout=10)
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Check response
            if response.status_code == 200:
                availability = 1
                error_message = None
            else:
                availability = 0
                error_message = f"HTTP {response.status_code}"
            
            # Send metrics
            cloudwatch.put_metric_data(
                Namespace='FRANK/SyntheticMonitoring',
                MetricData=[
                    {
                        'MetricName': 'Availability',
                        'Dimensions': [{'Name': 'Endpoint', 'Value': endpoint['name']}],
                        'Value': availability,
                        'Unit': 'Count'
                    },
                    {
                        'MetricName': 'ResponseTime',
                        'Dimensions': [{'Name': 'Endpoint', 'Value': endpoint['name']}],
                        'Value': response_time,
                        'Unit': 'Milliseconds'
                    }
                ]
            )
            
            results.append({
                'endpoint': endpoint['name'],
                'available': availability == 1,
                'response_time': response_time,
                'error': error_message
            })
            
        except Exception as e:
            # Send availability metric as 0
            cloudwatch.put_metric_data(
                Namespace='FRANK/SyntheticMonitoring',
                MetricData=[
                    {
                        'MetricName': 'Availability',
                        'Dimensions': [{'Name': 'Endpoint', 'Value': endpoint['name']}],
                        'Value': 0,
                        'Unit': 'Count'
                    }
                ]
            )
            
            results.append({
                'endpoint': endpoint['name'],
                'available': False,
                'error': str(e)
            })
    
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }
```

### 8. Cost Monitoring

#### Cost Allocation Tags
```yaml
ResourceTags:
  Project: frank
  Environment: prod
  Component: threat-intelligence
  Owner: security-team
  CostCenter: security-operations
```

#### Cost Alerts
```yaml
BudgetAlerts:
  MonthlyBudget:
    BudgetLimit: 5000
    CostFilters:
      Service: ['Lambda', 'DynamoDB', 'S3', 'API Gateway']
      Tag:
        Project: ['frank']
    AlertThresholds: [50, 80, 100, 120]
    
  DailySpendAlert:
    BudgetLimit: 200
    TimeUnit: DAILY
    AlertThresholds: [80, 100]
```

## Deployment

### CloudFormation Template
```bash
aws cloudformation deploy \
  --template-file monitoring-template.yaml \
  --stack-name frank-monitoring-prod \
  --parameter-overrides \
    Environment=prod \
    ProjectName=frank \
    NotificationEmail=devops@company.com \
  --capabilities CAPABILITY_IAM
```

### Dashboard Import
```bash
# Import custom dashboard
aws cloudwatch put-dashboard \
  --dashboard-name "FRANK-Executive-Dashboard" \
  --dashboard-body file://dashboards/executive-dashboard.json
```

## Operational Procedures

### Daily Monitoring Tasks
1. Review overnight alerts and incidents
2. Check dashboard for performance anomalies
3. Validate synthetic monitoring results
4. Review cost and usage reports

### Weekly Analysis
1. Analyze performance trends
2. Review and tune alarm thresholds
3. Update monitoring coverage
4. Cost optimization review

### Monthly Reviews
1. Dashboard and metrics review
2. Alert fatigue analysis
3. Monitoring strategy updates
4. Capacity planning based on trends
