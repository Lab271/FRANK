# ECS Configuration

## Overview

Amazon Elastic Container Service (ECS) provides containerized compute capacity for the FRANK platform, specifically for running SIGMA tools, batch processing workloads, and compute-intensive threat analysis tasks. This configuration includes ECS clusters, task definitions, and services for scalable threat intelligence processing.

## Components

### 1. ECS Cluster Configuration

#### Cluster Setup
- **Cluster Name**: `frank-cluster-{environment}`
- **Capacity Providers**: AWS Fargate and EC2 Auto Scaling
- **Container Insights**: Enabled for monitoring
- **Execute Command Logging**: CloudWatch for debugging

#### Compute Strategies
```yaml
Fargate:
  Use Case: Short-lived, stateless workloads
  Benefits: No server management, fast scaling
  Examples: SIGMA rule execution, data validation

EC2:
  Use Case: Long-running, resource-intensive tasks
  Benefits: Cost optimization, custom instance types
  Examples: Large-scale threat hunting, ML inference
```

### 2. Task Definitions

#### SIGMA Processor Task
```yaml
Family: frank-sigma-processor
CPU: 1024 (1 vCPU)
Memory: 2048 MB
Network Mode: awsvpc
Requires Compatibility: FARGATE

Container Definitions:
  - Name: sigma-processor
    Image: frank/sigma-processor:latest
    Essential: true
    Environment:
      - ENVIRONMENT: ${environment}
      - TENANT_ID: ${tenant_id}
      - LOG_LEVEL: INFO
    Secrets:
      - Name: DB_PASSWORD
        ValueFrom: arn:aws:secretsmanager:region:account:secret:frank/db
    LogConfiguration:
      LogDriver: awslogs
      LogGroup: /ecs/frank-sigma-processor
      StreamPrefix: ecs
```

#### Threat Hunter Task
```yaml
Family: frank-threat-hunter
CPU: 2048 (2 vCPU)
Memory: 4096 MB
Network Mode: awsvpc
Requires Compatibility: FARGATE, EC2

Container Definitions:
  - Name: threat-hunter
    Image: frank/threat-hunter:latest
    Essential: true
    MountPoints:
      - SourceVolume: threat-data
        ContainerPath: /data
        ReadOnly: false
    Environment:
      - HUNTING_MODE: batch
      - DATA_SOURCE: s3
    LogConfiguration:
      LogDriver: awslogs
      LogGroup: /ecs/frank-threat-hunter
      StreamPrefix: ecs

Volumes:
  - Name: threat-data
    EfsVolumeConfiguration:
      FileSystemId: ${efs_file_system_id}
      TransitEncryption: ENABLED
```

#### Data Enrichment Task
```yaml
Family: frank-data-enrichment
CPU: 512
Memory: 1024
Network Mode: awsvpc
Requires Compatibility: FARGATE

Container Definitions:
  - Name: data-enricher
    Image: frank/data-enricher:latest
    Essential: true
    Environment:
      - ENRICHMENT_SOURCES: virustotal,abuseipdb,shodan
      - RATE_LIMIT: 100
    Secrets:
      - Name: VT_API_KEY
        ValueFrom: arn:aws:secretsmanager:region:account:secret:frank/virustotal
      - Name: ABUSEIPDB_API_KEY
        ValueFrom: arn:aws:secretsmanager:region:account:secret:frank/abuseipdb
```

### 3. Service Configurations

#### SIGMA Processing Service
```yaml
ServiceName: frank-sigma-service
Cluster: frank-cluster-${environment}
TaskDefinition: frank-sigma-processor
DesiredCount: 2
LaunchType: FARGATE

NetworkConfiguration:
  Subnets: [private-subnet-1, private-subnet-2]
  SecurityGroups: [ecs-sigma-sg]
  AssignPublicIp: DISABLED

LoadBalancers:
  - TargetGroupArn: ${sigma_target_group_arn}
    ContainerName: sigma-processor
    ContainerPort: 8080

AutoScaling:
  MinCapacity: 1
  MaxCapacity: 10
  TargetCPUUtilization: 70
  TargetMemoryUtilization: 80
```

#### Scheduled Batch Processing
```yaml
ServiceName: frank-batch-processor
Cluster: frank-cluster-${environment}
TaskDefinition: frank-threat-hunter
SchedulingStrategy: REPLICA
DesiredCount: 0  # Scaled by EventBridge rules

PlacementConstraints:
  - Type: memberOf
    Expression: 'attribute:ecs.instance-type =~ t3.*'

ServiceTags:
  - Key: Purpose
    Value: BatchProcessing
  - Key: Schedule
    Value: EventBridge
```

