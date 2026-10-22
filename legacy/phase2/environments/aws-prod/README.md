# AWS Production Environment

Deploy FRANK Stage 3 to AWS production environment for live customer-facing service.

## Overview

- **Environment**: `aws-prod`
- **AWS Account**: Dedicated production account
- **Deployment**: ECS Fargate, DynamoDB, RDS PostgreSQL (Multi-AZ)
- **Best for**: Live customer service, production data

## ⚠️ Production Warnings

- **NO DIRECT CHANGES**: All changes must go through pre-prod first
- **BACKUPS REQUIRED**: Database backups before any deployment
- **CHANGE WINDOW**: Deployments only during approved maintenance windows
- **ROLLBACK PLAN**: Must have documented rollback procedure
- **APPROVAL REQUIRED**: Requires sign-off from operations lead

## Prerequisites

- AWS CLI configured with production profile
- Multi-factor authentication (MFA) enabled
- Production deployment permissions
- Approved change request
- Completed pre-prod validation

## Environment Variables

```bash
# Environment identifier
FRANK_ENVIRONMENT=aws-prod

# AWS Configuration
AWS_REGION=eu-central-1
AWS_PROFILE=frank-prod
AWS_ACCOUNT_ID=<prod-account-id>

# Infrastructure
ECS_CLUSTER_NAME=frank-prod
RDS_INSTANCE_NAME=frank-prod-db
DYNAMODB_TABLE_PREFIX=frank-prod

# Cognito
COGNITO_USER_POOL_ID=<prod-pool-id>
COGNITO_CLIENT_ID=<prod-client-id>

# Scaling (production capacity)
ECS_MIN_TASKS=2
ECS_MAX_TASKS=10
ECS_DESIRED_TASKS=3

# High Availability
RDS_MULTI_AZ=true
RDS_BACKUP_RETENTION=30
DYNAMODB_PITR=true  # Point-in-time recovery
```

## Deployment Process

### Pre-Deployment Checklist

- [ ] **Pre-prod validation** completed successfully
- [ ] **Change request** approved (with CR number)
- [ ] **Backup created** (database, configurations)
- [ ] **Rollback plan** documented and tested
- [ ] **Team notified** (operations, support, stakeholders)
- [ ] **Monitoring** ready (dashboards, alerts configured)
- [ ] **Maintenance window** scheduled and communicated

### Deployment

```bash
cd stage3
cp .env.stage3.example .env.stage3
# Edit for production settings
vi .env.stage3

# NEVER run blind deployment
# Always review plan first
make plan

# Deploy during approved maintenance window
make deploy
```

### Post-Deployment Verification

- [ ] **Health checks** passing
- [ ] **Smoke tests** completed
- [ ] **Monitoring** shows normal metrics
- [ ] **Error rate** within acceptable limits
- [ ] **Performance** meets SLAs
- [ ] **Team notified** of successful deployment

## High Availability Configuration

### Multi-AZ Setup

```yaml
# RDS Configuration
MultiAZ: true
BackupRetentionPeriod: 30
PreferredBackupWindow: "03:00-04:00"
PreferredMaintenanceWindow: "sun:04:00-sun:05:00"

# ECS Configuration
MinTasks: 2  # Across multiple AZs
HealthCheckGracePeriod: 60
DesiredCount: 3
```

### Auto Scaling

```yaml
# Scale on metrics
- CPU > 70% → Scale up
- Memory > 80% → Scale up
- Request rate > 1000/min per task → Scale up
- ALB target response time > 1s → Scale up
```

## Disaster Recovery

### Backup Strategy

```bash
# Automated backups
- RDS: Daily snapshots, 30-day retention
- DynamoDB: Point-in-time recovery (35 days)
- Configurations: S3 versioning enabled

# Manual backup before deployment
aws rds create-db-snapshot \
  --db-instance-identifier frank-prod-db \
  --db-snapshot-identifier frank-prod-pre-deploy-$(date +%Y%m%d-%H%M) \
  --profile frank-prod
```

### Rollback Procedure

```bash
# 1. Revert ECS task definition
aws ecs update-service \
  --cluster frank-prod \
  --service frank-prod-management-api \
  --task-definition frank-management-api:<previous-version> \
  --profile frank-prod

# 2. Restore database if needed
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier frank-prod-db-rollback \
  --db-snapshot-identifier <snapshot-id> \
  --profile frank-prod

# 3. Verify rollback
make health-check
```

