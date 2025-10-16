# FRANK Load Testing Guide

## Overview

This guide covers load testing for the FRANK Stage 3 API using Locust, a modern Python-based load testing framework. Locust provides an intuitive way to define user behavior and generate realistic load patterns.

## Prerequisites

```bash
# Install Locust
pip install locust

# Or add to requirements
echo "locust>=2.20.0" >> requirements.txt
pip install -r requirements.txt
```

## Quick Start

### 1. Start the API Locally

```bash
cd stages/stage3
python api.py --environment localstack --port 8080
```

### 2. Run Locust with Web UI

```bash
# Basic run with web interface
locust -f locustfile.py --host=http://localhost:8080

# Then open browser to http://localhost:8089
```

### 3. Configure Test Parameters

In the web UI:
- **Number of users**: Total users to simulate (e.g., 100)
- **Spawn rate**: Users to add per second (e.g., 10)
- **Host**: Target URL (pre-filled from --host)

Click "Start swarming" to begin the test.

## Running Headless (No Web UI)

For CI/CD or automated testing:

```bash
# Run 100 users for 5 minutes
locust -f locustfile.py \
  --host=http://localhost:8080 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless

# With custom API key
locust -f locustfile.py \
  --host=https://frank-stage3.lab271.io \
  --users 500 \
  --spawn-rate 50 \
  --run-time 10m \
  --api-key your-api-key \
  --headless

# Generate HTML report
locust -f locustfile.py \
  --host=http://localhost:8080 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 3m \
  --headless \
  --html load-test-report.html
```

## User Behavior Profiles

The locustfile defines two user types:

### 1. FRANKUser (Regular API User)

Simulates typical threat intelligence operations:

| Task | Weight | Description |
|------|--------|-------------|
| `create_submission_simple` | 3 | Create submission with 1-2 observables |
| `create_submission_complex` | 2 | Create submission with multiple observables |
| `query_observables_by_type` | 4 | Query observables filtered by type |
| `query_observables_with_filters` | 3 | Query with multiple filters |
| `search_observables` | 2 | Search by value substring |
| `get_submission_by_id` | 2 | Retrieve specific submission |
| `get_statistics` | 1 | Get platform statistics |
| `health_check` | 5 | Basic health check |

**Behavior:**
- Waits 1-5 seconds between tasks
- Creates submissions and stores IDs for later retrieval
- Simulates realistic user patterns

### 2. AdminUser (Monitoring/Analytics User)

Simulates administrative monitoring operations:

| Task | Weight | Description |
|------|--------|-------------|
| `deep_health_check` | 5 | Comprehensive health check |
| `get_comprehensive_statistics` | 3 | Statistics for multiple time periods |
| `bulk_observable_query` | 2 | Large queries for analytics |

**Behavior:**
- Waits 2-10 seconds between tasks
- Only 1 admin per 10 regular users (weight = 1)
- Performs more intensive queries

## Test Scenarios

### Scenario 1: Light Load (Development)

Test basic functionality under light load:

```bash
locust -f locustfile.py \
  --host=http://localhost:8080 \
  --users 10 \
  --spawn-rate 2 \
  --run-time 2m \
  --headless
```

**Expected Results:**
- Response time < 200ms
- 0% failure rate
- ~50-100 requests/sec

### Scenario 2: Normal Load (Staging)

Simulate typical production traffic:

```bash
locust -f locustfile.py \
  --host=https://frank-stage3.lab271.io \
  --users 100 \
  --spawn-rate 10 \
  --run-time 10m \
  --headless
```

**Expected Results:**
- Response time < 500ms (95th percentile)
- < 0.1% failure rate
- 500-1000 requests/sec

### Scenario 3: Stress Test (Load Testing)

Test system limits and auto-scaling:

```bash
locust -f locustfile.py \
  --host=https://frank-stage3.lab271.io \
  --users 500 \
  --spawn-rate 50 \
  --run-time 15m \
  --headless
```

**Expected Results:**
- Auto-scaling triggers (ECS adds tasks)
- Response time < 1000ms
- < 1% failure rate
- System stabilizes after scaling

### Scenario 4: Spike Test

Sudden traffic spike simulation:

```bash
locust -f locustfile.py \
  --host=https://frank-stage3.lab271.io \
  --users 1000 \
  --spawn-rate 100 \
  --run-time 5m \
  --headless
```

