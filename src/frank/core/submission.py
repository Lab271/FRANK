#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides core functionality for generating, parsing, serializing and validating
FRANK threat intelligence submissions following the "be forgiving on what you 
receive and strong on what you return" principle.
"""

import yaml
import json
from typing import Dict, Any, List, Tuple, Optional
import logging
from dataclasses import dataclass, field

from .exceptions import FRANKFormatError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _safe_get(obj:Any, key:str, default: Any=None) -> Any:
    """Get value from dict if it's a dict, otherwise return None."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default

def _check_nested_field(data: Dict, field_path: str) -> bool:
    """Check if a nested field exists using dot notation."""
    return _get_nested_field(data, field_path) is not None

def _get_nested_field(data: Dict, field_path: str) -> Any:
    """Get value from nested field using dot notation."""
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
    

@dataclass
class FRANKSubmission:
    """
    Pure dataclass container for FRANK threat intelligence submissions.
    
    Represents the structure and data of a submission without business logic.
    Core data must be set deliberately. Don't like empty strings
    """
    
    # Core submission data
    submitter_org_id: Optional[str] = None
    submitter_tier: Optional[str] = None
    sighting_id: Optional[str] = None
    timestamp: Optional[str] = None
    observables: Optional[Dict[str, List[Dict[str, Any]]]] = None
    confidence: int = 69
    
    # Optional metadata
    metadata: Optional[Dict[str, Any]] = None
    hit_target: Optional[Dict[str, Any]] = None
    severity: Optional[str] = None
    first_observed: Optional[str] = None
    last_observed: Optional[str] = None
    observation_count: Optional[int] = None
    sigma_detection: Optional[Dict[str, Any]] = None
    threat_context: Optional[Dict[str, Any]] = None
    impact: Optional[Dict[str, Any]] = None
    sharing: Optional[Dict[str, Any]] = None
    
    # Additional fields can be stored here
    extra_fields: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FRANKSubmission':
        """Create FRANKSubmission from dictionary."""
        submission_data = _safe_get(data, 'submission')
        submitter = _safe_get(submission_data, 'submitter')
        sighting = _safe_get(submission_data, 'sighting')
        
        return cls(
            submitter_org_id=_safe_get(submitter, 'organization_id'),
            submitter_tier=_safe_get(submitter, 'tier'),
            sighting_id=_safe_get(sighting, 'sighting_id'),
            timestamp=_safe_get(sighting, 'timestamp'),
            observables=_safe_get(sighting, 'observables'),
            confidence=_safe_get(sighting, 'confidence', 69),
            metadata=_safe_get(submission_data, 'metadata'),
            hit_target=_safe_get(submission_data, 'hit_target'),
            severity=_safe_get(sighting, 'severity'),
            first_observed=_safe_get(sighting, 'first_observed'),
            last_observed=_safe_get(sighting, 'last_observed'),
            observation_count=_safe_get(sighting, 'observation_count'),
            sigma_detection=_safe_get(sighting, 'sigma_detection'),
            threat_context=_safe_get(sighting, 'threat_context'),
            impact=_safe_get(sighting, 'impact'),
            sharing=_safe_get(submission_data, 'sharing'),
            extra_fields=_safe_get(data, 'extra_fields')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert FRANKSubmission to dictionary format."""
        submission = {}
        
        submitter = {}
        if self.submitter_tier:
            submitter['tier'] = self.submitter_tier
        if self.submitter_org_id:
            submitter['organization_id'] = self.submitter_org_id   

        # Add optional fields if they exist
        if self.metadata:
            submission["metadata"] = self.metadata
        if self.hit_target:
            submission["hit_target"] = self.hit_target
        if self.sharing:
            submission["sharing"] = self.sharing

        if submitter:
            submission['submitter'] = submitter

        
        sighting = {}

        if self.sighting_id:
            sighting["sighting_id"] = self.sighting_id
        if self.timestamp:
            sighting["timestamp"] = self.timestamp
        if self.timestamp:
            sighting["observables"] = self.observables
        if self.severity:
            sighting["severity"] = self.severity
        if self.first_observed:
            sighting["first_observed"] = self.first_observed
        if self.last_observed:
            sighting["last_observed"] = self.last_observed
        if self.observation_count:
            sighting["observation_count"] = self.observation_count
        if self.sigma_detection:
            sighting["sigma_detection"] = self.sigma_detection
        if self.threat_context:
            sighting["threat_context"] = self.threat_context
        if self.impact:
            sighting["impact"] = self.impact
        if sighting:
            sighting["confidence"] = self.confidence

        if sighting:    
            submission["sighting"] = sighting

        # Add any extra fields
        if self.extra_fields:
            submission.update(self.extra_fields)
            
        return {'submission': submission}


class FRANKValidator:
    """
    Handles validation of FRANK submissions following "be forgiving" principle.
    
    Separated validation logic from data representation.
    """
    
    # Constants moved here from original class
    REQUIRED_FIELDS = {
        'submission.submitter.organization_id',
        'submission.submitter.tier', 
        'submission.sighting.sighting_id',
        'submission.sighting.timestamp',
        'submission.sighting.observables'
    }
    
    VALID_TIERS = {'public', 'observer', 'contributor', 'partner', 'core_member'}
    VALID_SEVERITIES = {'low', 'medium', 'high', 'critical'}
    VALID_TLP_LEVELS = {'RED', 'AMBER+', 'AMBER', 'GREEN', 'CLEAR'}
    VALID_OBSERVABLE_TYPES = {'ipv4', 'ipv6', 'domain', 'url', 'file_hash', 'email', 'registry_key'}
    
    def validate_submission(self, submission: FRANKSubmission) -> Tuple[bool, List[str]]:
        """Validate a FRANKSubmission instance."""
        return self.validate_dict(submission.to_dict())
    
    def validate_dict(self, submission_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate submission dictionary following "be forgiving" principle."""
        issues = []
        
        try:
            # Check required fields
            for field_path in self.REQUIRED_FIELDS:
                if not _check_nested_field(submission_dict, field_path):
                    issues.append(f"Missing required field: {field_path}")
            
            # Validate tier
            tier = _get_nested_field(submission_dict, 'submission.submitter.tier')
            if tier and tier not in self.VALID_TIERS:
                issues.append(f"Invalid tier '{tier}'. Must be one of: {self.VALID_TIERS}")
            
            # Validate severity
            severity = _get_nested_field(submission_dict, 'submission.sighting.severity')
            if severity and severity not in self.VALID_SEVERITIES:
                issues.append(f"Invalid severity '{severity}'. Must be one of: {self.VALID_SEVERITIES}")
            
            # Validate observables
            observables = _get_nested_field(submission_dict, 'submission.sighting.observables')
            if observables:
                issues.extend(self._validate_observables(observables))
            
            # Validate confidence range
            confidence = _get_nested_field(submission_dict, 'submission.sighting.confidence')
            if confidence is not None and not (0 <= confidence <= 100):
                issues.append(f"Confidence {confidence} out of range [0-100]")
            
            # Validate TLP level
            tlp_level = _get_nested_field(submission_dict, 'submission.sharing.distribution_level')
            if tlp_level and tlp_level not in self.VALID_TLP_LEVELS:
                issues.append(f"Invalid TLP level '{tlp_level}'. Must be one of: {self.VALID_TLP_LEVELS}")
                
        except Exception as e:
            issues.append(f"Error during validation: {str(e)}")
        
        is_valid = len(issues) == 0
        level = "PASSED" if is_valid else "FAILED"
        logger.info(f"Validation result: {level} with {len(issues)} issues")
        
        return is_valid, issues
    
    def _validate_observables(self, observables: Dict) -> List[str]:
        """Validate observables structure."""
        issues = []
        
        if not any(observables.values()):
            issues.append("Observables section present but empty")
            return issues
        
        for category, obs_list in observables.items():
            if isinstance(obs_list, list):
                for i, obs in enumerate(obs_list):
                    if 'type' in obs and obs['type'] not in self.VALID_OBSERVABLE_TYPES:
                        issues.append(f"Invalid observable type '{obs['type']}' in {category}[{i}]")
                    if 'value' not in obs:
                        issues.append(f"Missing 'value' in observable {category}[{i}]")
        
        return issues
    




# Factory functions for easy instantiation
def create_validator() -> FRANKValidator:
    """Factory function to create a FRANKValidator."""
    return FRANKValidator()


# Support functions
def validate_submission(submission : FRANKSubmission) -> Tuple[bool, List[str]]:
    """Validate a submission quickly."""
    validator = create_validator()
    return validator.validate_submission(submission)

def validate_submission_dict(submission_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a submission quickly."""
    validator = create_validator()
    return validator.validate_dict(submission_dict)


def to_yaml(submission: FRANKSubmission) -> str:
    """Convert submission to YAML format."""
    try:
        return yaml.dump(submission.to_dict(), default_flow_style=False, sort_keys=False)
    except Exception as e:
        raise FRANKFormatError(f"Failed to convert to YAML: {e}")

def from_yaml(yaml_str: str) -> FRANKSubmission:
    """Parse submission from YAML format."""
    try:
        data = yaml.safe_load(yaml_str)
        return FRANKSubmission.from_dict(data)
    except yaml.YAMLError as e:
        raise FRANKFormatError(f"Invalid YAML format: {e}")

def to_json(submission: FRANKSubmission) -> str:
    """Convert submission to JSON format."""
    try:
        return json.dumps(submission.to_dict(), indent=2, default=str)
    except Exception as e:
        raise FRANKFormatError(f"Failed to convert to JSON: {e}")

def from_json(json_str: str) -> FRANKSubmission:
    """Parse submission from JSON format."""
    try:
        data = json.loads(json_str)
        return FRANKSubmission.from_dict(data)
    except json.JSONDecodeError as e:
        raise FRANKFormatError(f"Invalid JSON format: {e}")
