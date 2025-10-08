# FRANK Implementation Plan - 4-Stage Approach

## Overview
This document outlines the 4-stage progressive development approach for FRANK (Feedback Infrastructure for Cyber Risk Analysis and Network Knowledge sharing), evolving from a local SQLite/FastAPI prototype to a scalable Cloud agnostic production system.

## Strategic Approach: Infrastructure vs Functional Complexity

### Core Principle
**Separate infrastructure learning from data model complexity**:
- Stages 1 and 2: Simple / Complex submission model with infrastructure evolution
- Stage 3: Cloud production system
- Stage 4: Cloud agnostic system with full feature set

### Risk Management
Each stage maintains a **working fallback system**, ensuring continuous development capability and reducing deployment risk.

| Stage | Database | Compute | Location | Auth | **Functional Scope** | Purpose |
|-------|----------|---------|----------|------|---------------|---------|
| 1     | SQLite   | FastAPI | Local      | Mock JWT | **Minimal submissions** | Current foundation |
| 2     | DynamoDB | FastAPI | Docker / LocalStack | Mock JWT | **Submissions** | NoSQL/Containerization |
| 3     | DynamoDB | FastAPI | ECS / AWS  | Cognito | **Full scope calls** | Cloud deployment |
| 4     | ScyllaDB? | FastAPI | Kubernetes | Supertokens | **🚀 Extensive statistics** | Agnostic stack |


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

### **Stage 2: Local NoSQL Infrastructure Simulation (AWS)**
**Status**: ✅ **COMPLETE**

**Technology Stack**:
- **Database**: LocalStack RDS (MySQL) + LocalStack DynamoDB (parallel testing)
- **API**: FastAPI
- **Location**: Local development with LocalStack
- **Submissions**: Minimal model (unchanged)

**Key Learning Objectives**:
- AWS database service patterns (RDS configuration, connection management)
- Docker containerization and service orchestration
- Database abstraction layer implementation
- Complex data relationship modeling in NoSQL
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

### **Stage 3: Cloud Compute Introduction**
**Status**: 🚧 **IN PROGRESS**

**Technology Stack**:
- **Database**: DynamoDB (testing)
- **API**: FastAPI on ECS
- **Auth**: Cognito
- **Location**: Local development with LocalStack / AWS
- **Submissions**: **🚀 MAXIMUM MODEL** (major functional upgrade)

**Key Learning Objectives**:
- IoC on Cloud
- authentication implementation

**Implementation Focus**:
- Implement full FRANK submission model with complex observables
- DynamoDB single-table design with GSIs
- Advanced relationship handling (organisations, threat actors, campaigns)

**Success Criteria**:
- All FastAPI endpoints working in AWS

**Risk Mitigation**:
- Same business logic, different presentation layer
- Database layer unchanged from Stage 2

See [Stage 3/README.md](../stages/stage3/README.md)

---

### **Stage 4: NoSQL Migration + Data Model Evolution**
**Status**: ⏳ **PLANNED**

**Technology Stack**:
- **Database**: LocalStack ScyllaDB (primary)
- **API**: FastAPI on ECS
- **Auth**: Supertokens
- **Location**: Any cloud provider on Kubernetes
- **Submissions**: **🚀 MAXIMUM MODEL** (major functional upgrade)

**Production Features**:
- Supertokens authentication and authorization (with Postgresql)
- OpenSearch for analytics and full-text search
- Monitoring
- Container Functions for complex workflows

**Key Learning Objectives**:
- Full cloud-agnostic development

**Implementation Focus**:
- Become agnostic to non-generic technology

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
    submitter: Submitter
    sighting: Sighting

class Sighting:
    hit_target: Optional[HitTarget]
    threat_details: Optional[ThreatDetails]
    observables: List[SimpleObservable]
```

**Database design**
Single Table Design Pattern - General table (also see [nosql.md](./design/nosql.md))
```
    
    PK (Partition Key)  | SK (Sort Key)   | GSI1PK              | GSI1SK       | Entity Type     | Description
    ORG#{org_id}        | ORG             | TIER#{access_level} | #{timestamp} | organisation    | organisation metadata
    SUB#{sub_id}        | SUB             | ORG#{org_id}        | #{timestamp} | Submission      | Complete submission with nested data
    OBS#{obs_hash}      | SUB#{sub_id}    | TYPE#{obs_type}     | #{timestamp} | ObservableIndex | Observable cross-reference
    SIGHT#{sighting_id} | SUB#{sub_id}    | ORG#{org_id}        | #{timestamp} | Sighting        | Sighting details (confidence, severity, observables)
```

Log table (separate entity for access logs):
```
    PK (Partition Key)  | SK (Sort Key)   | GSI1PK          | GSI1SK       | Entity Type     | Description
    LOG#{org_id}        | LOG#{timestamp} | ACTION#{action} | #{timestamp} | Access Log      | Audit trail for actions

```