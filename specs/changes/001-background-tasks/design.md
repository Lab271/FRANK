# Design Document: Background Task Processing System

## Metadata

| Attribute | Value |
|-----------|-------|
| **Design ID** | CHANGE-001-DESIGN |
| **Status** | Draft |
| **Version** | 1.0 |
| **Related Proposal** | [proposal.md](proposal.md) |
| **Related Spec** | [spec.md](spec.md) |
| **Target Version** | 0.3.0 |

---

## System Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRANK Platform                                │
└─────────────────────────────────────────────────────────────────────┘

Client (Service Account)
  │
  │ POST /submit
  │ X-Async: true
  ▼
┌─────────────────────────────┐
│     FastAPI (Sightings)     │
│                             │
│  1. Validate request        │  < 200ms
│  2. Generate task_id        │
│  3. Queue task              │
│  4. Return 202 Accepted     │
└──────────┬──────────────────┘
           │
           │ Enqueue task
           ▼
┌─────────────────────────────┐     ┌──────────────────────┐
│       Task Queue            │────▶│   Dead Letter Queue  │
│                             │     │   (Failed Tasks)     │
│  - SQS (AWS Stage 3)        │     └──────────────────────┘
│  - queue.Queue (Stage 1)    │
│  - Redis (Stage 4)          │
└──────────┬──────────────────┘
           │
           │ Dequeue task
           ▼
┌─────────────────────────────┐
│       Task Worker           │
│                             │
│  1. Fetch task from queue   │
│  2. Process submission      │  2-5 seconds
│  3. Store in database       │
│  4. Update task status      │
│  5. Handle errors/retries   │
└──────────┬──────────────────┘
           │
           ├──────────────────┐
           ▼                  ▼
┌────────────────────┐  ┌────────────────────┐
│   DynamoDB         │  │  Task Status DB    │
│   (Submissions)    │  │  (SQLite/DynamoDB) │
└────────────────────┘  └────────────────────┘

Client
  │
  │ GET /tasks/{task_id}
  │ (poll for status)
  ▼
┌─────────────────────────────┐
│     FastAPI (Sightings)     │
│                             │
│  1. Authenticate user       │
│  2. Fetch task status       │  < 100ms
│  3. Return task info        │
└─────────────────────────────┘
```

---

## Stage-Specific Implementations

### Stage 1: Local Development (SQLite + In-Memory Queue)

**Goals**:
- Fast local development
- No external dependencies
- Full feature parity with production

**Architecture**:
```
┌─────────────────────────────┐
│   FastAPI Process           │
│                             │
│  ┌──────────────────────┐   │
│  │  API Endpoints       │   │
│  │  - POST /submit      │   │
│  │  - GET /tasks/{id}   │   │
│  └──────────┬───────────┘   │
│             │               │
│  ┌──────────▼───────────┐   │
│  │  queue.Queue()       │   │  In-memory queue
│  │  (Python stdlib)     │   │
│  └──────────┬───────────┘   │
│             │               │
│  ┌──────────▼───────────┐   │
│  │  Worker ThreadPool   │   │  concurrent.futures
│  │  (5 worker threads)  │   │
│  └──────────┬───────────┘   │
│             │               │
└─────────────┼───────────────┘
              │
              ▼
       ┌──────────────┐
       │   SQLite     │
       │  (tasks.db)  │
       └──────────────┘
```

**Implementation**:
```python
# src/frank/tasks/queue.py (Stage 1)

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

class LocalTaskQueue:
    def __init__(self, max_workers: int = 5):
        self._queue = queue.Queue()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown = threading.Event()

        # Start background worker loop
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def enqueue(self, task: Task) -> None:
        """Add task to queue"""
        self._queue.put(task)

    def _worker_loop(self) -> None:
        """Background thread continuously processes tasks"""
        while not _shutdown.is_set():
            try:
                task = self._queue.get(timeout=1)
                self._executor.submit(self._process_task, task)
            except queue.Empty:
                continue

    def _process_task(self, task: Task) -> None:
        """Process a single task"""
        try:
            # Update status to processing
            task_repo.update_status(task.task_id, TaskStatus.PROCESSING)

            # Process submission (actual work)
            result = process_submission(task.payload)

            # Mark completed
            task_repo.update_status(
                task.task_id,
                TaskStatus.COMPLETED,
                result=result
            )
        except Exception as e:
            # Handle retry logic
            if should_retry(e, task.retry_count):
                task.retry_count += 1
                delay = calculate_backoff(task.retry_count)
                time.sleep(delay)
                self.enqueue(task)  # Re-queue
            else:
                # Permanent failure
                task_repo.update_status(
                    task.task_id,
                    TaskStatus.FAILED,
                    error=str(e)
                )
