# Change Proposal: Background Task Processing System

## Metadata

| Attribute | Value |
|-----------|-------|
| **Proposal ID** | 001 |
| **Status** | Draft |
| **Created** | 2026-02-06 |
| **Author** | FRANK Architecture Team |
| **Priority** | High |
| **Complexity** | Moderate |
| **Estimated Effort** | 3-4 weeks |
| **Target Version** | 0.3.0 |

---

## Executive Summary

Implement asynchronous background task processing for long-running operations that currently block API responses. This will improve API responsiveness, enable bulk ingestion, and support future features like enrichment pipelines and automated reporting.

**Problem**: Currently, all threat intelligence processing happens synchronously in the API request/response cycle. Large bulk submissions (100+ observables) can take 5-10 seconds, blocking the HTTP connection and creating poor user experience. Service accounts experience timeouts during bulk ingestion.

**Solution**: Introduce an asynchronous task queue (AWS SQS + Lambda for cloud, or Celery for local) that processes submissions in the background. API immediately returns 202 Accepted with a task ID, allowing clients to poll for completion status.

**Business Value**:
- 10x improvement in API responsiveness (< 200ms for submission acceptance)
- Support for bulk ingestion up to 10,000 observables per submission
- Foundation for future enrichment pipeline (MITRE ATT&CK mapping, threat scoring)
- Better user experience for web GUI and service accounts

---

## Problem Statement

### Current Pain Points

1. **Slow API Response Times**
   - Submissions with 50+ observables take 3-5 seconds
   - Bulk submissions (500+ observables) timeout after 30 seconds
   - HTTP connections held open during entire processing time
   - Poor experience for automated ingestion services

2. **No Bulk Ingestion Support**
   - Service accounts must split large feeds into small chunks
   - Manual batching logic in every ingestion script
   - Increased network overhead (multiple HTTP requests)
   - Higher risk of partial failures

3. **Blocks Future Features**
   - Cannot add enrichment steps (external API calls)
   - Cannot implement threat scoring algorithms (ML inference)
   - Cannot generate automated reports
   - Cannot support scheduled tasks (daily summaries)

4. **Scalability Limitations**
   - ECS tasks scale based on HTTP request rate, not processing load
   - DynamoDB writes happen in API request context
   - No ability to retry failed operations
   - No visibility into processing queue depth

### Impact on Users

**Service Accounts** (Automated Ingestion):
- Timeout errors during bulk submission
- Complex retry logic required in scripts
- Inability to submit large threat feeds at once
- Degraded reliability during high-volume periods

**Human Users** (Web GUI):
- Slow form submission responses
- "Spinning wheel" for several seconds
- Cannot submit while previous submission processes
- Poor perceived performance

**Platform Operators**:
- No visibility into processing backlog
- Cannot prioritize high-value submissions
- Difficult to troubleshoot failed submissions
- No way to replay failed operations

### Business Impact

- **User Satisfaction**: Service accounts report frustration with timeouts
- **Scalability**: Cannot onboard high-volume partners (>10K submissions/day)
- **Competitive**: Modern threat intelligence platforms offer async processing
- **Technical Debt**: Synchronous processing limits future feature development

---

## Proposed Solution

### High-Level Approach

Implement a **two-phase submission flow**:

**Phase 1: Immediate Acceptance (< 200ms)**
```
Client → POST /submit → API validates → Queue task → Return 202 Accepted
                                                    ↓
                                            {task_id, status_url}
```

**Phase 2: Asynchronous Processing**
```
Task Queue → Worker → Process submission → Store in DB → Update task status
                                                       ↓
Client → GET /tasks/{task_id} → Return status (pending/processing/completed/failed)
```

### Technology Options

**Cloud Deployment (Stage 3)**: AWS SQS + Lambda
- Native AWS integration
- Serverless (no infrastructure management)
- Auto-scaling based on queue depth
- Pay-per-use pricing

**Local Development (Stage 1)**: In-memory queue
- Simple Python queue.Queue
- Runs in same process as API
- No external dependencies
- Fast for testing

**Alternative (Stage 4)**: Celery + Redis
- More flexible for complex workflows
- Better for local development
- Requires Redis infrastructure
- More mature ecosystem

### User Experience Flow

**Before (Synchronous)**:
```
POST /submit
  ↓ (wait 5 seconds...)
201 Created
{
  "submission_id": "submission--abc123",
  "status": "completed"
}
```

**After (Asynchronous)**:
```
POST /submit
  ↓ (< 200ms)
202 Accepted
{
  "task_id": "task-xyz789",
  "submission_id": "submission--abc123",
  "status": "pending",
  "status_url": "/tasks/task-xyz789"
}

# Client polls for status
GET /tasks/task-xyz789
  ↓
200 OK
{
  "task_id": "task-xyz789",
  "status": "completed",
  "submission_id": "submission--abc123",
  "created_at": "2026-02-06T14:30:00Z",
  "completed_at": "2026-02-06T14:30:03Z",
  "result": {
    "observables_stored": 125,
    "enrichments_applied": 3
  }
}
```

