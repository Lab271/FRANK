#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides core functionality for generating, parsing, and validating
FRANK threat intelligence submissions following the "be forgiving on what you 
receive and strong on what you return" principle.
"""

import yaml
import json
import uuid
import hashlib
from datetime import datetime, timezone
# from typing import Dict, Any, List, Optional, Tuple, Union
from typing import Dict, Any, List, Tuple
import logging
# from pathlib import Path

from frank.core.exceptions import FRANKFormatError, FRANKValidationError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FRANKSubmission:
    """
    Handles FRANK threat intelligence submissions with minimal required fields
    and graceful handling of optional extended data.
    
    Implements the "be forgiving on what you receive, strong on what you return" principle.
    """
    
    # Required fields for minimal submission
    REQUIRED_FIELDS = {
        'submission.submitter.organization_id',
        'submission.submitter.tier', 
        'submission.sighting.sighting_id',
        'submission.sighting.timestamp',
        'submission.sighting.observables'
    }
    
    # Default values following "be forgiving" principle
    DEFAULTS = {
        'confidence': 69,  # Default confidence as specified
        'format_version': '1.0',
        'submission_method': 'manual',
        'anonymization_level': 'moderate',
        'severity': 'medium',
        'observation_count': 1,
        'tlp_level': 'AMBER'
    }
    
    # Valid enumeration values
    VALID_TIERS = {'public', 'observer', 'contributor', 'partner', 'core_member'}
    VALID_SEVERITIES = {'low', 'medium', 'high', 'critical'}
    VALID_TLP_LEVELS = {'RED', 'AMBER+', 'AMBER', 'GREEN', 'CLEAR'}
    VALID_OBSERVABLE_TYPES = {'ipv4', 'ipv6', 'domain', 'url', 'file_hash', 'email', 'registry_key'}
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def generate_minimal_submission(self, 
                                  org_id: str = None,
                                  tier: str = "partner",
                                  observables: List[Dict] = None,
                                  confidence: int = None) -> Dict[str, Any]:
        """
        Generate a minimal FRANK submission with only required fields.
        
        Args:
            org_id: Organization identifier (generated if None)
            tier: Organization tier level
            observables: List of observable objects (default generated if None)
            confidence: Confidence level 0-100 (uses default if None)
            
        Returns:
            Dict containing minimal valid submission
            
        Raises:
            FRANKValidationError: If invalid values provided
        """
        
        # Validate inputs
        if tier not in self.VALID_TIERS:
            raise FRANKValidationError(f"Invalid tier '{tier}'. Must be one of: {self.VALID_TIERS}")
        
        if confidence is not None and not (0 <= confidence <= 100):
            raise FRANKValidationError(f"Confidence {confidence} out of range [0-100]")
        
        # Generate default values if not provided
        if org_id is None:
            org_id = f"identity-{uuid.uuid4()}"
            
        if observables is None:
            observables = [
                {
                    "id": f"ipv4-addr-{uuid.uuid4()}",
                    "type": "ipv4",
                    "value": "185.220.102.45"
                },
                {
                    "id": f"domain-name-{uuid.uuid4()}",
                    "type": "domain", 
                    "value": "secure-bank-verify.nl"
                }
            ]
        
        # Validate observables
        for obs in observables:
            if 'type' in obs and obs['type'] not in self.VALID_OBSERVABLE_TYPES:
                raise FRANKValidationError(f"Invalid observable type '{obs['type']}'. Must be one of: {self.VALID_OBSERVABLE_TYPES}")
        
        submission = {
            "submission": {
                "submitter": {
                    "organization_id": org_id,
                    "tier": tier
                },
                "sighting": {
                    "sighting_id": f"sighting-{uuid.uuid4()}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "confidence": confidence if confidence is not None else self.DEFAULTS['confidence'],
                    "observables": {
                        "network": observables
                    }
                }
            }
        }
        
        self.logger.info(f"Generated minimal submission for org {org_id}")
        return submission
    
    def generate_comprehensive_submission(self,
                                        org_id: str,
                                        tier: str = "partner",
                                        hit_target_org: str = None,
                                        observables: List[Dict] = None,
                                        severity: str = "medium",
                                        confidence: int = 85,
                                        campaign_context: Dict = None,
                                        sigma_detection: Dict = None,
                                        impact_data: Dict = None) -> Dict[str, Any]:
        """
        Generate a comprehensive FRANK submission with extended metadata.
        
        Args:
            org_id: Submitting organization ID
            tier: Organization tier
            hit_target_org: Organization that was targeted (optional)
            observables: List of observables
            severity: Threat severity level
            confidence: Confidence level 0-100
            campaign_context: Campaign attribution information
            sigma_detection: SIGMA rule detection context
            impact_data: Impact assessment data
            
        Returns:
            Dict containing comprehensive submission
        """
        
        # Start with minimal submission
        submission = self.generate_minimal_submission(org_id, tier, observables, confidence)
        
        # Add comprehensive metadata
        metadata = {
            "format_version": self.DEFAULTS['format_version'],
            "submission_id": f"submission-{uuid.uuid4()}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        submission["submission"]["metadata"] = metadata
        
        # Add hit target if provided
        if hit_target_org:
            submission["submission"]["hit_target"] = {
                "organization_id": hit_target_org,
                "organization_type": "customer"
            }
        
        # Enhance sighting data
        sighting = submission["submission"]["sighting"]
        sighting["severity"] = severity
        sighting["first_observed"] = datetime.now(timezone.utc).isoformat()
        sighting["last_observed"] = datetime.now(timezone.utc).isoformat()
        sighting["observation_count"] = len(observables) if observables else 1
        
        # Add SIGMA detection context if provided
        if sigma_detection:
            sighting["sigma_detection"] = sigma_detection
        
        # Add threat context if campaign provided
        if campaign_context:
            sighting["threat_context"] = {"campaign": campaign_context}
        
        # Add impact assessment if provided
        if impact_data:
            sighting["impact"] = impact_data
        
        # Add sharing preferences
        submission["submission"]["sharing"] = {
            "distribution_level": self.DEFAULTS['tlp_level'],
            "anonymization_level": self.DEFAULTS['anonymization_level']
        }
        
        self.logger.info(f"Generated comprehensive submission for org {org_id}")
        return submission
    
    def validate_submission(self, submission: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate submission following "be forgiving" principle.
        
        Args:
            submission: Submission dictionary to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        try:
            # Check required fields with graceful path traversal
            for field_path in self.REQUIRED_FIELDS:
                if not self._check_nested_field(submission, field_path):
                    issues.append(f"Missing required field: {field_path}")
            
            # Validate tier if present
            tier = self._get_nested_field(submission, 'submission.submitter.tier')
            if tier and tier not in self.VALID_TIERS:
                issues.append(f"Invalid tier '{tier}'. Must be one of: {self.VALID_TIERS}")
            
            # Validate severity if present
            severity = self._get_nested_field(submission, 'submission.sighting.severity')
            if severity and severity not in self.VALID_SEVERITIES:
                issues.append(f"Invalid severity '{severity}'. Must be one of: {self.VALID_SEVERITIES}")
            
            # Validate observables structure if present
            observables = self._get_nested_field(submission, 'submission.sighting.observables')
            if observables:
                if not any(observables.values()):
                    issues.append("Observables section present but empty")
                else:
                    # Validate individual observables
                    for category, obs_list in observables.items():
                        if isinstance(obs_list, list):
                            for i, obs in enumerate(obs_list):
                                if 'type' in obs and obs['type'] not in self.VALID_OBSERVABLE_TYPES:
                                    issues.append(f"Invalid observable type '{obs['type']}' in {category}[{i}]")
                                if 'value' not in obs:
                                    issues.append(f"Missing 'value' in observable {category}[{i}]")
            
            # Validate confidence range if present
            confidence = self._get_nested_field(submission, 'submission.sighting.confidence')
            if confidence is not None and not (0 <= confidence <= 100):
                issues.append(f"Confidence {confidence} out of range [0-100]")
            
            # Validate TLP level if present in sharing
            tlp_level = self._get_nested_field(submission, 'submission.sharing.distribution_level')
            if tlp_level and tlp_level not in self.VALID_TLP_LEVELS:
                issues.append(f"Invalid TLP level '{tlp_level}'. Must be one of: {self.VALID_TLP_LEVELS}")
                
        except Exception as e:
            issues.append(f"Error during validation: {str(e)}")
        
        is_valid = len(issues) == 0
        level = "PASSED" if is_valid else "FAILED"
        self.logger.info(f"Validation result: {level} with {len(issues)} issues")
        
        return is_valid, issues
    
    def _check_nested_field(self, data: Dict, field_path: str) -> bool:
        """
        Check if a nested field exists using dot notation.
        
        Args:
            data: Dictionary to check
            field_path: Dot-separated field path
            
        Returns:
            True if field exists and is not None
        """
        return self._get_nested_field(data, field_path) is not None
    
    def _get_nested_field(self, data: Dict, field_path: str) -> Any:
        """
        Get value from nested field using dot notation.
        
        Args:
            data: Dictionary to traverse
            field_path: Dot-separated field path
            
        Returns:
            Field value or None if not found
        """
        keys = field_path.split('.')
        current = data
        
        try:
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
            return current
        except:
            return None
    
    def enhance_submission(self, minimal_submission: Dict[str, Any], 
                          enhancements: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Enhance a minimal submission with additional data following "strong on return" principle.
        
        Args:
            minimal_submission: Base submission to enhance
            enhancements: Additional data to merge in
            
        Returns:
            Enhanced submission dictionary
        """
        if enhancements is None:
            enhancements = {}
        
        enhanced = self._deep_copy(minimal_submission)
        
        # Add format version if not present
        if not self._check_nested_field(enhanced, 'submission.metadata.format_version'):
            enhanced.setdefault('submission', {}).setdefault('metadata', {})['format_version'] = self.DEFAULTS['format_version']
        
        # Add metadata section with defaults
        metadata = enhanced['submission'].setdefault('metadata', {})
        metadata.setdefault('submission_id', f"submission-{uuid.uuid4()}")
        metadata.setdefault('format_version', self.DEFAULTS['format_version'])
        metadata.setdefault('timestamp', datetime.now(timezone.utc).isoformat())
        
        # Enhance submitter information
        submitter = enhanced['submission']['submitter']
        submitter.setdefault('submission_method', self.DEFAULTS['submission_method'])
        
        # Enhance sighting information
        sighting = enhanced['submission']['sighting']
        sighting.setdefault('severity', self.DEFAULTS['severity'])
        sighting.setdefault('observation_count', self.DEFAULTS['observation_count'])
        
        # Apply any custom enhancements
        self._deep_merge(enhanced, enhancements)
        
        self.logger.info("Enhanced submission with additional metadata")
        return enhanced
    
    def _deep_copy(self, obj: Any) -> Any:
        """Create a deep copy of an object."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj
    
    def _deep_merge(self, base: Dict, overlay: Dict) -> None:
        """
        Deep merge overlay dictionary into base dictionary.
        
        Args:
            base: Base dictionary to modify
            overlay: Dictionary to merge in
        """
        for key, value in overlay.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def hash_observable(self, observable_type: str, observable_value: str) -> str:
        """
        Create a hash for observable deduplication and quick lookups.
        
        Args:
            observable_type: Type of observable (ipv4, domain, etc.)
            observable_value: Value of the observable
            
        Returns:
            SHA256 hash string
        """
        combined = f"{observable_type}:{observable_value}".lower()
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def extract_observables(self, submission: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract all observables from a submission with normalized structure.
        
        Args:
            submission: FRANK submission dictionary
            
        Returns:
            List of observables with standardized fields
        """
        observables = []
        submission_observables = self._get_nested_field(submission, 'submission.sighting.observables')
        
        if not submission_observables:
            return observables
        
        for category, obs_list in submission_observables.items():
            if isinstance(obs_list, list):
                for obs in obs_list:
                    if 'type' in obs and 'value' in obs:
                        normalized = {
                            'id': obs.get('id', f"{obs['type']}-{uuid.uuid4()}"),
                            'type': obs['type'],
                            'value': obs['value'],
                            'category': category,
                            'hash': self.hash_observable(obs['type'], obs['value']),
                            'role': obs.get('role'),
                            'first_seen': obs.get('first_seen'),
                            'port': obs.get('port'),
                            'protocol': obs.get('protocol')
                        }
                        observables.append(normalized)
        
        return observables
    
    def to_yaml(self, submission: Dict[str, Any]) -> str:
        """
        Convert submission to YAML format for storage/transmission.
        
        Args:
            submission: Submission dictionary
            
        Returns:
            YAML string representation
        """
        try:
            return yaml.dump(submission, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise FRANKFormatError(f"Failed to convert to YAML: {e}")
    
    def from_yaml(self, yaml_str: str) -> Dict[str, Any]:
        """
        Parse submission from YAML format with error handling.
        
        Args:
            yaml_str: YAML string to parse
            
        Returns:
            Parsed submission dictionary
            
        Raises:
            FRANKFormatError: If YAML parsing fails
        """
        try:
            return yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            raise FRANKFormatError(f"Invalid YAML format: {e}")
    
    def to_json(self, submission: Dict[str, Any]) -> str:
        """
        Convert submission to JSON format for API transmission.
        
        Args:
            submission: Submission dictionary
            
        Returns:
            JSON string representation
        """
        try:
            return json.dumps(submission, indent=2, default=str)
        except Exception as e:
            raise FRANKFormatError(f"Failed to convert to JSON: {e}")
    
    def from_json(self, json_str: str) -> Dict[str, Any]:
        """
        Parse submission from JSON format with error handling.
        
        Args:
            json_str: JSON string to parse
            
        Returns:
            Parsed submission dictionary
            
        Raises:
            FRANKFormatError: If JSON parsing fails
        """
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise FRANKFormatError(f"Invalid JSON format: {e}")
    
    def normalize_submission(self, submission: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a submission to ensure consistent structure and fill in defaults.
        
        Args:
            submission: Raw submission dictionary
            
        Returns:
            Normalized submission with consistent structure
        """
        # Validate first
        is_valid, issues = self.validate_submission(submission)
        if not is_valid:
            raise FRANKValidationError(f"Cannot normalize invalid submission: {issues}")
        
        # Create normalized copy
        normalized = self._deep_copy(submission)
        
        # Ensure all default fields are present
        sighting = normalized['submission']['sighting']
        sighting.setdefault('confidence', self.DEFAULTS['confidence'])
        sighting.setdefault('severity', self.DEFAULTS['severity'])
        sighting.setdefault('observation_count', self.DEFAULTS['observation_count'])
        
        # Normalize timestamps
        if 'timestamp' in sighting:
            try:
                # Ensure ISO format
                dt = datetime.fromisoformat(sighting['timestamp'].replace('Z', '+00:00'))
                sighting['timestamp'] = dt.isoformat()
            except:
                sighting['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # Add metadata if missing
        normalized['submission'].setdefault('metadata', {})
        metadata = normalized['submission']['metadata']
        metadata.setdefault('format_version', self.DEFAULTS['format_version'])
        metadata.setdefault('submission_id', f"submission-{uuid.uuid4()}")
        
        # Normalize observables
        observables = normalized['submission']['sighting'].get('observables', {})
        for category, obs_list in observables.items():
            if isinstance(obs_list, list):
                for obs in obs_list:
                    if 'id' not in obs:
                        obs['id'] = f"{obs.get('type', 'unknown')}-{uuid.uuid4()}"
        
        self.logger.info("Normalized submission structure")
        return normalized


# Factory function for easy instantiation
def create_frank_submission() -> FRANKSubmission:
    """
    Factory function to create a FRANKSubmission instance.
    
    Returns:
        Configured FRANKSubmission instance
    """
    return FRANKSubmission()


# Convenience functions for common operations
def generate_minimal(org_id: str = None, **kwargs) -> Dict[str, Any]:
    """Generate a minimal submission quickly."""
    frank = create_frank_submission()
    return frank.generate_minimal_submission(org_id=org_id, **kwargs)


def validate_submission(submission: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a submission quickly."""
    frank = create_frank_submission()
    return frank.validate_submission(submission)


def to_yaml(submission: Dict[str, Any]) -> str:
    """Convert submission to YAML quickly."""
    frank = create_frank_submission()
    return frank.to_yaml(submission)


def from_yaml(yaml_str: str) -> Dict[str, Any]:
    """Parse submission from YAML quickly."""
    frank = create_frank_submission()
    return frank.from_yaml(yaml_str)


def to_json(submission: Dict[str, Any]) -> str:
    """Convert submission to JSON quickly."""
    frank = create_frank_submission()
    return frank.to_json(submission)


def from_json(json_str: str) -> Dict[str, Any]:
    """Parse submission from JSON quickly."""
    frank = create_frank_submission()
    return frank.from_json(json_str)


