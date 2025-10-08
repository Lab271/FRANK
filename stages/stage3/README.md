# FRANK Implementation Plan - Stage 3

## Overview
This stage 3 is part of the 4-stage progressive development approach for FRANK (Feedback Infrastructure for Cyber Risk Analysis and Network Knowledge sharing), evolving from a local SQLite/FastAPI prototype to a scalable Cloud agnostic production system. This stage is all about cloud native deployment away from localstack towards a cloud based production system


**Technology Stack**:
- **Database**: DynamoDB (testing)
- **API**: FastAPI on ECS
- **Auth**: Cognito
- **Location**: Local development with LocalStack / AWS
- **Submissions**: **🚀 MAXIMUM MODEL** (major functional upgrade)

**Key Learning Objectives**:
- IoC on Cloud
- authentication implementation
- autoscaling
- healthchecking

**Implementation Focus**:
- Implement full FRANK submission model with complex observables
- DynamoDB dual-table design with GSIs
- Advanced relationship handling (organisations, threat actors, campaigns)

**Success Criteria**:
- All FastAPI endpoints working in AWS

**Risk Mitigation**:
- Same business logic, different presentation layer
- Database layer unchanged from Stage 2

To run, try:
```bash

....
```

For more details see the [implementation plan](../../docs/implementation_plan.md#Stage-3).
This plan is inspired by [009_aws_stage4](../../tests/spikes/009_aws_stage4/README.md) and [009_aws_stage5](../../tests/spikes/009_aws_stage5/README.md).

# FRANK Ansible Deployment

This directory contains Ansible automation for deploying the FRANK AWS infrastructure.

## Structure

```
ansible/
├── playbook.yml                 # Main deployment playbook
├── requirements.yml             # Ansible collections requirements
├── templates/
│   └── frank-stage3-infra.yaml  # CloudFormation infrastructure template
└── tasks/
    ├── prerequisites.yml        # Check prerequisites and setup
    ├── ssl.yml                  # SSL certificate management
    ├── docker_build.yml         # Docker build and push to ECR
    ├── docker_deploy.yml        # Docker deployment operations
    ├── cloudformation.yml       # CloudFormation deployment
    └── cleanup.yml              # Resource cleanup
```
## Usage

### Deploy Infrastructure

```bash
# Create new stack (or update if exists)
ansible-playbook playbook.yml --tags "create"

# Update existing stack
ansible-playbook playbook.yml --tags "update"

# Remove stack
ansible-playbook playbook.yml --tags "destroy"
```

### Tag Combinations

You can combine multiple tags:

```bash
# Run SSL setup and Docker operations only
ansible-playbook playbook.yml --tags "ssl,docker"

# Run infrastructure and Docker deployment
ansible-playbook playbook.yml --tags "cloudformation,deploy"

# Run full deployment pipeline
ansible-playbook playbook.yml --tags "ssl,build,cloudformation,deploy"
```

### Custom Configuration

You can override default variables while using tags:

```bash
ansible-playbook playbook.yml --tags "create" \
  -e stack_name=my-frank-stack \
  -e aws_region=us-west-2 \
  -e image_tag_override=v1.2.3 \
  -e main_domain=my-domain.com
```
## Tags

These are the ansible playbook tags. Deploy the application to aws using

```bash
$ ansible-playbook ansible/playbook.yml --tags create
```

| Tag | Description | Tasks Included |
|-----|-------------|----------------|
| `requisites` | Prerequisites check | Environment validation and setup |
| `ssl` | SSL operations only | SSL certificate lookup |
| `create` | Create deployment | SSL, Docker (build), CloudFormation, Docker (deploy) |
| `update` | Update deployment | SSL, Docker (build), CloudFormation, Docker (deploy) |
| `docker` | Docker operations | Docker build and Docker deploy |
| `build` | Docker build only | Docker build and push to ECR |
| `cloudformation` | CloudFormation only | Infrastructure deployment |
| `infrastructure` | Infrastructure only | CloudFormation deployment (alias) |
| `deploy` | Docker deploy only | Docker deployment operations |
| `cleanup` | Cleanup operations | Delete stack and ECR |
| `delete` | Delete resources | Cleanup operations (alias) |
| `destroy` | Destroy resources | Cleanup operations (alias) |

## DynamoDB Table Design

Stage 4 introduces persistent data storage with two DynamoDB tables following a single table design pattern.

### Table Structure

Both tables are created with the following characteristics:
- **Billing Mode**: PAY_PER_REQUEST for automatic scaling
- **Encryption**: KMS encryption at rest enabled
- **Schema**: Flexible PK/SK pattern with GSI for alternative access patterns

#### Main Table: `${STACK_NAME}-main-table`

**Purpose**: Primary application data storage (submissions, organizations, observables)

**Schema Pattern**:
```
PK (Partition Key) | SK (Sort Key)    | GSI1PK          | GSI1SK      | Entity Type
ORG#123            | ORG              | TIER#partner    | 2025-01-01  | Organisation
SUB#456            | SUB              | ORG#123         | 2025-01-01  | Submission  
OBS#hash789        | SUB#456          | TYPE#ipv4       | 2025-01-01  | Observable
SIGHT#abc          | SUB#456          | ORG#123         | 2025-01-01  | Sighting
STAT#hash789       | STAT#ipv4        | FREQ#daily      | 2025-01-01  | Statistics
```

**Access Patterns**:
- Get organization by ID: `PK = ORG#{org_id}, SK = ORG`
- Get submissions by organization: `GSI1PK = ORG#{org_id}`
- Get observables by type: `GSI1PK = TYPE#{obs_type}`
- Get sightings by organization: `GSI1PK = ORG#{org_id} AND EntityType = Sighting`

#### Audit Table: `${STACK_NAME}-audit-table`

**Purpose**: Audit logs and compliance tracking with automatic TTL cleanup

**Schema Pattern**:
```
PK (Partition Key) | SK (Sort Key)    | GSI1PK          | GSI1SK      | Entity Type
LOG#123            | LOG#timestamp    | ACTION#query    | 2025-01-01  | AccessLog
AUDIT#456          | AUDIT#timestamp  | EVENT#create    | 2025-01-01  | AuditEvent
METRIC#789         | METRIC#daily     | TYPE#usage      | 2025-01-01  | Metrics
```

**Features**:
- **TTL Enabled**: Automatic cleanup of old audit records via `TTL` attribute
- **Action Indexing**: GSI allows querying by action type and time range
- **Compliance Ready**: Structured logging for security and compliance requirements

### Table Configuration

**Attributes**:
- `PK` (String): Partition key for data distribution
- `SK` (String): Sort key for item organization within partition
- `GSI1PK` (String): Global Secondary Index partition key for alternative queries
- `GSI1SK` (String): Global Secondary Index sort key for time-based sorting

**Features**:
- **DynamoDB Streams**: Enabled on main table for real-time data processing
- **Point-in-time Recovery**: Enabled for both tables for backup protection
- **KMS Encryption**: Server-side encryption for data security
- **Comprehensive Tagging**: Consistent resource tagging for management and cost tracking

### Deployment Order

The deployment follows this sequence to ensure dependencies are met:

#### Ansible Pipeline Order:
1. **Prerequisites** - Environment validation and setup
2. **SSL Certificate** - Domain certificate lookup and validation
3. **Docker** - Container build and push to ECR repository
4. **DynamoDB Tables** - Database infrastructure creation
5. **CloudFormation** - Complete AWS infrastructure deployment
6. **Cleanup** - Resource cleanup (when using delete tags)

#### CloudFormation Resource Creation Order:
The CloudFormation stack creates resources in this optimized order to handle dependencies:

1. **NETWORKING FOUNDATION** - VPC, Subnets, Gateways, Routes
   - Creates isolated network environment with public/private separation
   - Public subnets: ALB accessible from internet (3 AZs for HA)
   - Private subnets: ECS containers isolated from direct internet access

2. **SECURITY GROUPS** - ALB and ECS traffic rules
   - Virtual firewalls controlling traffic flow between components
   - ALB Security Group: Allows HTTP/HTTPS from internet
   - ECS Security Group: Only accepts traffic from ALB (zero-trust networking)

3. **LOAD BALANCER** - ALB, Target Groups, Listeners
   - Internet-facing entry point with SSL termination and health checking
   - Application Load Balancer: Distributes traffic across ECS tasks
   - Target Groups: Health checking and routing configuration

4. **COMPUTE PLATFORM** - ECS Cluster
   - Container orchestration environment for running FRANK application
   - ECS Cluster: Logical grouping of compute resources
   - CloudWatch Log Group: Centralized logging for containers

5. **IAM ROLES** - Task execution and application permissions
   - AWS permissions for ECS tasks and container execution
   - Task Execution Role: ECS service permissions (pull images, write logs)
   - Task Role: Application-level permissions (DynamoDB access for FRANK app)

6. **DATABASE** - DynamoDB tables and VPC endpoint
   - Serverless NoSQL database with private VPC access
   - Main DynamoDB Table: FRANK application data with single-table design
   - Audit Table: Compliance and change tracking with TTL
   - VPC Endpoint: Private connection to DynamoDB (no internet routing)

7. **CONTAINER DEFINITION** - Task Definition with environment
   - FRANK container with environment variables: Database connections, AWS region, application settings
   - Task Definition: Container blueprint with resource allocation and configuration
   - In container health checking, validating live processes

8. **SERVICE DEPLOYMENT** - ECS Service that runs the containers
   - Ensures desired number of containers are running and healthy
   - ECS Service: Maintains container availability and integrates with ALB
   - Load balancer integration: Automatic service discovery and health checks

9. **AUTO SCALING CONFIGURATION** - Dynamic scaling based on CPU, memory, and request metrics
   - Auto scaling for ECS service with configurable min/max capacity (2-10 containers)
   - CPU-based scaling: Target tracking at 70% average CPU utilization
   - Memory-based scaling: Target tracking at 80% average memory utilization
   - Request-based scaling: Target 1000 requests/minute per task via ALB metrics
   - Cooldown periods: 5 minutes scale-out, 5-10 minutes scale-in for stability

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `stack_name` | `frank-stage3` | CloudFormation stack name |
| `aws_region` | `eu-central-1` | AWS region |
| `main_domain` | `lab271.io` | Base domain for SSL certificate |
| `spike_subdomain` | `{{ stack_name }}.{{ main_domain }}` | Full subdomain (frank-stage3.lab271.io) |
| `cloudformation_template` | `{{ stack_name }}-infra.yaml` | CloudFormation template filename |
| `build_context` | `stages/stage3` | Docker build context directory |
| `frank_version` | Auto-detected | FRANK Python package version |
| `image_tag` | `{{ frank_version }}` | Docker image tag (can override with image_tag_override) |


### Generated vars

| Variable | Default | Description |
|----------|---------|-------------|
| `aws_account_id` | Auto-detected | AWS Account ID from STS |
| `ecr_url` | Auto-generated | ECR registry URL |
| `container_image` | Auto-generated | Full ECR image URI |
| `ssl_certificate_arn` | Auto-detected | SSL certificate ARN from ACM |

### For development only

| Variable | Default | Description |
|----------|---------|-------------|
| `aws_profile` | `spike-account` | AWS profile for deployment |
| `main_account_profile` | `main-account` | AWS profile for SSL certificates |


## Networking

The FRANK application uses a secure multi-tier architecture with Application Load Balancer (ALB) handling internet traffic and forwarding to FastAPI containers in private subnets. The ALB provides SSL termination, automatic HTTP-to-HTTPS redirection, and implements zero-trust networking by isolating containers from direct internet access while ensuring high availability across multiple availability zones.

### Traffic Flow

**Port 80 (HTTP) Flow:**
1. ALB redirects HTTP request on port 80 to HTTPS (port 443) with 301 redirect

**Port 443 (HTTPS) Flow:**
1. Internet client connects to ALB on port 443 with SSL/TLS
2. ALB forwards HTTP request to Target Group on port 8000
3. Target Group routes request to healthy ECS Fargate container on port 8000

**Security Controls:**
- ECS Security Group only allows traffic from ALB Security Group on port 8000
- Containers run in private subnets with no direct internet access
- ALB Security Group allows internet traffic only on ports 80 and 443

**Four level Health Checking strategy**
1. **Docker Health Check** - Container-level health verification using `HEALTHCHECK` instruction in Dockerfile, checks basic application responsiveness every 30 seconds with 3 retries and 5-second timeout.
2. **ECS Task Health Check** - Service-level monitoring through ECS task definition health checks, integrated with container orchestration for automatic task replacement on failure.
3. **ALB Target Group Health Check** - Load balancer health verification using `/v1/health` endpoint with optimized settings (15-second intervals, 2 healthy/unhealthy thresholds) for fast traffic routing decisions.
4. **Deep Application Health Check** - Comprehensive monitoring endpoint `/v1/health/deep` that validates all dependencies including DynamoDB connectivity, environment configuration, FRANK model integrity, and performance metrics with detailed status reporting for monitoring systems.

## Features

- **Idempotent**: Safe to run multiple times
- **Error Handling**: Comprehensive error checking and validation
- **SSL Support**: Automatic SSL certificate lookup and configuration
- **Auto scaling**: Fargate CPU basis auto scaling
- **Cleanup**: Complete resource cleanup with delete action

## Troubleshooting

1. **AWS Credentials**: Ensure your AWS profiles are configured correctly
2. **Docker**: Make sure Docker is running and buildx is available
3. **SSL**: SSL certificate must exist in the main account (us-east-1)
4. **Permissions**: Ensure AWS credentials have necessary permissions for ECS, ECR, CloudFormation, etc.