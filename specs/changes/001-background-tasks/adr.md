# ADR 001: Asynchronous Background Task Processing

**Status**: Proposed
**Date**: 2026-02-06
**Decision Makers**: Architecture Team, Backend Team
**Related Changes**: Proposal 001 - Background Task Processing System

---

## Context

FRANK currently processes all threat intelligence submissions synchronously within the HTTP request/response cycle. This creates several problems:

1. **Poor API Responsiveness**: Large submissions (100+ observables) take 5-10 seconds, blocking HTTP connections
2. **Timeout Issues**: Bulk submissions (500+ observables) exceed the 30-second ALB timeout
3. **Scalability Limitations**: ECS tasks scale based on HTTP request rate, not actual processing workload
4. **Future Feature Blockers**: Cannot add enrichment steps (external API calls), ML inference, or automated reporting
5. **Poor User Experience**: Service accounts experience frequent timeouts; human users see long "spinning wheel" delays

**Business Impact**:
- Service accounts report frustration with timeout errors during bulk ingestion
- Cannot onboard high-volume partners (>10K submissions/day)
- Modern threat intelligence platforms already offer async processing
- Synchronous processing limits future feature development

**Technical Context**:
- Current: FastAPI processes submissions inline during POST /submit
- Stage 1: SQLite with thread pool executor
- Stage 3: AWS ECS Fargate + DynamoDB
- Stage 4: Kubernetes with complex orchestration needs

---

## Decision

We will implement **asynchronous background task processing** using a two-phase submission flow:

### Phase 1: Immediate Acceptance
```
Client → POST /submit (X-Async: true) → API validates → Queue task → Return 202 Accepted
                                                                   ↓
                                                           {task_id, status_url}
```

### Phase 2: Background Processing
```
Task Queue → Worker → Process submission → Store in DB → Update task status
                                                       ↓
Client → GET /tasks/{task_id} → Return status (pending/processing/completed/failed)
```

### Technology Selection by Stage

**Stage 1 (Local Development)**: In-memory task queue
- Python `queue.Queue` with `ThreadPoolExecutor`
- Runs in same process as API server
- No external dependencies
- Simple for rapid development and testing

**Stage 3 (AWS Cloud)**: SQS + Lambda
- AWS SQS FIFO queue for task ordering
- Lambda functions for task processing
- DynamoDB for task status storage
- Native AWS integration with auto-scaling
- Dead letter queue for failed tasks

**Stage 4 (Kubernetes)**: Celery + Redis (future consideration)
- More flexible for complex workflows
- Better task chaining and scheduling
- Cross-platform compatibility
- Required when moving off AWS-specific services

### API Changes

**New Endpoints**:
- `GET /tasks/{task_id}` - Retrieve task status and results
- `GET /tasks` - List user's tasks with filtering

**Modified Endpoints**:
- `POST /submit` - Returns 202 Accepted (async) or 201 Created (sync) based on `X-Async` header

**Backward Compatibility**:
- Synchronous mode remains default (without `X-Async` header)
- Existing clients continue working unchanged
- Clients opt-in to async mode explicitly

---

## Alternatives Considered

### Alternative 1: HTTP Long Polling

**Description**: Keep HTTP connection open and stream status updates using chunked transfer encoding.

**Pros**:
- No polling required from client
- Real-time status updates
- Simpler client implementation (single request)

**Cons**:
- Holds server resources (connection pool, memory)
- Doesn't solve scalability issue (still blocking connections)
- Difficult to implement with ALB 30-second timeout
- Breaks with many reverse proxies and CDNs
- Cannot recover from network interruptions

**Decision**: ❌ **Rejected** - Doesn't solve the core scalability problem. Still blocks resources and doesn't allow us to scale processing independently from API servers.

---

### Alternative 2: WebSockets

**Description**: Establish persistent WebSocket connection for real-time bidirectional communication.

**Pros**:
- True real-time status updates
- Efficient for multiple submissions from same client
- Modern, user-friendly experience
- Low latency for status changes

**Cons**:
- Significant additional complexity (API Gateway WebSockets, connection management)
- Requires WebSocket infrastructure and state management
- Overkill for batch processing use case
- Not needed for service accounts (prefer simple polling)
- Connection state management increases complexity
- Difficult to implement in Stage 1 (local development)

