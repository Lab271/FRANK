# Specification: Background Task Processing System

## Metadata

| Attribute | Value |
|-----------|-------|
| **Spec ID** | CHANGE-001-SPEC |
| **Status** | Draft |
| **Version** | 1.0 |
| **Related Proposal** | [proposal.md](proposal.md) |
| **Related Design** | [design.md](design.md) |
| **Target Version** | 0.3.0 |

---

## Purpose

Define the functional and non-functional requirements for asynchronous background task processing in the FRANK platform. This specification documents the API contracts, data models, and behavior for submitting, processing, and monitoring background tasks.

---

## Functional Requirements

### FR1: Asynchronous Submission Acceptance

**Requirement**: Accept threat intelligence submissions asynchronously and return immediately with task tracking information.

**Acceptance Criteria**:
- POST /submit with `X-Async: true` header returns 202 Accepted (not 201 Created)
- Response includes task_id, submission_id, status, and status_url
- Response time < 200ms (p95)
- Request validation happens synchronously (bad requests return 422 immediately)
- JWT authentication and access tier checks happen synchronously
- Task queued successfully before response sent

**API Contract**:
```
POST /submit
Headers:
  Authorization: Bearer <jwt>
  X-Async: true           # Enables async mode

Request Body:
{
  "observables": [...],
  "confidence_score": 0.85,
  "severity": "HIGH"
}

Response (202 Accepted):
{
  "task_id": "task-a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "submission_id": "submission--...",
  "status": "pending",
  "status_url": "/tasks/task-a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "created_at": "2026-02-06T14:30:00Z"
}
```

---

### FR2: Task Status Retrieval

**Requirement**: Allow clients to poll task status and retrieve results when complete.

**Acceptance Criteria**:
- GET /tasks/{task_id} returns current task status
- Requires JWT authentication (same user who created task, or CORE_MEMBER)
- Status values: pending, processing, completed, failed
- Completed tasks include result details (observables stored, processing time)
- Failed tasks include error message and retry count
- Task status cached for 5 minutes after completion
- Old tasks (>7 days) automatically purged

**API Contract**:
```
GET /tasks/{task_id}
Headers:
  Authorization: Bearer <jwt>

Response (200 OK) - Pending:
{
  "task_id": "task-...",
  "status": "pending",
  "submission_id": "submission--...",
  "created_at": "2026-02-06T14:30:00Z",
  "updated_at": "2026-02-06T14:30:00Z"
}

Response (200 OK) - Processing:
{
  "task_id": "task-...",
  "status": "processing",
  "submission_id": "submission--...",
  "created_at": "2026-02-06T14:30:00Z",
  "updated_at": "2026-02-06T14:30:01Z",
  "progress": {
    "observables_processed": 45,
    "observables_total": 125
  }
}

Response (200 OK) - Completed:
{
  "task_id": "task-...",
  "status": "completed",
  "submission_id": "submission--...",
  "created_at": "2026-02-06T14:30:00Z",
  "updated_at": "2026-02-06T14:30:03Z",
  "completed_at": "2026-02-06T14:30:03Z",
  "result": {
    "observables_stored": 125,
    "sightings_created": 1,
    "processing_time_ms": 2847
  }
}

Response (200 OK) - Failed:
{
  "task_id": "task-...",
  "status": "failed",
  "submission_id": "submission--...",
  "created_at": "2026-02-06T14:30:00Z",
  "updated_at": "2026-02-06T14:30:05Z",
  "failed_at": "2026-02-06T14:30:05Z",
  "error": {
    "code": "DATABASE_UNAVAILABLE",
    "message": "DynamoDB connection timeout after 3 retries",
    "retry_count": 3,
    "retriable": false
  }
}

Response (404 Not Found):
{
  "detail": "Task not found: task-..."
}

Response (403 Forbidden):
{
  "detail": "Cannot access task created by another user"
}
```

---

### FR3: List User Tasks

**Requirement**: Allow users to list their tasks with filtering.

**Acceptance Criteria**:
- GET /tasks endpoint lists all user's tasks
- Supports filtering by status (pending, processing, completed, failed)
- Supports pagination (limit, offset)
- Supports date range filtering
- Returns most recent tasks first (DESC order)
- CORE_MEMBER can list all tasks (all users)

