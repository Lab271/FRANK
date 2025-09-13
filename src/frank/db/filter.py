class FRANKFilter:
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