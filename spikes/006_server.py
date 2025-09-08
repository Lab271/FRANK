#!/usr/bin/env python3
"""
FRANK Platform - FastAPI Spike Solution
A working prototype API server implementing the FRANK threat intelligence platform
using FastAPI and the SQLite database backend.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import enums from FRANK core 
from frank.core.enum import ObservableType, SeverityLevel, TierLevel, TLPLevel
from frank.core.models import Submission

# Import our FRANK database
from frank.db.sqlite import SQLiteFRANKDatabase
from frank.utils.sample_builder import generate_minimal_submission
from frank.utils.api import SubmissionRequest, SubmissionResponse, SightingSearchResponse, ErrorResponse
from frank import __version__

# Initialize FastAPI app
app = FastAPI(
    title="FRANK Platform API",
    description="Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)  # Don't auto-raise errors

# Database instance (global for spike)
db_path = os.getenv("FRANK_DB_PATH", "/tmp/frank_spike.db")
db = SQLiteFRANKDatabase(db_path)


# Authentication and authorization functions
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Extract user information from JWT token.
    In a real implementation, this would validate the JWT and extract claims.
    For this spike, we'll mock the user data.
    """
    # Check if credentials were provided
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    # Mock user data for spike - in production, decode and validate JWT
    token = credentials.credentials
    
    # Simple mock based on token prefix for demonstration
    if token.startswith("observer_"):
        return {
            "organization_id": "demo-observer-org",
            "tier": "observer",
            "sector": "technology"
        }
    elif token.startswith("contributor_"):
        return {
            "organization_id": "demo-contributor-org", 
            "tier": "contributor",
            "sector": "financial"
        }
    elif token.startswith("partner_"):
        return {
            "organization_id": "demo-partner-org",
            "tier": "partner", 
            "sector": "cybersecurity_services"
        }
    elif token.startswith("core_"):
        return {
            "organization_id": "demo-core-org",
            "tier": "core_member",
            "sector": "government"
        }
    else:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )

def check_submission_permissions(user: Dict[str, Any]) -> bool:
    """Check if user can submit threat intelligence"""
    allowed_tiers = ["contributor", "partner", "core_member"]
    return user.get("tier") in allowed_tiers

def check_access_level(user_tier: str, required_level: str) -> bool:
    """Check if user tier meets required access level"""
    tier_hierarchy = {
        "public": 0,
        "observer": 1,
        "contributor": 2,
        "partner": 3,
        "core_member": 4
    }
    
    user_level = tier_hierarchy.get(user_tier, 0)
    required_level_num = tier_hierarchy.get(required_level, 0)
    
    return user_level >= required_level_num

# Rate limiting (simplified for spike)
class RateLimiter:
    def __init__(self):
        self.requests = {}
    
    def check_rate_limit(self, user_id: str, tier: str) -> bool:
        # Simplified rate limiting - in production use Redis or similar
        # For spike, we'll just return True
        return True

rate_limiter = RateLimiter()

# API Endpoints

