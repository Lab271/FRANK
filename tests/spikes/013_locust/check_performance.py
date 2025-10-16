#!/usr/bin/env python3
"""
FRANK Platform - Performance Validation Script
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

Analyzes Locust test results and validates against performance targets.
Used in CI/CD pipelines to fail builds if performance degrades.

Usage:
    python check_performance.py --stats load-test-results_stats.csv

    python check_performance.py \
        --stats load-test-results_stats.csv \
        --max-response-time 500 \
        --max-failure-rate 0.1 \
        --min-rps 100

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import argparse
import csv
import sys
from typing import Dict, List, Tuple


class PerformanceChecker:
    """Validates load test results against performance targets"""

    def __init__(
        self,
        max_response_time: float = 500.0,
        max_failure_rate: float = 0.1,
        min_rps: float = 50.0,
        max_p95_response_time: float = 1000.0,
    ):
        """
        Initialize performance checker with thresholds.

        Args:
            max_response_time: Maximum average response time in ms
            max_failure_rate: Maximum failure rate as percentage
            min_rps: Minimum requests per second
            max_p95_response_time: Maximum 95th percentile response time in ms
        """
        self.max_response_time = max_response_time
        self.max_failure_rate = max_failure_rate
        self.min_rps = min_rps
        self.max_p95_response_time = max_p95_response_time

        self.results = []
        self.failures = []

    def load_stats(self, stats_file: str) -> List[Dict]:
        """
        Load statistics from Locust CSV output.

        Args:
            stats_file: Path to *_stats.csv file

        Returns:
            List of stat dictionaries
        """
        stats = []
        with open(stats_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip aggregated rows
                if row['Name'] in ['Aggregated', 'Total']:
                    continue
                stats.append(row)
        return stats

    def check_response_times(self, stats: List[Dict]) -> bool:
        """
        Check if response times are within acceptable limits.

        Args:
            stats: List of stat dictionaries

        Returns:
            True if all checks pass, False otherwise
        """
        all_passed = True

        print("\n" + "=" * 80)
        print("RESPONSE TIME CHECKS")
        print("=" * 80)

        for stat in stats:
            name = stat['Name']
            avg_response = float(stat['Average Response Time'])
            p95_response = float(stat.get('95%', 0))

            # Check average response time
            avg_passed = avg_response <= self.max_response_time
            p95_passed = p95_response <= self.max_p95_response_time

            status_avg = "✓ PASS" if avg_passed else "✗ FAIL"
            status_p95 = "✓ PASS" if p95_passed else "✗ FAIL"

            print(f"\n{name}")
            print(f"  Average: {avg_response:.2f}ms (limit: {self.max_response_time}ms) [{status_avg}]")
            print(f"  95th percentile: {p95_response:.2f}ms (limit: {self.max_p95_response_time}ms) [{status_p95}]")

            if not avg_passed:
                self.failures.append(f"{name}: Average response time {avg_response:.2f}ms exceeds limit {self.max_response_time}ms")
                all_passed = False

            if not p95_passed:
                self.failures.append(f"{name}: 95th percentile {p95_response:.2f}ms exceeds limit {self.max_p95_response_time}ms")
                all_passed = False

        return all_passed

    def check_failure_rates(self, stats: List[Dict]) -> bool:
        """
        Check if failure rates are within acceptable limits.

        Args:
            stats: List of stat dictionaries

        Returns:
            True if all checks pass, False otherwise
        """
        all_passed = True

        print("\n" + "=" * 80)
        print("FAILURE RATE CHECKS")
        print("=" * 80)

        for stat in stats:
            name = stat['Name']
            total_requests = int(stat['Request Count'])
            failures = int(stat['Failure Count'])

            if total_requests == 0:
                continue

            failure_rate = (failures / total_requests) * 100

            passed = failure_rate <= self.max_failure_rate
            status = "✓ PASS" if passed else "✗ FAIL"

            print(f"\n{name}")
            print(f"  Total Requests: {total_requests}")
            print(f"  Failures: {failures}")
            print(f"  Failure Rate: {failure_rate:.2f}% (limit: {self.max_failure_rate}%) [{status}]")

            if not passed:
                self.failures.append(f"{name}: Failure rate {failure_rate:.2f}% exceeds limit {self.max_failure_rate}%")
                all_passed = False

        return all_passed

    def check_throughput(self, stats: List[Dict]) -> bool:
        """
        Check if throughput meets minimum requirements.

        Args:
            stats: List of stat dictionaries

        Returns:
            True if check passes, False otherwise
        """
        print("\n" + "=" * 80)
        print("THROUGHPUT CHECKS")
        print("=" * 80)

        total_rps = 0
        for stat in stats:
            rps = float(stat.get('Requests/s', 0))
            total_rps += rps

            name = stat['Name']
            print(f"\n{name}")
            print(f"  RPS: {rps:.2f}")

        passed = total_rps >= self.min_rps
        status = "✓ PASS" if passed else "✗ FAIL"

        print(f"\nTotal RPS: {total_rps:.2f} (minimum: {self.min_rps}) [{status}]")

        if not passed:
            self.failures.append(f"Total RPS {total_rps:.2f} is below minimum {self.min_rps}")
            return False

        return True

    def print_summary(self) -> bool:
        """
        Print summary of all checks.

        Returns:
            True if all checks passed, False otherwise
        """
        print("\n" + "=" * 80)
        print("PERFORMANCE TEST SUMMARY")
        print("=" * 80)

        if not self.failures:
            print("\n✓ ALL CHECKS PASSED")
            print("\nPerformance meets all targets!")
            return True
        else:
            print("\n✗ PERFORMANCE CHECKS FAILED")
            print(f"\nFound {len(self.failures)} issue(s):")
            for i, failure in enumerate(self.failures, 1):
                print(f"{i}. {failure}")
            return False

    def check_all(self, stats_file: str) -> bool:
        """
        Run all performance checks.

        Args:
            stats_file: Path to Locust stats CSV file

        Returns:
            True if all checks pass, False otherwise
        """
        print("=" * 80)
        print("FRANK PERFORMANCE VALIDATION")
        print("=" * 80)
        print(f"\nAnalyzing: {stats_file}")
        print(f"\nThresholds:")
        print(f"  Max Average Response Time: {self.max_response_time}ms")
        print(f"  Max 95th Percentile Response Time: {self.max_p95_response_time}ms")
        print(f"  Max Failure Rate: {self.max_failure_rate}%")
        print(f"  Min Throughput: {self.min_rps} RPS")

        # Load stats
        try:
            stats = self.load_stats(stats_file)
        except FileNotFoundError:
            print(f"\n✗ ERROR: Stats file not found: {stats_file}")
            return False
        except Exception as e:
            print(f"\n✗ ERROR: Failed to load stats file: {e}")
            return False

        if not stats:
            print("\n✗ ERROR: No statistics found in file")
            return False

        # Run checks
        response_time_ok = self.check_response_times(stats)
        failure_rate_ok = self.check_failure_rates(stats)
        throughput_ok = self.check_throughput(stats)

        # Print summary
        all_passed = response_time_ok and failure_rate_ok and throughput_ok
        return self.print_summary()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Validate load test results against performance targets"
    )

    parser.add_argument(
        "--stats",
        required=True,
        help="Path to Locust stats CSV file (*_stats.csv)"
    )

    parser.add_argument(
        "--max-response-time",
        type=float,
        default=500.0,
        help="Maximum average response time in ms (default: 500)"
    )

    parser.add_argument(
        "--max-p95-response-time",
        type=float,
        default=1000.0,
        help="Maximum 95th percentile response time in ms (default: 1000)"
    )

    parser.add_argument(
        "--max-failure-rate",
        type=float,
        default=0.1,
        help="Maximum failure rate as percentage (default: 0.1)"
    )

    parser.add_argument(
        "--min-rps",
        type=float,
        default=50.0,
        help="Minimum requests per second (default: 50)"
    )

    args = parser.parse_args()

    # Create checker and run validation
    checker = PerformanceChecker(
        max_response_time=args.max_response_time,
        max_failure_rate=args.max_failure_rate,
        min_rps=args.min_rps,
        max_p95_response_time=args.max_p95_response_time,
    )

    all_passed = checker.check_all(args.stats)

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
