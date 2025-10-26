#!/usr/bin/env python3
"""
FRANK MCP Server - Threat Intelligence Query Interface
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module implements an MCP (Model Context Protocol) server that exposes
FRANK threat intelligence platform capabilities to AI assistants and other
MCP clients. It provides read-only access to threat intelligence data with
support for both LocalStack (Docker) and AWS environments.

Key Features:
- Query threat sightings by observable (IP, domain, hash, etc.)
- Retrieve specific submissions by ID
- Access platform statistics and configuration
- Support for LocalStack development environment and AWS production
- Comprehensive error handling and logging

The implementation follows FRANK's established patterns from frank_stage3.py
and provides a flexible configuration system for different deployment scenarios.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import argparse
from functools import lru_cache
import json
import os
from typing import Dict, Any, Optional

from mcp.server.fastmcp.server import FastMCP

import frank
from frank.core import gen_stix_id
from frank.core.enum import AccessTier, ObservableType
from frank.storage import create_dynamodb_database
from frank.util.server import create_server
from frank.util.logger import setup_logging, get_module_logger, configure_frank_logging

# ===================================
# Configuration
# ===================================

@lru_cache()
def get_config() -> Dict[str, Any]:
    """
    Get MCP server configuration from environment variables.
    Similar to frank_stage3.py but focused on MCP server needs.
    
    Returns:
        Dict containing configuration parameters
    """
    endpoint = os.environ.get("ENDPOINT", None)
    # Convert empty string to None for AWS
    if endpoint == "":
        endpoint = None

    environment = os.environ.get("FRANK_ENVIRONMENT", "localstack")  # "aws" or "localstack"
    profile = os.environ.get("AWS_PROFILE", None)
    region = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", None)
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", None)
    table_name = os.environ.get("DYNAMODB_TABLE", "frank-data")
    audit_table_name = os.environ.get("DYNAMODB_AUDIT_TABLE", "frank-audit")

    return {
        "endpoint": endpoint,  # None for AWS, set for LocalStack
        "environment": environment,
        "profile": profile,
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
        "region": region,
        "table_name": table_name,
        "audit_table_name": audit_table_name,
    }


# ===================================
# FRANK Server Initialization
# ===================================

# Global server instance (lazy loading)
_server = None
_logger = None


def get_logger():
    """Get or create logger instance"""
    global _logger
    if _logger is None:
        _logger = get_module_logger("frank.mcp")
    return _logger


def get_frank_server():
    """
    Lazy initialization of FRANK server with error handling.
    Creates database connection and server instance on first call.
    
    Returns:
        FRANKServer instance
        
    Raises:
        Exception: If server initialization fails
    """
    global _server
    if _server is None:
        try:
            config = get_config()
            logger = get_logger()
            logger.info(f"Initializing FRANK server for environment: {config['environment']}")
            
            db = create_dynamodb_database(config=config, logger=logger)
            _server = create_server(db=db, config=config, logger=logger)
            
            logger.info("FRANK server initialized successfully")
        except Exception as e:
            logger = get_logger()
            logger.error(f"Failed to initialize FRANK server: {e}")
            raise
    return _server


def create_mock_user(access_level: AccessTier = AccessTier.CORE_MEMBER) -> Dict[str, Any]:
    """
    Create a mock user context for MCP queries.
    Since MCP operates at system level, we use a system user with appropriate access.
    
    Args:
        access_level: Access tier for the system user
        
    Returns:
        Dict containing user context
    """
    return {
        "user_id": "system-mcp-user",
        "organisation_id": gen_stix_id("identity"),
        "access_level": access_level,
        "request_id": gen_stix_id("request"),
        "username": "mcp-system",
    }


# ===================================
# MCP Server Setup
# ===================================

mcp = FastMCP("frank_threat_intel")


@mcp.prompt()
def frank_usage_prompt():
    """
    Provide usage guidance for FRANK MCP tools and resources.
    
    Returns:
        Usage instructions and examples
    """
    return """
    You are interacting with the FRANK Threat Intelligence Platform via MCP.
    
    Available tools:
    1. 'query_sightings_by_observable' - Search for threat sightings by observable value
       Example: query_sightings_by_observable(observable_value="185.220.102.45", observable_type="ipv4-addr", limit=10)
    
    2. 'get_submission' - Retrieve a specific submission by ID
       Example: get_submission(submission_id="submission--1234abcd-12ab-34cd-56ef-1234567890ab")
    
    3. 'get_platform_stats' - Get platform health and statistics
       Example: get_platform_stats()
    
    4. 'get_health_check' - Perform deep health check on database
       Example: get_health_check()
    
    Available resources:
    - frank://config - Server configuration and environment details
    - frank://observable-types - List of available observable types
    - frank://access-tiers - Access tier information and levels
    
    Note: This MCP server operates with system-level access to FRANK data.
    All queries are read-only and do not modify the database.
    Results are formatted as JSON strings for easy parsing.
    """


# ===================================
# MCP Tools
# ===================================

@mcp.tool()
def query_sightings_by_observable(
    observable_value: str,
    observable_type: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Query threat intelligence sightings by observable value.
    
    This tool searches the FRANK database for sightings matching the provided
    observable value (e.g., IP address, domain name, file hash). Results include
    threat context, timestamps, and related information.
    
    Args:
        observable_value: The observable to search for (IP, domain, hash, etc.)
        observable_type: Optional filter for observable type (e.g., "ipv4-addr", "domain-name")
        limit: Maximum number of results to return (default: 10, max: 100)
    
    Returns:
        JSON string containing sighting data or error message
    
    Example:
        query_sightings_by_observable("185.220.102.45", "ipv4-addr", 5)
    """
    logger = get_logger()
    
    try:
        logger.info(f"Querying sightings for observable: {observable_value}")
        
        # Create system user context
        user = create_mock_user(AccessTier.CORE_MEMBER)
        
        # Prepare query parameters
        query_params = {
            "observable": observable_value,
            "observable_type": observable_type,
            "limit": min(limit, 100)  # Cap at 100 results
        }
        
        # Query via FRANK server
        server = get_frank_server()
        sightings = server.get_sightings_from_observations(user=user, **query_params)
        
        # Format results
        result = {
            "status": "success",
            "query": {
                "observable_value": observable_value,
                "observable_type": observable_type,
                "limit": limit
            },
            "total_results": len(sightings),
            "sightings": [s.model_dump(exclude_none=True) for s in sightings]
        }
        
        logger.info(f"Found {len(sightings)} sightings")
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query": {
                "observable_value": observable_value,
                "observable_type": observable_type,
                "limit": limit
            }
        }, indent=2)


