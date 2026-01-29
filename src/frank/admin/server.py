#!/usr/bin/env python3
"""
FRANK Platform - Admin TUI Entry Point

CLI entry point for the frank-admin command.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import argparse
import logging
import os
import sys

import frank
from frank.admin.app import create_admin_app
from frank.admin.config import AdminConfig


def setup_logging(log_level: str = "warning") -> logging.Logger:
    """
    Setup logging configuration.

    Args:
        log_level: Logging level (debug, info, warning, error)

    Returns:
        Configured logger
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
    return logging.getLogger("frank.admin")


def main():
    """Main entry point for frank-admin command."""
    parser = argparse.ArgumentParser(
        description="FRANK Admin - Terminal-based Organisation & User Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  frank-admin                     Start the admin TUI
  frank-admin --api http://...    Connect to specific API endpoint
  frank-admin --version           Show version information

Environment Variables:
  FRANK_API_ENDPOINT     Management API URL (default: http://localhost:8001)
  FRANK_KEYRING_SERVICE  Keyring service name (default: frank-admin)
        """,
    )

    parser.add_argument(
        "--api",
        type=str,
        default=os.getenv("FRANK_API_ENDPOINT", "http://localhost:8001"),
        help="Management API endpoint URL",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default=os.getenv("FRANK_LOG_LEVEL", "warning"),
        choices=["debug", "info", "warning", "error"],
        help="Logging level (default: warning)",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information and exit",
    )

    args = parser.parse_args()

    # Handle version flag
    if args.version:
        print(f"FRANK Admin v{frank.__version__}")
        print(f"API Endpoint: {args.api}")
        sys.exit(0)

    # Setup logging
    logger = setup_logging(args.log_level)
    logger.info(f"Starting FRANK Admin v{frank.__version__}")
    logger.info(f"API Endpoint: {args.api}")

    # Configure admin
    config = AdminConfig.configure(api_endpoint=args.api)
    logger.debug(f"Configuration: {config}")

    # Create and run app
    app = create_admin_app(config=config)

    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
