# FRANK Implementation Plan - 5-Stage Approach

## Overview
This document outlines the 5-stage progressive development approach for FRANK (Feedback Infrastructure for Cyber Risk Analysis and Network Knowledge sharing), evolving from a local SQLite/FastAPI prototype to a scalable AWS production system.

## Strategic Approach: Infrastructure vs Functional Complexity

### Core Principle
**Separate infrastructure learning from data model complexity**:
- Stages 1-3: Simple submission model with infrastructure evolution
- Stage 4: Complex submission model introduction with stable infrastructure
- Stage 5: Production optimization with full feature set

### Risk Management
Each stage maintains a **working fallback system**, ensuring continuous development capability and reducing deployment risk.

| Stage | Database | Compute | Location | **Functional Scope** | Purpose |
|-------|----------|---------|----------|---------------------|---------|
| 1 | SQLite | FastAPI | Local | **Minimal submissions** | Current foundation |
| 2 | RDS / DynamoDB | FastAPI | LocalStack / Mangum | **Minimal submissions** | AWS database patterns |
| 3 | DynamoDB | Lambda | LocalStack / Mangum | **Minimal submissions** | AWS compute patterns |
| 4 | DynamoDB | Lambda | LocalStack / Mangum | **🚀 Maximum submissions** | AWS NoSQL + full data model |
| 5 | DynamoDB | Lambda | Real AWS | **Maximum submissions** | Production deployment |

---

## Stage Progression

### **Stage 1: Foundation**
**Status**: ✅ **COMPLETE**

**Technology Stack**:
- **Database**: SQLite (local file)
- **API**: FastAPI
- **Location**: Local development
- **Submissions**: Minimal model

**Capabilities**:
- Pydantic data models with validation
- SQLite database with normalized schema
- Comprehensive unit tests
- Basic threat intelligence submission handling

**Deliverables**:
- Working FastAPI application
- SQLite database schema
- Unit test suite
- Minimal submission model

See [Stage 1/README.md](../stages/stage1/README.md)

---

### **Stage 2: Local AWS Infrastructure Simulation**
**Status**: 🚧 **IN PROGRESS**

**Technology Stack**:
- **Database**: LocalStack RDS (MySQL) + LocalStack DynamoDB (parallel testing)
- **API**: FastAPI
- **Location**: Local development with LocalStack
- **Submissions**: Minimal model (unchanged)

**Key Learning Objectives**:
- AWS database service patterns (RDS configuration, connection management)
- Docker containerization and service orchestration
- Database abstraction layer implementation
- LocalStack simulation environment setup

**Implementation Focus**:
- Dual database support (RDS and DynamoDB side-by-side)
- Repository pattern for database abstraction
- Docker Compose orchestration
- Environment-based configuration management

**Success Criteria**:
- FastAPI application connects to both LocalStack RDS and DynamoDB
- Same submission model works with both databases
- Performance comparison between SQL and NoSQL approaches
- Stable local development environment

**Risk Mitigation**:
- Fallback to Stage 1 (SQLite) always available
- Parallel database testing reduces commitment risk
- Infrastructure patterns learned apply to real AWS

See [Stage 2/README.md](../stages/stage2/README.md)

---

### **Stage 3: Serverless Compute Introduction**
**Status**: ⏳ **PLANNED**

**Technology Stack**:
- **Database**: LocalStack RDS (primary) + LocalStack DynamoDB (testing)
- **API**: AWS Lambda handlers with Mangum (LocalStack)
- **Location**: Local development with LocalStack
- **Submissions**: Minimal model (unchanged)

**Key Learning Objectives**:
- FastAPI to Lambda handler conversion
- API Gateway event/response format handling
- Lambda cold start patterns and optimization
- Serverless application architecture

**Implementation Focus**:
- Convert FastAPI endpoints to Lambda handlers
- API Gateway integration via LocalStack
- Lambda-specific error handling and logging
- Database connection pooling for Lambda

**Success Criteria**:
- All FastAPI endpoints converted to Lambda handlers
- API Gateway routing works correctly
- Database connections optimized for Lambda lifecycle
- Performance benchmarks established

