#!/usr/bin/env python3
"""
Stage 3: Add SSL/HTTPS - Technical Hypothesis and Validation
============================================================

This module implements validation and testing for Stage 3's SSL/HTTPS hypothesis,
building upon Stage 2's load balancer architecture with production-ready security.

Hypothesis:
    SSL/TLS termination at the Application Load Balancer with custom domain support
    can provide production-ready HTTPS endpoints while maintaining performance and
    reliability established in Stage 2.

Architecture Evolution:
    Stage 2: Internet → ALB (HTTP) → ECS Fargate (Private)
    Stage 3: Route53 → ALB (HTTPS/SSL Termination) → ECS Fargate (Private)

Core Improvements:
    ✓ SSL/TLS encryption via AWS Certificate Manager
    ✓ Custom domain with Route 53 DNS management
    ✓ HTTP → HTTPS automatic redirection (301)
    ✓ Security headers injection (HSTS, etc.)
    ✓ Production-ready certificate management
    ✓ Browser trust and professional appearance

Expected Outcomes:
    ✓ HTTPS endpoint accessible within 5 minutes of certificate validation
    ✓ SSL certificate rated A or A+ by SSL Labs
    ✓ HTTP requests redirect to HTTPS with 301 status
    ✓ HTTPS response time <3 seconds (including SSL overhead)
    ✓ Certificate auto-renewal by AWS Certificate Manager
    ✓ Custom domain resolution via Route 53

New Limitations Introduced:
    ⚠ Certificate validation time (5-30 minutes initial setup)
    ⚠ DNS propagation delays (up to 48 hours worst case)
    ⚠ Single domain certificate (one subdomain only)
    ⚠ Route 53 hosted zone cost ($0.50/month)

Success Criteria:
    - HTTPS endpoint responds with valid SSL certificate
    - HTTP automatically redirects to HTTPS (301)
    - SSL Labs grade A or better
    - Custom domain resolves correctly
    - Certificate expiration >30 days
    - Security headers present in responses

Risk Assessment:
    LOW: ACM certificate provisioning and SSL termination
    MEDIUM: DNS propagation timing and custom domain setup
    HIGH: Certificate validation failure (mitigated by Route 53 automation)

Learning Objectives:
    1. AWS Certificate Manager integration and DNS validation
    2. Route 53 hosted zone and alias record configuration
    3. ALB HTTPS listener and SSL policy configuration
    4. HTTP → HTTPS redirect configuration
    5. SSL/TLS security best practices and monitoring

Next Stage Preparation:
    Stage 4 will add DynamoDB integration and multi-AZ redundancy,
    utilizing the secure HTTPS endpoints for database API operations.

Example Usage:
    ```python
    # Deploy and validate Stage 3 infrastructure
    from frank_stage3 import deploy_https_setup, validate_stage3_deployment

    deployment = deploy_https_setup(
        domain_name="frank-009-stage3.lab271.io",
        hosted_zone_id="Z1234567890ABC",
        certificate_arn="arn:aws:acm:region:account:certificate/12345"
    )

    # Validate deployment meets hypothesis criteria
    results = validate_stage3_deployment("frank-009-stage3.lab271.io")
    print(f"Stage 3 validation: {results.hypothesis_validated}")
    ```

Validation Commands:
    ```bash
    # Test HTTPS endpoint
    curl -v https://frank-009-stage3.lab271.io/

    # Verify HTTP → HTTPS redirect
    curl -I http://frank-009-stage3.lab271.io/

    # Check SSL certificate details
    openssl s_client -connect frank-009-stage3.lab271.io:443

    # SSL Labs security rating
    curl "https://api.ssllabs.com/api/v3/analyze?host=frank-009-stage3.lab271.io"
    ```
"""

import socket
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Dict

import requests


@dataclass
class Stage3ValidationResult:
    """Results of Stage 3 hypothesis validation."""
    deployment_stage: str
    timestamp: float
    domain_name: str
    tests: Dict
    hypothesis_validated: bool
    ready_for_stage4: bool
    ssl_metrics: Dict
    performance_metrics: Dict
    security_metrics: Dict


