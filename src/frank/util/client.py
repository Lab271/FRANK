#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This modules provides a high-level client interface combining submission handling
with database operations for easy integration into applications.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
from typing import Dict, Any, List, Optional

import logging
from datetime import datetime, timezone

from frank.core.models import Submission
from frank.core.enum import TierLevel
from frank.storage import BaseFRANKDatabase
from frank.storage import FRANKDatabaseError, FRANKConfigurationError, FRANKConnectionError

from .sample_builder import FRANKDatabaseSeeder
from .logging import NullLogger
from frank import __version__
    
class FRANKClient:
    """
    High-level FRANK client that combines submission handling with database operations.
    
    This is the main interface most users should interact with, providing a simple
    API that handles both submission processing and storage automatically.
    """

    def __init__(self, database: BaseFRANKDatabase, logger: logging.Logger = None):
        self.logger = logger or NullLogger()
        self.database = database
        self.database.logger = self.logger

    def submit_threat_intelligence(self, submission: Submission) -> (bool, int):
        """
        Submit threat intelligence to the FRANK platform.
        
        Args:
            submission: Threat intelligence submission dictionary
            
        Returns:
            True if successful
            
        """
        
        # Store in database
        success = self.database.store_submission(submission)

        # Calculate contribution score impact (simplified)
        score_impact = calculate_contribution_score(submission)
                
        # Extract submission ID
        return (success, score_impact)


    def query_threats(self, org_id: str, 
        tier: TierLevel, limit: int, offset: int, format: Optional[str], 
        observable: Optional[str] = None, **filters) -> "Tuple[int, List[Dict], Dict[str, Any], Dict[str, Any]]":
        """
        Query threat intelligence records for a given organization, applying access level filtering, pagination, and formatting.

        This method retrieves threat intelligence data from the database, applying the specified tier for access control.
        If an observable is provided, performs a targeted search; otherwise, executes a general query with additional filters.
        Results are paginated and formatted according to the requested format and tier. Aggregations and threat context are
        included for higher access levels.

        Args:
            org_id (str): Organization ID making the query.
            tier (TierLevel): Access tier for filtering and formatting results.
            limit (int): Maximum number of results to return.
            offset (int): Pagination offset.
            format (Optional[str]): Response format type.
            observable (Optional[str]): Specific observable value to search for.
            **filters: Additional query parameters (e.g., observable_type, min_confidence, days_back).

        Returns:
            Tuple[int, List[Dict], Dict[str, Any], Dict[str, Any]]: A tuple containing:
                - total_results (int): Total number of matching records.
                - sightings (List[Dict]): List of formatted sighting records for the current page.
                - aggregations (Dict[str, Any]): Statistical aggregations (for contributor and above).
                - threat_context (Dict[str, Any]): Threat context information (for partner and above).
        """

        # Search by specific observable if provided
        if observable:
            results = self.database.search_observables_by_value(org_id, observable, tier)
        else:
            # General query
            results = self.database.query_observables(**filters)

        total_results = len(results)
        paginated_results = results[offset : offset + limit]

        # Build response based on access level and format
        sightings = []
        for result in paginated_results:
            sighting = format_sighting_response(result, tier, format)
            sightings.append(sighting)

        aggregations = {}
        threat_context = {}
        # Add aggregations for contributor and above
        if tier.check_access_level(TierLevel.CONTRIBUTOR):
            aggregations = generate_aggregations(results, tier)

        # Add threat context for partner and above
        if tier.check_access_level(TierLevel.PARTNER):
            threat_context = generate_threat_context(results)

        return (total_results, sightings, aggregations, threat_context)


    def get_observations(self, org_id: str, days: int, observable_type: str, limit: int) -> "Tuple[List[Dict], Dict[str, Any]]":
        """
        Retrieve observable statistics and details for a given organization and time window.

        This method queries the database for observable statistics for the specified organization and number of days.
        It returns a list of observation summaries (filtered by observable type if provided) and the full statistics dictionary.

        Args:
            org_id (str): The organization ID for which to retrieve observations.
            days (int): Number of days to include in the statistics summary.
            observable_type (str): Filter to include only observations of this type (if provided).
            limit (int): Maximum number of observation summaries to return.

        Returns:
            Tuple[List[Dict], Dict[str, Any]]: A tuple containing:
                - List of observation summaries (each with 'observable_type' and 'count').
                - Full statistics dictionary as returned by the database.
        """
        stats = self.database.get_statistics_summary(org_id, days=days)
        observations = []
        for obs_type, count in stats.get('observable_totals', {}).items():
            if observable_type and obs_type != observable_type:
                continue
            observations.append({
                'observable_type': obs_type,
                'count': count
            })
        return observations[:limit], stats
        

    def get_platform_statistics(self, org_id: str, days: int, tier: TierLevel) -> Dict[str, Any]:
        """
        Retrieve platform statistics for a given organization and time window.

        This method queries the database for summary statistics related to submissions, observables,
        and activity for the specified organization and number of days. The returned statistics are
        filtered based on the user's access tier:
        - Observers receive only non-sensitive, aggregate statistics.
        - Higher tiers receive full statistics as provided by the database.

        Args:
            org_id (str): The organization ID for which to retrieve statistics.
            days (int): Number of days to include in the statistics summary.
            tier (TierLevel): The user's access tier, used to filter sensitive data.

        Returns:
            Dict[str, Any]: Dictionary containing platform statistics, filtered by access level.
                For observers, only aggregate stats are included.
        """
        stats = self.database.get_statistics_summary(org_id, days=days)

        # Filter stats based on access level
        if tier == TierLevel.OBSERVER:
            # Remove sensitive information for observers
            filtered_stats = {
                "total_submissions": stats.get("total_submissions", 0),
                "observable_types": stats.get("observable_types", {}),
                "daily_activity": stats.get("daily_activity", {}),
            }
            return filtered_stats

        return stats
    
    def health_check(self) -> Dict[str, str]:
        """
        Perform a health check on the FRANK platform database backend.

        This method queries the underlying database's health status and returns a summary
        including the status, current timestamp, database-specific health details, and
        the FRANK library version. Intended for use in monitoring and diagnostics.

        Returns:
            Dict[str, str]: A dictionary containing:
                - 'status': Overall health status ('healthy', 'unhealthy', etc.)
                - 'timestamp': ISO-formatted timestamp of the health check
                - '<database_name>': Database-specific health details
                - 'version': FRANK library version
        """
        health_status = self.database.health_check()
        return {
            "status": health_status["status"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            self.database.name: health_status,
            "version": __version__  # Present the proper library version
        }

    def seed_database(self, seeder: FRANKDatabaseSeeder) -> bool:
        """
        Seed the database with initial data using the provided seeder.

        This method invokes the seed method of the provided FRANKDatabaseSeeder instance,
        passing in the database client. It handles any exceptions and logs errors if seeding fails.

        Args:
            seeder (FRANKDatabaseSeeder): An instance of a database seeder class.  
        """
        try:
            seeder.seed(self.database)
            return True
        except Exception as e:
            self.logger.error(f"Database seeding failed: {e}")
            return False 

# ===============================
# Helper functions
# ===============================

def format_sighting_response(result: Dict[str, Any], access_level: TierLevel, format_type: str) -> Dict[str, Any]:
    """Format sighting data based on access level and format type"""

    if access_level == TierLevel.OBSERVER:
        # Minimal data for observers
        return {
            "sighting_id": f"sighting-masked-{result.get('observable_hash', 'unknown')[:8]}",
            "timestamp": result.get("last_seen", datetime.now(timezone.utc).isoformat()),
            "observable_type": result.get("observable_type"),
            "observable_value": mask_observable_value(
                result.get("observable_value", ""), result.get("observable_type", "")
            ),
            "confidence": result.get("avg_confidence", 50),
            "geographic_region": "masked",
        }
    elif access_level == TierLevel.CONTRIBUTOR:
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
            "sectors": result.get("sectors", []),
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
            "regions": result.get("regions", []),
        }


def mask_observable_value(value: str, obs_type: str) -> str:
    """Mask observable values for lower access tiers"""
    if obs_type == "ipv4" and "." in value:
        parts = value.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.***"
    elif obs_type == "domain":
        return f"{'*' * (len(value) // 2)}{value[len(value) // 2 :]}"
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
        "total_sightings": sum(result.get("total_sightings", 0) for result in results),
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
            "tactics": ["initial_access", "command_and_control"],
        },
        "affected_sectors": ["financial", "healthcare", "retail"],
    }



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

# ===============================
# Factory function
# ===============================

def create_client(db: BaseFRANKDatabase, logger: logging.Logger = None) -> FRANKClient:
    """
    Factory function to create a complete FRANK client with database backend.
    
    Args:
        config: Configuration dictionary (uses defaults if None)
        
    Returns:
        Configured FRANK client instance
        
    Example:
        >>> import frank
        >>> client = frank.create_frank_client()
        >>> health = client.health_check()
    """

    # Return a client that combines both
    return FRANKClient(db, logger)