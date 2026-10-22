"""
Stage 2: Add Load Balancer - Technical Hypothesis and Validation
================================================================

This module implements validation and testing for Stage 2's load balancer hypothesis,
addressing the limitations identified in Stage 1's direct public IP approach.

Hypothesis:
    An Application Load Balancer (ALB) with private subnet deployment can provide
    stable endpoint access, automated health monitoring, and improved security
    posture while maintaining the simplicity established in Stage 1.

Architecture Evolution:
    Stage 1: Internet → ECS Fargate (Public Subnet)
    Stage 2: Internet → ALB (Public) → ECS Fargate (Private) → NAT Gateway

Core Improvements:
    ✓ Stable endpoint via ALB DNS name
    ✓ Automated health checking (/v1/health)
    ✓ Network security through private subnets
    ✓ Foundation for horizontal scaling
    ✓ CloudWatch metrics and logging
    ✓ Python package inclusion in container

Expected Outcomes:
    ✓ ALB endpoint accessible within 3 minutes of deployment
    ✓ Health checks pass consistently (>99% success rate)
    ✓ Application response time <2 seconds
    ✓ Zero downtime during task restarts
    ✓ Fargate tasks isolated from direct internet access
    ✓ Main package version reflected in API response

New Limitations Introduced:
    ⚠ Increased cost (~$70-100/month additional)
    ⚠ Additional complexity in networking
    ⚠ HTTP only (no SSL/TLS - addressed in Stage 3)
    ⚠ Single AZ deployment (addressed in Stage 4)

Success Criteria:
    - ALB health checks maintain 99%+ success rate
    - Application accessible via stable ALB DNS name
    - Response time under 2 seconds for all endpoints
    - Task restarts cause <30 seconds of potential impact
    - Private subnet isolation verified

Risk Assessment:
    LOW: ALB reliability and health check accuracy
    MEDIUM: NAT Gateway cost and single point of failure
    HIGH: Application health endpoint reliability (mitigated by robust implementation)

Learning Objectives:
    1. Application Load Balancer configuration and target groups
    2. Private subnet networking and NAT Gateway usage
    3. Health check implementation and monitoring
    4. Security group layered architecture
    5. ALB metrics and logging integration

Next Stage Preparation:
    Stage 3 will add SSL/TLS termination at ALB and custom domain configuration,
    building on the stable endpoint and health monitoring established here.

Example Usage:
    ```python
    # Deploy and validate Stage 2 infrastructure
    from frank_stage2 import deploy_load_balanced_setup, validate_stage2_deployment

    deployment = deploy_load_balanced_setup(
        cluster_name="frank-stage2",
        service_name="frank-app",
        image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/frank:latest"
    )

    # Validate deployment meets hypothesis criteria
    results = validate_stage2_deployment(deployment.alb_dns_name)
    print(f"Stage 2 validation: {results['hypothesis_validated']}")
    ```

Validation Commands:
    ```bash
    # Test stable endpoint
    curl http://frank-alb-xxx.region.elb.amazonaws.com/

    # Verify health checks
    curl http://frank-alb-xxx.region.elb.amazonaws.com/v1/health

    # Monitor ALB metrics
    aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB

    # Check target health
    aws elbv2 describe-target-health --target-group-arn <arn>
    ```
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict

import requests


@dataclass
class Stage2ValidationResult:
    """Results of Stage 2 hypothesis validation."""
    deployment_stage: str
    timestamp: float
    alb_dns_name: str
    tests: Dict
    hypothesis_validated: bool
    ready_for_stage3: bool
    performance_metrics: Dict
    security_validation: Dict


class Stage2HypothesisValidator:
    """
    Comprehensive validation of Stage 2 load balancer hypothesis.

    Tests the following hypothesis components:
    1. Stable endpoint accessibility
    2. Health check reliability
    3. Network security isolation
    4. Performance requirements
    5. Resilience during task operations
    """

    def __init__(self, alb_dns_name: str, region: str = "eu-central-1"):
        self.alb_dns_name = alb_dns_name
        self.region = region
        self.base_url = f"http://{alb_dns_name}"
        self.session = requests.Session()
        self.session.timeout = 10

    def validate_stable_endpoint(self) -> Dict:
        """
        Validate that ALB provides stable endpoint access.

        Tests:
        - Root endpoint accessibility
        - Consistent DNS resolution
        - Response format validation
        """
        test_result = {
            "test_name": "stable_endpoint",
            "hypothesis": "ALB provides stable, consistent endpoint access",
            "status": "UNKNOWN",
            "details": {}
        }

        try:
            # Test root endpoint
            start_time = time.time()
            response = self.session.get(f"{self.base_url}/")
            response_time = time.time() - start_time

            test_result["details"]["root_endpoint"] = {
                "status_code": response.status_code,
                "response_time": response_time,
                "success": response.status_code == 200
            }

            # Test endpoint consistency over multiple requests
            consistency_results = []
            for i in range(5):
                try:
                    resp = self.session.get(f"{self.base_url}/", timeout=5)
                    consistency_results.append(resp.status_code == 200)
                except Exception:
                    consistency_results.append(False)
                time.sleep(1)

            consistency_rate = sum(consistency_results) / len(consistency_results)
            test_result["details"]["consistency"] = {
                "success_rate": consistency_rate,
                "meets_requirement": consistency_rate >= 0.95
            }

            # Overall test success
            endpoint_success = test_result["details"]["root_endpoint"]["success"]
            consistency_success = test_result["details"]["consistency"]["meets_requirement"]

            test_result["status"] = "PASS" if (endpoint_success and consistency_success) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False

        return test_result

    def validate_health_monitoring(self) -> Dict:
        """
        Validate ALB health check functionality.

        Tests:
        - Health endpoint response
        - Health check response time
        - Health endpoint reliability over time
        """
        test_result = {
            "test_name": "health_monitoring",
            "hypothesis": "ALB health checks provide reliable application monitoring",
            "status": "UNKNOWN",
            "details": {}
        }

        try:
            # Test health endpoint response
            start_time = time.time()
            response = self.session.get(f"{self.base_url}/v1/health")
            response_time = time.time() - start_time

            test_result["details"]["health_endpoint"] = {
                "status_code": response.status_code,
                "response_time": response_time,
                "content": response.json() if response.status_code == 200 else None,
                "meets_time_requirement": response_time < 1.0  # <1 second requirement
            }

            # Test health check reliability over time
            health_checks = []
            for i in range(10):
                try:
                    start = time.time()
                    resp = self.session.get(f"{self.base_url}/v1/health", timeout=5)
                    duration = time.time() - start
                    health_checks.append({
                        "success": resp.status_code == 200,
                        "response_time": duration
                    })
                except Exception:
                    health_checks.append({"success": False, "response_time": 5.0})
                time.sleep(2)

            success_rate = sum(1 for check in health_checks if check["success"]) / len(health_checks)
            avg_response_time = sum(check["response_time"] for check in health_checks) / len(health_checks)

            test_result["details"]["reliability"] = {
                "success_rate": success_rate,
                "average_response_time": avg_response_time,
                "meets_reliability_requirement": success_rate >= 0.99,
                "meets_performance_requirement": avg_response_time < 1.0
            }

            # Overall health monitoring success
            endpoint_success = test_result["details"]["health_endpoint"]["status_code"] == 200
            time_success = test_result["details"]["health_endpoint"]["meets_time_requirement"]
            reliability_success = test_result["details"]["reliability"]["meets_reliability_requirement"]

            test_result["status"] = "PASS" if (endpoint_success and time_success and reliability_success) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False

        return test_result

    def validate_performance_requirements(self) -> Dict:
        """
        Validate Stage 2 performance hypothesis.

        Tests:
        - Response time under 2 seconds
        - Concurrent request handling
        - ALB overhead measurement
        """
        test_result = {
            "test_name": "performance_requirements",
            "hypothesis": "ALB adds minimal overhead while maintaining <2s response times",
            "status": "UNKNOWN",
            "details": {}
        }

        try:
            # Single request performance
            start_time = time.time()
            response = self.session.get(f"{self.base_url}/")
            response_time = time.time() - start_time

            test_result["details"]["single_request"] = {
                "response_time": response_time,
                "meets_requirement": response_time < 2.0,
                "status_code": response.status_code
            }

            # Concurrent request testing
            def make_request():
                start = time.time()
                try:
                    resp = self.session.get(f"{self.base_url}/", timeout=10)
                    return {
                        "success": resp.status_code == 200,
                        "response_time": time.time() - start
                    }
                except Exception:
                    return {"success": False, "response_time": 10.0}

            # Test with 5 concurrent requests
            with ThreadPoolExecutor(max_workers=5) as executor:
                concurrent_futures = [executor.submit(make_request) for _ in range(5)]
                concurrent_results = [future.result() for future in as_completed(concurrent_futures)]

            avg_concurrent_time = sum(r["response_time"] for r in concurrent_results) / len(concurrent_results)
            concurrent_success_rate = sum(1 for r in concurrent_results if r["success"]) / len(concurrent_results)

            test_result["details"]["concurrent_requests"] = {
                "average_response_time": avg_concurrent_time,
                "success_rate": concurrent_success_rate,
                "meets_time_requirement": avg_concurrent_time < 2.0,
                "meets_success_requirement": concurrent_success_rate >= 0.95
            }

            # Overall performance validation
            single_success = test_result["details"]["single_request"]["meets_requirement"]
            concurrent_time_success = test_result["details"]["concurrent_requests"]["meets_time_requirement"]
            concurrent_success_success = test_result["details"]["concurrent_requests"]["meets_success_requirement"]

            test_result["status"] = "PASS" if (single_success and concurrent_time_success and concurrent_success_success) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False

        return test_result

    def validate_network_security(self) -> Dict:
        """
        Validate network security hypothesis.

        Note: This test validates what can be validated externally.
        Full private subnet validation requires AWS API access.
        """
        test_result = {
            "test_name": "network_security",
            "hypothesis": "ALB provides secure access layer with private subnet isolation",
            "status": "UNKNOWN",
            "details": {}
        }

        try:
            # Test that only HTTP ports are accessible
            test_result["details"]["http_access"] = {
                "port_80_accessible": self._test_port_access(80),
                "port_443_accessible": self._test_port_access(443),
                "port_22_accessible": self._test_port_access(22),
                "port_8000_accessible": self._test_port_access(8000)
            }

            # Validate that only expected ports are open
            expected_open = test_result["details"]["http_access"]["port_80_accessible"]
            unexpected_closed = (
                not test_result["details"]["http_access"]["port_22_accessible"] and
                not test_result["details"]["http_access"]["port_8000_accessible"]
            )

            test_result["details"]["security_validation"] = {
                "expected_ports_open": expected_open,
                "unexpected_ports_closed": unexpected_closed,
                "security_posture_correct": expected_open and unexpected_closed
            }

            test_result["status"] = "PASS" if test_result["details"]["security_validation"]["security_posture_correct"] else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False

        return test_result

    def _test_port_access(self, port: int) -> bool:
        """Test if a specific port is accessible on the ALB."""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.alb_dns_name, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def run_comprehensive_validation(self) -> Stage2ValidationResult:
        """
        Run complete Stage 2 hypothesis validation.

        Returns:
            Stage2ValidationResult with all test results and overall validation status
        """
        print("Starting Stage 2 Hypothesis Validation...")
        print(f"Testing ALB endpoint: {self.alb_dns_name}")

        # Run all validation tests
        tests = {}

        print("✓ Validating stable endpoint...")
        tests["stable_endpoint"] = self.validate_stable_endpoint()

        print("✓ Validating health monitoring...")
        tests["health_monitoring"] = self.validate_health_monitoring()

        print("✓ Validating performance requirements...")
        tests["performance_requirements"] = self.validate_performance_requirements()

        print("✓ Validating network security...")
        tests["network_security"] = self.validate_network_security()

        # Compile performance metrics
        performance_metrics = {
            "average_response_time": tests["performance_requirements"]["details"].get("single_request", {}).get("response_time", 0),
            "health_check_avg_time": tests["health_monitoring"]["details"].get("reliability", {}).get("average_response_time", 0),
            "concurrent_avg_time": tests["performance_requirements"]["details"].get("concurrent_requests", {}).get("average_response_time", 0),
            "health_success_rate": tests["health_monitoring"]["details"].get("reliability", {}).get("success_rate", 0)
        }

        # Compile security validation
        security_validation = tests["network_security"]["details"].get("security_validation", {})

        # Overall hypothesis validation
        all_tests_passed = all(test.get("hypothesis_met", False) for test in tests.values())

        # Stage 3 readiness assessment
        ready_for_stage3 = (
            all_tests_passed and
            performance_metrics["average_response_time"] < 2.0 and
            performance_metrics["health_success_rate"] >= 0.99
        )

        return Stage2ValidationResult(
            deployment_stage="Stage 2 - Load Balancer",
            timestamp=time.time(),
            alb_dns_name=self.alb_dns_name,
            tests=tests,
            hypothesis_validated=all_tests_passed,
            ready_for_stage3=ready_for_stage3,
            performance_metrics=performance_metrics,
            security_validation=security_validation
        )


def validate_stage2_deployment(alb_dns_name: str, region: str = "eu-central-1") -> Stage2ValidationResult:
    """
    Main validation function for Stage 2 deployment.

    Args:
        alb_dns_name: The DNS name of the Application Load Balancer
        region: AWS region where the deployment exists

    Returns:
        Stage2ValidationResult with comprehensive validation results

    Example:
        ```python
        results = validate_stage2_deployment("frank-alb-xxx.eu-central-1.elb.amazonaws.com")

        if results.hypothesis_validated:
            print("✅ Stage 2 hypothesis validated successfully!")
            if results.ready_for_stage3:
                print("🚀 Ready to proceed to Stage 3 (SSL/HTTPS)")
        else:
            print("❌ Stage 2 hypothesis validation failed")
            for test_name, test_result in results.tests.items():
                if not test_result.get("hypothesis_met", False):
                    print(f"  - {test_name}: {test_result.get('error', 'Requirements not met')}")
        ```
    """
    validator = Stage2HypothesisValidator(alb_dns_name, region)
    return validator.run_comprehensive_validation()


def print_validation_report(results: Stage2ValidationResult):
    """Print a formatted validation report."""
    print("\n" + "="*60)
    print(f"FRANK Application - {results.deployment_stage}")
    print("Hypothesis Validation Report")
    print("="*60)

    print(f"ALB Endpoint: {results.alb_dns_name}")
    print(f"Validation Time: {time.ctime(results.timestamp)}")
    print(f"Overall Status: {'✅ PASSED' if results.hypothesis_validated else '❌ FAILED'}")
    print(f"Stage 3 Ready: {'🚀 YES' if results.ready_for_stage3 else '⏳ NOT YET'}")

    print("\n📊 Performance Metrics:")
    metrics = results.performance_metrics
    print(f"  Average Response Time: {metrics.get('average_response_time', 0):.3f}s")
    print(f"  Health Check Avg Time: {metrics.get('health_check_avg_time', 0):.3f}s")
    print(f"  Concurrent Request Avg: {metrics.get('concurrent_avg_time', 0):.3f}s")
    print(f"  Health Success Rate: {metrics.get('health_success_rate', 0)*100:.1f}%")

    print("\n🔒 Security Validation:")
    security = results.security_validation
    print(f"  Expected Ports Open: {'✅' if security.get('expected_ports_open') else '❌'}")
    print(f"  Unexpected Ports Closed: {'✅' if security.get('unexpected_ports_closed') else '❌'}")
    print(f"  Security Posture: {'✅ CORRECT' if security.get('security_posture_correct') else '❌ ISSUES'}")

    print("\n🧪 Test Results:")
    for test_name, test_result in results.tests.items():
        status_icon = "✅" if test_result.get("hypothesis_met") else "❌"
        print(f"  {status_icon} {test_name}: {test_result.get('status', 'UNKNOWN')}")
        if test_result.get("error"):
            print(f"      Error: {test_result['error']}")

    print("\n" + "="*60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python stage2_hypothesis.py <alb-dns-name> [region]")
        print("Example: python stage2_hypothesis.py frank-alb-xxx.eu-central-1.elb.amazonaws.com")
        sys.exit(1)

    alb_dns_name = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else "eu-central-1"

    # Run validation
    results = validate_stage2_deployment(alb_dns_name, region)

    # Print report
    print_validation_report(results)

    # Exit with appropriate code
    sys.exit(0 if results.hypothesis_validated else 1)
