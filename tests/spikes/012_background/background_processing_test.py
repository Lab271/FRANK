#!/usr/bin/env python3
"""
FRANK Platform - Background Task Processing Implementation
Asynchronous processing of threat intelligence submissions with task queues.

DESCRIPTION:
A production-ready implementation demonstrating background task processing for FRANK
threat intelligence submissions using FastAPI BackgroundTasks and an in-memory queue.
This spike shows how to handle long-running operations like enrichment, validation,
and threat correlation asynchronously without blocking API responses.

HYPOTHESIS:
Can background task processing significantly improve API response times while enabling
complex threat intelligence enrichment, SIGMA rule matching, and cross-correlation
analysis without impacting user experience?

RATIONALE:
Modern threat intelligence platforms need to balance immediate submission acceptance
with time-intensive processing tasks like MITRE ATT&CK mapping, threat actor attribution,
malware family classification, and historical correlation. Background processing allows
the API to quickly accept submissions while performing sophisticated analysis asynchronously.

KEY VALIDATION AREAS:
- API response time improvement with deferred processing
- Task queue reliability and error handling for failed enrichment operations
- Status tracking and progress monitoring for long-running analysis tasks
- Concurrent processing capabilities for multiple simultaneous submissions
- Resource management and backpressure handling under high submission volumes

IMPLEMENTATION:
This spike implements:
1. FastAPI endpoints for submission with background task processing
2. In-memory task queue with status tracking and progress monitoring
3. Background workers for threat enrichment, SIGMA detection, and correlation
4. Status endpoints for monitoring task progress and retrieving results
5. Simulated long-running operations (enrichment, rule matching, threat correlation)

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
import uuid
import time
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum
import logging
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

# Import FRANK core components
from frank.core.enum import AccessTier
from frank.core.models import Submission, Observable, Observables
from frank.storage.sqlite import create_sqlite_database
from frank.util.sample_builder import generate_minimal_submission
from frank.util.requests import SubmissionRequest
from frank import __version__

logger = logging.getLogger(__name__)


# Task Status Enum
class TaskStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    ENRICHING = "enriching"
    VALIDATING = "validating"
    CORRELATING = "correlating"
    COMPLETED = "completed"
    FAILED = "failed"


# Task Queue (In-memory for spike - use Redis/RabbitMQ in production)
class TaskQueue:
    """Simple in-memory task queue for spike demonstration"""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.processing_times: Dict[str, List[float]] = defaultdict(list)

    def create_task(self, submission_id: str, submission: Submission) -> str:
        """Create a new background task"""
        task_id = f"task-{uuid.uuid4()}"
        self.tasks[task_id] = {
            "task_id": task_id,
            "submission_id": submission_id,
            "submission": submission,
            "status": TaskStatus.QUEUED,
            "progress": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "steps": [],
            "enrichment_results": {},
            "errors": []
        }
        return task_id

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        return self.tasks.get(task_id)

    def update_task(self, task_id: str, status: TaskStatus, progress: int, step: str = None):
        """Update task status and progress"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status
            self.tasks[task_id]["progress"] = progress
            self.tasks[task_id]["updated_at"] = datetime.now(timezone.utc)
            if step:
                self.tasks[task_id]["steps"].append({
                    "step": step,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": status
                })

    def complete_task(self, task_id: str, results: Dict[str, Any]):
        """Mark task as completed with results"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = TaskStatus.COMPLETED
            self.tasks[task_id]["progress"] = 100
            self.tasks[task_id]["enrichment_results"] = results
            self.tasks[task_id]["updated_at"] = datetime.now(timezone.utc)

            # Track processing time
            duration = (self.tasks[task_id]["updated_at"] - self.tasks[task_id]["created_at"]).total_seconds()
            submission = self.tasks[task_id]["submission"]
            if submission and submission.submitter:
                access_level = submission.submitter.access_level
                self.processing_times[str(access_level)].append(duration)

    def fail_task(self, task_id: str, error: str):
        """Mark task as failed with error"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = TaskStatus.FAILED
            self.tasks[task_id]["errors"].append({
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            self.tasks[task_id]["updated_at"] = datetime.now(timezone.utc)

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        status_counts = defaultdict(int)
        for task in self.tasks.values():
            status_counts[task["status"]] += 1

        avg_processing_times = {}
        for tier, times in self.processing_times.items():
            avg_processing_times[tier] = sum(times) / len(times) if times else 0

        return {
            "total_tasks": len(self.tasks),
            "status_counts": dict(status_counts),
            "average_processing_times": avg_processing_times,
            "queue_depth": status_counts[TaskStatus.QUEUED]
        }


# Global task queue
task_queue = TaskQueue()


# Background Processing Functions
async def enrich_submission(task_id: str, submission: Submission, db):
    """
    Background worker that enriches a submission with additional threat intelligence.

    This simulates:
    1. SIGMA rule detection matching
    2. MITRE ATT&CK technique mapping
    3. Threat actor attribution
    4. Historical correlation with previous sightings
    5. Geographic and infrastructure enrichment
    """
    try:
        task_queue.update_task(task_id, TaskStatus.PROCESSING, 10, "Starting enrichment")
        logger.info(f"Starting enrichment for task {task_id}")

        # Step 1: Initial validation (simulate processing time)
        await asyncio.sleep(0.5)
        task_queue.update_task(task_id, TaskStatus.VALIDATING, 25, "Validating observables")
        logger.info(f"Task {task_id}: Validating observables")

        # Step 2: SIGMA rule detection (simulate rule matching)
        await asyncio.sleep(1.0)
        task_queue.update_task(task_id, TaskStatus.ENRICHING, 40, "Matching SIGMA rules")
        logger.info(f"Task {task_id}: Matching SIGMA detection rules")

        sigma_matches = simulate_sigma_detection(submission)

        # Step 3: MITRE ATT&CK mapping
        await asyncio.sleep(0.8)
        task_queue.update_task(task_id, TaskStatus.ENRICHING, 60, "Mapping MITRE techniques")
        logger.info(f"Task {task_id}: Mapping MITRE ATT&CK techniques")

        mitre_techniques = simulate_mitre_mapping(submission)

        # Step 4: Historical correlation
        await asyncio.sleep(1.2)
        task_queue.update_task(task_id, TaskStatus.CORRELATING, 75, "Correlating with historical data")
        logger.info(f"Task {task_id}: Correlating with historical sightings")

        correlation_results = simulate_correlation(submission, db)

        # Step 5: Threat actor attribution
        await asyncio.sleep(0.7)
        task_queue.update_task(task_id, TaskStatus.ENRICHING, 90, "Threat actor attribution")
        logger.info(f"Task {task_id}: Performing threat actor attribution")

        attribution = simulate_threat_attribution(submission)

        # Compile enrichment results
        enrichment_results = {
            "sigma_detections": sigma_matches,
            "mitre_attack": mitre_techniques,
            "correlations": correlation_results,
            "threat_attribution": attribution,
            "enrichment_timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence_boost": calculate_confidence_boost(sigma_matches, correlation_results)
        }

        # Mark task as completed
        task_queue.complete_task(task_id, enrichment_results)
        logger.info(f"Task {task_id}: Enrichment completed successfully")

        # Store enriched submission in database
        db.store_submission(submission)

    except Exception as e:
        logger.error(f"Task {task_id}: Enrichment failed - {str(e)}")
        task_queue.fail_task(task_id, str(e))


# Simulation Functions (placeholder for real enrichment logic)
def simulate_sigma_detection(submission: Submission) -> List[Dict[str, Any]]:
    """Simulate SIGMA rule detection matching"""
    observables = submission.sighting.observables
    network_obs = observables.network if observables else []

    if not network_obs:
        return []

    # Simulate finding matching SIGMA rules
    return [
        {
            "rule_id": f"sigma-{uuid.uuid4()}",
            "rule_name": "Suspicious C2 Communication Pattern",
            "rule_version": "1.2.0",
            "rule_status": "stable",
            "match_confidence": 0.85,
            "matched_observables": [obs.value for obs in network_obs[:2]]
        },
        {
            "rule_id": f"sigma-{uuid.uuid4()}",
            "rule_name": "Known Malicious Infrastructure",
            "rule_version": "2.0.1",
            "rule_status": "stable",
            "match_confidence": 0.92,
            "matched_observables": [network_obs[0].value] if network_obs else []
        }
    ]


def simulate_mitre_mapping(submission: Submission) -> Dict[str, Any]:
    """Simulate MITRE ATT&CK technique mapping"""
    return {
        "techniques": [
            {
                "id": "T1071.001",
                "name": "Application Layer Protocol: Web Protocols",
                "tactic": "Command and Control",
                "confidence": 0.88
            },
            {
                "id": "T1566.001",
                "name": "Phishing: Spearphishing Attachment",
                "tactic": "Initial Access",
                "confidence": 0.75
            }
        ],
        "tactics": ["initial_access", "command_and_control", "exfiltration"]
    }


def simulate_correlation(submission: Submission, db) -> Dict[str, Any]:
    """Simulate correlation with historical sightings"""
    observables = submission.sighting.observables
    network_obs = observables.network if observables else []

    if not network_obs:
        return {"related_sightings": 0, "campaigns": []}

    # Simulate querying database for related sightings
    try:
        # Search for related observables
        search_value = network_obs[0].value
        results = db.search_observables_by_value("system", search_value, AccessTier.CORE_MEMBER)

        return {
            "related_sightings": len(results),
            "campaigns": ["banking_trojan_2025_q1", "phishing_campaign_financial"],
            "first_seen_platform": results[0]["first_seen"] if results else None,
            "total_reporting_orgs": len(set(r.get("submitter_id") for r in results)) if results else 0
        }
    except Exception as e:
        logger.warning(f"Correlation query failed: {e}")
        return {"related_sightings": 0, "campaigns": []}


def simulate_threat_attribution(submission: Submission) -> Dict[str, Any]:
    """Simulate threat actor attribution"""
    return {
        "attributed_actor": "APT-Unknown-2025",
        "attribution_confidence": 0.65,
        "actor_characteristics": [
            "financial_motivation",
            "sophisticated_infrastructure",
            "european_targets"
        ],
        "related_campaigns": ["banking_trojan_2025_q1"]
    }


def calculate_confidence_boost(sigma_matches: List[Dict], correlations: Dict) -> int:
    """Calculate confidence boost based on enrichment results"""
    boost = 0

    # Boost from SIGMA matches
    if sigma_matches:
        avg_sigma_conf = sum(m["match_confidence"] for m in sigma_matches) / len(sigma_matches)
        boost += int(avg_sigma_conf * 10)

    # Boost from correlations
    if correlations.get("related_sightings", 0) > 5:
        boost += 5

    return min(boost, 20)  # Cap at 20 point boost


# FastAPI Application
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and demo data on startup"""
    logger.info(f"Starting FRANK Background Processing Spike")
    initialize_demo_data()
    logger.info(f"Initialization complete")
    yield


app = FastAPI(
    title="FRANK Platform - Background Processing",
    description="Threat Intelligence Platform with Asynchronous Background Task Processing",
    version=__version__,
    lifespan=lifespan
)

# Security
security = HTTPBearer(auto_error=False)

# Database
db_path = os.getenv("FRANK_DB_PATH", "/tmp/frank_background_spike.db")
db = create_sqlite_database(db_path)


# Authentication
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Mock authentication for spike"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    token = credentials.credentials

    if token.startswith("contributor_"):
        return {"organisation_id": "demo-contributor", "access_level": AccessTier.CONTRIBUTOR}
    elif token.startswith("partner_"):
        return {"organisation_id": "demo-partner", "access_level": AccessTier.PARTNER}
    else:
        raise HTTPException(status_code=401, detail="Invalid token")


# API Endpoints
@app.post("/v1/submission")
async def submit_threat_intelligence(
    submission_request: SubmissionRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Submit threat intelligence with background processing.
    Returns immediately while enrichment happens asynchronously.
    """
    submission = submission_request.submission
    submission_id = submission.submission_id

    # Create background task
    task_id = task_queue.create_task(submission_id, submission)

    # Schedule background enrichment
    background_tasks.add_task(enrich_submission, task_id, submission, db)

    return {
        "status": "accepted",
        "submission_id": submission_id,
        "task_id": task_id,
        "message": "Submission accepted and queued for processing",
        "status_url": f"/v1/task/{task_id}",
        "estimated_processing_time": "5-10 seconds"
    }


@app.get("/v1/task/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get the status of a background task"""
    task = task_queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Return task status with progress
    return {
        "task_id": task["task_id"],
        "submission_id": task["submission_id"],
        "status": task["status"],
        "progress": task["progress"],
        "created_at": task["created_at"].isoformat(),
        "updated_at": task["updated_at"].isoformat(),
        "steps": task["steps"],
        "enrichment_results": task["enrichment_results"] if task["status"] == TaskStatus.COMPLETED else None,
        "errors": task["errors"]
    }


@app.get("/v1/queue/stats")
async def get_queue_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get queue statistics (requires partner tier or above)"""
    if current_user["access_level"] not in [AccessTier.PARTNER, AccessTier.CORE_MEMBER]:
        raise HTTPException(status_code=403, detail="Insufficient access level")

    return task_queue.get_queue_stats()


@app.get("/v1/health")
async def health_check():
    """Health check endpoint"""
    queue_stats = task_queue.get_queue_stats()
    db_health = db.health_check()

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "queue": {
            "total_tasks": queue_stats["total_tasks"],
            "queue_depth": queue_stats["queue_depth"],
            "status": "operational"
        },
        "database": db_health
    }


# Demo data initialization
def initialize_demo_data():
    """Initialize demo data for testing"""
    logger.info(f"Initializing demo database: {db_path}")

    # Create demo organisations
    demo_orgs = [
        {
            "organisation_id": "demo-contributor",
            "access_level": "contributor",
            "sector": "financial"
        },
        {
            "organisation_id": "demo-partner",
            "access_level": "partner",
            "sector": "cybersecurity_services"
        }
    ]

    for org in demo_orgs:
        db.upsert_organisation(org)

    # Create some historical submissions for correlation
    for i in range(10):
        demo_submission = generate_minimal_submission(
            org_id="demo-partner",
            access_level="partner",
            confidence=70 + i * 2
        )
        db.store_submission(demo_submission)

    logger.info("Demo data initialized")


# Test function for pytest
def test_run_spike():
    """Test function for pytest validation"""
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Test health endpoint
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert "queue" in response.json()

    # Test authentication
    response = client.get("/v1/queue/stats")
    assert response.status_code == 401

    # Test with mock token
    headers = {"Authorization": "Bearer partner_test_token"}
    response = client.get("/v1/queue/stats", headers=headers)
    assert response.status_code == 200
    assert "total_tasks" in response.json()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
