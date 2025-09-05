import json
import sqlite3
import uuid
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import logging
from pathlib import Path

from frank.db.sqlite import SQLiteFRANKDatabase
from frank.db.client import create_client
from frank.utils.sample_builder import generate_minimal_submission

# Default configuration
DEFAULT_CONFIG = {
    'database_type': 'sqlite',
    'database_path': '/tmp/frank.db',
    'log_level': 'INFO',
    'default_tier': 'contributor',
    'retention_days': 90
}


# # Set up logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)


# class FRANKDatabaseError(Exception):
#     """Base exception for FRANK database operations."""
#     pass

# class FRANKConfigurationError(FRANKDatabaseError):
#     """Raised when database configuration fails."""
#     pass

# class FRANKConnectionError(FRANKDatabaseError):
#     """Raised when database connection fails."""
#     pass


# class FRANKStorageError(FRANKDatabaseError):
#     """Raised when storage operations fail."""
#     pass


# class FRANKQueryError(FRANKDatabaseError):
#     """Raised when query operations fail."""
#     pass


# class BaseFRANKDatabase(ABC):
#     """
#     Abstract base class defining the interface for FRANK database operations.
#     Supports both SQLite and DynamoDB implementations with consistent API.
#     """
    
#     def __init__(self, connection_params: Dict[str, Any]):
#         self.connection_params = connection_params
#         self.logger = logging.getLogger(self.__class__.__name__)
#         self.initialize()
    
#     @abstractmethod
#     def initialize(self) -> None:
#         """Initialize database connection and schema."""
#         pass
    
#     @abstractmethod
#     def store_submission(self, submission: Dict[str, Any]) -> bool:
#         """Store a complete submission in the database."""
#         pass
    
#     @abstractmethod
#     def get_submission_by_id(self, submission_id: str, org_id: str, access_level: str = 'contributor') -> Optional[Dict[str, Any]]:
#         """Retrieve a specific submission with access level filtering."""
#         pass
    
#     @abstractmethod
#     def query_observables(self, org_id: str, observable_type: str = None, 
#                          limit: int = 100, access_level: str = 'contributor') -> List[Dict[str, Any]]:
#         """Query observables with access level filtering."""
#         pass
    
#     @abstractmethod
#     def get_statistics_summary(self, org_id: str, days: int = 30) -> Dict[str, Any]:
#         """Get platform statistics summary."""
#         pass
    
#     @abstractmethod
#     def upsert_organization(self, org_data: Dict[str, Any]) -> bool:
#         """Insert or update organization information."""
#         pass
    
#     @abstractmethod
#     def log_access(self, org_id: str, action: str, resource_type: str = None, resource_id: str = None) -> bool:
#         """Log access for auditing purposes."""
#         pass
    
#     @abstractmethod
#     def cleanup_old_data(self, days: int = 90) -> int:
#         """Clean up old data according to retention policies."""
#         pass
    
#     def hash_observable(self, observable_type: str, observable_value: str) -> str:
#         """Create a hash for observable deduplication and quick lookups."""
#         combined = f"{observable_type}:{observable_value}".lower()
#         return hashlib.sha256(combined.encode()).hexdigest()

# def create_database(db_type: str = "sqlite", **kwargs) -> BaseFRANKDatabase:
#     """
#     Factory function to create appropriate database backend.
    
#     Args:
#         db_type: Type of database backend ('sqlite' or 'dynamodb')
#         **kwargs: Database-specific configuration parameters
        
#     Returns:
#         Configured database instance
        
#     Raises:
#         FRANKConfigurationError: If invalid db_type or missing parameters
#         FRANKConnectionError: If database connection fails
        
#     Examples:
#         # SQLite for development
#         db = create_database('sqlite', database_path='frank_dev.db')
        
#         # DynamoDB for production
#         db = create_database('dynamodb', 
#                            table_prefix='frank-prod',
#                            region='us-east-1')
#     """
    
#     if db_type.lower() == 'sqlite':
#         try:
            
#             # Extract SQLite-specific parameters
#             db_path = kwargs.get('database_path', kwargs.get('db_path', 'frank_local.db'))
            
#             logger.info(f"Creating SQLite database at {db_path}")
#             return SQLiteFRANKDatabase(db_path)
            
#         except ImportError as e:
#             raise FRANKConfigurationError(f"SQLite backend not available: {e}")
#         except Exception as e:
#             raise FRANKConnectionError(f"Failed to create SQLite database: {e}")
    
#     elif db_type.lower() == 'dynamodb':
#         try:
            
#             # Extract DynamoDB-specific parameters
#             required_params = ['table_prefix']
#             for param in required_params:
#                 if param not in kwargs:
#                     raise FRANKConfigurationError(f"Missing required parameter for DynamoDB: {param}")
            
#             logger.info(f"Creating DynamoDB database with prefix {kwargs['table_prefix']}")
#             return DynamoDBFRANKDatabase(kwargs)
            
#         except ImportError as e:
#             raise FRANKConfigurationError(f"DynamoDB backend not available: {e}")
#         except Exception as e:
#             raise FRANKConnectionError(f"Failed to create DynamoDB database: {e}")
    
#     else:
#         raise FRANKConfigurationError(
#             f"Unknown database type '{db_type}'. Supported types: 'sqlite', 'dynamodb'"
#         )


# def create_sqlite_database(db_path: str = "frank_local.db") -> BaseFRANKDatabase:
#     """
#     Convenience function to create SQLite database.
    
#     Args:
#         db_path: Path to SQLite database file
        
#     Returns:
#         SQLite database instance
#     """
#     return create_database('sqlite', database_path=db_path)


# def create_dynamodb_database(table_prefix: str, region: str = 'us-east-1', 
#                             **kwargs) -> BaseFRANKDatabase:
#     """
#     Convenience function to create DynamoDB database.
    
#     Args:
#         table_prefix: Prefix for DynamoDB table names
#         region: AWS region
#         **kwargs: Additional DynamoDB configuration
        
#     Returns:
#         DynamoDB database instance
#     """
#     config = {
#         'table_prefix': table_prefix,
#         'region': region,
#         **kwargs
#     }
#     return create_database('dynamodb', **config)


# # Database configuration helpers
# def get_database_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Extract database configuration from a larger config dictionary.
    
#     Args:
#         config_dict: Full configuration dictionary
        
#     Returns:
#         Database-specific configuration
#     """
#     db_config = {}
    
#     # Extract database-related keys
#     for key, value in config_dict.items():
#         if key.startswith('database_') or key.startswith('db_'):
#             db_config[key] = value
    
#     # Map common configuration patterns
#     if 'DATABASE_URL' in config_dict:
#         db_config['database_url'] = config_dict['DATABASE_URL']
    
