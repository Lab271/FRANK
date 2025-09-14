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


from .base import BaseFRANKDatabase
from .sqlite import SQLiteFRANKDatabase
from .mysql import MySQLFRANKDatabase
from .exceptions import FRANKDatabaseError, FRANKConfigurationError, FRANKConnectionError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
    
# Default configuration
DEFAULT_CONFIG = {
    'database_type': 'sqlite',
    'database_path': '/tmp/frank.db',
    'log_level': 'INFO',
    'default_access_level': 'contributor',
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
    elif db_type.lower() == 'mysql':
        try:

            # Extract MySQL-specific parameters
            host = kwargs.get('database_host', 'localhost')
            port = kwargs.get('database_port', 3306)
            database = kwargs.get('database_name', 'frank')
            user = kwargs.get('database_user', 'frank_user')
            password = kwargs.get('database_password', 'frank_password')

            logger.info(f"Creating MySQL database at {host}:{port}/{database}")
            return MySQLFRANKDatabase(host=host, port=port, database=database, user=user, password=password)

        except ImportError as e:
            raise FRANKConfigurationError(f"MySQL backend not available: {e}")
        except Exception as e:
            raise FRANKConnectionError(f"Failed to create MySQL database: {e}")
            
    # elif db_type.lower() == 'dynamodb':
    #     try:
            
    #         # Extract DynamoDB-specific parameters
    #         required_params = ['table_prefix']
    #         for param in required_params:
    #             if param not in kwargs:
    #                 raise FRANKConfigurationError(f"Missing required parameter for DynamoDB: {param}")
            
    #         logger.info(f"Creating DynamoDB database with prefix {kwargs['table_prefix']}")
    #         return DynamoDBFRANKDatabase(kwargs)
            
    #     except ImportError as e:
    #         raise FRANKConfigurationError(f"DynamoDB backend not available: {e}")
    #     except Exception as e:
    #         raise FRANKConnectionError(f"Failed to create DynamoDB database: {e}")
    
    else:
        raise FRANKConfigurationError(
            f"Unknown database type '{db_type}'. Supported types: 'sqlite', 'dynamodb'"
        )
