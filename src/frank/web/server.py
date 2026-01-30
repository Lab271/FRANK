#!/usr/bin/env python3
"""
FRANK Platform - Web GUI Server

Entry point for running the Web GUI server.

Usage:
    python -m frank.web.server
    python -m frank.web.server --port 3000 --reload

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import argparse
import logging
import os

import uvicorn

import frank
from frank.web.app import create_web_app
from frank.web.config import WebConfig


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

    # Initialize web config from environment
    config = WebConfig.configure()

    # Create app
    _app_instance = create_web_app(config=config)

    return _app_instance


def main():
    """Main function with argparse for uvicorn configuration"""
    CURRENT_MODULE = "frank.web.server"

    parser = argparse.ArgumentParser(description="FRANK Web GUI Server")
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host to bind the server to (default: HOST or 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "3000")),
        help="Port to run the Web GUI on (default: PORT or 3000)"
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

    # API configuration
    parser.add_argument(
        "--management-api-url",
        type=str,
        default=os.getenv("FRANK_MANAGEMENT_API_URL", "http://localhost:8001"),
        help="Management API URL (default: http://localhost:8001 or FRANK_MANAGEMENT_API_URL)"
    )
    parser.add_argument(
        "--cognito-url",
        type=str,
        default=os.getenv("COGNITO_URL", "http://localhost:8100"),
        help="Cognito service URL (default: http://localhost:8100 or COGNITO_URL)"
    )

    # Session configuration
    parser.add_argument(
        "--session-secret",
        type=str,
        default=os.getenv("FRANK_SESSION_SECRET"),
        help="Session secret key (default: FRANK_SESSION_SECRET or generated)"
    )

    args = parser.parse_args()

    # Set environment variables for app initialization
    os.environ["FRANK_MANAGEMENT_API_URL"] = args.management_api_url
    os.environ["COGNITO_URL"] = args.cognito_url
    if args.session_secret:
        os.environ["FRANK_SESSION_SECRET"] = args.session_secret
    if args.reload:
        os.environ["TEMPLATE_AUTO_RELOAD"] = "true"

    # Setup logging
    logger = setup_logging(args.log_level)

    # Log startup configuration
    logger.info(f"Starting FRANK Web GUI on {args.host}:{args.port}")
    logger.info(f"Version: {frank.__version__}")
    logger.info(f"Reload enabled: {args.reload}")
    logger.info(f"Log level: {args.log_level}")
    logger.info(f"Management API: {args.management_api_url}")
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