#     if 'AWS_REGION' in config_dict:
#         db_config['region'] = config_dict['AWS_REGION']
    
#     return db_config


# def validate_database_config(db_type: str, config: Dict[str, Any]) -> List[str]:
#     """
#     Validate database configuration for specific backend type.
    
#     Args:
#         db_type: Database backend type
#         config: Configuration dictionary
        
#     Returns:
#         List of validation errors (empty if valid)
#     """
#     errors = []
    
#     if db_type.lower() == 'sqlite':
#         # SQLite validation
#         db_path = config.get('database_path', config.get('db_path'))
#         if not db_path:
#             errors.append("SQLite requires 'database_path' or 'db_path' parameter")
#         elif not isinstance(db_path, str):
#             errors.append("database_path must be a string")
    
#     elif db_type.lower() == 'dynamodb':
#         # DynamoDB validation
#         if 'table_prefix' not in config:
#             errors.append("DynamoDB requires 'table_prefix' parameter")
#         elif not isinstance(config['table_prefix'], str):
#             errors.append("table_prefix must be a string")
        
#         if 'region' in config and not isinstance(config['region'], str):
#             errors.append("region must be a string")
    
#     else:
#         errors.append(f"Unknown database type: {db_type}")
    
#     return errors


# class SQLiteFRANKDatabase(BaseFRANKDatabase):
#     """
#     SQLite implementation of FRANK database for local development.
#     Provides full functionality with file-based storage and supports
#     the complete FRANK access tier model.
#     """
    
#     def __init__(self, db_path: str = "frank_local.db"):
#         """
#         Initialize SQLite database connection.
        
#         Args:
#             db_path: Path to SQLite database file
#         """
#         self.db_path = db_path
#         self.logger = logging.getLogger(self.__class__.__name__)
#         self.initialize()
    
#     def initialize(self) -> None:
#         """Initialize the SQLite database with FRANK schema."""
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.execute("PRAGMA foreign_keys = ON")
#                 conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
                
#                 # Organizations table (cyber partners and customers)
#                 conn.execute("""
#                     CREATE TABLE IF NOT EXISTS organizations (
#                         organization_id TEXT PRIMARY KEY,
#                         organization_type TEXT NOT NULL CHECK (organization_type IN ('cyber_partner', 'customer')),
#                         tier TEXT CHECK (tier IN ('public', 'observer', 'contributor', 'partner', 'core_member')),
#                         sector TEXT,
#                         region TEXT,
#                         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                         last_active TIMESTAMP,
#                         contribution_score INTEGER DEFAULT 0,
#                         client_count INTEGER DEFAULT 0,
#                         metadata_json TEXT
#                     )
#                 """)
                
#                 # Submissions table (main submission data)
#                 conn.execute("""
#                     CREATE TABLE IF NOT EXISTS submissions (
#                         submission_id TEXT PRIMARY KEY,
#                         submitter_org_id TEXT NOT NULL,
#                         hit_target_org_id TEXT,
#                         format_version TEXT DEFAULT '1.0',
#                         submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                         confidence INTEGER CHECK (confidence >= 0 AND confidence <= 100),
#                         severity TEXT CHECK (severity IN ('low', 'medium', 'high', 'critical')),
#                         tlp_level TEXT CHECK (tlp_level IN ('RED', 'AMBER+', 'AMBER', 'GREEN', 'CLEAR')),
#                         full_submission_json TEXT NOT NULL,
#                         processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                         FOREIGN KEY (submitter_org_id) REFERENCES organizations (organization_id),
#                         FOREIGN KEY (hit_target_org_id) REFERENCES organizations (organization_id)
#                     )
#                 """)
                
#                 # Sightings table (individual threat sightings)
#                 conn.execute("""
#                     CREATE TABLE IF NOT EXISTS sightings (
#                         sighting_id TEXT PRIMARY KEY,
#                         submission_id TEXT NOT NULL,
#                         first_observed TIMESTAMP,
#                         last_observed TIMESTAMP,
#                         observation_count INTEGER DEFAULT 1,
#                         confidence INTEGER,
#                         severity TEXT,
#                         sigma_rule_id TEXT,
#                         campaign_id TEXT,
#                         FOREIGN KEY (submission_id) REFERENCES submissions (submission_id) ON DELETE CASCADE
#                     )
#                 """)
                
#                 # Observables table (IoCs and artifacts)
#                 conn.execute("""
#                     CREATE TABLE IF NOT EXISTS observables (
#                         observable_id TEXT PRIMARY KEY,
#                         sighting_id TEXT NOT NULL,
#                         observable_type TEXT NOT NULL CHECK (observable_type IN ('ipv4', 'ipv6', 'domain', 'url', 'file_hash', 'email', 'registry_key')),
#                         observable_value TEXT NOT NULL,
#                         observable_hash TEXT NOT NULL, -- for quick lookups and deduplication
#                         role TEXT,
#                         port INTEGER,
#                         protocol TEXT,
#                         first_seen TIMESTAMP,
#                         metadata_json TEXT,
#                         FOREIGN KEY (sighting_id) REFERENCES sightings (sighting_id) ON DELETE CASCADE
#                     )
#                 """)
                
#                 # Statistics table (aggregated sighting data)
#                 conn.execute("""
#                     CREATE TABLE IF NOT EXISTS observable_statistics (
#                         id INTEGER PRIMARY KEY AUTOINCREMENT,
#                         observable_hash TEXT NOT NULL,
#                         observable_type TEXT NOT NULL,
#                         observable_value TEXT NOT NULL,
#                         total_sightings INTEGER DEFAULT 1,
#                         unique_organizations INTEGER DEFAULT 1,
#                         first_seen TIMESTAMP,
#                         last_seen TIMESTAMP,
#                         avg_confidence REAL,
#                         sectors_json TEXT, -- JSON array of affected sectors
#                         regions_json TEXT, -- JSON array of affected regions
#                         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                         updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                         UNIQUE(observable_hash)
#                     )
#                 """)
                
#                 # Access logs for auditing
#                 conn.execute("""
#                     CREATE TABLE IF NOT EXISTS access_logs (
#                         id INTEGER PRIMARY KEY AUTOINCREMENT,
#                         organization_id TEXT NOT NULL,
#                         action TEXT NOT NULL,
#                         resource_type TEXT,
#                         resource_id TEXT,
#                         timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                         access_level TEXT,
#                         success BOOLEAN DEFAULT TRUE,
#                         ip_address TEXT,
#                         user_agent TEXT,
#                         details_json TEXT
#                     )
#                 """)
                