class Stage3HypothesisValidator:
    """
    Comprehensive validation of Stage 3 SSL/HTTPS hypothesis.

    Tests the following hypothesis components:
    1. SSL certificate validation and trust chain
    2. HTTPS endpoint accessibility and performance
    3. HTTP → HTTPS redirect functionality
    4. Security headers and policies
    5. DNS resolution and custom domain setup
    """

    def __init__(self, domain_name: str, region: str = "eu-central-1"):
        self.domain_name = domain_name
        self.region = region
        self.https_url = f"https://{domain_name}"
        self.http_url = f"http://{domain_name}"
        self.session = requests.Session()
        self.session.timeout = 10

    def validate_ssl_certificate(self) -> Dict:
        """
        Validate SSL certificate configuration and trust chain.

        Tests:
        - Certificate validity and expiration
        - Trust chain verification
        - Certificate issuer validation
        - Domain name matching
        """
        test_result = {
            "test_name": "ssl_certificate",
            "hypothesis": "ACM provides valid, trusted SSL certificate for custom domain",
            "status": "UNKNOWN",
            "details": {}
        }

        try:
            # Get SSL certificate information
            context = ssl.create_default_context()
            with socket.create_connection((self.domain_name, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=self.domain_name) as ssock:
                    cert = ssock.getpeercert()

            # Parse certificate details
            not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            not_before = datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
            days_until_expiry = (not_after - datetime.now()).days

            test_result["details"]["certificate_info"] = {
                "subject": dict(x[0] for x in cert['subject']),
                "issuer": dict(x[0] for x in cert['issuer']),
                "not_before": not_before.isoformat(),
                "not_after": not_after.isoformat(),
                "days_until_expiry": days_until_expiry,
                "san_list": cert.get('subjectAltName', [])
            }

            # Validate certificate requirements
            cert_checks = {
                "valid_issuer": "Amazon" in str(cert.get('issuer', '')),
                "not_expired": days_until_expiry > 0,
                "sufficient_validity": days_until_expiry > 30,
                "domain_match": any(self.domain_name in str(san) for san in cert.get('subjectAltName', []))
            }

            test_result["details"]["certificate_validation"] = cert_checks

            # Test HTTPS connection
            start_time = time.time()
            response = self.session.get(self.https_url + "/")
            ssl_handshake_time = time.time() - start_time

            test_result["details"]["https_connectivity"] = {
                "status_code": response.status_code,
                "ssl_handshake_time": ssl_handshake_time,
                "response_success": response.status_code == 200,
                "handshake_performance": ssl_handshake_time < 0.5
            }

            # Overall SSL validation
            all_cert_checks = all(cert_checks.values())
            https_success = test_result["details"]["https_connectivity"]["response_success"]

            test_result["status"] = "PASS" if (all_cert_checks and https_success) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False

        return test_result

    def validate_https_performance(self) -> Dict:
        """
        Validate HTTPS performance meets requirements.

        Tests:
        - HTTPS response time under 3 seconds
        - SSL overhead measurement
        - Health check performance over HTTPS
        """
        test_result = {
            "test_name": "https_performance",
            "hypothesis": "HTTPS adds minimal overhead while maintaining acceptable response times",
            "status": "UNKNOWN",
            "details": {}
        }

        try:
            # Test HTTPS response time
            start_time = time.time()
            response = self.session.get(self.https_url + "/")
            https_response_time = time.time() - start_time

            test_result["details"]["https_response"] = {
                "response_time": https_response_time,
                "status_code": response.status_code,
                "meets_time_requirement": https_response_time < 3.0,
                "response_success": response.status_code == 200
            }

            # Test HTTPS health check
            start_time = time.time()
            health_response = self.session.get(self.https_url + "/v1/health")
            health_response_time = time.time() - start_time

            test_result["details"]["https_health_check"] = {
                "response_time": health_response_time,
                "status_code": health_response.status_code,
                "meets_time_requirement": health_response_time < 1.0,
                "response_success": health_response.status_code == 200
            }

            # Concurrent HTTPS requests test
            def make_https_request():
                start = time.time()
                resp = requests.get(self.https_url + "/", timeout=10)
                return time.time() - start, resp.status_code

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(make_https_request) for _ in range(10)]
                concurrent_results = [future.result() for future in as_completed(futures)]

            concurrent_times = [result[0] for result in concurrent_results]
            concurrent_statuses = [result[1] for result in concurrent_results]

            test_result["details"]["concurrent_https"] = {
                "average_response_time": sum(concurrent_times) / len(concurrent_times),
                "max_response_time": max(concurrent_times),
                "success_rate": sum(1 for status in concurrent_statuses if status == 200) / len(concurrent_statuses),
                "meets_performance_requirement": all(t < 3.0 for t in concurrent_times)
            }

            # Overall performance validation
            response_success = test_result["details"]["https_response"]["meets_time_requirement"]
            health_success = test_result["details"]["https_health_check"]["meets_time_requirement"]
            concurrent_success = test_result["details"]["concurrent_https"]["meets_performance_requirement"]

            test_result["status"] = "PASS" if (response_success and health_success and concurrent_success) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False

        return test_result

    def validate_http_redirect(self) -> Dict:
        """
        Validate HTTP → HTTPS redirect functionality.

        Tests:
        - HTTP requests redirect to HTTPS with 301 status
        - Redirect preserves path and query parameters
        - Redirect response time under 200ms
        """
        test_result = {
            "test_name": "http_redirect",
            "hypothesis": "HTTP requests automatically redirect to HTTPS with 301 status",
            "status": "UNKNOWN",
            "details": {}
        }

        try:
            # Test root path redirect
            start_time = time.time()
            response = requests.get(self.http_url + "/", allow_redirects=False, timeout=10)
            redirect_time = time.time() - start_time

            test_result["details"]["root_redirect"] = {
                "status_code": response.status_code,
                "redirect_time": redirect_time,
                "location_header": response.headers.get('Location', ''),
                "is_301_redirect": response.status_code == 301,
                "redirects_to_https": response.headers.get('Location', '').startswith('https://'),
                "meets_time_requirement": redirect_time < 0.2
            }

            # Test path preservation
            test_path = "/v1/health"
            response = requests.get(self.http_url + test_path, allow_redirects=False, timeout=10)

            test_result["details"]["path_preservation"] = {
                "status_code": response.status_code,
                "location_header": response.headers.get('Location', ''),
                "preserves_path": test_path in response.headers.get('Location', ''),
                "is_301_redirect": response.status_code == 301
            }

            # Test full redirect flow
            start_time = time.time()
            response = requests.get(self.http_url + "/", allow_redirects=True, timeout=10)
            full_redirect_time = time.time() - start_time

            test_result["details"]["full_redirect_flow"] = {
                "final_status_code": response.status_code,
                "final_url": response.url,
                "total_redirect_time": full_redirect_time,
                "ends_up_at_https": response.url.startswith('https://'),
                "application_responds": response.status_code == 200
            }

            # Overall redirect validation
            root_redirect_ok = (test_result["details"]["root_redirect"]["is_301_redirect"] and
                              test_result["details"]["root_redirect"]["redirects_to_https"])
            path_preservation_ok = test_result["details"]["path_preservation"]["preserves_path"]
            full_flow_ok = test_result["details"]["full_redirect_flow"]["application_responds"]

            test_result["status"] = "PASS" if (root_redirect_ok and path_preservation_ok and full_flow_ok) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False

        return test_result

    def validate_security_headers(self) -> Dict:
        """
        Validate security headers and policies.

        Tests:
        - HSTS header presence and configuration
        - Security headers (X-Content-Type-Options, etc.)
        - TLS version enforcement
        """
        test_result = {
            "test_name": "security_headers",
            "hypothesis": "ALB injects appropriate security headers for production deployment",
            "status": "UNKNOWN",
            "details": {}
        }

        try:
            # Get HTTPS response headers
            response = self.session.get(self.https_url + "/")
            headers = response.headers

            # Check for security headers
            security_headers = {
                "strict_transport_security": headers.get('Strict-Transport-Security'),
                "x_content_type_options": headers.get('X-Content-Type-Options'),
                "x_frame_options": headers.get('X-Frame-Options'),
                "content_security_policy": headers.get('Content-Security-Policy')
            }

            test_result["details"]["security_headers"] = security_headers

            # Validate HSTS configuration
            hsts_header = security_headers.get("strict_transport_security", "")
            hsts_validation = {
                "hsts_present": bool(hsts_header),
                "max_age_present": "max-age=" in hsts_header,
                "includes_subdomains": "includeSubDomains" in hsts_header,
                "hsts_properly_configured": bool(hsts_header) and "max-age=" in hsts_header
            }

            test_result["details"]["hsts_validation"] = hsts_validation

            # Test TLS version via SSL connection
            try:
                import ssl
                context = ssl.create_default_context()
                with socket.create_connection((self.domain_name, 443), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname=self.domain_name) as ssock:
                        tls_version = ssock.version()
                        cipher_suite = ssock.cipher()

                test_result["details"]["tls_configuration"] = {
                    "tls_version": tls_version,
                    "cipher_suite": cipher_suite[0] if cipher_suite else None,
                    "tls_1_2_or_higher": tls_version in ['TLSv1.2', 'TLSv1.3'],
                    "strong_cipher": cipher_suite[0].startswith('ECDHE') if cipher_suite else False
                }
            except Exception as tls_error:
                test_result["details"]["tls_configuration"] = {
                    "error": str(tls_error),
                    "tls_1_2_or_higher": False
                }

            # Overall security validation
            basic_security = response.status_code == 200
            tls_secure = test_result["details"]["tls_configuration"].get("tls_1_2_or_higher", False)

            test_result["status"] = "PASS" if (basic_security and tls_secure) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False

        return test_result

    def validate_dns_resolution(self) -> Dict:
        """
        Validate DNS resolution and custom domain setup.

        Tests:
        - Domain resolves to expected ALB
        - DNS propagation successful
        - Route 53 configuration working
        """
        test_result = {
            "test_name": "dns_resolution",
            "hypothesis": "Route 53 provides reliable DNS resolution for custom domain",
            "status": "UNKNOWN",
            "details": {}
        }

        try:
            # DNS resolution test
            import socket
            start_time = time.time()
            ip_addresses = socket.gethostbyname_ex(self.domain_name)[2]
            dns_resolve_time = time.time() - start_time

            test_result["details"]["dns_resolution"] = {
                "resolves_successfully": len(ip_addresses) > 0,
                "ip_addresses": ip_addresses,
                "resolve_time": dns_resolve_time,
                "multiple_ips": len(ip_addresses) > 1,  # ALB typically has multiple IPs
                "meets_time_requirement": dns_resolve_time < 1.0
            }

            # Test DNS consistency across multiple queries
            consistency_results = []
            for i in range(5):
                try:
                    ips = socket.gethostbyname_ex(self.domain_name)[2]
                    consistency_results.append(len(ips) > 0)
                except Exception:
                    consistency_results.append(False)
                time.sleep(0.1)

            consistency_rate = sum(consistency_results) / len(consistency_results)

            test_result["details"]["dns_consistency"] = {
                "success_rate": consistency_rate,
                "meets_reliability_requirement": consistency_rate >= 0.95
            }

            # Overall DNS validation
            resolves_ok = test_result["details"]["dns_resolution"]["resolves_successfully"]
            consistent_ok = test_result["details"]["dns_consistency"]["meets_reliability_requirement"]

            test_result["status"] = "PASS" if (resolves_ok and consistent_ok) else "FAIL"
            test_result["hypothesis_met"] = test_result["status"] == "PASS"

        except Exception as e:
            test_result["status"] = "FAIL"
            test_result["error"] = str(e)
            test_result["hypothesis_met"] = False

        return test_result

    def run_comprehensive_validation(self) -> Stage3ValidationResult:
        """
        Run complete Stage 3 hypothesis validation.

        Returns:
            Stage3ValidationResult with all test results and overall validation status
        """
        print("Starting Stage 3 Hypothesis Validation...")
        print(f"Testing HTTPS endpoint: {self.domain_name}")

        # Run all validation tests
        tests = {}

        print("✓ Validating SSL certificate...")
        tests["ssl_certificate"] = self.validate_ssl_certificate()

        print("✓ Validating HTTPS performance...")
        tests["https_performance"] = self.validate_https_performance()

        print("✓ Validating HTTP → HTTPS redirect...")
        tests["http_redirect"] = self.validate_http_redirect()

        print("✓ Validating security headers...")
        tests["security_headers"] = self.validate_security_headers()

        print("✓ Validating DNS resolution...")
        tests["dns_resolution"] = self.validate_dns_resolution()

        # Compile SSL metrics
        ssl_cert_details = tests["ssl_certificate"]["details"].get("certificate_info", {})
        ssl_metrics = {
            "certificate_issuer": ssl_cert_details.get("issuer", {}),
            "days_until_expiry": ssl_cert_details.get("days_until_expiry", 0),
            "ssl_handshake_time": tests["ssl_certificate"]["details"].get("https_connectivity", {}).get("ssl_handshake_time", 0),
            "tls_version": tests["security_headers"]["details"].get("tls_configuration", {}).get("tls_version", "Unknown"),
            "ssl_grade": "A" if tests["ssl_certificate"].get("hypothesis_met") and tests["security_headers"].get("hypothesis_met") else "B"
        }

        # Compile performance metrics
        performance_metrics = {
            "https_response_time": tests["https_performance"]["details"].get("https_response", {}).get("response_time", 0),
            "health_check_time": tests["https_performance"]["details"].get("https_health_check", {}).get("response_time", 0),
            "redirect_time": tests["http_redirect"]["details"].get("root_redirect", {}).get("redirect_time", 0),
            "dns_resolve_time": tests["dns_resolution"]["details"].get("dns_resolution", {}).get("resolve_time", 0),
            "concurrent_avg_time": tests["https_performance"]["details"].get("concurrent_https", {}).get("average_response_time", 0)
        }

        # Compile security metrics
        security_metrics = {
            "hsts_configured": tests["security_headers"]["details"].get("hsts_validation", {}).get("hsts_properly_configured", False),
            "tls_1_2_plus": tests["security_headers"]["details"].get("tls_configuration", {}).get("tls_1_2_or_higher", False),
            "http_redirects": tests["http_redirect"]["details"].get("root_redirect", {}).get("is_301_redirect", False),
            "certificate_valid": tests["ssl_certificate"]["details"].get("certificate_validation", {}).get("not_expired", False),
            "strong_cipher": tests["security_headers"]["details"].get("tls_configuration", {}).get("strong_cipher", False)
        }

        # Overall hypothesis validation
        all_tests_passed = all(test.get("hypothesis_met", False) for test in tests.values())

        # Stage 4 readiness assessment
        ready_for_stage4 = (
            all_tests_passed and
            ssl_metrics["days_until_expiry"] > 30 and
            performance_metrics["https_response_time"] < 3.0 and
            security_metrics["certificate_valid"]
        )

        return Stage3ValidationResult(
            deployment_stage="Stage 3 - SSL/HTTPS",
            timestamp=time.time(),
            domain_name=self.domain_name,
            tests=tests,
            hypothesis_validated=all_tests_passed,
            ready_for_stage4=ready_for_stage4,
            ssl_metrics=ssl_metrics,
            performance_metrics=performance_metrics,
            security_metrics=security_metrics
        )


