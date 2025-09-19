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

**Implementation Focus**:
- Implement full FRANK submission model with complex observables
- DynamoDB single-table design with GSIs
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