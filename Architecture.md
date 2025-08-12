# FRANK AWS Architecture

## Overview

FRANK (Feedbackinfrastructuur voor cyberRisico Analyse en netwerk Kennisdeling) is a serverless cybersecurity threat intelligence sharing platform built on AWS. The architecture enables secure ingestion, processing, and sharing of Indicators of Compromise (IoCs), SIGMA rules, and security sightings across multiple tenants while maintaining privacy through pseudonymization and aggregation.

## Architecture Principles

- **Security-by-Default**: All data encrypted with KMS, no public S3 access, least privilege IAM
- **Multi-tenant**: Tenant separation in data and policies with anonymous/aggregated output
- **Serverless-First**: Leveraging managed AWS services for scalability and cost efficiency
- **Privacy-Preserving**: Pseudonymization of sensitive data with aggregated analytics only

## High-Level Architecture Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Clients   │    │  SIGMA Updates  │    │   Dashboards    │
│  (Organizations)│    │   (Admins)      │    │   (Analysts)    │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │                      │                      │
┌─────────▼──────────────────────▼──────────────────────▼────────┐
│                     API Gateway + WAF                          │
│    /v1/sightings  /v1/sigma/*  /v1/stats                       │
└─────────┬──────────────────────────────────────────────────────┘
          │
┌─────────▼──────────┐
│  Cognito User Pool │
│   Authentication   │
└─────────┬──────────┘
          │
┌─────────▼──────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Lambda Functions  │    │ Step Functions  │    │  ECS Fargate    │
│                    │    │   Workflows.    │    │  SIGMA Tools    │
│ • ingest_sightings │    │                 │    │                 │
│ • write_persistence│    │ • SigmaTranslate│    │ • sigma-cli     │
│ • query_stats      │    │ • TenantOffboard│    │ • Validation    │
│ • sigma_update_job │    │ • ReportGenerate│    │                 │
└─────────┬──────────┘    └─────────────────┘    └─────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data Layer                               │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │     S3      │  │  DynamoDB    │  │    OpenSearch Service  │  │
│  │             │  │              │  │                        │  │
│  │ • Raw Data  │  │ • Aggregates │  │ • Search & Analytics   │  │
│  │ • Artifacts │  │ • Tenants    │  │ • Dashboards           │  │
│  │ • Exports   │  │ • Idempotency│  │ • Multi-tenant Indices │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Core Services Architecture

### 1. API Gateway Layer

**Purpose**: Secure entry point for all external interactions

**Components**:
- REST API with multiple endpoints:
  - `POST /v1/sightings` - Ingest security sightings from participants
  - `GET /v1/stats` - Retrieve aggregated statistics (filterable)
  - `GET /v1/sigma/{ruleId}` - Fetch SIGMA rules and versions
  - `POST /v1/sigma/{ruleId}/update` - Admin updates to SIGMA rules

**Security Features**:
- Cognito JWT authorizer for authentication
- Request/response validation with JSON Schema
- Throttling and usage plans for rate limiting
- AWS WAF integration for protection against common attacks
- CORS configuration for controlled access
- Comprehensive logging to CloudWatch

### 2. Authentication & Authorization

**Amazon Cognito User Pool**:
- JWT-based authentication with custom attributes (tenant_id, sector)
- Role-based access control with groups (publisher, reader)
- Resource server with OAuth2 scopes
- MFA and advanced security features enabled
- Integration with API Gateway method-level authorization

### 3. Compute Layer

**AWS Lambda Functions**:

1. **ingest_sightings**
   - Validates incoming sighting data
   - Performs schema normalization
   - Implements deduplication via idempotency
   - Applies pseudonymization using HMAC-SHA256

2. **write_persistence**
   - Stores raw data to S3 with tenant partitioning
   - Updates DynamoDB aggregates
   - Indexes data in OpenSearch for analytics

3. **query_stats**
   - Retrieves aggregated statistics from DynamoDB/OpenSearch
   - Ensures only anonymized data is returned
   - Supports filtering by IoC type, sector, and time

4. **sigma_update_job**
   - Validates and processes SIGMA rule updates
   - Updates S3 artifacts
   - Triggers downstream indexing and notifications

**Configuration**:
- Python/Node.js runtime with AWS Powertools
- Environment variables for resource ARNs
- DLQ (SQS) and retry policies
- IAM roles with least privilege access

### 4. Orchestration

**AWS Step Functions**:

1. **SigmaTranslate Workflow**
   - S3 trigger → ECS Fargate task → validation → publish
   - Orchestrates SIGMA rule processing pipeline

2. **TenantOffboard Workflow**
   - Credential revocation → data purging → audit logging
   - Ensures complete tenant data removal

3. **ReportGenerate Workflow**
   - Athena queries → S3 exports → signed URL generation
   - Automated report generation process

**AWS ECS Fargate**:
- Containerized SIGMA processing tools
- On-demand execution via Step Functions
- Custom Docker images stored in Amazon ECR

### 5. Data Architecture

**Amazon S3 Storage**:

Bucket Structure:
```
s3://frank-raw-<env>/
├── tenant_id=org1/
│   └── date=2025/08/12/
│       └── sightings.json
s3://frank-artifacts-<env>/
├── sigma-rules/
│   └── rule-id-version.yml
s3://frank-exports-<env>/
├── reports/
└── athena-results/
```

**Amazon DynamoDB Tables**:

1. **frank-aggregates**
   - PK: `ioc#type`, SK: `timebucket#sector#tenant`
   - Stores hot aggregated statistics
   - GSIs for different query patterns

2. **frank-tenants**
   - PK: `tenant_id`
   - Tenant metadata, configuration, and policies

3. **frank-idempotency**
   - Request deduplication with TTL

**Amazon OpenSearch Service**:
- VPC-deployed for security
- Multi-tenant index strategy: `frank-sightings-<tenant>-YYYY.MM`
- Fine-grained access control (FGAC)
- Index lifecycle management (ILM) policies
- OpenSearch Dashboards for visualization

### 6. Security Architecture

**Encryption Strategy**:
- **Customer Managed KMS Keys**:
  - `frank-s3-key`: S3 bucket encryption
  - `frank-ddb-key`: DynamoDB table encryption
  - `frank-os-key`: OpenSearch at-rest encryption
  - `frank-app-key`: Application-level HMAC seeds

**Network Security**:
- VPC endpoints for service communication
- Private subnets for compute resources
- Security groups with least privilege rules
- AWS WAF rules for API protection

**Identity & Access Management**:
- Service-specific IAM roles
- Condition-based policies using resource tags
- Regular access reviews with IAM Access Analyzer

**Compliance & Monitoring**:
- AWS CloudTrail for all API calls
- AWS Config for compliance monitoring
- Security Hub for centralized security findings
- GuardDuty for threat detection
- Macie for PII discovery in S3

### 7. Data Governance

**Multi-Tenant Data Isolation**:
- S3 prefix-based partitioning: `tenant_id=<tenant>/`
- DynamoDB partition key includes tenant_id
- OpenSearch per-tenant indices
- Cognito claims validation at API layer

**Pseudonymization Process**:
```
Original_ID + Tenant_Salt + KMS_Key → HMAC-SHA256 → Pseudonymized_ID
```

**Data Lifecycle**:
- S3 lifecycle policies: Hot → IA → Glacier → Delete
- DynamoDB TTL for temporary data
- OpenSearch ILM for index management
- Configurable retention per tenant

### 8. Analytics & Query Layer

**AWS Glue & Athena**:
- Data Catalog for S3 data lake schema
- Partitioned tables for efficient querying
- Athena workgroups for access control
- Lake Formation for fine-grained permissions

**Aggregation Strategy**:
- Real-time aggregation in Lambda
- Hot aggregates in DynamoDB
- Historical analysis via Athena
- Anonymous statistics only in public APIs

## Operational Architecture

### Observability

**Amazon CloudWatch**:
- Centralized logging for all services
- Custom metrics and alarms
- Dashboards for system health
- Log retention policies

**AWS X-Ray**:
- End-to-end request tracing
- Performance bottleneck identification
- Service map visualization

### Backup & Recovery

**AWS Backup**:
- Automated DynamoDB backups
- OpenSearch snapshots to S3
- S3 versioning and cross-region replication
- Point-in-time recovery capabilities

### Cost Optimization

**Resource Right-Sizing**:
- DynamoDB On-Demand scaling
- Lambda memory optimization
- OpenSearch instance sizing
- S3 storage class optimization

**Cost Monitoring**:
- AWS Budgets with alerts
- Cost allocation tags
- Regular cost optimization reviews

## Deployment Architecture

### Infrastructure as Code

**CloudFormation/CDK Templates**:
- Environment-specific deployments
- Parameterized configurations
- Nested stacks for modularity
- Service Catalog for standardization

### CI/CD Pipeline

**CodePipeline Stages**:
1. Source (CodeCommit/GitHub)
2. Build (CodeBuild with security scanning)
3. Test (Unit, integration, security tests)
4. Deploy Dev
5. Manual approval
6. Deploy Prod

## Scalability Considerations

### Current MVP Scaling

**Immediate Scalability**:
- API Gateway: 10,000 requests/second
- Lambda: 1,000 concurrent executions
- DynamoDB: On-demand scaling
- S3: Virtually unlimited

### Future Scaling Options

**High-Volume Ingestion**:
- Kinesis Data Streams for streaming ingestion
- Kinesis Analytics for real-time aggregation
- ElastiCache for caching layer
- CloudFront for global distribution

## Security Compliance

### Privacy Protection

**Data Minimization**:
- Only necessary data collected
- Pseudonymization at ingestion
- Aggregation before exposure
- Regular data purging

**Tenant Isolation**:
- Complete data segregation
- Independent encryption keys
- Separate IAM policies
- Audit trails per tenant

### Regulatory Compliance

**GDPR Compliance**:
- Right to erasure via offboarding workflow
- Data portability through export APIs
- Privacy by design architecture
- Consent management integration

## Disaster Recovery

### RTO/RPO Targets

**Recovery Objectives**:
- RTO: 4 hours for critical services
- RPO: 1 hour for data loss
- Cross-region backup strategy
- Automated failover procedures

### Business Continuity

**Service Resilience**:
- Multi-AZ deployments
- Auto-scaling groups
- Circuit breaker patterns
- Graceful degradation

## Validation Assessment

Based on the design analysis, this architecture **can work effectively** as described in the introduction because:

### ✅ **Strengths**

1. **Security-First Design**: Comprehensive encryption, isolation, and monitoring
2. **Scalable Architecture**: Serverless components that scale automatically
3. **Multi-Tenant Ready**: Proper data isolation and tenant management
4. **Privacy Preserving**: Strong pseudonymization and aggregation strategies
5. **Operational Excellence**: Comprehensive monitoring, backup, and IaC

### ⚠️ **Considerations**

1. **Complexity**: The architecture is comprehensive but may be complex to implement initially
2. **Cost Management**: Multiple managed services require careful cost monitoring
3. **Cold Start Latency**: Lambda cold starts may impact initial response times
4. **OpenSearch Sizing**: Requires careful capacity planning for multi-tenant workloads

### 🔧 **Recommendations**

1. **Phased Implementation**: Follow the provided checklist for systematic deployment
2. **Performance Testing**: Conduct load testing for Lambda functions and DynamoDB
3. **Cost Optimization**: Implement reserved capacity for predictable workloads
4. **Security Reviews**: Regular penetration testing and security assessments

The architecture is well-designed for a cybersecurity threat intelligence sharing platform and aligns with AWS best practices for security, scalability, and operational excellence.
