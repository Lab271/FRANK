# FRANK AWS Deployment Spike

## Status
ABANDONED

## Integrated Into
- Superseded by Ansible-based deployment (see 009-013 AWS spikes)

---

https://saml-doc.okta.com/SAML_Docs/How-to-Configure-SAML-2.0-for-Amazon-Web-Service.html?baseAdminUrl=https://sbplabs-admin.okta-emea.com&app=amazon_aws&instanceId=0oaf6yvlks5CemF4J0i7#A-step1

## Overview

This spike demonstrates **Stage 3** of the FRANK (Feedback Infrastructure for Cyber Risk Analysis and Network Knowledge sharing) platform deployment: migrating from LocalStack/Docker (Stage 2) to production AWS infrastructure using ECS and real cloud services.

FRANK is a threat intelligence sharing platform developed by Schuberg Philis that enables organizations to collaboratively share and analyze cybersecurity threat data. This Stage 3 spike focuses on establishing production AWS deployment patterns while maintaining the DynamoDB database architecture established in Stage 2.

## What This Spike Achieves

### 🎯 **Primary Goals**
- **Stage 3 Implementation**: Deploy FRANK from LocalStack (Stage 2) to real AWS cloud infrastructure
- **Cloud Migration**: Bridge from containerized local development to AWS ECS deployment
- **Authentication Readiness**: Prepare infrastructure for AWS Cognito integration
- **Production Patterns**: Establish scalable AWS patterns that can evolve to Stage 4 Kubernetes

### 🏗️ **Infrastructure Components**
- **VPC**: Multi-AZ network with public subnets across eu-west-1a and eu-west-1b
- **ECS Fargate**: Serverless container platform for the FastAPI application
- **Application Load Balancer**: Internet-facing load balancer with health checks
- **ECR**: Private container registry for FRANK application images
- **DynamoDB**: NoSQL database (carried forward from Stage 2)
- **CloudWatch**: Centralized logging and monitoring
- **Cognito Ready**: Infrastructure prepared for AWS Cognito authentication

### 🚀 **Application Features**
- **FastAPI Server**: Full FRANK Stage 2 application with DynamoDB integration
- **Threat Intelligence API**: Complete submission and sighting endpoints
- **Health Monitoring**: Health check endpoint at `/health` for load balancer integration
- **Authentication Framework**: Ready for Cognito JWT integration (currently mock JWT)

## Architecture

```
Internet
    ↓
Application Load Balancer (HTTP:80)
    ↓
Target Group (/health checks)
    ↓
ECS Service (Fargate)
    ↓
FRANK Container (FastAPI:8000)
    ↓                    ↓
DynamoDB        CloudWatch Logs
(Threat Intel)    (Monitoring)
```

**Network Design:**
- VPC: `10.0.0.0/16`
- Public Subnet 1: `10.0.1.0/24` (eu-west-1a)
- Public Subnet 2: `10.0.2.0/24` (eu-west-1b)

## Why This Spike Matters

### 🎓 **Learning Objectives**
1. **Stage 2 → Stage 3 Migration**: Moving from LocalStack to real AWS services
2. **DynamoDB in Production**: Operating NoSQL database in cloud environment
3. **ECS Container Orchestration**: Production-grade container deployment
4. **Authentication Preparation**: Infrastructure setup for Cognito integration
5. **Infrastructure as Code**: Advanced OpenTofu patterns for complex deployments

### 🔄 **FRANK Stage Progression Context**
This spike represents **Stage 3** in FRANK's updated 4-stage development approach:

| Stage | Database | Compute | Location | Auth | Functional Scope | Purpose |
|-------|----------|---------|----------|------|------------------|---------|
| 1     | SQLite   | FastAPI | Local      | Mock JWT | **Minimal submissions** | Current foundation |
| 2     | DynamoDB | FastAPI | Docker/LocalStack | Mock JWT | **Submissions** | NoSQL/Containerization |
| **3** | **DynamoDB** | **FastAPI** | **ECS/AWS**  | **Cognito** | **Full scope calls** | **Cloud deployment** ← *This spike* |
| 4     | ScyllaDB | FastAPI | Kubernetes | Supertokens | **Extensive statistics** | Agnostic stack |

### 🎯 **Production Readiness**
While this represents Stage 3, it includes patterns that scale to Stage 4:
- Multi-AZ deployment for high availability
- Database abstraction ready for ScyllaDB migration
- Container patterns that translate to Kubernetes
- Authentication framework expandable to Supertokens
- Monitoring and logging for extensive statistics collection

## Quick Start

### Prerequisites
- AWS CLI configured with appropriate permissions
- Docker installed and running
- OpenTofu installed
- FRANK application code (Stage 2 FastAPI implementation)

### Deployment

1. **Clone and navigate to spike directory**
   ```bash
   git clone <frank-repo>
   cd tests/spikes/008_aws
   ```

2. **Deploy infrastructure and application**
   ```bash
   # Make deployment script executable
   chmod +x deploy.sh
   
   # Full deployment
   ./deploy.sh
   ```

