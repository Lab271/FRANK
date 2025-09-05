#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)
Support models for API handling.
Implements "be forgiving on what you receive, strong on what you return" principle.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from frank.core.enum import TierLevel
from frank.core.models import Submission, Submitter, Sighting

class SubmissionWrapper(BaseModel):
    """
    API wrapper that handles the nested 'submission' format your API expects.
    """
    model_config = ConfigDict(
        extra="ignore"
    )
    
    submission: Submission = Field(..., description="The actual FRANK submission")


# Validation schemas for different use cases
class MinimalSubmissionRequest(BaseModel):
    """Minimal required fields for quick submissions"""
    model_config = ConfigDict(extra="forbid")  # Strict on input for requests
    
    submitter_tier: TierLevel
    target_sector: str = Field(..., min_length=1)
    threat_indicators: List[str] = Field(..., min_length=1)
    confidence: Optional[int] = Field(69, ge=0, le=100)


class SubmissionData(BaseModel):
    submitter: Submitter = Field(..., description="Submitting organization data")
    hit_target: Optional[Dict[str, Any]] = Field(None, description="Target organization data")
    sighting: Sighting = Field(..., description="Threat sighting data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Submission metadata")
    sharing: Optional[Dict[str, Any]] = Field(None, description="Sharing preferences")

class SubmissionRequest(BaseModel):
    submission: SubmissionData = Field(..., description="Submission data")

# Response models
class SubmissionResponse(BaseModel):
    status: str = Field(..., description="Processing status")
    submission_id: str = Field(..., description="Unique submission identifier")
    contribution_score_impact: Optional[int] = Field(None, description="Contribution score impact")
    processing_status: str = Field(..., description="Current processing state")
    validation_required: bool = Field(False, description="Whether validation is required")
    errors: Optional[List[str]] = Field(None, description="Validation errors")
    estimated_processing_time: Optional[str] = Field(None, description="Processing time estimate")

class SightingSearchResponse(BaseModel):
    total_results: int = Field(..., description="Total matching results")
    returned_results: int = Field(..., description="Results in this response")
    sightings: List[Dict[str, Any]] = Field(..., description="Array of sighting objects")
    aggregations: Optional[Dict[str, Any]] = Field(None, description="Statistical summaries")
    threat_context: Optional[Dict[str, Any]] = Field(None, description="Threat context data")
    pagination: Optional[Dict[str, Any]] = Field(None, description="Pagination information")