#                 # SIGMA rules table
#                 conn.execute("""
#                     CREATE TABLE IF NOT EXISTS sigma_rules (
#                         rule_id TEXT PRIMARY KEY,
#                         rule_name TEXT NOT NULL,
#                         rule_version TEXT,
#                         rule_status TEXT CHECK (rule_status IN ('stable', 'test', 'experimental')),
#                         sigma_yaml TEXT NOT NULL,
#                         created_by_org TEXT,
#                         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                         updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                         effectiveness_score REAL,
#                         false_positive_rate REAL,
#                         FOREIGN KEY (created_by_org) REFERENCES organizations (organization_id)
#                     )
#                 """)
                
#                 # Campaign tracking table
#                 conn.execute("""
#                     CREATE TABLE IF NOT EXISTS campaigns (
#                         campaign_id TEXT PRIMARY KEY,
#                         campaign_name TEXT NOT NULL,
#                         attribution TEXT,
#                         target_sectors_json TEXT,
#                         attack_vector TEXT,
#                         payload_type TEXT,
#                         campaign_start TIMESTAMP,
#                         estimated_victims INTEGER,
#                         confidence INTEGER,
#                         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                         updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#                     )
#                 """)
                
#                 # Create indexes for performance
#                 self._create_indexes(conn)
                
#                 conn.commit()
#                 self.logger.info(f"Database initialized at {self.db_path}")
                
#         except sqlite3.Error as e:
#             self.logger.error(f"Database initialization error: {e}")
#             raise FRANKConnectionError(f"Failed to initialize database: {e}")
    
#     def _create_indexes(self, conn: sqlite3.Connection) -> None:
#         """Create database indexes for optimal query performance."""
#         indexes = [
#             "CREATE INDEX IF NOT EXISTS idx_submissions_submitter ON submissions (submitter_org_id)",
#             "CREATE INDEX IF NOT EXISTS idx_submissions_timestamp ON submissions (submission_timestamp)",
#             "CREATE INDEX IF NOT EXISTS idx_submissions_severity ON submissions (severity)",
#             "CREATE INDEX IF NOT EXISTS idx_submissions_tlp ON submissions (tlp_level)",
            
#             "CREATE INDEX IF NOT EXISTS idx_sightings_submission ON sightings (submission_id)",
#             "CREATE INDEX IF NOT EXISTS idx_sightings_confidence ON sightings (confidence)",
#             "CREATE INDEX IF NOT EXISTS idx_sightings_observed ON sightings (first_observed)",
            
#             "CREATE INDEX IF NOT EXISTS idx_observables_hash ON observables (observable_hash)",
#             "CREATE INDEX IF NOT EXISTS idx_observables_type ON observables (observable_type)",
#             "CREATE INDEX IF NOT EXISTS idx_observables_sighting ON observables (sighting_id)",
#             "CREATE INDEX IF NOT EXISTS idx_observables_value ON observables (observable_value)",
            
#             "CREATE INDEX IF NOT EXISTS idx_statistics_hash ON observable_statistics (observable_hash)",
#             "CREATE INDEX IF NOT EXISTS idx_statistics_type ON observable_statistics (observable_type)",
#             "CREATE INDEX IF NOT EXISTS idx_statistics_updated ON observable_statistics (updated_at)",
            
#             "CREATE INDEX IF NOT EXISTS idx_access_logs_org ON access_logs (organization_id)",
#             "CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON access_logs (timestamp)",
#             "CREATE INDEX IF NOT EXISTS idx_access_logs_action ON access_logs (action)",
            
#             "CREATE INDEX IF NOT EXISTS idx_organizations_tier ON organizations (tier)",
#             "CREATE INDEX IF NOT EXISTS idx_organizations_sector ON organizations (sector)",
#             "CREATE INDEX IF NOT EXISTS idx_organizations_active ON organizations (last_active)"
#         ]
        
#         for index_sql in indexes:
#             try:
#                 conn.execute(index_sql)
#             except sqlite3.Error as e:
#                 self.logger.warning(f"Failed to create index: {e}")
    
#     def hash_observable(self, observable_type: str, observable_value: str) -> str:
#         """Create a hash for observable deduplication and quick lookups."""
#         combined = f"{observable_type}:{observable_value}".lower()
#         return hashlib.sha256(combined.encode()).hexdigest()
    
#     def store_submission(self, submission: Dict[str, Any]) -> bool:
#         """
#         Store a complete submission in the database with full normalization.
        
#         Args:
#             submission: Complete FRANK submission dictionary
            
#         Returns:
#             True if stored successfully, False otherwise
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.execute("PRAGMA foreign_keys = ON")
                
#                 # Extract main submission data
#                 sub_data = submission['submission']
#                 submitter = sub_data['submitter']
#                 sighting = sub_data['sighting']
#                 metadata = sub_data.get('metadata', {})
                
#                 submission_id = metadata.get('submission_id', f"submission-{uuid.uuid4()}")
                
#                 # Store or update organization
#                 self._upsert_organization(conn, submitter)
                
#                 # Store hit target if present
#                 hit_target = sub_data.get('hit_target')
#                 hit_target_id = None
#                 if hit_target:
#                     self._upsert_organization(conn, hit_target, org_type='customer')
#                     hit_target_id = hit_target['organization_id']
                
#                 # Store main submission
#                 conn.execute("""
#                     INSERT OR REPLACE INTO submissions 
#                     (submission_id, submitter_org_id, hit_target_org_id, format_version, 
#                      submission_timestamp, confidence, severity, tlp_level, full_submission_json)
#                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#                 """, (
#                     submission_id,
#                     submitter['organization_id'],
#                     hit_target_id,
#                     metadata.get('format_version', '1.0'),
#                     metadata.get('timestamp', datetime.now(timezone.utc).isoformat()),
#                     sighting.get('confidence'),
#                     sighting.get('severity'),
#                     sub_data.get('sharing', {}).get('distribution_level'),
#                     json.dumps(submission)
#                 ))
                
#                 # Store sighting
#                 conn.execute("""
#                     INSERT OR REPLACE INTO sightings 
#                     (sighting_id, submission_id, first_observed, last_observed, 
#                      observation_count, confidence, severity, sigma_rule_id, campaign_id)
#                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#                 """, (
#                     sighting['sighting_id'],
#                     submission_id,
#                     sighting.get('first_observed'),
#                     sighting.get('last_observed'),
#                     sighting.get('observation_count', 1),
#                     sighting.get('confidence'),
#                     sighting.get('severity'),
#                     sighting.get('sigma_detection', {}).get('rule_id'),
#                     sighting.get('threat_context', {}).get('campaign', {}).get('id')
#                 ))
                
#                 # Store observables and update statistics
#                 self._store_observables(conn, sighting, submitter)
                
#                 # Store SIGMA rule if present
#                 self._store_sigma_rule(conn, sighting, submitter)
                
#                 # Store campaign if present
#                 self._store_campaign(conn, sighting)
                