```

**Pros**:
- Simple implementation (< 200 lines)
- No external dependencies
- Fast startup (no AWS setup)
- Easy debugging (same process)

**Cons**:
- Tasks lost on server restart
- Limited scalability (5 workers)
- Not production-ready

---

### Stage 3: AWS Cloud (SQS + Lambda)

**Goals**:
- Production-ready
- Auto-scaling
- High availability
- Cost-efficient

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────┐
│  ECS Fargate        │
│  (FastAPI)          │
│                     │
│  POST /submit       │
│    ↓                │
│  boto3.send_message │──┐
└─────────────────────┘  │
                         │
                         ▼
              ┌──────────────────────┐
              │   SQS Standard Queue │
              │   frank-tasks.fifo   │
              │                      │
              │  Visibility: 300s    │
              │  Retention: 14 days  │
              └──────────┬───────────┘
                         │
                         │ Trigger (batch size: 10)
                         ▼
              ┌──────────────────────┐
              │   Lambda Function    │
              │   frank-task-worker  │
              │                      │
              │   Memory: 1024 MB    │
              │   Timeout: 60s       │
              │   Concurrency: 100   │
              │   Reserved: 5        │  Warm instances
              └──────────┬───────────┘
                         │
                         ├───────────────┐
                         ▼               ▼
              ┌──────────────────┐  ┌─────────────────┐
              │  DynamoDB        │  │  DynamoDB       │
              │  frank-tasks     │  │  frank-submit   │
              │  (Task Status)   │  │  (Submissions)  │
              └──────────────────┘  └─────────────────┘
```

**Implementation**:
```python
# src/frank/tasks/queue.py (Stage 3)

import boto3
import json
from typing import Dict, Any

class SQSTaskQueue:
    def __init__(self, queue_url: str):
        self.sqs = boto3.client('sqs')
        self.queue_url = queue_url

    def enqueue(self, task: Task) -> None:
        """Send task to SQS"""
        message = {
            'task_id': task.task_id,
            'submission_id': task.submission_id,
            'payload': task.payload,
            'retry_count': task.retry_count
        }

        self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(message),
            MessageAttributes={
                'task_id': {
                    'StringValue': task.task_id,
                    'DataType': 'String'
                }
            }
        )

# lambda/task_worker.py (Lambda handler)

import json
import boto3
from frank.storage.dynamodb import DynamoDBFRANKDatabase
from frank.tasks.processor import TaskProcessor

dynamodb = boto3.resource('dynamodb')
db = DynamoDBFRANKDatabase(dynamodb)
processor = TaskProcessor(db)

def lambda_handler(event, context):
    """
    Process batch of tasks from SQS.

    Event format:
    {
      "Records": [
        {
          "body": "{task_id: ..., payload: ...}",
          "receiptHandle": "..."
        }
      ]
    }
    """
    batch_failures = []

    for record in event['Records']:
        try:
            task_data = json.loads(record['body'])
            task = Task(**task_data)

            # Process task
            processor.process(task)

        except Exception as e:
            # Return failed message for retry
            batch_failures.append({
                'itemIdentifier': record['messageId']
            })
            logger.error(f"Task processing failed: {e}", exc_info=True)

    # Return failed messages for SQS to retry
    return {
        'batchItemFailures': batch_failures
    }
```

**Pros**:
- Auto-scales to 100 workers
- High availability (multi-AZ)
- No server management
- Cost-efficient ($50/month)

**Cons**:
- More complex setup (Ansible/CloudFormation)
- AWS vendor lock-in
- Lambda cold starts (mitigated with reserved concurrency)

---

## Task Processing Flow

### Detailed Sequence Diagram

