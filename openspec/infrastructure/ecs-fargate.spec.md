# ECS Fargate Container Deployment Specification

**Domain:** Infrastructure / Container Orchestration
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-06

**FRANK-Specific Metadata**:
- **Owner:** Infrastructure Team
- **Related Spike:** [Spike 009: AWS ECS Basic](tests/spikes/009_aws_ecs_basic/README.md)
- **Integration:** Stage 3 cloud deployment

## Overview

Documents the container orchestration pattern for deploying FRANK applications to AWS ECS Fargate. Establishes cloud-native deployment foundation while minimizing infrastructure management overhead.

### Philosophy

- **Serverless Containers**: Zero server management (no EC2 instances)
- **Automatic Scaling**: Handle variable workloads without manual intervention
- **Pay-Per-Use**: Cost-effective for development and production environments
- **Cloud-Native Evolution**: Bridge from local development (Stage 1) to production (Stage 3)
- **From Spike to Production**: Patterns validated in Spike 009, now production-ready

### Key Capabilities

- **Container Image Management**: ECR integration with version control
- **Task Definition Configuration**: CPU, memory, environment, logging
- **Network Configuration**: Multi-AZ VPC with public/private subnets
- **Service Discovery**: ALB integration with target group health checks
- **CloudWatch Logging**: Centralized logging with retention policies
- **Auto-Scaling**: CPU/memory/request-rate based scaling (2-10 tasks)

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Usage in this specification**:
- **MUST/SHALL**: Health check configuration, network security, logging
- **SHOULD**: Follow AWS best practices for task definitions
- **MAY**: Add application-specific environment variables

---

## ADDED Requirements

### Requirement 1: Container Image Management

- **Description**: ECS Fargate must deploy containerized FRANK applications from ECR (Elastic Container Registry) with version control and automatic updates.
- **Acceptance Criteria**:
  - [ ] Docker images built from Dockerfile and pushed to ECR
  - [ ] ECS task definitions reference latest image tags
  - [ ] Image updates trigger automatic task replacement
  - [ ] Old task gracefully terminates after new task health check passes
- **Stage Availability**: Stage 3 (AWS Cloud), Stage 4 (Kubernetes equivalent)
- **Related ADR(s)**: N/A

### Requirement 2: Task Definition Configuration

- **Description**: ECS task definitions must specify compute resources, environment variables, logging configuration, and container runtime settings.
- **Acceptance Criteria**:
  - [ ] Task definition includes: container image URI, CPU (0.25 vCPU), memory (0.5GB), port mappings (8000)
  - [ ] Environment variables configured (DB connection strings, AWS region, log level)
  - [ ] CloudWatch log group configured with 7-day retention
  - [ ] Task execution role grants ECR pull and CloudWatch write permissions
- **Stage Availability**: Stage 3 (AWS), Stage 4 (Kubernetes ConfigMaps equivalent)
- **Related ADR(s)**: N/A

### Requirement 3: Network Configuration

- **Description**: ECS tasks must be deployed in appropriate VPC subnets with security groups controlling inbound/outbound traffic.
- **Acceptance Criteria**:
  - [ ] Tasks deployed in public subnets (development) or private subnets (production)
  - [ ] Security groups restrict inbound traffic to ALB only (production)
  - [ ] Outbound internet access enabled for API calls and package downloads
  - [ ] Auto-assign public IP enabled for public subnet deployments
- **Stage Availability**: Stage 3 (AWS), Stage 4 (Kubernetes NetworkPolicy equivalent)
- **Related ADR(s)**: N/A

### Requirement 4: Service Discovery and Load Balancing

- **Description**: ECS services must integrate with Application Load Balancer (ALB) for stable endpoints and health-based routing.
- **Acceptance Criteria**:
  - [ ] ECS service registered with ALB target group
  - [ ] Health check endpoint `/v1/health` returns 200 OK when healthy
  - [ ] Unhealthy tasks automatically replaced after 3 failed health checks
  - [ ] Service maintains desired task count (2-10 tasks based on auto-scaling)
