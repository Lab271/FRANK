# AWS Pre-Production Environment

Deploy FRANK Stage 3 to AWS pre-production environment for final validation before production release.

## Overview

- **Environment**: `aws-preprod`
- **AWS Account**: Shared or dedicated pre-prod account
- **Deployment**: ECS Fargate, DynamoDB, RDS PostgreSQL
- **Best for**: Final validation, performance testing, stakeholder demos

## Purpose

Pre-production (staging) environment mirrors production configuration but with:
- Lower resource limits (cost optimization)
- Test data only (no real customer data)
- Relaxed monitoring thresholds
- Deployment testing ground

## Prerequisites

- AWS CLI configured with appropriate profile
- Ansible installed
- Docker for building images
- Deployment permissions for pre-prod account

## Environment Variables

```bash
# Environment identifier
FRANK_ENVIRONMENT=aws-preprod

# AWS Configuration
AWS_REGION=eu-central-1
AWS_PROFILE=frank-preprod
AWS_ACCOUNT_ID=<preprod-account-id>

# Infrastructure
ECS_CLUSTER_NAME=frank-preprod
RDS_INSTANCE_NAME=frank-preprod-db
DYNAMODB_TABLE_PREFIX=frank-preprod

# Cognito
COGNITO_USER_POOL_ID=<preprod-pool-id>
COGNITO_CLIENT_ID=<preprod-client-id>

# Scaling (reduced from production)
ECS_MIN_TASKS=1
ECS_MAX_TASKS=5
```

## Deployment

### Deploy Infrastructure

```bash
cd stage3
cp .env.stage3.example .env.stage3
# Edit for pre-prod settings
vi .env.stage3

make deploy
```

### Update Application

```bash
make update-app
```

## Resource Configuration

### Compared to Production

| Resource | Production | Pre-Production |
|----------|-----------|----------------|
| ECS Tasks | 2-10 | 1-5 |
| RDS Instance | db.t3.medium | db.t3.small |
| DynamoDB Mode | On-Demand | On-Demand (lower usage) |
| ALB | Multi-AZ | Single-AZ optional |

### Cost Optimization

- Scheduled scaling (scale down nights/weekends)
- Smaller RDS instance
- Reduced ECS task count
- Optional: Stop services outside business hours

```bash
# Example: Stop pre-prod overnight
aws ecs update-service \
  --cluster frank-preprod \
  --service frank-preprod-management-api \
  --desired-count 0 \
  --profile frank-preprod
```

## Testing Strategy

### Pre-Production Checklist

Before promoting to production:

- [ ] **Functional Testing**: All features work as expected
- [ ] **Integration Testing**: External services integrate correctly
- [ ] **Performance Testing**: Load testing with production-like data volume
- [ ] **Security Testing**: Vulnerability scanning, penetration testing
- [ ] **Disaster Recovery**: Backup/restore procedures validated
- [ ] **Monitoring**: Alerts and dashboards configured correctly
- [ ] **Documentation**: Deployment runbooks up to date

### Performance Testing

```bash
# Load testing (example with artillery)
artillery quick --count 100 --num 50 https://<preprod-alb>/api/health

# Or use k6, JMeter, Gatling
```

### Database Migration Testing

Test migration scripts in pre-prod before production:

```bash
# Run migration
ansible-playbook ansible/playbook.yml --tags db-migrate
```

## Promotion to Production

### Promotion Checklist

- [ ] All pre-prod tests passed
- [ ] Code review completed
- [ ] Security scan passed
- [ ] Database migration tested
- [ ] Rollback plan documented
- [ ] Stakeholder approval obtained
- [ ] Production deployment scheduled

### Deployment Procedure

1. Deploy to pre-prod
2. Run full test suite
3. Performance validation
4. Security validation
5. Get approval
6. Deploy to production (`environments/aws-prod/`)

## Monitoring

### CloudWatch Dashboards

Create pre-prod specific dashboards:
- Request rate
- Error rate
- Latency (p50, p95, p99)
- Task CPU/Memory
- Database connections

### Alarms

Configure relaxed thresholds:
- Error rate > 10% (vs 5% in prod)
- Latency p95 > 2s (vs 1s in prod)
- CPU > 80% (vs 70% in prod)

## Data Management

### Test Data

```bash
# Seed test data
ansible-playbook ansible/playbook.yml --tags seed-data

# Clear test data
ansible-playbook ansible/playbook.yml --tags clear-data
```

### Data Refresh

Periodically refresh with sanitized production data:

```bash
# Sanitize and copy from production (future)
./scripts/refresh-preprod-data.sh
```

## Access Control

### User Access

Pre-prod should have:
- Development team (full access)
- QA team (read/write for testing)
- Product owners (read-only for demos)
- Security team (audit access)

### Service Accounts

Test service accounts with same permissions as production.

## Cost Management

Estimated monthly cost: **$40-80**

- Lower than production due to reduced resources
- Can be further reduced with scheduled scaling
- Consider AWS Cost Explorer for monitoring

## Related

- **Development**: `environments/aws-dev/` - Development testing
- **Production**: `environments/aws-prod/` - Live environment
- **Local**: `environments/local-docker/` - Local validation first
- **Documentation**: `docs/environments.md` - Comprehensive guide