### 4. Auto Scaling Configuration

#### Service Auto Scaling
```yaml
ScalableTarget:
  ServiceNamespace: ecs
  ResourceId: service/frank-cluster-${environment}/frank-sigma-service
  ScalableDimension: ecs:service:DesiredCount
  MinCapacity: 1
  MaxCapacity: 20

ScalingPolicies:
  - PolicyName: CPUScaling
    PolicyType: TargetTrackingScaling
    TargetValue: 70.0
    ScaleOutCooldown: 300
    ScaleInCooldown: 300
    
  - PolicyName: MemoryScaling
    PolicyType: TargetTrackingScaling
    TargetValue: 80.0
    MetricType: ECSServiceAverageMemoryUtilization
```

#### Cluster Auto Scaling (EC2)
```yaml
AutoScalingGroup:
  LaunchTemplate: frank-ecs-launch-template
  MinSize: 0
  MaxSize: 10
  DesiredCapacity: 2
  TargetGroupARNs: []
  VPCZoneIdentifier: [private-subnet-1, private-subnet-2]

LaunchTemplate:
  ImageId: ami-0c02fb55956c7d316  # ECS-optimized AMI
  InstanceType: t3.medium
  UserData: |
    #!/bin/bash
    echo ECS_CLUSTER=frank-cluster-${environment} >> /etc/ecs/ecs.config
    echo ECS_ENABLE_CONTAINER_METADATA=true >> /etc/ecs/ecs.config
```

### 5. Networking and Security

#### VPC Configuration
```yaml
VPC:
  CIDR: 10.0.0.0/16
  
Subnets:
  Private:
    - 10.0.1.0/24 (AZ-a)
    - 10.0.2.0/24 (AZ-b)
    - 10.0.3.0/24 (AZ-c)
  Public:
    - 10.0.101.0/24 (AZ-a) - NAT Gateway only
    - 10.0.102.0/24 (AZ-b) - NAT Gateway only

SecurityGroups:
  ECS-Tasks:
    - Port 8080: ALB access
    - Port 443: Outbound HTTPS
    - Port 53: DNS resolution
  ECS-ALB:
    - Port 80: Internet access
    - Port 443: Internet access
```

#### IAM Roles and Policies
```yaml
TaskExecutionRole:
  Policies:
    - AmazonECSTaskExecutionRolePolicy
    - Custom policy for Secrets Manager access
    - Custom policy for CloudWatch Logs

TaskRole:
  Policies:
    - DynamoDB read/write for specific tables
    - S3 access for data buckets
    - OpenSearch access for indexing
    - SNS publish for notifications
```

### 6. Container Images and Registry

#### ECR Repositories
```yaml
Repositories:
  - frank/sigma-processor
  - frank/threat-hunter
  - frank/data-enricher
  - frank/yara-scanner

ImageScanningConfiguration:
  ScanOnPush: true
  
LifecyclePolicy:
  Rules:
    - Keep last 10 tagged images
    - Delete untagged images after 1 day
    - Keep production images indefinitely
```

#### Container Build Process
```dockerfile
# Example: SIGMA Processor Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Set up non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080
CMD ["python", "src/main.py"]
```

### 7. Monitoring and Logging

#### CloudWatch Container Insights
```yaml
Configuration:
  Enabled: true
  MetricCollection: enhanced
  
Metrics:
  - CPU utilization
  - Memory utilization
  - Network I/O
  - Disk I/O
  - Task count
  - Service events
```

#### Log Aggregation
```yaml
LogGroups:
  /ecs/frank-sigma-processor:
    RetentionInDays: 30
    
  /ecs/frank-threat-hunter:
    RetentionInDays: 7
    
  /ecs/frank-data-enricher:
    RetentionInDays: 14

LogFilters:
  - FilterName: ErrorFilter
    FilterPattern: '[timestamp, request_id, level="ERROR", ...]'
    DestinationArn: arn:aws:logs:region:account:destination:frank-errors
```

#### X-Ray Tracing
```yaml
Configuration:
  TracingConfig:
    Type: Active
    
SidecarContainer:
  - Name: xray-daemon
    Image: amazon/aws-xray-daemon:latest
    Cpu: 32
    Memory: 256
    PortMappings:
      - ContainerPort: 2000
        Protocol: udp
```

### 8. Event-Driven Processing