#                 # Log access
#                 self._log_access(conn, submitter['organization_id'], 'SUBMIT', 'submission', submission_id)
                
#                 conn.commit()
#                 self.logger.info(f"Stored submission {submission_id}")
#                 return True
                
#         except sqlite3.Error as e:
#             self.logger.error(f"Error storing submission: {e}")
#             raise FRANKStorageError(f"Failed to store submission: {e}")
#         except Exception as e:
#             self.logger.error(f"Unexpected error storing submission: {e}")
#             return False
    
#     def _store_observables(self, conn: sqlite3.Connection, sighting: Dict[str, Any], submitter: Dict[str, Any]) -> None:
#         """Store observables and update statistics."""
#         observables = sighting.get('observables', {})
        
#         for obs_category, obs_list in observables.items():
#             if isinstance(obs_list, list):
#                 for obs in obs_list:
#                     if 'type' not in obs or 'value' not in obs:
#                         continue
                        
#                     obs_hash = self.hash_observable(obs['type'], obs['value'])
                    
#                     # Store observable
#                     conn.execute("""
#                         INSERT OR REPLACE INTO observables 
#                         (observable_id, sighting_id, observable_type, observable_value, 
#                          observable_hash, role, port, protocol, first_seen, metadata_json)
#                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#                     """, (
#                         obs.get('id', f"obs-{uuid.uuid4()}"),
#                         sighting['sighting_id'],
#                         obs['type'],
#                         obs['value'],
#                         obs_hash,
#                         obs.get('role'),
#                         obs.get('port'),
#                         obs.get('protocol'),
#                         obs.get('first_seen'),
#                         json.dumps({k: v for k, v in obs.items() 
#                                    if k not in ['id', 'type', 'value', 'role', 'port', 'protocol', 'first_seen']})
#                     ))
                    
#                     # Update statistics
#                     self._update_observable_statistics(conn, obs, submitter)
    
#     def _store_sigma_rule(self, conn: sqlite3.Connection, sighting: Dict[str, Any], submitter: Dict[str, Any]) -> None:
#         """Store SIGMA rule if present in sighting."""
#         sigma_detection = sighting.get('sigma_detection')
#         if not sigma_detection:
#             return
            
#         conn.execute("""
#             INSERT OR REPLACE INTO sigma_rules 
#             (rule_id, rule_name, rule_version, rule_status, sigma_yaml, 
#              created_by_org, effectiveness_score, false_positive_rate)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#         """, (
#             sigma_detection.get('rule_id'),
#             sigma_detection.get('rule_name'),
#             sigma_detection.get('rule_version'),
#             sigma_detection.get('rule_status'),
#             sigma_detection.get('sigma_yaml'),
#             submitter['organization_id'],
#             sigma_detection.get('rule_effectiveness'),
#             sigma_detection.get('false_positive_rate')
#         ))
    
#     def _store_campaign(self, conn: sqlite3.Connection, sighting: Dict[str, Any]) -> None:
#         """Store campaign information if present."""
#         threat_context = sighting.get('threat_context', {})
#         campaign = threat_context.get('campaign')
        
#         if not campaign:
#             return
            
#         conn.execute("""
#             INSERT OR REPLACE INTO campaigns 
#             (campaign_id, campaign_name, attribution, target_sectors_json, 
#              attack_vector, payload_type, campaign_start, estimated_victims, confidence)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#         """, (
#             campaign.get('id'),
#             campaign.get('name'),
#             campaign.get('attribution'),
#             json.dumps(campaign.get('target_sectors', [])),
#             campaign.get('attack_vector'),
#             campaign.get('payload_type'),
#             campaign.get('campaign_start'),
#             campaign.get('estimated_victims'),
#             campaign.get('confidence')
#         ))
    
#     def _upsert_organization(self, conn: sqlite3.Connection, org_data: Dict[str, Any], org_type: str = 'cyber_partner') -> None:
#         """Insert or update organization information."""
#         metadata = {k: v for k, v in org_data.items() 
#                    if k not in ['organization_id', 'organization_type', 'tier', 'sector', 'region', 'client_count']}
        
#         conn.execute("""
#             INSERT OR REPLACE INTO organizations 
#             (organization_id, organization_type, tier, sector, region, 
#              last_active, client_count, metadata_json)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#         """, (
#             org_data['organization_id'],
#             org_data.get('organization_type', org_type),
#             org_data.get('tier'),
#             org_data.get('sector'),
#             org_data.get('region'),
#             datetime.now(timezone.utc).isoformat(),
#             org_data.get('client_count', 0),
#             json.dumps(metadata)
#         ))
    
#     def _update_observable_statistics(self, conn: sqlite3.Connection, observable: Dict[str, Any], submitter: Dict[str, Any]) -> None:
#         """Update aggregated statistics for observables."""
#         obs_hash = self.hash_observable(observable['type'], observable['value'])
        
#         # Check if statistics record exists
#         cursor = conn.execute("""
#             SELECT total_sightings, unique_organizations, sectors_json, regions_json 
#             FROM observable_statistics WHERE observable_hash = ?
#         """, (obs_hash,))
        
#         existing = cursor.fetchone()
        
#         if existing:
#             # Update existing record
#             total_sightings, unique_orgs, sectors_json, regions_json = existing
            
#             # Parse existing JSON data
#             sectors = json.loads(sectors_json) if sectors_json else []
#             regions = json.loads(regions_json) if regions_json else []
            
#             # Add new sector/region if not present
#             if submitter.get('sector') and submitter['sector'] not in sectors:
#                 sectors.append(submitter['sector'])
#             if submitter.get('region') and submitter['region'] not in regions:
#                 regions.append(submitter['region'])
            
#             # Update statistics
#             conn.execute("""
#                 UPDATE observable_statistics 
#                 SET total_sightings = total_sightings + 1,
#                     unique_organizations = ?,
#                     last_seen = ?,
#                     sectors_json = ?,
#                     regions_json = ?,
#                     updated_at = ?
#                 WHERE observable_hash = ?
#             """, (
#                 unique_orgs + 1,  # Simplified - should track unique orgs properly
#                 datetime.now(timezone.utc).isoformat(),
#                 json.dumps(sectors),
#                 json.dumps(regions),
#                 datetime.now(timezone.utc).isoformat(),
#                 obs_hash
#             ))
#         else:
#             # Create new statistics record
#             sectors = [submitter.get('sector')] if submitter.get('sector') else []
#             regions = [submitter.get('region')] if submitter.get('region') else []
            