**Risk Mitigation**:
- Keep FastAPI implementation as fallback
- Same business logic, different presentation layer
- Database layer unchanged from Stage 2

---

### **Stage 4: NoSQL Migration + Data Model Evolution**
**Status**: ⏳ **PLANNED**

**Technology Stack**:
- **Database**: LocalStack DynamoDB (primary) + RDS (migration support)
- **API**: AWS Lambda handlers (LocalStack)
- **Location**: Local development with LocalStack
- **Submissions**: **🚀 MAXIMUM MODEL** (major functional upgrade)

**Key Learning Objectives**:
- DynamoDB single-table design patterns
- Complex data relationship modeling in NoSQL
- Data migration strategies (RDS → DynamoDB)
- Advanced submission model implementation

**Implementation Focus**:
- Implement full FRANK submission model with complex observables
- DynamoDB single-table design with GSIs
- Data migration tooling from RDS to DynamoDB
- Advanced relationship handling (organizations, threat actors, campaigns)

**Functional Enhancements**:
```python
# Minimal Submission (Stages 1-3)
class MinimalSubmission:
    submission_id: str
    submitter_org_id: str
    observables: List[SimpleObservable]
    confidence: Optional[int]
    timestamp: datetime

# Maximum Submission (Stage 4+)
class MaximumSubmission:
    submission_id: str
    submitter_org_id: str
    hit_target_org_id: Optional[str]
    attack_context: Optional[AttackContext]
    threat_actor: Optional[ThreatActorInfo]
    campaign_info: Optional[CampaignInfo]
    observables: List[ComplexObservable]
    sharing_level: str
    validation_status: str
    # ... extensive additional fields
```

**Success Criteria**:
- Complex submission model fully implemented
- DynamoDB single-table design supports all query patterns
- Migration from RDS completed successfully
- Performance meets or exceeds RDS implementation

**Risk Mitigation**:
- Dual-write pattern during migration
- RDS backup remains available
- Incremental data model migration
- Comprehensive testing with both simple and complex data

---

### **Stage 5: AWS Production Deployment**
**Status**: ⏳ **PLANNED**

**Technology Stack**:
- **Database**: AWS DynamoDB (production)
- **API**: AWS Lambda + API Gateway
- **Location**: Real AWS infrastructure
- **Submissions**: Maximum model + production features

**Production Features**:
- AWS Cognito authentication and authorization
- S3 integration for large artifacts
- OpenSearch for analytics and full-text search
- CloudWatch monitoring and X-Ray tracing
- KMS encryption for data protection
- Step Functions for complex workflows

**Implementation Focus**:
- Real AWS service integration
- Production security implementation
- Monitoring and observability setup
- CI/CD pipeline establishment
- Cost optimization and scaling configuration

**Success Criteria**:
- Full AWS deployment with all services integrated
- Production-grade security and monitoring
- Automated deployment pipeline
- Performance and cost optimization completed
- User acceptance testing passed

**Risk Mitigation**:
- LocalStack environment remains for development
- Staged rollout with gradual traffic migration
- Comprehensive testing in AWS staging environment
- Rollback procedures documented and tested

See [Stage 5/README.md](../stages/stage5/README.md)


---

## Database Evolution Strategy

### Stage 2-3: SQL Foundation
```sql
-- Normalized relational design
CREATE TABLE organizations (
    organization_id TEXT PRIMARY KEY,
    organization_type TEXT NOT NULL,
    access_level TEXT,
    sector TEXT
);

CREATE TABLE submissions (
    submission_id TEXT PRIMARY KEY,
    submitter_org_id TEXT NOT NULL,
    confidence INTEGER,
    submission_timestamp TIMESTAMP,
    FOREIGN KEY (submitter_org_id) REFERENCES organizations(organization_id)
);
```