---

## Success Criteria

### Functional Requirements

1. **API Responsiveness**
   - POST /submit returns within 200ms (p95)
   - Immediate task ID returned to client
   - Backward compatibility: clients can opt-in to async mode

2. **Task Status Tracking**
   - GET /tasks/{task_id} endpoint for status checking
   - Task states: pending, processing, completed, failed
   - Progress updates for long-running tasks (optional)

3. **Reliability**
   - Failed tasks automatically retried (3 attempts)
   - Exponential backoff between retries
   - Dead letter queue for permanently failed tasks
   - All operations idempotent

4. **Observability**
   - Task queue depth metrics (CloudWatch)
   - Processing time per task
   - Success/failure rates
   - Alerting for queue backup (>1000 tasks)

### Non-Functional Requirements

1. **Performance**
   - Process 1000 tasks/minute (normal load)
   - Support burst to 5000 tasks/minute
   - Queue depth < 100 tasks during normal operation

2. **Scalability**
   - Lambda concurrency scales to 100 workers
   - SQS supports unlimited queue depth
   - No single point of contention

3. **Cost**
   - AWS costs < $50/month for 10K submissions/day
   - Efficient batch processing to reduce Lambda invocations

4. **Developer Experience**
   - Local development works without AWS
   - Tests can mock async processing
   - Clear error messages for task failures

---

## Constraints and Dependencies

### Hard Constraints

1. **Backward Compatibility**
   - Existing synchronous /submit must continue working
   - Clients opt-in to async mode via header or query param
   - Response format must be distinguishable (201 vs 202)

2. **Stage 1 Support**
   - Must work in local development (SQLite)
   - Cannot require AWS services in Stage 1
   - Fallback to synchronous mode if no queue available

3. **Security**
   - Task IDs must not be guessable (UUIDs)
   - Task status requires authentication
   - Cannot query other users' tasks

### Soft Constraints

1. **Implementation Timeline**
   - Proof of concept: 1 week
   - Stage 1 implementation: 1 week
   - Stage 3 (AWS) implementation: 1 week
   - Testing and documentation: 1 week

2. **Resource Constraints**
   - No additional infrastructure for Stage 1/2
   - AWS costs must stay under $100/month
   - Team bandwidth: 2-3 engineers

### Dependencies

**Upstream**:
- ✅ Submission model already supports batch observables
- ✅ Database abstraction already supports bulk writes
- ✅ Authentication system works for task status endpoints

**Downstream**:
- 🔄 Enrichment pipeline will build on task system
- 🔄 Report generation will use task scheduling
- 🔄 Bulk export will leverage async processing

---

## Alternative Approaches Considered

### Alternative 1: HTTP Long Polling

**Description**: Keep HTTP connection open and stream status updates

**Pros**:
- No polling required from client
- Real-time status updates
- Simple client implementation

**Cons**:
- Holds server resources (connection pool)
- Doesn't solve scalability issue
- Difficult to implement with ALB timeout (30s)
- Breaks with reverse proxies

**Decision**: ❌ Rejected - doesn't solve core scalability problem

---

### Alternative 2: WebSockets

**Description**: Persistent WebSocket connection for real-time updates

**Pros**:
- True real-time status updates
- Efficient for multiple submissions
- Modern, user-friendly

**Cons**:
- Significant additional complexity
- Requires WebSocket infrastructure (API Gateway Websockets)
- Overkill for this use case
- Not needed for service accounts (batch processing)

**Decision**: ❌ Rejected - too complex for current needs, revisit in Stage 4

---

### Alternative 3: Inline Processing with Streaming Response

**Description**: Process synchronously but stream progress updates

**Pros**:
- No task queue infrastructure
- Simple implementation
- Works in all stages

**Cons**:
- Still blocks HTTP connection
- Doesn't improve scalability
- Limited to 30-second ALB timeout
- Client must handle streaming

**Decision**: ❌ Rejected - doesn't solve timeout issues

---

### Alternative 4: Celery + Redis (Recommended Alternative)

**Description**: Use Celery task queue with Redis backend

**Pros**:
- Mature, well-tested ecosystem
- Rich feature set (workflows, scheduling, retries)
- Works locally and in cloud
- Python-native, easy to integrate

**Cons**:
- Requires Redis infrastructure
- More complex than SQS for simple use case
- Additional service to monitor and maintain

**Decision**: ⚠️ Consider for Stage 4 - better for complex workflows, overkill for Stage 3

---

## Implementation Timeline

### Phase 1: Proof of Concept (1 week)

**Goal**: Validate approach with minimal implementation

**Deliverables**:
- In-memory task queue in FastAPI
- Basic task status endpoint
- Demo with 10 concurrent submissions
- Performance benchmarks (API response time)

**Success Criteria**:
- POST /submit returns < 200ms
- Tasks process in background
- Status polling works

---

### Phase 2: Stage 1 Implementation (1 week)

**Goal**: Full local development support

