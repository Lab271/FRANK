#!/usr/bin/env python3
"""
FRANK Platform - Filtering Logic

This module contains the filtering logic for the FRANK platform, including functions to filter submissions
based on access levels and to format responses.


Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Any, Dict
from datetime import datetime, timezone
import logging

from frank.core.enum import TierLevel  
from frank.core.logger import NullLogger       

class FRANKFilter:
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or NullLogger()

    def filter_submission_by_access_level(self, submission: Dict[str, Any], access_level: TierLevel) -> Dict[str, Any]:
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
        
    def filter_observable_by_access_level(self, observable: Dict[str, Any], access_level: TierLevel) -> Dict[str, Any]:
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


    # # Combine with filter method?
    # def anonymize_for_tier(self, access_tier: TierLevel) -> "Submission":
    #     """Anonymize submission based on access tier - 'strong on return'"""
    #     import copy

    #     anonymized = copy.deepcopy(self)

    #     if access_tier == TierLevel.PUBLIC:
    #         # Heavy anonymization for public access
    #         for obs in anonymized.sighting.observables.network:
    #             obs.value = f"hash_{hash(obs.value) % 10000:04d}"
    #         # Remove detailed metadata
    #         anonymized.hit_target.organization_id = "redacted"
    #         anonymized.submitter.organization_id = "redacted"

    #     elif access_tier == TierLevel.OBSERVER:
    #         # Partial anonymization

    #         for obs in anonymized.sighting.observables.network:
    #             if obs.type == ObservableType.IPV4:
    #                 parts = obs.value.split(".")
    #                 obs.value = f"{parts[0]}.{parts[1]}.x.x"
    #             elif obs.type == ObservableType.DOMAIN:
    #                 obs.value = f"*.{'.'.join(obs.value.split('.')[1:])}"

    #     return anonymized

 
 
 
   # # 5. Demonstrate access-based anonymization
    # print("\n5. Testing tier-based anonymization...")
    # public_view = parsed.anonymize_for_tier(TierLevel.PUBLIC)
    # observer_view = parsed.anonymize_for_tier(TierLevel.OBSERVER)

    # print(f"  - Original IP: {parsed.sighting.observables.network[0].value}")
    # print(f"  - Observer view: {observer_view.sighting.observables.network[0].value}")
    # print(f"  - Public view: {public_view.sighting.observables.network[0].value}")
        # print("✓ Access-tier based data filtering")


    def format_sighting_response(self, result: Dict[str, Any], access_level: TierLevel, format_type: str) -> Dict[str, Any]:
        """Format sighting data based on access level and format type"""

        if access_level == TierLevel.OBSERVER:
            # Minimal data for observers
            return {
                "sighting_id": f"sighting-masked-{result.get('observable_hash', 'unknown')[:8]}",
                "timestamp": result.get("last_seen", datetime.now(timezone.utc).isoformat()),
                "observable_type": result.get("observable_type"),
                "observable_value": self._mask_observable_value(
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

    def _mask_observable_value(self, value: str, obs_type: str) -> str:
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