@mcp.tool()
def get_submission(submission_id: str) -> str:
    """
    Retrieve a specific threat intelligence submission by ID.
    
    This tool fetches a complete submission record including all observables,
    threat context, impact information, and submitter details.
    
    Args:
        submission_id: STIX-formatted submission identifier (e.g., "submission--...")
    
    Returns:
        JSON string with submission details or error message
    
    Example:
        get_submission("submission--1234abcd-12ab-34cd-56ef-1234567890ab")
    """
    logger = get_logger()
    
    try:
        logger.info(f"Retrieving submission: {submission_id}")
        
        # Create system user context
        user = create_mock_user(AccessTier.CORE_MEMBER)
        
        # Fetch submission
        server = get_frank_server()
        submission = server.get_submission_by_id(user, submission_id)
        
        if not submission:
            result = {
                "status": "not_found",
                "submission_id": submission_id,
                "message": "Submission not found"
            }
            logger.warning(f"Submission not found: {submission_id}")
        else:
            result = {
                "status": "success",
                "submission_id": submission_id,
                "submission": submission.model_dump(exclude_none=True)
            }
            logger.info(f"Successfully retrieved submission: {submission_id}")
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to retrieve submission: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "submission_id": submission_id
        }, indent=2)


@mcp.tool()
def get_platform_stats() -> str:
    """
    Get FRANK platform health check and basic statistics.
    
    This tool retrieves platform status including version, environment,
    configuration, and basic health information.
    
    Returns:
        JSON string with platform statistics
    
    Example:
        get_platform_stats()
    """
    logger = get_logger()
    
    try:
        logger.info("Retrieving platform statistics")
        
        server = get_frank_server()
        health = server.health_check()
        
        result = {
            "status": "success",
            "platform": health
        }
        
        logger.info("Successfully retrieved platform statistics")
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to retrieve statistics: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)


