#!/usr/bin/env python3
"""
FRANK Platform - Initialize Comprehensive Fixture Data

This script initializes the database with comprehensive fixture data matching
the mock_cognito user pool. Run this after starting mock_cognito to populate
the database with organizations and user memberships.

Usage:
    # From project root with virtual environment activated
    python tests/spikes/014_cognito/init_fixtures.py

    # Or using uv (recommended)
    uv run python tests/spikes/014_cognito/init_fixtures.py

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
import sys
from pathlib import Path

# Add src to path so we can import frank
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from frank.storage.sqlite import SQLiteFRANKDatabase
from frank.util.sample_builder import ComprehensiveFixtureSeeder

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Initialize comprehensive fixture data"""

    logger.info("=== FRANK Comprehensive Fixture Initialization ===\n")

    # Create SQLite database (use environment variable or default location)
    import os
    db_path = os.environ.get("DB_PATH", "/tmp/frank_stage1.db")
    logger.info(f"Using database: {db_path}")

    db = SQLiteFRANKDatabase({"db_path": db_path}, logger=logger)

    # Seed with comprehensive fixture data
    logger.info("\nSeeding database with comprehensive fixture data...")
    seeder = ComprehensiveFixtureSeeder()
    success = seeder.seed(db)

    if success:
        logger.info("\n✅ Database seeded successfully!\n")

        # Display organizations
        logger.info("=== Organizations Created ===")
        orgs = [
            ("Schuberg Philis", "Core Member", "admin, ijsbrand"),
            ("S-Unit", "Partner", "s_unit_analyst"),
            ("Rabobank", "Contributor", "rabobank_security"),
            ("ING Bank", "Contributor", "ing_soc"),
            ("Gemeente Amsterdam", "Observer", "amsterdam_monitor"),
            ("KPN", "Observer", "kpn_observer")
        ]

        for name, tier, users in orgs:
            logger.info(f"  {name:25} | {tier:15} | Users: {users}")

        logger.info("\n=== Next Steps ===")
        logger.info("1. Start mock_cognito: python mock_cognito.py --reload")
        logger.info("2. Start FRANK server with the seeded database")
        logger.info("3. Login with any user (e.g., admin/admin123)")
        logger.info("\nUsers can now:")
        logger.info("  - Core Members (admin, ijsbrand): See everything")
        logger.info("  - Partner (s_unit_analyst): See partner-level data")
        logger.info("  - Contributors: See contributor-level data")
        logger.info("  - Observers: See only their own organization data")

    else:
        logger.error("❌ Database seeding failed!")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
