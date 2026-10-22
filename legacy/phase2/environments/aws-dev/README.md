# AWS Development Environment

Deploy FRANK Stage 3 to AWS development account for cloud testing and experimentation.

## Overview

- **Environment**: `aws-dev`
- **AWS Account**: Development/Spike account
- **Deployment**: ECS Fargate, DynamoDB, RDS PostgreSQL
- **Best for**: Cloud testing, learning AWS, integration validation

## Prerequisites

- AWS CLI configured with `spike-account` profile
- Ansible installed (for deployment automation)
- Terraform installed (alternative deployment method - future)
- Docker (for building images)
- Appropriate AWS permissions

## Quick Start

### 1. Configure AWS Profile

```bash
# Check AWS configuration
aws configure list --profile spike-account

# Or login with SSO
aws sso login --profile spike-account

# Verify access
aws sts get-caller-identity --profile spike-account
```

### 2. Configure Environment

```bash
cd stage3
cp .env.stage3.example .env.stage3

# Edit with your AWS-specific settings
vi .env.stage3
```

### 3. Deploy to AWS

```bash
cd stage3
make deploy

# Or with Ansible directly
ansible-playbook ansible/playbook.yml --tags create
```

## Directory Structure

```
aws-dev/
├── stage3/
│   ├── ansible/
│   │   ├── playbook.yml          # Main deployment playbook
│   │   ├── inventory/            # AWS inventory
│   │   ├── roles/                # Deployment roles
│   │   └── vars/                 # Variables
│   ├── terraform/                # Future: Terraform alternative
│   ├── .env.stage3               # Environment config
│   └── .env.stage3.example       # Template
└── README.md (this file)
```

## Environment Variables

```bash
# Environment identifier
FRANK_ENVIRONMENT=aws-dev

# AWS Configuration
AWS_REGION=eu-central-1
AWS_PROFILE=spike-account
AWS_ACCOUNT_ID=<your-account-id>

# Infrastructure
ECS_CLUSTER_NAME=frank-dev
RDS_INSTANCE_NAME=frank-dev-db
DYNAMODB_TABLE_PREFIX=frank-dev

# Cognito
COGNITO_USER_POOL_ID=<pool-id>
COGNITO_CLIENT_ID=<client-id>
```

## Deployment Commands

### Full Deployment

```bash
cd stage3
make deploy

# Or step-by-step
make ssl                  # SSL certificate
make docker-build         # Build and push images
make cloudformation       # Create infrastructure
make deploy-app           # Deploy application
```

### Update Application Only

```bash
make update-app
```

### Destroy Infrastructure

```bash
make destroy

# Or with Ansible
ansible-playbook ansible/playbook.yml --tags destroy
```

## Deployment Tags

Ansible supports selective deployment:

```bash
# SSL certificate only
ansible-playbook ansible/playbook.yml --tags ssl

# Build and push Docker images
ansible-playbook ansible/playbook.yml --tags "build,push"

# Deploy infrastructure
ansible-playbook ansible/playbook.yml --tags cloudformation

# Full deployment
ansible-playbook ansible/playbook.yml --tags create
```

## AWS Resources Created

### Networking
- VPC with public/private subnets (Multi-AZ)
- Internet Gateway
- NAT Gateways (for private subnets)
- Security Groups (zero-trust model)

### Compute
- ECS Fargate Cluster
- ECS Services (Management API, Web GUI, Sightings API)
- Application Load Balancer
- Auto Scaling (2-10 tasks based on CPU/memory/requests)

### Database
- DynamoDB table (submissions, sightings)
- RDS PostgreSQL (management data)
- DynamoDB audit table (with TTL)

### Authentication
- Cognito User Pool
- Cognito App Client
- Cognito Groups (FRANK_OBSERVER, FRANK_CONTRIBUTOR, etc.)

### Monitoring
- CloudWatch Logs
- CloudWatch Metrics
- CloudWatch Alarms

## Access Points

After deployment:

```bash
# Get ALB DNS name
aws elbv2 describe-load-balancers \
  --profile spike-account \
  --region eu-central-1 \
  --query 'LoadBalancers[?contains(LoadBalancerName, `frank`)].DNSName'

# Access services
# Web GUI: https://<alb-dns>/
# Management API: https://<alb-dns>/api/docs
```

## Monitoring

### CloudWatch Logs

```bash
# View logs
aws logs tail /aws/ecs/frank-dev-management-api --follow --profile spike-account
aws logs tail /aws/ecs/frank-dev-web-gui --follow --profile spike-account
```

### Metrics

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster frank-dev \
  --services frank-dev-management-api \
  --profile spike-account
```

## Cost Estimation

AWS Dev environment (estimated monthly):
- **ECS Fargate**: $20-50 (depends on task count)
- **RDS PostgreSQL**: $15-30 (db.t3.micro)
- **DynamoDB**: $5-20 (on-demand pricing)
- **Data Transfer**: $5-10
- **ALB**: $16-20 (fixed cost)

**Total: ~$60-130/month**

## Troubleshooting

### Deployment fails

```bash
# Check CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name frank-dev \
  --profile spike-account \
  --region eu-central-1

# View stack status
aws cloudformation describe-stacks \
  --stack-name frank-dev \
  --profile spike-account
```

### ECS tasks won't start

```bash
# Check task failures
aws ecs describe-tasks \
  --cluster frank-dev \
  --tasks <task-arn> \
  --profile spike-account

# View logs
aws logs get-log-events \
  --log-group-name /aws/ecs/frank-dev-management-api \
  --log-stream-name <stream-name> \
  --profile spike-account
```

## Security

- ✅ TLS/HTTPS enforced via ALB
- ✅ Security groups restrict access
- ✅ Secrets in AWS Secrets Manager
- ✅ IAM roles for ECS tasks
- ✅ VPC with private subnets
- ✅ CloudTrail logging enabled

## Related

- **Local testing**: `environments/local-docker/` - Test before deploying
- **Staging**: `environments/aws-preprod/` - Pre-production validation
- **Production**: `environments/aws-prod/` - Live environment
- **Documentation**: `docs/environments.md` - Comprehensive guide
