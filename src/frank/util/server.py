#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This modules provides a high-level server interface combining submission handling
with database operations for easy integration into applications.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
from typing import Dict, Any, List, Optional

from datetime import datetime, timezone
import logging

from frank.core.models import Submission
from frank.core.enum import AccessTier
from frank.storage import BaseFRANKDatabase
from frank.util.filter import FRANKFilter

from .sample_builder import FRANKDatabaseSeeder
from .logger import NullLogger
from frank import __version__
    
class FRANKServer:
    """
    High-level FRANK server that combines submission handling with database operations.
    
    This is the main interface most users should interact with, providing a simple
    API that handles both submission processing and storage automatically.

    Main features:
        - submit_threat_intelligence: Submission of threat intelligence data
        - query_threats: Querying of threat intelligence records
        - get_observations: Retrieve observable statistics and details
        - get_platform_statistics: Retrieve platform usage statistics   
        - check_health: Perform health checks on the database backend
        - seed_database: Seed the database with initial data
    """

    def __init__(self, database: BaseFRANKDatabase, logger: Optional[logging.Logger] = None):
        self.logger = logger or NullLogger()
        self.database = database
        self.database.logger = self.logger
        self.filter = FRANKFilter(self.logger)

    def submit_threat_intelligence(self, user_id: str, submission: Submission) -> int:
        """
        Submit threat intelligence to the FRANK platform.
        
        Args:
            user_id (str): Identifier for the user submitting the threat intelligence.
            submission: Threat intelligence submission dictionary
            
        Returns:
            True if successful     
        """
        
        # Store in database
        self.database.store_submission(submission)
            
        # Calculate contribution score impact (simplified)
        score_impact = calculate_contribution_score(submission)
                
        self.database.log_access(user_id, 'SUBMIT', 'submission', submission.submission_id)

        # Extract submission ID
        return score_impact


    def query_threats(self, user_id: str, access_level: AccessTier, 
        limit: int, offset: int, format: Optional[str], 
        observable: Optional[str] = None, **filters) -> "Tuple[int, List[Dict], Dict[str, Any], Dict[str, Any]]":
        """
        Query threat intelligence records for a given user, applying access level filtering, pagination, and formatting.

        This method retrieves threat intelligence data from the database, applying the specified tier for access control.
        If an observable is provided, performs a targeted search; otherwise, executes a general query with additional filters.
        Results are paginated and formatted according to the requested format and tier. Aggregations and threat context are
        included for higher access levels.

        Args:
            user_id (str): Identifier for the user querying the threat intelligence.
            access_level (AccessTier): Access tier for filtering and formatting results.
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
            results = self.database.search_observables_by_value(user_id, observable, access_level)
        else:
            # General query
            results = self.database.query_observables(user_id=user_id,  access_level=access_level,
                                            observable_type=filters.get("observable_type"), min_confidence=filters.get("min_confidence"),
                                            limit=filters.get("limit", 100), days_back=filters.get("days_back"))

        total_results = len(results)
        paginated_results = results[offset : offset + limit]

        # Build response based on access level and format
        sightings = []
        for result in paginated_results:
            sighting = format_sighting_response(result, access_level, format)
            sightings.append(sighting)

        aggregations = {}
        threat_context = {}
        # Add aggregations for contributor and above

        if access_level.check_access_level(AccessTier.CONTRIBUTOR):
            aggregations = generate_aggregations(results, access_level)

        # Add threat context for partner and above
        if access_level.check_access_level(AccessTier.PARTNER):
            threat_context = generate_threat_context(results)


        self.database.log_access(user_id, 'SEARCH', 'observables', details={'search_results': total_results})

        return (total_results, sightings, aggregations, threat_context)


    def get_observations(self, user_id: str, days: int, observable_type: str, limit: int) -> "Tuple[List[Dict], Dict[str, Any]]":
        """
        Retrieve observable statistics and details for a given user (organization) and time window.

        This method queries the database for observable statistics for the specified user and number of days.
        It returns a list of observation summaries (filtered by observable type if provided) and the full statistics dictionary.

        Args:
            user_id (str): Identifier for the user retrieving the observations.
            days (int): Number of days to include in the statistics summary.
            observable_type (str): Filter to include only observations of this type (if provided).
            limit (int): Maximum number of observation summaries to return.

        Returns:
            Tuple[List[Dict], Dict[str, Any]]: A tuple containing:
                - List of observation summaries (each with 'observable_type' and 'count').
                - Full statistics dictionary as returned by the database.
        """
        stats = self.database.get_statistics_summary(user_id, days=days)

        observations = []
        for obs_type, count in stats.get('observable_totals', {}).items():
            if observable_type and obs_type != observable_type:
                continue
            observations.append({
                'observable_type': obs_type,
                'count': count
            })
        return observations[:limit], stats
        

    def get_platform_statistics(self, user_id: str, access_level: AccessTier, days: int) -> Dict[str, Any]:
        """
        Retrieve platform statistics for a given user and time window.

        This method queries the database for summary statistics related to submissions, observables,
        and activity for the specified user and number of days. The returned statistics are
        filtered based on the user's access access_level:
        - Observers receive only non-sensitive, aggregate statistics.
        - Higher tiers receive full statistics as provided by the database.

        Args:
            user_id (str): Identifier for the user submitting the threat intelligence.
            days (int): Number of days to include in the statistics summary.
            access_level (AccessTier): The user's access tier, used to filter sensitive data.

        Returns:
            Dict[str, Any]: Dictionary containing platform statistics, filtered by access level.
                For observers, only aggregate stats are included.
        """
        stats = self.database.get_statistics_summary(user_id, days=days)

        # Filter stats based on access level
        if access_level == AccessTier.OBSERVER:
            # Remove sensitive information for observers
            filtered_stats = {
                "total_submissions": stats.get("total_submissions", 0),
                "observable_types": stats.get("observable_types", {}),
                "daily_activity": stats.get("daily_activity", {}),
            }
            return filtered_stats

        return stats

    def get_submission_by_id(self, user_id: str, access_level: AccessTier, submission_id: str) -> Optional[Submission]:
        submission_dict = self.database.get_submission_by_id(submission_id)
        if not submission_dict:
            return None
        filtered_submission = self.filter.submission_by_access_level(submission_dict, access_level)
        self.logger.debug(f"Filtered submission for access level {access_level}: {filtered_submission}")

        # Log access
        self.database.log_access(user_id, 'READ', 'submission', submission_id)

        return Submission(**filtered_submission["submission"]) if filtered_submission else None


    def health_check(self) -> Dict[str, Any]:
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
            "database": health_status,
            "version": __version__  # Present the proper library version
        }

    def seed_database(self, seeder: FRANKDatabaseSeeder) -> bool:
        """
        Seed the database with initial data using the provided seeder.

        This method invokes the seed method of the provided FRANKDatabaseSeeder instance,
        passing in the database handler. It handles any exceptions and logs errors if seeding fails.

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

def format_sighting_response(result: Dict[str, Any], access_level: AccessTier, format_type: str) -> Dict[str, Any]:
    """Format sighting data based on access level and format type"""

    if access_level == AccessTier.OBSERVER:
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
    elif access_level == AccessTier.CONTRIBUTOR:
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

def create_server(db: BaseFRANKDatabase, logger: logging.Logger = None) -> FRANKServer:
    """
    Factory function to create a complete FRANK server with database backend.
    
    Args:
        config: Configuration dictionary (uses defaults if None)
        
    Returns:
        Configured FRANK server instance
        
    Example:
        >>> import frank
        >>> server = frank.create_frank_server()
        >>> health = server.health_check()
    """

    # Return a server that combines both
    return FRANKServer(db, logger)