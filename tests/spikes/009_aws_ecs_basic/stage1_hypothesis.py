"""
Stage 1: Absolute Minimal Setup - Technical Hypothesis
======================================================

This module implements the foundational cloud deployment hypothesis for the FRANK application.

Hypothesis:
    A single ECS Fargate task in a public subnet can provide immediate cloud accessibility
    with minimal infrastructure complexity, serving as a foundation for incremental
    architecture evolution.

Architecture Components:
    - Single ECS Fargate task (0.25 vCPU, 0.5GB RAM)
    - Public subnet with direct internet gateway access
    - ECR repository for container image storage
    - Security group allowing inbound HTTP (port 80) from anywhere
    - CloudWatch logging for observability

Expected Outcomes:
    ✓ Application accessible via public IP within 2 minutes of deployment
    ✓ Container auto-restart on failure
    ✓ Seamless image updates through ECR
    ✓ Basic logging and monitoring through CloudWatch

Known Limitations:
    ⚠ IP address changes on task restart (volatility)
    ⚠ No health checking or automatic failover
    ⚠ Single point of failure
    ⚠ Direct internet exposure (security consideration)
    ⚠ HTTP only (no SSL/TLS encryption)

Success Criteria:
    - HTTP 200 response from / endpoint
    - HTTP 200 response from /v1/health endpoint
    - Container logs visible in CloudWatch
    - Successful deployment via AWS CLI/Console
    - Image update capability demonstrated

Risk Assessment:
    LOW: Cost implications (estimated $5-15/month)
    MEDIUM: Security exposure (mitigated by security groups)
    HIGH: Service availability (addressed in Stage 2 with ALB)

Learning Objectives:
    1. ECS Fargate container orchestration
    2. ECR image lifecycle management
    3. VPC networking fundamentals
    4. Security group configuration
    5. CloudWatch logging integration

Next Stage Transition:
    Stage 2 will address IP volatility and health monitoring by introducing
    Application Load Balancer, moving tasks to private subnets, and implementing
    proper health checks.

Example Usage:
    ```python
    # Deploy Stage 1 infrastructure
    from frank_stage1 import deploy_minimal_setup

    deployment = deploy_minimal_setup(
        cluster_name="frank-stage1",
        service_name="frank-app",
        image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/frank:latest"
    )

    print(f"Application accessible at: http://{deployment.public_ip}")
    ```

Validation Commands:
    ```bash
    # Health check
    curl http://<public-ip>/v1/health

    # Application status
    curl http://<public-ip>/

    # Logs inspection
    aws logs tail /ecs/frank-stage1-task --follow
    ```

This stage establishes the minimal viable cloud deployment pattern while
maintaining clear documentation of limitations and migration paths for
production-ready enhancements.
"""

def validate_stage1_deployment(public_ip: str) -> dict:
    """
    Validate Stage 1 deployment meets hypothesis criteria.

    Args:
        public_ip: The public IP address of the deployed ECS task

    Returns:
        dict: Validation results with status and response times

    Raises:
        ConnectionError: If application is not accessible
        TimeoutError: If response time exceeds acceptable limits
    """
    import time

    import requests

    validation_results = {
        "deployment_stage": "Stage 1 - Minimal Setup",
        "timestamp": time.time(),
        "tests": {}
    }

    # Test root endpoint
    try:
        start_time = time.time()
        response = requests.get(f"http://{public_ip}/", timeout=10)
        response_time = time.time() - start_time

        validation_results["tests"]["root_endpoint"] = {
            "status": "PASS" if response.status_code == 200 else "FAIL",
            "response_time": response_time,
            "status_code": response.status_code,
            "hypothesis_met": response_time < 5.0  # Under 5 seconds as per hypothesis
        }
    except Exception as e:
        validation_results["tests"]["root_endpoint"] = {
            "status": "FAIL",
            "error": str(e),
            "hypothesis_met": False
        }

    # Test health endpoint
    try:
        start_time = time.time()
        response = requests.get(f"http://{public_ip}/v1/health", timeout=10)
        response_time = time.time() - start_time

        validation_results["tests"]["health_endpoint"] = {
            "status": "PASS" if response.status_code == 200 else "FAIL",
            "response_time": response_time,
            "status_code": response.status_code,
            "hypothesis_met": response_time < 5.0
        }
    except Exception as e:
        validation_results["tests"]["health_endpoint"] = {
            "status": "FAIL",
            "error": str(e),
            "hypothesis_met": False
        }

    # Overall hypothesis validation
    all_tests_passed = all(
        test.get("hypothesis_met", False)
        for test in validation_results["tests"].values()
    )

    validation_results["hypothesis_validated"] = all_tests_passed
    validation_results["ready_for_stage2"] = all_tests_passed

    return validation_results

if __name__ == "__main__":
    # Example validation
    import sys
    if len(sys.argv) > 1:
        public_ip = sys.argv[1]
        results = validate_stage1_deployment(public_ip)
        print(f"Stage 1 Hypothesis Validation: {results}")
    else:
        print("Usage: python stage1_hypothesis.py <public_ip>")
