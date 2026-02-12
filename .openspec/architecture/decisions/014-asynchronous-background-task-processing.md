# Asynchronous Background Task Processing

- **Status:** Proposed
- **Date:** 2026-02-06
- **Decision Makers:** Architecture Team, Backend Team
- **Related:** [Change Proposal 001](../../specs/changes/001-background-tasks/proposal.md)

---

## Context and Problem Statement

FRANK currently processes all threat intelligence submissions synchronously within the HTTP request/response cycle. This creates significant problems for both service accounts and human users:

**Current Pain Points**:
- Large submissions (100+ observables) take 5-10 seconds, blocking HTTP connections
- Bulk submissions (500+ observables) exceed 30-second ALB timeout
- Service accounts must implement complex batching and retry logic
- Cannot add enrichment steps (external API calls, ML inference)
- ECS tasks scale on HTTP rate, not processing workload

**Business Impact**:
- Cannot onboard high-volume partners (>10K submissions/day)
- Service accounts report frustration with timeout errors
- Blocks future features (enrichment pipelines, automated reporting)
- Poor competitive position vs modern threat intelligence platforms

## Decision Drivers

- **API Responsiveness**: Need <200ms response time for submission acceptance
- **Bulk Ingestion**: Support up to 10,000 observables per submission
- **Future Features**: Enable enrichment pipelines and scheduled tasks
- **Scalability**: Independent scaling of API and processing workers
- **Stage Compatibility**: Must work across all FRANK stages (local → AWS → Kubernetes)
- **Backward Compatibility**: Existing synchronous clients continue working
- **Cost**: Keep AWS costs under $100/month for 10K submissions/day

## Considered Options

- **Option 1**: Asynchronous Task Queue (AWS SQS + Lambda for Stage 3)
- **Option 2**: HTTP Long Polling (keep connection open, stream updates)
- **Option 3**: WebSockets (persistent bidirectional connection)
- **Option 4**: Inline Processing with Streaming Response (SSE)
- **Option 5**: Celery + Redis (alternative distributed task queue)

## Decision Outcome

Chosen option: "**Option 1: Asynchronous Task Queue (SQS + Lambda)**", because it solves core scalability problems, enables future features, and provides clear separation between API and processing layers.

**Implementation**:
- Stage 1: In-memory `queue.Queue` with `ThreadPoolExecutor`
- Stage 3: AWS SQS FIFO queue + Lambda workers
- Stage 4: Consider migrating to Celery + Redis for complex workflows

**API Changes**:
- New: `GET /tasks/{task_id}` (retrieve task status)
- New: `GET /tasks` (list user tasks)
- Modified: `POST /submit` returns 202 Accepted with `X-Async: true` header

### Positive Consequences

- **10x API Responsiveness**: POST /submit returns in <200ms (vs 5-10 seconds)
- **Bulk Ingestion**: Support 10,000 observables per submission
- **Independent Scaling**: Processing workers scale separately from API servers
- **Reliability**: Automatic retries with exponential backoff (3 attempts)
- **Visibility**: CloudWatch metrics for queue depth, processing time, success rates
- **Foundation**: Enables future enrichment pipelines and scheduled tasks

### Negative Consequences

- **Increased Complexity**: New task management subsystem to maintain
- **Client Changes**: Service accounts must implement polling logic
- **Eventual Consistency**: Task status updates are eventually consistent
- **Operational Overhead**: SQS queue, Lambda cold starts, DynamoDB capacity planning
- **Cost Increase**: $50-100/month AWS costs (SQS, Lambda, provisioned concurrency, DynamoDB)
- **Stage 1 Limitations**: In-memory queue lost on server restart

## Pros and Cons of the Options

### Option 1: Asynchronous Task Queue (SQS + Lambda)

AWS SQS FIFO queue for task ordering with Lambda workers for processing.