#             conn.execute("""
#                 INSERT INTO observable_statistics 
#                 (observable_hash, observable_type, observable_value, total_sightings, 
#                  unique_organizations, first_seen, last_seen, sectors_json, regions_json)
#                 VALUES (?, ?, ?, 1, 1, ?, ?, ?, ?)
#             """, (
#                 obs_hash,
#                 observable['type'],
#                 observable['value'],
#                 datetime.now(timezone.utc).isoformat(),
#                 datetime.now(timezone.utc).isoformat(),
#                 json.dumps(sectors),
#                 json.dumps(regions)
#             ))
    
#     def get_submission_by_id(self, submission_id: str, org_id: str, access_level: str = 'contributor') -> Optional[Dict[str, Any]]:
#         """
#         Retrieve a specific submission with access level filtering.
        
#         Args:
#             submission_id: Submission ID to retrieve
#             org_id: Organization ID making the request
#             access_level: Access level for filtering
            
#         Returns:
#             Filtered submission dictionary or None if not found
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.row_factory = sqlite3.Row
                
#                 cursor = conn.execute("""
#                     SELECT s.*, o.tier as submitter_tier
#                     FROM submissions s
#                     JOIN organizations o ON s.submitter_org_id = o.organization_id
#                     WHERE s.submission_id = ?
#                 """, (submission_id,))
                
#                 row = cursor.fetchone()
#                 if not row:
#                     return None
                
#                 submission = json.loads(row['full_submission_json'])
                
#                 # Apply access level filtering
#                 filtered_submission = self._filter_submission_by_access_level(submission, access_level)
                
#                 # Log access
#                 self._log_access(conn, org_id, 'READ', 'submission', submission_id)
#                 conn.commit()
                
#                 return filtered_submission
                
#         except sqlite3.Error as e:
#             self.logger.error(f"Error retrieving submission {submission_id}: {e}")
#             raise FRANKQueryError(f"Failed to retrieve submission: {e}")
    
#     def query_observables(self, org_id: str, observable_type: str = None, 
#                          limit: int = 100, access_level: str = 'contributor',
#                          min_confidence: int = None, sectors: List[str] = None,
#                          days_back: int = None) -> List[Dict[str, Any]]:
#         """
#         Query observables with access level filtering and advanced filters.
        
#         Args:
#             org_id: Organization ID making the query
#             observable_type: Filter by observable type
#             limit: Maximum number of results
#             access_level: Access level for filtering
#             min_confidence: Minimum confidence threshold
#             sectors: Filter by affected sectors
#             days_back: Only return observables from last N days
            
#         Returns:
#             List of filtered observable statistics
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.row_factory = sqlite3.Row
                
#                 # Build query based on access level and filters
#                 query_parts = ["""
#                     SELECT os.observable_hash, os.observable_type, os.observable_value,
#                            os.total_sightings, os.unique_organizations, os.first_seen, 
#                            os.last_seen, os.avg_confidence, os.sectors_json, os.regions_json
#                     FROM observable_statistics os
#                 """]
                
#                 where_clauses = []
#                 params = []
                
#                 if observable_type:
#                     where_clauses.append("os.observable_type = ?")
#                     params.append(observable_type)
                
#                 if min_confidence:
#                     where_clauses.append("os.avg_confidence >= ?")
#                     params.append(min_confidence)
                
#                 if days_back:
#                     where_clauses.append("os.last_seen >= datetime('now', '-{} days')".format(days_back))
                
#                 if sectors:
#                     # This is a simplified sector filter - in production would use JSON functions
#                     sector_conditions = []
#                     for sector in sectors:
#                         sector_conditions.append("os.sectors_json LIKE ?")
#                         params.append(f'%"{sector}"%')
#                     where_clauses.append(f"({' OR '.join(sector_conditions)})")
                
#                 if where_clauses:
#                     query_parts.append(" WHERE " + " AND ".join(where_clauses))
                
#                 query_parts.append(f" ORDER BY os.last_seen DESC LIMIT {limit}")
                
#                 query = "".join(query_parts)
#                 cursor = conn.execute(query, params)
#                 results = []
                
#                 for row in cursor.fetchall():
#                     result = dict(row)
                    
#                     # Apply access level filtering
#                     result = self._filter_observable_by_access_level(result, access_level)
                    
#                     # Parse JSON fields
#                     try:
#                         result['sectors'] = json.loads(result['sectors_json']) if result['sectors_json'] else []
#                         result['regions'] = json.loads(result['regions_json']) if result['regions_json'] else []
#                         del result['sectors_json']
#                         del result['regions_json']
#                     except:
#                         result['sectors'] = []
#                         result['regions'] = []
                    
#                     results.append(result)
                
#                 # Log access
#                 self._log_access(conn, org_id, 'QUERY', 'observables')
#                 conn.commit()
                
#                 self.logger.info(f"Retrieved {len(results)} observables for {org_id} (access: {access_level})")
#                 return results
                
#         except sqlite3.Error as e:
#             self.logger.error(f"Error querying observables: {e}")
#             raise FRANKQueryError(f"Failed to query observables: {e}")
    
#     def get_statistics_summary(self, org_id: str, days: int = 30) -> Dict[str, Any]:
#         """
#         Get platform statistics summary.
        
#         Args:
#             org_id: Organization ID making the request
#             days: Number of days to look back
            
#         Returns:
#             Statistics summary dictionary
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.row_factory = sqlite3.Row
                
#                 stats = {}
                
#                 # Basic submission statistics
#                 cursor = conn.execute("""
#                     SELECT 
#                         COUNT(DISTINCT submission_id) as total_submissions,
#                         COUNT(DISTINCT submitter_org_id) as active_organizations,
#                         AVG(confidence) as avg_confidence
#                     FROM submissions 
#                     WHERE submission_timestamp >= datetime('now', '-{} days')
#                 """.format(days))
                
#                 basic_stats = dict(cursor.fetchone())
#                 stats.update(basic_stats)
                
#                 # Observable type distribution
#                 cursor = conn.execute("""
#                     SELECT observable_type, COUNT(*) as count,
#                            AVG(total_sightings) as avg_sightings
#                     FROM observable_statistics
#                     WHERE updated_at >= datetime('now', '-{} days')
#                     GROUP BY observable_type
#                     ORDER BY count DESC
#                     LIMIT 10
#                 """.format(days))
                
#                 stats['observable_types'] = dict(cursor.fetchall())
                
#                 # Severity distribution
#                 cursor = conn.execute("""
#                     SELECT severity, COUNT(*) as count
#                     FROM submissions
#                     WHERE submission_timestamp >= datetime('now', '-{} days')
#                     AND severity IS NOT NULL
#                     GROUP BY severity
#                 """.format(days))
                
#                 stats['severity_distribution'] = dict(cursor.fetchall())
                
