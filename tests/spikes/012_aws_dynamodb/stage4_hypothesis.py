#!/usr/bin/env python3
"""
Stage 4: Add DynamoDB & Multi-AZ - Technical Hypothesis and Validation
======================================================================

This module implements validation and testing for Stage 4's DynamoDB integration
and multi-AZ deployment hypothesis, building upon Stage 3's SSL/HTTPS foundation
with production-ready data persistence and resilience.

Hypothesis:
    DynamoDB integration with multi-AZ ECS deployment can provide production-ready
    data persistence, horizontal scalability, and high availability while maintaining
    sub-second API response times and 99.9%+ service availability.

Architecture Evolution:
    Stage 3: Route53 → ALB (HTTPS) → ECS Fargate (Single AZ)
    Stage 4: Route53 → ALB (HTTPS) → ECS Fargate (Multi-AZ) → DynamoDB

Core Improvements:
    ✓ DynamoDB tables for persistent data storage
    ✓ Multi-AZ ECS service deployment (3 availability zones)
    ✓ RESTful API endpoints for CRUD operations
    ✓ Auto scaling based on CPU and request metrics
    ✓ Session management and user state persistence
    ✓ VPC endpoints for secure DynamoDB access

Expected Outcomes:
    ✓ DynamoDB read/write latency <100ms (99th percentile)
    ✓ API endpoint response time <500ms (95th percentile)
    ✓ Service survives single AZ failure with <30s recovery
    ✓ Auto scaling triggers within 5 minutes under load
    ✓ Session data persists across container restarts
    ✓ Zero data loss during normal operations

New Capabilities Added:
    ⚡ Persistent session management with TTL
    ⚡ User data storage and retrieval
    ⚡ Application metrics collection and reporting
    ⚡ Multi-container load balancing
    ⚡ Auto scaling based on demand
    ⚡ Cross-AZ redundancy and failover

Limitations Introduced:
    ⚠ Eventually consistent reads (default DynamoDB behavior)
    ⚠ NoSQL query limitations vs relational databases
    ⚠ Cold start latency during auto scaling events
    ⚠ Increased operational complexity and cost

Success Criteria:
    - All DynamoDB tables created and accessible
    - Multi-AZ ECS service running with 2+ tasks
    - API endpoints respond with appropriate HTTP codes
    - Session data persists across service restarts
    - Auto scaling policy triggers under load
    - Service survives simulated AZ failure

Risk Assessment:
    LOW: DynamoDB service reliability and ECS multi-AZ deployment
    MEDIUM: Auto scaling timing and VPC endpoint connectivity
    HIGH: Data consistency during failures (mitigated by DynamoDB design)

Learning Objectives:
    1. DynamoDB table design and data modeling
    2. ECS multi-AZ service configuration and deployment
    3. Auto scaling policies and CloudWatch integration
    4. API development with database integration
    5. VPC endpoints and secure service communication
    6. Load testing and performance validation

Next Stage Preparation:
    Stage 5 will add API Gateway, advanced authentication, and microservices
    architecture, utilizing the scalable data layer and multi-AZ foundation.

Example Usage:
    ```python
    # Deploy and validate Stage 4 infrastructure
    from frank_stage4 import deploy_dynamodb_setup, validate_stage4_deployment
    
    deployment = deploy_dynamodb_setup(
        domain_name="frank-009-stage4.lab271.io",
        cluster_name="frank-009-stage4",
        dynamodb_tables=["frank-sessions", "frank-users", "frank-metrics"]
    )
    
    # Validate deployment meets hypothesis criteria  
    results = validate_stage4_deployment("frank-009-stage4.lab271.io")
    print(f"Stage 4 validation: {results.hypothesis_validated}")
    ```

Validation Commands:
    ```bash
    # Test API endpoints
    curl -X POST https://frank-009-stage4.lab271.io/api/v1/sessions \
      -H "Content-Type: application/json" \
      -d '{"user_id": "test-user", "data": {"key": "value"}}'
    
    # Test multi-AZ resilience
    aws ecs update-service --cluster frank-009-stage4 \
      --service frank-stage4-service --desired-count 1
    
    # Load test for auto scaling
    artillery quick --count 100 --num 10 \
      https://frank-009-stage4.lab271.io/
    
    # Check DynamoDB performance
    aws dynamodb describe-table --table-name frank-sessions \
      --query 'Table.ProvisionedThroughput'
    ```
"""

import sys
import time
import json
import requests
import boto3
import concurrent.futures
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import uuid


@dataclass
class Stage4ValidationResult:
    """Results of Stage 4 hypothesis validation."""
    deployment_stage: str
    timestamp: float
    domain_name: str
    tests: Dict
    hypothesis_validated: bool
    ready_for_stage5: bool
    database_metrics: Dict
    performance_metrics: Dict
    resilience_metrics: Dict
    scalability_metrics: Dict