- Good, because solves timeout problem completely (30-second limit doesn't apply)
- Good, because enables independent scaling (API vs processing workers)
- Good, because provides retry mechanism with dead letter queue
- Good, because enables visibility into queue depth and processing backlog
- Good, because foundation for future features (enrichment, ML inference, reporting)
- Good, because serverless Lambda reduces operational overhead
- Bad, because adds infrastructure complexity (SQS, Lambda, DynamoDB for status)
- Bad, because requires client changes (polling for status)
- Bad, because eventual consistency (status updates lag actual completion)
- Bad, because Lambda cold starts can add 1-5 second latency
- Bad, because AWS-specific (Stage 3 only, migration needed for Stage 4 Kubernetes)

### Option 2: HTTP Long Polling

Keep HTTP connection open and stream status updates.

- Good, because no polling required from client
- Good, because real-time status updates
- Good, because simpler client implementation (single request)
- Bad, because still holds server resources (connection pool, memory)
- Bad, because doesn't solve scalability issue (processing still tied to API capacity)
- Bad, because difficult with ALB 30-second timeout
- Bad, because breaks with many reverse proxies and CDNs
- Bad, because cannot recover from network interruptions

**Decision**: ❌ Rejected - doesn't solve core scalability problem

### Option 3: WebSockets

Establish persistent WebSocket connection for bidirectional communication.

- Good, because true real-time status updates with low latency
- Good, because efficient for multiple submissions from same client
- Good, because modern, user-friendly experience
- Bad, because significant additional complexity (API Gateway WebSockets, connection state management)
- Bad, because overkill for batch processing use case
- Bad, because not needed for service accounts (prefer simple polling)
- Bad, because difficult to implement in Stage 1 (local development)

**Decision**: ❌ Rejected - too complex for current needs, may revisit in Stage 4

### Option 4: Inline Processing with Streaming Response

Process synchronously but stream progress updates using Server-Sent Events (SSE).

- Good, because no task queue infrastructure needed
- Good, because relatively simple implementation
- Good, because works in all stages (no AWS dependencies)
- Good, because client receives progress updates
- Bad, because still blocks HTTP connection during processing
- Bad, because doesn't improve scalability (processing tied to API capacity)
- Bad, because limited by 30-second ALB timeout
- Bad, because client must handle streaming response format
- Bad, because cannot retry failed operations

**Decision**: ❌ Rejected - doesn't solve timeout issues or enable independent scaling

### Option 5: Celery + Redis

Use Celery distributed task queue with Redis as message broker.

- Good, because mature, battle-tested ecosystem (10+ years)
- Good, because rich feature set (task chaining, workflows, periodic tasks, retries)
- Good, because works locally and in cloud (platform-agnostic)
- Good, because strong monitoring tools (Flower, Celery Events)
- Good, because supports complex task dependencies and DAGs
- Bad, because requires Redis infrastructure (additional service to manage)
- Bad, because more complex than SQS for simple point-to-point queuing
- Bad, because operational overhead (Redis persistence, replication, monitoring)
- Bad, because additional cost (AWS ElastiCache ~$50-100/month)
- Bad, because not serverless (requires worker processes running continuously)

**Decision**: ⚠️ Consider for Stage 4 when we need complex workflows (enrichment pipelines with multiple stages, task chaining, scheduled periodic tasks) and platform-agnostic deployment (Kubernetes)

## Related Specifications

- **Originating Spec**: [Change Proposal 001: Background Task Processing](../../specs/changes/001-background-tasks/proposal.md) - Full problem statement and business case
- **Design Document**: [Design Doc](../../specs/changes/001-background-tasks/design.md) - Technical architecture and implementation details
- **Requirements Spec**: [Functional/Non-Functional Requirements](../../specs/changes/001-background-tasks/spec.md)
- **Implementation Tasks**: [Task Breakdown](../../specs/changes/001-background-tasks/tasks.md) - 25 tasks across 4 phases (15 days)
- **Implementing Specs**: [To be added after implementation]
- **Impacted Specs**:
  - [Sightings API Spec](../../specs/apis/sightings-api.spec.md) - Will add async mode
  - [Management API Spec](../../specs/apis/management-api.spec.md) - Task status endpoints

## References

- [Change Proposal 001](../../specs/changes/001-background-tasks/) - Complete proposal package
- [AWS SQS Documentation](https://docs.aws.amazon.com/sqs/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Celery Documentation](https://docs.celeryq.dev/) - Alternative for Stage 4

---

**Document Status**: Proposed - awaiting architecture review and approval

**Target Decision Date**: 2026-02-13

**Implementation Start**: 2026-02-20 (if approved)
