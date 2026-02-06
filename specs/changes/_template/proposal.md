# Change Proposal: [Feature Name]

⭐ **Required sections marked with star**

- **Status:** ⭐ DRAFT | REVIEW | APPROVED | IMPLEMENTED | SUPERSEDED
- **Proposal ID:** ⭐ XXX (e.g., 001, 002, etc.)
- **Issue:** ⭐ #XXX (GitHub issue number)
- **Owner:** ⭐ [Name or Team]
- **Last Updated:** YYYY-MM-DD

---

## Executive Summary

⭐ **One-paragraph summary** answering these questions:
- What change are we proposing?
- Why do we need it?
- What value does it deliver?
- When should we do it?

**Example**:
> We propose implementing a unified Sightings API to enable threat intelligence teams to share observations of threat indicators across organizations. This directly addresses FRANK's core value proposition and enables the pilot phase with 5+ organizations. The API design follows established REST patterns from Spike 007 (FastAPI) and integrates with existing Cognito authentication. We recommend implementing this in Stage 1 (SQLite) first for rapid feedback, then scaling to Stage 3 (AWS) for production deployment.

---

## 1. Problem Statement

⭐ **Why do we need this change?** Describe the current situation and why it's unsatisfactory.

### Current Situation

What's the current state? What's missing?

**Example**:
> Currently, FRANK receives threat intelligence submissions but has no standardized way for organizations to query recent sightings of threat indicators. Teams resort to:
> - Email exchanges (no audit trail, slow)
> - Direct database access (security risk, not scalable)
> - Custom scripts (fragile, not reusable)

### The Problem

What's the gap or pain point?

**Example**:
> This fragmentation creates:
> - **Security Risk**: Direct database access violates principle of least privilege
> - **Integration Pain**: Custom scripts break when database schema changes
> - **Compliance Gap**: No audit trail of who accessed what data when
> - **Scalability Wall**: Email exchanges don't work with hundreds of sightings per day

### Business Impact

How does this problem affect FRANK's mission and users?

**Example**:
> - **Threat Intelligence Decay**: Organizations can't efficiently learn from recent observations
> - **Missed Collaboration**: Teams can't easily discover shared threats across organizations
> - **Pilot Blocker**: Pilot organizations requested this feature as a must-have
> - **Market Competitiveness**: Competing solutions provide out-of-the-box APIs

---

## 2. Proposed Solution Overview

⭐ **What are we proposing?** High-level summary of the solution.

### What We're Building

Provide a clear vision of the solution:

**Example**:
> A RESTful Sightings API that enables authorized users to query and submit threat intelligence observations. The API provides:
> - **Query Interface**: Search sightings by observable ID, date range, confidence level
> - **Submit Interface**: Report new sightings with structured details
> - **Access Control**: Enforce organization and access tier restrictions
> - **Audit Logging**: Track all API usage for compliance

### Key Features

List the main capabilities:

**Example**:
- Query sightings of specific threat indicators (IPs, domains, file hashes)
- Filter by date range, confidence level, reporter organization
- Submit new sightings with detailed context
- Support pagination for large result sets
- Real-time notifications (future enhancement)

### Success Criteria

How will we know this change succeeds?

**Example**:
- [ ] Pilot organizations can integrate API into their workflows
- [ ] Query performance: 95th percentile < 200ms response time
- [ ] Reduced manual coordination emails by 80%
- [ ] Zero security incidents related to direct database access
- [ ] ≥85% test coverage across all code paths
- [ ] Documentation enables new developers to use API within 1 hour

---

## 3. Value Proposition

⭐ **Why should we do this now?** Articulate the business and technical value.

### For Users
What benefits does this provide to FRANK users?

**Example**:
- **Faster Threat Intelligence Sharing**: Real-time access to sightings vs. email delays
- **Better Integration**: API enables integration with security tools (SIEM, threat feeds)
- **Compliance Support**: Audit logging helps meet security standards
- **Improved Collaboration**: Discover threats reported by other organizations

### For FRANK Project
What strategic benefits?