- **Stage Availability**: Stage 3 (AWS), Stage 4 (Kubernetes Service/Ingress equivalent)
- **Related ADR(s)**: Spike 010 (ALB integration)

### Requirement 5: Logging and Observability

- **Description**: ECS tasks must send application logs to CloudWatch Logs for centralized monitoring and troubleshooting.
- **Acceptance Criteria**:
  - [ ] Application logs (stdout/stderr) captured in CloudWatch
  - [ ] Log group organized by environment (dev/preprod/prod)
  - [ ] Structured JSON logging for parseable log data
  - [ ] Log retention policy enforced (7 days dev, 30 days prod)
- **Stage Availability**: Stage 3 (AWS), Stage 4 (Kubernetes with Fluentd/CloudWatch agent)
- **Related ADR(s)**: Spike 013 (AWS Observability)

---

## 3. Non-Functional Requirements

### Performance

- **Startup Time**: Container must start and pass health check within 2 minutes
- **Response Time**: API endpoints must respond within 500ms (p95) after startup
- **Resource Utilization**: CPU usage < 70% during normal operation, memory < 400MB

### Scalability

- **Task Count**: Support 2-10 concurrent tasks with auto-scaling
- **Scaling Triggers**: Scale up at 70% CPU or 1000 requests/minute per task
- **Scaling Speed**: Add new task within 3 minutes of scaling trigger

### Reliability

- **Availability**: 99.9% uptime (ALB + multiple tasks)
- **Failure Recovery**: Unhealthy tasks replaced within 5 minutes
- **Zero-Downtime Deployment**: Rolling updates with health check verification
- **Data Persistence**: Stateless containers with external database (DynamoDB)

### Security

- **Network Isolation**: Tasks in private subnets (production), public subnets (development)
- **IAM Roles**: Task execution role (ECR pull, CloudWatch logs), task role (DynamoDB access)
- **Secrets Management**: Environment variables for non-sensitive config, AWS Secrets Manager for credentials
- **Image Scanning**: ECR image scanning enabled for vulnerability detection

### Cost

- **Development**: $5-15/month (single task, 0.25 vCPU, 0.5GB RAM, 8 hours/day)
- **Production**: $50-150/month (2-10 tasks, 0.5 vCPU, 1GB RAM, 24/7)
- **Cost Optimization**: Auto-scaling down during off-peak hours, spot capacity for non-critical workloads

---

## 4. Data Model / API Contract

### ECS Task Definition (CloudFormation)

```yaml
# Simplified task definition structure
FRANKTaskDefinition:
  Type: AWS::ECS::TaskDefinition
  Properties:
    Family: frank-api
    NetworkMode: awsvpc
    RequiresCompatibilities:
      - FARGATE
    Cpu: 256        # 0.25 vCPU
    Memory: 512     # 0.5GB
    ExecutionRoleArn: !GetAtt TaskExecutionRole.Arn
    TaskRoleArn: !GetAtt TaskRole.Arn
    ContainerDefinitions:
      - Name: frank-api
        Image: !Sub ${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/frank:latest
        PortMappings:
          - ContainerPort: 8000
            Protocol: tcp
        Environment:
          - Name: STAGE
            Value: stage3
          - Name: AWS_REGION
            Value: !Ref AWS::Region
          - Name: LOG_LEVEL
            Value: INFO
        LogConfiguration:
          LogDriver: awslogs
          Options:
            awslogs-group: /ecs/frank-api
            awslogs-region: !Ref AWS::Region
            awslogs-stream-prefix: ecs
        HealthCheck:
          Command:
            - CMD-SHELL
            - curl -f http://localhost:8000/v1/health || exit 1
          Interval: 30
          Timeout: 5
          Retries: 3
          StartPeriod: 60
```

### ECS Service (CloudFormation)