## Monitoring & Alerts

### Critical Alarms

- **Service Down**: Any ECS task failure
- **High Error Rate**: >5% error rate for 5 minutes
- **High Latency**: p95 latency >1s for 5 minutes
- **Database Issues**: RDS connection failures, replication lag
- **Security**: Unauthorized access attempts, unusual traffic patterns

### Alerting Channels

- **PagerDuty**: Critical alerts (24/7 on-call)
- **Slack**: Warning alerts (#frank-prod-alerts)
- **Email**: Info alerts (operations team)

### Dashboards

CloudWatch dashboards:
- **Overview**: Key metrics at a glance
- **Performance**: Request rate, latency, errors
- **Infrastructure**: CPU, memory, disk, network
- **Database**: Connections, queries, replication
- **Security**: Authentication, authorization, threats

## Security

### Access Control

```bash
# Production access requires:
1. MFA authentication
2. VPN connection
3. Temporary credentials (no permanent keys)
4. Audit logging enabled
5. Least privilege IAM policies
```

### Compliance

- ✅ **Data Encryption**: At rest and in transit
- ✅ **Audit Logging**: CloudTrail, VPC Flow Logs
- ✅ **Secrets Management**: AWS Secrets Manager
- ✅ **Network Isolation**: Private subnets, Security Groups
- ✅ **Regular Audits**: Quarterly security reviews
- ✅ **Incident Response**: Documented procedures

### Security Scanning

```bash
# Pre-deployment security checks
- Container image scanning (ECR)
- Dependency vulnerability scanning
- Infrastructure compliance (AWS Config)
- OWASP Top 10 validation
```

## Performance SLAs

### Service Level Objectives

| Metric | Target | Threshold |
|--------|--------|-----------|
| **Availability** | 99.9% | 99.5% |
| **Latency (p95)** | <500ms | <1s |
| **Error Rate** | <1% | <5% |
| **Response Time** | <200ms (p50) | <500ms |

### Performance Monitoring

```bash
# Key metrics tracked
- Request throughput (requests/sec)
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx)
- Database query time
- Cache hit rate
```

## Cost Management

Estimated monthly cost: **$150-300**

### Cost Breakdown

- **ECS Fargate**: $80-120 (3-10 tasks)
- **RDS PostgreSQL**: $50-80 (db.t3.medium, Multi-AZ)
- **DynamoDB**: $20-50 (on-demand + PITR)
- **Data Transfer**: $10-20
- **ALB**: $20-25 (Multi-AZ)
- **Monitoring/Logs**: $5-10

### Cost Optimization

- Right-size resources based on actual usage
- Use Reserved Instances for predictable workloads
- Enable S3 lifecycle policies for log retention
- Review CloudWatch metrics for unused resources

## Operational Procedures

### Daily Operations

```bash
# Morning health check
make health-check

# Review overnight metrics
aws cloudwatch get-metric-statistics ...

# Check error logs
aws logs tail /aws/ecs/frank-prod-management-api --since 24h
```

### Weekly Operations

- Review performance metrics
- Check cost reports
- Security log review
- Backup verification
- Capacity planning review

### Monthly Operations

- Security patch review and deployment
- Disaster recovery drill
- Cost optimization review
- Performance trending analysis
- Access review (remove unused accounts)

## Incident Response

### Severity Levels

- **SEV-1** (Critical): Service down, data loss
- **SEV-2** (High): Degraded performance, partial outage
- **SEV-3** (Medium): Minor issues, workaround available
- **SEV-4** (Low): Cosmetic, no user impact

### Incident Procedure

1. **Detect**: Monitoring alerts trigger
2. **Assess**: Determine severity and impact
3. **Notify**: Page on-call, notify stakeholders
4. **Mitigate**: Immediate actions to restore service
5. **Resolve**: Fix root cause
6. **Document**: Incident report and postmortem

## Related

- **Pre-production**: `environments/aws-preprod/` - Test before prod deployment
- **Development**: `environments/aws-dev/` - Development testing
- **Local**: `environments/local-docker/` - Local validation
- **Documentation**: `docs/environments.md` - Comprehensive guide
- **Runbooks**: `docs/runbooks/` - Operational procedures