```
Client          API          Queue        Worker        Task DB      Submit DB
  │             │             │             │             │             │
  │ POST /submit              │             │             │             │
  │ X-Async: true             │             │             │             │
  ├────────────>│             │             │             │             │
  │             │             │             │             │             │
  │             │ 1. Validate │             │             │             │
  │             │    request  │             │             │             │
  │             │             │             │             │             │
  │             │ 2. Generate │             │             │             │
  │             │    task_id  │             │             │             │
  │             │             │             │             │             │
  │             │ 3. Create   │             │             │             │
  │             │    task     │             │             │             │
  │             ├─────────────┼─────────────┼────────────>│             │
  │             │             │             │             │             │
  │             │ 4. Enqueue  │             │             │             │
  │             ├────────────>│             │             │             │
  │             │             │             │             │             │
  │ 202 Accepted              │             │             │             │
  │ {task_id}   │             │             │             │             │
  │<────────────┤             │             │             │             │
  │             │             │             │             │             │
  │             │             │ 5. Dequeue  │             │             │
  │             │             │<────────────┤             │             │
  │             │             │             │             │             │
  │             │             │             │ 6. Update   │             │
  │             │             │             │    status=  │             │
  │             │             │             │    processing             │
  │             │             │             ├────────────>│             │
  │             │             │             │             │             │
  │             │             │             │ 7. Process  │             │
  │             │             │             │    submission             │
  │             │             │             │             │             │
  │             │             │             │ 8. Store    │             │
  │             │             │             │    submission             │
  │             │             │             ├─────────────┼────────────>│
  │             │             │             │             │             │
  │             │             │             │ 9. Update   │             │
  │             │             │             │    status=  │             │
  │             │             │             │    completed│             │
  │             │             │             ├────────────>│             │
  │             │             │             │             │             │
  │ GET /tasks/{task_id}      │             │             │             │
  ├────────────>│             │             │             │             │
  │             │ 10. Fetch   │             │             │             │
  │             │     status  │             │             │             │
  │             ├─────────────┼─────────────┼────────────>│             │
  │             │<────────────┼─────────────┼─────────────┤             │
  │             │             │             │             │             │
  │ 200 OK      │             │             │             │             │
  │ {status:    │             │             │             │             │
  │  completed} │             │             │             │             │
  │<────────────┤             │             │             │             │
```

---

## Error Handling and Retry Strategy

### Retry Decision Matrix

| Error Type | Retriable | Max Retries | Backoff | Action |
|------------|-----------|-------------|---------|--------|
| DynamoDB Timeout | ✅ Yes | 3 | 10s, 30s, 90s | Retry |
| DynamoDB Throttling | ✅ Yes | 3 | 10s, 30s, 90s | Retry |
| Network Timeout | ✅ Yes | 3 | 10s, 30s, 90s | Retry |
| Validation Error | ❌ No | 0 | N/A | Fail immediately |
| Auth Error | ❌ No | 0 | N/A | Fail immediately |
| Malformed Payload | ❌ No | 0 | N/A | Fail immediately |
| DB Connection Lost | ✅ Yes | 3 | 10s, 30s, 90s | Retry |

### Retry Implementation

```python
# src/frank/tasks/retry.py

import random
import time
from typing import Tuple

class RetryConfig:
    MAX_RETRIES = 3
    BASE_DELAY = 10  # seconds
    BACKOFF_MULTIPLIER = 3
    JITTER_RANGE = 0.2  # ±20%

def should_retry(error: Exception, retry_count: int) -> bool:
    """Determine if error is retriable"""
    if retry_count >= RetryConfig.MAX_RETRIES:
        return False

    # Retriable errors
    retriable_errors = (
        DatabaseTimeoutError,
        ThrottlingError,
        ConnectionError,
        NetworkTimeoutError,
    )

    if isinstance(error, retriable_errors):
        return True

    # Non-retriable errors
    non_retriable_errors = (
        ValidationError,
        AuthenticationError,
        AuthorizationError,
        MalformedPayloadError,
    )

    if isinstance(error, non_retriable_errors):
        return False

    # Unknown errors: default to non-retriable (fail-safe)
    return False

def calculate_backoff(retry_count: int) -> int:
    """Calculate delay before retry with exponential backoff and jitter"""
    # Exponential backoff: 10s, 30s, 90s
    base_delay = RetryConfig.BASE_DELAY * (RetryConfig.BACKOFF_MULTIPLIER ** retry_count)

    # Add jitter to prevent thundering herd
    jitter = random.uniform(
        -RetryConfig.JITTER_RANGE,
        RetryConfig.JITTER_RANGE
    )
    delay = int(base_delay * (1 + jitter))

    return delay

# Example usage
try:
    process_task(task)
except Exception as e:
    if should_retry(e, task.retry_count):
        task.retry_count += 1
        delay = calculate_backoff(task.retry_count)
        logger.info(f"Retrying task {task.task_id} in {delay}s (attempt {task.retry_count})")
        time.sleep(delay)
        queue.enqueue(task)
    else:
        logger.error(f"Task {task.task_id} permanently failed: {e}")
        task_repo.mark_failed(task.task_id, error=str(e))
```