**Example**:
- **Pilot Success**: Enables go-live with pilot organizations
- **Feature Completeness**: Closes gap between core submission and threat sharing
- **Architecture Validation**: Tests repository pattern across storage backends
- **Evolutionary Path**: Demonstrates Stage 1 → Stage 3 scaling strategy

### For Development Team
What technical benefits?

**Example**:
- **Pattern Reuse**: Leverages established FastAPI patterns from Spike 007
- **Test Framework**: Demonstrates testing approach across three layers
- **Authentication Integration**: Validates Cognito integration from Spike 014
- **Knowledge Capture**: Documents API design approach in specs

### ROI Timeline

When do we realize value?

**Example**:
- **Weeks 1-2**: Implementation and testing (2-3 developers)
- **Week 3**: Pilot organization integration
- **Week 4**: Production deployment to AWS
- **Months 2-3**: Realized benefits (threat sharing, reduced emails)

---

## 4. Constraints & Dependencies

⭐ **What are the constraints and dependencies?**

### Technical Dependencies

What existing systems or patterns must be in place?

**Example**:
- ✅ Pydantic v2 model framework (Observable, Submission models)
- ✅ FastAPI server patterns (Spike 007)
- ✅ Cognito authentication (Spike 014, ADR-0005)
- ✅ SQLite repository implementation (Stage 1)
- ⚠️ DynamoDB repository (under development, needed for Stage 3)

### External Dependencies

Any external services or data?

**Example**:
- AWS Cognito for JWT token validation
- GitHub for issue tracking and PRs
- DockerHub for base images

### Schedule Constraints

Timeline or milestone dependencies?

**Example**:
- **Hard Deadline**: Pilot go-live required by March 31, 2026
- **Soft Deadline**: Prefer Stage 3 deployment by end of Q1
- **Dependency**: DynamoDB implementation must complete before AWS deployment

### Budget/Resource Constraints

Available people, compute, or time?

**Example**:
- 2-3 developers full-time for 3 weeks
- Development: $0 (internal team)
- Infrastructure: ~$2K/month AWS for pilot (RDS, DynamoDB, ECS)

---

## 5. Alternative Approaches Considered

⭐ **What other options did we evaluate?** Document trade-offs.

### Alternative 1: Direct Database Access

Allow organizations to query submission database directly with connection strings.

**Pros**:
- Fastest implementation (existing database connection patterns)
- Maximum flexibility (organizations control their queries)

**Cons**:
- ❌ Major security risk (exposing internal database)
- ❌ No access control or filtering
- ❌ Schema changes break external queries
- ❌ No audit trail for compliance
- **Verdict**: Rejected for security reasons

### Alternative 2: Bulk Export API

Export all sightings as JSON files, organizations import locally.

**Pros**:
- Simple batch processing
- Organizations have full data locally

**Cons**:
- ❌ Not real-time (batches run daily)
- ❌ Data transfer inefficient for large result sets
- ❌ Organizations can't filter (must process entire export)
- ❌ Doesn't support targeted queries

**Verdict**: Rejected - doesn't meet pilot requirements for real-time access

### Alternative 3: GraphQL API

Full GraphQL API instead of REST.

**Pros**:
- ✅ Highly flexible querying
- ✅ Clients request only needed fields
- ✅ Single endpoint for all data needs

**Cons**:
- ⚠️ More complex implementation (GraphQL server framework)
- ⚠️ Steeper learning curve for API consumers
- ⚠️ Not consistent with existing FastAPI REST patterns
- ⚠️ Team has no GraphQL experience

**Verdict**: Deferred - consider in future enhancement, stick with REST for now

### Recommended Approach

**RESTful Sightings API** (selected)

**Rationale**:
- ✅ Familiar REST patterns reduce learning curve
- ✅ Aligns with Spike 007 (FastAPI) learnings
- ✅ Straightforward to secure and audit
- ✅ Easy to version and evolve
- ✅ Standard industry pattern for threat intelligence sharing

---

## 6. Implementation Timeline

⭐ **When and how will we implement this?** Provide a phased approach.

### Phase 1: Design & Planning (Days 1-2)

Create formal specification and design documents.

