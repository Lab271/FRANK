# FRANK Ansible Deployment

This directory contains Ansible automation for deploying the FRANK AWS infrastructure.

## Structure

```
ansible/
├── playbook.yml                     # Main deployment playbook
├── requirements.yml                 # Ansible collections requirements
├── templates/
│   └── frank-009-stage5-infra.yaml  # CloudFormation infrastructure template
└── tasks/
    ├── prerequisites.yml            # Check prerequisites and setup
    ├── ssl.yml                      # SSL certificate management
    ├── docker_build.yml             # Docker build and push to ECR
    ├── docker_deploy.yml            # Docker deployment operations
    ├── cloudformation.yml           # CloudFormation deployment
    └── cleanup.yml                  # Resource cleanup
```

## Prerequisites

1. **Install Ansible**:
   ```bash
   pip install ansible
   ```

2. **Install required collections**:
   ```bash
   ansible-galaxy collection install -r requirements.yml
   ```

3. **AWS CLI configured** with profiles:
   - `spike-account`: For the deployment account
   - `main-account` (or your main account): For SSL certificates

4. **Docker** installed and running

## Usage

### Deploy Infrastructure

```bash
# Create new stack (or update if exists)
ansible-playbook playbook.yml --tags "create"

# Update existing stack
ansible-playbook playbook.yml --tags "update"

# Deploy (smart create/update)
ansible-playbook playbook.yml --tags "deploy"

# Delete stack
ansible-playbook playbook.yml --tags "delete"

# Run only Docker operations
ansible-playbook playbook.yml --tags "docker"

# Run only DynamoDB table creation
ansible-playbook playbook.yml --tags "dynamodb"

# Run only SSL setup
ansible-playbook playbook.yml --tags "ssl"

# Run only CloudFormation deployment
ansible-playbook playbook.yml --tags "cloudformation"

# Run cleanup operations
ansible-playbook playbook.yml --tags "cleanup"
```

### Tag Combinations

You can combine multiple tags:

```bash
# Run SSL setup and Docker operations only
ansible-playbook playbook.yml --tags "ssl,docker"

# Run database and infrastructure deployment
ansible-playbook playbook.yml --tags "dynamodb,cloudformation"

# Run full deployment pipeline
ansible-playbook playbook.yml --tags "ssl,docker,dynamodb,cloudformation"
```

### Custom Configuration

You can override default variables while using tags:

```bash
ansible-playbook playbook.yml --tags "deploy" \
  -e stack_name=my-frank-stack \
  -e aws_region=us-west-2 \
  -e image_tag=v1.2.3 \
  -e ssl_domain=my-domain.com
```

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
ORG#123           | ORG              | TIER#partner    | 2025-01-01  | Organisation
SUB#456           | SUB              | ORG#123         | 2025-01-01  | Submission  
OBS#hash789       | SUB#456          | TYPE#ipv4       | 2025-01-01  | Observable
SIGHT#abc         | SUB#456          | ORG#123         | 2025-01-01  | Sighting
STAT#hash789      | STAT#ipv4        | FREQ#daily      | 2025-01-01  | Statistics
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
LOG#123           | LOG#timestamp    | ACTION#query    | 2025-01-01  | AccessLog
AUDIT#456         | AUDIT#timestamp  | EVENT#create    | 2025-01-01  | AuditEvent
METRIC#789        | METRIC#daily     | TYPE#usage      | 2025-01-01  | Metrics
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

1. **Prerequisites** - Environment validation
2. **SSL Certificate** - Domain certificate lookup
3. **Docker** - Container build and push to ECR
4. **DynamoDB Tables** - Database infrastructure ← **New in Stage 4**
5. **CloudFormation** - ECS service and load balancer
6. **Cleanup** - Resource cleanup (when using delete tags)

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `stack_name` | `frank-009-stage4` | CloudFormation stack name |
| `aws_region` | `eu-central-1` | AWS region |
| `aws_profile` | `spike-account` | AWS profile for deployment |
| `main_account_profile` | `main-account` | AWS profile for SSL certificates |
| `app_name` | `simple_api` | Application name for ECR repository |
| `image_tag` | `latest` | Docker image tag |
| `ssl_domain` | `frank-009-stage4.lab271.io` | Domain for SSL certificate |

## Tags

| Tag | Description | Tasks Included |
|-----|-------------|----------------|
| `always` | Always runs | Prerequisites, Display info |
| `create` | Create deployment | SSL, Docker, DynamoDB, CloudFormation |
| `update` | Update deployment | SSL, Docker, DynamoDB, CloudFormation |
| `deploy` | Smart create/update | SSL, Docker, DynamoDB, CloudFormation |
| `ssl` | SSL operations only | SSL certificate lookup |
| `docker` | Docker operations only | ECR, Build, Push |
| `dynamodb` | Database operations only | DynamoDB table creation |
| `database` | Database operations only | DynamoDB table creation (alias) |
| `delete` | Delete resources | Cleanup operations |
| `cleanup` | Cleanup operations | Delete stack and ECR |

## Features

- **Idempotent**: Safe to run multiple times
- **Error Handling**: Comprehensive error checking and validation
- **SSL Support**: Automatic SSL certificate lookup and configuration
- **Cleanup**: Complete resource cleanup with delete action

## Troubleshooting

1. **AWS Credentials**: Ensure your AWS profiles are configured correctly
2. **Docker**: Make sure Docker is running and buildx is available
3. **SSL**: SSL certificate must exist in the main account (us-east-1)
4. **Permissions**: Ensure AWS credentials have necessary permissions for ECS, ECR, CloudFormation, etc.