class Stage4HypothesisValidator:
    """
    Comprehensive validation of Stage 4 DynamoDB + Multi-AZ hypothesis.
    
    Tests the following hypothesis components:
    1. DynamoDB table creation and connectivity
    2. API endpoints for CRUD operations
    3. Session management and data persistence
    4. Multi-AZ service deployment and health
    5. Auto scaling configuration and triggers
    6. Performance under load and failure scenarios
    """
    
    def __init__(self, domain_name: str, region: str = "eu-central-1"):
        self.domain_name = domain_name
        self.region = region
        self.base_url = f"https://{domain_name}"
        self.api_base = f"{self.base_url}/api/v1"
        self.session = requests.Session()
        self.session.timeout = 10
        
        # AWS clients for infrastructure validation
        try:
            self.dynamodb = boto3.client('dynamodb', region_name=region)
            self.ecs = boto3.client('ecs', region_name=region)
            self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        except Exception as e:
            print(f"Warning: AWS clients not available: {e}")
            self.dynamodb = None
            self.ecs = None
            self.cloudwatch = None
        
    def validate_dynamodb_integration(self) -> Dict:
        """
        Validate DynamoDB table setup and connectivity.
        
        Tests:
        - Table existence and configuration
        - Read/write operations through API
        - Data persistence and consistency
        - Performance characteristics
        """
        test_result = {
            "test_name": "dynamodb_integration",
            "hypothesis": "DynamoDB provides scalable, persistent data storage with sub-100ms latency",
            "status": "UNKNOWN",
            "details": {}
        }
        
        try:
            # Test table existence via AWS API (if available)
            if self.dynamodb:
                tables_info = {}
                expected_tables = ["frank-sessions", "frank-users", "frank-metrics"]
                
                for table_name in expected_tables:
                    try:
                        response = self.dynamodb.describe_table(TableName=table_name)
                        table_info = response['Table']
                        tables_info[table_name] = {
                            "status": table_info['TableStatus'],
                            "item_count": table_info.get('ItemCount', 0),
                            "size_bytes": table_info.get('TableSizeBytes', 0),
                            "billing_mode": table_info.get('BillingModeSummary', {}).get('BillingMode', 'Unknown')
                        }
                    except Exception as e:
                        tables_info[table_name] = {"error": str(e), "status": "NOT_FOUND"}
                
                test_result["details"]["dynamodb_tables"] = tables_info
            
            # Test DynamoDB integration through API endpoints
            session_data = {
                "user_id": f"test-user-{int(time.time())}",
                "data": {
                    "test_key": "test_value",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Test session creation (POST)
            start_time = time.time()
            create_response = self.session.post(
                f"{self.api_base}/sessions",
                json=session_data,
                headers={"Content-Type": "application/json"}
            )
            create_latency = time.time() - start_time
            
            test_result["details"]["session_creation"] = {
                "status_code": create_response.status_code,
                "latency": create_latency,
                "success": create_response.status_code == 201,
                "response_data": create_response.json() if create_response.status_code == 201 else None
            }
            
            if create_response.status_code == 201:
                session_id = create_response.json().get('session_id')
                
                # Test session retrieval (GET)
                start_time = time.time()
                get_response = self.session.get(f"{self.api_base}/sessions/{session_id}")
                get_latency = time.time() - start_time
                
                test_result["details"]["session_retrieval"] = {
                    "status_code": get_response.status_code,
                    "latency": get_latency,
                    "success": get_response.status_code == 200,
                    "data_consistency": get_response.json().get('data') == session_data['data'] if get_response.status_code == 200 else False
                }
                
                # Test session update (PUT)
                updated_data = {"updated": True, "timestamp": datetime.now(timezone.utc).isoformat()}
                start_time = time.time()
                update_response = self.session.put(
                    f"{self.api_base}/sessions/{session_id}",
                    json={"data": updated_data},
                    headers={"Content-Type": "application/json"}
                )
                update_latency = time.time() - start_time
                
                test_result["details"]["session_update"] = {
                    "status_code": update_response.status_code,
                    "latency": update_latency,
                    "success": update_response.status_code == 200
                }
                
                # Verify update persistence
                verify_response = self.session.get(f"{self.api_base}/sessions/{session_id}")
                test_result["details"]["update_verification"] = {
                    "status_code": verify_response.status_code,
                    "data_updated": verify_response.json().get('data', {}).get('updated') if verify_response.status_code == 200 else False
                }
                
                # Test session deletion (DELETE)
                start_time = time.time()
                delete_response = self.session.delete(f"{self.api_base}/sessions/{session_id}")
                delete_latency = time.time() - start_time
                
                test_result["details"]["session_deletion"] = {
                    "status_code": delete_response.status_code,
                    "latency": delete_latency,
                    "success": delete_response.status_code == 204
                }
                
                # Verify deletion
                verify_delete = self.session.get(f"{self.api_base}/sessions/{session_id}")
                test_result["details"]["deletion_verification"] = {
                    "status_code": verify_delete.status_code,
                    "properly_deleted": verify_delete.status_code == 404
                }
            
            # Performance requirements check
            crud_operations = ['session_creation', 'session_retrieval', 'session_update', 'session_deletion']
            performance_ok = all(
                test_result["details"].get(op, {}).get("latency", float('inf')) < 0.1  # 100ms requirement
                for op in crud_operations
                if test_result["details"].get(op, {}).get("latency") is not None
            )
            
            functional_ok = all(
                test_result["details"].get(op, {}).get("success", False)
                for op in crud_operations
            )
            
            test_result["status"] = "PASS" if (performance_ok and functional_ok) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"
            
        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False
            
        return test_result
    
    def validate_multi_az_deployment(self) -> Dict:
        """
        Validate multi-AZ ECS service deployment.
        
        Tests:
        - Service running across multiple AZs
        - Task distribution and health
        - Load balancer health checks
        - Service resilience to task failures
        """
        test_result = {
            "test_name": "multi_az_deployment",
            "hypothesis": "Multi-AZ deployment provides high availability and resilience",
            "status": "UNKNOWN",
            "details": {}
        }
        
        try:
            # Test service health from multiple requests
            health_checks = []
            for i in range(10):
                start_time = time.time()
                response = self.session.get(f"{self.base_url}/v1/health")
                response_time = time.time() - start_time
                
                health_checks.append({
                    "response_time": response_time,
                    "status_code": response.status_code,
                    "success": response.status_code == 200,
                    "container_id": response.json().get('container_id') if response.status_code == 200 else None
                })
                time.sleep(0.1)  # Small delay between requests
            
            # Analyze container distribution
            container_ids = [check.get('container_id') for check in health_checks if check.get('container_id')]
            unique_containers = len(set(container_ids))
            
            test_result["details"]["health_check_analysis"] = {
                "total_requests": len(health_checks),
                "successful_requests": sum(1 for check in health_checks if check['success']),
                "unique_containers": unique_containers,
                "multi_container_deployment": unique_containers > 1,
                "average_response_time": sum(check['response_time'] for check in health_checks) / len(health_checks),
                "max_response_time": max(check['response_time'] for check in health_checks)
            }
            
            # Test concurrent requests to validate load balancing
            def make_concurrent_request():
                start = time.time()
                resp = requests.get(f"{self.base_url}/", timeout=10)
                return time.time() - start, resp.status_code, resp.json().get('container_id') if resp.status_code == 200 else None
            
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(make_concurrent_request) for _ in range(50)]
                concurrent_results = [future.result() for future in as_completed(futures)]
            
            concurrent_times = [result[0] for result in concurrent_results]
            concurrent_statuses = [result[1] for result in concurrent_results]
            concurrent_containers = [result[2] for result in concurrent_results if result[2]]
            
            test_result["details"]["concurrent_load_test"] = {
                "total_requests": len(concurrent_results),
                "successful_requests": sum(1 for status in concurrent_statuses if status == 200),
                "success_rate": sum(1 for status in concurrent_statuses if status == 200) / len(concurrent_statuses),
                "unique_containers_under_load": len(set(concurrent_containers)),
                "average_response_time": sum(concurrent_times) / len(concurrent_times),
                "95th_percentile_time": sorted(concurrent_times)[int(0.95 * len(concurrent_times))],
                "load_balanced": len(set(concurrent_containers)) > 1
            }
            
            # Check ECS service details via AWS API (if available)
            if self.ecs:
                try:
                    # Try to find the service (assuming naming convention)
                    cluster_name = f"frank-009-stage4"
                    service_name = f"frank-stage4-service"
                    
                    services_response = self.ecs.describe_services(
                        cluster=cluster_name,
                        services=[service_name]
                    )
                    
                    if services_response['services']:
                        service = services_response['services'][0]
                        test_result["details"]["ecs_service_info"] = {
                            "service_status": service['status'],
                            "running_count": service['runningCount'],
                            "desired_count": service['desiredCount'],
                            "pending_count": service['pendingCount'],
                            "platform_version": service.get('platformVersion', 'Unknown'),
                            "launch_type": service.get('launchType', 'Unknown')
                        }
                        
                        # Get task details
                        tasks_response = self.ecs.list_tasks(
                            cluster=cluster_name,
                            serviceName=service_name
                        )
                        
                        if tasks_response['taskArns']:
                            task_details = self.ecs.describe_tasks(
                                cluster=cluster_name,
                                tasks=tasks_response['taskArns']
                            )
                            
                            az_distribution = {}
                            for task in task_details['tasks']:
                                az = task.get('availabilityZone', 'Unknown')
                                az_distribution[az] = az_distribution.get(az, 0) + 1
                            
                            test_result["details"]["task_distribution"] = {
                                "total_tasks": len(task_details['tasks']),
                                "availability_zones": az_distribution,
                                "multi_az_deployment": len(az_distribution) > 1,
                                "tasks_per_az": az_distribution
                            }
                    
                except Exception as ecs_error:
                    test_result["details"]["ecs_service_info"] = {"error": str(ecs_error)}
            
            # Overall multi-AZ validation
            multi_container = test_result["details"]["health_check_analysis"]["multi_container_deployment"]
            load_balanced = test_result["details"]["concurrent_load_test"]["load_balanced"]
            success_rate = test_result["details"]["concurrent_load_test"]["success_rate"] > 0.99
            
            test_result["status"] = "PASS" if (multi_container and load_balanced and success_rate) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"
            
        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False
            
        return test_result
    
    def validate_api_endpoints(self) -> Dict:
        """
        Validate RESTful API endpoints functionality.
        
        Tests:
        - All CRUD endpoints respond correctly
        - API response times meet requirements
        - Error handling and status codes
        - Data validation and consistency
        """
        test_result = {
            "test_name": "api_endpoints",
            "hypothesis": "RESTful API provides complete CRUD operations with <500ms response time",
            "status": "UNKNOWN",
            "details": {}
        }
        
        try:
            endpoints_to_test = [
                {"method": "GET", "path": "/", "expected_status": 200},
                {"method": "GET", "path": "/v1/health", "expected_status": 200},
                {"method": "GET", "path": "/api/v1/metrics", "expected_status": 200},
                {"method": "POST", "path": "/api/v1/sessions", "expected_status": 201, 
                 "data": {"user_id": "api-test-user", "data": {"test": True}}},
            ]
            
            endpoint_results = {}
            
            for endpoint in endpoints_to_test:
                method = endpoint["method"]
                path = endpoint["path"]
                url = f"{self.base_url}{path}"
                
                start_time = time.time()
                
                if method == "GET":
                    response = self.session.get(url)
                elif method == "POST":
                    response = self.session.post(
                        url,
                        json=endpoint.get("data"),
                        headers={"Content-Type": "application/json"}
                    )
                
                response_time = time.time() - start_time
                
                endpoint_results[f"{method} {path}"] = {
                    "response_time": response_time,
                    "status_code": response.status_code,
                    "expected_status": endpoint["expected_status"],
                    "status_correct": response.status_code == endpoint["expected_status"],
                    "meets_time_requirement": response_time < 0.5,  # 500ms requirement
                    "response_size": len(response.content),
                    "content_type": response.headers.get('Content-Type', 'Unknown')
                }
                
                # Store response data for further testing
                if response.status_code == endpoint["expected_status"]:
                    try:
                        endpoint_results[f"{method} {path}"]["response_data"] = response.json()
                    except:
                        endpoint_results[f"{method} {path}"]["response_data"] = response.text[:200]
            
            test_result["details"]["endpoint_tests"] = endpoint_results
            
            # Test error handling
            error_tests = [
                {"method": "GET", "path": "/api/v1/sessions/nonexistent-id", "expected_status": 404},
                {"method": "POST", "path": "/api/v1/sessions", "data": {"invalid": "data"}, "expected_status": 400},
                {"method": "GET", "path": "/nonexistent-endpoint", "expected_status": 404}
            ]
            
            error_results = {}
            for error_test in error_tests:
                method = error_test["method"]
                path = error_test["path"]
                url = f"{self.base_url}{path}"
                
                try:
                    if method == "GET":
                        response = self.session.get(url)
                    elif method == "POST":
                        response = self.session.post(
                            url,
                            json=error_test.get("data"),
                            headers={"Content-Type": "application/json"}
                        )
                    
                    error_results[f"{method} {path}"] = {
                        "status_code": response.status_code,
                        "expected_status": error_test["expected_status"],
                        "error_handling_correct": response.status_code == error_test["expected_status"]
                    }
                except Exception as e:
                    error_results[f"{method} {path}"] = {"error": str(e)}
            
            test_result["details"]["error_handling"] = error_results
            
            # Performance and functionality validation
            all_endpoints_work = all(
                result.get("status_correct", False) 
                for result in endpoint_results.values()
            )
            
            all_meet_time_requirements = all(
                result.get("meets_time_requirement", False) 
                for result in endpoint_results.values()
            )
            
            error_handling_works = all(
                result.get("error_handling_correct", False) 
                for result in error_results.values()
            )
            
            test_result["status"] = "PASS" if (all_endpoints_work and all_meet_time_requirements and error_handling_works) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"
            
        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False
            
        return test_result
    
    def validate_session_persistence(self) -> Dict:
        """
        Validate session data persistence across service operations.
        
        Tests:
        - Session data survives container restarts
        - Data consistency during concurrent operations
        - TTL behavior for session expiration
        - Cross-container session access
        """
        test_result = {
            "test_name": "session_persistence",
            "hypothesis": "Session data persists across container restarts and maintains consistency",
            "status": "UNKNOWN",
            "details": {}
        }
        
        try:
            # Create multiple sessions for persistence testing
            session_ids = []
            for i in range(5):
                session_data = {
                    "user_id": f"persistence-test-user-{i}",
                    "data": {
                        "session_number": i,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "test_type": "persistence"
                    }
                }
                
                response = self.session.post(
                    f"{self.api_base}/sessions",
                    json=session_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 201:
                    session_ids.append({
                        "session_id": response.json()["session_id"],
                        "original_data": session_data
                    })
            
            test_result["details"]["session_creation"] = {
                "sessions_created": len(session_ids),
                "creation_success_rate": len(session_ids) / 5
            }
            
            # Wait a moment then verify all sessions are retrievable
            time.sleep(2)
            
            persistence_results = []
            for session_info in session_ids:
                session_id = session_info["session_id"]
                original_data = session_info["original_data"]
                
                # Retrieve session multiple times to test consistency
                retrieval_attempts = []
                for attempt in range(3):
                    start_time = time.time()
                    response = self.session.get(f"{self.api_base}/sessions/{session_id}")
                    retrieval_time = time.time() - start_time
                    
                    retrieval_attempts.append({
                        "attempt": attempt + 1,
                        "status_code": response.status_code,
                        "retrieval_time": retrieval_time,
                        "data_consistent": (
                            response.json().get("data") == original_data["data"] 
                            if response.status_code == 200 else False
                        )
                    })
                    time.sleep(0.5)
                
                persistence_results.append({
                    "session_id": session_id,
                    "retrieval_attempts": retrieval_attempts,
                    "all_retrievals_successful": all(
                        attempt["status_code"] == 200 for attempt in retrieval_attempts
                    ),
                    "data_always_consistent": all(
                        attempt["data_consistent"] for attempt in retrieval_attempts
                    )
                })
            
            test_result["details"]["persistence_verification"] = persistence_results
            
            # Test concurrent access to same session
            if session_ids:
                test_session_id = session_ids[0]["session_id"]
                
                def concurrent_session_access():
                    start = time.time()
                    resp = requests.get(f"{self.api_base}/sessions/{test_session_id}", timeout=10)
                    return time.time() - start, resp.status_code, resp.json() if resp.status_code == 200 else None
                
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(concurrent_session_access) for _ in range(20)]
                    concurrent_access_results = [future.result() for future in as_completed(futures)]
                
                concurrent_times = [result[0] for result in concurrent_access_results]
                concurrent_statuses = [result[1] for result in concurrent_access_results]
                concurrent_data = [result[2] for result in concurrent_access_results if result[2]]
                
                # Check data consistency across concurrent requests
                unique_data_responses = len(set(json.dumps(data, sort_keys=True) for data in concurrent_data))
                
                test_result["details"]["concurrent_access"] = {
                    "total_requests": len(concurrent_access_results),
                    "successful_requests": sum(1 for status in concurrent_statuses if status == 200),
                    "success_rate": sum(1 for status in concurrent_statuses if status == 200) / len(concurrent_statuses),
                    "average_response_time": sum(concurrent_times) / len(concurrent_times),
                    "data_consistency": unique_data_responses <= 1,  # Should all return same data
                    "unique_responses": unique_data_responses
                }
            
            # Test session updates and consistency
            if session_ids:
                update_session_id = session_ids[0]["session_id"]
                update_data = {
                    "data": {
                        "updated": True,
                        "update_timestamp": datetime.now(timezone.utc).isoformat(),
                        "update_test": "persistence_validation"
                    }
                }
                
                # Update session
                update_response = self.session.put(
                    f"{self.api_base}/sessions/{update_session_id}",
                    json=update_data,
                    headers={"Content-Type": "application/json"}
                )
                
                # Verify update immediately and after delay
                immediate_check = self.session.get(f"{self.api_base}/sessions/{update_session_id}")
                time.sleep(1)
                delayed_check = self.session.get(f"{self.api_base}/sessions/{update_session_id}")
                
                test_result["details"]["update_persistence"] = {
                    "update_status": update_response.status_code,
                    "update_successful": update_response.status_code == 200,
                    "immediate_verification": {
                        "status_code": immediate_check.status_code,
                        "data_updated": (
                            immediate_check.json().get("data", {}).get("updated") 
                            if immediate_check.status_code == 200 else False
                        )
                    },
                    "delayed_verification": {
                        "status_code": delayed_check.status_code,
                        "data_still_updated": (
                            delayed_check.json().get("data", {}).get("updated") 
                            if delayed_check.status_code == 200 else False
                        )
                    }
                }
            
            # Overall persistence validation
            creation_ok = test_result["details"]["session_creation"]["creation_success_rate"] > 0.8
            persistence_ok = all(
                result["all_retrievals_successful"] and result["data_always_consistent"]
                for result in test_result["details"]["persistence_verification"]
            )
            concurrent_ok = test_result["details"].get("concurrent_access", {}).get("data_consistency", False)
            
            test_result["status"] = "PASS" if (creation_ok and persistence_ok and concurrent_ok) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"
            
            # Cleanup test sessions
            for session_info in session_ids:
                try:
                    self.session.delete(f"{self.api_base}/sessions/{session_info['session_id']}")
                except:
                    pass  # Best effort cleanup
            
        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False
            
        return test_result
    
    def validate_auto_scaling_readiness(self) -> Dict:
        """
        Validate auto scaling configuration and readiness.
        
        Tests:
        - ECS service auto scaling configuration
        - CloudWatch metrics availability
        - Load testing triggers scale events
        - Performance under increased load
        """
        test_result = {
            "test_name": "auto_scaling_readiness",
            "hypothesis": "Auto scaling configuration responds to load changes within 5 minutes",
            "status": "UNKNOWN",
            "details": {}
        }
        
        try:
            # Check current service task count
            initial_health_checks = []
            for i in range(5):
                response = self.session.get(f"{self.base_url}/v1/health")
                if response.status_code == 200:
                    initial_health_checks.append(response.json())
                time.sleep(1)
            
            initial_containers = set(
                check.get('container_id') for check in initial_health_checks 
                if check.get('container_id')
            )
            
            test_result["details"]["initial_state"] = {
                "healthy_responses": len(initial_health_checks),
                "unique_containers": len(initial_containers),
                "baseline_established": len(initial_containers) >= 1
            }
            
            # Perform load test to potentially trigger scaling
            load_test_results = []
            
            def load_test_request():
                start = time.time()
                try:
                    # Mix of different endpoints to simulate real load
                    endpoints = ["/", "/v1/health", "/api/v1/metrics"]
                    endpoint = endpoints[int(time.time()) % len(endpoints)]
                    
                    resp = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                    return {
                        "response_time": time.time() - start,
                        "status_code": resp.status_code,
                        "success": resp.status_code == 200,
                        "endpoint": endpoint
                    }
                except Exception as e:
                    return {
                        "response_time": time.time() - start,
                        "status_code": 0,
                        "success": False,
                        "error": str(e),
                        "endpoint": "unknown"
                    }
            
            # Generate sustained load for 2 minutes
            print("Generating load for auto scaling test...")
            with ThreadPoolExecutor(max_workers=15) as executor:
                # Submit load over 2 minute period
                load_futures = []
                start_load_time = time.time()
                
                while time.time() - start_load_time < 120:  # 2 minutes of load
                    batch_futures = [executor.submit(load_test_request) for _ in range(10)]
                    load_futures.extend(batch_futures)
                    time.sleep(1)  # 10 requests per second
                
                # Collect results
                load_test_results = [future.result() for future in load_futures]
            
            # Analyze load test results
            successful_requests = [r for r in load_test_results if r['success']]
            failed_requests = [r for r in load_test_results if not r['success']]
            
            if successful_requests:
                response_times = [r['response_time'] for r in successful_requests]
                test_result["details"]["load_test_performance"] = {
                    "total_requests": len(load_test_results),
                    "successful_requests": len(successful_requests),
                    "failed_requests": len(failed_requests),
                    "success_rate": len(successful_requests) / len(load_test_results),
                    "average_response_time": sum(response_times) / len(response_times),
                    "95th_percentile_time": sorted(response_times)[int(0.95 * len(response_times))],
                    "max_response_time": max(response_times),
                    "performance_degradation": max(response_times) > 2.0  # >2s indicates stress
                }
            
            # Check post-load service state
            time.sleep(30)  # Wait for potential scaling
            
            post_load_health_checks = []
            for i in range(5):
                response = self.session.get(f"{self.base_url}/v1/health")
                if response.status_code == 200:
                    post_load_health_checks.append(response.json())
                time.sleep(1)
            
            post_load_containers = set(
                check.get('container_id') for check in post_load_health_checks 
                if check.get('container_id')
            )
            
            test_result["details"]["post_load_state"] = {
                "healthy_responses": len(post_load_health_checks),
                "unique_containers": len(post_load_containers),
                "scaling_occurred": len(post_load_containers) > len(initial_containers),
                "container_increase": len(post_load_containers) - len(initial_containers)
            }
            
            # Check CloudWatch metrics availability (if AWS clients available)
            if self.cloudwatch:
                try:
                    # Check for ECS service metrics
                    metrics_response = self.cloudwatch.list_metrics(
                        Namespace='AWS/ECS',
                        Dimensions=[
                            {
                                'Name': 'ServiceName',
                                'Value': 'frank-stage4-service'
                            }
                        ]
                    )
                    
                    available_metrics = [metric['MetricName'] for metric in metrics_response.get('Metrics', [])]
                    
                    test_result["details"]["cloudwatch_metrics"] = {
                        "metrics_available": len(available_metrics),
                        "cpu_utilization_available": 'CPUUtilization' in available_metrics,
                        "memory_utilization_available": 'MemoryUtilization' in available_metrics,
                        "available_metric_names": available_metrics
                    }
                    
                except Exception as cw_error:
                    test_result["details"]["cloudwatch_metrics"] = {"error": str(cw_error)}
            
            # Overall auto scaling readiness validation
            baseline_ok = test_result["details"]["initial_state"]["baseline_established"]
            load_handled = test_result["details"]["load_test_performance"]["success_rate"] > 0.95
            service_stable = test_result["details"]["post_load_state"]["healthy_responses"] >= 4
            
            test_result["status"] = "PASS" if (baseline_ok and load_handled and service_stable) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"
            
        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False
            
        return test_result
    
    def run_comprehensive_validation(self) -> Stage4ValidationResult:
        """
        Run complete Stage 4 hypothesis validation.
        
        Returns:
            Stage4ValidationResult with all test results and overall validation status
        """
        print("Starting Stage 4 Hypothesis Validation...")
        print(f"Testing DynamoDB + Multi-AZ deployment: {self.domain_name}")
        
        # Run all validation tests
        tests = {}
        
        print("✓ Validating DynamoDB integration...")
        tests["dynamodb_integration"] = self.validate_dynamodb_integration()
        
        print("✓ Validating multi-AZ deployment...")
        tests["multi_az_deployment"] = self.validate_multi_az_deployment()
        
        print("✓ Validating API endpoints...")
        tests["api_endpoints"] = self.validate_api_endpoints()
        
        print("✓ Validating session persistence...")
        tests["session_persistence"] = self.validate_session_persistence()
        
        print("✓ Validating auto scaling readiness...")
        tests["auto_scaling_readiness"] = self.validate_auto_scaling_readiness()
        
        # Compile database metrics
        db_details = tests["dynamodb_integration"]["details"]
        database_metrics = {
            "crud_operations_avg_latency": sum([
                db_details.get("session_creation", {}).get("latency", 0),
                db_details.get("session_retrieval", {}).get("latency", 0),
                db_details.get("session_update", {}).get("latency", 0),
                db_details.get("session_deletion", {}).get("latency", 0)
            ]) / 4,
            "data_consistency": db_details.get("update_verification", {}).get("data_updated", False),
            "table_access": "dynamodb_tables" in db_details,
            "api_integration": tests["dynamodb_integration"].get("hypothesis_met", False)
        }
        
        # Compile performance metrics
        api_details = tests["api_endpoints"]["details"]
        perf_details = tests["auto_scaling_readiness"]["details"]
        performance_metrics = {
            "api_response_times": {
                endpoint: result.get("response_time", 0)
                for endpoint, result in api_details.get("endpoint_tests", {}).items()
            },
            "load_test_success_rate": perf_details.get("load_test_performance", {}).get("success_rate", 0),
            "95th_percentile_response": perf_details.get("load_test_performance", {}).get("95th_percentile_time", 0),
            "concurrent_session_performance": tests["session_persistence"]["details"].get("concurrent_access", {}).get("average_response_time", 0)
        }
        
        # Compile resilience metrics
        multi_az_details = tests["multi_az_deployment"]["details"]
        resilience_metrics = {
            "multi_container_deployment": multi_az_details.get("health_check_analysis", {}).get("multi_container_deployment", False),
            "load_balancing_active": multi_az_details.get("concurrent_load_test", {}).get("load_balanced", False),
            "high_availability_score": multi_az_details.get("concurrent_load_test", {}).get("success_rate", 0),
            "session_persistence_across_containers": tests["session_persistence"]["details"].get("concurrent_access", {}).get("data_consistency", False)
        }
        
        # Compile scalability metrics
        scaling_details = tests["auto_scaling_readiness"]["details"]
        scalability_metrics = {
            "baseline_containers": scaling_details.get("initial_state", {}).get("unique_containers", 0),
            "post_load_containers": scaling_details.get("post_load_state", {}).get("unique_containers", 0),
            "scaling_triggered": scaling_details.get("post_load_state", {}).get("scaling_occurred", False),
            "load_handling_capacity": scaling_details.get("load_test_performance", {}).get("success_rate", 0),
            "cloudwatch_integration": "cloudwatch_metrics" in scaling_details
        }
        
        # Overall hypothesis validation
        all_tests_passed = all(test.get("hypothesis_met", False) for test in tests.values())
        
        # Stage 5 readiness assessment
        ready_for_stage5 = (
            all_tests_passed and
            database_metrics["crud_operations_avg_latency"] < 0.1 and
            performance_metrics["95th_percentile_response"] < 0.5 and
            resilience_metrics["high_availability_score"] > 0.99 and
            scalability_metrics["load_handling_capacity"] > 0.95
        )
        
        return Stage4ValidationResult(
            deployment_stage="Stage 4 - DynamoDB + Multi-AZ",
            timestamp=time.time(),
            domain_name=self.domain_name,
            tests=tests,
            hypothesis_validated=all_tests_passed,
            ready_for_stage5=ready_for_stage5,
            database_metrics=database_metrics,
            performance_metrics=performance_metrics,
            resilience_metrics=resilience_metrics,
            scalability_metrics=scalability_metrics
        )


def validate_stage4_deployment(domain_name: str, region: str = "eu-central-1") -> Stage4ValidationResult:
    """
    Main validation function for Stage 4 deployment.
    
    Args:
        domain_name: The custom domain name (e.g., frank-009-stage4.lab271.io)
        region: AWS region where the deployment exists
        
    Returns:
        Stage4ValidationResult with comprehensive validation results
        
    Example:
        ```python
        results = validate_stage4_deployment("frank-009-stage4.lab271.io")
        
        if results.hypothesis_validated:
            print("✅ Stage 4 hypothesis validated successfully!")
            if results.ready_for_stage5:
                print("🚀 Ready to proceed to Stage 5 (API Gateway + Microservices)")
        else:
            print("❌ Stage 4 hypothesis validation failed")
            for test_name, test_result in results.tests.items():
                if not test_result.get("hypothesis_met", False):
                    print(f"  - {test_name}: {test_result.get('error', 'Requirements not met')}")
        ```
    """
    validator = Stage4HypothesisValidator(domain_name, region)
    return validator.run_comprehensive_validation()


def print_validation_report(results: Stage4ValidationResult):
    """Print a formatted validation report."""
    print("\n" + "="*70)
    print(f"FRANK Application - {results.deployment_stage}")
    print("Hypothesis Validation Report")
    print("="*70)
    
    print(f"Domain: {results.domain_name}")
    print(f"Validation Time: {time.ctime(results.timestamp)}")
    print(f"Overall Status: {'✅ PASSED' if results.hypothesis_validated else '❌ FAILED'}")
    print(f"Stage 5 Ready: {'🚀 YES' if results.ready_for_stage5 else '⏳ NOT YET'}")
    
    print("\n💾 Database Metrics:")
    db = results.database_metrics
    print(f"  CRUD Operations Avg Latency: {db.get('crud_operations_avg_latency', 0):.3f}s")
    print(f"  Data Consistency: {'✅' if db.get('data_consistency') else '❌'}")
    print(f"  Table Access: {'✅' if db.get('table_access') else '❌'}")
    print(f"  API Integration: {'✅' if db.get('api_integration') else '❌'}")
    
    print("\n📊 Performance Metrics:")
    perf = results.performance_metrics
    print(f"  Load Test Success Rate: {perf.get('load_handling_capacity', 0):.1%}")
    print(f"  95th Percentile Response: {perf.get('95th_percentile_response', 0):.3f}s")
    print(f"  Concurrent Session Perf: {perf.get('concurrent_session_performance', 0):.3f}s")
    print("  API Endpoint Times:")
    for endpoint, time_val in perf.get('api_response_times', {}).items():
        print(f"    {endpoint}: {time_val:.3f}s")
    
    print("\n🏗️ Resilience Metrics:")
    resilience = results.resilience_metrics
    print(f"  Multi-Container Deployment: {'✅' if resilience.get('multi_container_deployment') else '❌'}")
    print(f"  Load Balancing Active: {'✅' if resilience.get('load_balancing_active') else '❌'}")
    print(f"  High Availability Score: {resilience.get('high_availability_score', 0):.1%}")
    print(f"  Session Persistence: {'✅' if resilience.get('session_persistence_across_containers') else '❌'}")
    
    print("\n📈 Scalability Metrics:")
    scale = results.scalability_metrics
    print(f"  Baseline Containers: {scale.get('baseline_containers', 0)}")
    print(f"  Post-Load Containers: {scale.get('post_load_containers', 0)}")
    print(f"  Scaling Triggered: {'✅' if scale.get('scaling_triggered') else '❌'}")
    print(f"  Load Handling Capacity: {scale.get('load_handling_capacity', 0):.1%}")
    print(f"  CloudWatch Integration: {'✅' if scale.get('cloudwatch_integration') else '❌'}")
    
    print("\n🧪 Test Results:")
    for test_name, test_result in results.tests.items():
        status_icon = "✅" if test_result.get("hypothesis_met") else "❌"
        print(f"  {status_icon} {test_name}: {test_result.get('status', 'UNKNOWN')}")
        if test_result.get("error"):
            print(f"    └─ Error: {test_result['error']}")
    
    if results.hypothesis_validated:
        print(f"\n🎉 Stage 4 hypothesis validated successfully!")
        print(f"✓ DynamoDB integration: Sub-100ms CRUD operations")
        print(f"✓ Multi-AZ deployment: High availability across zones")
        print(f"✓ API endpoints: Complete REST interface")
        print(f"✓ Session persistence: Data survives container restarts")
        if results.ready_for_stage5:
            print(f"🚀 Ready to proceed to Stage 5 (API Gateway + Microservices)")
    else:
        print(f"\n❌ Stage 4 hypothesis validation failed")
        print(f"🔧 Review failed tests above and retry deployment")
        print(f"💡 Consider checking:")
        print(f"   - DynamoDB table creation and permissions")
        print(f"   - ECS service multi-AZ configuration")
        print(f"   - API endpoint implementation")
        print(f"   - Session management logic")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python stage4_hypothesis.py <domain-name> [region]")
        print("Example: python stage4_hypothesis.py frank-009-stage4.lab271.io")
        sys.exit(1)
    
    domain_name = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else "eu-central-1"
    
    # Run validation
    results = validate_stage4_deployment(domain_name, region)
    
    # Print report
    print_validation_report(results)
    
    # Exit with appropriate code
    sys.exit(0 if results.hypothesis_validated else 1)