**Deliverables**:
- [ ] Specification complete (spec.md)
- [ ] API design finalized (design.md)
- [ ] Implementation tasks defined (tasks.md)
- [ ] Architecture decision recorded (adr.md)
- [ ] Design review approved by team

**Owner**: [Name]
**Resources**: 1 architect, 2 developers
**Timeline**: 2 days

### Phase 2: Stage 1 Implementation (Days 3-7)

Implement full API on SQLite with comprehensive tests.

**Deliverables**:
- [ ] All endpoints implemented
- [ ] Unit tests with ≥85% coverage
- [ ] Integration tests (BDD scenarios)
- [ ] Implementation PR reviewed and merged
- [ ] Code working on developer laptops

**Owner**: [Name]
**Resources**: 2-3 developers
**Timeline**: 5 days

### Phase 3: Testing & Documentation (Days 8-9)

Comprehensive testing and user documentation.

**Deliverables**:
- [ ] Integration testing with pilot users
- [ ] API documentation (Swagger/OpenAPI)
- [ ] User guide and examples
- [ ] Troubleshooting guide
- [ ] Feedback incorporated into code

**Owner**: [Name]
**Resources**: 1 developer, 1 technical writer
**Timeline**: 2 days

### Phase 4: Stage 3 Implementation (Days 10-14)

Deploy to AWS with DynamoDB backend.

**Deliverables**:
- [ ] DynamoDB implementation complete
- [ ] CloudFormation templates updated
- [ ] AWS deployment tested
- [ ] Performance validated against NFRs
- [ ] Monitoring and logging configured

**Owner**: [Name]
**Resources**: 2 developers (infrastructure focused)
**Timeline**: 5 days

### Phase 5: Pilot Deployment (Day 15+)

Deploy to pilot organizations for real-world validation.

**Deliverables**:
- [ ] Pilot organizations onboarded
- [ ] API endpoints available in production
- [ ] Monitoring and alerting active
- [ ] Feedback collection in place
- [ ] Support plan documented

**Owner**: [Name]
**Resources**: 1 developer (support), 1 PM
**Timeline**: Ongoing

**Total Timeline**: 15+ days (3+ weeks) for full deployment

---

## 7. Risk Assessment

⭐ **What could go wrong?** Identify and mitigate risks.

### Risk 1: Performance Doesn't Meet Requirements

**Description**: Query response times exceed 200ms target, especially in Stage 3 with large datasets.