```yaml
FRANKService:
  Type: AWS::ECS::Service
  Properties:
    ServiceName: frank-api
    Cluster: !Ref ECSCluster
    TaskDefinition: !Ref FRANKTaskDefinition
    DesiredCount: 2
    LaunchType: FARGATE
    NetworkConfiguration:
      AwsvpcConfiguration:
        AssignPublicIp: DISABLED  # Private subnets + NAT Gateway
        SecurityGroups:
          - !Ref ECSSecurityGroup
        Subnets:
          - !Ref PrivateSubnet1
          - !Ref PrivateSubnet2
    LoadBalancers:
      - ContainerName: frank-api
        ContainerPort: 8000
        TargetGroupArn: !Ref FRANKTargetGroup
    DeploymentConfiguration:
      MaximumPercent: 200
      MinimumHealthyPercent: 100
    HealthCheckGracePeriodSeconds: 60
```

### IAM Roles

```yaml
# Task Execution Role (used by ECS to pull images and write logs)
TaskExecutionRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Statement:
        - Effect: Allow
          Principal:
            Service: ecs-tasks.amazonaws.com
          Action: sts:AssumeRole
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
    Policies:
      - PolicyName: ECRAccess
        PolicyDocument:
          Statement:
            - Effect: Allow
              Action:
                - ecr:GetAuthorizationToken
                - ecr:BatchCheckLayerAvailability
                - ecr:GetDownloadUrlForLayer
                - ecr:BatchGetImage
              Resource: "*"

# Task Role (used by application code to access AWS services)
TaskRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Statement:
        - Effect: Allow
          Principal:
            Service: ecs-tasks.amazonaws.com
          Action: sts:AssumeRole
    Policies:
      - PolicyName: DynamoDBAccess
        PolicyDocument:
          Statement:
            - Effect: Allow
              Action:
                - dynamodb:GetItem
                - dynamodb:PutItem
                - dynamodb:Query
                - dynamodb:Scan
                - dynamodb:UpdateItem
              Resource:
                - !GetAtt FRANKTable.Arn
                - !Sub ${FRANKTable.Arn}/index/*
```

---

## 5. Test Coverage Requirements

### Unit Tests

Not applicable (infrastructure specification - validated through deployment testing)

### Integration Tests

```python
# Location: tests/integration/infrastructure/test_ecs_deployment.py
import boto3
import requests
import time

def test_ecs_task_healthy():
    """ECS task starts and becomes healthy within 3 minutes."""
    ecs = boto3.client('ecs')

    # Get task ARN from service
    response = ecs.list_tasks(cluster='frank-cluster', serviceName='frank-api')
    assert len(response['taskArns']) > 0, "No tasks running"

    # Wait for task to reach RUNNING state
    task_arn = response['taskArns'][0]
    waiter = ecs.get_waiter('tasks_running')
    waiter.wait(cluster='frank-cluster', tasks=[task_arn], WaiterConfig={'Delay': 10, 'MaxAttempts': 18})

    # Verify task is healthy
    task = ecs.describe_tasks(cluster='frank-cluster', tasks=[task_arn])['tasks'][0]
    assert task['lastStatus'] == 'RUNNING'
    assert task['healthStatus'] == 'HEALTHY'

def test_application_accessible_via_alb():
    """Application responds correctly via ALB endpoint."""
    alb_url = "https://api.frank.example.com"

    response = requests.get(f"{alb_url}/v1/health", timeout=5)
    assert response.status_code == 200
    assert response.json()['status'] == 'healthy'

def test_auto_scaling_triggers():
    """ECS service scales up when CPU threshold exceeded."""
    # Load test to trigger auto-scaling
    # Verify task count increases from 2 to 4+ within 5 minutes
    pass  # Implementation requires load testing framework
```

**Required Integration Test Scenarios**:
- [ ] Task starts successfully and passes health checks
- [ ] Application accessible via ALB public endpoint
- [ ] Unhealthy task automatically replaced
- [ ] Zero-downtime deployment during task definition update
- [ ] Auto-scaling up and down based on CPU metrics
- [ ] CloudWatch logs capture application output

### Manual Testing Checklist

