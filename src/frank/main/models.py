"""
FRANK Platform - Main API Request/Response Models

Pydantic v2 models for Main API (Sightings API) endpoints.

Note: Authentication models (LoginRequest, LoginResponse, etc.) are shared
      from frank.management.models as both APIs use the same Cognito auth.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from frank.core.models import Observable, Submission


# Submission Models

class SubmissionRequest(BaseModel):
    """Request model for submitting threat intelligence."""
    model_config = ConfigDict(extra="ignore")

    timestamp: Optional[datetime] = Field(
        default=None,
        description="Observation timestamp (defaults to now)"
    )
    observables: List[Observable] = Field(
        ...,
        description="List of threat observables (IPs, domains, hashes, etc.)"
    )
    confidence_score: Optional[float] = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence level (0.0-1.0)"
    )
    severity: Optional[str] = Field(
        default="MEDIUM",
        description="Severity level"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the threat"
    )


class SubmissionResponse(BaseModel):
    """Response after successful submission."""
    submission_id: str
    timestamp: datetime
    status: str = "accepted"
    message: str = "Submission accepted successfully"


# Query Models

class ObservableQueryParams(BaseModel):
    """Query parameters for observable search."""
    model_config = ConfigDict(extra="ignore")

    observable_type: Optional[str] = Field(
        default=None,
        description="Filter by observable type (ipv4, domain, hash, etc.)"
    )
    value: Optional[str] = Field(
        default=None,
        description="Search by observable value"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum results to return"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Offset for pagination"
    )


class ObservableQueryResponse(BaseModel):
    """Response for observable queries."""
    observables: List[Observable]
    total: int
    offset: int
    limit: int


# Statistics Models

class StatisticsResponse(BaseModel):
    """Platform statistics response."""
    total_submissions: int
    total_observables: int
    submissions_last_24h: int
    submissions_last_7d: int
    top_observable_types: List[dict]
    top_contributors: List[dict]


# Health Check Models

class HealthResponse(BaseModel):
    """Basic health check response."""
    status: str = "healthy"
    timestamp: datetime
    version: str


class DeepHealthResponse(BaseModel):
    """Deep health check response with component status."""
    status: str
    timestamp: datetime
    version: str
    components: dict = Field(
        ...,
        description="Status of each component (database, auth, etc.)"
    )