---

## Database Schema Design

### Task Lifecycle State Machine

```
         ┌──────────┐
         │  PENDING │  Initial state
         └────┬─────┘
              │
              ▼
       ┌────────────┐
       │ PROCESSING │  Worker started
       └─────┬──────┘
             │
        ┌────┴────┐
        │         │
        ▼         ▼
  ┌───────────┐ ┌──────────┐
  │ COMPLETED │ │  FAILED  │  Terminal states
  └───────────┘ └────┬─────┘
                     │
                     │ retry_count < 3?
                     │
                ┌────┴────┐
                │   Yes   │
                └────┬────┘
                     │
                     └─────> Back to PENDING
```

### Task Status Transitions

```python
# Valid transitions
ALLOWED_TRANSITIONS = {
    TaskStatus.PENDING: [TaskStatus.PROCESSING, TaskStatus.CANCELLED],
    TaskStatus.PROCESSING: [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PENDING],
    TaskStatus.COMPLETED: [],  # Terminal
    TaskStatus.FAILED: [TaskStatus.PENDING],  # Only for retry
    TaskStatus.CANCELLED: [],  # Terminal
}

def can_transition(from_status: TaskStatus, to_status: TaskStatus) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, [])
```

---

## Infrastructure as Code

### Ansible Playbook (Stage 3 AWS)

```yaml
# ansible/tasks/sqs_task_queue.yml

- name: Create SQS task queue
  amazon.aws.sqs_queue:
    name: frank-tasks
    region: "{{ aws_region }}"
    default_visibility_timeout: 300  # 5 minutes
    message_retention_period: 1209600  # 14 days
    receive_message_wait_time_seconds: 20  # Long polling
    dead_letter_queue:
      target_arn: "arn:aws:sqs:{{ aws_region }}:{{ aws_account_id }}:frank-tasks-dlq"
      max_receive_count: 3
  register: task_queue

- name: Create dead letter queue
  amazon.aws.sqs_queue:
    name: frank-tasks-dlq
    region: "{{ aws_region }}"
    message_retention_period: 1209600  # 14 days
  register: dlq_queue

- name: Create Lambda execution role
  amazon.aws.iam_role:
    name: frank-task-worker-role
    assume_role_policy_document:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Principal:
            Service: lambda.amazonaws.com
          Action: sts:AssumeRole
    managed_policy:
      - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      - arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
      - arn:aws:iam::aws:policy/AmazonSQSFullAccess

- name: Deploy Lambda function
  amazon.aws.lambda:
    name: frank-task-worker
    runtime: python3.13
    role: "{{ task_worker_role.arn }}"
    handler: lambda.task_worker.lambda_handler
    zip_file: "{{ lambda_package_path }}"
    memory_size: 1024
    timeout: 60
    environment_variables:
      FRANK_ENV: production
      DYNAMODB_TASKS_TABLE: frank-tasks
      DYNAMODB_SUBMISSIONS_TABLE: frank-submissions
    reserved_concurrent_executions: 5  # Keep 5 warm
  register: task_worker_lambda

- name: Create SQS trigger for Lambda
  amazon.aws.lambda_event:
    lambda_function_arn: "{{ task_worker_lambda.function_arn }}"
    event_source_arn: "{{ task_queue.queue_arn }}"
    batch_size: 10
    maximum_batching_window_in_seconds: 5
```

---

## Monitoring and Observability

### CloudWatch Metrics

