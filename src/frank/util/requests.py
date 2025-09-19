#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)

Support models for API handling.
Implements "be forgiving on what you receive, strong on what you return" principle.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from frank.core.models import Submission, Submitter

# Request models
class SubmissionRequest(BaseModel):
    """
    API wrapper that handles the nested 'submission' format your API expects.
    """
    model_config = ConfigDict(
        extra="ignore"
    )
    
    submission: Submission = Field(..., description="Submission data")

class OrganisationRequest(BaseModel):
    """
    API wrapper that handles the nested 'organisation' format your API expects.
    """
    model_config = ConfigDict(
        extra="ignore"
    )
    
    organisation: Submitter = Field(..., description="Submitter data")
    

# Response models
class SubmissionResponse(BaseModel):
    status: str = Field(..., description="Processing status")
    submission_id: str = Field(..., description="Unique submission identifier")
    contribution_score_impact: Optional[int] = Field(None, description="Contribution score impact")
    processing_status: str = Field(..., description="Current processing state")
    validation_required: bool = Field(False, description="Whether validation is required")
    estimated_processing_time: Optional[str] = Field(None, description="Processing time estimate")

class SightingSearchResponse(BaseModel):
    total_results: int = Field(..., description="Total matching results")
    returned_results: int = Field(..., description="Results in this response")
    sightings: List[Dict[str, Any]] = Field(..., description="Array of sighting objects")
    aggregations: Optional[Dict[str, Any]] = Field(None, description="Statistical summaries")
    threat_context: Optional[Dict[str, Any]] = Field(None, description="Threat context data")
    pagination: Optional[Dict[str, Any]] = Field(None, description="Pagination information")


# Dedicated response model for Observations (Observable statistics/details)
class ObservationsResponse(BaseModel):
    total_results: int = Field(..., description="Total number of matching observations")
    returned_results: int = Field(..., description="Number of observations in this response")
    observations: List[Dict[str, Any]] = Field(..., description="Array of observation/observable objects")
    stats: Optional[Dict[str, Any]] = Field(None, description="Aggregated statistics for observables")
    observable_types: Optional[List[str]] = Field(None, description="List of observable types included")
    pagination: Optional[Dict[str, Any]] = Field(None, description="Pagination information")