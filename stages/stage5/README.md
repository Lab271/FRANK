# FRANK Development Configuration

This directory contains comprehensive configuration documentation and deployment scripts for all AWS components in the FRANK platform.

## Directory Structure

```
development/
├── README.md                           # This file
├── 01-cognito/                         # Authentication & Authorization
│   ├── cognito-configuration.md        # Detailed configuration guide
│   ├── cognito-template.yaml          # CloudFormation template
│   └── setup-cognito.sh               # Setup script
├── 02-kms/                            # Key Management Service
│   ├── kms-configuration.md           # KMS keys and policies
│   └── kms-template.yaml              # CloudFormation template
├── 03-s3/                             # Simple Storage Service
│   ├── s3-configuration.md            # S3 buckets and lifecycle
│   └── s3-template.yaml               # CloudFormation template
├── 04-dynamodb/                       # NoSQL Database
│   ├── dynamodb-configuration.md      # Table design and access patterns
│   └── dynamodb-template.yaml         # CloudFormation template
├── 05-lambda/                         # Serverless Functions
│   ├── lambda-configuration.md        # Function configuration
│   └── generate-lambda-config.py      # Template generator
├── 06-api-gateway/                    # REST API
│   └── api-gateway-configuration.md   # API configuration
├── 07-opensearch/                     # Search and Analytics
│   ├── opensearch-configuration.md    # OpenSearch domain and index configuration
│   ├── opensearch-template.yaml       # CloudFormation template
│   ├── setup-opensearch.sh           # Configuration script
│   └── templates/                     # Index templates
│       ├── sightings-template.json    # Sightings data mapping
│       └── indicators-template.json   # Indicators data mapping
├── 08-step-functions/                 # Workflow Orchestration
│   ├── step-functions-configuration.md # State machine definitions
│   └── stepfunctions-template.yaml    # CloudFormation template
├── 09-ecs/                           # Container Service
│   └── ecs-configuration.md          # ECS cluster and task definitions
├── 10-monitoring/                     # CloudWatch & X-Ray
│   └── monitoring-configuration.md   # CloudWatch dashboards and alarms
└── scripts/                          # Deployment and utility scripts
    ├── deploy-all.sh                 # Master deployment script
    ├── teardown.sh                   # Environment cleanup
    └── validate-config.sh            # Configuration validation
```

## Getting Started

### Prerequisites

1. **AWS CLI**: Version 2.0 or later
   ```bash
   aws --version
   aws configure
   ```

2. **SAM CLI**: For Lambda deployment
   ```bash
   sam --version
   ```

3. **Python**: Version 3.11 for Lambda functions
   ```bash
   python3.11 --version
   ```

4. **Docker**: For building Lambda layers
   ```bash
   docker --version
   ```

### Quick Start

1. **Clone and Navigate**
   ```bash
   cd development/
   ```

2. **Configure Environment**
   ```bash
   export AWS_REGION=eu-west-1
   export ENVIRONMENT=dev
   export PROJECT_NAME=frank
   ```

3. **Deploy Infrastructure** (in order)
   ```bash
   # Deploy KMS keys first
   cd 02-kms/
   aws cloudformation deploy --template-file kms-template.yaml \
     --stack-name frank-kms-dev \
     --parameter-overrides Environment=dev

   # Deploy S3 buckets
   cd ../03-s3/
   aws cloudformation deploy --template-file s3-template.yaml \
     --stack-name frank-s3-dev \
     --parameter-overrides Environment=dev S3KeyArn=<kms-key-arn>

   # Continue with other components...
   ```

## Component Overview

### 1. Cognito (Authentication)
- **Purpose**: User authentication and authorization
- **Key Features**: JWT tokens, multi-tenant support, MFA
- **Dependencies**: None
- **Configuration**: [cognito-configuration.md](01-cognito/cognito-configuration.md)

### 2. KMS (Encryption)
- **Purpose**: Encryption key management
- **Key Features**: Customer-managed keys, automatic rotation
- **Dependencies**: None (deploy first)
- **Configuration**: [kms-configuration.md](02-kms/kms-configuration.md)

### 3. S3 (Storage)
- **Purpose**: Data lake for raw data, artifacts, and exports
- **Key Features**: Lifecycle policies, encryption, event notifications
- **Dependencies**: KMS keys
- **Configuration**: [s3-configuration.md](03-s3/s3-configuration.md)