#### EventBridge Integration
```yaml
Rules:
  - Name: sigma-processing-schedule
    ScheduleExpression: rate(1 hour)
    Targets:
      - Id: sigma-batch-task
        Arn: arn:aws:ecs:region:account:cluster/frank-cluster
        RoleArn: arn:aws:iam::account:role/EventBridgeECSRole
        EcsParameters:
          TaskDefinitionArn: frank-sigma-processor
          LaunchType: FARGATE
          NetworkConfiguration:
            AwsVpcConfiguration:
              Subnets: [private-subnet-1, private-subnet-2]
              SecurityGroups: [ecs-sigma-sg]

  - Name: s3-upload-trigger
    EventPattern:
      source: [aws.s3]
      detail:
        eventSource: [s3.amazonaws.com]
        eventName: [PutObject]
    Targets:
      - Id: process-uploaded-data
        Arn: arn:aws:ecs:region:account:cluster/frank-cluster
        EcsParameters:
          TaskDefinitionArn: frank-data-enrichment
```

### 9. Cost Optimization

#### Spot Instance Configuration
```yaml
CapacityProviders:
  - Name: EC2-Spot
    AutoScalingGroupProvider:
      AutoScalingGroupArn: arn:aws:autoscaling:region:account:autoScalingGroup:*
      ManagedScaling:
        Status: ENABLED
        TargetCapacity: 80
      ManagedTerminationProtection: ENABLED

SpotFleetRequestConfig:
  IamFleetRole: arn:aws:iam::account:role/aws-ec2-spot-fleet-role
  AllocationStrategy: diversified
  TargetCapacity: 2
  SpotPrice: 0.05
  LaunchSpecifications:
    - ImageId: ami-0c02fb55956c7d316
      InstanceType: t3.medium
      KeyName: frank-keypair
      SecurityGroups: [ecs-instance-sg]
      SubnetId: private-subnet-1
```

#### Resource Optimization
```yaml
TaskSizing:
  Development:
    CPU: 256
    Memory: 512
  
  Production:
    CPU: 1024
    Memory: 2048

ScheduledScaling:
  BusinessHours:
    DesiredCount: 4
    Schedule: "0 8 * * MON-FRI"
  
  OffHours:
    DesiredCount: 1
    Schedule: "0 18 * * MON-FRI"
```

### 10. Disaster Recovery

#### Multi-AZ Deployment
```yaml
ServiceConfiguration:
  PlacementStrategy:
    - Type: spread
      Field: attribute:ecs.availability-zone
  
  PlacementConstraints:
    - Type: distinctInstance
```

#### Backup Strategy
```yaml
EFS_Backup:
  BackupPolicy:
    Status: ENABLED
  
  BackupPlan:
    BackupPlanName: frank-efs-backup
    BackupPlanRule:
      - RuleName: DailyBackups
        TargetBackupVault: default
        ScheduleExpression: cron(0 2 * * ? *)
        Lifecycle:
          DeleteAfterDays: 30
```

## Deployment

### Prerequisites
1. VPC and subnets configured
2. ECR repositories created
3. Container images built and pushed
4. IAM roles and policies configured

### CloudFormation Deployment
```bash
aws cloudformation deploy \
  --template-file ecs-template.yaml \
  --stack-name frank-ecs-${ENVIRONMENT} \
  --parameter-overrides \
    Environment=${ENVIRONMENT} \
    ProjectName=frank \
    VPCId=${VPC_ID} \
    PrivateSubnetIds=${PRIVATE_SUBNET_IDS} \
  --capabilities CAPABILITY_IAM
```

### Container Deployment
```bash
# Build and push images
docker build -t frank/sigma-processor:latest .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
docker tag frank/sigma-processor:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/frank/sigma-processor:latest
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/frank/sigma-processor:latest

# Update service
aws ecs update-service \
  --cluster frank-cluster-${ENVIRONMENT} \
  --service frank-sigma-service \
  --force-new-deployment
```

## Operational Procedures

### Monitoring and Troubleshooting
1. Monitor CloudWatch Container Insights dashboard
2. Check ECS service events for deployment issues
3. Review application logs in CloudWatch Logs
4. Use ECS Exec for debugging running containers

### Scaling Operations
1. Monitor service CPU/memory utilization
2. Adjust auto-scaling policies based on workload patterns
3. Scale cluster capacity providers for cost optimization
4. Review and adjust task resource allocations

### Security Management
1. Regular security scanning of container images
2. Update base images and dependencies
3. Rotate secrets and credentials
4. Review and update IAM policies

### Performance Optimization
1. Profile application performance in containers
2. Optimize container resource allocation
3. Implement efficient caching strategies
4. Monitor and optimize network performance
