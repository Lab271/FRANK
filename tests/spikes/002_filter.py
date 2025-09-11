#!/usr/bin/env python3
"""
FRANK Platform - Access-Based Filtering Architecture
Defines filtering rules and software architecture for tier-based data access control.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import hashlib
import re


class AccessTier(Enum):
    PUBLIC = "public"
    OBSERVER = "observer"
    CONTRIBUTOR = "contributor"
    PARTNER = "partner"
    CORE_MEMBER = "core_member"


class FilterAction(Enum):
    ALLOW = "allow"           # Pass through unchanged
    REMOVE = "remove"         # Remove field entirely
    HASH = "hash"            # Replace with hash
    MASK = "mask"            # Partial masking (e.g., IP obfuscation)
    AGGREGATE = "aggregate"   # Replace with statistical summary
    GENERALIZE = "generalize" # Replace with broader category


@dataclass
class FilterRule:
    """Defines how to filter a specific field based on access tier."""
    field_path: str
    access_tier: AccessTier
    action: FilterAction
    parameters: Optional[Dict[str, Any]] = None


class FieldFilter:
    """Handles individual field filtering operations."""
    
    @staticmethod
    def hash_value(value: Any, salt: str = "frank_platform") -> str:
        """Generate deterministic hash for anonymization."""
        combined = f"{value}_{salt}"
        return f"hash_{hashlib.sha256(combined.encode()).hexdigest()[:8]}"
    
    @staticmethod
    def mask_ip(ip: str, mask_level: int = 2) -> str:
        """Mask IP address based on level (1=last octet, 2=last two octets)."""
        parts = ip.split('.')
        if len(parts) != 4:
            return "invalid_ip"
        
        if mask_level == 1:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.x"
        elif mask_level == 2:
            return f"{parts[0]}.{parts[1]}.x.x"
        else:
            return "x.x.x.x"
    
    @staticmethod
    def generalize_sector(sector: str) -> str:
        """Generalize specific sectors to broader categories."""
        financial_sectors = ["banking", "insurance", "fintech", "payment_processing"]
        if any(fin in sector.lower() for fin in financial_sectors):
            return "financial_services"
        elif "health" in sector.lower():
            return "healthcare"
        elif "government" in sector.lower():
            return "public_sector"
        else:
            return "private_sector"
    
    @staticmethod
    def generalize_region(region: str) -> str:
        """Generalize specific regions to broader areas."""
        if region.startswith("nl_"):
            return "netherlands"
        elif region.startswith("de_"):
            return "germany"
        elif region.startswith("be_"):
            return "belgium"
        else:
            return "europe"


class AccessControlFilter:
    """Main filtering engine that applies access control rules."""
    
    def __init__(self):
        self.rules = self._define_filtering_rules()
    
    def _define_filtering_rules(self) -> Dict[AccessTier, List[FilterRule]]:
        """Define comprehensive filtering rules for each access tier."""
        return {
            AccessTier.PUBLIC: [
                # Remove all organizational identifiers
                FilterRule("submission.metadata.submitter.organization_id", AccessTier.PUBLIC, FilterAction.REMOVE),
                FilterRule("submission.metadata.hit_target.organization_id", AccessTier.PUBLIC, FilterAction.REMOVE),
                FilterRule("submission.metadata.hit_target.customer_relationship", AccessTier.PUBLIC, FilterAction.REMOVE),
                
                # Hash all observables
                FilterRule("submission.sighting.observables.network.*.value", AccessTier.PUBLIC, FilterAction.HASH),
                FilterRule("submission.sighting.observables.files.*.hash_*", AccessTier.PUBLIC, FilterAction.HASH),
                FilterRule("submission.sighting.observables.email.*.sender", AccessTier.PUBLIC, FilterAction.HASH),
                
                # Remove all operational details
                FilterRule("submission.sighting.sigma_detection", AccessTier.PUBLIC, FilterAction.REMOVE),
                FilterRule("submission.sighting.impact", AccessTier.PUBLIC, FilterAction.REMOVE),
                FilterRule("submission.sighting.technical_details", AccessTier.PUBLIC, FilterAction.REMOVE),
                
                # Generalize geographic and sector data
                FilterRule("submission.metadata.submitter.sector", AccessTier.PUBLIC, FilterAction.GENERALIZE),
                FilterRule("submission.metadata.hit_target.sector", AccessTier.PUBLIC, FilterAction.GENERALIZE),
                FilterRule("submission.metadata.submitter.region", AccessTier.PUBLIC, FilterAction.GENERALIZE),
                FilterRule("submission.metadata.hit_target.region", AccessTier.PUBLIC, FilterAction.GENERALIZE),
                
                # Aggregate threat context
                FilterRule("submission.sighting.threat_context.campaign.name", AccessTier.PUBLIC, FilterAction.HASH),
                FilterRule("submission.sighting.threat_context.malware_family.name", AccessTier.PUBLIC, FilterAction.GENERALIZE),
            ],
            
            AccessTier.OBSERVER: [
                # Remove organizational identifiers but keep anonymized references
                FilterRule("submission.metadata.submitter.organization_id", AccessTier.OBSERVER, FilterAction.HASH),
                FilterRule("submission.metadata.hit_target.organization_id", AccessTier.OBSERVER, FilterAction.HASH),
                FilterRule("submission.metadata.hit_target.customer_relationship.msp_provider", AccessTier.OBSERVER, FilterAction.HASH),
                
                # Mask network observables
                FilterRule("submission.sighting.observables.network.*.value", AccessTier.OBSERVER, FilterAction.MASK, {"mask_level": 2}),
                FilterRule("submission.sighting.observables.network.*.resolution_ip", AccessTier.OBSERVER, FilterAction.MASK, {"mask_level": 2}),
                
                # Remove detailed SIGMA rules but keep rule metadata
                FilterRule("submission.sighting.sigma_detection.sigma_yaml", AccessTier.OBSERVER, FilterAction.REMOVE),
                FilterRule("submission.sighting.sigma_detection.detection_engine", AccessTier.OBSERVER, FilterAction.REMOVE),
                
                # Remove sensitive impact details
                FilterRule("submission.sighting.impact.financial_impact_eur", AccessTier.OBSERVER, FilterAction.REMOVE),
                FilterRule("submission.sighting.impact.mitigation_actions", AccessTier.OBSERVER, FilterAction.REMOVE),
                
                # Remove detailed technical information
                FilterRule("submission.sighting.technical_details.infrastructure", AccessTier.OBSERVER, FilterAction.REMOVE),
                FilterRule("submission.sighting.technical_details.evasion_techniques", AccessTier.OBSERVER, FilterAction.REMOVE),
            ],
            
            AccessTier.CONTRIBUTOR: [
                # Keep anonymized organizational identifiers
                FilterRule("submission.metadata.submitter.organization_id", AccessTier.CONTRIBUTOR, FilterAction.HASH),
                FilterRule("submission.metadata.hit_target.organization_id", AccessTier.CONTRIBUTOR, FilterAction.HASH),
                FilterRule("submission.metadata.hit_target.customer_relationship.msp_provider", AccessTier.CONTRIBUTOR, FilterAction.HASH),
                
                # Partial masking of network observables
                FilterRule("submission.sighting.observables.network.*.value", AccessTier.CONTRIBUTOR, FilterAction.MASK, {"mask_level": 1}),
                
                # Allow SIGMA rule metadata but not full YAML
                FilterRule("submission.sighting.sigma_detection.sigma_yaml", AccessTier.CONTRIBUTOR, FilterAction.REMOVE),
                
                # Generalize sensitive impact information
                FilterRule("submission.sighting.impact.financial_impact_eur", AccessTier.CONTRIBUTOR, FilterAction.AGGREGATE, {"ranges": ["<10k", "10k-50k", "50k+"]}),
                FilterRule("submission.sighting.impact.mitigation_actions.*.timestamp", AccessTier.CONTRIBUTOR, FilterAction.REMOVE),
                
                # Remove infrastructure details
                FilterRule("submission.sighting.technical_details.infrastructure.hosting_provider", AccessTier.CONTRIBUTOR, FilterAction.GENERALIZE),
                FilterRule("submission.sighting.technical_details.infrastructure.geographic_location", AccessTier.CONTRIBUTOR, FilterAction.GENERALIZE),
            ],
            
            AccessTier.PARTNER: [
                # Allow most data with minimal filtering
                FilterRule("submission.metadata.submitter.organization_id", AccessTier.PARTNER, FilterAction.HASH),
                FilterRule("submission.metadata.hit_target.organization_id", AccessTier.PARTNER, FilterAction.HASH),
                
                # Allow full observables
                FilterRule("submission.sighting.observables", AccessTier.PARTNER, FilterAction.ALLOW),
                
                # Allow SIGMA rules and technical details
                FilterRule("submission.sighting.sigma_detection", AccessTier.PARTNER, FilterAction.ALLOW),
                FilterRule("submission.sighting.technical_details", AccessTier.PARTNER, FilterAction.ALLOW),
                FilterRule("submission.sighting.impact", AccessTier.PARTNER, FilterAction.ALLOW),
            ],
            
            AccessTier.CORE_MEMBER: [
                # Allow everything - no filtering
                FilterRule("*", AccessTier.CORE_MEMBER, FilterAction.ALLOW),
            ]
        }
    
    def apply_filters(self, data: Dict[str, Any], access_tier: AccessTier) -> Dict[str, Any]:
        """Apply access control filters to submission data."""
        filtered_data = self._deep_copy(data)
        rules = self.rules.get(access_tier, [])
        
        for rule in rules:
            self._apply_single_rule(filtered_data, rule)
        
        return filtered_data
    
    def _apply_single_rule(self, data: Dict[str, Any], rule: FilterRule) -> None:
        """Apply a single filtering rule to the data."""
        if rule.field_path == "*":
            return  # Allow all - no filtering
        
        paths = self._resolve_field_paths(data, rule.field_path)
        
        for path in paths:
            value = self._get_nested_value(data, path)
            if value is None:
                continue
            
            if rule.action == FilterAction.REMOVE:
                self._remove_nested_value(data, path)
            elif rule.action == FilterAction.HASH:
                hashed_value = FieldFilter.hash_value(value)
                self._set_nested_value(data, path, hashed_value)
            elif rule.action == FilterAction.MASK:
                if "mask_level" in (rule.parameters or {}):
                    masked_value = FieldFilter.mask_ip(str(value), rule.parameters["mask_level"])
                    self._set_nested_value(data, path, masked_value)
            elif rule.action == FilterAction.GENERALIZE:
                if "sector" in path:
                    generalized = FieldFilter.generalize_sector(str(value))
                elif "region" in path:
                    generalized = FieldFilter.generalize_region(str(value))
                else:
                    generalized = "generalized"
                self._set_nested_value(data, path, generalized)
            elif rule.action == FilterAction.AGGREGATE:
                if rule.parameters and "ranges" in rule.parameters:
                    aggregated = self._aggregate_financial_impact(value, rule.parameters["ranges"])
                    self._set_nested_value(data, path, aggregated)
    
    def _resolve_field_paths(self, data: Dict[str, Any], pattern: str) -> List[str]:
        """Resolve wildcard patterns in field paths to actual paths."""
        if "*" not in pattern:
            return [pattern]
        
        # Handle wildcards in field paths
        # This is a simplified implementation - production code would need more robust pattern matching
        paths = []
        if ".*.value" in pattern:
            # Handle network observables array
            base_path = pattern.split(".*.value")[0]
            if "network" in base_path:
                network_items = self._get_nested_value(data, base_path.replace(".*", ""))
                if isinstance(network_items, list):
                    for i, item in enumerate(network_items):
                        if "value" in item:
                            actual_path = base_path.replace(".*", f".{i}") + ".value"
                            paths.append(actual_path)
        
        return paths if paths else [pattern]
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        try:
            for key in keys:
                if isinstance(current, list):
                    current = current[int(key)]
                else:
                    current = current[key]
            return current
        except (KeyError, IndexError, ValueError, TypeError):
            return None
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set value in nested dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        try:
            for key in keys[:-1]:
                if isinstance(current, list):
                    current = current[int(key)]
                else:
                    current = current[key]
            
            final_key = keys[-1]
            if isinstance(current, list):
                current[int(final_key)] = value
            else:
                current[final_key] = value
        except (KeyError, IndexError, ValueError, TypeError):
            pass  # Silently fail if path doesn't exist
    
    def _remove_nested_value(self, data: Dict[str, Any], path: str) -> None:
        """Remove value from nested dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        try:
            for key in keys[:-1]:
                if isinstance(current, list):
                    current = current[int(key)]
                else:
                    current = current[key]
            
            final_key = keys[-1]
            if isinstance(current, list):
                # Don't remove from list to maintain indices
                current[int(final_key)] = None
            else:
                del current[final_key]
        except (KeyError, IndexError, ValueError, TypeError):
            pass  # Silently fail if path doesn't exist
    
    def _aggregate_financial_impact(self, value: float, ranges: List[str]) -> str:
        """Aggregate financial impact into predefined ranges."""
        if value < 10000:
            return ranges[0] if len(ranges) > 0 else "<10k"
        elif value < 50000:
            return ranges[1] if len(ranges) > 1 else "10k-50k"
        else:
            return ranges[2] if len(ranges) > 2 else "50k+"
    
    def _deep_copy(self, obj: Any) -> Any:
        """Create deep copy of object."""
        import copy
        return copy.deepcopy(obj)


class FrankQueryEngine:
    """High-level query engine that applies access control filtering."""
    
    def __init__(self):
        self.filter_engine = AccessControlFilter()
    
    def query_sightings(
        self, 
        user_access_tier: AccessTier,
        filters: Dict[str, Any] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query sightings with access control filtering applied."""
        
        # Step 1: Query raw data (implementation would connect to actual database)
        raw_sightings = self._fetch_raw_sightings(filters, limit)
        
        # Step 2: Apply access control filtering
        filtered_sightings = []
        for sighting in raw_sightings:
            filtered_sighting = self.filter_engine.apply_filters(sighting, user_access_tier)
            filtered_sightings.append(filtered_sighting)
        
        return filtered_sightings
    
    def _fetch_raw_sightings(self, filters: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Fetch raw sightings from storage (placeholder implementation)."""
        # This would connect to your actual database/storage system
        # For now, return empty list
        return []


# Example usage and testing
if __name__ == "__main__":
    # Sample sighting data (simplified)
    sample_sighting = {
        "submission": {
            "metadata": {
                "submitter": {
                    "organization_id": "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff",
                    "tier": "partner",
                    "sector": "financial_banking",
                    "region": "nl_amsterdam"
                },
                "hit_target": {
                    "organization_id": "identity-c9b5d123-8877-4422-9966-112233445566",
                    "sector": "financial_services",
                    "region": "nl_north_holland",
                    "customer_relationship": {
                        "msp_provider": "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff"
                    }
                }
            },
            "sighting": {
                "observables": {
                    "network": [
                        {"value": "185.220.102.45", "type": "ipv4"},
                        {"value": "secure-bank-verify.nl", "type": "domain"}
                    ]
                },
                "impact": {
                    "financial_impact_eur": 25000
                }
            }
        }
    }
    
    # Test filtering for different access tiers
    filter_engine = AccessControlFilter()
    
    print("=== Original Data ===")
    print(f"Submitter ID: {sample_sighting['submission']['metadata']['submitter']['organization_id']}")
    print(f"Network Observable: {sample_sighting['submission']['sighting']['observables']['network'][0]['value']}")
    print(f"Financial Impact: {sample_sighting['submission']['sighting']['impact']['financial_impact_eur']}")
    
    print("\n=== Public Access ===")
    public_filtered = filter_engine.apply_filters(sample_sighting, AccessTier.PUBLIC)
    print(f"Submitter ID: {public_filtered['submission']['metadata']['submitter'].get('organization_id', 'REMOVED')}")
    print(f"Sector: {public_filtered['submission']['metadata']['submitter'].get('sector', 'REMOVED')}")
    
    print("\n=== Observer Access ===")
    observer_filtered = filter_engine.apply_filters(sample_sighting, AccessTier.OBSERVER)
    print(f"Submitter ID: {observer_filtered['submission']['metadata']['submitter'].get('organization_id', 'REMOVED')}")
    
    print("\n=== Partner Access ===")
    partner_filtered = filter_engine.apply_filters(sample_sighting, AccessTier.PARTNER)
    print(f"Financial Impact: {partner_filtered['submission']['sighting']['impact'].get('financial_impact_eur', 'REMOVED')}")