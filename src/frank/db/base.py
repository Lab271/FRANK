#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This modules provides an abstract base class defining the interface for
FRANK database operations, supporting both SQLite and DynamoDB implementations
with a consistent API.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from frank.core.models import Submission, Observable
from frank.core.enum import ObservableType, TierLevel
from frank.utils import NullLogger

class BaseFRANKDatabase(ABC):
    """
    Abstract base class defining the interface for FRANK database operations.
    Supports both SQLite and DynamoDB implementations with consistent API.
    """
    
    def __init__(self, connection_params: Dict[str, Any], logger: Optional[logging.Logger] = None):
        self.connection_params = connection_params
        self.logger = logger or NullLogger()
        self.initialize()
    
    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize database connection and schema.

        This method should set up the database connection and create any required tables or indexes.
        It is called automatically during class instantiation.

        Returns:
            None
        """
        pass

    @abstractmethod
    def upsert_organization(self, org_data: Dict[str, Any]) -> bool:
        """
        Insert or update organization information in the database.

        Args:
            org_data (Dict[str, Any]): Dictionary containing organization details.

        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def store_submission(self, submission: Submission) -> bool:
        """
        Store a complete submission in the database.

        Args:
            submission (Submission): The submission object to store.

        Returns:
            bool: True if stored successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_submission_by_id(self, submission_id: str, org_id: str, access_level: TierLevel = TierLevel.CONTRIBUTOR) -> Optional[Submission]:
        """
        Retrieve a specific submission with access level filtering.

        Args:
            submission_id (str): The ID of the submission to retrieve.
            org_id (str): The organization ID making the request.
            access_level (TierLevel): The access level for filtering (default: CONTRIBUTOR).

        Returns:
            Optional[Submission]: The filtered Submission object, or None if not found.
        """
        pass
    
    @abstractmethod
    def query_observables(self, org_id: str, observable_type: ObservableType = None, 
                         limit: int = 100, access_level: TierLevel = TierLevel.CONTRIBUTOR) -> List[Observable]:
        """
        Query observables with access level filtering.

        Args:
            org_id (str): The organization ID making the request.
            observable_type (ObservableType, optional): Type of observable to filter (default: None).
            limit (int, optional): Maximum number of results to return (default: 100).
            access_level (TierLevel, optional): Access level for filtering (default: CONTRIBUTOR).

        Returns:
            List[Observable]: List of filtered Observable objects.
        """
        pass
    
    @abstractmethod
    def get_statistics_summary(self, org_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get platform statistics summary for an organization.

        Args:
            org_id (str): The organization ID to get statistics for.
            days (int, optional): Number of days to include in the summary (default: 30).

        Returns:
            Dict[str, Any]: Dictionary containing summary statistics.
        """
        pass

    @abstractmethod
    def log_access(self, org_id: str, action: str, 
                   resource_type: str = None, resource_id: str = None, 
                   details: Dict[str, Any] = None) -> bool:
        """
        Log an access event for auditing purposes.

        Args:
            org_id (str): The organization ID performing the action.
            action (str): The action performed (e.g., 'READ', 'WRITE').
            resource_type (str, optional): Type of resource accessed (e.g., 'submission').
            resource_id (str, optional): ID of the resource accessed.
            details (Dict[str, Any], optional): Additional details about the access event.

        Returns:
            bool: True if the log was stored successfully, False otherwise.
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the database.

        Returns:
            Dict[str, Any]: Dictionary containing health status and metadata.
        """
        pass
     
    def hash_observable(self, observable_type: str, observable_value: str) -> str:
        """
        Create a SHA-256 hash for observable deduplication and quick lookups.

        Args:
            observable_type (str): The type/category of the observable (e.g., 'ip', 'domain').
            observable_value (str): The value of the observable (e.g., '1.2.3.4', 'example.com').

        Returns:
            str: A SHA-256 hexadecimal hash string uniquely representing the observable.
        """
        combined = f"{observable_type}:{observable_value}".lower()
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def _filter_submission_by_access_level(self, submission: Dict[str, Any], access_level: TierLevel) -> Dict[str, Any]:
        """
        Filter submission data based on the provided access level.

        This method applies privacy and access rules to a submission dict, returning only the allowed fields
        for the specified access tier. It supports the following tiers:

        - PUBLIC: Only basic statistics (submission_id, timestamp, sighting confidence, timestamp, observation_count).
        - OBSERVER: Masks observable values, removes sensitive fields (hit_target, tlp_level).
        - CONTRIBUTOR: Removes organization_id from hit_target, anonymizes sector.
        - PARTNER/CORE_MEMBER: Returns full submission data.

        Args:
            submission (Dict[str, Any]): The full submission data as a dictionary.
            access_level (TierLevel): The access tier to filter for (PUBLIC, OBSERVER, CONTRIBUTOR, etc).

        Returns:
            Dict[str, Any]: A dictionary containing the filtered submission data under the 'submission' key.
        """
        self.logger.info(f"Filtering submission for access level: {access_level.value}")
        self.logger.debug(f"Original submission data: {submission}")
        if access_level == TierLevel.PUBLIC:
            # Only basic statistics
            return {
                'submission': {
                    'submission_id': submission.get('submission_id'),
                    'timestamp': submission.get('timestamp'),
                    'sighting': {
                        'confidence': submission['sighting'].get('confidence'),
                        'timestamp': submission['sighting'].get('timestamp'),
                        'observation_count': submission['sighting'].get('observation_count')
                    }
                }
            }
        elif access_level == TierLevel.OBSERVER:
            # Add some observable types but mask values
            filtered = self._deep_copy(submission)
            observables = filtered['sighting'].get('observables', {})
            for category, obs_list in observables.items():
                if isinstance(obs_list, list):
                    for obs in obs_list:
                        if 'value' in obs:
                            obs['value'] = obs['value'][:10] + "..." if len(obs['value']) > 10 else obs['value']
            
            # Remove sensitive sections
            filtered.pop('hit_target', None)
            filtered.pop('tlp_level', None)

            return {'submission': filtered}
        elif access_level == TierLevel.CONTRIBUTOR:
            # Remove only the most sensitive information
            filtered = self._deep_copy(submission)
            
            # Anonymize hit target details
            if 'hit_target' in filtered:
                hit_target = filtered['hit_target']
                hit_target.pop('organization_id', None)
                hit_target['sector'] = hit_target.get('sector', 'unknown')

            return {'submission': filtered}

        # Partner and core_member get full access
        return {'submission': submission}

    def _deep_copy(self, obj: Any) -> Any:
        """Create a deep copy of an object."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj
        
    def _filter_observable_by_access_level(self, observable: Dict[str, Any], access_level: TierLevel) -> Dict[str, Any]:
        """
        Filter observable data based on the provided access level.

        This method applies privacy and access rules to an observable summary dict, returning only the allowed fields
        for the specified access tier. It supports the following tiers:

        - PUBLIC: Only basic statistics (observable_type, total_sightings, last_seen).
        - OBSERVER: Masks observable_value, returns all other fields.
        - CONTRIBUTOR, PARTNER, CORE_MEMBER: Returns full observable data.

        Args:
            observable (Dict[str, Any]): The full observable summary data as a dictionary.
            access_level (TierLevel): The access tier to filter for (PUBLIC, OBSERVER, CONTRIBUTOR, etc).

        Returns:
            Dict[str, Any]: A dictionary containing the filtered observable data.
        """
        if access_level == TierLevel.PUBLIC:
            return {
                'observable_type': observable['observable_type'],
                'total_sightings': observable['total_sightings'],
                'last_seen': observable['last_seen']
            }
        elif access_level == TierLevel.OBSERVER:
            filtered = dict(observable)
            # Mask observable value
            if 'observable_value' in filtered:
                value = filtered['observable_value']
                filtered['observable_value'] = value[:10] + "..." if len(value) > 10 else value
            return filtered
        
        # Contributor and above get full access
        return observable