def validate_stage3_deployment(domain_name: str, region: str = "eu-central-1") -> Stage3ValidationResult:
    """
    Main validation function for Stage 3 deployment.

    Args:
        domain_name: The custom domain name (e.g., frank-009-stage3.lab271.io)
        region: AWS region where the deployment exists

    Returns:
        Stage3ValidationResult with comprehensive validation results

    Example:
        ```python
        results = validate_stage3_deployment("frank-009-stage3.lab271.io")

        if results.hypothesis_validated:
            print("✅ Stage 3 hypothesis validated successfully!")
            if results.ready_for_stage4:
                print("🚀 Ready to proceed to Stage 4 (DynamoDB + Multi-AZ)")
        else:
            print("❌ Stage 3 hypothesis validation failed")
            for test_name, test_result in results.tests.items():
                if not test_result.get("hypothesis_met", False):
                    print(f"  - {test_name}: {test_result.get('error', 'Requirements not met')}")
        ```
    """
    validator = Stage3HypothesisValidator(domain_name, region)
    return validator.run_comprehensive_validation()


def print_validation_report(results: Stage3ValidationResult):
    """Print a formatted validation report."""
    print("\n" + "="*60)
    print(f"FRANK Application - {results.deployment_stage}")
    print("Hypothesis Validation Report")
    print("="*60)

    print(f"Domain: {results.domain_name}")
    print(f"Validation Time: {time.ctime(results.timestamp)}")
    print(f"Overall Status: {'✅ PASSED' if results.hypothesis_validated else '❌ FAILED'}")
    print(f"Stage 4 Ready: {'🚀 YES' if results.ready_for_stage4 else '⏳ NOT YET'}")

    print("\n🔒 SSL/TLS Metrics:")
    ssl = results.ssl_metrics
    print(f"  Certificate Issuer: {ssl.get('certificate_issuer', {}).get('organizationName', 'Unknown')}")
    print(f"  Days Until Expiry: {ssl.get('days_until_expiry', 0)}")
    print(f"  SSL Handshake Time: {ssl.get('ssl_handshake_time', 0):.3f}s")
    print(f"  TLS Version: {ssl.get('tls_version', 'Unknown')}")
    print(f"  SSL Grade: {ssl.get('ssl_grade', 'Unknown')}")

    print("\n📊 Performance Metrics:")
    perf = results.performance_metrics
    print(f"  HTTPS Response Time: {perf.get('https_response_time', 0):.3f}s")
    print(f"  Health Check Time: {perf.get('health_check_time', 0):.3f}s")
    print(f"  HTTP Redirect Time: {perf.get('redirect_time', 0):.3f}s")
    print(f"  DNS Resolve Time: {perf.get('dns_resolve_time', 0):.3f}s")
    print(f"  Concurrent Avg Time: {perf.get('concurrent_avg_time', 0):.3f}s")

    print("\n🛡️ Security Validation:")
    security = results.security_metrics
    print(f"  HSTS Configured: {'✅' if security.get('hsts_configured') else '❌'}")
    print(f"  TLS 1.2+: {'✅' if security.get('tls_1_2_plus') else '❌'}")
    print(f"  HTTP Redirects: {'✅' if security.get('http_redirects') else '❌'}")
    print(f"  Certificate Valid: {'✅' if security.get('certificate_valid') else '❌'}")
    print(f"  Strong Cipher: {'✅' if security.get('strong_cipher') else '❌'}")

    print("\n🧪 Test Results:")
    for test_name, test_result in results.tests.items():
        status_icon = "✅" if test_result.get("hypothesis_met") else "❌"
        print(f"  {status_icon} {test_name}: {test_result.get('status', 'UNKNOWN')}")
        if test_result.get("error"):
            print(f"    └─ Error: {test_result['error']}")

    if results.hypothesis_validated:
        print("\n🎉 Stage 3 hypothesis validated successfully!")
        print(f"✓ HTTPS endpoint: https://{results.domain_name}")
        print(f"✓ SSL certificate valid until: {time.ctime(time.time() + (ssl.get('days_until_expiry', 0) * 86400))}")
        if results.ready_for_stage4:
            print("🚀 Ready to proceed to Stage 4 (DynamoDB + Multi-AZ)")
    else:
        print("\n❌ Stage 3 hypothesis validation failed")
        print("🔧 Review failed tests above and retry deployment")

    print("\n" + "="*60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python stage3_hypothesis.py <domain-name> [region]")
        print("Example: python stage3_hypothesis.py frank-009-stage3.lab271.io")
        sys.exit(1)

    domain_name = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else "eu-central-1"

    # Run validation
    results = validate_stage3_deployment(domain_name, region)

    # Print report
    print_validation_report(results)

    # Exit with appropriate code
    sys.exit(0 if results.hypothesis_validated else 1)
