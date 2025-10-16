#!/usr/bin/env python3
"""
FRANK Platform - Performance Test Runner
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

Convenience script to run comprehensive performance tests with proper reporting.
Wraps Locust execution and validates results automatically.

Usage:
    # Quick test
    python run_performance_test.py --quick

    # Full test
    python run_performance_test.py --full

    # Custom test
    python run_performance_test.py \
        --users 100 \
        --spawn-rate 10 \
        --duration 5m \
        --host http://localhost:8080

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import argparse
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path


class PerformanceTestRunner:
    """Orchestrates performance testing with Locust"""

    def __init__(self, host: str, api_key: str = "dev-key-12345"):
        self.host = host
        self.api_key = api_key
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results_dir = Path("performance-results")
        self.results_dir.mkdir(exist_ok=True)

    def run_locust(
        self,
        users: int,
        spawn_rate: int,
        duration: str,
        test_name: str = "performance",
    ) -> bool:
        """
        Run Locust load test.

        Args:
            users: Number of concurrent users
            spawn_rate: User spawn rate per second
            duration: Test duration (e.g., '5m', '1h')
            test_name: Name for this test run

        Returns:
            True if test completed successfully
        """
        output_base = self.results_dir / f"{test_name}_{self.timestamp}"

        cmd = [
            "locust",
            "-f", "locustfile.py",
            "--host", self.host,
            "--users", str(users),
            "--spawn-rate", str(spawn_rate),
            "--run-time", duration,
            "--headless",
            "--html", f"{output_base}.html",
            "--csv", str(output_base),
            "--api-key", self.api_key,
        ]

        print("=" * 80)
        print(f"RUNNING PERFORMANCE TEST: {test_name}")
        print("=" * 80)
        print(f"\nConfiguration:")
        print(f"  Host: {self.host}")
        print(f"  Users: {users}")
        print(f"  Spawn Rate: {spawn_rate}/sec")
        print(f"  Duration: {duration}")
        print(f"\nCommand: {' '.join(cmd)}")
        print("\n" + "=" * 80)

        try:
            result = subprocess.run(cmd, check=True)
            print("\n" + "=" * 80)
            print("LOCUST TEST COMPLETED")
            print("=" * 80)
            return True
        except subprocess.CalledProcessError as e:
            print("\n" + "=" * 80)
            print("LOCUST TEST FAILED")
            print("=" * 80)
            print(f"Error: {e}")
            return False
        except FileNotFoundError:
            print("\n✗ ERROR: Locust not found. Install with: pip install locust")
            return False

    def validate_results(self, test_name: str, **thresholds) -> bool:
        """
        Validate test results against performance targets.

        Args:
            test_name: Name of test run
            **thresholds: Performance thresholds to check

        Returns:
            True if validation passed
        """
        stats_file = self.results_dir / f"{test_name}_{self.timestamp}_stats.csv"

        if not stats_file.exists():
            print(f"\n✗ ERROR: Stats file not found: {stats_file}")
            return False

        cmd = [
            "python",
            "check_performance.py",
            "--stats", str(stats_file),
        ]

        # Add threshold arguments
        if "max_response_time" in thresholds:
            cmd.extend(["--max-response-time", str(thresholds["max_response_time"])])
        if "max_p95_response_time" in thresholds:
            cmd.extend(["--max-p95-response-time", str(thresholds["max_p95_response_time"])])
        if "max_failure_rate" in thresholds:
            cmd.extend(["--max-failure-rate", str(thresholds["max_failure_rate"])])
        if "min_rps" in thresholds:
            cmd.extend(["--min-rps", str(thresholds["min_rps"])])

        try:
            result = subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def print_report_location(self, test_name: str):
        """Print location of generated reports"""
        output_base = self.results_dir / f"{test_name}_{self.timestamp}"

        print("\n" + "=" * 80)
        print("GENERATED REPORTS")
        print("=" * 80)
        print(f"\nHTML Report: {output_base}.html")
        print(f"CSV Stats: {output_base}_stats.csv")
        print(f"CSV History: {output_base}_stats_history.csv")
        print(f"CSV Failures: {output_base}_failures.csv")
        print("\n" + "=" * 80)

    def run_quick_test(self) -> bool:
        """Run quick validation test (2 minutes, 10 users)"""
        success = self.run_locust(
            users=10,
            spawn_rate=2,
            duration="2m",
            test_name="quick",
        )

        if not success:
            return False

        self.print_report_location("quick")

        return self.validate_results(
            "quick",
            max_response_time=200,
            max_p95_response_time=500,
            max_failure_rate=0.1,
            min_rps=10,
        )

    def run_standard_test(self) -> bool:
        """Run standard performance test (5 minutes, 50 users)"""
        success = self.run_locust(
            users=50,
            spawn_rate=5,
            duration="5m",
            test_name="standard",
        )

        if not success:
            return False

        self.print_report_location("standard")

        return self.validate_results(
            "standard",
            max_response_time=500,
            max_p95_response_time=1000,
            max_failure_rate=0.1,
            min_rps=50,
        )

    def run_stress_test(self) -> bool:
        """Run stress test (10 minutes, 200 users)"""
        success = self.run_locust(
            users=200,
            spawn_rate=20,
            duration="10m",
            test_name="stress",
        )

        if not success:
            return False

        self.print_report_location("stress")

        return self.validate_results(
            "stress",
            max_response_time=1000,
            max_p95_response_time=2000,
            max_failure_rate=1.0,
            min_rps=100,
        )

    def run_full_suite(self) -> bool:
        """Run complete performance test suite"""
        print("\n" + "=" * 80)
        print("RUNNING FULL PERFORMANCE TEST SUITE")
        print("=" * 80)

        all_passed = True

        # Quick test
        print("\n\n1/3: Quick Validation Test")
        if not self.run_quick_test():
            print("\n✗ Quick test FAILED")
            all_passed = False
        else:
            print("\n✓ Quick test PASSED")

        # Standard test
        print("\n\n2/3: Standard Performance Test")
        if not self.run_standard_test():
            print("\n✗ Standard test FAILED")
            all_passed = False
        else:
            print("\n✓ Standard test PASSED")

        # Stress test
        print("\n\n3/3: Stress Test")
        if not self.run_stress_test():
            print("\n✗ Stress test FAILED")
            all_passed = False
        else:
            print("\n✓ Stress test PASSED")

        # Final summary
        print("\n" + "=" * 80)
        print("FULL SUITE SUMMARY")
        print("=" * 80)

        if all_passed:
            print("\n✓ ALL TESTS PASSED")
            print("\nSystem meets all performance requirements!")
        else:
            print("\n✗ SOME TESTS FAILED")
            print("\nReview individual test reports for details.")

        return all_passed


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run FRANK performance tests with Locust"
    )

    # Test presets
    preset_group = parser.add_mutually_exclusive_group()
    preset_group.add_argument(
        "--quick",
        action="store_true",
        help="Run quick validation test (2min, 10 users)"
    )
    preset_group.add_argument(
        "--standard",
        action="store_true",
        help="Run standard performance test (5min, 50 users)"
    )
    preset_group.add_argument(
        "--stress",
        action="store_true",
        help="Run stress test (10min, 200 users)"
    )
    preset_group.add_argument(
        "--full",
        action="store_true",
        help="Run full test suite (all presets)"
    )

    # Custom test parameters
    parser.add_argument(
        "--users",
        type=int,
        help="Number of concurrent users"
    )
    parser.add_argument(
        "--spawn-rate",
        type=int,
        help="User spawn rate per second"
    )
    parser.add_argument(
        "--duration",
        type=str,
        help="Test duration (e.g., '5m', '1h')"
    )

    # Configuration
    parser.add_argument(
        "--host",
        default="http://localhost:8080",
        help="Target host URL (default: http://localhost:8080)"
    )
    parser.add_argument(
        "--api-key",
        default="dev-key-12345",
        help="API key for authentication"
    )

    args = parser.parse_args()

    # Create runner
    runner = PerformanceTestRunner(host=args.host, api_key=args.api_key)

    # Run appropriate test
    if args.quick:
        success = runner.run_quick_test()
    elif args.standard:
        success = runner.run_standard_test()
    elif args.stress:
        success = runner.run_stress_test()
    elif args.full:
        success = runner.run_full_suite()
    elif args.users and args.spawn_rate and args.duration:
        # Custom test
        success = runner.run_locust(
            users=args.users,
            spawn_rate=args.spawn_rate,
            duration=args.duration,
            test_name="custom",
        )
        if success:
            runner.print_report_location("custom")
            success = runner.validate_results("custom")
    else:
        parser.print_help()
        print("\nError: Must specify a test preset (--quick, --standard, --stress, --full) ")
        print("       or custom parameters (--users, --spawn-rate, --duration)")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