**Deliverables**:
- Task model (SQLite storage)
- Worker thread pool for processing
- Retry logic with exponential backoff
- Unit tests (≥85% coverage)
- Integration tests (BDD scenarios)

**Success Criteria**:
- Works without AWS dependencies
- Handles failed tasks gracefully
- Tests pass in CI/CD

---

### Phase 3: Stage 3 (AWS) Implementation (1 week)

**Goal**: Production-ready cloud deployment

**Deliverables**:
- SQS queue creation (Ansible)
- Lambda function for task processing
- CloudWatch metrics and alarms
- Dead letter queue
- Task status in DynamoDB

**Success Criteria**:
- Handles 1000 tasks/minute
- Auto-scales to 100 workers
- Costs < $50/month for 10K submissions/day

---

### Phase 4: Testing and Documentation (1 week)

**Goal**: Production readiness

**Deliverables**:
- Load testing (10K submissions)
- Failure scenario testing (DynamoDB unavailable)
- Client SDK updates (Python, JavaScript)
- API documentation updates
- ADR documenting decision

**Success Criteria**:
- All tests pass
- Documentation complete
- Ready for production deployment

---

## Risk Assessment

### High Risk

**Risk**: Lambda cold starts cause inconsistent processing times
- **Impact**: First submission after quiet period takes 5s instead of 1s
- **Mitigation**: Keep 5 warm Lambda instances with provisioned concurrency
- **Cost**: $20/month for 5 warm instances

**Risk**: DynamoDB throttling during high volume
- **Impact**: Task status updates fail, clients see stale status
- **Mitigation**: Use on-demand capacity mode, implement exponential backoff
- **Cost**: Higher DynamoDB costs during spikes ($10-30/month)

### Medium Risk

**Risk**: Task queue grows unbounded during outage
- **Impact**: 1M+ tasks queued, takes hours to process backlog
- **Mitigation**: Set SQS retention to 4 hours, alert on queue depth > 1000
- **Cost**: None (queue management is free)

**Risk**: Clients don't handle async mode correctly
- **Impact**: Clients treat 202 Accepted as success, don't poll for status
- **Mitigation**: Comprehensive client SDK updates, clear documentation, gradual rollout
- **Cost**: Developer time for client updates

### Low Risk

**Risk**: Task ID collision (UUID)
- **Impact**: Status returned for wrong task
- **Mitigation**: Use UUID v4, probability of collision is negligible (2^-128)
- **Cost**: None

---

## Success Metrics

### Performance Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| API response time (p95) | 5000ms | 200ms | CloudWatch |
| Max submission size | 50 observables | 10,000 observables | Load test |
| Throughput | 100 submissions/min | 1000 submissions/min | CloudWatch |
| Queue depth (p95) | N/A | < 100 tasks | CloudWatch |

### Business Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Timeout errors | 5% | < 0.1% | Error logs |
| User satisfaction | 6/10 | 8/10 | Survey |
| Service account adoption | 10 orgs | 25 orgs | Database |
| Bulk submissions/day | 0 | 100+ | Metrics |

---

## Open Questions

1. **Backward Compatibility Strategy**
   - Should sync mode remain the default?
   - Should we deprecate sync mode in future versions?
   - How long to support both modes?

2. **Client SDK Updates**
   - Which clients need updates? (Python, JavaScript, CLI)
   - Should we provide automatic polling helper functions?
   - How to handle different client versions?

3. **Retry Policy**
   - How many retries? (Proposed: 3 attempts)
   - Backoff strategy? (Proposed: exponential with jitter)
   - When to give up and move to dead letter queue?

4. **Cost Optimization**
   - Is batch processing worth the added complexity?
   - Should we use Lambda reserved concurrency?
   - What's acceptable cost per 1M submissions?

5. **Stage 2 Implementation**
   - Do we need full async support in LocalStack?
   - Or is Stage 1 (local) + Stage 3 (AWS) enough?
   - Worth implementing Celery for Stage 2?

---

## Next Steps

1. **Review and Approval**
   - Architecture team review (this proposal)
   - Security team review (task ID security, auth)
   - Product team approval (UX changes)

2. **Spike Implementation**
   - Create spike: `tests/spikes/016_background_tasks/`
   - Implement proof of concept
   - Benchmark performance improvements
   - Validate approach

3. **Create Detailed Specifications**
   - specs/changes/001-background-tasks/spec.md
   - specs/changes/001-background-tasks/design.md
   - specs/changes/001-background-tasks/tasks.md
   - specs/changes/001-background-tasks/adr.md

4. **Begin Implementation**
   - Phase 1: Proof of concept (1 week)
   - Phase 2: Stage 1 implementation (1 week)
   - Phase 3: AWS implementation (1 week)
   - Phase 4: Testing and documentation (1 week)

---

**Proposal Status**: Draft - awaiting architecture review
**Target Decision Date**: 2026-02-13
**Implementation Start**: 2026-02-20 (if approved)

**Related ADR**: [ADR-0013: Asynchronous Background Task Processing](../../../docs/adr/0013-asynchronous-background-task-processing.md)