3. **Access your application**
   - The deployment will output the application URL
   - Example: `http://frank-spike-alb-1234567890.eu-west-1.elb.amazonaws.com`

### Testing Endpoints

```bash
# Health check
curl http://your-alb-url/health

# API documentation
curl http://your-alb-url/docs
```

## Project Structure

```
infrastructure/aws-spike/
├── main.tf              # OpenTofu infrastructure configuration
├── Dockerfile           # Container image definition  
├── deploy.sh           # Deployment automation script
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Configuration Options

### Minimal vs Full-Featured

**Current Configuration (Minimal)**:
- HTTP only (no SSL)
- Uses ALB DNS name
- Basic monitoring
- Single container instance

**Possible Enhancements**:
- SSL certificate with custom domain
- Auto-scaling based on load
- Database integration (RDS/DynamoDB)
- Enhanced monitoring and alerting
- Multi-environment support

### Customization

Key values can be modified in `main.tf`:

```hcl
# Resource sizing
cpu    = 256    # Container CPU units
memory = 512    # Container memory (MB)

# Networking
vpc_cidr = "10.0.0.0/16"
public_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]

# Application
container_port = 8000
```

## Monitoring and Troubleshooting

### CloudWatch Logs
```bash
# View application logs
aws logs tail /ecs/frank-spike --follow --region eu-west-1
```

### ECS Service Status
```bash
# Check service health
aws ecs describe-services \
  --cluster frank-spike-cluster \
  --services frank-spike-service \
  --region eu-west-1
```

### Load Balancer Health
```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups \
    --names frank-spike-tg \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text \
    --region eu-west-1) \
  --region eu-west-1
```

## Cost Considerations

### Estimated Monthly Costs (eu-west-1)
- **ECS Fargate**: ~$15-25 (single instance, 256 CPU, 512MB RAM)
- **Application Load Balancer**: ~$16 + data transfer
- **ECR**: <$1 (minimal image storage)
- **CloudWatch Logs**: <$5 (basic logging)
- **Data Transfer**: Variable based on usage

**Total**: ~$35-50/month for basic spike deployment

### Cost Optimization Tips
- Use smaller instance sizes for development
- Implement auto-scaling to scale to zero during off-hours
- Set up log retention policies
- Clean up unused ECR images

## Security Considerations

### Current Security Measures
- **VPC Isolation**: Application runs in isolated network
- **Security Groups**: Least privilege network access
- **Container Security**: Non-root user execution
- **ECR**: Private container registry

### Production Security Enhancements
- Enable AWS WAF for web application firewall
- Implement SSL/TLS encryption
- Add AWS Secrets Manager for sensitive configuration
- Enable VPC Flow Logs for network monitoring
- Implement AWS Config for compliance monitoring

## Next Steps

### Immediate Stage 3 Enhancements
1. **AWS Cognito Integration**: Replace mock JWT with real Cognito authentication
2. **DynamoDB Production Config**: Optimize table design and access patterns  
3. **SSL Certificate**: Add HTTPS support with ACM for security
4. **Full Scope Implementation**: Complete all FRANK API endpoints

### Stage 4 Preparation (Kubernetes Migration)
1. **Container Orchestration**: Translate ECS patterns to Kubernetes
2. **Database Migration**: Plan ScyllaDB integration and migration strategy
3. **Authentication Upgrade**: Evaluate Supertokens integration
4. **Statistics Framework**: Design extensive analytics and reporting
5. **Multi-cloud Strategy**: Platform-agnostic deployment patterns

### Production Evolution
- **Blue/Green Deployments**: Zero-downtime deployment strategies
- **Service Mesh**: Advanced microservice communication patterns
- **Observability**: Enhanced monitoring with distributed tracing
- **Global Scale**: Multi-region deployment for worldwide availability

## Troubleshooting

### Common Issues

**Container Won't Start**
```bash
# Check ECS logs
aws logs tail /ecs/frank-spike --follow

# Check task definition
aws ecs describe-tasks --cluster frank-spike-cluster --tasks <task-arn>
```

**Health Check Failures**
- Verify `/health` endpoint returns HTTP 200
- Check security group allows ALB → ECS communication on port 8000
- Ensure container starts within health check grace period

**Deployment Failures**
- Verify AWS credentials and permissions
- Check ECR repository access
- Validate OpenTofu syntax with `tofu validate`

## Cleanup

To avoid ongoing costs, destroy the infrastructure when done:

```bash
# Destroy all resources
tofu destroy -auto-approve

# Or use the deployment script
./deploy.sh destroy
```

## Contributing

This spike is part of the larger FRANK project. For contributions:

1. Test changes in a separate AWS account/region
2. Validate infrastructure changes don't break existing deployments
3. Update documentation for any configuration changes
4. Follow FRANK project coding standards and security practices

## References

- [FRANK Project Documentation](../docs/implementation_plan.md)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [OpenTofu Documentation](https://opentofu.org/docs/)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)

---

**Project**: FRANK (Feedback Infrastructure for Cyber Risk Analysis and Network Knowledge sharing)  
**Organization**: Schuberg Philis B.V.  
**License**: Apache 2.0  
**Stage**: Infrastructure Spike for Production Deployment