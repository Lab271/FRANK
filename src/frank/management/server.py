#!/usr/bin/env python3
"""
FRANK Platform - Management API Server

Entry point for running the Management API server.

Usage:
    python -m frank.management.server
    python -m frank.management.server --port 8001 --reload

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import argparse
import logging
import os
from pathlib import Path

import uvicorn

import frank
from frank.auth.config import AuthConfig
from frank.management.api import create_management_app
from frank.management.cognito_service import get_cognito_service
from frank.storage.sqlite import create_sqlite_database


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


def create_app():
    """Factory function for creating the app (used by uvicorn with --factory)"""
    global _app_instance

    if _app_instance is not None:
        return _app_instance

    # Initialize auth config from environment
    AuthConfig.configure()

    # Create database
    db_path = os.getenv("FRANK_DB_PATH", "/tmp/frank_management.db")
    logger = logging.getLogger(__name__)
    database = create_sqlite_database(db_path, logger=logger)

    # Create Cognito service
    cognito_service = get_cognito_service()

    # Create app
    _app_instance = create_management_app(
        database=database,
        cognito_service=cognito_service
    )

    return _app_instance


def main():
    """Main function with argparse for uvicorn configuration"""
    CURRENT_MODULE = "frank.management.server"

    parser = argparse.ArgumentParser(description="FRANK Management API Server")
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host to bind the server to (default: HOST or 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8001")),
        help="Port to run the Management API on (default: PORT or 8001)"
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

    # Database options
    parser.add_argument(
        "--db-path",
        type=str,
        default=os.getenv("FRANK_DB_PATH", "/tmp/frank_management.db"),
        help="Path to SQLite database (default: /tmp/frank_management.db or FRANK_DB_PATH)"
    )

    # Auth configuration
    parser.add_argument(
        "--cognito-url",
        type=str,
        default=os.getenv("COGNITO_URL", "http://localhost:8100"),
        help="Cognito service URL (default: http://localhost:8100 or COGNITO_URL)"
    )
    parser.add_argument(
        "--auth-mode",
        type=str,
        default=os.getenv("FRANK_AUTH_MODE", "mock"),
        choices=["mock", "aws"],
        help="Authentication mode: mock or aws (default: mock or FRANK_AUTH_MODE)"
    )

    args = parser.parse_args()

    # Set environment variables for app initialization
    os.environ["FRANK_DB_PATH"] = args.db_path
    os.environ["COGNITO_URL"] = args.cognito_url
    os.environ["FRANK_AUTH_MODE"] = args.auth_mode

    # Setup logging
    logger = setup_logging(args.log_level)

    # Log startup configuration
    logger.info(f"Starting FRANK Management API on {args.host}:{args.port}")
    logger.info(f"Version: {frank.__version__}")
    logger.info(f"Reload enabled: {args.reload}")
    logger.info(f"Log level: {args.log_level}")
    logger.info(f"Database path: {args.db_path}")
    logger.info(f"Auth mode: {args.auth_mode}")
    logger.info(f"Cognito URL: {args.cognito_url}")

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
