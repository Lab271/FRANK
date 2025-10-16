#!/usr/bin/env python3
"""
FRANK Platform - API Test Script
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

Test script for the Stage 3 API endpoints.
Demonstrates creating submissions and querying data.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import requests
import json
from datetime import datetime
from typing import Dict, Any


class FRANKAPIClient:
    """Simple client for testing FRANK API"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def create_submission(self, submission_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new submission"""
        url = f"{self.base_url}/api/v1/submissions"
        response = requests.post(url, headers=self.headers, json=submission_data)
        response.raise_for_status()
        return response.json()

    def get_submission(self, submission_id: str) -> Dict[str, Any]:
        """Get a specific submission by ID"""
        url = f"{self.base_url}/api/v1/submissions/{submission_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def query_observables(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Query observables with filters"""
        url = f"{self.base_url}/api/v1/observables"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def search_observables(self, search_value: str) -> Dict[str, Any]:
        """Search observables by value"""
        url = f"{self.base_url}/api/v1/observables/search"
        response = requests.get(url, headers=self.headers, params={"value": search_value})
        response.raise_for_status()
        return response.json()

    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get platform statistics"""
        url = f"{self.base_url}/api/v1/statistics"
        response = requests.get(url, headers=self.headers, params={"days": days})
        response.raise_for_status()
        return response.json()

    def health_check(self) -> Dict[str, Any]:
        """Get health status"""
        url = f"{self.base_url}/v1/health"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()


def create_example_submission_1() -> Dict[str, Any]:
    """Create example submission with malicious IP addresses"""
    return {
        "submitter_access_level": "PARTNER",
        "submitter_sector": "financial",
        "submitter_region": "eu-west",
        "hit_target_sector": "healthcare",
        "hit_target_size": "large",
        "hit_target_region": "eu-central",
        "confidence": 85,
        "severity": "HIGH",
        "network_observables": [
            {
                "type": "ipv4",
                "value": "185.220.102.45",
                "role": "c2",
                "port": 443,
                "protocol": "https",
                "connection_count": 127,
            },
            {
                "type": "ipv4",
                "value": "203.0.113.42",
                "role": "exfiltration",
                "port": 8080,
                "protocol": "http",
                "connection_count": 45,
            },
            {
                "type": "domain",
                "value": "malicious-c2.example.com",
                "role": "c2",
            },
        ],
        "tlp_level": "AMBER",
        "processing_notes": "Detected via SIEM correlation rules. High confidence C2 communication.",
    }


def create_example_submission_2() -> Dict[str, Any]:
    """Create example submission with file hashes"""
    return {
        "submitter_access_level": "CONTRIBUTOR",
        "submitter_sector": "technology",
        "submitter_region": "eu-west",
        "hit_target_sector": "financial",
        "hit_target_size": "medium",
        "hit_target_region": "eu-west",
        "confidence": 95,
        "severity": "CRITICAL",
        "network_observables": [
            {
                "type": "ipv4",
                "value": "192.168.1.100",
                "role": "victim",
            },
        ],
        "file_observables": [
            {
                "type": "md5",
                "value": "5d41402abc4b2a76b9719d911017c592",
            },
            {
                "type": "sha256",
                "value": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
            },
        ],
        "tlp_level": "RED",
        "processing_notes": "Ransomware payload detected. Immediate action required.",
    }


def create_example_submission_3() -> Dict[str, Any]:
    """Create example submission with URLs and domains"""
    return {
        "submitter_access_level": "PARTNER",
        "submitter_sector": "government",
        "submitter_region": "eu-north",
        "hit_target_sector": "public_sector",
        "hit_target_size": "large",
        "hit_target_region": "eu-north",
        "confidence": 75,
        "severity": "MEDIUM",
        "network_observables": [
            {
                "type": "url",
                "value": "https://phishing-site.example.com/login",
                "role": "phishing",
            },
            {
                "type": "domain",
                "value": "phishing-site.example.com",
                "role": "phishing",
            },
            {
                "type": "ipv4",
                "value": "198.51.100.23",
                "role": "hosting",
                "port": 443,
            },
        ],
        "tlp_level": "GREEN",
        "processing_notes": "Phishing campaign targeting government employees. Multiple reports received.",
    }


def main():
    """Main test routine"""
    print("=" * 80)
    print("FRANK Platform API - Test Script")
    print("=" * 80)

    # Configuration
    BASE_URL = "http://localhost:8080"  # Change to your API endpoint
    API_KEY = "dev-key-12345"  # Change to your API key

    client = FRANKAPIClient(BASE_URL, API_KEY)

    # Test 1: Health Check
    print("\n1. Testing Health Check...")
    try:
        health = client.health_check()
        print(f"   ✓ Status: {health['status']}")
        print(f"   ✓ Version: {health['version']}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return

    # Test 2: Create Submissions
    print("\n2. Creating Example Submissions...")
    submissions = []

    for i, submission_data in enumerate(
        [
            create_example_submission_1(),
            create_example_submission_2(),
            create_example_submission_3(),
        ],
        1,
    ):
        try:
            result = client.create_submission(submission_data)
            submissions.append(result)
            print(f"   ✓ Submission {i} created: {result['submission_id']}")
        except Exception as e:
            print(f"   ✗ Submission {i} failed: {e}")

    # Test 3: Retrieve Submission
    if submissions:
        print("\n3. Retrieving First Submission...")
        try:
            submission_id = submissions[0]["submission_id"]
            submission = client.get_submission(submission_id)
            print(f"   ✓ Retrieved submission: {submission_id}")
            print(f"   ✓ Confidence: {submission.get('confidence', 'N/A')}")
            print(f"   ✓ TLP Level: {submission.get('tlp_level', 'N/A')}")
        except Exception as e:
            print(f"   ✗ Error: {e}")

    # Test 4: Query Observables
    print("\n4. Querying Observables...")
    try:
        results = client.query_observables({"observable_type": "ipv4", "limit": 10})
        print(f"   ✓ Found {results['total']} IPv4 observables")
        if results["observables"]:
            print(f"   ✓ First observable: {results['observables'][0].get('observable_value', 'N/A')}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 5: Search Observables
    print("\n5. Searching for Specific Observable...")
    try:
        results = client.search_observables("185.220")
        print(f"   ✓ Found {results['total']} matching observables")
        if results["observables"]:
            for obs in results["observables"][:3]:
                print(f"   ✓ Match: {obs.get('observable_value', 'N/A')}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 6: Get Statistics
    print("\n6. Getting Platform Statistics...")
    try:
        stats = client.get_statistics(days=30)
        print(f"   ✓ Total Submissions: {stats.get('total_submissions', 0)}")
        print(f"   ✓ Total Observables: {stats.get('total_observables', 0)}")
        print(f"   ✓ Total Organizations: {stats.get('total_organisations', 0)}")
        print(f"   ✓ Observable Types:")
        for obs_type, count in stats.get("observable_totals", {}).items():
            if count > 0:
                print(f"      - {obs_type}: {count}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    print("\n" + "=" * 80)
    print("Test Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
