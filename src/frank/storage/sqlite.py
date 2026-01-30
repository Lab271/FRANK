#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This modules provides sqlite3 based local database storage for FRANK submissions.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from frank.core.enum import AccessTier, ObservableType
from frank.core.models import Sighting, Submission, Submitter

from .base import BaseFRANKDatabase
from .exceptions import FRANKConnectionError, FRANKQueryError, FRANKStorageError

# Configure SQLite datetime adapter to avoid Python 3.12 deprecation warnings
sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
sqlite3.register_converter("DATETIME", lambda b: datetime.fromisoformat(b.decode()))

# Default configuration
DEFAULT_CONFIG = {
    'database_type': 'sqlite',
    'database_path': '/tmp/frank.db',
    'log_level': 'INFO',
    'default_tier': 'contributor',
    'retention_days': 90
}


class SQLiteFRANKDatabase(BaseFRANKDatabase):
    """
    SQLite implementation of FRANK database for local development.
    Provides full functionality with file-based storage and supports
    the complete FRANK access tier model.
    """

    def initialize(self) -> None:
        """Initialize the SQLite database with FRANK schema."""
        self.name = 'sqlite'
        db_path = self.connection_params['db_path']
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency

                # organisations table (cyber partners and customers)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS organisations (
                        organisation_id TEXT PRIMARY KEY,
                        organisation_type TEXT NOT NULL CHECK (organisation_type IN ('cyber_partner', 'customer')),
                        access_level TEXT CHECK (access_level IN ('public', 'observer', 'contributor', 'partner', 'core_member')),
                        sector TEXT,
                        region TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP,
                        contribution_score INTEGER DEFAULT 0,
                        client_count INTEGER DEFAULT 0,
                        metadata_json TEXT
                    )
                """)

                # Submissions table (main submission data)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS submissions (
                        submission_id TEXT PRIMARY KEY,
                        submitter_org_id TEXT NOT NULL,
                        hit_target_org_id TEXT,
                        format_version TEXT DEFAULT 'unknown',
                        submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        confidence INTEGER CHECK (confidence >= 0 AND confidence <= 100),
                        severity TEXT CHECK (severity IN ('low', 'medium', 'high', 'critical')),
                        tlp_level TEXT CHECK (tlp_level IN ('RED', 'AMBER+', 'AMBER', 'GREEN', 'CLEAR')),
                        full_submission_json TEXT NOT NULL,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (submitter_org_id) REFERENCES organisations (organisation_id),
                        FOREIGN KEY (hit_target_org_id) REFERENCES organisations (organisation_id)
                    )
                """)

                # Sightings table (individual threat sightings)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sightings (
                        sighting_id TEXT PRIMARY KEY,
                        submission_id TEXT NOT NULL,
                        sighting_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        first_observed TIMESTAMP,
                        last_observed TIMESTAMP,
                        observation_count INTEGER DEFAULT 1,
                        confidence INTEGER,
                        severity TEXT,
                        sigma_rule_id TEXT,
                        campaign_id TEXT,
                        affected_systems INTEGER,
                        compromised_accounts INTEGER,
                        containment_time TEXT,
                        financial_impact_eur INTEGER,
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
                        observable_hash TEXT NOT NULL, -- for quick lookups and deduplication
                        role TEXT,
                        port INTEGER,
                        protocol TEXT,
                        first_seen TIMESTAMP,
                        metadata_json TEXT,
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
                        organisation_ids_json TEXT, -- JSON array of unique organisation IDs
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(observable_hash)
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
                        success BOOLEAN DEFAULT TRUE,
                        ip_address TEXT,
                        user_agent TEXT,
                        details_json TEXT
                    )
                """)

                # Organisation members table (maps Cognito users to organisations)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS organisation_members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        organisation_id TEXT NOT NULL,
                        username TEXT NOT NULL,
                        role TEXT NOT NULL CHECK (role IN ('member', 'admin', 'owner')),
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id) ON DELETE CASCADE,
                        UNIQUE(organisation_id, username)
                    )
                """)

                # SIGMA rules table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sigma_rules (
                        rule_id TEXT PRIMARY KEY,
                        rule_name TEXT NOT NULL,
                        rule_version TEXT,
                        rule_status TEXT CHECK (rule_status IN ('stable', 'test', 'experimental')),
                        sigma_yaml TEXT,
                        created_by_org TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        effectiveness_score REAL,
                        false_positive_rate REAL,
                        FOREIGN KEY (created_by_org) REFERENCES organisations (organisation_id)
                    )
                """)

                # Campaign tracking table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS campaigns (
                        campaign_id TEXT PRIMARY KEY,
                        campaign_name TEXT NOT NULL,
                        attribution TEXT,
                        target_sectors_json TEXT,
                        attack_vector TEXT,
                        payload_type TEXT,
                        campaign_start TIMESTAMP,
                        estimated_victims INTEGER,
                        confidence INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # API keys table for programmatic access
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS api_keys (
                        key_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        key_hash TEXT NOT NULL UNIQUE,
                        key_prefix TEXT NOT NULL,
                        name TEXT NOT NULL,
                        expires_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used_at TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                """)

                # Refresh tokens table for OAuth2 flow
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS refresh_tokens (
                        token_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        token_hash TEXT NOT NULL UNIQUE,
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_revoked BOOLEAN DEFAULT 0
                    )
                """)

                # Create indexes for performance
                self._create_indexes(conn)

                conn.commit()
                self.logger.info(f"Database initialized at {db_path}")

        except sqlite3.Error as e:
            self.logger.error(f"Database initialization error: {e}")
            raise FRANKConnectionError(f"Failed to initialize database: {e}")

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        """Create database indexes for optimal query performance."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_submissions_submitter ON submissions (submitter_org_id)",
            "CREATE INDEX IF NOT EXISTS idx_submissions_timestamp ON submissions (submission_timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_submissions_severity ON submissions (severity)",
            "CREATE INDEX IF NOT EXISTS idx_submissions_tlp ON submissions (tlp_level)",

            "CREATE INDEX IF NOT EXISTS idx_sightings_submission ON sightings (submission_id)",
            "CREATE INDEX IF NOT EXISTS idx_sightings_confidence ON sightings (confidence)",
            "CREATE INDEX IF NOT EXISTS idx_sightings_observed ON sightings (first_observed)",

            "CREATE INDEX IF NOT EXISTS idx_observables_hash ON observables (observable_hash)",
            "CREATE INDEX IF NOT EXISTS idx_observables_type ON observables (observable_type)",
            "CREATE INDEX IF NOT EXISTS idx_observables_sighting ON observables (sighting_id)",
            "CREATE INDEX IF NOT EXISTS idx_observables_value ON observables (observable_value)",

            "CREATE INDEX IF NOT EXISTS idx_statistics_hash ON observable_statistics (observable_hash)",
            "CREATE INDEX IF NOT EXISTS idx_statistics_type ON observable_statistics (observable_type)",
            "CREATE INDEX IF NOT EXISTS idx_statistics_updated ON observable_statistics (updated_at)",

            "CREATE INDEX IF NOT EXISTS idx_access_logs_org ON access_logs (organisation_id)",
            "CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON access_logs (timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_access_logs_action ON access_logs (action)",

            "CREATE INDEX IF NOT EXISTS idx_organisations_tier ON organisations (tier)",
            "CREATE INDEX IF NOT EXISTS idx_organisations_sector ON organisations (sector)",
            "CREATE INDEX IF NOT EXISTS idx_organisations_active ON organisations (last_active)",

            "CREATE INDEX IF NOT EXISTS idx_org_members_org ON organisation_members (organisation_id)",
            "CREATE INDEX IF NOT EXISTS idx_org_members_user ON organisation_members (username)",

            "CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys (key_hash)",
            "CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys (is_active)",

            "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens (token_hash)",
            "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_revoked ON refresh_tokens (is_revoked)"
        ]

        for index_sql in indexes:
            try:
                conn.execute(index_sql)
            except sqlite3.Error as e:
                self.logger.warning(f"Failed to create index: {e}")

    def store_submission(self, submission: Submission) -> bool:
        """
        Store a complete submission in the database with full normalization.
        
        Args:
            submission: Complete FRANK submission dictionary
            
        Returns:
            True if stored successfully, False otherwise
        """
        self.logger.info(f"Storing submission: {submission.model_dump_json(exclude_none=True, exclude_defaults=True,by_alias=True)}...")
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")

                # Extract main submission data
                submitter = submission.submitter
                hit_target = submission.hit_target
                sighting = submission.sighting

                # Store or update organisation
                self._upsert_organisation(conn, submitter.model_dump(
                        exclude_none=True,
                        by_alias=True), org_type='cyber_partner')

                # Store hit target if present
                hit_target_id = None
                if hit_target:
                    self._upsert_organisation(conn, hit_target.model_dump(
                        exclude_none=True,
                        by_alias=True), org_type='customer')
                    hit_target_id = hit_target.organisation_id

                # Store main submission
                conn.execute("""
                    INSERT OR REPLACE INTO submissions 
                    (submission_id, submitter_org_id, hit_target_org_id, format_version, 
                     submission_timestamp, confidence, severity, tlp_level, full_submission_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    submission.submission_id, # assume this is always set
                    submitter.organisation_id,
                    hit_target_id,
                    submission.format_version,
                    submission.timestamp,
                    sighting.confidence,
                    sighting.severity,
                    submission.tlp_level,
                    submission.model_dump_json(by_alias=True, exclude_none=True)
                ))

                # Store sighting
                conn.execute("""
                    INSERT OR REPLACE INTO sightings 
                    (sighting_id, submission_id, first_observed, last_observed, 
                     observation_count, confidence, severity, sigma_rule_id, campaign_id,
                     affected_systems, compromised_accounts, containment_time, financial_impact_eur
                     )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sighting.sighting_id,
                    submission.submission_id,
                    sighting.first_observed,
                    sighting.last_observed,
                    sighting.observation_count,
                    sighting.confidence,
                    sighting.severity,
                    sighting.sigma_detection.rule_id if sighting.sigma_detection else None,
                    sighting.threat_context.campaign.id if sighting.threat_context else None,
                    sighting.impact.affected_systems if sighting.impact else None,
                    sighting.impact.compromised_accounts if sighting.impact else None,
                    sighting.impact.containment_time if sighting.impact else None,
                    sighting.impact.financial_impact_eur if sighting.impact else None
                ))

                # # Store observables and update statistics
                self._store_observables(conn, sighting, submitter)

                # # Store SIGMA rule if present
                self._store_sigma_rule(conn, sighting, submitter)

                # # Store campaign if present
                self._store_campaign(conn, sighting)

                # # Log access
                self._log_access(conn, submitter.organisation_id, 'SUBMIT', 'submission', submission.submission_id)

                conn.commit()
                self.logger.info(f"Stored submission {submission.submission_id}")
                return True

        except sqlite3.Error as e:
            self.logger.error(f"Error storing submission: {e}")
            raise FRANKStorageError(f"Failed to store submission: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error storing submission: {e}")
            return False

    def _store_observables(self, conn: sqlite3.Connection, sighting: Sighting, submitter: Submitter) -> None:
        """Store observables and update statistics."""
        observables = sighting.observables.model_dump(exclude_none=True, by_alias=True)
        self.logger.debug(f"Storing observables: {observables}")

        for obs_category, obs_list in observables.items():
            if isinstance(obs_list, list):
                for obs in obs_list:
                    if 'type' not in obs or 'value' not in obs:
                        continue

                    obs_hash = self.hash_observable(obs['type'], obs['value'])

                    # Store observable
                    conn.execute("""
                        INSERT OR REPLACE INTO observables 
                        (observable_id, sighting_id, observable_type, observable_value, 
                         observable_hash, role, port, protocol, first_seen, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        obs.get('id', f"obs-{uuid.uuid4()}"),
                        sighting.sighting_id,
                        obs['type'],
                        obs['value'],
                        obs_hash,
                        obs.get('role'),
                        obs.get('port'),
                        obs.get('protocol'),
                        obs.get('first_seen'),
                        json.dumps({k: v for k, v in obs.items()
                                   if k not in ['id', 'type', 'value', 'role', 'port', 'protocol', 'first_seen']})
                    ))

                    # Update statistics
                    self._update_observable_statistics(conn, obs, submitter)

    def _store_sigma_rule(self, conn: sqlite3.Connection, sighting: Sighting, submitter: Submitter) -> None:
        """Store SIGMA rule if present in sighting."""
        sigma_detection = sighting.sigma_detection
        if not sigma_detection:
            return

        conn.execute("""
            INSERT OR REPLACE INTO sigma_rules 
            (rule_id, rule_name, rule_version, rule_status, sigma_yaml, 
             created_by_org, effectiveness_score, false_positive_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sigma_detection.rule_id,
            sigma_detection.rule_name,
            sigma_detection.rule_version,
            sigma_detection.rule_status,
            sigma_detection.sigma_yaml,
            submitter.organisation_id,
            sigma_detection.rule_effectiveness,
            sigma_detection.false_positive_rate
        ))

    def _store_campaign(self, conn: sqlite3.Connection, sighting: Sighting) -> None:
        """Store campaign information if present."""
        if sighting.threat_context is None:
            return

        campaign = sighting.threat_context.campaign
        if not campaign:
            return

        conn.execute("""
            INSERT OR REPLACE INTO campaigns 
            (campaign_id, campaign_name, attribution, target_sectors_json, 
             attack_vector, payload_type, campaign_start, estimated_victims, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            campaign.id,
            campaign.name,
            campaign.attribution,
            json.dumps(campaign.target_sectors or []),
            campaign.attack_vector,
            campaign.payload_type,
            campaign.campaign_start,
            campaign.estimated_victims,
            campaign.confidence
        ))



    def _upsert_organisation(self, conn: sqlite3.Connection, org_data: Dict[str, Any], org_type: str = 'cyber_partner') -> None:
        """Insert or update organisation information."""
        self.logger.debug(f"Upserting organisation: {org_data}")
        metadata = {k: v for k, v in org_data.items()
                   if k not in ['organisation_id', 'organisation_type', 'access_level', 'sector', 'region', 'client_count']}

        conn.execute("""
            INSERT OR REPLACE INTO organisations 
            (organisation_id, organisation_type, access_level, sector, region, 
             last_active, client_count, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            org_data['organisation_id'],
            org_data.get('organisation_type', org_type),
            org_data.get('access_level'),
            org_data.get('sector'),
            org_data.get('region'),
            datetime.now(timezone.utc).isoformat(),
            org_data.get('client_count', 0),
            json.dumps(metadata)
        ))
        self.logger.info(f"Upserted organisation {org_data['organisation_id']}")

    def _update_observable_statistics(self, conn: sqlite3.Connection, observable: Dict[str, Any], submitter: Submitter) -> None:
        """Update aggregated statistics for observables."""
        obs_hash = self.hash_observable(observable['type'], observable['value'])

        # Check if statistics record exists
        cursor = conn.execute("""
            SELECT total_sightings, unique_organisations, sectors_json, regions_json, organisation_ids_json
            FROM observable_statistics WHERE observable_hash = ?
        """, (obs_hash,))

        existing = cursor.fetchone()

        if existing:
            # Update existing record
            total_sightings, unique_orgs, sectors_json, regions_json, org_ids_json = existing

            # Parse existing JSON data
            sectors = json.loads(sectors_json) if sectors_json else []
            regions = json.loads(regions_json) if regions_json else []
            org_ids = json.loads(org_ids_json) if org_ids_json else []

            # Add new sector/region if not present
            if submitter.sector and submitter.sector not in sectors:
                sectors.append(submitter.sector)
            if submitter.region and submitter.region not in regions:
                regions.append(submitter.region)

            # Track unique organisations - only increment if new org
            is_new_org = submitter.organisation_id not in org_ids
            if is_new_org:
                org_ids.append(submitter.organisation_id)

            # Update statistics
            conn.execute("""
                UPDATE observable_statistics
                SET total_sightings = total_sightings + 1,
                    unique_organisations = ?,
                    last_seen = ?,
                    sectors_json = ?,
                    regions_json = ?,
                    organisation_ids_json = ?,
                    updated_at = ?
                WHERE observable_hash = ?
            """, (
                unique_orgs + (1 if is_new_org else 0),
                datetime.now(timezone.utc).isoformat(),
                json.dumps(sectors),
                json.dumps(regions),
                json.dumps(org_ids),
                datetime.now(timezone.utc).isoformat(),
                obs_hash
            ))
        else:
            # Create new statistics record
            sectors = [submitter.sector] if submitter.sector else []
            regions = [submitter.region] if submitter.region else []
            org_ids = [submitter.organisation_id]

            conn.execute("""
                INSERT INTO observable_statistics
                (observable_hash, observable_type, observable_value, total_sightings,
                 unique_organisations, first_seen, last_seen, sectors_json, regions_json, organisation_ids_json)
                VALUES (?, ?, ?, 1, 1, ?, ?, ?, ?, ?)
            """, (
                obs_hash,
                observable['type'],
                observable['value'],
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
                json.dumps(sectors),
                json.dumps(regions),
                json.dumps(org_ids)
            ))

    def get_submission_by_id(self, submission_id: str, org_id: str, access_level: AccessTier = AccessTier.CONTRIBUTOR) -> Optional[Submission]:
        """
        Retrieve a specific submission with access level filtering.
        
        Args:
            submission_id: Submission ID to retrieve
            org_id: organisation ID making the request
            access_level: Access level for filtering
            
        Returns:
            Filtered Submission or None if not found
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
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

                submission_dict = json.loads(row['full_submission_json'])
                # Apply access level filtering
                filtered_submission = self._filter_submission_by_access_level(submission_dict, access_level)

                # Log access
                self._log_access(conn, org_id, 'READ', 'submission', submission_id)
                conn.commit()

                return Submission(**filtered_submission['submission'])

        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving submission {submission_id}: {e}")
            raise FRANKQueryError(f"Failed to retrieve submission: {e}")

    def query_observables(self, org_id: str, observable_type: ObservableType = None,
                         limit: int = 100, access_level: AccessTier = AccessTier.CONTRIBUTOR,
                         min_confidence: int = None, sectors: List[str] = None,
                         days_back: int = None) -> List[Dict[str, Any]]:
        """
        Query observables with access level filtering and advanced filters.
        
        Args:
            org_id: organisation ID making the query
            observable_type: Filter by observable type
            limit: Maximum number of results
            access_level: Access level for filtering
            min_confidence: Minimum confidence threshold
            sectors: Filter by affected sectors
            days_back: Only return observables from last N days
            
        Returns:
            List of filtered observable statistics
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Build query based on access level and filters
                query_parts = ["""
                    SELECT os.observable_hash, os.observable_type, os.observable_value,
                           os.total_sightings, os.unique_organisations, os.first_seen, 
                           os.last_seen, os.avg_confidence, os.sectors_json, os.regions_json
                    FROM observable_statistics os
                """]

                where_clauses = []
                params = []

                if observable_type:
                    where_clauses.append("COALESCE(os.observable_type, \"\") = ?")
                    params.append(observable_type.value)

                if min_confidence:
                    self.logger.info(f"finding min_confidence: {min_confidence}")
                    where_clauses.append("COALESCE(os.avg_confidence, 0) >= ?")
                    params.append(min_confidence)

                if days_back:
                    where_clauses.append("os.last_seen >= datetime('now', '-{} days')".format(days_back))

                if sectors:
                    # This is a simplified sector filter - in production would use JSON functions
                    sector_conditions = []
                    for sector in sectors:
                        sector_conditions.append("COALESCE(os.sectors_json, \"\") LIKE ?")
                        params.append(f'%"{sector}"%')
                    where_clauses.append(f"({' OR '.join(sector_conditions)})")

                if where_clauses:
                    query_parts.append(" WHERE " + " AND ".join(where_clauses))

                query_parts.append(f" ORDER BY os.last_seen DESC LIMIT {limit}")

                query = "".join(query_parts)
                cursor = conn.execute(query, params)
                results = []

                for row in cursor.fetchall():
                    result = dict(row)

                    # Apply access level filtering
                    result = self._filter_observable_by_access_level(result, access_level)

                    # Parse JSON fields
                    try:
                        result['sectors'] = json.loads(result['sectors_json']) if result['sectors_json'] else []
                        result['regions'] = json.loads(result['regions_json']) if result['regions_json'] else []
                        del result['sectors_json']
                        del result['regions_json']
                    except:
                        result['sectors'] = []
                        result['regions'] = []

                    results.append(result)

                # Log access
                self._log_access(conn, org_id, 'QUERY', 'observables')
                conn.commit()

                self.logger.info(f"Retrieved {len(results)} observables for {org_id} (access: {access_level.value})")
                return results

        except sqlite3.Error as e:
            self.logger.error(f"Error querying observables: {e}")
            raise FRANKQueryError(f"Failed to query observables: {e}")

    def get_statistics_summary(self, org_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get platform statistics summary.
        
        Args:
            org_id: organisation ID making the request
            days: Number of days to look back
            
        Returns:
            Statistics summary dictionary
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                stats = {}

                # Basic submission statistics
                cursor = conn.execute("""
                    SELECT 
                        COUNT(DISTINCT submission_id) as total_submissions,
                        COUNT(DISTINCT submitter_org_id) as active_organisations,
                        AVG(confidence) as avg_confidence
                    FROM submissions 
                    WHERE submission_timestamp >= datetime('now', '-{} days')
                """.format(days))

                basic_stats = dict(cursor.fetchone())
                stats.update(basic_stats)

                # Observable type distribution
                cursor = conn.execute("""
                    SELECT observable_type, COUNT(*) as count,
                           AVG(total_sightings) as avg_sightings
                    FROM observable_statistics
                    WHERE updated_at >= datetime('now', '-{} days')
                    GROUP BY observable_type
                    ORDER BY count DESC
                    LIMIT 10
                """.format(days))

                stats['observable_types'] = {
                       row[0]: {'count': row[1], 'avg_sightings': row[2]}
                       for row in cursor.fetchall()
                }

                # Severity distribution
                cursor = conn.execute("""
                    SELECT severity, COUNT(*) as count
                    FROM submissions
                    WHERE submission_timestamp >= datetime('now', '-{} days')
                    AND severity IS NOT NULL
                    GROUP BY severity
                """.format(days))

                stats['severity_distribution'] = dict(cursor.fetchall())

                # Top sectors by activity
                cursor = conn.execute("""
                    SELECT sector, COUNT(*) as submissions
                    FROM submissions s
                    JOIN organisations o ON s.submitter_org_id = o.organisation_id
                    WHERE s.submission_timestamp >= datetime('now', '-{} days')
                    AND o.sector IS NOT NULL
                    GROUP BY sector
                    ORDER BY submissions DESC
                    LIMIT 5
                """.format(days))

                stats['top_sectors'] = dict(cursor.fetchall())

                # Recent activity trend (daily counts)
                cursor = conn.execute("""
                    SELECT DATE(submission_timestamp) as date, COUNT(*) as count
                    FROM submissions
                    WHERE submission_timestamp >= datetime('now', '-{} days')
                    GROUP BY DATE(submission_timestamp)
                    ORDER BY date DESC
                """.format(days))

                stats['daily_activity'] = dict(cursor.fetchall())

                # Log access
                self._log_access(conn, org_id, 'STATS', 'summary')
                conn.commit()

                return stats

        except sqlite3.Error as e:
            self.logger.error(f"Error getting statistics: {e}")
            raise FRANKQueryError(f"Failed to get statistics: {e}")

    def upsert_organisation(self, org_data: Dict[str, Any]) -> bool:
        """
        Insert or update organisation information.
        
        Args:
            org_data: organisation data dictionary
            
        Returns:
            True if successful
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                self._upsert_organisation(conn, org_data)
                conn.commit()
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Error upserting organisation: {e}")
            return False

    def _log_access(self, conn: sqlite3.Connection, org_id: str, action: str,
                   resource_type: str = None, resource_id: str = None,
                   details: Dict[str, Any] = None) -> None:
        """Internal method to log access."""
        conn.execute("""
            INSERT INTO access_logs 
            (organisation_id, action, resource_type, resource_id, details_json)
            VALUES (?, ?, ?, ?, ?)
        """, (
            org_id,
            action,
            resource_type,
            resource_id,
            json.dumps(details) if details else None
        ))

    def log_access(self, org_id: str, action: str,
                   resource_type: str = None, resource_id: str = None,
                   details: Dict[str, Any] = None) -> bool:
        """
        Log an access event for auditing purposes.
        
        Args:
            org_id: organisation ID performing the action
            action: Action performed (e.g., 'READ', 'SUBMIT', 'QUERY')
            resource_type: Type of resource accessed (optional)
            resource_id: ID of the resource accessed (optional)
            details: Additional details as a dictionary (optional)
        
        Returns:
            True if the log entry was successfully written, False otherwise
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                self._log_access(conn, org_id, action, resource_type, resource_id, details)
                conn.commit()
                return True
        except sqlite3.Error as e:
            self.logger.error(f"Error logging access: {e}")
            return False

    # def _filter_submission_by_access_level(self, submission: Dict[str, Any], access_level: AccessTier) -> Dict[str, Any]:
    #     """Filter submission data based on access level."""
    #     # TODO: Upgrade this to Pydantic classes
    #     self.logger.info(f"Filtering submission for access level: {access_level.value}")
    #     self.logger.debug(f"Original submission data: {submission}")
    #     if access_level == AccessTier.PUBLIC:
    #         # Only basic statistics
    #         return {
    #             'submission': {
    #                 'submission_id': submission.get('submission_id'),
    #                 'timestamp': submission.get('timestamp'),
    #                 'sighting': {
    #                     'confidence': submission['sighting'].get('confidence'),
    #                     'timestamp': submission['sighting'].get('timestamp'),
    #                     'observation_count': submission['sighting'].get('observation_count')
    #                 }
    #             }
    #         }
    #     elif access_level == AccessTier.OBSERVER:
    #         # Add some observable types but mask values
    #         filtered = self._deep_copy(submission)
    #         observables = filtered['sighting'].get('observables', {})
    #         for category, obs_list in observables.items():
    #             if isinstance(obs_list, list):
    #                 for obs in obs_list:
    #                     if 'value' in obs:
    #                         obs['value'] = obs['value'][:10] + "..." if len(obs['value']) > 10 else obs['value']

    #         # Remove sensitive sections
    #         filtered.pop('hit_target', None)
    #         filtered.pop('tlp_level', None)

    #         return {'submission': filtered}
    #     elif access_level == AccessTier.CONTRIBUTOR:
    #         # Remove only the most sensitive information
    #         filtered = self._deep_copy(submission)

    #         # Anonymize hit target details
    #         if 'hit_target' in filtered:
    #             hit_target = filtered['hit_target']
    #             hit_target.pop('organisation_id', None)
    #             hit_target['sector'] = hit_target.get('sector', 'unknown')

    #         return {'submission': filtered}

    #     # Partner and core_member get full access
    #     return {'submission': submission}

    # def _filter_observable_by_access_level(self, observable: Dict[str, Any], access_level: AccessTier) -> Dict[str, Any]:
    #     """Filter observable data based on access level."""
    #     if access_level == AccessTier.PUBLIC:
    #         return {
    #             'observable_type': observable['observable_type'],
    #             'total_sightings': observable['total_sightings'],
    #             'last_seen': observable['last_seen']
    #         }
    #     elif access_level == AccessTier.OBSERVER:
    #         filtered = dict(observable)
    #         # Mask observable value
    #         if 'observable_value' in filtered:
    #             value = filtered['observable_value']
    #             filtered['observable_value'] = value[:10] + "..." if len(value) > 10 else value
    #         return filtered

    #     # Contributor and above get full access
    #     return observable

    # def _deep_copy(self, obj: Any) -> Any:
    #     """Create a deep copy of an object."""
    #     if isinstance(obj, dict):
    #         return {k: self._deep_copy(v) for k, v in obj.items()}
    #     elif isinstance(obj, list):
    #         return [self._deep_copy(item) for item in obj]
    #     else:
    #         return obj

    def search_observables_by_value(self, org_id: str, search_value: str,
                                   access_level: AccessTier = AccessTier.CONTRIBUTOR) -> List[Dict[str, Any]]:
        """
        Search for observables by partial value match.
        
        Args:
            org_id: organisation performing the search
            search_value: Value to search for (supports wildcards)
            access_level: Access level for filtering
            
        Returns:
            List of matching observables
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                cursor = conn.execute("""
                    SELECT os.* FROM observable_statistics os
                    WHERE os.observable_value LIKE ?
                    ORDER BY os.total_sightings DESC
                    LIMIT 100
                """, (f"%{search_value}%",))

                results = []
                for row in cursor.fetchall():
                    result = dict(row)
                    result = self._filter_observable_by_access_level(result, access_level)

                    # Parse JSON fields
                    try:
                        result['sectors'] = json.loads(result['sectors_json']) if result['sectors_json'] else []
                        result['regions'] = json.loads(result['regions_json']) if result['regions_json'] else []
                        del result['sectors_json']
                        del result['regions_json']
                    except:
                        result['sectors'] = []
                        result['regions'] = []

                    results.append(result)

                # Log access
                self._log_access(conn, org_id, 'SEARCH', 'observables', details={'search_value': search_value})
                conn.commit()

                return results

        except sqlite3.Error as e:
            self.logger.error(f"Error searching observables: {e}")
            raise FRANKQueryError(f"Failed to search observables: {e}")

    def get_organisation_info(self, org_id: str) -> Optional[Dict[str, Any]]:
        """
        Get organisation information.
        
        Args:
            org_id: organisation ID to look up
            
        Returns:
            organisation data or None if not found
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                cursor = conn.execute("""
                    SELECT * FROM organisations WHERE organisation_id = ?
                """, (org_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                org_data = dict(row)

                # Parse metadata JSON
                try:
                    metadata = json.loads(org_data['metadata_json']) if org_data['metadata_json'] else {}
                    org_data.update(metadata)
                    del org_data['metadata_json']
                except:
                    del org_data['metadata_json']

                return org_data

        except sqlite3.Error as e:
            self.logger.error(f"Error getting organisation info: {e}")
            return None

    def get_sigma_rules(self, org_id: str, rule_status: str = None,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get SIGMA rules with optional filtering.
        
        Args:
            org_id: organisation requesting the rules
            rule_status: Filter by rule status (stable, test, experimental)
            limit: Maximum number of rules to return
            
        Returns:
            List of SIGMA rule dictionaries
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                query = "SELECT * FROM sigma_rules"
                params = []

                if rule_status:
                    query += " WHERE rule_status = ?"
                    params.append(rule_status)

                query += f" ORDER BY updated_at DESC LIMIT {limit}"

                cursor = conn.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]

                # Log access
                self._log_access(conn, org_id, 'QUERY', 'sigma_rules')
                conn.commit()

                return results

        except sqlite3.Error as e:
            self.logger.error(f"Error getting SIGMA rules: {e}")
            raise FRANKQueryError(f"Failed to get SIGMA rules: {e}")

    def get_campaigns(self, org_id: str, active_only: bool = False,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get campaign information.
        
        Args:
            org_id: organisation requesting campaigns
            active_only: Only return recently active campaigns
            limit: Maximum number of campaigns to return
            
        Returns:
            List of campaign dictionaries
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                query = "SELECT * FROM campaigns"

                if active_only:
                    query += " WHERE updated_at >= datetime('now', '-30 days')"

                query += f" ORDER BY updated_at DESC LIMIT {limit}"

                cursor = conn.execute(query)
                results = []

                for row in cursor.fetchall():
                    campaign = dict(row)

                    # Parse JSON fields
                    try:
                        campaign['target_sectors'] = json.loads(campaign['target_sectors_json']) if campaign['target_sectors_json'] else []
                        del campaign['target_sectors_json']
                    except:
                        campaign['target_sectors'] = []

                    results.append(campaign)

                # Log access
                self._log_access(conn, org_id, 'QUERY', 'campaigns')
                conn.commit()

                return results

        except sqlite3.Error as e:
            self.logger.error(f"Error getting campaigns: {e}")
            raise FRANKQueryError(f"Failed to get campaigns: {e}")

    def get_access_logs(self, org_id: str, days: int = 7,
                       actions: List[str] = None) -> List[Dict[str, Any]]:
        """
        Get access logs for auditing.
        
        Args:
            org_id: organisation to get logs for
            days: Number of days to look back
            actions: Filter by specific actions
            
        Returns:
            List of access log entries
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                query = """
                    SELECT * FROM access_logs 
                    WHERE organisation_id = ? 
                    AND timestamp >= datetime('now', '-{} days')
                """.format(days)

                params = [org_id]

                if actions:
                    placeholders = ','.join('?' * len(actions))
                    query += f" AND action IN ({placeholders})"
                    params.extend(actions)

                query += " ORDER BY timestamp DESC LIMIT 1000"

                cursor = conn.execute(query, params)
                results = []

                for row in cursor.fetchall():
                    log_entry = dict(row)

                    # Parse details JSON
                    try:
                        details = json.loads(log_entry['details_json']) if log_entry['details_json'] else {}
                        log_entry['details'] = details
                        del log_entry['details_json']
                    except:
                        log_entry['details'] = {}
                        del log_entry['details_json']

                    results.append(log_entry)

                return results

        except sqlite3.Error as e:
            self.logger.error(f"Error getting access logs: {e}")
            raise FRANKQueryError(f"Failed to get access logs: {e}")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the database.
        
        Returns:
            Health status dictionary
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                # Basic connectivity test
                cursor = conn.execute("SELECT 1")
                cursor.fetchone()

                # Get database statistics
                cursor = conn.execute("""
                    SELECT name, COUNT(*) as count FROM (
                        SELECT 'organisations' as name FROM organisations
                        UNION ALL
                        SELECT 'submissions' as name FROM submissions
                        UNION ALL
                        SELECT 'sightings' as name FROM sightings
                        UNION ALL
                        SELECT 'observables' as name FROM observables
                        UNION ALL
                        SELECT 'observable_statistics' as name FROM observable_statistics
                        UNION ALL
                        SELECT 'access_logs' as name FROM access_logs
                    ) GROUP BY name
                """)

                table_counts = dict(cursor.fetchall())

                # Check database size
                db_size = Path(db_path).stat().st_size if Path(db_path).exists() else 0

                return {
                    'status': 'healthy',
                    'database_path': db_path,
                    'database_size_bytes': db_size,
                    'table_counts': table_counts
                }

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

    # ========== Organisation CRUD Methods ==========

    def create_organisation(self, org_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new organisation in the database.

        Args:
            org_data: Organisation data including name, organisation_type, access_level, etc.

        Returns:
            Created organisation data with generated organisation_id
        """
        db_path = self.connection_params['db_path']

        # Generate organisation_id if not provided
        if 'organisation_id' not in org_data or not org_data['organisation_id']:
            org_data['organisation_id'] = f"identity--{uuid.uuid4()}"

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")

                # Extract fields
                metadata = {k: v for k, v in org_data.items()
                           if k not in ['organisation_id', 'organisation_type', 'access_level',
                                       'sector', 'region', 'client_count', 'name']}
                # Include name in metadata for storage
                if 'name' in org_data:
                    metadata['name'] = org_data['name']

                conn.execute("""
                    INSERT INTO organisations
                    (organisation_id, organisation_type, access_level, sector, region,
                     last_active, client_count, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    org_data['organisation_id'],
                    org_data.get('organisation_type', 'customer'),
                    org_data.get('access_level'),
                    org_data.get('sector'),
                    org_data.get('region'),
                    datetime.now(timezone.utc).isoformat(),
                    org_data.get('client_count', 0),
                    json.dumps(metadata)
                ))
                conn.commit()

                self.logger.info(f"Created organisation {org_data['organisation_id']}")
                return self.get_organisation(org_data['organisation_id'])

        except sqlite3.IntegrityError as e:
            self.logger.error(f"Organisation already exists: {e}")
            raise FRANKStorageError(f"Organisation already exists: {e}")
        except sqlite3.Error as e:
            self.logger.error(f"Error creating organisation: {e}")
            raise FRANKStorageError(f"Failed to create organisation: {e}")

    def get_organisation(self, organisation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an organisation by ID.

        Args:
            organisation_id: The organisation ID to retrieve

        Returns:
            Organisation data or None if not found
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                cursor = conn.execute("""
                    SELECT * FROM organisations WHERE organisation_id = ?
                """, (organisation_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                org_data = dict(row)

                # Parse metadata JSON
                try:
                    metadata = json.loads(org_data['metadata_json']) if org_data['metadata_json'] else {}
                    org_data.update(metadata)
                    del org_data['metadata_json']
                except (json.JSONDecodeError, KeyError):
                    if 'metadata_json' in org_data:
                        del org_data['metadata_json']

                return org_data

        except sqlite3.Error as e:
            self.logger.error(f"Error getting organisation: {e}")
            return None

    def list_organisations(
        self,
        organisation_type: str = None,
        access_level: str = None,
        sector: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List organisations with optional filtering.

        Args:
            organisation_type: Filter by organisation type
            access_level: Filter by access level
            sector: Filter by sector
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of matching organisations
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                query = "SELECT * FROM organisations WHERE 1=1"
                params = []

                if organisation_type:
                    query += " AND organisation_type = ?"
                    params.append(organisation_type)

                if access_level:
                    query += " AND access_level = ?"
                    params.append(access_level)

                if sector:
                    query += " AND sector = ?"
                    params.append(sector)

                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor = conn.execute(query, params)
                results = []

                for row in cursor.fetchall():
                    org_data = dict(row)

                    # Parse metadata JSON
                    try:
                        metadata = json.loads(org_data['metadata_json']) if org_data['metadata_json'] else {}
                        org_data.update(metadata)
                        del org_data['metadata_json']
                    except (json.JSONDecodeError, KeyError):
                        if 'metadata_json' in org_data:
                            del org_data['metadata_json']

                    results.append(org_data)

                return results

        except sqlite3.Error as e:
            self.logger.error(f"Error listing organisations: {e}")
            raise FRANKQueryError(f"Failed to list organisations: {e}")

    def update_organisation(self, organisation_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update an existing organisation.

        Args:
            organisation_id: The organisation ID to update
            updates: Fields to update

        Returns:
            Updated organisation data or None if not found
        """
        db_path = self.connection_params['db_path']

        # Check if organisation exists
        existing = self.get_organisation(organisation_id)
        if not existing:
            return None

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")

                # Build update query dynamically
                allowed_fields = ['organisation_type', 'access_level', 'sector', 'region', 'client_count']
                set_clauses = []
                params = []

                for field in allowed_fields:
                    if field in updates:
                        set_clauses.append(f"{field} = ?")
                        params.append(updates[field])

                # Handle metadata updates
                metadata_fields = {k: v for k, v in updates.items() if k not in allowed_fields and k != 'organisation_id'}
                if metadata_fields:
                    # Merge with existing metadata
                    existing_metadata = {k: v for k, v in existing.items()
                                        if k not in ['organisation_id', 'organisation_type', 'access_level',
                                                    'sector', 'region', 'client_count', 'created_at', 'last_active',
                                                    'contribution_score']}
                    existing_metadata.update(metadata_fields)
                    set_clauses.append("metadata_json = ?")
                    params.append(json.dumps(existing_metadata))

                if not set_clauses:
                    return existing

                # Always update last_active
                set_clauses.append("last_active = ?")
                params.append(datetime.now(timezone.utc).isoformat())

                params.append(organisation_id)

                query = f"UPDATE organisations SET {', '.join(set_clauses)} WHERE organisation_id = ?"
                conn.execute(query, params)
                conn.commit()

                self.logger.info(f"Updated organisation {organisation_id}")
                return self.get_organisation(organisation_id)

        except sqlite3.Error as e:
            self.logger.error(f"Error updating organisation: {e}")
            raise FRANKStorageError(f"Failed to update organisation: {e}")

    def delete_organisation(self, organisation_id: str) -> bool:
        """
        Delete an organisation by ID.

        Args:
            organisation_id: The organisation ID to delete

        Returns:
            True if deleted, False if not found
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")

                cursor = conn.execute("""
                    DELETE FROM organisations WHERE organisation_id = ?
                """, (organisation_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    self.logger.info(f"Deleted organisation {organisation_id}")
                    return True
                return False

        except sqlite3.Error as e:
            self.logger.error(f"Error deleting organisation: {e}")
            raise FRANKStorageError(f"Failed to delete organisation: {e}")

    # ========== Organisation Member Methods ==========

    def add_organisation_member(
        self,
        organisation_id: str,
        username: str,
        role: str = "member"
    ) -> Dict[str, Any]:
        """
        Add a user as a member of an organisation.

        Args:
            organisation_id: The organisation ID
            username: The Cognito username
            role: Member role ('member', 'admin', 'owner')

        Returns:
            Membership record
        """
        db_path = self.connection_params['db_path']

        # Validate role
        if role not in ['member', 'admin', 'owner']:
            raise FRANKStorageError(f"Invalid role: {role}. Must be 'member', 'admin', or 'owner'")

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")

                conn.execute("""
                    INSERT INTO organisation_members (organisation_id, username, role)
                    VALUES (?, ?, ?)
                """, (organisation_id, username, role))
                conn.commit()

                self.logger.info(f"Added member {username} to organisation {organisation_id} with role {role}")
                return {
                    "organisation_id": organisation_id,
                    "username": username,
                    "role": role,
                    "joined_at": datetime.now(timezone.utc).isoformat()
                }

        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint" in str(e):
                raise FRANKStorageError(f"User {username} is already a member of organisation {organisation_id}")
            elif "FOREIGN KEY constraint" in str(e):
                raise FRANKStorageError(f"Organisation {organisation_id} does not exist")
            raise FRANKStorageError(f"Failed to add member: {e}")
        except sqlite3.Error as e:
            self.logger.error(f"Error adding organisation member: {e}")
            raise FRANKStorageError(f"Failed to add member: {e}")

    def remove_organisation_member(self, organisation_id: str, username: str) -> bool:
        """
        Remove a user from an organisation.

        Args:
            organisation_id: The organisation ID
            username: The Cognito username

        Returns:
            True if removed, False if not found
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM organisation_members
                    WHERE organisation_id = ? AND username = ?
                """, (organisation_id, username))
                conn.commit()

                if cursor.rowcount > 0:
                    self.logger.info(f"Removed member {username} from organisation {organisation_id}")
                    return True
                return False

        except sqlite3.Error as e:
            self.logger.error(f"Error removing organisation member: {e}")
            raise FRANKStorageError(f"Failed to remove member: {e}")

    def get_organisation_members(
        self,
        organisation_id: str,
        role: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get all members of an organisation.

        Args:
            organisation_id: The organisation ID
            role: Filter by role (optional)

        Returns:
            List of membership records
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                query = """
                    SELECT organisation_id, username, role, joined_at
                    FROM organisation_members
                    WHERE organisation_id = ?
                """
                params = [organisation_id]

                if role:
                    query += " AND role = ?"
                    params.append(role)

                query += " ORDER BY joined_at ASC"

                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            self.logger.error(f"Error getting organisation members: {e}")
            raise FRANKQueryError(f"Failed to get organisation members: {e}")

    def get_user_organisations(self, username: str) -> List[Dict[str, Any]]:
        """
        Get all organisations a user belongs to.

        Args:
            username: The Cognito username

        Returns:
            List of organisations with membership role
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                cursor = conn.execute("""
                    SELECT o.*, m.role as member_role, m.joined_at as member_joined_at
                    FROM organisations o
                    JOIN organisation_members m ON o.organisation_id = m.organisation_id
                    WHERE m.username = ?
                    ORDER BY m.joined_at ASC
                """, (username,))

                results = []
                for row in cursor.fetchall():
                    org_data = dict(row)

                    # Parse metadata JSON
                    try:
                        metadata = json.loads(org_data['metadata_json']) if org_data['metadata_json'] else {}
                        org_data.update(metadata)
                        del org_data['metadata_json']
                    except (json.JSONDecodeError, KeyError):
                        if 'metadata_json' in org_data:
                            del org_data['metadata_json']

                    results.append(org_data)

                return results

        except sqlite3.Error as e:
            self.logger.error(f"Error getting user organisations: {e}")
            raise FRANKQueryError(f"Failed to get user organisations: {e}")

    def get_organisation_member(
        self,
        organisation_id: str,
        username: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific organisation member.

        Args:
            organisation_id: The organisation ID
            username: The Cognito username

        Returns:
            Membership record or None if not found
        """
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                cursor = conn.execute("""
                    SELECT organisation_id, username, role, joined_at
                    FROM organisation_members
                    WHERE organisation_id = ? AND username = ?
                """, (organisation_id, username))

                row = cursor.fetchone()
                return dict(row) if row else None

        except sqlite3.Error as e:
            self.logger.error(f"Error getting organisation member: {e}")
            return None

    # ========== API Key Methods ==========

    def create_api_key(
        self,
        user_id: str,
        key_hash: str,
        name: str,
        expires_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """Store a new API key in the database."""
        db_path = self.connection_params['db_path']
        key_id = f"key-{uuid.uuid4().hex[:12]}"
        key_prefix = f"frank_...{key_hash[-8:]}"  # Last 8 chars of hash for display
        now = datetime.now(timezone.utc).isoformat()

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    INSERT INTO api_keys (key_id, user_id, key_hash, key_prefix, name, expires_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (key_id, user_id, key_hash, key_prefix, name, expires_at, now))
                conn.commit()

                self.logger.info(f"Created API key {key_id} for user {user_id}")
                return {
                    "key_id": key_id,
                    "user_id": user_id,
                    "key_prefix": key_prefix,
                    "name": name,
                    "expires_at": expires_at,
                    "created_at": now,
                    "is_active": True
                }

        except sqlite3.IntegrityError as e:
            self.logger.error(f"API key already exists: {e}")
            raise FRANKStorageError(f"API key already exists: {e}")
        except sqlite3.Error as e:
            self.logger.error(f"Error creating API key: {e}")
            raise FRANKStorageError(f"Failed to create API key: {e}")

    def get_api_key_by_hash(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve an API key by its hash."""
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT key_id, user_id, key_prefix, name, expires_at, created_at, last_used_at, is_active
                    FROM api_keys
                    WHERE key_hash = ? AND is_active = 1
                """, (key_hash,))

                row = cursor.fetchone()
                if not row:
                    return None

                result = dict(row)
                # Check expiry
                if result.get("expires_at"):
                    expires = datetime.fromisoformat(result["expires_at"])
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > expires:
                        return None  # Expired

                return result

        except sqlite3.Error as e:
            self.logger.error(f"Error getting API key: {e}")
            return None

    def list_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """List all API keys for a user."""
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT key_id, user_id, key_prefix, name, expires_at, created_at, last_used_at, is_active
                    FROM api_keys
                    WHERE user_id = ? AND is_active = 1
                    ORDER BY created_at DESC
                """, (user_id,))

                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            self.logger.error(f"Error listing API keys: {e}")
            return []

    def update_api_key(
        self,
        key_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update API key metadata."""
        db_path = self.connection_params['db_path']

        # Only allow updating name and expires_at
        allowed_fields = {"name", "expires_at"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return None

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Build update query
                set_clause = ", ".join(f"{k} = ?" for k in filtered_updates.keys())
                values = list(filtered_updates.values()) + [key_id, user_id]

                cursor = conn.execute(f"""
                    UPDATE api_keys
                    SET {set_clause}
                    WHERE key_id = ? AND user_id = ? AND is_active = 1
                """, values)
                conn.commit()

                if cursor.rowcount == 0:
                    return None

                # Fetch updated record
                cursor = conn.execute("""
                    SELECT key_id, user_id, key_prefix, name, expires_at, created_at, last_used_at, is_active
                    FROM api_keys
                    WHERE key_id = ?
                """, (key_id,))
                row = cursor.fetchone()
                return dict(row) if row else None

        except sqlite3.Error as e:
            self.logger.error(f"Error updating API key: {e}")
            return None

    def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        """Revoke (soft delete) an API key."""
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("""
                    UPDATE api_keys
                    SET is_active = 0
                    WHERE key_id = ? AND user_id = ? AND is_active = 1
                """, (key_id, user_id))
                conn.commit()

                if cursor.rowcount > 0:
                    self.logger.info(f"Revoked API key {key_id} for user {user_id}")
                    return True
                return False

        except sqlite3.Error as e:
            self.logger.error(f"Error revoking API key: {e}")
            return False

    def update_api_key_last_used(self, key_id: str) -> None:
        """Update the last_used_at timestamp for an API key."""
        db_path = self.connection_params['db_path']
        now = datetime.now(timezone.utc).isoformat()

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    UPDATE api_keys
                    SET last_used_at = ?
                    WHERE key_id = ?
                """, (now, key_id))
                conn.commit()

        except sqlite3.Error as e:
            self.logger.warning(f"Error updating API key last_used: {e}")

    # ========== Refresh Token Methods ==========

    def store_refresh_token(
        self,
        user_id: str,
        token_id: str,
        token_hash: str,
        expires_at: str
    ) -> Dict[str, Any]:
        """Store a refresh token hash in the database."""
        db_path = self.connection_params['db_path']
        now = datetime.now(timezone.utc).isoformat()

        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    INSERT INTO refresh_tokens (token_id, user_id, token_hash, expires_at, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (token_id, user_id, token_hash, expires_at, now))
                conn.commit()

                self.logger.info(f"Stored refresh token {token_id} for user {user_id}")
                return {
                    "token_id": token_id,
                    "user_id": user_id,
                    "expires_at": expires_at,
                    "created_at": now
                }

        except sqlite3.IntegrityError as e:
            self.logger.error(f"Refresh token already exists: {e}")
            raise FRANKStorageError(f"Refresh token already exists: {e}")
        except sqlite3.Error as e:
            self.logger.error(f"Error storing refresh token: {e}")
            raise FRANKStorageError(f"Failed to store refresh token: {e}")

    def get_refresh_token(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a refresh token by its ID."""
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT token_id, user_id, token_hash, expires_at, created_at, is_revoked
                    FROM refresh_tokens
                    WHERE token_id = ? AND is_revoked = 0
                """, (token_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                result = dict(row)
                # Check expiry
                if result.get("expires_at"):
                    expires = datetime.fromisoformat(result["expires_at"])
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > expires:
                        return None  # Expired

                return result

        except sqlite3.Error as e:
            self.logger.error(f"Error getting refresh token: {e}")
            return None

    def revoke_refresh_token(self, token_id: str) -> bool:
        """Revoke a refresh token."""
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("""
                    UPDATE refresh_tokens
                    SET is_revoked = 1
                    WHERE token_id = ? AND is_revoked = 0
                """, (token_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    self.logger.info(f"Revoked refresh token {token_id}")
                    return True
                return False

        except sqlite3.Error as e:
            self.logger.error(f"Error revoking refresh token: {e}")
            return False

    def revoke_all_user_refresh_tokens(self, user_id: str) -> int:
        """Revoke all refresh tokens for a user."""
        db_path = self.connection_params['db_path']

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("""
                    UPDATE refresh_tokens
                    SET is_revoked = 1
                    WHERE user_id = ? AND is_revoked = 0
                """, (user_id,))
                conn.commit()

                count = cursor.rowcount
                if count > 0:
                    self.logger.info(f"Revoked {count} refresh tokens for user {user_id}")
                return count

        except sqlite3.Error as e:
            self.logger.error(f"Error revoking user refresh tokens: {e}")
            return 0


# Factory function for easy instantiation
def create_sqlite_database(db_path: str = "/tmp/frank_local.db",
                           logger: Optional[logging.Logger] = None) -> SQLiteFRANKDatabase:
    """
    Factory function to create a SQLiteFRANKDatabase instance.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        Configured SQLiteFRANKDatabase instance
    """

    connection_params = {
        "db_path": db_path
    }

    # Set up logging
    if not logger:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)

    return SQLiteFRANKDatabase(connection_params, logger=logger)