**Expected Results:**
- Initial response time spike
- Auto-scaling response within 5 minutes
- System recovers and stabilizes

### Scenario 5: Endurance Test

Long-running test for stability:

```bash
locust -f locustfile.py \
  --host=https://frank-stage3.lab271.io \
  --users 200 \
  --spawn-rate 20 \
  --run-time 2h \
  --headless
```

**Expected Results:**
- No memory leaks
- Consistent performance over time
- < 0.5% failure rate

## Monitoring During Tests

### CloudWatch Metrics (AWS)

Monitor these metrics during load tests:

1. **ECS Service Metrics**
   - CPU Utilization (target: < 70%)
   - Memory Utilization (target: < 80%)
   - Running Task Count (should scale 2-10)

2. **ALB Metrics**
   - Request Count
   - Target Response Time
   - HTTP 5xx Errors (target: 0)
   - Healthy Host Count

3. **DynamoDB Metrics**
   - Read/Write Capacity Units
   - Throttled Requests (target: 0)
   - Latency (target: < 100ms)

### Locust Web UI Metrics

Key metrics to watch:

- **RPS (Requests Per Second)**: Current throughput
- **Response Time (ms)**: 50th, 95th, 99th percentiles
- **Failures**: Percentage of failed requests
- **Users**: Number of simulated users

### Custom Monitoring Script

```python
# monitor_load_test.py
import boto3
import time
from datetime import datetime, timedelta

def monitor_ecs_metrics(cluster_name, service_name, duration_minutes=10):
    """Monitor ECS metrics during load test"""
    cloudwatch = boto3.client('cloudwatch', region_name='eu-central-1')
    ecs = boto3.client('ecs', region_name='eu-central-1')

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(minutes=duration_minutes)

    print(f"Monitoring {service_name} for {duration_minutes} minutes...")
    print("=" * 80)

    while datetime.utcnow() < end_time:
        # Get running task count
        response = ecs.describe_services(
            cluster=cluster_name,
            services=[service_name]
        )
        service = response['services'][0]
        running_count = service['runningCount']
        desired_count = service['desiredCount']

        # Get CPU/Memory metrics
        metrics_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/ECS',
            MetricName='CPUUtilization',
            Dimensions=[
                {'Name': 'ServiceName', 'Value': service_name},
                {'Name': 'ClusterName', 'Value': cluster_name}
            ],
            StartTime=datetime.utcnow() - timedelta(minutes=5),
            EndTime=datetime.utcnow(),
            Period=300,
            Statistics=['Average']
        )

        cpu_avg = metrics_response['Datapoints'][0]['Average'] if metrics_response['Datapoints'] else 0

        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
              f"Tasks: {running_count}/{desired_count} | "
              f"CPU: {cpu_avg:.1f}%")

        time.sleep(30)  # Check every 30 seconds

    print("=" * 80)
    print("Monitoring complete")

if __name__ == "__main__":
    monitor_ecs_metrics('frank-stage3', 'frank-stage3-service', duration_minutes=10)
```

## Interpreting Results

### Response Time Analysis

```
Response Time Percentiles:
- 50th percentile (median): < 200ms - Excellent
- 95th percentile: < 500ms - Good
- 99th percentile: < 1000ms - Acceptable

If 95th > 1000ms: System is overloaded or has issues
```

### Failure Rate Analysis

```
Failure Rate:
- 0% - Perfect
- < 0.1% - Excellent
- 0.1% - 1% - Acceptable (investigate specific failures)
- > 1% - Poor (system issues or capacity problems)
```

### Common Issues

**High Response Times**
- DynamoDB throttling (increase capacity or check indexes)
- ECS tasks under-provisioned (increase CPU/memory)
- Network latency (check security groups, VPC endpoints)

**High Failure Rates**
- Authentication errors (check API keys)
- Database connection issues (check IAM roles, security groups)
- Rate limiting (expected at very high loads)

**Auto-Scaling Not Triggering**
- Check scaling policies (CPU/memory thresholds)
- Verify CloudWatch alarms configured correctly
- Review scaling cooldown periods

## Advanced Usage

### Custom User Distribution

Create custom user ratios:

```python
# In locustfile.py

class LightUser(HttpUser):
    weight = 5  # 5x more light users

class HeavyUser(HttpUser):
    weight = 1  # 1x heavy users
```

### Distributed Load Testing