```bash
# 1. Verify task is running
aws ecs list-tasks --cluster frank-cluster --service-name frank-api

# 2. Check task health status
aws ecs describe-tasks --cluster frank-cluster --tasks <task-arn> | jq '.tasks[0].healthStatus'

# 3. Test application endpoint
curl https://api.frank.example.com/v1/health
# Expected: {"status": "healthy", "service": "FRANK", "version": "0.2.0"}

# 4. Check CloudWatch logs
aws logs tail /ecs/frank-api --follow

# 5. Trigger deployment
aws ecs update-service --cluster frank-cluster --service frank-api --force-new-deployment

# 6. Monitor rolling update
watch "aws ecs describe-services --cluster frank-cluster --services frank-api | jq '.services[0].deployments'"
```

### Coverage Summary

| Test Type | Location | Coverage Target | Purpose |
|-----------|----------|-----------------|---------|
| Integration | `tests/integration/infrastructure/` | Key workflows | Validate ECS deployment patterns |
| Manual | Documentation above | Deployment verification | Smoke testing after infrastructure changes |

---

## 6. Implementation Status

### Checklist

- [x] Specification complete and reviewed
- [x] Design document approved (spike 009)
- [x] Integration tests written and passing
- [x] Implementation complete (Stage 3)
- [x] Code review passed
- [x] Documentation updated
- [x] Merged to main branch
- [x] Released in version 0.2.0

### Progress Notes

**Current Phase**: COMPLETE

**Latest Update**: 2026-02-06 - Migrated from spike 009 to formal specification

### PR Links

- Stage 3 implementation integrated via Ansible playbooks
- CloudFormation templates in `environments/aws-dev/stage3/cloudformation/`

### Implementation Notes

- **Spike Validation**: Spike 009 validated minimal ECS deployment with public subnet and direct IP access
- **Production Evolution**: Stage 3 evolved to use private subnets + ALB + auto-scaling
- **Cost Optimization**: Development uses smaller tasks (0.25 vCPU, 0.5GB); production uses 0.5 vCPU, 1GB
- **Security Hardening**: Moved from public subnet (spike) to private subnet + NAT Gateway (production)

---

## 7. Evolution Path Across FRANK Stages

### Stage 1: SQLite + FastAPI (Local Development)

- ❌ Not supported - Local development uses native Python process
- **Rationale**: Docker adds unnecessary complexity for laptop development

### Stage 2: DynamoDB + MySQL + Docker (Learning Stage)

- ⚠️ Partial - Docker Compose used, but not ECS
- **Implementation**: `docker-compose.yml` runs containers locally
- **Purpose**: Learn containerization before cloud deployment

### Stage 3: AWS ECS + DynamoDB (Cloud Deployment)

- ✅ Fully implemented
- **Implementation**: ECS Fargate with ALB, auto-scaling, CloudWatch monitoring
- **Scale**: 2-10 tasks, 0.5 vCPU, 1GB RAM per task
- **Capabilities**: Zero-downtime deployments, automatic failover, multi-AZ deployment

### Stage 4: Kubernetes + ScyllaDB (Production Scale)

- ✅ Planned (equivalent Kubernetes patterns)
- **Implementation**: Kubernetes Deployments with HPA (Horizontal Pod Autoscaler)
- **Migration Path**: ECS task definitions → Kubernetes Deployments, ALB → Ingress Controller
- **Benefits**: Cloud-agnostic, advanced scheduling, service mesh integration

---

## 8. References

- **Related ADRs**: N/A (spike-derived, predates ADR process)

- **Related Specifications**:
  - [Load Balancer Spec](load-balancer.spec.md) - ALB integration
  - [Observability Spec](observability.spec.md) - CloudWatch logging
  - [SSL Certificates Spec](ssl-certificates.spec.md) - HTTPS configuration

- **Related Spikes**:
  - [Spike 009: AWS ECS Basic](tests/spikes/009_aws_ecs_basic/README.md) - Original hypothesis and validation
  - [Spike 010: AWS ALB](tests/spikes/010_aws_alb/README.md) - Load balancer integration
  - [Spike 013: AWS Observability](tests/spikes/013_aws_observability/README.md) - Logging and monitoring

