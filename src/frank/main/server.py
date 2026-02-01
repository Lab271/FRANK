#!/usr/bin/env python3
"""
FRANK Platform - Main API Server

Entry point for running the Main API (Sightings API) server.

Usage:
    python -m frank.main.server
    python -m frank.main.server --port 8002 --reload

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import argparse
import logging
import os

import uvicorn

import frank
from frank.config import EnvironmentConfig
from frank.main.api import create_main_app
from frank.management.cognito_service import BaseCognitoService, get_cognito_service
from frank.storage.base import BaseFRANKDatabase


def setup_logging(log_level: str = "info"):
    """Setup logging to match Uvicorn's colored output"""
    try:
        from uvicorn.logging import DefaultFormatter

        formatter = DefaultFormatter(fmt="%(levelprefix)s %(message)s")

        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))

        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    except ImportError:
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="\033[32mINFO\033[0m:     %(message)s",
            handlers=[logging.StreamHandler()]
        )

    return logging.getLogger("uvicorn")


# Global instances for uvicorn factory
_app_instance = None
_database_instance = None
_cognito_instance = None


def create_database() -> BaseFRANKDatabase:
    """
    Create database instance based on environment configuration.

    Returns:
        Database instance (DynamoDB for cloud, SQLite for local)
    """
    env_config = EnvironmentConfig.get()
    logger = logging.getLogger(__name__)

    # Determine database type based on environment
    if env_config.is_local:
        # Local development: Try DynamoDB (LocalStack), fallback to SQLite
        dynamodb_endpoint = os.getenv("DYNAMODB_ENDPOINT")

        if dynamodb_endpoint:
            # Use DynamoDB (LocalStack)
            try:
                from frank.storage.dynamodb import DynamoDBFRANKDatabase

                logger.info(
                    f"Initializing DynamoDB for {env_config.environment.value} "
                    f"(endpoint: {dynamodb_endpoint})"
                )

                connection_params = {
                    "DYNAMODB_ENDPOINT": dynamodb_endpoint,
                    "DYNAMODB_TABLE": os.getenv("DYNAMODB_TABLE", "frank-submissions"),
                    "DYNAMODB_AUDIT_TABLE": os.getenv("DYNAMODB_AUDIT_TABLE", "frank-audit"),
                    "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", "test"),
                    "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
                    "AWS_REGION": os.getenv("AWS_REGION", "eu-west-1"),
                }

                return DynamoDBFRANKDatabase(connection_params=connection_params)

            except Exception as e:
                logger.warning(f"Failed to initialize DynamoDB: {e}")
                logger.info("Falling back to SQLite")

        # Fallback to SQLite for local development
        try:
            from frank.storage.sqlite import SQLiteFRANKDatabase

            db_path = os.getenv("SQLITE_DB_PATH", "/tmp/frank_main.db")
            logger.info(
                f"Initializing SQLite for {env_config.environment.value} "
                f"(path: {db_path})"
            )

            return SQLiteFRANKDatabase(connection_params={"SQLITE_DB_PATH": db_path})

        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")
            raise

    else:
        # AWS environment: Use DynamoDB
        try:
            from frank.storage.dynamodb import DynamoDBFRANKDatabase

            logger.info(
                f"Initializing DynamoDB for {env_config.environment.value} "
                f"(AWS {os.getenv('AWS_REGION', 'eu-west-1')})"
            )

            connection_params = {
                "DYNAMODB_TABLE": os.getenv("DYNAMODB_TABLE", "frank-submissions"),
                "DYNAMODB_AUDIT_TABLE": os.getenv("DYNAMODB_AUDIT_TABLE", "frank-audit"),
                "AWS_REGION": os.getenv("AWS_REGION", "eu-west-1"),
            }

            return DynamoDBFRANKDatabase(connection_params=connection_params)

        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB for AWS: {e}")
            raise


def create_app():
    """Factory function for creating the app (used by uvicorn with --factory)"""
    global _app_instance, _database_instance, _cognito_instance

    if _app_instance is not None:
        return _app_instance

    # Initialize environment config
    env_config = EnvironmentConfig.configure()

    # Create database
    _database_instance = create_database()

    # Create Cognito service
    _cognito_instance = get_cognito_service()
    logging.info(f"Cognito service initialized for {env_config.environment.value}")

    # Create app
    _app_instance = create_main_app(
        database=_database_instance,
        cognito_service=_cognito_instance
    )

    return _app_instance


def main():
    """Main function with argparse for uvicorn configuration"""
    CURRENT_MODULE = "frank.main.server"

    parser = argparse.ArgumentParser(description="FRANK Main API Server")
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host to bind the server to (default: HOST or 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8002")),
        help="Port to run the Main API on (default: PORT or 8002)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("RELOAD", "False").lower() in ("true", "1", "yes"),
        help="Enable auto-reload for development (default: False or RELOAD)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=os.getenv("LOG_LEVEL", "info"),
        choices=["debug", "info", "warning", "error"],
        help="Logging level (default: info or LOG_LEVEL)"
    )

    # Environment configuration
    parser.add_argument(
        "--environment",
        type=str,
        default=os.getenv("FRANK_ENVIRONMENT"),
        help="FRANK environment (default: FRANK_ENVIRONMENT env var)"
    )
    parser.add_argument(
        "--stage",
        type=int,
        default=None,
        help="Infrastructure stage 1-4 (default: FRANK_STAGE env var)"
    )

    args = parser.parse_args()

    # Set environment variables for app initialization
    if args.environment:
        os.environ["FRANK_ENVIRONMENT"] = args.environment
    if args.stage is not None:
        os.environ["FRANK_STAGE"] = str(args.stage)

    # Setup logging
    logger = setup_logging(args.log_level)

    # Initialize environment config
    env_config = EnvironmentConfig.configure()

    # Log startup configuration
    logger.info(f"Starting FRANK Main API on {args.host}:{args.port}")
    logger.info(f"Version: {frank.__version__}")
    logger.info(f"Environment: {env_config.environment.value}")
    logger.info(f"Stage: {env_config.stage}")
    logger.info(f"Reload enabled: {args.reload}")
    logger.info(f"Log level: {args.log_level}")

    # Run uvicorn server
    uvicorn.run(
        f"{CURRENT_MODULE}:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
        log_level=args.log_level
    )


if __name__ == "__main__":  # pragma: no cover
    main()
