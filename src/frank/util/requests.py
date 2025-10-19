#!/usr/bin/env python3
"""
FRANK Platform - Pydantic Models (v2 Compatible)

Support models for API handling.
Implements "be forgiving on what you receive, strong on what you return" principle.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
from datetime import datetime, timezone

from fastapi import Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from pydantic import field_validator

from frank.util.http_exceptions import BadRequestException
from frank.core.models import Submission, Submitter, ObservableType, Sighting
from frank.core.enum import TLPLevel, SubmissionLevel

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
    

class ObservationsSearchQuery(BaseModel):
    """Model for sighting search query parameters"""

    model_config = ConfigDict(
        extra="ignore",  # Be forgiving on input
        use_enum_values=True,
        populate_by_name=True,  # Allow both field name and alias
    )


    observable: Optional[str] = Query(None, description="Specific IoC to search for")
    observable_type: Optional[ObservableType] = Query(None, alias="type", description="Observable type filter")
    start_date: Optional[datetime] = Query(None, description="Search start date")
    end_date: Optional[datetime] = Query(None, description="Search end date")
    limit: int = Query(100, description="Maximum number of results to return")  

    @field_validator("end_date")
    def validate_date_range(cls, end_date, info):
        start_date = info.data.get("start_date")
        if start_date and end_date and start_date >= end_date:
            raise BadRequestException(
                "Invalid date range: start_date must be before end_date"
            )
        return end_date

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dict excluding None values"""
        query_params = self.model_dump()
        # Add sector as list if present
        # if query_params.get("sector"):
        #     query_params["sectors"] = [query_params.pop("sector")]

        # Calculate days_back if start_date is present
        if query_params.get("start_date"):
            days_back = (datetime.now(timezone.utc) - query_params["start_date"]).days
            query_params["days_back"] = max(1, days_back)

        return query_params

# Response models
class SubmissionResponse(BaseModel):
    status: str = Field(..., description="Processing status")
    submission_id: str = Field(..., description="Unique submission identifier")
    submitter_id: Optional[str] = Field(None, description="Unique submitter identifier")
    request_id: Optional[str] = Field(None, description="Unique request identifier")
    timestamp: datetime = Field(..., description="Timestamp of submission acceptance")
    tlp_level: Optional[TLPLevel] = Field(None, description="TLP classification level")
    submission_level: Optional[SubmissionLevel] = Field(None, description="Depth of the submission")
    processing_status: str = Field(..., description="Current processing state")
    validation_required: bool = Field(False, description="Whether validation is required")
    estimated_processing_time: Optional[str] = Field(None, description="Processing time estimate")

class SightingSearchResponse(BaseModel):
    total_results: int = Field(..., description="Total matching results")
    sightings: List[Sighting] = Field(..., description="Array of sighting objects")


# Dedicated response model for Observations (Observable statistics/details)
class ObservationsResponse(BaseModel):
    total_results: int = Field(..., description="Total number of matching observations")
    # returned_results: int = Field(..., description="Number of observations in this response")
    observations: List[Dict[str, Any]] = Field(..., description="Array of observation/observable objects")
    # stats: Optional[Dict[str, Any]] = Field(None, description="Aggregated statistics for observables")
    # observable_types: Optional[List[str]] = Field(None, description="List of observable types included")
    # pagination: Optional[Dict[str, Any]] = Field(None, description="Pagination information")