@app.post("/v1/submission", response_model=SubmissionResponse)
async def submit_threat_intelligence(
    request: Request,
    submission_request: SubmissionRequest = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Submit threat intelligence sighting to the platform.
    Requires Contributor, Partner, or Core Member access level.
    """
    
    # Check permissions
    if not check_submission_permissions(current_user):
        raise HTTPException(
            status_code=403,
            detail="Insufficient access level for submission"
        )
    
    # Check rate limiting
    if not rate_limiter.check_rate_limit(current_user["organization_id"], current_user["tier"]):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )
    
    try:
     
        # Store in database
        success = db.store_submission(submission_request.submission)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to store submission"
            )
        
        # Calculate contribution score impact (simplified)
        score_impact = calculate_contribution_score(submission_request.submission)
        
        return SubmissionResponse(
            status="accepted",
            submission_id=submission_request.submission.submission_id,
            contribution_score_impact=score_impact,
            processing_status="queued",
            validation_required=False,
            estimated_processing_time="2-5 minutes"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Submission validation failed: {str(e)}"
        )

@app.get("/v1/sighting", response_model=SightingSearchResponse)
async def search_threat_sightings(
    current_user: Dict[str, Any] = Depends(get_current_user),
    observable: Optional[str] = Query(None, description="Specific IoC to search for"),
    type: Optional[ObservableType] = Query(None, description="Observable type filter"),
    start_date: Optional[datetime] = Query(None, description="Search start date"),
    end_date: Optional[datetime] = Query(None, description="Search end date"),
    sector: Optional[str] = Query(None, description="Target sector filter"),
    confidence_min: Optional[int] = Query(None, ge=0, le=100, description="Minimum confidence score"),
    tlp_level: Optional[TLPLevel] = Query(None, description="Traffic Light Protocol level"),
    campaign: Optional[str] = Query(None, description="Threat campaign identifier"),
    limit: Optional[int] = Query(50, ge=1, le=1000, description="Maximum results to return"),
    offset: Optional[int] = Query(0, ge=0, description="Pagination offset"),
    format: Optional[str] = Query("summary", description="Response format")
):
    """
    Retrieve threat intelligence sightings based on search criteria.
    Available to Observer, Contributor, Partner, and Core Member tiers.
    """
    
    # Check rate limiting
    if not rate_limiter.check_rate_limit(current_user["organization_id"], current_user["tier"]):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )
    
    try:
        # Validate date range
        if start_date and end_date and start_date >= end_date:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_QUERY_PARAMETERS",
                        "message": "Invalid date range: start_date must be before end_date",
                        "details": {
                            "start_date": start_date.isoformat() if start_date else None,
                            "end_date": end_date.isoformat() if end_date else None
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "request_id": f"req-{uuid.uuid4()}"
                    }
                }
            )
        
        # Build query parameters
        query_params = {
            "org_id": current_user["organization_id"],
            "access_level": current_user["tier"],
            "limit": limit
        }
        
        # Add filters if provided
        if type:
            query_params["observable_type"] = type.value
        if confidence_min:
            query_params["min_confidence"] = confidence_min
        if sector:
            query_params["sectors"] = [sector]
        if start_date or end_date:
            # Calculate days back from start_date if provided
            if start_date:
                days_back = (datetime.now(timezone.utc) - start_date).days
                query_params["days_back"] = max(1, days_back)
        
        # Search by specific observable if provided
        if observable:
            results = db.search_observables_by_value(
                current_user["organization_id"],
                observable,
                current_user["tier"]
            )
        else:
            # General query
            results = db.query_observables(**query_params)
        
        # Apply pagination
        total_results = len(results)
        paginated_results = results[offset:offset + limit]
        
        # Build response based on access level and format
        sightings = []
        for result in paginated_results:
            sighting = format_sighting_response(result, current_user["tier"], format)
            sightings.append(sighting)
        
        response = SightingSearchResponse(
            total_results=total_results,
            returned_results=len(sightings),
            sightings=sightings
        )
        
        # Add aggregations for contributor and above
        if check_access_level(current_user["tier"], "contributor"):
            response.aggregations = generate_aggregations(results, current_user["tier"])
        
        # Add threat context for partner and above
        if check_access_level(current_user["tier"], "partner"):
            response.threat_context = generate_threat_context(results)
        
        # Add pagination info
        if total_results > offset + limit:
            response.pagination = {
                "has_next": True,
                "next_offset": offset + limit,
                "has_previous": offset > 0,
                "previous_offset": max(0, offset - limit)
            }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )

# Health and status endpoints
@app.get("/v1/health")
async def health_check():
    """Health check endpoint"""
    health_status = db.health_check()
    return {
        "status": "healthy" if health_status["status"] == "healthy" else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": health_status,
        "version": "0.1.0"
    }

@app.get("/v1/statistics")
async def get_platform_statistics(
    current_user: Dict[str, Any] = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """Get platform usage statistics"""
    if not check_access_level(current_user["tier"], "observer"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient access level"
        )
    
    stats = db.get_statistics_summary(current_user["organization_id"], days)
    
    # Filter stats based on access level
    if current_user["tier"] == "observer":
        # Remove sensitive information for observers
        filtered_stats = {
            "total_submissions": stats.get("total_submissions", 0),
            "observable_types": stats.get("observable_types", {}),
            "daily_activity": stats.get("daily_activity", {})
        }
        return filtered_stats
    
    return stats

# Helper functions
def calculate_contribution_score(submission: Submission) -> int:
    """Calculate contribution score impact for a submission"""
    base_score = 10
    
    # Add points for observables
    obs = submission.sighting.observables
    observable_count = len(obs.network or []) + len(obs.file or []) + len(obs.process or [])
    score = base_score + observable_count * 2
    
    # Add points for SIGMA detection
    if submission.sighting.sigma_detection:
        score += 5
    
    # Add points for threat context
    if submission.sighting.threat_context:
        score += 3
    
    # Add points for impact data
    if submission.sighting.impact:
        score += 2
    
    return min(score, 25)  # Cap at 25 points

def format_sighting_response(result: Dict[str, Any], access_level: str, format_type: str) -> Dict[str, Any]:
    """Format sighting data based on access level and format type"""
    
    if access_level == "observer":
        # Minimal data for observers
        return {
            "sighting_id": f"sighting-masked-{result.get('observable_hash', 'unknown')[:8]}",
            "timestamp": result.get("last_seen", datetime.now(timezone.utc).isoformat()),
            "observable_type": result.get("observable_type"),
            "observable_value": mask_observable_value(result.get("observable_value", ""), result.get("observable_type", "")),
            "confidence": result.get("avg_confidence", 50),
            "geographic_region": "masked"
        }
    elif access_level == "contributor":
        # Partial data for contributors
        return {
            "sighting_id": f"sighting-{result.get('observable_hash', 'unknown')[:12]}",
            "timestamp": result.get("last_seen"),
            "observable": {
                "type": result.get("observable_type"),
                "value": result.get("observable_value"),
            },
            "confidence": result.get("avg_confidence"),
            "total_sightings": result.get("total_sightings"),
            "sectors": result.get("sectors", [])
        }
    else:
        # Full data for partners and core members
        return {
            "sighting_id": f"sighting-{result.get('observable_hash')}",
            "timestamp": result.get("last_seen"),
            "observable": {
                "type": result.get("observable_type"),
                "value": result.get("observable_value"),
            },
            "confidence": result.get("avg_confidence"),
            "total_sightings": result.get("total_sightings"),
            "unique_organizations": result.get("unique_organizations"),
            "first_seen": result.get("first_seen"),
            "sectors": result.get("sectors", []),
            "regions": result.get("regions", [])
        }

def mask_observable_value(value: str, obs_type: str) -> str:
    """Mask observable values for lower access tiers"""
    if obs_type == "ipv4" and "." in value:
        parts = value.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.***"
    elif obs_type == "domain":
        return f"{'*' * (len(value) // 2)}{value[len(value) // 2:]}"
    elif len(value) > 10:
        return f"{value[:10]}..."
    return value

def generate_aggregations(results: List[Dict[str, Any]], access_level: str) -> Dict[str, Any]:
    """Generate statistical aggregations from results"""
    if not results:
        return {}
    
    # Count unique organizations (simplified)
    total_orgs = len(set(result.get("observable_hash") for result in results))
    
    # Confidence distribution
    confidence_dist = {"high": 0, "medium": 0, "low": 0}
    for result in results:
        conf = result.get("avg_confidence", 0) or 0
        if conf >= 80:
            confidence_dist["high"] += 1
        elif conf >= 60:
            confidence_dist["medium"] += 1
        else:
            confidence_dist["low"] += 1
    
    return {
        "total_organizations": total_orgs,
        "confidence_distribution": confidence_dist,
        "total_sightings": sum(result.get("total_sightings", 0) for result in results)
    }

def generate_threat_context(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate threat context information for high-tier users"""
    # This would typically involve querying campaign and threat actor data
    # For the spike, we'll return mock context
    return {
        "campaigns_involved": ["banking_campaign_2025", "phishing_wave_q1"],
        "threat_actors": ["unknown_cybercriminal_group"],
        "mitre_attack": {
            "techniques": ["T1566.001", "T1071.001"],
            "tactics": ["initial_access", "command_and_control"]
        },
        "affected_sectors": ["financial", "healthcare", "retail"]
    }

# Startup event to initialize demo data
@app.on_event("startup")
async def startup_event():
    """Initialize the database with some demo data"""
    print(f"Starting FRANK API server with database: {db_path}")
    
    # Create some demo organizations
    demo_orgs = [
        {
            "organization_id": "demo-observer-org",
            "tier": "observer",
            "sector": "technology",
            "region": "nl_north_holland"
        },
        {
            "organization_id": "demo-contributor-org", 
            "tier": "contributor",
            "sector": "financial",
            "region": "nl_north_holland"
        },
        {
            "organization_id": "demo-partner-org",
            "tier": "partner",
            "sector": "cybersecurity_services",
            "region": "nl_north_holland"
        },
        {
            "organization_id": "demo-core-org",
            "tier": "core_member",
            "sector": "government",
            "region": "nl_north_holland"
        }
    ]
    
    for org in demo_orgs:
        db.upsert_organization(org)
    
    # Create some demo submissions
    for i in range(5):
        demo_submission = generate_minimal_submission(
            org_id="demo-partner-org",
            tier="partner",
            confidence=70 + i * 5
        )
        db.store_submission(demo_submission)
    
    print("Demo data initialized")

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": f"req-{uuid.uuid4()}"
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR", 
                "message": "An internal server error occurred",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": f"req-{uuid.uuid4()}"
            }
        }
    )

if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        # "main:app",
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )