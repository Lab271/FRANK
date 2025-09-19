#!/usr/bin/env python3
"""
FRANK Platform - Local Development Version with SQLite
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This script demonstrates generating and parsing minimal threat intelligence submissions
with SQLite database storage following the "be forgiving on what you receive and 
strong on what you return" principle and dedicated models not from the system.
Created before included in the overall FRANK library for clarity.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import yaml
import json
import uuid
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FRANKDatabase:
    """
    SQLite database handler for FRANK platform following DynamoDB-like patterns
    but adapted for local development with relational structure.
    """
    
    def __init__(self, db_path: str = "/tmp/frank_local.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(self.__class__.__name__)
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database with FRANK schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                # organisations table (cyber partners and customers)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS organisations (
                        organisation_id TEXT PRIMARY KEY,
                        organisation_type TEXT NOT NULL CHECK (organisation_type IN ('cyber_partner', 'customer')),
                        tier TEXT CHECK (tier IN ('public', 'observer', 'contributor', 'partner', 'core_member')),
                        sector TEXT,
                        region TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP,
                        contribution_score INTEGER DEFAULT 0,
                        client_count INTEGER DEFAULT 0
                    )
                """)
                
                # Submissions table (main submission data)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS submissions (
                        submission_id TEXT PRIMARY KEY,
                        submitter_org_id TEXT NOT NULL,
                        hit_target_org_id TEXT,
                        format_version TEXT DEFAULT '1.0',
                        submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        confidence INTEGER CHECK (confidence >= 0 AND confidence <= 100),
                        severity TEXT CHECK (severity IN ('low', 'medium', 'high', 'critical')),
                        tlp_level TEXT CHECK (tlp_level IN ('RED', 'AMBER+', 'AMBER', 'GREEN', 'CLEAR')),
                        full_submission_json TEXT NOT NULL,
                        FOREIGN KEY (submitter_org_id) REFERENCES organisations (organisation_id),
                        FOREIGN KEY (hit_target_org_id) REFERENCES organisations (organisation_id)
                    )
                """)
                
                # Sightings table (individual threat sightings)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sightings (
                        sighting_id TEXT PRIMARY KEY,
                        submission_id TEXT NOT NULL,
                        first_observed TIMESTAMP,
                        last_observed TIMESTAMP,
                        observation_count INTEGER DEFAULT 1,
                        confidence INTEGER,
                        severity TEXT,
                        FOREIGN KEY (submission_id) REFERENCES submissions (submission_id) ON DELETE CASCADE
                    )
                """)
                
                # Observables table (IoCs and artifacts)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS observables (
                        observable_id TEXT PRIMARY KEY,
                        sighting_id TEXT NOT NULL,
                        observable_type TEXT NOT NULL CHECK (observable_type IN ('ipv4', 'ipv6', 'domain', 'url', 'file_hash', 'email', 'registry_key')),
                        observable_value TEXT NOT NULL,
                        observable_hash TEXT, -- for quick lookups and deduplication
                        role TEXT,
                        port INTEGER,
                        protocol TEXT,
                        first_seen TIMESTAMP,
                        FOREIGN KEY (sighting_id) REFERENCES sightings (sighting_id) ON DELETE CASCADE
                    )
                """)
                
                # Statistics table (aggregated sighting data)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS observable_statistics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        observable_hash TEXT NOT NULL,
                        observable_type TEXT NOT NULL,
                        observable_value TEXT NOT NULL,
                        total_sightings INTEGER DEFAULT 1,
                        unique_organisations INTEGER DEFAULT 1,
                        first_seen TIMESTAMP,
                        last_seen TIMESTAMP,
                        avg_confidence REAL,
                        sectors_json TEXT, -- JSON array of affected sectors
                        regions_json TEXT, -- JSON array of affected regions
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Access logs for auditing
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS access_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        organisation_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        resource_type TEXT,
                        resource_id TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        access_level TEXT,
                        success BOOLEAN DEFAULT TRUE
                    )
                """)
                
                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_submitter ON submissions (submitter_org_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_timestamp ON submissions (submission_timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_observables_hash ON observables (observable_hash)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_observables_type ON observables (observable_type)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_statistics_hash ON observable_statistics (observable_hash)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_org ON access_logs (organisation_id)")
                
                conn.commit()
                self.logger.info(f"Database initialized at {self.db_path}")
                
        except sqlite3.Error as e:
            self.logger.error(f"Database initialization error: {e}")
            raise
    
    def hash_observable(self, observable_type: str, observable_value: str) -> str:
        """Create a hash for observable deduplication and quick lookups."""
        combined = f"{observable_type}:{observable_value}".lower()
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def store_submission(self, submission: Dict[str, Any]) -> bool:
        """
        Store a complete submission in the database with full normalization.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Extract main submission data
                sub_data = submission['submission']
                submitter = sub_data['submitter']
                sighting = sub_data['sighting']
                
                submission_id = sub_data.get('metadata', {}).get('submission_id', f"submission-{uuid.uuid4()}")
                
                # Store or update organisation
                self._upsert_organisation(conn, submitter)
                
                # Store hit target if present
                hit_target = sub_data.get('hit_target')
                if hit_target:
                    self._upsert_organisation(conn, hit_target, org_type='customer')
                
                # Store main submission
                conn.execute("""
                    INSERT OR REPLACE INTO submissions 
                    (submission_id, submitter_org_id, hit_target_org_id, format_version, 
                     submission_timestamp, confidence, severity, tlp_level, full_submission_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    submission_id,
                    submitter['organisation_id'],
                    hit_target['organisation_id'] if hit_target else None,
                    sub_data.get('metadata', {}).get('format_version', '1.0'),
                    datetime.now(timezone.utc).isoformat(),
                    sighting.get('confidence'),
                    sighting.get('severity'),
                    sub_data.get('sharing', {}).get('distribution_level'),
                    json.dumps(submission)
                ))
                
                # Store sighting
                conn.execute("""
                    INSERT OR REPLACE INTO sightings 
                    (sighting_id, submission_id, first_observed, last_observed, 
                     observation_count, confidence, severity)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    sighting['sighting_id'],
                    submission_id,
                    sighting.get('first_observed'),
                    sighting.get('last_observed'),
                    sighting.get('observation_count', 1),
                    sighting.get('confidence'),
                    sighting.get('severity')
                ))
                
                # Store observables
                observables = sighting.get('observables', {})
                for obs_category, obs_list in observables.items():
                    if isinstance(obs_list, list):
                        for obs in obs_list:
                            obs_hash = self.hash_observable(obs['type'], obs['value'])
                            
                            conn.execute("""
                                INSERT OR REPLACE INTO observables 
                                (observable_id, sighting_id, observable_type, observable_value, 
                                 observable_hash, role, port, protocol, first_seen)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                obs.get('id', f"obs-{uuid.uuid4()}"),
                                sighting['sighting_id'],
                                obs['type'],
                                obs['value'],
                                obs_hash,
                                obs.get('role'),
                                obs.get('port'),
                                obs.get('protocol'),
                                obs.get('first_seen')
                            ))
                            
                            # Update statistics
                            self._update_observable_statistics(conn, obs, submitter)
                
                # Log access
                self._log_access(conn, submitter['organisation_id'], 'SUBMIT', 'submission', submission_id)
                
                conn.commit()
                self.logger.info(f"Stored submission {submission_id}")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Error storing submission: {e}")
            return False
    
    def _upsert_organisation(self, conn: sqlite3.Connection, org_data: Dict[str, Any], org_type: str = 'cyber_partner'):
        """Insert or update organisation information."""
        conn.execute("""
            INSERT OR REPLACE INTO organisations 
            (organisation_id, organisation_type, tier, sector, region, last_active, client_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            org_data['organisation_id'],
            org_data.get('organisation_type', org_type),
            org_data.get('access_level'),
            org_data.get('sector'),
            org_data.get('region'),
            datetime.now(timezone.utc).isoformat(),
            org_data.get('client_count', 0)
        ))
    
    def _update_observable_statistics(self, conn: sqlite3.Connection, observable: Dict[str, Any], submitter: Dict[str, Any]):
        """Update aggregated statistics for observables."""
        obs_hash = self.hash_observable(observable['type'], observable['value'])
        
        # Check if statistics record exists
        cursor = conn.execute("""
            SELECT total_sightings, unique_organisations, sectors_json, regions_json, avg_confidence 
            FROM observable_statistics WHERE observable_hash = ?
        """, (obs_hash,))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing record
            total_sightings, unique_orgs, sectors_json, regions_json, avg_confidence = existing
            
            # Parse existing JSON data
            sectors = json.loads(sectors_json) if sectors_json else []
            regions = json.loads(regions_json) if regions_json else []
            
            # Add new sector/region if not present
            if submitter.get('sector') and submitter['sector'] not in sectors:
                sectors.append(submitter['sector'])
            if submitter.get('region') and submitter['region'] not in regions:
                regions.append(submitter['region'])
            
            # Update statistics
            conn.execute("""
                UPDATE observable_statistics 
                SET total_sightings = total_sightings + 1,
                    unique_organisations = ?,
                    last_seen = ?,
                    sectors_json = ?,
                    regions_json = ?,
                    updated_at = ?
                WHERE observable_hash = ?
            """, (
                unique_orgs + 1,  # Simplified - should track unique orgs properly
                datetime.now(timezone.utc).isoformat(),
                json.dumps(sectors),
                json.dumps(regions),
                datetime.now(timezone.utc).isoformat(),
                obs_hash
            ))
        else:
            # Create new statistics record
            sectors = [submitter.get('sector')] if submitter.get('sector') else []
            regions = [submitter.get('region')] if submitter.get('region') else []
            
            conn.execute("""
                INSERT INTO observable_statistics 
                (observable_hash, observable_type, observable_value, total_sightings, 
                 unique_organisations, first_seen, last_seen, sectors_json, regions_json)
                VALUES (?, ?, ?, 1, 1, ?, ?, ?, ?)
            """, (
                obs_hash,
                observable['type'],
                observable['value'],
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
                json.dumps(sectors),
                json.dumps(regions)
            ))
    
    def _log_access(self, conn: sqlite3.Connection, org_id: str, action: str, resource_type: str = None, resource_id: str = None):
        """Log access for auditing purposes."""
        conn.execute("""
            INSERT INTO access_logs (organisation_id, action, resource_type, resource_id)
            VALUES (?, ?, ?, ?)
        """, (org_id, action, resource_type, resource_id))
    
    def query_observables(self, org_id: str, observable_type: str = None, 
                         limit: int = 100, access_level: str = 'contributor') -> List[Dict[str, Any]]:
        """
        Query observables with access level filtering (implements tiered access).
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Build query based on access level
                base_query = """
                    SELECT os.observable_hash, os.observable_type, os.observable_value,
                           os.total_sightings, os.unique_organisations, os.first_seen, os.last_seen
                    FROM observable_statistics os
                """
                
                params = []
                where_clauses = []
                
                if observable_type:
                    where_clauses.append("os.observable_type = ?")
                    params.append(observable_type)
                
                # Apply access level filtering
                if access_level in ['public', 'observer']:
                    # Limited data for lower tiers
                    base_query = base_query.replace("os.observable_value,", "SUBSTR(os.observable_value, 1, 10) || '...' as observable_value,")
                
                if where_clauses:
                    base_query += " WHERE " + " AND ".join(where_clauses)
                
                base_query += f" ORDER BY os.last_seen DESC LIMIT {limit}"
                
                cursor = conn.execute(base_query, params)
                results = [dict(row) for row in cursor.fetchall()]
                
                # Log access
                self._log_access(conn, org_id, 'QUERY', 'observables')
                conn.commit()
                
                self.logger.info(f"Retrieved {len(results)} observables for {org_id} (access: {access_level})")
                return results
                
        except sqlite3.Error as e:
            self.logger.error(f"Error querying observables: {e}")
            return []
    
    def get_submission_by_id(self, submission_id: str, org_id: str, access_level: str = 'contributor') -> Optional[Dict[str, Any]]:
        """Retrieve a specific submission with access level filtering."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute("""
                    SELECT s.*, o.access_level as submitter_tier
                    FROM submissions s
                    JOIN organisations o ON s.submitter_org_id = o.organisation_id
                    WHERE s.submission_id = ?
                """, (submission_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                submission = json.loads(row['full_submission_json'])
                
                # Apply access level filtering
                if access_level in ['public', 'observer']:
                    # Remove sensitive information for lower access levels
                    submission = self._filter_submission_by_access_level(submission, access_level)
                
                # Log access
                self._log_access(conn, org_id, 'READ', 'submission', submission_id)
                conn.commit()
                
                return submission
                
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving submission {submission_id}: {e}")
            return None
    
    def _filter_submission_by_access_level(self, submission: Dict[str, Any], access_level: str) -> Dict[str, Any]:
        """Filter submission data based on access level."""
        if access_level == 'public':
            # Only basic statistics
            return {
                'submission': {
                    'sighting': {
                        'confidence': submission['submission']['sighting'].get('confidence'),
                        'severity': submission['submission']['sighting'].get('severity'),
                        'timestamp': submission['submission']['sighting'].get('timestamp')
                    }
                }
            }
        elif access_level == 'observer':
            # Add some observable types but mask values
            filtered = submission.copy()
            observables = filtered['submission']['sighting'].get('observables', {})
            for category, obs_list in observables.items():
                if isinstance(obs_list, list):
                    for obs in obs_list:
                        if 'value' in obs:
                            obs['value'] = obs['value'][:10] + "..."
            return filtered
        
        return submission  # Full access for contributor and above
    
    def get_statistics_summary(self, org_id: str, days: int = 30) -> Dict[str, Any]:
        """Get platform statistics summary."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Add this line
                cursor = conn.execute("""
                    SELECT 
                        COUNT(DISTINCT submission_id) as total_submissions,
                        COUNT(DISTINCT submitter_org_id) as active_organisations,
                        COUNT(*) as total_observables
                    FROM submissions 
                    WHERE submission_timestamp >= datetime('now', '-{} days')
                """.format(days))
                
                stats = dict(cursor.fetchone())
                
                # Get top observable types
                cursor = conn.execute("""
                    SELECT observable_type, COUNT(*) as count
                    FROM observable_statistics
                    GROUP BY observable_type
                    ORDER BY count DESC
                    LIMIT 5
                """)
                
                stats['top_observable_types'] = dict(cursor.fetchall())
                
                # Log access
                self._log_access(conn, org_id, 'STATS', 'summary')
                conn.commit()
                
                return stats
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}
    
    def cleanup_old_data(self, days: int = 90):
        """Clean up old data according to retention policies."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM submissions 
                    WHERE submission_timestamp < datetime('now', '-{} days')
                """.format(days))
                
                deleted = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Cleaned up {deleted} old submissions")
                return deleted
                
        except sqlite3.Error as e:
            self.logger.error(f"Error during cleanup: {e}")
            return 0


class FRANKSubmission:
    """
    Handles FRANK threat intelligence submissions with minimal required fields
    and graceful handling of optional extended data. Now integrated with SQLite storage.
    """
    
    # Required fields for minimal submission
    REQUIRED_FIELDS = {
        'submission.submitter.organisation_id',
        'submission.submitter.access_level', 
        'submission.sighting.sighting_id',
        'submission.sighting.timestamp',
        'submission.sighting.observables'
    }
    
    # Default values following "be forgiving" principle
    DEFAULTS = {
        'confidence': 69,  # Default confidence as specified
        'format_version': '1.0',
        'submission_method': 'manual',
        'anonymization_level': 'moderate'
    }
    
    def __init__(self, db_path: str = "frank_local.db"):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = FRANKDatabase(db_path)
    
    def generate_minimal_submission(self, 
                                  org_id: str = None,
                                  access_level: str = "partner",
                                  observables: List[Dict] = None) -> Dict[str, Any]:
        """
        Generate a minimal FRANK submission with only required fields.
        Optional parameters allow customization while maintaining minimalism.
        """
        
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
        
        submission = {
            "submission": {
                "submitter": {
                    "organisation_id": org_id,
                    "access_level": tier
                },
                "sighting": {
                    "sighting_id": f"sighting-{uuid.uuid4()}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "confidence": self.DEFAULTS['confidence'],
                    "observables": {
                        "network": observables
                    }
                }
            }
        }
        
        self.logger.info(f"Generated minimal submission for org {org_id}")
        return submission
    
    def submit_to_database(self, submission: Dict[str, Any]) -> bool:
        """
        Validate and store submission in database.
        Returns True if successful, False otherwise.
        """
        # Validate first
        is_valid, issues = self.validate_submission(submission)
        if not is_valid:
            self.logger.error(f"Submission validation failed: {issues}")
            return False
        
        # Store in database
        return self.db.store_submission(submission)
    
    def query_threats(self, org_id: str, access_level: str = "contributor", 
                     observable_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query threat intelligence with access level filtering.
        """
        return self.db.query_observables(org_id, observable_type, limit, tier)
    
    def get_platform_statistics(self, org_id: str, days: int = 30) -> Dict[str, Any]:
        """Get platform statistics summary."""
        return self.db.get_statistics_summary(org_id, days)
    
    def validate_submission(self, submission: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate submission following "be forgiving" principle.
        Returns (is_valid, list_of_issues)
        """
        issues = []
        
        # Check required fields with graceful path traversal
        for field_path in self.REQUIRED_FIELDS:
            if not self._check_nested_field(submission, field_path):
                issues.append(f"Missing required field: {field_path}")
        
        # Validate observables structure if present
        try:
            observables = submission.get('submission', {}).get('sighting', {}).get('observables', {})
            if observables and not any(observables.values()):
                issues.append("Observables section present but empty")
        except Exception as e:
            issues.append(f"Error validating observables: {str(e)}")
        
        # Validate confidence range if present
        try:
            confidence = submission.get('submission', {}).get('sighting', {}).get('confidence')
            if confidence is not None and not (0 <= confidence <= 100):
                issues.append(f"Confidence {confidence} out of range [0-100]")
        except Exception as e:
            issues.append(f"Error validating confidence: {str(e)}")
        
        is_valid = len(issues) == 0
        self.logger.info(f"Validation result: {'PASSED' if is_valid else 'FAILED'} with {len(issues)} issues")
        
        return is_valid, issues
    
    def _check_nested_field(self, data: Dict, field_path: str) -> bool:
        """
        Check if a nested field exists using dot notation.
        Returns True if field exists, False otherwise.
        """
        keys = field_path.split('.')
        current = data
        
        try:
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return False
            return current is not None
        except:
            return False
    
    def enhance_submission(self, minimal_submission: Dict[str, Any], 
                          enhancements: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Enhance a minimal submission with additional data following "strong on return" principle.
        """
        if enhancements is None:
            enhancements = {}
        
        enhanced = minimal_submission.copy()
        
        # Add format version if not present
        if 'format_version' not in enhanced.get('submission', {}):
            enhanced.setdefault('submission', {})['format_version'] = self.DEFAULTS['format_version']
        
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
        sighting.setdefault('severity', 'medium')
        sighting.setdefault('observation_count', 1)
        
        # Apply any custom enhancements
        self._deep_merge(enhanced, enhancements)
        
        self.logger.info("Enhanced submission with additional metadata")
        return enhanced
    
    def _deep_merge(self, base: Dict, overlay: Dict) -> None:
        """
        Deep merge overlay dictionary into base dictionary.
        """
        for key, value in overlay.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def to_yaml(self, submission: Dict[str, Any]) -> str:
        """
        Convert submission to YAML format for storage/transmission.
        """
        return yaml.dump(submission, default_flow_style=False, sort_keys=False)
    
    def from_yaml(self, yaml_str: str) -> Dict[str, Any]:
        """
        Parse submission from YAML format with error handling.
        """
        try:
            return yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            self.logger.error(f"YAML parsing error: {e}")
            raise ValueError(f"Invalid YAML format: {e}")
    
    def to_json(self, submission: Dict[str, Any]) -> str:
        """
        Convert submission to JSON format for API transmission.
        """
        return json.dumps(submission, indent=2, default=str)
    
    def from_json(self, json_str: str) -> Dict[str, Any]:
        """
        Parse submission from JSON format with error handling.
        """
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            raise ValueError(f"Invalid JSON format: {e}")


def run_tests():
    """
    Run comprehensive tests of the FRANK submission system with database integration.
    """
    print("="*70)
    print("FRANK Platform - Local Development Test Suite with SQLite")
    print("="*70)
    
    # Initialize with a test database
    test_db_path = "/tmp/frank_test.db"
    if Path(test_db_path).exists():
        Path(test_db_path).unlink()  # Clean start for tests
    
    frank = FRANKSubmission(test_db_path)
    
    # Test 1: Generate minimal submission
    print("\n1. Testing minimal submission generation...")
    minimal = frank.generate_minimal_submission()
    print("✓ Minimal submission generated")
    
    # Test 2: Validate minimal submission
    print("\n2. Testing submission validation...")
    is_valid, issues = frank.validate_submission(minimal)
    if is_valid:
        print("✓ Minimal submission is valid")
    else:
        print(f"✗ Validation failed: {issues}")
    
    # Test 3: Database storage
    print("\n3. Testing database storage...")
    stored = frank.submit_to_database(minimal)
    if stored:
        print("✓ Submission stored in database")
    else:
        print("✗ Failed to store submission")
    
    # Test 4: Generate and store multiple submissions
    print("\n4. Testing multiple submissions...")
    test_orgs = ["org-alpha", "org-beta", "org-gamma"]
    test_observables = [
        [{"id": "ip-1", "type": "ipv4", "value": "192.168.1.100"}],
        [{"id": "domain-1", "type": "domain", "value": "malicious-site.com"}],
        [{"id": "hash-1", "type": "file_hash", "value": "d41d8cd98f00b204e9800998ecf8427e"}]
    ]
    
    stored_count = 0
    for i, org in enumerate(test_orgs):
        test_submission = frank.generate_minimal_submission(
            org_id=org,
            access_level="partner",
            observables=test_observables[i]
        )
        if frank.submit_to_database(test_submission):
            stored_count += 1
    
    print(f"✓ Stored {stored_count}/{len(test_orgs)} test submissions")
    
    # Test 5: Query threats with different access levels
    print("\n5. Testing threat intelligence queries...")
    
    # Test different access levels
    access_levels = ["public", "observer", "contributor", "partner"]
    for level in access_levels:
        threats = frank.query_threats("org-alpha", access_level=level, limit=10)
        print(f"  {level.capitalize()}: Retrieved {len(threats)} threats")
    
    # Test 6: Platform statistics
    print("\n6. Testing platform statistics...")
    stats = frank.get_platform_statistics("org-alpha")
    if stats:
        print("✓ Platform statistics retrieved:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    else:
        print("✗ Failed to retrieve statistics")
    
    # Test 7: YAML serialization
    print("\n7. Testing YAML serialization...")
    yaml_output = frank.to_yaml(minimal)
    print("✓ YAML serialization successful")
    
    # Test 8: JSON serialization  
    print("\n8. Testing JSON serialization...")
    json_output = frank.to_json(minimal)
    print("✓ JSON serialization successful")
    
    # Test 9: Database query by submission ID
    print("\n9. Testing submission retrieval...")
    submission_id = minimal['submission']['sighting']['sighting_id']
    retrieved = frank.db.get_submission_by_id(submission_id, "org-alpha", "partner")
    if retrieved:
        print("✓ Submission retrieved from database")
    else:
        print("✗ Failed to retrieve submission")
    
    # Test 10: Enhanced submission with database storage
    print("\n10. Testing enhanced submissions...")
    enhanced = frank.enhance_submission(minimal)
    enhanced_stored = frank.submit_to_database(enhanced)
    if enhanced_stored:
        print("✓ Enhanced submission stored")
    else:
        print("✗ Failed to store enhanced submission")
    
    # Test 11: Access level filtering
    print("\n11. Testing access level filtering...")
    public_threats = frank.query_threats("test-org", access_level="public", limit=5)
    partner_threats = frank.query_threats("test-org", access_level="partner", limit=5)
    
    print(f"✓ Public access: {len(public_threats)} threats (filtered)")
    print(f"✓ Partner access: {len(partner_threats)} threats (full access)")
    
    # Test 12: Database performance and statistics
    print("\n12. Testing database performance...")
    
    # Check database file size
    db_size = Path(test_db_path).stat().st_size if Path(test_db_path).exists() else 0
    print(f"✓ Database size: {db_size:,} bytes")
    
    # Count records in each table
    with sqlite3.connect(test_db_path) as conn:
        tables = ['organisations', 'submissions', 'sightings', 'observables', 'observable_statistics', 'access_logs']
        for table in tables:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} records")
    
    # Test 13: Error handling and validation
    print("\n13. Testing error handling...")
    
    # Invalid submission
    invalid_submission = {"invalid": "structure"}
    is_valid, issues = frank.validate_submission(invalid_submission)
    if not is_valid:
        print(f"✓ Invalid submission correctly rejected: {len(issues)} issues")
    
    # Try to store invalid submission
    stored_invalid = frank.submit_to_database(invalid_submission)
    if not stored_invalid:
        print("✓ Invalid submission correctly rejected by database")
    
    # Test 14: Data cleanup
    print("\n14. Testing data cleanup...")
    cleaned = frank.db.cleanup_old_data(days=0)  # Clean everything for test
    print(f"✓ Cleaned {cleaned} old records")
    
    print("\n" + "="*70)
    print("Test Suite Complete - All Database Operations Tested")
    print("="*70)
    
    return {
        'minimal_submission': minimal,
        'enhanced_submission': enhanced,
        'yaml_format': yaml_output,
        'json_format': json_output,
        'database_path': test_db_path,
        'statistics': stats
    }


def run_database_demo():
    """
    Demonstrate FRANK database capabilities with realistic scenarios.
    """
    print("\n" + "="*70)
    print("FRANK Platform - Database Demonstration")
    print("="*70)
    
    frank = FRANKSubmission("/tmp/frank_demo.db")
    
    # Scenario 1: Multiple organisations reporting the same threat
    print("\n📊 Scenario 1: Collaborative Threat Detection")
    print("-" * 50)
    
    shared_threat_ip = "203.0.113.42"
    organisations = [
        {"id": "bank-alpha", "access_level": "partner", "sector": "financial"},
        {"id": "retail-beta", "access_level": "contributor", "sector": "retail"},
        {"id": "tech-gamma", "access_level": "partner", "sector": "technology"}
    ]
    
    # Each org reports the same threat
    for i, org in enumerate(organisations):
        submission = frank.generate_minimal_submission(
            org_id=org["id"],
            access_level=org["access_level"],
            observables=[{
                "id": f"shared-threat-{i}",
                "type": "ipv4",
                "value": shared_threat_ip
            }]
        )
        
        # Add organisation context
        submission["submission"]["submitter"]["sector"] = org["sector"]
        
        stored = frank.submit_to_database(submission)
        print(f"  {org['id']} ({org['sector']}): {'✓' if stored else '✗'} Reported threat {shared_threat_ip}")
    
    # Check aggregated statistics
    stats = frank.get_platform_statistics("bank-alpha")
    print(f"  📈 Platform now has {stats.get('total_submissions', 0)} submissions from {stats.get('active_organisations', 0)} organisations")
    
    # Scenario 2: Access level demonstration
    print("\n🔒 Scenario 2: Tiered Access Control")
    print("-" * 50)
    
    access_levels = [
        ("public", "General public access"),
        ("observer", "Security researcher access"),
        ("contributor", "Contributing organisation access"), 
        ("partner", "Trusted partner access")
    ]
    
    for level, description in access_levels:
        threats = frank.query_threats("demo-org", access_level=level, limit=3)
        print(f"  {level.upper():12} ({description}): {len(threats)} threats visible")
        
        if threats:
            # Show first threat with access filtering applied
            threat = threats[0]
            observable_value = threat.get('observable_value', 'N/A')
            if len(observable_value) > 15:
                observable_value = observable_value[:15] + "..."
            print(f"               Sample: {threat.get('observable_type', 'unknown')} -> {observable_value}")
    
    # Scenario 3: Threat intelligence sharing workflow
    print("\n🔄 Scenario 3: Intelligence Sharing Workflow")
    print("-" * 50)
    
    # MSP reports threat on behalf of customer
    msp_submission = {
        "submission": {
            "submitter": {
                "organisation_id": "msp-services-inc",
                "access_level": "partner",
                "sector": "cybersecurity_services"
            },
            "hit_target": {
                "organisation_id": "customer-retail-chain",
                "organisation_type": "customer",
                "sector": "retail"
            },
            "sighting": {
                "sighting_id": f"sighting-{uuid.uuid4()}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence": 85,
                "severity": "high",
                "observables": {
                    "network": [{
                        "id": f"malware-c2-{uuid.uuid4()}",
                        "type": "domain",
                        "value": "evil-command-control.darknet"
                    }]
                }
            },
            "sharing": {
                "distribution_level": "AMBER",
                "anonymization_level": "high"
            }
        }
    }
    
    stored = frank.submit_to_database(msp_submission)
    print(f"  MSP Report: {'✓' if stored else '✗'} High-severity threat reported for retail customer")
    
    # Query recent high-severity threats
    with sqlite3.connect("/tmp/frank_demo.db") as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT s.severity, s.confidence, o.observable_type, COUNT(*) as count
            FROM submissions s
            JOIN sightings sg ON s.submission_id = sg.submission_id
            JOIN observables o ON sg.sighting_id = o.sighting_id
            WHERE s.severity = 'high'
            GROUP BY s.severity, o.observable_type
        """)
        
        high_severity = cursor.fetchall()
        if high_severity:
            print("  📊 High-severity threat summary:")
            for row in high_severity:
                print(f"      {row['observable_type']}: {row['count']} incidents")
    
    # Scenario 4: Real-time threat correlation
    print("\n⚡ Scenario 4: Real-time Threat Correlation")
    print("-" * 50)
    
    # Simulate multiple sightings of related threats
    related_threats = [
        "malware-dropper.exe",
        "credential-stealer.dll", 
        "backdoor-payload.bin"
    ]
    
    for i, threat_file in enumerate(related_threats):
        file_hash = hashlib.md5(threat_file.encode()).hexdigest()
        
        submission = frank.generate_minimal_submission(
            org_id=f"security-team-{i+1}",
            access_level="contributor",
            observables=[{
                "id": f"file-{uuid.uuid4()}",
                "type": "file_hash",
                "value": file_hash
            }]
        )
        
        frank.submit_to_database(submission)
        print(f"  Security Team {i+1}: Reported malicious file {threat_file}")
    
    # Show correlation statistics
    final_stats = frank.get_platform_statistics("demo-analyst")
    print(f"\n📈 Final Platform Statistics:")
    print(f"  Total Submissions: {final_stats.get('total_submissions', 0)}")
    print(f"  Active organisations: {final_stats.get('active_organisations', 0)}")
    print(f"  Total Observables: {final_stats.get('total_observables', 0)}")
    
    if 'top_observable_types' in final_stats:
        print(f"  Top Observable Types:")
        for obs_type, count in final_stats['top_observable_types'].items():
            print(f"    {obs_type}: {count}")
    
    print("\n✅ Database demonstration complete!")
    print(f"📁 Demo database saved as: /tmp/frank_demo.db")
    
    return frank


if __name__ == "__main__":
    # Run the test suite
    print("🚀 Starting FRANK Platform Local Development Tests...")
    results = run_tests()
    
    # Run the database demonstration
    demo_frank = run_database_demo()
    
    # Save sample outputs for reference
    print("\n💾 Saving sample files...")
    
    sample_files = [
        ('/tmp/frank_minimal_sample.yaml', results['yaml_format']),
        ('/tmp/frank_enhanced_sample.yaml', demo_frank.to_yaml(results['enhanced_submission'])),
        ('/tmp/frank_minimal_sample.json', results['json_format']),
        ('/tmp/frank_statistics.json', json.dumps(results['statistics'], indent=2))
    ]
    
    for filename, content in sample_files:
        try:
            with open(filename, 'w') as f:
                f.write(content)
            print(f"✓ Saved {filename}")
        except Exception as e:
            print(f"✗ Failed to save {filename}: {e}")
    
    print(f"\n🎯 FRANK local development environment ready!")
    print(f"📊 Test database: {results['database_path']}")
    print(f"📊 Demo database: /tmp/frank_demo.db")
    print(f"\nNext development stages:")
    print(f"  Stage 3: Add REST API endpoints (Flask/FastAPI)")
    print(f"  Stage 4: Implement contribution scoring algorithms")
    print(f"  Stage 5: Add real-time threat feed capabilities")
    print(f"  Stage 6: Implement SIGMA rule integration")
    print(f"  Stage 7: Add anonymization and TLP controls")
    
    # Provide database inspection commands
    print(f"\n🔍 Database inspection commands:")
    print(f"  sqlite3 /tmp/frank_demo.db '.tables'")
    print(f"  sqlite3 /tmp/frank_demo.db 'SELECT * FROM observable_statistics;'")
    print(f"  sqlite3 /tmp/frank_demo.db 'SELECT COUNT(*) FROM submissions;'")