@mcp.tool()
def get_health_check() -> str:
    """
    Perform deep health check on FRANK platform and database.
    
    This tool performs comprehensive health checks including database
    connectivity, table status, and system readiness.
    
    Returns:
        JSON string with detailed health check results
    
    Example:
        get_health_check()
    """
    logger = get_logger()
    
    try:
        logger.info("Performing deep health check")
        
        server = get_frank_server()
        health = server.deep_health_check()
        
        result = {
            "status": "success",
            "health_check": health
        }
        
        logger.info("Health check completed successfully")
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "message": "Database health check failed"
        }, indent=2)


# ===================================
# MCP Resources
# ===================================

@mcp.resource(uri="frank://config")
def get_frank_config():
    """
    Expose FRANK MCP server configuration.
    
    Returns configuration details including environment, region,
    database settings, and version information.
    
    Returns:
        Configuration data as dictionary
    """
    config = get_config()
    return {
        "environment": config["environment"],
        "region": config["region"],
        "table_name": config["table_name"],
        "audit_table_name": config["audit_table_name"],
        "endpoint": config["endpoint"] or "AWS Direct",
        "frank_version": frank.__version__,
        "mcp_server": "frank_threat_intel"
    }


@mcp.resource(uri="frank://observable-types")
def get_observable_types():
    """
    List available observable types in FRANK.
    
    Returns all supported observable types with their values and names.
    
    Returns:
        Observable types dictionary
    """
    types = {
        t.value: {
            "name": t.name,
            "value": t.value,
            "description": f"Observable type: {t.name}"
        }
        for t in ObservableType
    }
    return types


@mcp.resource(uri="frank://access-tiers")
def get_access_tiers():
    """
    List FRANK access tier levels.
    
    Returns information about all access tiers including their
    hierarchy and capabilities.
    
    Returns:
        Access tiers dictionary
    """
    tiers = {
        t.value: {
            "name": t.name,
            "level": t.value,
            "numeric_level": t.value,
            "can_submit": AccessTier.can_submit(t),
            "description": f"Access tier: {t.name}"
        }
        for t in AccessTier
    }
    return tiers


# ===================================
# Environment Setup
# ===================================

def setup_environment(args):
    """
    Configure environment variables based on command-line arguments.
    Ensures proper settings for LocalStack or AWS environments.
    
    Args:
        args: Parsed command-line arguments
    """
    os.environ["FRANK_ENVIRONMENT"] = args.environment
    os.environ["AWS_DEFAULT_REGION"] = args.region
    
    if args.environment == "localstack":
        os.environ["ENDPOINT"] = args.endpoint
        if args.profile:
            os.environ["AWS_PROFILE"] = args.profile
        else:
            os.environ["AWS_ACCESS_KEY_ID"] = args.aws_access_key_id
            os.environ["AWS_SECRET_ACCESS_KEY"] = args.aws_secret_access_key
    elif args.environment == "aws":
        # Clear LocalStack-specific env vars for AWS environment
        os.environ.pop("ENDPOINT", None)
        if args.profile:
            os.environ["AWS_PROFILE"] = args.profile
        # Don't set explicit credentials for AWS - let boto3 use default credential chain
        os.environ.pop("AWS_ACCESS_KEY_ID", None)
        os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
    
    os.environ["DYNAMODB_TABLE"] = args.table_name
    os.environ["DYNAMODB_AUDIT_TABLE"] = args.audit_table_name