#                 # Top sectors by activity
#                 cursor = conn.execute("""
#                     SELECT sector, COUNT(*) as submissions
#                     FROM submissions s
#                     JOIN organizations o ON s.submitter_org_id = o.organization_id
#                     WHERE s.submission_timestamp >= datetime('now', '-{} days')
#                     AND o.sector IS NOT NULL
#                     GROUP BY sector
#                     ORDER BY submissions DESC
#                     LIMIT 5
#                 """.format(days))
                
#                 stats['top_sectors'] = dict(cursor.fetchall())
                
#                 # Recent activity trend (daily counts)
#                 cursor = conn.execute("""
#                     SELECT DATE(submission_timestamp) as date, COUNT(*) as count
#                     FROM submissions
#                     WHERE submission_timestamp >= datetime('now', '-{} days')
#                     GROUP BY DATE(submission_timestamp)
#                     ORDER BY date DESC
#                 """.format(days))
                
#                 stats['daily_activity'] = dict(cursor.fetchall())
                
#                 # Log access
#                 self._log_access(conn, org_id, 'STATS', 'summary')
#                 conn.commit()
                
#                 return stats
                
#         except sqlite3.Error as e:
#             self.logger.error(f"Error getting statistics: {e}")
#             raise FRANKQueryError(f"Failed to get statistics: {e}")
    
#     def upsert_organization(self, org_data: Dict[str, Any]) -> bool:
#         """
#         Insert or update organization information.
        
#         Args:
#             org_data: Organization data dictionary
            
#         Returns:
#             True if successful
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 self._upsert_organization(conn, org_data)
#                 conn.commit()
#                 return True
#         except sqlite3.Error as e:
#             self.logger.error(f"Error upserting organization: {e}")
#             return False
    
#     def log_access(self, org_id: str, action: str, resource_type: str = None, 
#                    resource_id: str = None, details: Dict[str, Any] = None) -> bool:
#         """
#         Log access for auditing purposes.
        
#         Args:
#             org_id: Organization ID performing the action
#             action: Action being performed
#             resource_type: Type of resource being accessed
#             resource_id: ID of specific resource
#             details: Additional details to log
            
#         Returns:
#             True if logged successfully
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 self._log_access(conn, org_id, action, resource_type, resource_id, details)
#                 conn.commit()
#                 return True
#         except sqlite3.Error as e:
#             self.logger.error(f"Error logging access: {e}")
#             return False
    
#     def _log_access(self, conn: sqlite3.Connection, org_id: str, action: str, 
#                    resource_type: str = None, resource_id: str = None, 
#                    details: Dict[str, Any] = None) -> None:
#         """Internal method to log access."""
#         conn.execute("""
#             INSERT INTO access_logs 
#             (organization_id, action, resource_type, resource_id, details_json)
#             VALUES (?, ?, ?, ?, ?)
#         """, (
#             org_id,
#             action,
#             resource_type,
#             resource_id,
#             json.dumps(details) if details else None
#         ))
    
#     def cleanup_old_data(self, days: int = 90) -> int:
#         """
#         Clean up old data according to retention policies.
        
#         Args:
#             days: Remove data older than this many days
            
#         Returns:
#             Number of records deleted
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 # Clean up old submissions (cascades to sightings and observables)
#                 cursor = conn.execute("""
#                     DELETE FROM submissions 
#                     WHERE submission_timestamp < datetime('now', '-{} days')
#                 """.format(days))
                
#                 deleted_submissions = cursor.rowcount
                
#                 # Clean up old access logs
#                 cursor = conn.execute("""
#                     DELETE FROM access_logs 
#                     WHERE timestamp < datetime('now', '-{} days')
#                 """.format(days))
                
#                 deleted_logs = cursor.rowcount
                
#                 # Clean up orphaned statistics (where no recent sightings exist)
#                 cursor = conn.execute("""
#                     DELETE FROM observable_statistics 
#                     WHERE last_seen < datetime('now', '-{} days')
#                     AND observable_hash NOT IN (
#                         SELECT DISTINCT observable_hash 
#                         FROM observables o
#                         JOIN sightings s ON o.sighting_id = s.sighting_id
#                         JOIN submissions sub ON s.submission_id = sub.submission_id
#                         WHERE sub.submission_timestamp >= datetime('now', '-{} days')
#                     )
#                 """.format(days))
                
#                 deleted_stats = cursor.rowcount
                
#                 conn.commit()
                
#                 total_deleted = deleted_submissions + deleted_logs + deleted_stats
#                 self.logger.info(f"Cleaned up {total_deleted} old records")
#                 return total_deleted
                
#         except sqlite3.Error as e:
#             self.logger.error(f"Error during cleanup: {e}")
#             raise FRANKStorageError(f"Failed to cleanup old data: {e}")
    
#     def _filter_submission_by_access_level(self, submission: Dict[str, Any], access_level: str) -> Dict[str, Any]:
#         """Filter submission data based on access level."""
#         if access_level == 'public':
#             # Only basic statistics
#             return {
#                 'submission': {
#                     'metadata': {
#                         'submission_id': submission['submission'].get('metadata', {}).get('submission_id'),
#                         'timestamp': submission['submission'].get('metadata', {}).get('timestamp')
#                     },
#                     'sighting': {
#                         'confidence': submission['submission']['sighting'].get('confidence'),
#                         'severity': submission['submission']['sighting'].get('severity'),
#                         'timestamp': submission['submission']['sighting'].get('timestamp'),
#                         'observation_count': submission['submission']['sighting'].get('observation_count')
#                     }
#                 }
#             }
#         elif access_level == 'observer':
#             # Add some observable types but mask values
#             filtered = self._deep_copy(submission)
#             observables = filtered['submission']['sighting'].get('observables', {})
#             for category, obs_list in observables.items():
#                 if isinstance(obs_list, list):
#                     for obs in obs_list:
#                         if 'value' in obs:
#                             obs['value'] = obs['value'][:10] + "..." if len(obs['value']) > 10 else obs['value']
            
#             # Remove sensitive sections
#             filtered['submission'].pop('hit_target', None)
#             filtered['submission'].pop('sharing', None)
            
#             return filtered
#         elif access_level == 'contributor':
#             # Remove only the most sensitive information
#             filtered = self._deep_copy(submission)
            
#             # Anonymize hit target details
#             if 'hit_target' in filtered['submission']:
#                 hit_target = filtered['submission']['hit_target']
#                 hit_target.pop('organization_id', None)
#                 hit_target['sector'] = hit_target.get('sector', 'unknown')
            
#             return filtered
        
#         # Partner and core_member get full access
#         return submission
    
