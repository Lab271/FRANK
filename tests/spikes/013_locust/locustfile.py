#!/usr/bin/env python3
"""
FRANK Platform - Locust Load Testing Configuration
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

Load testing suite for the Stage 3 API endpoints using Locust.
Tests submission creation, observable queries, and statistics endpoints.

Usage:
    # Run with Web UI
    locust -f locustfile.py --host=http://localhost:8080

    # Run headless (no UI)
    locust -f locustfile.py --host=http://localhost:8080 \
        --users 100 --spawn-rate 10 --run-time 5m --headless

    # Run against AWS
    locust -f locustfile.py --host=https://frank-stage3.lab271.io \
        --users 500 --spawn-rate 50 --run-time 10m

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import random
import time
from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask


class FRANKUser(HttpUser):
    """
    Simulated FRANK API user performing typical threat intelligence operations.

    User behavior:
    - Creates submissions with varying complexity
    - Queries observables with different filters
    - Searches for specific indicators
    - Retrieves statistics
    - Fetches individual submissions
    """

    # Wait between 1-5 seconds between tasks
    wait_time = between(1, 5)

    # Store created submission IDs for later retrieval
    submission_ids = []

    def on_start(self):
        """
        Called when a simulated user starts.
        Sets up authentication headers and initial state.
        """
        # API key for authentication (default dev key)
        self.api_key = self.environment.parsed_options.api_key if hasattr(self.environment, 'parsed_options') else "dev-key-12345"

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Test authentication on start
        with self.client.get("/v1/health", catch_response=True) as response:
            if response.status_code != 200:
                response.failure("Health check failed on user start")

    @task(3)
    def create_submission_simple(self):
        """
        Create a simple submission with 1-2 observables.
        Weight: 3 (most common operation)
        """
        submission_data = {
            "submitter_access_level": random.choice(["CONTRIBUTOR", "PARTNER"]),
            "submitter_sector": random.choice(["financial", "technology", "healthcare"]),
            "submitter_region": random.choice(["eu-west", "eu-central", "eu-north"]),
            "hit_target_sector": random.choice(["financial", "healthcare", "public_sector", "technology"]),
            "hit_target_size": random.choice(["small", "medium", "large"]),
            "confidence": random.randint(60, 95),
            "severity": random.choice(["LOW", "MEDIUM", "HIGH"]),
            "network_observables": [
                {
                    "type": "ipv4",
                    "value": f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 255)}",
                    "role": random.choice(["c2", "exfiltration", "scanning"]),
                    "port": random.choice([443, 80, 8080, 22, 3389]),
                }
            ],
            "tlp_level": random.choice(["GREEN", "AMBER"]),
        }

        with self.client.post(
            "/api/v1/submissions",
            json=submission_data,
            headers=self.headers,
            catch_response=True,
            name="/api/v1/submissions [simple]"
        ) as response:
            if response.status_code == 201:
                result = response.json()
                self.submission_ids.append(result["submission_id"])
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(2)
    def create_submission_complex(self):
        """
        Create a complex submission with multiple observables.
        Weight: 2 (less common)
        """
        submission_data = {
            "submitter_access_level": "PARTNER",
            "submitter_sector": "technology",
            "hit_target_sector": "financial",
            "hit_target_size": "large",
            "confidence": random.randint(80, 95),
            "severity": random.choice(["HIGH", "CRITICAL"]),
            "network_observables": [
                {
                    "type": "ipv4",
                    "value": f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 255)}",
                    "role": "c2",
                    "port": 443,
                },
                {
                    "type": "domain",
                    "value": f"malicious-{random.randint(1000, 9999)}.example.com",
                    "role": "c2",
                },
                {
                    "type": "url",
                    "value": f"https://phishing-{random.randint(1000, 9999)}.example.com/login",
                    "role": "phishing",
                },
            ],
            "file_observables": [
                {
                    "type": "sha256",
                    "value": ''.join(random.choices('0123456789abcdef', k=64)),
                }
            ],
            "tlp_level": "AMBER",
        }

        with self.client.post(
            "/api/v1/submissions",
            json=submission_data,
            headers=self.headers,
            catch_response=True,
            name="/api/v1/submissions [complex]"
        ) as response:
            if response.status_code == 201:
                result = response.json()
                self.submission_ids.append(result["submission_id"])
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(4)
    def query_observables_by_type(self):
        """
        Query observables filtered by type.
        Weight: 4 (common read operation)
        """
        obs_type = random.choice(["ipv4", "domain", "url", "sha256"])
        params = {
            "observable_type": obs_type,
            "limit": random.choice([10, 50, 100]),
        }

        with self.client.get(
            "/api/v1/observables",
            params=params,
            headers=self.headers,
            catch_response=True,
            name=f"/api/v1/observables?type={obs_type}"
        ) as response:
            if response.status_code == 200:
                result = response.json()
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(3)
    def query_observables_with_filters(self):
        """
        Query observables with multiple filters.
        Weight: 3 (common filtered query)
        """
        params = {
            "observable_type": random.choice(["ipv4", "domain"]),
            "min_confidence": random.choice([60, 70, 80]),
            "days_back": random.choice([7, 14, 30]),
            "limit": 50,
        }

        with self.client.get(
            "/api/v1/observables",
            params=params,
            headers=self.headers,
            catch_response=True,
            name="/api/v1/observables [filtered]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(2)
    def search_observables(self):
        """
        Search for observables by value.
        Weight: 2 (less common search operation)
        """
        # Generate random search patterns
        search_patterns = [
            f"{random.randint(1, 255)}.{random.randint(0, 255)}",  # IP prefix
            f"malicious-{random.randint(1000, 1999)}",  # Domain prefix
            f"{random.choice('0123456789abcdef')}{random.choice('0123456789abcdef')}",  # Hash prefix
        ]

        search_value = random.choice(search_patterns)

        with self.client.get(
            "/api/v1/observables/search",
            params={"value": search_value},
            headers=self.headers,
            catch_response=True,
            name="/api/v1/observables/search"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(2)
    def get_submission_by_id(self):
        """
        Retrieve a specific submission by ID.
        Weight: 2 (occasional detail view)
        """
        if not self.submission_ids:
            # No submissions created yet, skip this task
            raise RescheduleTask()

        submission_id = random.choice(self.submission_ids)

        with self.client.get(
            f"/api/v1/submissions/{submission_id}",
            headers=self.headers,
            catch_response=True,
            name="/api/v1/submissions/{id}"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                # Submission might have been cleaned up or doesn't exist
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(1)
    def get_statistics(self):
        """
        Get platform statistics.
        Weight: 1 (infrequent dashboard view)
        """
        params = {"days": random.choice([7, 30, 90])}

        with self.client.get(
            "/api/v1/statistics",
            params=params,
            headers=self.headers,
            catch_response=True,
            name="/api/v1/statistics"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(5)
    def health_check(self):
        """
        Basic health check.
        Weight: 5 (most frequent - monitoring)
        """
        with self.client.get(
            "/v1/health",
            catch_response=True,
            name="/v1/health"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")


class AdminUser(HttpUser):
    """
    Simulated admin user performing monitoring and analytics operations.

    Admin behavior:
    - Frequently checks health endpoints
    - Reviews statistics and metrics
    - Performs bulk queries
    """

    wait_time = between(2, 10)
    weight = 1  # Only 1 admin for every 10 regular users

    def on_start(self):
        """Setup admin user with API key"""
        self.api_key = "dev-key-12345"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    @task(5)
    def deep_health_check(self):
        """
        Comprehensive health check including database.
        Weight: 5 (frequent monitoring)
        """
        with self.client.get(
            "/v1/health/deep",
            catch_response=True,
            name="/v1/health/deep"
        ) as response:
            if response.status_code == 200:
                result = response.json()
                if result.get("status") != "healthy":
                    response.failure(f"System unhealthy: {result}")
                else:
                    response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(3)
    def get_comprehensive_statistics(self):
        """
        Get detailed statistics for various time periods.
        Weight: 3 (regular dashboard updates)
        """
        for days in [7, 30, 90]:
            with self.client.get(
                "/api/v1/statistics",
                params={"days": days},
                headers=self.headers,
                catch_response=True,
                name=f"/api/v1/statistics?days={days}"
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Failed with status {response.status_code}")

            time.sleep(0.5)  # Brief pause between requests

    @task(2)
    def bulk_observable_query(self):
        """
        Query large numbers of observables for analytics.
        Weight: 2 (occasional bulk operations)
        """
        params = {
            "limit": 1000,  # Maximum allowed
            "days_back": 30,
        }

        with self.client.get(
            "/api/v1/observables",
            params=params,
            headers=self.headers,
            catch_response=True,
            name="/api/v1/observables [bulk]"
        ) as response:
            if response.status_code == 200:
                result = response.json()
                # Verify we got results
                if result.get("total", 0) > 0:
                    response.success()
                else:
                    response.failure("No observables returned")
            else:
                response.failure(f"Failed with status {response.status_code}")


# Custom command line arguments
@events.init_command_line_parser.add_listener
def add_custom_arguments(parser):
    """Add custom command line arguments for Locust"""
    parser.add_argument(
        "--api-key",
        type=str,
        default="dev-key-12345",
        help="API key for authentication (default: dev-key-12345)"
    )


# Test event handlers for reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts"""
    print("=" * 80)
    print("FRANK Load Test Starting")
    print("=" * 80)
    print(f"Target: {environment.host}")
    print(f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    print("=" * 80)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops"""
    print("=" * 80)
    print("FRANK Load Test Complete")
    print("=" * 80)

    # Print summary statistics
    stats = environment.stats
    print(f"\nTotal Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"Max Response Time: {stats.total.max_response_time:.2f}ms")
    print(f"Requests/sec: {stats.total.total_rps:.2f}")
    print(f"Failure Rate: {(stats.total.num_failures / stats.total.num_requests * 100) if stats.total.num_requests > 0 else 0:.2f}%")
    print("=" * 80)
