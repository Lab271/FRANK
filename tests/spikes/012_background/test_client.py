#!/usr/bin/env python3
"""
FRANK Platform - Background Processing Test Client
Demonstrates how to submit threat intelligence and poll for enrichment results.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import time
import json
from frank.core.models import Submission, Submitter, Sighting, HitTarget, Observables, Observable
from frank.core.enum import AccessTier, ObservableType
from frank.util.requests import SubmissionRequest


def create_test_submission() -> SubmissionRequest:
    """Create a test submission with threat intelligence data"""

    # Create network observables
    network_observables = [
        Observable(
            observable_type=ObservableType.IPV4,
            value="185.220.102.45",
            role="c2_server",
            port=443,
            protocol="https"
        ),
        Observable(
            observable_type=ObservableType.DOMAIN,
            value="malicious-banking-phish.com",
            role="phishing_domain"
        ),
        Observable(
            observable_type=ObservableType.IPV4,
            value="203.0.113.42",
            role="data_exfiltration"
        )
    ]

    # Create observables container
    observables = Observables(network=network_observables)

    # Create sighting
    sighting = Sighting(
        observables=observables,
        confidence=75,
        observation_count=3
    )

    # Create submitter
    submitter = Submitter(
        access_level=AccessTier.PARTNER,
        sector="financial",
        region="nl_north_holland"
    )

    # Create hit target
    hit_target = HitTarget(
        sector="financial",
        organisation_size="large",
        region="nl_north_holland"
    )

    # Create submission
    submission = Submission(
        submitter=submitter,
        sighting=sighting,
        hit_target=hit_target,
        tlp_level="AMBER"
    )

    return SubmissionRequest(submission=submission)


def test_background_processing():
    """
    Test the background processing workflow.
    This function demonstrates the complete submission and polling cycle.
    """
    from fastapi.testclient import TestClient
    from background_processing_test import app

    print("=" * 80)
    print("FRANK Background Processing Test Client")
    print("=" * 80)

    # Create test client
    client = TestClient(app)
    headers = {"Authorization": "Bearer partner_test_token"}

    # Step 1: Create submission
    print("\n[1] Creating test submission...")
    submission_request = create_test_submission()
    submission_data = {"submission": submission_request.submission.model_dump(exclude_none=True, by_alias=True)}

    # Step 2: Submit to API
    print("[2] Submitting to API...")
    response = client.post(
        "/v1/submission",
        headers=headers,
        json=submission_data
    )

    if response.status_code != 200:
        print(f"ERROR: Submission failed with status {response.status_code}")
        print(response.json())
        return

    result = response.json()
    print(f"✓ Submission accepted!")
    print(f"  Submission ID: {result['submission_id']}")
    print(f"  Task ID: {result['task_id']}")
    print(f"  Status URL: {result['status_url']}")

    task_id = result["task_id"]

    # Step 3: Poll for completion
    print(f"\n[3] Polling for task completion...")
    print("-" * 80)

    max_polls = 15
    poll_count = 0

    while poll_count < max_polls:
        poll_count += 1
        time.sleep(1)

        status_response = client.get(
            f"/v1/task/{task_id}",
            headers=headers
        )

        if status_response.status_code != 200:
            print(f"ERROR: Status check failed with status {status_response.status_code}")
            break

        status = status_response.json()

        # Display progress
        progress_bar = "=" * (status['progress'] // 2) + ">" + " " * (50 - status['progress'] // 2)
        print(f"Poll {poll_count}: [{progress_bar}] {status['progress']}% - {status['status']}")

        # Display latest step
        if status['steps']:
            latest_step = status['steps'][-1]
            print(f"         Current: {latest_step['step']}")

        # Check completion
        if status['status'] == 'completed':
            print("\n✓ Task completed successfully!")
            print("\n[4] Enrichment Results:")
            print("-" * 80)

            results = status['enrichment_results']

            # Display SIGMA detections
            print("\nSIGMA Detections:")
            for detection in results.get('sigma_detections', []):
                print(f"  • {detection['rule_name']} (v{detection['rule_version']})")
                print(f"    Confidence: {detection['match_confidence']:.2%}")
                print(f"    Matched: {', '.join(detection['matched_observables'])}")

            # Display MITRE ATT&CK mapping
            print("\nMITRE ATT&CK Techniques:")
            for technique in results.get('mitre_attack', {}).get('techniques', []):
                print(f"  • {technique['id']}: {technique['name']}")
                print(f"    Tactic: {technique['tactic']}")
                print(f"    Confidence: {technique['confidence']:.2%}")

            # Display correlations
            correlations = results.get('correlations', {})
            print(f"\nHistorical Correlations:")
            print(f"  • Related sightings: {correlations.get('related_sightings', 0)}")
            print(f"  • Campaigns: {', '.join(correlations.get('campaigns', []))}")
            print(f"  • Reporting organizations: {correlations.get('total_reporting_orgs', 0)}")

            # Display threat attribution
            attribution = results.get('threat_attribution', {})
            print(f"\nThreat Attribution:")
            print(f"  • Actor: {attribution.get('attributed_actor', 'Unknown')}")
            print(f"  • Confidence: {attribution.get('attribution_confidence', 0):.2%}")
            print(f"  • Characteristics: {', '.join(attribution.get('actor_characteristics', []))}")

            # Display confidence boost
            print(f"\nConfidence Boost: +{results.get('confidence_boost', 0)} points")

            break

        elif status['status'] == 'failed':
            print(f"\n✗ Task failed!")
            print(f"Errors: {status['errors']}")
            break

    if poll_count >= max_polls:
        print(f"\n⚠ Max polls reached, task still processing...")

    # Step 4: Get queue statistics
    print(f"\n[5] Queue Statistics:")
    print("-" * 80)
    stats_response = client.get("/v1/queue/stats", headers=headers)
    if stats_response.status_code == 200:
        stats = stats_response.json()
        print(f"Total tasks: {stats['total_tasks']}")
        print(f"Queue depth: {stats['queue_depth']}")
        print(f"Status counts: {stats['status_counts']}")
        print(f"Avg processing times: {stats.get('average_processing_times', {})}")

    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)


if __name__ == "__main__":
    test_background_processing()