#     def _filter_observable_by_access_level(self, observable: Dict[str, Any], access_level: str) -> Dict[str, Any]:
#         """Filter observable data based on access level."""
#         if access_level == 'public':
#             return {
#                 'observable_type': observable['observable_type'],
#                 'total_sightings': observable['total_sightings'],
#                 'last_seen': observable['last_seen']
#             }
#         elif access_level == 'observer':
#             filtered = dict(observable)
#             # Mask observable value
#             if 'observable_value' in filtered:
#                 value = filtered['observable_value']
#                 filtered['observable_value'] = value[:10] + "..." if len(value) > 10 else value
#             return filtered
        
#         # Contributor and above get full access
#         return observable
    
#     def _deep_copy(self, obj: Any) -> Any:
#         """Create a deep copy of an object."""
#         if isinstance(obj, dict):
#             return {k: self._deep_copy(v) for k, v in obj.items()}
#         elif isinstance(obj, list):
#             return [self._deep_copy(item) for item in obj]
#         else:
#             return obj
    
#     def search_observables_by_value(self, org_id: str, search_value: str, 
#                                    access_level: str = 'contributor') -> List[Dict[str, Any]]:
#         """
#         Search for observables by partial value match.
        
#         Args:
#             org_id: Organization performing the search
#             search_value: Value to search for (supports wildcards)
#             access_level: Access level for filtering
            
#         Returns:
#             List of matching observables
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.row_factory = sqlite3.Row
                
#                 cursor = conn.execute("""
#                     SELECT os.* FROM observable_statistics os
#                     WHERE os.observable_value LIKE ?
#                     ORDER BY os.total_sightings DESC
#                     LIMIT 100
#                 """, (f"%{search_value}%",))
                
#                 results = []
#                 for row in cursor.fetchall():
#                     result = dict(row)
#                     result = self._filter_observable_by_access_level(result, access_level)
                    
#                     # Parse JSON fields
#                     try:
#                         result['sectors'] = json.loads(result['sectors_json']) if result['sectors_json'] else []
#                         result['regions'] = json.loads(result['regions_json']) if result['regions_json'] else []
#                         del result['sectors_json']
#                         del result['regions_json']
#                     except:
#                         result['sectors'] = []
#                         result['regions'] = []
                    
#                     results.append(result)
                
#                 # Log access
#                 self._log_access(conn, org_id, 'SEARCH', 'observables', details={'search_value': search_value})
#                 conn.commit()
                
#                 return results
                
#         except sqlite3.Error as e:
#             self.logger.error(f"Error searching observables: {e}")
#             raise FRANKQueryError(f"Failed to search observables: {e}")
    
#     def get_organization_info(self, org_id: str) -> Optional[Dict[str, Any]]:
#         """
#         Get organization information.
        
#         Args:
#             org_id: Organization ID to look up
            
#         Returns:
#             Organization data or None if not found
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.row_factory = sqlite3.Row
                
#                 cursor = conn.execute("""
#                     SELECT * FROM organizations WHERE organization_id = ?
#                 """, (org_id,))
                
#                 row = cursor.fetchone()
#                 if not row:
#                     return None
                
#                 org_data = dict(row)
                
#                 # Parse metadata JSON
#                 try:
#                     metadata = json.loads(org_data['metadata_json']) if org_data['metadata_json'] else {}
#                     org_data.update(metadata)
#                     del org_data['metadata_json']
#                 except:
#                     del org_data['metadata_json']
                
#                 return org_data
                
#         except sqlite3.Error as e:
#             self.logger.error(f"Error getting organization info: {e}")
#             return None
    
#     def get_sigma_rules(self, org_id: str, rule_status: str = None, 
#                        limit: int = 100) -> List[Dict[str, Any]]:
#         """
#         Get SIGMA rules with optional filtering.
        
#         Args:
#             org_id: Organization requesting the rules
#             rule_status: Filter by rule status (stable, test, experimental)
#             limit: Maximum number of rules to return
            
#         Returns:
#             List of SIGMA rule dictionaries
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.row_factory = sqlite3.Row
                
#                 query = "SELECT * FROM sigma_rules"
#                 params = []
                
#                 if rule_status:
#                     query += " WHERE rule_status = ?"
#                     params.append(rule_status)
                
#                 query += f" ORDER BY updated_at DESC LIMIT {limit}"
                
#                 cursor = conn.execute(query, params)
#                 results = [dict(row) for row in cursor.fetchall()]
                
#                 # Log access
#                 self._log_access(conn, org_id, 'QUERY', 'sigma_rules')
#                 conn.commit()
                
#                 return results
                
#         except sqlite3.Error as e:
#             self.logger.error(f"Error getting SIGMA rules: {e}")
#             raise FRANKQueryError(f"Failed to get SIGMA rules: {e}")
    
#     def get_campaigns(self, org_id: str, active_only: bool = False, 
#                      limit: int = 100) -> List[Dict[str, Any]]:
#         """
#         Get campaign information.
        
#         Args:
#             org_id: Organization requesting campaigns
#             active_only: Only return recently active campaigns
#             limit: Maximum number of campaigns to return
            
#         Returns:
#             List of campaign dictionaries
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.row_factory = sqlite3.Row
                
#                 query = "SELECT * FROM campaigns"
                
#                 if active_only:
#                     query += " WHERE updated_at >= datetime('now', '-30 days')"
                
#                 query += f" ORDER BY updated_at DESC LIMIT {limit}"
                
#                 cursor = conn.execute(query)
#                 results = []
                
#                 for row in cursor.fetchall():
#                     campaign = dict(row)
                    
#                     # Parse JSON fields
#                     try:
#                         campaign['target_sectors'] = json.loads(campaign['target_sectors_json']) if campaign['target_sectors_json'] else []
#                         del campaign['target_sectors_json']
#                     except:
#                         campaign['target_sectors'] = []
                    
#                     results.append(campaign)
                
#                 # Log access
#                 self._log_access(conn, org_id, 'QUERY', 'campaigns')
#                 conn.commit()
                
#                 return results
                
#         except sqlite3.Error as e:
#             self.logger.error(f"Error getting campaigns: {e}")
#             raise FRANKQueryError(f"Failed to get campaigns: {e}")
    
#     def get_access_logs(self, org_id: str, days: int = 7, 
#                        actions: List[str] = None) -> List[Dict[str, Any]]:
#         """
#         Get access logs for auditing.
        
#         Args:
#             org_id: Organization to get logs for
#             days: Number of days to look back
#             actions: Filter by specific actions
            
#         Returns:
#             List of access log entries
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 conn.row_factory = sqlite3.Row
                
#                 query = """
#                     SELECT * FROM access_logs 
#                     WHERE organization_id = ? 
#                     AND timestamp >= datetime('now', '-{} days')
#                 """.format(days)
                
#                 params = [org_id]
                
#                 if actions:
#                     placeholders = ','.join('?' * len(actions))
#                     query += f" AND action IN ({placeholders})"
#                     params.extend(actions)
                
#                 query += " ORDER BY timestamp DESC LIMIT 1000"
                