```python
# src/frank/tasks/metrics.py

import boto3
from datetime import datetime

cloudwatch = boto3.client('cloudwatch')

class TaskMetrics:
    NAMESPACE = 'FRANK/Tasks'

    @staticmethod
    def record_task_submitted():
        cloudwatch.put_metric_data(
            Namespace=TaskMetrics.NAMESPACE,
            MetricData=[{
                'MetricName': 'TasksSubmitted',
                'Value': 1.0,
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            }]
        )

    @staticmethod
    def record_processing_time(duration_ms: float):
        cloudwatch.put_metric_data(
            Namespace=TaskMetrics.NAMESPACE,
            MetricData=[{
                'MetricName': 'ProcessingTime',
                'Value': duration_ms,
                'Unit': 'Milliseconds',
                'Timestamp': datetime.utcnow()
            }]
        )

    @staticmethod
    def record_task_status(status: TaskStatus):
        cloudwatch.put_metric_data(
            Namespace=TaskMetrics.NAMESPACE,
            MetricData=[{
                'MetricName': f'Tasks{status.value.capitalize()}',
                'Value': 1.0,
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            }]
        )

    @staticmethod
    def record_queue_depth(depth: int):
        cloudwatch.put_metric_data(
            Namespace=TaskMetrics.NAMESPACE,
            MetricData=[{
                'MetricName': 'QueueDepth',
                'Value': float(depth),
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            }]
        )
```

### CloudWatch Alarms

```yaml
# cloudformation/alarms.yml

Resources:
  HighQueueDepthAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: frank-tasks-high-queue-depth
      MetricName: ApproximateNumberOfMessagesVisible
      Namespace: AWS/SQS
      Dimensions:
        - Name: QueueName
          Value: frank-tasks
      Statistic: Average
      Period: 300  # 5 minutes
      EvaluationPeriods: 1
      Threshold: 1000
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref SNSAlertTopic

  HighFailureRateAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: frank-tasks-high-failure-rate
      MetricName: TasksFailed
      Namespace: FRANK/Tasks
      Statistic: Sum
      Period: 600  # 10 minutes
      EvaluationPeriods: 1
      Threshold: 50  # > 5% if 1000 tasks/10min
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref SNSAlertTopic
```

---

## Testing Strategy

### Unit Tests (Mock Queue)

```python
# tests/unit/tasks/test_queue.py

import pytest
from unittest.mock import Mock, patch
from frank.tasks.queue import LocalTaskQueue
from frank.tasks.models import Task, TaskStatus

def test_enqueue_task():
    """Task enqueued successfully"""
    queue = LocalTaskQueue(max_workers=1)
    task = Task(task_id="task-123", ...)

    queue.enqueue(task)

    # Verify task in queue
    assert not queue._queue.empty()

def test_process_task_success():
    """Task processes successfully"""
    queue = LocalTaskQueue(max_workers=1)
    task = Task(task_id="task-123", ...)

    with patch('frank.tasks.processor.process_submission') as mock_process:
        mock_process.return_value = {"observables_stored": 10}

        queue.enqueue(task)
        queue._worker_thread.join(timeout=5)

        # Verify task completed
        task_status = task_repo.get(task.task_id)
        assert task_status.status == TaskStatus.COMPLETED
```

### Integration Tests (Real Queue)

```python
# tests/integration/tasks/test_async_submission.py

def test_async_submission_flow(client, auth_token):
    """Complete async submission flow"""
    # Submit asynchronously
    response = client.post(
        "/submit",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "X-Async": "true"
        },
        json=submission_data
    )

    assert response.status_code == 202
    task_id = response.json()["task_id"]

    # Poll for completion
    for _ in range(30):  # Max 30 seconds
        status_response = client.get(
            f"/tasks/{task_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        status = status_response.json()["status"]

        if status == "completed":
            break

        time.sleep(1)

    assert status == "completed"
    assert "result" in status_response.json()
```

---

## Performance Optimization

### Batch Processing

```python
# lambda/task_worker.py (optimized)

def lambda_handler(event, context):
    """Process batch of tasks efficiently"""
    tasks = [Task(**json.loads(record['body'])) for record in event['Records']]

    # Batch database writes
    with db.batch_writer() as batch:
        for task in tasks:
            # Process task
            result = processor.process(task)

            # Write to batch (deferred until exit)
            batch.put_item(Item={
                'task_id': task.task_id,
                'status': 'completed',
                'result': result
            })

    # Single network round-trip instead of N round-trips
```

---

## Related Documentation

- **Proposal**: [proposal.md](proposal.md) - Why we need this
- **Spec**: [spec.md](spec.md) - What it should do
- **Tasks**: [tasks.md](tasks.md) - Implementation checklist
- **ADR**: [adr.md](adr.md) - Architectural decisions
- **ADR-0001**: Four-Stage Infrastructure Evolution

---

**Design Status**: Draft - awaiting review
**Last Updated**: 2026-02-06
**Reviewers**: Architecture Team, Platform Team