**Likelihood**: Medium (database performance is hard to predict at scale)
**Impact**: High (pilot organizations won't use slow API)
**Mitigation**:
- [ ] Performance testing in Phase 2 with realistic data volumes
- [ ] Database indexing strategy defined in design phase
- [ ] Spike 012 (DynamoDB) learnings guide performance design
- [ ] Fallback: Cache frequently-queried sightings

### Risk 2: Security Vulnerability

**Description**: API or authentication code has vulnerability, exposing threat intelligence data.

**Likelihood**: Medium (complex security implementation)
**Impact**: Critical (compliance breach, data exposure)
**Mitigation**:
- [ ] Security review by dedicated security engineer
- [ ] Cognito authentication validated (Spike 014)
- [ ] Access control testing covers all edge cases
- [ ] Penetration testing before pilot deployment

### Risk 3: Scope Creep

**Description**: Feature requests expand beyond initial API (real-time notifications, ML analytics, etc.).

**Likelihood**: High (typical for first user-facing API)
**Impact**: Medium (timeline slips, team overloaded)
**Mitigation**:
- [ ] Clear scope boundary in proposal and spec
- [ ] Feature request tracking separate from implementation
- [ ] Design supports future enhancements without rework

### Risk 4: Team Lacks GraphQL/Modern API Experience

**Description**: Implementation delays due to learning curve or unfamiliar patterns.

**Likelihood**: Low (REST is familiar, FastAPI proven in Spike 007)
**Impact**: Medium (2-3 day delay)
**Mitigation**:
- [ ] Selected REST instead of GraphQL
- [ ] FastAPI patterns documented in Spike 007
- [ ] Team pairing on unfamiliar code
- [ ] External expert available if needed

---

## 8. Success Metrics

⭐ **How will we measure success?** Define measurable outcomes.

### Adoption Metrics

**Pilot Organizations Using API**:
- **Target**: ≥80% of pilot organizations (4 out of 5)
- **Measurement**: API usage logs, organization surveys
- **Timeline**: 30 days after deployment

**API Requests/Day**:
- **Target**: ≥1000 requests/day by end of pilot
- **Measurement**: CloudWatch metrics, API usage dashboards
- **Timeline**: End of pilot period (60 days)

### Quality Metrics

**Code Coverage**:
- **Target**: ≥85% (per [ADR-0012](../docs/adr/0012-testing-philosophy.md))
- **Measurement**: Coverage reports from CI/CD
- **Timeline**: Before merge to main

**Performance**:
- **Target**: 95th percentile response time < 200ms
- **Measurement**: CloudWatch, load testing
- **Timeline**: Before pilot deployment

**Reliability**:
- **Target**: ≥99.5% uptime
- **Measurement**: Uptime monitoring, incident tracking
- **Timeline**: First month of pilot

### User Satisfaction

**Ease of Integration**:
- **Target**: New developers integrate API within 2 hours
- **Measurement**: User feedback, onboarding time tracking
- **Timeline**: After documentation published

**Support Burden**:
- **Target**: <1 support request per organization/week on average
- **Measurement**: Issue tracking, support email logs
- **Timeline**: During pilot

---

## 9. Next Steps

⭐ **What happens now?** Clear action items.

### Immediate (Next 24 Hours)

- [ ] **Review**: Team reviews proposal and provides feedback
- [ ] **Approve/Reject**: Decision makers approve or request changes
- [ ] **Communicate**: Share decision with stakeholders

### If Approved (Days 1-2)

- [ ] **Create Spec**: Write formal specification (spec.md)
- [ ] **Create Design**: Document architecture and implementation approach (design.md)
- [ ] **Create Tasks**: Break down implementation into concrete tasks (tasks.md)
- [ ] **Create ADR**: Document architectural decisions (adr.md)

### Implementation (Days 3-15)

- [ ] **Phase 1**: Design & planning
- [ ] **Phase 2**: Stage 1 implementation
- [ ] **Phase 3**: Testing & documentation
- [ ] **Phase 4**: Stage 3 implementation
- [ ] **Phase 5**: Pilot deployment

---

## Appendix: References

### Related ADRs

- [ADR-0002: Repository Pattern & Database Abstraction](../../docs/adr/0002-repository-pattern-database-abstraction.md)
- [ADR-0003: Tiered Access Control Model](../../docs/adr/0003-tiered-access-control-model.md)
- [ADR-0005: Cognito Authentication](../../docs/adr/0005-cognito-authentication.md)
- [ADR-0007: Forgiving Input, Strong Output](../../docs/adr/0007-forgiving-input-strong-output.md)
- [ADR-0010: Stages vs. Environments](../../docs/adr/0010-stages-vs-environments.md)

### Related Spikes

- [Spike 007: FastAPI Application Structure](../../tests/spikes/007_fastapi/README.md)
- [Spike 012: DynamoDB Table Design](../../tests/spikes/012_aws_dynamodb/README.md)
- [Spike 014: Cognito Authentication](../../tests/spikes/014_cognito/README.md)
- [Spike 015: FastAPI Testing](../../tests/spikes/015_fastapi_testing/README.md)

### External Resources

- [STIX 2.1 Specification](https://docs.oasis-open.org/cti/stix/v2.1/cs01/stix-v2.1-cs01.html)
- [REST API Best Practices](https://restfulapi.net/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [AWS DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)

### GitHub

- **Issue**: [#92 - Implement Main API (Sightings API) for threat intelligence](https://github.com/example/frank/issues/92)
- **Pilot Organizations**: [ACME Corp, TechSecure Inc, DefenseWorks LLC, ...]

---

## Document History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| YYYY-MM-DD | 1.0 | [Name] | Initial proposal |
| YYYY-MM-DD | 1.1 | [Name] | Incorporated feedback from team review |

---

**Next**: Read [`spec.md`](spec.md) for detailed functional and non-functional requirements.
