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
import os
from pathlib import Path

from frank.core.models import Submission, Sighting, Submitter
from frank.core.enum import AccessTier
from frank.storage import BaseFRANKDatabase
from frank.util.filter import FRANKFilter
from frank.util.aws import get_container_info

from .sample_builder import FRANKDatabaseSeeder
from .logger import NullLogger
from .http_exceptions import InternalError
import frank

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

    def __init__(self, database: BaseFRANKDatabase, config: Dict[str, Any], logger: logging.Logger = None):
        self.logger = logger
        self.database = database
        self.database.logger = self.logger
        self.filter = FRANKFilter(self.logger)
        self.config = config

    def submit_threat_intelligence(self, user: Dict[str, Any], submission: Submission) -> None:
        """
        Submit threat intelligence to the FRANK platform.
        
        Args:
            user (Dict[str, Any]): User information including user ID.
            submission: Threat intelligence submission dictionary
  
        """
        
        # Store in database
        self.database.store_submission(user, submission)       
      
        self.database.log_access(user, submission.submitter.organisation_id, "SUBMIT", submission.submission_id, 'success')

    def get_sightings_from_observations(self, user: Dict[str, Any], **query_params) -> List[Sighting]:
        """
        Retrieve sightings based on query parameters and user access level.

        This method queries the database for sightings matching the provided parameters,
        applies access level filtering, and returns a list of formatted sighting records.

        Args:
            user (Dict[str, Any]): Identifier for the user retrieving the sightings.
            **query_params: Additional query parameters (e.g., observable, observable_type, start_date, end_date, limit).
        Returns:
            List[Dict[str, Any]]: A list of formatted sighting records.
        """
        self.logger.debug(f"Querying sightings with parameters: {query_params} for user: {user}")

        sightings = self.database.list_sightings_from_observations(
          observable_value=query_params.get("observable"), observable_type=query_params.get("observable_type"),
          start_date=query_params.get("start_date"), end_date=query_params.get("end_date"),
          limit=query_params.get("limit", 100))


        return sightings

    # def query_threats(self, user_id: str, access_level: AccessTier, 
    #     limit: int, offset: int, format: Optional[str], 
    #     observable: Optional[str] = None, **filters) -> "Tuple[int, List[Dict], Dict[str, Any], Dict[str, Any]]":
    #     """
    #     Query threat intelligence records for a given user, applying access level filtering, pagination, and formatting.

    #     This method retrieves threat intelligence data from the database, applying the specified tier for access control.
    #     If an observable is provided, performs a targeted search; otherwise, executes a general query with additional filters.
    #     Results are paginated and formatted according to the requested format and tier. Aggregations and threat context are
    #     included for higher access levels.

    #     Args:
    #         user_id (str): Identifier for the user querying the threat intelligence.
    #         access_level (AccessTier): Access tier for filtering and formatting results.
    #         limit (int): Maximum number of results to return.
    #         offset (int): Pagination offset.
    #         format (Optional[str]): Response format type.
    #         observable (Optional[str]): Specific observable value to search for.
    #         **filters: Additional query parameters (e.g., observable_type, min_confidence, days_back).

    #     Returns:
    #         Tuple[int, List[Dict], Dict[str, Any], Dict[str, Any]]: A tuple containing:
    #             - total_results (int): Total number of matching records.
    #             - sightings (List[Dict]): List of formatted sighting records for the current page.
    #             - aggregations (Dict[str, Any]): Statistical aggregations (for contributor and above).
    #             - threat_context (Dict[str, Any]): Threat context information (for partner and above).
    #     """

    #     # Search by specific observable if provided
    #     if observable:
    #         results = self.database.search_observables_by_value(user_id, observable, access_level)
    #     else:
    #         # General query
    #         results = self.database.query_observables(user_id=user_id,  access_level=access_level,
    #                                         observable_type=filters.get("observable_type"), min_confidence=filters.get("min_confidence"),
    #                                         limit=filters.get("limit", 100), days_back=filters.get("days_back"))

    #     total_results = len(results)
    #     paginated_results = results[offset : offset + limit]

    #     # Build response based on access level and format
    #     sightings = []
    #     for result in paginated_results:
    #         sighting = format_sighting_response(result, access_level, format)
    #         sightings.append(sighting)

    #     aggregations = {}
    #     threat_context = {}
    #     # Add aggregations for contributor and above

    #     if access_level.check_access_level(AccessTier.CONTRIBUTOR):
    #         aggregations = generate_aggregations(results, access_level)

    #     # Add threat context for partner and above
    #     if access_level.check_access_level(AccessTier.PARTNER):
    #         threat_context = generate_threat_context(results)


    #     self.database.log_access(user_id, 'SEARCH', 'observables', details={'search_results': total_results})

    #     return (total_results, sightings, aggregations, threat_context)

    def upsert_organisation(self, user: Dict[str, Any], submitter: Submitter) -> None:
        """
        Create or update an organisation in the database.

        This method validates and upserts a Submitter (organisation) record into the database,
        logs the access event, and returns True if successful, False otherwise.

        Args:
            user (Dict[str, Any]): Identifier for the user performing the upsert.
            submitter (Submitter): The organisation Submitter object to upsert.

        Returns:
            bool: True if upsert was successful, False otherwise.
        """
        # Upsert organisation in the database
        self.database.upsert_organisation(submitter.model_dump(exclude_unset=True, by_alias=True))
        self.logger.info(f"Upserted organisation: {submitter.organisation_id}")

        # Log access
        self.database.log_access(user, submitter.organisation_id, 'UPSERT', submitter.organisation_id, 'success')


    # def get_observations(self, user: Dict[str, Any], **query_params) -> "Tuple[List[Dict], Dict[str, Any]]":
    #     """
    #     Retrieve observable statistics and details for a given user (organisation) and time window.

    #     This method queries the database for observable statistics for the specified user and number of days.
    #     It returns a list of observation summaries (filtered by observable type if provided) and the full statistics dictionary.

    #     Args:
    #         user_id (str): Identifier for the user retrieving the observations.
    #         days (int): Number of days to include in the statistics summary.
    #         observable_type (str): Filter to include only observations of this type (if provided).
    #         limit (int): Maximum number of observation summaries to return.

    #     Returns:
    #         Tuple[List[Dict], Dict[str, Any]]: A tuple containing:
    #             - List of observation summaries (each with 'observable_type' and 'count').
    #             - Full statistics dictionary as returned by the database.
    #     """

    #     observations = []
    #     for obs_type, count in stats.get('observable_totals', {}).items():
    #         if observable_type and obs_type != observable_type:
    #             continue
    #         observations.append({
    #             'observable_type': obs_type,
    #             'count': count
    #         })
    #     return observations[:limit], stats
        

    # def get_platform_statistics(self, user_id: str, access_level: AccessTier, days: int) -> Dict[str, Any]:
    #     """
    #     Retrieve platform statistics for a given user and time window.

    #     This method queries the database for summary statistics related to submissions, observables,
    #     and activity for the specified user and number of days. The returned statistics are
    #     filtered based on the user's access access_level:
    #     - Observers receive only non-sensitive, aggregate statistics.
    #     - Higher tiers receive full statistics as provided by the database.

    #     Args:
    #         user_id (str): Identifier for the user submitting the threat intelligence.
    #         days (int): Number of days to include in the statistics summary.
    #         access_level (AccessTier): The user's access tier, used to filter sensitive data.

    #     Returns:
    #         Dict[str, Any]: Dictionary containing platform statistics, filtered by access level.
    #             For observers, only aggregate stats are included.
    #     """
    #     stats = self.database.get_statistics_summary(user_id, days=days)

    #     # Filter stats based on access level
    #     if access_level == AccessTier.OBSERVER:
    #         # Remove sensitive information for observers
    #         filtered_stats = {
    #             "total_submissions": stats.get("total_submissions", 0),
    #             "observable_types": stats.get("observable_types", {}),
    #             "daily_activity": stats.get("daily_activity", {}),
    #         }
    #         return filtered_stats

    #     return stats

    def get_submission_by_id(self, user: Dict[str, Any], submission_id: str) -> Optional[Submission]:
        """
        Retrieve a submission by its ID, applying access level filtering.

        This method fetches a submission from the database by its unique ID, applies access level-based filtering,
        logs the access event, and returns a Submission object if accessible, or None if not found or not permitted.

        Args:
            user (Dict[str, Any]): Identifier for the user requesting the submission.
            submission_id (str): The unique identifier of the submission to retrieve.

        Returns:
            Optional[Submission]: The filtered Submission object if accessible, or None if not found or not permitted.
        """
        submission_dict = self.database.get_submission_by_id(submission_id)
        if not submission_dict:
            return None
        filtered_submission = self.filter.submission_by_access_level(submission_dict, user["access_level"])
        self.logger.debug(f"Filtered submission for access level {user['access_level']}: {filtered_submission}")

        submission = Submission(**filtered_submission["submission"]) if filtered_submission else None

        if submission:
            # Log access
            self.database.log_access(user, user["organisation_id"], "READ", submission.submission_id, 'success')
       
        return submission


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
        container_info = get_container_info()

        health = {
            "status": "healthy",
            "service": "frank-stage3",
            "version": frank.__version__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "container_info": container_info,
            "environement": {
                "profile": self.config.get("profile", "<not set>"),
                "environment": self.config.get("environment", "<not set>"),
                "region": self.config.get("region", "<not set>"),
                "ENDPOINT": self.config.get("endpoint", "<not set>"),
            },
            "CONTAINER_ID": os.getenv("CONTAINER_ID", "unknown"),
            "filename": Path(__file__).name, # "frank_stage3.py"
        }

        return health

    def deep_health_check(self) -> Dict[str, Any]:
        """
        Perform a deep health check on the FRANK platform database backend.

        This method performs an in-depth health check of the underlying database,
        returning detailed status information including connectivity, read/write tests,
        and other diagnostics. Useful for comprehensive monitoring and troubleshooting.

        Returns:
            Dict[str, Any]: A dictionary containing detailed health status information
            from the database backend.
        """
        health = self.health_check()

        try:
            status = self.database.health_check()
            health.update(status)
            health.update({
                "status": "connected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "table_cfg": {
                    "DYNAMODB_TABLE": self.config["table_name"],
                    "AUDIT_TABLE": self.config["audit_table_name"],
                }
            })
        except Exception as e:
            self.logger.error(f"Database connection error: {str(e)}")
            raise InternalError(detail=f"Database connection failed: {str(e)}")
        return health

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
            "unique_organisations": result.get("unique_organisations"),
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

    # Count unique organisations (simplified)
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
        "total_organisations": total_orgs,
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

def create_server(db: BaseFRANKDatabase, config: Dict[str, Any], logger: logging.Logger = None) -> FRANKServer:
    """
    Factory function to create a complete FRANK server with database backend.
    
    Args:
        db: Instance of BaseFRANKDatabase for data storage and retrieval
        config: Configuration dictionary (uses defaults if None)
        logger: Optional logger instance for logging (uses NullLogger if None)
        
    Returns:
        Configured FRANK server instance
        
    Example:
        >>> import frank
        >>> server = frank.create_server(db, logger)
        >>> health = server.health_check()
    """
    logger = logger or NullLogger()

    # Return a server that combines both
    return FRANKServer(db, config, logger)