#                 cursor = conn.execute(query, params)
#                 results = []
                
#                 for row in cursor.fetchall():
#                     log_entry = dict(row)
                    
#                     # Parse details JSON
#                     try:
#                         details = json.loads(log_entry['details_json']) if log_entry['details_json'] else {}
#                         log_entry['details'] = details
#                         del log_entry['details_json']
#                     except:
#                         log_entry['details'] = {}
#                         del log_entry['details_json']
                    
#                     results.append(log_entry)
                
#                 return results
                
#         except sqlite3.Error as e:
#             self.logger.error(f"Error getting access logs: {e}")
#             raise FRANKQueryError(f"Failed to get access logs: {e}")
    
#     def health_check(self) -> Dict[str, Any]:
#         """
#         Perform a health check on the database.
        
#         Returns:
#             Health status dictionary
#         """
#         try:
#             with sqlite3.connect(self.db_path) as conn:
#                 # Basic connectivity test
#                 cursor = conn.execute("SELECT 1")
#                 cursor.fetchone()
                
#                 # Get database statistics
#                 cursor = conn.execute("""
#                     SELECT name, COUNT(*) as count FROM (
#                         SELECT 'organizations' as name FROM organizations
#                         UNION ALL
#                         SELECT 'submissions' as name FROM submissions
#                         UNION ALL
#                         SELECT 'sightings' as name FROM sightings
#                         UNION ALL
#                         SELECT 'observables' as name FROM observables
#                         UNION ALL
#                         SELECT 'observable_statistics' as name FROM observable_statistics
#                         UNION ALL
#                         SELECT 'access_logs' as name FROM access_logs
#                     ) GROUP BY name
#                 """)
                
#                 table_counts = dict(cursor.fetchall())
                
#                 # Check database size
#                 db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
                
#                 return {
#                     'status': 'healthy',
#                     'database_path': self.db_path,
#                     'database_size_bytes': db_size,
#                     'table_counts': table_counts,
#                     'timestamp': datetime.now(timezone.utc).isoformat()
#                 }
                
#         except Exception as e:
#             self.logger.error(f"Health check failed: {e}")
#             return {
#                 'status': 'unhealthy',
#                 'error': str(e),
#                 'timestamp': datetime.now(timezone.utc).isoformat()
#             }


# # Factory function for easy instantiation
# def create_sqlite_database(db_path: str = "frank_local.db") -> SQLiteFRANKDatabase:
#     """
#     Factory function to create a SQLiteFRANKDatabase instance.
    
#     Args:
#         db_path: Path to SQLite database file
        
#     Returns:
#         Configured SQLiteFRANKDatabase instance
#     """
#     return SQLiteFRANKDatabase(db_path)

# class FRANKClient:
#     """
#     High-level FRANK client that combines submission handling with database operations.
    
#     This is the main interface most users should interact with, providing a simple
#     API that handles both submission processing and storage automatically.
#     """
    
#     def __init__(self, submission_handler: frank.FRANKSubmission, 
#                  database: BaseFRANKDatabase, config: Dict[str, Any]):
#         self.submission_handler = submission_handler
#         self.database = database
#         self.config = config
    
#     def submit_threat_intelligence(self, submission: Dict[str, Any], 
#                                  validate: bool = True) -> str:
#         """
#         Submit threat intelligence to the FRANK platform.
        
#         Args:
#             submission: Threat intelligence submission dictionary
#             validate: Whether to validate before storing (default: True)
            
#         Returns:
#             Submission ID if successful
            
#         Raises:
#             FRANKValidationError: If validation fails
#             FRANKDatabaseError: If storage fails
#         """
#         if validate:
#             is_valid, issues = self.submission_handler.validate_submission(submission)
#             if not is_valid:
#                 raise frank.FRANKValidationError(
#                     "Submission validation failed", 
#                     validation_errors=issues
#                 )
        
#         # Normalize submission
#         normalized = self.submission_handler.normalize_submission(submission)
        
#         # Store in database
#         success = self.database.store_submission(normalized)
#         if not success:
#             raise frank.FRANKError("Failed to store submission in database")
        
#         # Extract submission ID
#         return normalized['submission']['metadata']['submission_id']
    
#     def generate_and_submit(self, org_id: str, tier: str = "partner", 
#                           observables: List[Dict] = None, **kwargs) -> str:
#         """
#         Generate a minimal submission and submit it automatically.
        
#         Convenience method for quick threat intelligence submission.
#         """
#         submission = self.submission_handler.generate_minimal_submission(
#             org_id=org_id, tier=tier, observables=observables, **kwargs
#         )
#         return self.submit_threat_intelligence(submission)
    
#     def query_threats(self, org_id: str, access_level: str = None, **filters) -> List[Dict]:
#         """
#         Query threat intelligence with automatic access level filtering.
        
#         Args:
#             org_id: Organization ID making the query
#             access_level: Access level (auto-determined if None)
#             **filters: Additional query filters
            
#         Returns:
#             List of filtered threat intelligence records
#         """
#         if access_level is None:
#             access_level = self.config.get('default_tier', 'contributor')
        
#         return self.database.query_observables(
#             org_id=org_id, 
#             access_level=access_level,
#             **filters
#         )
    
#     def get_platform_statistics(self, org_id: str) -> Dict[str, Any]:
#         """Get platform statistics for an organization."""
#         return self.database.get_statistics_summary(org_id)
    
    
# def create_frank_client(config: dict = None):
#     """
#     Factory function to create a complete FRANK client with database backend.
    
#     Args:
#         config: Configuration dictionary (uses defaults if None)
        
#     Returns:
#         Configured FRANK client instance
        
#     Example:
#         >>> import frank
#         >>> client = frank.create_frank_client()
#         >>> submission = client.generate_minimal_submission()
#     """
#     if config is None:
#         config = DEFAULT_CONFIG.copy()
    
#     # Create database backend
#     db = create_database(
#         db_type=config.get('database_type', 'sqlite'),
#         **{k: v for k, v in config.items() if k.startswith('database_')}
#     )
    
#     # Create submission handler
#     submission_handler = frank.FRANKSubmission()
    
#     # Return a client that combines both
#     return FRANKClient(submission_handler, db, config)

if __name__ == "__main__":
    db = SQLiteFRANKDatabase("/tmp/custom.db")

    # Quick start
    client = create_client()

    # Generate and submit threat intelligence
    submission_id = client.generate_and_submit(
        org_id="my-org-123",
        tier="partner"
    )

    # Query threats
    threats = client.query_threats("my-org-123")

    # Advanced usage with specific components
    db = SQLiteFRANKDatabase("/tmp/custom.db")

    # Manual operations
    submission = generate_minimal_submission()
    db.store_submission(submission.to_dict())