def log_startup_info(logger, args):
    """
    Log startup information for debugging and monitoring.
    
    Args:
        logger: Logger instance
        args: Parsed command-line arguments
    """
    logger.info("=" * 60)
    logger.info("FRANK MCP Server Starting")
    logger.info("=" * 60)
    logger.info(f"FRANK Version: {frank.__version__}")
    logger.info(f"Environment: {args.environment}")
    logger.info(f"Region: {args.region}")
    
    if args.environment == "localstack":
        logger.info(f"LocalStack Endpoint: {args.endpoint}")
        if args.profile:
            logger.info(f"AWS Profile: {args.profile}")
        else:
            logger.info("Using explicit AWS credentials for LocalStack")
    else:
        logger.info("Connecting to AWS")
        if args.profile:
            logger.info(f"AWS Profile: {args.profile}")
        else:
            logger.info("Using default AWS credential chain")
    
    logger.info(f"DynamoDB Table: {args.table_name}")
    logger.info(f"Audit Table: {args.audit_table_name}")
    logger.info(f"Log Level: {args.log_level.upper()}")
    logger.info("=" * 60)


# ===================================
# Main Function
# ===================================

def main():
    """
    Main function with argument parsing for flexible MCP server configuration.
    Inspired by frank_stage3.py main() function.
    """
    parser = argparse.ArgumentParser(
        description="FRANK MCP Server - Threat Intelligence Query Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with LocalStack (development)
  %(prog)s --environment localstack --endpoint http://localhost:4566
  
  # Run with AWS (production)
  %(prog)s --environment aws --profile my-profile --region eu-west-1
  
  # Run with custom table names
  %(prog)s --table-name frank-prod-data --audit-table-name frank-prod-audit
        """
    )
    
    # Environment configuration
    parser.add_argument(
        "--environment",
        type=str,
        default=os.getenv("FRANK_ENVIRONMENT", "localstack"),
        choices=["localstack", "aws"],
        help="Configuration environment (default: FRANK_ENVIRONMENT or 'localstack')"
    )
    
    # AWS configuration
    parser.add_argument(
        "--region",
        type=str,
        default=os.getenv("AWS_DEFAULT_REGION", "eu-west-1"),
        help="AWS region (default: AWS_DEFAULT_REGION or 'eu-west-1')"
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=os.getenv("AWS_PROFILE", None),
        help="AWS profile name (default: AWS_PROFILE or None)"
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.getenv("ENDPOINT", "http://localhost:4566"),
        help="DynamoDB endpoint URL for LocalStack (default: ENDPOINT or 'http://localhost:4566')"
    )
    parser.add_argument(
        "--aws-access-key-id",
        type=str,
        default=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        help="AWS Access Key ID for LocalStack (default: AWS_ACCESS_KEY_ID or 'test')"
    )
    parser.add_argument(
        "--aws-secret-access-key",
        type=str,
        default=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
        help="AWS Secret Access Key for LocalStack (default: AWS_SECRET_ACCESS_KEY or 'test')"
    )
    
    # DynamoDB configuration
    parser.add_argument(
        "--table-name",
        type=str,
        default=os.getenv("DYNAMODB_TABLE", "frank-data"),
        help="DynamoDB table name (default: DYNAMODB_TABLE or 'frank-data')"
    )
    parser.add_argument(
        "--audit-table-name",
        type=str,
        default=os.getenv("DYNAMODB_AUDIT_TABLE", "frank-audit"),
        help="DynamoDB audit table name (default: DYNAMODB_AUDIT_TABLE or 'frank-audit')"
    )
    
    # Logging configuration
    parser.add_argument(
        "--log-level",
        type=str,
        default=os.getenv("LOG_LEVEL", "info"),
        choices=["debug", "info", "warning", "error"],
        help="Logging level (default: LOG_LEVEL or 'info')"
    )
    parser.add_argument(
        "-s", "--silent",
        action="store_true",
        default=os.getenv("SILENT", "False").lower() in ("true", "1", "yes"),
        help="Enable silent mode (default: SILENT or False)"
    )
    
    args = parser.parse_args()
    
    # Set environment variables
    setup_environment(args)
    
    # Setup logging
    if args.silent:
        logger = setup_logging(silent=True)
    else:
        logger = setup_logging(silent=False)
        log_startup_info(logger, args)
    
    # Configure logging levels for FRANK components
    configure_frank_logging(args.log_level)
    logger.info(f"Set logging level to {args.log_level.upper()} for FRANK components")
    
    # Run MCP server
    try:
        logger.info("Starting MCP server via stdio transport...")
        mcp.run(transport='stdio')
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.error(f"MCP server failed: {e}")
        raise


if __name__ == "__main__":
    main()