### Stage 4-5: NoSQL Single-Table Design
```python
# DynamoDB single-table pattern
Table: frank-data-{env}

# Organization record
PK: "ORG#bank-alpha"           SK: "PROFILE"
# Submission record  
PK: "ORG#bank-alpha"           SK: "SUB#2025-01-15#uuid"
# Observable record
PK: "OBS#ipv4#192.168.1.1"    SK: "SUB#uuid"
# Threat actor record
PK: "ACTOR#apt29"              SK: "SUB#uuid"
```

## Technology Decision Points

### Stage 2: Database Choice Validation
**Decision Point**: RDS vs DynamoDB for Stage 3
- **Parallel Implementation**: Test both databases in Stage 2
- **Evaluation Criteria**: Performance, complexity, learning curve
- **Decision Timeline**: End of Stage 2
- **Fallback**: Continue with better-performing option

### Stage 4: Data Model Migration Strategy
**Decision Point**: Gradual vs complete migration
- **Recommended**: Dual-write pattern with gradual read migration
- **Validation**: Shadow testing with production load simulation
- **Rollback**: Maintain RDS as backup during transition

## Development Workflow

### Local Development Environment
```bash
# Stage 2+ Development Stack
docker-compose up localstack mysql dynamodb
export FRANK_ENVIRONMENT=localstack
export DATABASE_TYPE=dual  # Test both RDS and DynamoDB

# Application startup
python -m frank.server --environment=localstack
```

### Testing Strategy
- **Unit Tests**: Pydantic model validation, business logic
- **Integration Tests**: Database operations, API endpoints
- **Performance Tests**: Load testing, latency measurement
- **Migration Tests**: Data consistency, performance comparison

### Configuration Management
```python
# Environment-based configuration
class FrankConfig:
    def __init__(self, environment: str):
        if environment == "local":
            self.database_url = "sqlite:///frank.db"
        elif environment == "localstack":
            self.database_url = "mysql://frank:pass@localhost:4566/frank"
            self.dynamodb_endpoint = "http://localhost:4566"
        elif environment == "aws":
            self.database_url = None  # DynamoDB only
            self.dynamodb_endpoint = None  # Real AWS
```

## Success Metrics

### Stage 2 Metrics
- [ ] LocalStack RDS connection established
- [ ] DynamoDB LocalStack integration working
- [ ] Repository pattern abstraction complete
- [ ] Docker Compose stack reliable

### Stage 3 Metrics
- [ ] All FastAPI endpoints converted to Lambda
- [ ] API Gateway integration functional
- [ ] Lambda cold start < 3 seconds
- [ ] Database connection pooling optimized

### Stage 4 Metrics
- [ ] Complex submission model implemented
- [ ] DynamoDB single-table design supports all queries
- [ ] Migration tools tested and validated
- [ ] Performance matches or exceeds SQL implementation

### Stage 5 Metrics
- [ ] AWS production deployment successful
- [ ] All security requirements met
- [ ] Monitoring and alerting operational
- [ ] Cost targets achieved

## Risk Assessment and Mitigation

### Technical Risks
1. **Learning Curve**: Each stage introduces new complexity
   - **Mitigation**: Incremental approach, maintain fallbacks
2. **Data Migration**: Risk of data loss or corruption
   - **Mitigation**: Dual-write patterns, comprehensive testing
3. **Performance**: Unknown performance characteristics
   - **Mitigation**: Benchmarking at each stage, optimization focus

### Operational Risks
1. **Development Velocity**: Complex migration may slow feature development
   - **Mitigation**: Working system maintained at each stage
2. **Team Knowledge**: AWS expertise required
   - **Mitigation**: Progressive learning, documentation focus
3. **Cost**: AWS services may exceed budget
   - **Mitigation**: LocalStack development, cost monitoring

## Conclusion

This 5-stage approach provides a systematic, low-risk path from local development to production AWS deployment. Each stage builds incrementally on the previous stage while maintaining a working system and clear fallback options.

The separation of infrastructure complexity (Stages 2-3) from functional complexity (Stage 4) allows focused learning and reduces the risk of simultaneous failures across multiple system components.

**Next Action**: Implement Stage 2 with dual database support to validate the approach and begin AWS service integration learning.