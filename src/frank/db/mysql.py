#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This modules provides MySQL based database storage for FRANK submissions using PyMySQL.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import json
import pymysql
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import logging

from frank.db.exceptions import FRANKConnectionError, FRANKQueryError, FRANKStorageError
from frank.db.base import BaseFRANKDatabase
from frank.core.models import Submission, Sighting, Submitter
from frank.core.enum import ObservableType, TierLevel


class MySQLFRANKDatabase(BaseFRANKDatabase):
    """
    MySQL (PyMySQL) implementation of FRANK database for scalable deployment.
    Provides full functionality with relational database storage and supports
    the complete FRANK access tier model.
    """
       
    def get_connection(self) -> pymysql.Connection:
        """Get a fresh database connection."""
        try:
            return pymysql.connect(**self.connection_params)
        except pymysql.Error as e:
            self.logger.error(f"Failed to connect to MySQL: {e}")
            raise FRANKConnectionError(f"Database connection failed: {e}")
    
    def initialize(self) -> None:
        """Initialize the MySQL database with FRANK schema."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Set SQL mode for strict operations
            cursor.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO'")
            
            # Organizations table (cyber partners and customers)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS organizations (
                    organization_id VARCHAR(255) PRIMARY KEY,
                    organization_type ENUM('cyber_partner', 'customer') NOT NULL,
                    tier ENUM('public', 'observer', 'contributor', 'partner', 'core_member') NULL,
                    sector VARCHAR(100) NULL,
                    region VARCHAR(100) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP NULL,
                    contribution_score INT DEFAULT 0,
                    client_count INT DEFAULT 0,
                    metadata_json JSON NULL,
                    INDEX idx_organizations_tier (tier),
                    INDEX idx_organizations_sector (sector),
                    INDEX idx_organizations_active (last_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Submissions table (main submission data)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS submissions (
                    submission_id VARCHAR(255) PRIMARY KEY,
                    submitter_org_id VARCHAR(255) NOT NULL,
                    hit_target_org_id VARCHAR(255) NULL,
                    format_version VARCHAR(50) DEFAULT 'unknown',
                    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confidence TINYINT UNSIGNED NULL CHECK (confidence >= 0 AND confidence <= 100),
                    severity ENUM('low', 'medium', 'high', 'critical') NULL,
                    tlp_level ENUM('RED', 'AMBER+', 'AMBER', 'GREEN', 'CLEAR') NULL,
                    full_submission_json JSON NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (submitter_org_id) REFERENCES organizations (organization_id) ON DELETE RESTRICT,
                    FOREIGN KEY (hit_target_org_id) REFERENCES organizations (organization_id) ON DELETE SET NULL,
                    INDEX idx_submissions_submitter (submitter_org_id),
                    INDEX idx_submissions_timestamp (submission_timestamp),
                    INDEX idx_submissions_severity (severity),
                    INDEX idx_submissions_tlp (tlp_level)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Sightings table (individual threat sightings)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sightings (
                    sighting_id VARCHAR(255) PRIMARY KEY,
                    submission_id VARCHAR(255) NOT NULL,
                    sighting_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    first_observed TIMESTAMP NULL,
                    last_observed TIMESTAMP NULL,
                    observation_count INT DEFAULT 1,
                    confidence TINYINT UNSIGNED NULL,
                    severity ENUM('low', 'medium', 'high', 'critical') NULL,
                    sigma_rule_id VARCHAR(255) NULL,
                    campaign_id VARCHAR(255) NULL,
                    affected_systems INT NULL,
                    compromised_accounts INT NULL,
                    containment_time VARCHAR(50) NULL,
                    financial_impact_eur DECIMAL(15,2) NULL,
                    FOREIGN KEY (submission_id) REFERENCES submissions (submission_id) ON DELETE CASCADE,
                    INDEX idx_sightings_submission (submission_id),
                    INDEX idx_sightings_confidence (confidence),
                    INDEX idx_sightings_observed (first_observed)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Observables table (IoCs and artifacts)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS observables (
                    observable_id VARCHAR(255) PRIMARY KEY,
                    sighting_id VARCHAR(255) NOT NULL,
                    observable_type ENUM('ipv4', 'ipv6', 'domain', 'url', 'file_hash', 'email', 'registry_key') NOT NULL,
                    observable_value TEXT NOT NULL,
                    observable_hash VARCHAR(64) NOT NULL,
                    role VARCHAR(100) NULL,
                    port SMALLINT UNSIGNED NULL,
                    protocol VARCHAR(20) NULL,
                    first_seen TIMESTAMP NULL,
                    metadata_json JSON NULL,
                    FOREIGN KEY (sighting_id) REFERENCES sightings (sighting_id) ON DELETE CASCADE,
                    INDEX idx_observables_hash (observable_hash),
                    INDEX idx_observables_type (observable_type),
                    INDEX idx_observables_sighting (sighting_id),
                    INDEX idx_observables_value (observable_value(255))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Statistics table (aggregated sighting data)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS observable_statistics (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    observable_hash VARCHAR(64) NOT NULL UNIQUE,
                    observable_type ENUM('ipv4', 'ipv6', 'domain', 'url', 'file_hash', 'email', 'registry_key') NOT NULL,
                    observable_value TEXT NOT NULL,
                    total_sightings INT DEFAULT 1,
                    unique_organizations INT DEFAULT 1,
                    first_seen TIMESTAMP NULL,
                    last_seen TIMESTAMP NULL,
                    avg_confidence DECIMAL(5,2) NULL,
                    sectors_json JSON NULL,
                    regions_json JSON NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_statistics_hash (observable_hash),
                    INDEX idx_statistics_type (observable_type),
                    INDEX idx_statistics_updated (updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Access logs for auditing
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS access_logs (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    organization_id VARCHAR(255) NOT NULL,
                    action VARCHAR(100) NOT NULL,
                    resource_type VARCHAR(100) NULL,
                    resource_id VARCHAR(255) NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_level VARCHAR(50) NULL,
                    success BOOLEAN DEFAULT TRUE,
                    ip_address VARCHAR(45) NULL,
                    user_agent TEXT NULL,
                    details_json JSON NULL,
                    INDEX idx_access_logs_org (organization_id),
                    INDEX idx_access_logs_timestamp (timestamp),
                    INDEX idx_access_logs_action (action)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # SIGMA rules table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sigma_rules (
                    rule_id VARCHAR(255) PRIMARY KEY,
                    rule_name VARCHAR(500) NOT NULL,
                    rule_version VARCHAR(50) NULL,
                    rule_status ENUM('stable', 'test', 'experimental') NULL,
                    sigma_yaml TEXT NULL,
                    created_by_org VARCHAR(255) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    effectiveness_score DECIMAL(5,2) NULL,
                    false_positive_rate DECIMAL(5,2) NULL,
                    FOREIGN KEY (created_by_org) REFERENCES organizations (organization_id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Campaign tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    campaign_id VARCHAR(255) PRIMARY KEY,
                    campaign_name VARCHAR(500) NOT NULL,
                    attribution VARCHAR(500) NULL,
                    target_sectors_json JSON NULL,
                    attack_vector VARCHAR(200) NULL,
                    payload_type VARCHAR(200) NULL,
                    campaign_start TIMESTAMP NULL,
                    estimated_victims INT NULL,
                    confidence TINYINT UNSIGNED NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            conn.commit()
            cursor.close()
            conn.close()
            self.logger.info(f"PyMySQL database initialized successfully")
                
        except pymysql.Error as e:
            self.logger.error(f"Database initialization error: {e}")
            raise FRANKConnectionError(f"Failed to initialize database: {e}")
    
    def hash_observable(self, observable_type: str, observable_value: str) -> str:
        """Create a hash for observable deduplication and quick lookups."""
        combined = f"{observable_type}:{observable_value}".lower()
        return hashlib.sha256(combined.encode()).hexdigest()

    def store_submission(self, submission: Submission) -> bool:
        """
        Store a complete submission in the database with full normalization.
        
        Args:
            submission: Complete FRANK submission dictionary
            
        Returns:
            True if stored successfully, False otherwise
        """
        self.logger.info(f"Storing submission: {submission.model_dump_json(exclude_none=True, exclude_defaults=True,by_alias=True)}...")
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Extract main submission data
            submitter = submission.submitter
            hit_target = submission.hit_target
            sighting = submission.sighting

            # Store or update organization
            self._upsert_organization(cursor, submitter.model_dump(
                    exclude_none=True,
                    by_alias=True), org_type='cyber_partner')
            
            # Store hit target if present
            hit_target_id = None
            if hit_target:
                self._upsert_organization(cursor, hit_target.model_dump(
                    exclude_none=True,
                    by_alias=True), org_type='customer')
                hit_target_id = hit_target.organization_id
            
            # Store main submission
            cursor.execute("""
                INSERT INTO submissions 
                (submission_id, submitter_org_id, hit_target_org_id, format_version, 
                 submission_timestamp, confidence, severity, tlp_level, full_submission_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                submitter_org_id = VALUES(submitter_org_id),
                hit_target_org_id = VALUES(hit_target_org_id),
                format_version = VALUES(format_version),
                submission_timestamp = VALUES(submission_timestamp),
                confidence = VALUES(confidence),
                severity = VALUES(severity),
                tlp_level = VALUES(tlp_level),
                full_submission_json = VALUES(full_submission_json)
            """, (
                submission.submission_id,
                submitter.organization_id,
                hit_target_id,
                submission.format_version,
                submission.timestamp,
                sighting.confidence,
                sighting.severity,
                submission.tlp_level,
                submission.model_dump_json(by_alias=True, exclude_none=True)
            ))
            
            # Store sighting
            cursor.execute("""
                INSERT INTO sightings 
                (sighting_id, submission_id, first_observed, last_observed, 
                 observation_count, confidence, severity, sigma_rule_id, campaign_id,
                 affected_systems, compromised_accounts, containment_time, financial_impact_eur
                 )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                submission_id = VALUES(submission_id),
                first_observed = VALUES(first_observed),
                last_observed = VALUES(last_observed),
                observation_count = VALUES(observation_count),
                confidence = VALUES(confidence),
                severity = VALUES(severity),
                sigma_rule_id = VALUES(sigma_rule_id),
                campaign_id = VALUES(campaign_id),
                affected_systems = VALUES(affected_systems),
                compromised_accounts = VALUES(compromised_accounts),
                containment_time = VALUES(containment_time),
                financial_impact_eur = VALUES(financial_impact_eur)
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
            
            # Store observables and update statistics
            self._store_observables(cursor, sighting, submitter) # type: ignore
            
            # Store SIGMA rule if present
            self._store_sigma_rule(cursor, sighting, submitter) # type: ignore
            
            # Store campaign if present
            self._store_campaign(cursor, sighting)

            # Log access
            self._log_access(cursor, submitter.organization_id, 'SUBMIT', 'submission', submission.submission_id)

            conn.commit()
            cursor.close()
            self.logger.info(f"Stored submission {submission.submission_id}")
            return True
                
        except pymysql.Error as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Error storing submission: {e}")
            raise FRANKStorageError(f"Failed to store submission: {e}")
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Unexpected error storing submission: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def _store_observables(self, cursor, sighting: Sighting, submitter: Submitter) -> None:
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
                    cursor.execute("""
                        INSERT INTO observables 
                        (observable_id, sighting_id, observable_type, observable_value, 
                         observable_hash, role, port, protocol, first_seen, metadata_json)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        sighting_id = VALUES(sighting_id),
                        observable_type = VALUES(observable_type),
                        observable_value = VALUES(observable_value),
                        observable_hash = VALUES(observable_hash),
                        role = VALUES(role),
                        port = VALUES(port),
                        protocol = VALUES(protocol),
                        first_seen = VALUES(first_seen),
                        metadata_json = VALUES(metadata_json)
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
                    self._update_observable_statistics(cursor, obs, submitter)

    def _store_sigma_rule(self, cursor, sighting: Sighting, submitter: Submitter) -> None:
        """Store SIGMA rule if present in sighting."""
        sigma_detection = sighting.sigma_detection
        if not sigma_detection:
            return
            
        cursor.execute("""
            INSERT INTO sigma_rules 
            (rule_id, rule_name, rule_version, rule_status, sigma_yaml, 
             created_by_org, effectiveness_score, false_positive_rate)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            rule_name = VALUES(rule_name),
            rule_version = VALUES(rule_version),
            rule_status = VALUES(rule_status),
            sigma_yaml = VALUES(sigma_yaml),
            created_by_org = VALUES(created_by_org),
            effectiveness_score = VALUES(effectiveness_score),
            false_positive_rate = VALUES(false_positive_rate)
        """, (
            sigma_detection.rule_id,
            sigma_detection.rule_name,
            sigma_detection.rule_version,
            sigma_detection.rule_status,
            sigma_detection.sigma_yaml,
            submitter.organization_id,
            sigma_detection.rule_effectiveness,
            sigma_detection.false_positive_rate
        ))

    def _store_campaign(self, cursor, sighting: Sighting) -> None:
        """Store campaign information if present."""
        if sighting.threat_context is None:
            return

        campaign = sighting.threat_context.campaign
        if not campaign:
            return
            
        cursor.execute("""
            INSERT INTO campaigns 
            (campaign_id, campaign_name, attribution, target_sectors_json, 
             attack_vector, payload_type, campaign_start, estimated_victims, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            campaign_name = VALUES(campaign_name),
            attribution = VALUES(attribution),
            target_sectors_json = VALUES(target_sectors_json),
            attack_vector = VALUES(attack_vector),
            payload_type = VALUES(payload_type),
            campaign_start = VALUES(campaign_start),
            estimated_victims = VALUES(estimated_victims),
            confidence = VALUES(confidence)
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

    def _upsert_organization(self, cursor, org_data: Dict[str, Any], org_type: str = 'cyber_partner') -> None:
        """Insert or update organization information."""
        self.logger.debug(f"Upserting organization: {org_data}")
        metadata = {k: v for k, v in org_data.items() 
                   if k not in ['organization_id', 'organization_type', 'tier', 'sector', 'region', 'client_count']}
        
        cursor.execute("""
            INSERT INTO organizations 
            (organization_id, organization_type, tier, sector, region, 
             last_active, client_count, metadata_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            organization_type = VALUES(organization_type),
            tier = VALUES(tier),
            sector = VALUES(sector),
            region = VALUES(region),
            last_active = VALUES(last_active),
            client_count = VALUES(client_count),
            metadata_json = VALUES(metadata_json)
        """, (
            org_data['organization_id'],
            org_data.get('organization_type', org_type),
            org_data.get('tier'),
            org_data.get('sector'),
            org_data.get('region'),
            datetime.now(timezone.utc),
            org_data.get('client_count', 0),
            json.dumps(metadata)
        ))
        self.logger.info(f"Upserted organization {org_data['organization_id']}")

    def _update_observable_statistics(self, cursor, observable: Dict[str, Any], submitter: Submitter) -> None:
        """Update aggregated statistics for observables."""
        obs_hash = self.hash_observable(observable['type'], observable['value'])
        
        # Check if statistics record exists
        cursor.execute("""
            SELECT total_sightings, unique_organizations, sectors_json, regions_json 
            FROM observable_statistics WHERE observable_hash = %s
        """, (obs_hash,))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing record
            total_sightings = existing['total_sightings']
            unique_orgs = existing['unique_organizations']
            sectors_json = existing['sectors_json']
            regions_json = existing['regions_json']
            
            # Parse existing JSON data
            sectors = json.loads(sectors_json) if sectors_json else []
            regions = json.loads(regions_json) if regions_json else []
            
            # Add new sector/region if not present
            if submitter.sector and submitter.sector not in sectors:
                sectors.append(submitter.sector)
            if submitter.region and submitter.region not in regions:
                regions.append(submitter.region)

            # Update statistics
            cursor.execute("""
                UPDATE observable_statistics 
                SET total_sightings = total_sightings + 1,
                    unique_organizations = %s,
                    last_seen = %s,
                    sectors_json = %s,
                    regions_json = %s,
                    updated_at = %s
                WHERE observable_hash = %s
            """, (
                unique_orgs + 1,  # Simplified - should track unique orgs properly
                datetime.now(timezone.utc),
                json.dumps(sectors),
                json.dumps(regions),
                datetime.now(timezone.utc),
                obs_hash
            ))
        else:
            # Create new statistics record
            sectors = [submitter.sector] if submitter.sector else []
            regions = [submitter.region] if submitter.region else []

            cursor.execute("""
                INSERT INTO observable_statistics 
                (observable_hash, observable_type, observable_value, total_sightings, 
                 unique_organizations, first_seen, last_seen, sectors_json, regions_json)
                VALUES (%s, %s, %s, 1, 1, %s, %s, %s, %s)
            """, (
                obs_hash,
                observable['type'],
                observable['value'],
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
                json.dumps(sectors),
                json.dumps(regions)
            ))

    def get_submission_by_id(self, submission_id: str, org_id: str, access_level: TierLevel = TierLevel.CONTRIBUTOR) -> Optional[Submission]:
        """
        Retrieve a specific submission with access level filtering.
        
        Args:
            submission_id: Submission ID to retrieve
            org_id: Organization ID making the request
            access_level: Access level for filtering
            
        Returns:
            Filtered Submission or None if not found
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT s.*, o.tier as submitter_tier
                FROM submissions s
                JOIN organizations o ON s.submitter_org_id = o.organization_id
                WHERE s.submission_id = %s
            """, (submission_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            submission_dict = json.loads(row['full_submission_json'])
            # Apply access level filtering
            filtered_submission = self._filter_submission_by_access_level(submission_dict, access_level)
            
            # Log access
            self._log_access(cursor, org_id, 'READ', 'submission', submission_id)
            conn.commit()
            cursor.close()
            
            return Submission(**filtered_submission['submission'])
                
        except pymysql.Error as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Error retrieving submission {submission_id}: {e}")
            raise FRANKQueryError(f"Failed to retrieve submission: {e}")
        finally:
            if conn:
                conn.close()

    def query_observables(self, org_id: str, observable_type: ObservableType = None, 
                         limit: int = 100, access_level: TierLevel = TierLevel.CONTRIBUTOR,
                         min_confidence: int = None, sectors: List[str] = None,
                         days_back: int = None) -> List[Dict[str, Any]]:
        """
        Query observables with access level filtering and advanced filters.
        
        Args:
            org_id: Organization ID making the query
            observable_type: Filter by observable type
            limit: Maximum number of results
            access_level: Access level for filtering
            min_confidence: Minimum confidence threshold
            sectors: Filter by affected sectors
            days_back: Only return observables from last N days
            
        Returns:
            List of filtered observable statistics
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Build query based on access level and filters
            query_parts = ["""
                SELECT os.observable_hash, os.observable_type, os.observable_value,
                       os.total_sightings, os.unique_organizations, os.first_seen, 
                       os.last_seen, os.avg_confidence, os.sectors_json, os.regions_json
                FROM observable_statistics os
            """]
            
            where_clauses = []
            params = []
            
            if observable_type:
                where_clauses.append("os.observable_type = %s")
                params.append(observable_type.value)
            
            if min_confidence:
                self.logger.info(f"finding min_confidence: {min_confidence}")
                where_clauses.append("COALESCE(os.avg_confidence, 0) >= %s")
                params.append(min_confidence)
            
            if days_back:
                where_clauses.append("os.last_seen >= DATE_SUB(NOW(), INTERVAL %s DAY)")
                params.append(days_back)
            
            if sectors:
                # Use JSON functions for proper sector filtering
                sector_conditions = []
                for sector in sectors:
                    sector_conditions.append("JSON_CONTAINS(COALESCE(os.sectors_json, '[]'), %s)")
                    params.append(json.dumps(sector))
                where_clauses.append(f"({' OR '.join(sector_conditions)})")
            
            if where_clauses:
                query_parts.append(" WHERE " + " AND ".join(where_clauses))
            
            query_parts.append(f" ORDER BY os.last_seen DESC LIMIT {limit}")
            
            query = "".join(query_parts)
            cursor.execute(query, params)
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
            self._log_access(cursor, org_id, 'QUERY', 'observables')
            conn.commit()
            cursor.close()
            
            self.logger.info(f"Retrieved {len(results)} observables for {org_id} (access: {access_level.value})")
            return results
                
        except pymysql.Error as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Error querying observables: {e}")
            raise FRANKQueryError(f"Failed to query observables: {e}")
        finally:
            if conn:
                conn.close()

    def get_statistics_summary(self, org_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get platform statistics summary.
        
        Args:
            org_id: Organization ID making the request
            days: Number of days to look back
            
        Returns:
            Statistics summary dictionary
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            stats = {}
            
            # Basic submission statistics
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT submission_id) as total_submissions,
                    COUNT(DISTINCT submitter_org_id) as active_organizations,
                    AVG(confidence) as avg_confidence
                FROM submissions 
                WHERE submission_timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (days,))
            
            basic_stats = cursor.fetchone()
            stats.update(basic_stats)
            
            # Observable type distribution
            cursor.execute("""
                SELECT observable_type, COUNT(*) as count,
                    AVG(total_sightings) as avg_sightings
                FROM observable_statistics
                WHERE updated_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY observable_type
                ORDER BY count DESC
                LIMIT 10
            """, (days,))

            stats['observable_types'] = {
                row['observable_type']: {'count': row['count'], 'avg_sightings': row['avg_sightings']} 
                for row in cursor.fetchall()
            }
                            
            # Severity distribution
            cursor.execute("""
                SELECT severity, COUNT(*) as count
                FROM submissions
                WHERE submission_timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
                AND severity IS NOT NULL
                GROUP BY severity
            """, (days,))
            
            stats['severity_distribution'] = {row['severity']: row['count'] for row in cursor.fetchall()}
            
            # Top sectors by activity
            cursor.execute("""
                SELECT sector, COUNT(*) as submissions
                FROM submissions s
                JOIN organizations o ON s.submitter_org_id = o.organization_id
                WHERE s.submission_timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
                AND o.sector IS NOT NULL
                GROUP BY sector
                ORDER BY submissions DESC
                LIMIT 5
            """, (days,))
            
            stats['top_sectors'] = {row['sector']: row['submissions'] for row in cursor.fetchall()}
            
            # Recent activity trend (daily counts)
            cursor.execute("""
                SELECT DATE(submission_timestamp) as date, COUNT(*) as count
                FROM submissions
                WHERE submission_timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY DATE(submission_timestamp)
                ORDER BY date DESC
            """, (days,))
            
            stats['daily_activity'] = {str(row['date']): row['count'] for row in cursor.fetchall()}
            
            # Log access
            self._log_access(cursor, org_id, 'STATS', 'summary')
            conn.commit()
            cursor.close()
            
            return stats
                
        except pymysql.Error as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Error getting statistics: {e}")
            raise FRANKQueryError(f"Failed to get statistics: {e}")
        finally:
            if conn:
                conn.close()

    def upsert_organization(self, org_data: Dict[str, Any]) -> bool:
        """
        Insert or update organization information.
        
        Args:
            org_data: Organization data dictionary
            
        Returns:
            True if successful
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            self._upsert_organization(conn, org_data)
            conn.commit()
            return True
        except pymysql.Error as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Error getting statistics: {e}")
            raise FRANKQueryError(f"Failed to get statistics: {e}")
        finally:
            if conn:
                conn.close()
        return False
    
    def _log_access(self, cursor, org_id: str, action: str, 
                   resource_type: str = None, resource_id: str = None, 
                   details: Dict[str, Any] = None) -> None:
        """Internal method to log access."""
        cursor.execute("""
            INSERT INTO access_logs 
            (organization_id, action, resource_type, resource_id, details_json)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            org_id,
            action,
            resource_type,
            resource_id,
            json.dumps(details) if details else None
        ))

    def _filter_submission_by_access_level(self, submission: Dict[str, Any], access_level: TierLevel) -> Dict[str, Any]:
        """Filter submission data based on access level."""
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

    def _filter_observable_by_access_level(self, observable: Dict[str, Any], access_level: TierLevel) -> Dict[str, Any]:
        """Filter observable data based on access level."""
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
    
    def _deep_copy(self, obj: Any) -> Any:
        """Create a deep copy of an object."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the database.
        
        Returns:
            Health status dictionary
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Basic connectivity test
            cursor.execute("SELECT 1 as test")
            cursor.fetchone()
            
            # Get database statistics
            table_counts = {}
            tables = ['organizations', 'submissions', 'sightings', 'observables', 
                     'observable_statistics', 'access_logs', 'sigma_rules', 'campaigns']
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                result = cursor.fetchone()
                table_counts[table] = result['count']
            
            # Check database size
            cursor.execute("""
                SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 1) AS 'size_mb'
                FROM information_schema.tables 
                WHERE table_schema = %s
            """, (self.connection_params['database'],))
            
            size_result = cursor.fetchone()
            db_size_mb = size_result['size_mb'] if size_result['size_mb'] else 0
            
            cursor.close()
            
            return {
                'status': 'healthy',
                'database_host': self.connection_params['host'],
                'database_name': self.connection_params['database'],
                'database_size_mb': float(db_size_mb),
                'table_counts': table_counts,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        finally:
            if conn:
                conn.close()


# Factory function for easy instantiation
def create_mysql_database(host: str = "localhost", port: int = 3306, 
                           database: str = "frank", user: str = "frank_user", 
                           password: str = "frank_password",
                           logger: Optional[logging.Logger] = None) -> MySQLFRANKDatabase:
    """
    Factory function to create a MySQLFRANKDatabase instance.
    
    Args:
        host: MySQL server hostname
        port: MySQL server port
        database: Database name
        user: Database username
        password: Database password
        
    Returns:
        Configured MySQLFRANKDatabase instance
    """

    # Set up logging
    if not logger:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)

    connection_params = {
        "host": host,
        "port": port,
        "database": database,
        "user": user,
        "password": password,
        'charset': 'utf8mb4',
        'autocommit': False,
        'cursorclass': pymysql.cursors.DictCursor
    }
    return MySQLFRANKDatabase(connection_params, logger=logger)