**API Contract**:
```
GET /tasks?status=completed&limit=50&offset=0
Headers:
  Authorization: Bearer <jwt>

Response (200 OK):
{
  "tasks": [
    {
      "task_id": "task-...",
      "status": "completed",
      "submission_id": "submission--...",
      "created_at": "2026-02-06T14:30:00Z",
      "completed_at": "2026-02-06T14:30:03Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

### FR4: Automatic Task Retry

**Requirement**: Automatically retry failed tasks with exponential backoff.

**Acceptance Criteria**:
- Transient failures (DynamoDB throttling, network timeout) trigger retry
- Maximum 3 retry attempts
- Exponential backoff: 10s, 30s, 90s
- Jitter added to prevent thundering herd (±20% variance)
- Permanent failures (validation error, auth error) not retried
- Retry count tracked in task status
- After 3 failures, task moved to "failed" status
- Dead letter queue captures permanently failed tasks

**Retry Logic**:
```python
def should_retry(error: Exception, retry_count: int) -> bool:
    if retry_count >= 3:
        return False

    # Retriable errors
    if isinstance(error, (DatabaseTimeout, ThrottlingError)):
        return True

    # Non-retriable errors
    if isinstance(error, (ValidationError, AuthError)):
        return False

    return False

def calculate_backoff(retry_count: int) -> int:
    base_delay = 10 * (3 ** retry_count)  # 10s, 30s, 90s
    jitter = random.uniform(-0.2, 0.2)    # ±20%
    return int(base_delay * (1 + jitter))
```

---

### FR5: Task Cancellation

**Requirement**: Allow users to cancel pending or processing tasks.

**Acceptance Criteria**:
- DELETE /tasks/{task_id} cancels task
- Can only cancel own tasks (or CORE_MEMBER can cancel any)
- Can only cancel tasks in "pending" or "processing" status
- Completed or failed tasks cannot be cancelled
- Returns 204 No Content on success
- Processing tasks gracefully stop (no partial writes)

**API Contract**:
```
DELETE /tasks/{task_id}
Headers:
  Authorization: Bearer <jwt>

Response (204 No Content)

Response (400 Bad Request):
{
  "detail": "Cannot cancel task in 'completed' status"
}

Response (404 Not Found):
{
  "detail": "Task not found"
}
```

---

### FR6: Backward Compatibility (Synchronous Mode)

**Requirement**: Support existing synchronous /submit behavior when async mode not requested.

**Acceptance Criteria**:
- POST /submit without X-Async header works as before (synchronous)
- Returns 201 Created with full submission data
- Response time matches current behavior (2-5 seconds)
- No task tracking for synchronous submissions
- Clients can opt-in to async mode at their convenience

**API Contract**:
```
POST /submit
Headers:
  Authorization: Bearer <jwt>
  # No X-Async header = synchronous mode

Request Body:
{
  "observables": [...],
  "confidence_score": 0.85
}

Response (201 Created):
{
  "submission_id": "submission--...",
  "timestamp": "2026-02-06T14:30:00Z",
  "status": "accepted",
  "message": "Submission accepted with 125 observables"
}
```

---

## Non-Functional Requirements

### NFR1: Performance

**Requirement**: System must meet performance targets under normal and peak load.

**Acceptance Criteria**:
- API response time < 200ms (p95) for async submission acceptance
- Process 1000 tasks/minute under normal load
- Support burst to 5000 tasks/minute for 5 minutes
- Task status retrieval < 100ms (p95)
- Queue depth < 100 tasks during normal operation (p95)
- < 50ms additional latency for async vs sync validation

**Load Test Scenarios**:
```yaml
Scenario 1: Normal Load
  - 1000 submissions/minute
  - 100 observables per submission
  - Duration: 1 hour
  - Expected: 0 errors, queue depth < 50

Scenario 2: Burst Load
  - 5000 submissions/minute
  - 50 observables per submission
  - Duration: 5 minutes
  - Expected: < 0.1% errors, queue depth < 500

Scenario 3: Large Submissions
  - 10 submissions/minute
  - 10,000 observables per submission
  - Duration: 10 minutes
  - Expected: All complete, processing time < 30s each
```

---

### NFR2: Scalability

**Requirement**: System must scale horizontally to handle increased load.

**Acceptance Criteria**:
- Lambda workers scale from 5 to 100 instances automatically
- SQS queue supports unlimited depth
- DynamoDB auto-scales to handle write load
- No single point of contention
- Adding workers improves throughput linearly (up to 100 workers)

---

### NFR3: Reliability

**Requirement**: System must handle failures gracefully without data loss.

**Acceptance Criteria**:
- Zero data loss (all tasks eventually complete or marked failed)
- Idempotent operations (retrying doesn't cause duplicates)
- Graceful degradation if queue unavailable (fallback to sync mode)
- Database outages don't cause task loss (queue retains messages)
- Worker crashes don't lose tasks (SQS visibility timeout)
- Dead letter queue captures permanently failed tasks for investigation

**Failure Scenarios**:
```yaml
Scenario 1: DynamoDB Unavailable
  - Action: Stop DynamoDB
  - Expected: Tasks retry, succeed when DB returns
  - Recovery: < 5 minutes

Scenario 2: Worker Lambda Crashes
  - Action: Throw exception in worker
  - Expected: Task returns to queue, processed by another worker
  - Recovery: Immediate (next worker)