Run Locust in distributed mode for massive load:

```bash
# Start master node
locust -f locustfile.py --master --expect-workers 4

# Start worker nodes (on different machines)
locust -f locustfile.py --worker --master-host=<master-ip>
locust -f locustfile.py --worker --master-host=<master-ip>
locust -f locustfile.py --worker --master-host=<master-ip>
locust -f locustfile.py --worker --master-host=<master-ip>
```

### Custom Step Load Profile

Gradually increase load:

```python
# In locustfile.py
from locust import LoadTestShape

class StepLoadShape(LoadTestShape):
    """
    Step load pattern:
    - Start with 50 users
    - Every 2 minutes, add 50 users
    - Run for 10 minutes total
    """
    step_time = 120  # 2 minutes
    step_load = 50
    spawn_rate = 10
    time_limit = 600  # 10 minutes

    def tick(self):
        run_time = self.get_run_time()

        if run_time > self.time_limit:
            return None

        current_step = run_time // self.step_time
        user_count = (current_step + 1) * self.step_load

        return (user_count, self.spawn_rate)
```

### Generate Reports

```bash
# Generate CSV reports
locust -f locustfile.py \
  --host=http://localhost:8080 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless \
  --csv=load-test-results

# This creates:
# - load-test-results_stats.csv
# - load-test-results_stats_history.csv
# - load-test-results_failures.csv

# Generate HTML report
locust -f locustfile.py \
  --host=http://localhost:8080 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless \
  --html=load-test-report.html
```

## Performance Targets

Based on Stage 3 architecture:

| Metric | Target | Notes |
|--------|--------|-------|
| API Response Time (95th) | < 500ms | Health checks < 100ms |
| Database Latency (99th) | < 100ms | DynamoDB target |
| Throughput | 1000+ req/min per task | With auto-scaling |
| Error Rate | < 0.1% | Under normal load |
| Service Availability | > 99.9% | Multi-AZ deployment |
| Auto-Scale Response | < 5 minutes | From trigger to stable |

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/load-test.yml
name: Load Test

on:
  schedule:
    - cron: '0 2 * * *'  # Run daily at 2 AM
  workflow_dispatch:

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install locust boto3

      - name: Run load test
        env:
          FRANK_API_KEY: ${{ secrets.FRANK_API_KEY }}
        run: |
          cd stages/stage3
          locust -f locustfile.py \
            --host=https://frank-stage3.lab271.io \
            --users 100 \
            --spawn-rate 10 \
            --run-time 5m \
            --headless \
            --html=load-test-report.html \
            --csv=load-test-results \
            --api-key=$FRANK_API_KEY

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: load-test-results
          path: |
            stages/stage3/load-test-report.html
            stages/stage3/load-test-results*.csv

      - name: Check performance thresholds
        run: |
          python stages/stage3/check_performance.py \
            --stats stages/stage3/load-test-results_stats.csv \
            --max-response-time 500 \
            --max-failure-rate 0.1
```

## Best Practices

1. **Start Small**: Begin with low user counts and gradually increase
2. **Monitor Resources**: Watch CloudWatch metrics during tests
3. **Test Off-Hours**: Run load tests during low-traffic periods
4. **Clean Test Data**: Clean up submissions created during testing
5. **Use Realistic Data**: Mix of simple and complex operations
6. **Run Regularly**: Schedule periodic load tests to catch regressions
7. **Document Results**: Keep historical records for comparison

## Troubleshooting

### Connection Refused

```bash
# Check API is running
curl http://localhost:8080/v1/health

# Check firewall/security groups
# Check correct port number
```

### Authentication Failures

```bash
# Verify API key
curl -H "Authorization: Bearer dev-key-12345" \
  http://localhost:8080/v1/health

# Update API key in command
locust -f locustfile.py --api-key your-key
```

### High Failure Rates

```bash
# Check Locust logs for specific errors
# Review API server logs
# Check DynamoDB throttling in CloudWatch
# Verify network connectivity
```

### Locust Won't Start

```bash
# Reinstall Locust
pip uninstall locust
pip install locust

# Check Python version (3.7+)
python --version

# Verify locustfile syntax
python -m py_compile locustfile.py
```

## Additional Resources

- [Locust Documentation](https://docs.locust.io/)
- [AWS ECS Auto Scaling](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-auto-scaling.html)
- [DynamoDB Performance](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)

## License

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