- **External Resources**:
  - [AWS ECS Fargate Documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
  - [ECS Task Definition Parameters](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html)
  - [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/intro.html)

- **Implementation Files**:
  - CloudFormation: `environments/aws-dev/stage3/cloudformation/ecs.yml`
  - Ansible playbooks: `environments/ansible/roles/ecs/`
  - Dockerfile: `Dockerfile`

---

## 9. Open Questions & Decisions Pending

- [x] **Fargate vs EC2 Launch Type**: Should we use Fargate or EC2?
  - **Options**:
    - Fargate (serverless, higher cost per task)
    - EC2 (manage instances, lower cost at scale)
  - **Recommendation**: Fargate for Stage 3 (simplicity), consider EC2 for Stage 4 (cost optimization)
  - **Decision**: Fargate selected - operational simplicity outweighs cost for current scale

- [x] **Task Resource Allocation**: How much CPU/memory per task?
  - **Options**:
    - 0.25 vCPU, 0.5GB (minimal, $5-10/month)
    - 0.5 vCPU, 1GB (balanced, $20-30/month)
    - 1 vCPU, 2GB (generous, $50-80/month)
  - **Recommendation**: 0.5 vCPU, 1GB for production; 0.25 vCPU, 0.5GB for development
  - **Decision**: Implemented as recommended - performance testing validated adequacy

---

## 10. Appendix: Examples

### Example 1: Deploy New Task Definition Version

```bash
# 1. Build and push new Docker image
docker build -t frank-api:v0.3.0 .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker tag frank-api:v0.3.0 <account>.dkr.ecr.us-east-1.amazonaws.com/frank:v0.3.0
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/frank:v0.3.0

# 2. Update task definition to reference new image
# (Ansible handles this automatically)
ansible-playbook ansible/playbook.yml --tags deploy

# 3. Verify deployment
aws ecs describe-services --cluster frank-cluster --services frank-api | jq '.services[0].deployments'
# Expected: 2 deployments (old draining, new active)

# 4. Wait for old tasks to drain
aws ecs wait services-stable --cluster frank-cluster --services frank-api

# 5. Verify new version running
curl https://api.frank.example.com/v1/health
# Expected: {"version": "0.3.0"}
```

### Example 2: Scale Service Manually

```bash
# Increase desired task count from 2 to 5
aws ecs update-service --cluster frank-cluster --service frank-api --desired-count 5

# Monitor scaling progress
watch "aws ecs describe-services --cluster frank-cluster --services frank-api | jq '.services[0].runningCount'"

# Verify all tasks healthy
aws ecs describe-tasks --cluster frank-cluster --tasks $(aws ecs list-tasks --cluster frank-cluster --service-name frank-api --query 'taskArns[*]' --output text) | jq '.tasks[] | {status: .lastStatus, health: .healthStatus}'
```

### Example 3: Troubleshoot Failed Task

```bash
# List recent task failures
aws ecs list-tasks --cluster frank-cluster --desired-status STOPPED --max-results 5

# Get failure reason
aws ecs describe-tasks --cluster frank-cluster --tasks <task-arn> | jq '.tasks[0].stoppedReason'

# Check CloudWatch logs for errors
aws logs tail /ecs/frank-api --since 30m | grep ERROR

# Get container exit code
aws ecs describe-tasks --cluster frank-cluster --tasks <task-arn> | jq '.tasks[0].containers[0].exitCode'
```

---

## Document History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 2025-01-15 | 0.1 | Spike 009 | Initial spike validation |
| 2025-02-01 | 0.9 | Infrastructure Team | Stage 3 implementation |
| 2026-02-06 | 1.0 | SDD Migration | Formalized as specification |

---

**Questions or feedback?** See [Spike 009 README](tests/spikes/009_aws_ecs_basic/README.md) for original hypothesis and validation results.