**Decision**: ❌ **Rejected** - Too complex for current needs. May revisit in Stage 4 if real-time updates become a priority user requirement.

---

### Alternative 3: Inline Processing with Streaming Response

**Description**: Process synchronously but stream progress updates using Server-Sent Events (SSE).

**Pros**:
- No task queue infrastructure needed
- Relatively simple implementation
- Works in all stages (no AWS dependencies)
- Client receives progress updates

**Cons**:
- Still blocks HTTP connection during processing
- Doesn't improve scalability (processing tied to API server capacity)
- Limited by 30-second ALB timeout
- Client must handle streaming response format
- Cannot retry failed operations
- No visibility into queue depth or backlog

**Decision**: ❌ **Rejected** - Doesn't solve timeout issues or enable independent scaling of processing workers.

---

### Alternative 4: Celery + Redis

**Description**: Use Celery distributed task queue with Redis as message broker and result backend.

**Pros**:
- Mature, battle-tested ecosystem (10+ years)
- Rich feature set: task chaining, workflows, periodic tasks, retries
- Works locally and in cloud (platform-agnostic)
- Python-native with excellent FastAPI integration
- Strong monitoring tools (Flower, Celery Events)
- Supports complex task dependencies and DAGs

**Cons**:
- Requires Redis infrastructure (additional service to manage)
- More complex than SQS for simple use case (point-to-point queuing)
- Operational overhead: Redis persistence, replication, monitoring
- Additional cost for managed Redis (AWS ElastiCache ~$50-100/month)
- Not serverless (requires worker processes running continuously)

**Decision**: ⚠️ **Consider for Stage 4** - Better fit when we need:
- Complex workflows (enrichment pipelines with multiple stages)
- Task chaining (submission → enrichment → scoring → reporting)
- Scheduled periodic tasks (daily reports, cleanup jobs)
- Platform-agnostic deployment (moving to Kubernetes)

For Stage 3, SQS + Lambda is simpler, serverless, and sufficient for basic async processing.

---

### Alternative 5: Do Nothing (Optimize Synchronous Processing)

**Description**: Keep synchronous processing but optimize database writes and observable parsing.

**Pros**:
- No architectural changes needed
- Simplest implementation (just performance tuning)
- No new infrastructure

**Cons**:
- Cannot solve fundamental timeout problem (30-second hard limit)
- Cannot support bulk submissions (>1000 observables)
- Blocks future features requiring external API calls or ML inference
- Doesn't address scalability concerns
- Processing still coupled to API server capacity

**Decision**: ❌ **Rejected** - Performance optimization alone cannot overcome 30-second timeout limit or enable future features like enrichment pipelines.

---

## Consequences

### Positive

1. **Improved API Responsiveness**
   - POST /submit returns in < 200ms (vs 5-10 seconds)
   - HTTP connections released immediately
   - Better user experience for all clients

2. **Bulk Ingestion Support**
   - Service accounts can submit up to 10,000 observables per request
   - No need for manual batching logic in client scripts
   - Reduced network overhead (fewer HTTP requests)

3. **Independent Scaling**
   - Processing workers scale independently from API servers
   - Lambda auto-scales to 100 workers based on queue depth
   - Better resource utilization during traffic spikes

4. **Reliability Improvements**
   - Automatic retries with exponential backoff (3 attempts)
   - Dead letter queue for permanently failed tasks
   - Visibility into processing queue depth and backlog

5. **Foundation for Future Features**
   - Can add enrichment steps (MITRE ATT&CK mapping, threat scoring)
   - Can implement ML inference for threat classification
   - Can generate automated reports without blocking API
   - Can support scheduled tasks (daily summaries, cleanup)

6. **Observability**
   - CloudWatch metrics for queue depth, processing time, success rates
   - Alerts for queue backup (>1000 tasks)
   - Task-level tracing and debugging

### Negative

1. **Increased Complexity**
   - New task management subsystem to maintain
   - Task status polling logic in clients
   - Additional database tables for task storage
   - More moving parts to monitor and debug

2. **Client Changes Required**
   - Service accounts must implement polling logic
   - Client SDKs need updates (Python, JavaScript)
   - Documentation must explain async vs sync modes
   - Migration path for existing integrations