Scenario 3: Queue Service Outage
  - Action: SQS unavailable
  - Expected: API falls back to synchronous mode
  - Recovery: Automatic when SQS returns
```

---

### NFR4: Observability

**Requirement**: Provide visibility into task processing health and performance.

**Acceptance Criteria**:
- CloudWatch metrics: queue depth, processing time, success/failure rate
- CloudWatch alarms: queue depth > 1000, failure rate > 5%
- Structured logs: task lifecycle events (created, processing, completed, failed)
- Distributed tracing: correlation ID across API → queue → worker → DB
- Dashboard: real-time queue depth, throughput, error rate

**Metrics**:
```yaml
Metrics to Track:
  - frank.tasks.submitted (counter)
  - frank.tasks.processing_time_ms (histogram)
  - frank.tasks.queue_depth (gauge)
  - frank.tasks.success_count (counter)
  - frank.tasks.failure_count (counter)
  - frank.tasks.retry_count (counter)

Alarms:
  - Queue depth > 1000 for 5 minutes
  - Failure rate > 5% for 10 minutes
  - Processing time p95 > 10 seconds
  - Dead letter queue depth > 10
```

---

### NFR5: Cost Efficiency

**Requirement**: Keep AWS costs under budget while meeting performance targets.

**Acceptance Criteria**:
- Total cost < $100/month for 10K submissions/day
- Lambda cost < $50/month (with provisioned concurrency)
- SQS cost < $10/month
- DynamoDB cost < $40/month
- Batch processing reduces Lambda invocations where possible

**Cost Optimization**:
```yaml
Strategies:
  - Use Lambda reserved concurrency (5 warm instances)
  - Batch multiple tasks per Lambda invocation (up to 10)
  - DynamoDB on-demand capacity (no reserved capacity)
  - SQS standard queue (not FIFO, cheaper)
  - Purge completed tasks after 7 days
```

---

## Data Models

### Task Model (Database)

```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task(BaseModel):
    task_id: str = Field(..., description="UUID task identifier")
    user_id: str = Field(..., description="User who created task")
    organisation_id: str = Field(..., description="User's organisation")
    submission_id: str = Field(..., description="Associated submission ID")
    status: TaskStatus = Field(default=TaskStatus.PENDING)

    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None

    retry_count: int = Field(default=0, ge=0, le=3)
    error_message: Optional[str] = None
    error_code: Optional[str] = None

    # Task payload (submission request)
    payload: dict = Field(..., description="Submission request data")

    # Result (when completed)
    result: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task-a1b2c3d4-5678-90ab-cdef-1234567890ab",
                "user_id": "john.doe@rabobank.nl",
                "organisation_id": "identity--rabobank",
                "submission_id": "submission--...",
                "status": "completed",
                "created_at": "2026-02-06T14:30:00Z",
                "updated_at": "2026-02-06T14:30:03Z",
                "completed_at": "2026-02-06T14:30:03Z",
                "retry_count": 0,
                "payload": {...},
                "result": {
                    "observables_stored": 125,
                    "processing_time_ms": 2847
                }
            }
        }
```

### SQLite Schema (Stage 1)

```sql
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    organisation_id TEXT NOT NULL,
    submission_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    failed_at TEXT,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    error_code TEXT,
    payload_json TEXT NOT NULL,
    result_json TEXT,
    FOREIGN KEY (user_id) REFERENCES users(username)
);

CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX idx_tasks_submission_id ON tasks(submission_id);
```

### DynamoDB Schema (Stage 3)

```yaml
Table: frank-tasks
Partition Key: task_id (String)
Sort Key: created_at (Number, Unix timestamp)

Attributes:
  - task_id: String (task-{uuid})
  - user_id: String
  - organisation_id: String
  - submission_id: String
  - status: String (pending/processing/completed/failed/cancelled)
  - created_at: Number (Unix timestamp ms)
  - updated_at: Number (Unix timestamp ms)
  - started_at: Number (optional)
  - completed_at: Number (optional)
  - failed_at: Number (optional)
  - retry_count: Number
  - error_message: String (optional)
  - error_code: String (optional)
  - payload_json: String (JSON)
  - result_json: String (optional, JSON)
  - ttl: Number (created_at + 7 days, for auto-purge)

GSI-1: user_id (PK) + created_at (SK)  # List user's tasks
GSI-2: status (PK) + created_at (SK)   # List tasks by status
GSI-3: submission_id (PK)              # Find task by submission

