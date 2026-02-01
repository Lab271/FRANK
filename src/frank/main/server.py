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


# Global app instance for uvicorn factory
_app_instance = None
_database_instance = None


def create_database() -> BaseFRANKDatabase:
    """
    Create database instance based on environment configuration.

    Returns:
        Database instance (DynamoDB for cloud, SQLite for local)
    """
    env_config = EnvironmentConfig.get()

    # For now, return None - database initialization will be added later
    # TODO: Initialize DynamoDB or SQLite based on env_config.is_local
    logging.info(
        f"Database initialization for {env_config.environment.value} "
        f"not yet implemented"
    )
    return None


def create_app():
    """Factory function for creating the app (used by uvicorn with --factory)"""
    global _app_instance, _database_instance

    if _app_instance is not None:
        return _app_instance

    # Initialize environment config
    env_config = EnvironmentConfig.configure()

    # Create database
    _database_instance = create_database()

    # Create app
    _app_instance = create_main_app(database=_database_instance)

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