3. **Operational Overhead**
   - SQS queue to monitor and manage
   - Lambda cold start considerations (provisioned concurrency)
   - DynamoDB capacity planning for task status
   - Dead letter queue processing and investigation

4. **Cost Increase**
   - AWS costs estimated at $50-100/month for 10K submissions/day:
     - SQS: ~$5/month (1M requests)
     - Lambda: ~$20-30/month (compute time)
     - Provisioned concurrency: ~$20/month (5 warm instances)
     - DynamoDB: ~$15/month (task status storage)

5. **Eventual Consistency**
   - Task status updates are eventually consistent
   - Clients must handle stale status responses
   - Race conditions possible (task completed but status not updated)

6. **Stage 1 Limitations**
   - In-memory queue lost on server restart
   - No persistence for pending tasks
   - Limited to single-process scaling
   - Not suitable for production use

### Neutral

1. **Backward Compatibility Maintained**
   - Synchronous mode remains available
   - Existing clients work unchanged
   - Gradual migration path for service accounts

2. **Technology Lock-in (Stage 3)**
   - SQS + Lambda ties Stage 3 to AWS
   - Migration to Celery + Redis required for Stage 4 (Kubernetes)
   - Abstraction layer helps minimize impact

3. **Learning Curve**
   - Team must learn async patterns and SQS/Lambda
   - New testing strategies for async operations
   - Different debugging approaches for distributed systems

---

## Implementation Notes

### Phased Rollout Strategy

**Phase 1: Proof of Concept (1 week)**
- Validate approach with in-memory queue
- Benchmark performance improvements
- Demo async flow with 10 concurrent submissions

**Phase 2: Stage 1 Implementation (1 week)**
- Full local development support with SQLite
- Worker thread pool for processing
- Retry logic with exponential backoff
- Unit tests (≥85% coverage)

**Phase 3: AWS Implementation (1 week)**
- SQS queue creation (Ansible)
- Lambda function for task processing
- CloudWatch metrics and alarms
- Dead letter queue configuration

**Phase 4: Testing and Documentation (1 week)**
- Load testing (10K submissions)
- Failure scenario testing (DynamoDB unavailable, Lambda timeout)
- Client SDK updates
- API documentation updates

### Success Criteria

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| API response time (p95) | 5000ms | 200ms | CloudWatch |
| Max submission size | 50 observables | 10,000 observables | Load test |
| Throughput | 100 submissions/min | 1000 submissions/min | CloudWatch |
| Queue depth (p95) | N/A | < 100 tasks | CloudWatch |
| Timeout errors | 5% | < 0.1% | Error logs |

### Risk Mitigation

**Risk**: Lambda cold starts cause inconsistent processing times
**Mitigation**: Keep 5 warm Lambda instances with provisioned concurrency ($20/month)

**Risk**: DynamoDB throttling during high volume
**Mitigation**: Use on-demand capacity mode, implement exponential backoff

**Risk**: Task queue grows unbounded during outage
**Mitigation**: Set SQS retention to 4 hours, alert on queue depth > 1000

**Risk**: Clients don't handle async mode correctly
**Mitigation**: Comprehensive SDK updates, clear documentation, gradual rollout with metrics

---

## Related Decisions

- **ADR 002** (future): Enrichment pipeline architecture using task chaining
- **ADR 003** (future): Migration from SQS to Celery for Stage 4
- **ADR 004** (future): Task scheduling and periodic job execution

---

## References

- Proposal 001: Background Task Processing System
- Spec 001: Functional and Non-Functional Requirements
- Design 001: Technical Architecture and Implementation Details
- Tasks 001: Implementation Task Breakdown (25 tasks, 15 days)
- Spike 006: DynamoDB Integration Patterns
- Spike 009: AWS ECS Basic Deployment
- AWS SQS Documentation: https://docs.aws.amazon.com/sqs/
- AWS Lambda Documentation: https://docs.aws.amazon.com/lambda/
- Celery Documentation: https://docs.celeryq.dev/

---

## Decision Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-06 | Proposal created | Initial draft for architecture review |
| 2026-02-13 | Architecture review | Target decision date |
| 2026-02-20 | Implementation start | If approved |
| 2026-03-15 | Production deployment | Estimated completion (4 weeks) |

---

**ADR Status**: Proposed - awaiting architecture review and approval