TTL Attribute: ttl (auto-delete after 7 days)
```

---

## Test Coverage Requirements

### Unit Tests

**Task Model**:
- [ ] Task creation with valid data
- [ ] Task status transitions (pending → processing → completed)
- [ ] Invalid status transitions (completed → pending)
- [ ] Retry count increment
- [ ] TTL calculation
- [ ] Serialization to JSON

**Task Repository**:
- [ ] Create task
- [ ] Get task by ID
- [ ] List user tasks with filtering
- [ ] Update task status
- [ ] Delete task
- [ ] Task not found handling

**Retry Logic**:
- [ ] Calculate backoff (10s, 30s, 90s)
- [ ] Jitter calculation (±20%)
- [ ] Max retries enforced (3)
- [ ] Retriable vs non-retriable errors

---

### Integration Tests (BDD)

```gherkin
Feature: Asynchronous Task Processing

Scenario: Submit threat intelligence asynchronously
  Given I am authenticated as a PARTNER user
  When I POST /submit with X-Async header
  Then I receive 202 Accepted
  And response includes task_id
  And response includes status_url
  And response time is under 200ms

Scenario: Poll task status until completion
  Given I have submitted a task asynchronously
  When I GET /tasks/{task_id} repeatedly
  Then initial status is "pending"
  And status eventually becomes "processing"
  And status eventually becomes "completed"
  And result includes observables_stored count

Scenario: Task retry on transient failure
  Given DynamoDB is temporarily unavailable
  When worker processes a task
  Then task status becomes "failed"
  And retry_count is 1
  When DynamoDB becomes available
  Then task is automatically retried
  And task eventually completes

Scenario: List user tasks
  Given I have created 5 tasks
  When I GET /tasks?status=completed
  Then I receive list of completed tasks
  And tasks are sorted by created_at DESC

Scenario: Cannot access other user's tasks
  Given another user created a task
  When I GET /tasks/{their_task_id}
  Then I receive 403 Forbidden
```

---

### Performance Tests

```python
@pytest.mark.performance
def test_async_submission_response_time():
    """POST /submit with X-Async returns in < 200ms"""
    response_times = []

    for _ in range(100):
        start = time.time()
        response = client.post(
            "/submit",
            headers={"X-Async": "true", "Authorization": f"Bearer {token}"},
            json=submission_data
        )
        end = time.time()

        assert response.status_code == 202
        response_times.append((end - start) * 1000)

    p95 = sorted(response_times)[94]  # 95th percentile
    assert p95 < 200, f"p95 response time {p95}ms exceeds 200ms"

@pytest.mark.performance
def test_throughput_1000_per_minute():
    """System processes 1000 tasks/minute"""
    # Submit 1000 tasks
    task_ids = []
    for _ in range(1000):
        response = client.post("/submit", headers={"X-Async": "true"}, ...)
        task_ids.append(response.json()["task_id"])

    # Wait for all to complete
    start = time.time()
    while not all_tasks_completed(task_ids):
        time.sleep(1)
    duration = time.time() - start

    assert duration < 120, f"Processing took {duration}s, expected < 120s"
```

---

## API Error Responses

All endpoints follow ADR-0008 (Explicit Error Communication):

```json
# 400 Bad Request - Invalid async header
{
  "detail": "X-Async header must be 'true' or 'false'"
}

# 401 Unauthorized - Missing token
{
  "detail": "Invalid or missing authorization token"
}

# 403 Forbidden - Access denied
{
  "detail": "Cannot access task created by another user"
}

# 404 Not Found - Task doesn't exist
{
  "detail": "Task not found: task-a1b2c3d4-..."
}

# 422 Unprocessable Entity - Validation error
{
  "detail": "Validation error: confidence_score must be between 0.0 and 1.0"
}

# 429 Too Many Requests - Rate limit
{
  "detail": "Rate limit exceeded: 1000 submissions per minute"
}

# 503 Service Unavailable - Queue unavailable
{
  "detail": "Task queue unavailable, falling back to synchronous processing"
}
```

---

## Security Considerations

### Task ID Security

- Task IDs use UUID v4 (unguessable)
- Cannot enumerate tasks by incrementing IDs
- Must authenticate to access task status
- Can only access own tasks (unless CORE_MEMBER)

### Authentication

- All task endpoints require JWT authentication
- Task creator stored in task record
- Access control: user can only see their tasks
- CORE_MEMBER can see all tasks (admin access)

### Data Privacy

- Task payload may contain sensitive observables
- Task results stored with same access tier as submission
- Completed tasks purged after 7 days (GDPR compliance)
- Failed tasks in dead letter queue reviewed and purged weekly

---

## Related Documentation

- **Proposal**: [proposal.md](proposal.md) - Why we need this
- **Design**: [design.md](design.md) - How to implement it
- **Tasks**: [tasks.md](tasks.md) - Implementation checklist
- **ADR**: [adr.md](adr.md) - Architectural decisions

---

**Specification Status**: Draft - awaiting review
**Last Updated**: 2026-02-06
**Approvers**: Architecture Team, Security Team