### 4. DynamoDB (Database)
- **Purpose**: Hot storage for aggregates and metadata
- **Key Features**: Auto-scaling, TTL, Global Secondary Indexes
- **Dependencies**: KMS keys
- **Configuration**: [dynamodb-configuration.md](04-dynamodb/dynamodb-configuration.md)

### 5. Lambda (Compute)
- **Purpose**: Serverless processing functions
- **Key Features**: Event-driven, auto-scaling, observability
- **Dependencies**: All storage services, Cognito
- **Configuration**: [lambda-configuration.md](05-lambda/lambda-configuration.md)

### 6. API Gateway (API)
- **Purpose**: REST API interface
- **Key Features**: Authentication, throttling, validation
- **Dependencies**: Lambda functions, Cognito
- **Configuration**: [api-gateway-configuration.md](06-api-gateway/api-gateway-configuration.md)

## Deployment Order

The components must be deployed in a specific order due to dependencies:

1. **KMS** - Encryption keys (no dependencies)
2. **Cognito** - Authentication (no dependencies)
3. **S3** - Storage buckets (requires KMS)
4. **DynamoDB** - Database tables (requires KMS)
5. **Lambda** - Functions (requires storage services)
6. **API Gateway** - REST API (requires Lambda, Cognito)
7. **OpenSearch** - Search service (requires KMS, VPC)
8. **Step Functions** - Workflows (requires Lambda)
9. **ECS** - Container service (requires VPC)
10. **Monitoring** - CloudWatch dashboards (requires all services)

## Environment Configuration

### Development Environment
- **Purpose**: Local development and testing
- **Settings**: Debug logging, relaxed security, minimal scaling
- **Cost**: Optimized for development

### Test Environment
- **Purpose**: Integration testing and staging
- **Settings**: Production-like configuration with test data
- **Cost**: Moderate resource allocation

### Production Environment
- **Purpose**: Live system
- **Settings**: Full security, monitoring, and scaling
- **Cost**: Optimized for performance and availability

## Security Considerations

### Encryption
- All data encrypted at rest and in transit
- Customer-managed KMS keys with rotation
- Separate keys per service for isolation

### Network Security
- VPC endpoints for service communication
- Security groups with least privilege
- Private subnets for compute resources

### Access Control
- IAM roles with minimal permissions
- Resource-based policies
- Multi-factor authentication

### Monitoring
- CloudTrail for all API calls
- CloudWatch for metrics and logs
- X-Ray for distributed tracing

## Cost Optimization

### Strategies
- **Right-sizing**: Match resources to actual usage
- **Lifecycle Policies**: Automatic data tiering
- **Reserved Capacity**: For predictable workloads
- **Spot Instances**: For non-critical batch processing

### Monitoring
- AWS Budgets with alerts
- Cost Explorer dashboards
- Resource tagging for cost allocation

## Troubleshooting

### Common Issues

1. **Deployment Failures**
   - Check CloudFormation events
   - Verify IAM permissions
   - Validate parameter values

2. **Authentication Issues**
   - Verify Cognito configuration
   - Check JWT token validity
   - Validate user pool settings

3. **Performance Issues**
   - Monitor CloudWatch metrics
   - Check Lambda cold starts
   - Review DynamoDB throttling

### Debugging Tools
- CloudWatch Logs for application logs
- X-Ray for distributed tracing
- VPC Flow Logs for network issues

## Best Practices

### Infrastructure as Code
- Use CloudFormation/SAM templates
- Version control all configurations
- Automated testing of infrastructure

### Configuration Management
- Environment-specific parameters
- Secrets in AWS Secrets Manager
- Configuration validation scripts

### Monitoring and Alerting
- Comprehensive CloudWatch dashboards
- Proactive alerting on key metrics
- Regular health checks

### Security
- Regular security assessments
- Automated compliance checking
- Incident response procedures

## Support and Maintenance

### Regular Tasks
- Monitor costs and usage
- Review security findings
- Update dependencies
- Backup verification

### Documentation
- Keep configurations updated
- Document changes and decisions
- Maintain runbooks for operations

### Contact Information
- **Technical Support**: [Support team contact]
- **Security Issues**: [Security team contact]
- **Emergency Escalation**: [Emergency contact]

## Contributing

### Making Changes
1. Create feature branch
2. Update relevant configuration files
3. Test changes in development environment
4. Update documentation
5. Submit pull request

### Testing
- Validate CloudFormation templates
- Test deployment in clean environment
- Verify functionality end-to-end
- Check security configurations

---

For detailed configuration of specific components, refer to the individual configuration files in each subdirectory.
