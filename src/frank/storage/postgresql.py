#!/usr/bin/env python3
"""
FRANK Platform - PostgreSQL Database Storage

PostgreSQL implementation for FRANK Management API data storage.
Handles organisations and organisation members.

Note: Authentication is handled by AWS Cognito. Service accounts are
Cognito users with 'service-*' naming convention stored as regular members.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

from frank.core.enum import AccessTier, ObservableType
from frank.core.models import Observable, Submission

from .base import BaseFRANKDatabase
from .exceptions import FRANKConnectionError


class PostgreSQLFRANKDatabase(BaseFRANKDatabase):
    """
    PostgreSQL implementation of FRANK database for Management API.

    Supports Management API operations:
    - Organisation management
    - Organisation member management (including service accounts)

    Authentication: AWS Cognito handles all authentication via JWT tokens.
    Service accounts are Cognito users with 'service-*' naming convention.

    Note: This implementation focuses on Management API tables only.
    Threat intelligence data (submissions, observables) uses DynamoDB.
    """

    def initialize(self) -> None:
        """Initialize PostgreSQL database connection and create schema."""
        self.name = 'postgresql'
        self.connection_string = self.connection_params.get('connection_string')

        if not self.connection_string:
            raise FRANKConnectionError("PostgreSQL connection_string is required")

        try:
            # Test connection and create tables
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    # Enable UUID extension
                    cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")

                    # Organisations table
                    cur.execute("""
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

                    # Organisation members table (includes service accounts)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS organisation_members (
                            id SERIAL PRIMARY KEY,
                            organisation_id TEXT NOT NULL,
                            username TEXT NOT NULL,
                            role TEXT NOT NULL CHECK (role IN ('member', 'admin', 'owner')),
                            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id) ON DELETE CASCADE,
                            UNIQUE(organisation_id, username)
                        )
                    """)

                    # Refresh tokens table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS refresh_tokens (
                            token_id TEXT PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            token_hash TEXT NOT NULL UNIQUE,
                            expires_at TIMESTAMP NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            is_revoked BOOLEAN DEFAULT FALSE
                        )
                    """)

                    # Create indexes
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_org_members_org_id ON organisation_members(organisation_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_org_members_username ON organisation_members(username)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash)")

                    conn.commit()

            self.logger.info(f"PostgreSQL database initialized: {self.connection_string.split('@')[1] if '@' in self.connection_string else 'local'}")

        except psycopg.Error as e:
            self.logger.error(f"Failed to initialize PostgreSQL database: {e}")
            raise FRANKConnectionError(f"PostgreSQL initialization failed: {e}")

    # ========== Organisation Management ==========

    def upsert_organisation(self, org_data: Dict[str, Any]) -> bool:
        """Insert or update organisation information."""
        try:
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO organisations
                        (organisation_id, organisation_type, access_level, sector, region,
                         contribution_score, client_count, metadata_json)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (organisation_id) DO UPDATE SET
                            organisation_type = EXCLUDED.organisation_type,
                            access_level = EXCLUDED.access_level,
                            sector = EXCLUDED.sector,
                            region = EXCLUDED.region,
                            contribution_score = EXCLUDED.contribution_score,
                            client_count = EXCLUDED.client_count,
                            metadata_json = EXCLUDED.metadata_json,
                            last_active = CURRENT_TIMESTAMP
                    """, (
                        org_data.get('organisation_id'),
                        org_data.get('organisation_type', 'customer'),
                        org_data.get('access_level', 'contributor'),
                        org_data.get('sector'),
                        org_data.get('region'),
                        org_data.get('contribution_score', 0),
                        org_data.get('client_count', 0),
                        json.dumps(org_data.get('metadata', {})) if org_data.get('metadata') else None
                    ))
                    conn.commit()
                    return True

        except psycopg.Error as e:
            self.logger.error(f"Error upserting organisation: {e}")
            return False

    def create_organisation(self, org_data: Dict[str, Any]) -> Optional[str]:
        """Create a new organisation."""
        organisation_id = org_data.get('organisation_id')
        if self.upsert_organisation(org_data):
            return organisation_id
        return None

    def get_organisation(self, organisation_id: str) -> Optional[Dict[str, Any]]:
        """Get organisation by ID."""
        try:
            with psycopg.connect(self.connection_string, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM organisations WHERE organisation_id = %s
                    """, (organisation_id,))
                    row = cur.fetchone()

                    if row:
                        # Parse metadata_json if present
                        if row.get('metadata_json'):
                            row['metadata'] = json.loads(row['metadata_json'])
                            del row['metadata_json']
                        return row
                    return None

        except psycopg.Error as e:
            self.logger.error(f"Error getting organisation: {e}")
            return None

    def list_organisations(self, **filters) -> List[Dict[str, Any]]:
        """List organisations with optional filters."""
        try:
            with psycopg.connect(self.connection_string, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    query = "SELECT * FROM organisations WHERE 1=1"
                    params = []

                    if filters.get('organisation_type'):
                        query += " AND organisation_type = %s"
                        params.append(filters['organisation_type'])

                    if filters.get('access_level'):
                        query += " AND access_level = %s"
                        params.append(filters['access_level'])

                    if filters.get('sector'):
                        query += " AND sector = %s"
                        params.append(filters['sector'])

                    query += " ORDER BY created_at DESC"

                    if filters.get('limit'):
                        query += f" LIMIT {int(filters['limit'])}"

                    cur.execute(query, params)
                    rows = cur.fetchall()

                    # Parse metadata_json for each row
                    for row in rows:
                        if row.get('metadata_json'):
                            row['metadata'] = json.loads(row['metadata_json'])
                            del row['metadata_json']

                    return rows

        except psycopg.Error as e:
            self.logger.error(f"Error listing organisations: {e}")
            return []

    def update_organisation(self, organisation_id: str, update_data: Dict[str, Any]) -> bool:
        """Update organisation fields."""
        try:
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    # Build dynamic UPDATE query
                    set_clauses = []
                    params = []

                    for field in ['organisation_type', 'access_level', 'sector', 'region',
                                  'contribution_score', 'client_count']:
                        if field in update_data:
                            set_clauses.append(f"{field} = %s")
                            params.append(update_data[field])

                    if 'metadata' in update_data:
                        set_clauses.append("metadata_json = %s")
                        params.append(json.dumps(update_data['metadata']))

                    if not set_clauses:
                        return True  # Nothing to update

                    set_clauses.append("last_active = CURRENT_TIMESTAMP")
                    params.append(organisation_id)

                    query = f"UPDATE organisations SET {', '.join(set_clauses)} WHERE organisation_id = %s"
                    cur.execute(query, params)
                    conn.commit()

                    return cur.rowcount > 0

        except psycopg.Error as e:
            self.logger.error(f"Error updating organisation: {e}")
            return False

    def delete_organisation(self, organisation_id: str) -> bool:
        """Delete organisation (cascades to members)."""
        try:
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM organisations WHERE organisation_id = %s", (organisation_id,))
                    conn.commit()
                    return cur.rowcount > 0

        except psycopg.Error as e:
            self.logger.error(f"Error deleting organisation: {e}")
            return False

    # ========== Organisation Member Management ==========

    def add_organisation_member(self, organisation_id: str, username: str, role: str = "member") -> Dict[str, Any]:
        """Add a user to an organisation."""
        from datetime import datetime

        try:
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO organisation_members (organisation_id, username, role)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (organisation_id, username) DO UPDATE SET
                            role = EXCLUDED.role
                        RETURNING organisation_id, username, role, joined_at
                    """, (organisation_id, username, role))

                    row = cur.fetchone()
                    conn.commit()

                    return {
                        "organisation_id": row[0],
                        "username": row[1],
                        "role": row[2],
                        "joined_at": row[3].isoformat() if row[3] else datetime.now(timezone.utc).isoformat()
                    }

        except psycopg.Error as e:
            self.logger.error(f"Error adding organisation member: {e}")
            from frank.storage.base import FRANKStorageError
            raise FRANKStorageError(f"Failed to add organisation member: {e}")

    def remove_organisation_member(self, organisation_id: str, username: str) -> bool:
        """Remove a user from an organisation."""
        try:
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM organisation_members
                        WHERE organisation_id = %s AND username = %s
                    """, (organisation_id, username))
                    conn.commit()
                    return cur.rowcount > 0

        except psycopg.Error as e:
            self.logger.error(f"Error removing organisation member: {e}")
            return False

    def get_organisation_members(self, organisation_id: str, role: str = None) -> List[Dict[str, Any]]:
        """Get all members of an organisation, optionally filtered by role."""
        try:
            with psycopg.connect(self.connection_string, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    if role:
                        cur.execute("""
                            SELECT organisation_id, username, role, joined_at
                            FROM organisation_members
                            WHERE organisation_id = %s AND role = %s
                            ORDER BY joined_at DESC
                        """, (organisation_id, role))
                    else:
                        cur.execute("""
                            SELECT organisation_id, username, role, joined_at
                            FROM organisation_members
                            WHERE organisation_id = %s
                            ORDER BY joined_at DESC
                        """, (organisation_id,))
                    return cur.fetchall()

        except psycopg.Error as e:
            self.logger.error(f"Error getting organisation members: {e}")
            return []

    def get_user_organisations(self, username: str) -> List[Dict[str, Any]]:
        """Get all organisations a user belongs to."""
        try:
            with psycopg.connect(self.connection_string, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT o.organisation_id, o.organisation_type, o.access_level,
                               o.sector, o.region, m.role, m.joined_at
                        FROM organisation_members m
                        JOIN organisations o ON m.organisation_id = o.organisation_id
                        WHERE m.username = %s
                        ORDER BY m.joined_at DESC
                    """, (username,))
                    return cur.fetchall()

        except psycopg.Error as e:
            self.logger.error(f"Error getting user organisations: {e}")
            return []

    def get_organisation_member(self, organisation_id: str, username: str) -> Optional[Dict[str, Any]]:
        """Get a specific organisation member."""
        try:
            with psycopg.connect(self.connection_string, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT username, role, joined_at
                        FROM organisation_members
                        WHERE organisation_id = %s AND username = %s
                    """, (organisation_id, username))
                    return cur.fetchone()

        except psycopg.Error as e:
            self.logger.error(f"Error getting organisation member: {e}")
            return None

    # ========== Refresh Token Management ==========

    def store_refresh_token(self, user_id: str, token_id: str, token_hash: str,
                           expires_at: datetime) -> bool:
        """Store a refresh token."""
        try:
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO refresh_tokens (token_id, user_id, token_hash, expires_at)
                        VALUES (%s, %s, %s, %s)
                    """, (token_id, user_id, token_hash, expires_at))
                    conn.commit()
                    return True

        except psycopg.Error as e:
            self.logger.error(f"Error storing refresh token: {e}")
            return False

    def get_refresh_token(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Get refresh token by token ID."""
        try:
            with psycopg.connect(self.connection_string, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM refresh_tokens
                        WHERE token_id = %s AND is_revoked = FALSE
                    """, (token_id,))
                    return cur.fetchone()

        except psycopg.Error as e:
            self.logger.error(f"Error getting refresh token: {e}")
            return None

    def revoke_refresh_token(self, token_id: str) -> bool:
        """Revoke a specific refresh token."""
        try:
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE refresh_tokens SET is_revoked = TRUE WHERE token_id = %s
                    """, (token_id,))
                    conn.commit()
                    return cur.rowcount > 0

        except psycopg.Error as e:
            self.logger.error(f"Error revoking refresh token: {e}")
            return False

    def revoke_all_user_refresh_tokens(self, user_id: str) -> int:
        """Revoke all refresh tokens for a user."""
        try:
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE refresh_tokens
                        SET is_revoked = TRUE
                        WHERE user_id = %s AND is_revoked = FALSE
                    """, (user_id,))
                    conn.commit()
                    return cur.rowcount

        except psycopg.Error as e:
            self.logger.error(f"Error revoking user refresh tokens: {e}")
            return 0

    # ========== Audit Logging ==========

    def log_access(self, org_id: str, action: str,
                   resource_type: str = None, resource_id: str = None,
                   details: Dict[str, Any] = None) -> bool:
        """Log an access event (placeholder - implement if audit logging needed)."""
        # For now, just log to application logger
        self.logger.debug(f"Access: org={org_id}, action={action}, resource={resource_type}:{resource_id}")
        return True

    # ========== Unimplemented Methods (Not Used by Management API) ==========

    def store_submission(self, submission: Submission) -> None:
        """Not implemented - submissions use DynamoDB."""
        raise NotImplementedError("Submissions are stored in DynamoDB, not PostgreSQL")

    def get_submission_by_id(self, submission_id: str) -> Dict[str, Any]:
        """Not implemented - submissions use DynamoDB."""
        raise NotImplementedError("Submissions are stored in DynamoDB, not PostgreSQL")

    def query_observables(self, org_id: str, observable_type: ObservableType = None,
                         limit: int = 100, access_level: AccessTier = AccessTier.CONTRIBUTOR,
                         min_confidence: float = None, sectors: List[str] = None,
                         days_back: int = None) -> List[Observable]:
        """Not implemented - observables use DynamoDB."""
        raise NotImplementedError("Observables are stored in DynamoDB, not PostgreSQL")

    def search_observables_by_value(self, org_id: str, search_value: str,
                                    access_level: AccessTier = AccessTier.CONTRIBUTOR) -> List[Dict[str, Any]]:
        """Not implemented - observables use DynamoDB."""
        raise NotImplementedError("Observables are stored in DynamoDB, not PostgreSQL")

    def get_statistics_summary(self, org_id: str, days: int = 30) -> Dict[str, Any]:
        """Not implemented - statistics use DynamoDB."""
        raise NotImplementedError("Statistics are stored in DynamoDB, not PostgreSQL")

    def health_check(self) -> Dict[str, Any]:
        """Check PostgreSQL database health."""
        try:
            with psycopg.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                    return {
                        "status": "healthy",
                        "database": "postgresql",
                        "message": "PostgreSQL connection successful"
                    }
        except psycopg.Error as e:
            return {
                "status": "unhealthy",
                "database": "postgresql",
                "error": str(e)
            }


def create_postgresql_database(connection_string: str,
                               logger: Optional[logging.Logger] = None) -> PostgreSQLFRANKDatabase:
    """
    Factory function to create a PostgreSQLFRANKDatabase instance.

    Args:
        connection_string: PostgreSQL connection string (e.g., postgresql://user:pass@host:port/db)
        logger: Optional logger instance

    Returns:
        Configured PostgreSQLFRANKDatabase instance

    Example:
        db = create_postgresql_database("postgresql://frank:password@localhost:5432/frank_management")
    """
    connection_params = {
        "connection_string": connection_string
    }

    # Set up logging
    if not logger:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)

    return PostgreSQLFRANKDatabase(connection_params, logger=logger)
