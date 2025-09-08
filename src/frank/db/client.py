#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This modules provides a high-level client interface combining submission handling
with database operations for easy integration into applications.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import logging
from typing import Dict, Any, List


from frank.core.models import Submission, Observables
from frank.db.base import BaseFRANKDatabase
from frank.db.sqlite import SQLiteFRANKDatabase
from frank.db.exceptions import FRANKDatabaseError, FRANKConfigurationError, FRANKConnectionError

from frank.utils.sample_builder import generate_minimal_submission

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
    
# Default configuration
DEFAULT_CONFIG = {
    'database_type': 'sqlite',
    'database_path': '/tmp/frank.db',
    'log_level': 'INFO',
    'default_tier': 'contributor',
    'retention_days': 90
}


def create_database(db_type: str = "sqlite", **kwargs) -> BaseFRANKDatabase:
    """
    Factory function to create appropriate database backend.
    
    Args:
        db_type: Type of database backend ('sqlite' or 'dynamodb')
        **kwargs: Database-specific configuration parameters
        
    Returns:
        Configured database instance
        
    Raises:
        FRANKConfigurationError: If invalid db_type or missing parameters
        FRANKConnectionError: If database connection fails
        
    Examples:
        # SQLite for development
        db = create_database('sqlite', database_path='frank_dev.db')
        
        # DynamoDB for production
        db = create_database('dynamodb', 
                           table_prefix='frank-prod',
                           region='us-east-1')
    """
    
    if db_type.lower() == 'sqlite':
        try:
            
            # Extract SQLite-specific parameters
            db_path = kwargs.get('database_path', kwargs.get('db_path', '/tmp/frank_local.db'))
            
            logger.info(f"Creating SQLite database at {db_path}")
            return SQLiteFRANKDatabase(db_path)
            
        except ImportError as e:
            raise FRANKConfigurationError(f"SQLite backend not available: {e}")
        except Exception as e:
            raise FRANKConnectionError(f"Failed to create SQLite database: {e}")
    
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
    
    else:
        raise FRANKConfigurationError(
            f"Unknown database type '{db_type}'. Supported types: 'sqlite', 'dynamodb'"
        )


class FRANKClient:
    """
    High-level FRANK client that combines submission handling with database operations.
    
    This is the main interface most users should interact with, providing a simple
    API that handles both submission processing and storage automatically.
    """
    
    def __init__(self, database: BaseFRANKDatabase, config: Dict[str, Any]):
        self.database = database
        self.config = config
    
    def submit_threat_intelligence(self, submission: Submission) -> str:
        """
        Submit threat intelligence to the FRANK platform.
        
        Args:
            submission: Threat intelligence submission dictionary
            validate: Whether to validate before storing (default: True)
            
        Returns:
            Submission ID if successful
            
        Raises:
            FRANKValidationError: If validation fails
            FRANKDatabaseError: If storage fails
        """
        
        # Store in database
        success = self.database.store_submission(submission)
        if not success:
            raise FRANKDatabaseError("Failed to store submission in database")
        
        # Extract submission ID
        return submission.submission_id
    
    def generate_and_submit(self, org_id: str, tier: str = "partner", 
                          observables: Observables = None, **kwargs) -> str:
        """
        Generate a minimal submission and submit it automatically.
        
        Convenience method for quick threat intelligence submission.
        """
        submission = generate_minimal_submission(
            org_id=org_id, tier=tier, observables=observables, **kwargs
        )
        return self.submit_threat_intelligence(submission)
    
    def query_threats(self, org_id: str, access_level: str = None, **filters) -> List[Dict]:
        """
        Query threat intelligence with automatic access level filtering.
        
        Args:
            org_id: Organization ID making the query
            access_level: Access level (auto-determined if None)
            **filters: Additional query filters
            
        Returns:
            List of filtered threat intelligence records
        """
        if access_level is None:
            access_level = self.config.get('default_tier', 'contributor')
        
        return self.database.query_observables(
            org_id=org_id, 
            access_level=access_level,
            **filters
        )
    
    def get_platform_statistics(self, org_id: str) -> Dict[str, Any]:
        """Get platform statistics for an organization."""
        return self.database.get_statistics_summary(org_id)
    


def create_client(config: dict = None) -> FRANKClient:
    """
    Factory function to create a complete FRANK client with database backend.
    
    Args:
        config: Configuration dictionary (uses defaults if None)
        
    Returns:
        Configured FRANK client instance
        
    Example:
        >>> import frank
        >>> client = frank.create_frank_client()
        >>> submission = client.generate_minimal_submission()
    """
    if config is None:
        config = DEFAULT_CONFIG.copy()
    
    # Create database backend
    db = create_database(
        db_type=config.get('database_type', 'sqlite'),
        **{k: v for k, v in config.items() if k.startswith('database_')}
    )
    
    # Return a client that combines both
    return FRANKClient(db, config)