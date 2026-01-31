#!/usr/bin/env python3
"""
FRANK Platform - Database Seeding

Provides initial data seeding for the Management API database.
Seeds organisations and members that match the users in Mock Cognito.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
from typing import Dict, Any, List

from frank.storage.base import BaseFRANKDatabase

logger = logging.getLogger(__name__)

# Initial organisations matching Mock Cognito fixture data
INITIAL_ORGANISATIONS = [
    {
        "organisation_id": "identity--schuberg-philis",
        "organisation_type": "cyber_partner",
        "access_level": "core_member",
        "sector": "Technology",
        "region": "Netherlands",
        "contribution_score": 1000,
        "client_count": 50,
        "metadata": {
            "description": "Schuberg Philis - Core FRANK Platform Member",
            "website": "https://schubergphilis.com",
            "verified": True
        }
    },
    {
        "organisation_id": "identity--s-unit",
        "organisation_type": "cyber_partner",
        "access_level": "partner",
        "sector": "Security Services",
        "region": "Netherlands",
        "contribution_score": 750,
        "client_count": 25,
        "metadata": {
            "description": "S-Unit - Cybersecurity Partner",
            "website": "https://s-unit.nl",
            "verified": True
        }
    },
    {
        "organisation_id": "identity--rabobank",
        "organisation_type": "customer",
        "access_level": "contributor",
        "sector": "Finance",
        "region": "Netherlands",
        "contribution_score": 500,
        "client_count": 0,
        "metadata": {
            "description": "Rabobank - Financial Services Contributor",
            "website": "https://rabobank.nl",
            "verified": True
        }
    },
    {
        "organisation_id": "identity--ing",
        "organisation_type": "customer",
        "access_level": "contributor",
        "sector": "Finance",
        "region": "Netherlands",
        "contribution_score": 450,
        "client_count": 0,
        "metadata": {
            "description": "ING Bank - Financial Services Contributor",
            "website": "https://ing.nl",
            "verified": True
        }
    },
    {
        "organisation_id": "identity--gemeente-amsterdam",
        "organisation_type": "customer",
        "access_level": "observer",
        "sector": "Government",
        "region": "Netherlands",
        "contribution_score": 100,
        "client_count": 0,
        "metadata": {
            "description": "Gemeente Amsterdam - Government Observer",
            "website": "https://amsterdam.nl",
            "verified": True
        }
    },
    {
        "organisation_id": "identity--kpn",
        "organisation_type": "customer",
        "access_level": "observer",
        "sector": "Telecommunications",
        "region": "Netherlands",
        "contribution_score": 150,
        "client_count": 0,
        "metadata": {
            "description": "KPN - Telecommunications Observer",
            "website": "https://kpn.com",
            "verified": True
        }
    }
]

# Initial organisation members matching Mock Cognito users
INITIAL_MEMBERS = [
    # Schuberg Philis members
    {
        "organisation_id": "identity--schuberg-philis",
        "username": "admin",
        "role": "owner"
    },
    {
        "organisation_id": "identity--schuberg-philis",
        "username": "ijsbrand",
        "role": "admin"
    },
    # S-Unit members
    {
        "organisation_id": "identity--s-unit",
        "username": "s_unit_analyst",
        "role": "member"
    },
    # Rabobank members
    {
        "organisation_id": "identity--rabobank",
        "username": "rabobank_security",
        "role": "member"
    },
    # ING members
    {
        "organisation_id": "identity--ing",
        "username": "ing_soc",
        "role": "member"
    },
    # Gemeente Amsterdam members
    {
        "organisation_id": "identity--gemeente-amsterdam",
        "username": "amsterdam_monitor",
        "role": "member"
    },
    # KPN members
    {
        "organisation_id": "identity--kpn",
        "username": "kpn_observer",
        "role": "member"
    }
]


def seed_database(db: BaseFRANKDatabase, force: bool = False) -> Dict[str, Any]:
    """
    Seed the database with initial organisations and members.

    Args:
        db: Database instance to seed
        force: If True, reseed even if data exists (recreates all data)

    Returns:
        Dictionary with seeding results
    """
    logger.info("Starting database seeding...")
    results = {
        "organisations_created": 0,
        "members_created": 0,
        "organisations_updated": 0,
        "errors": []
    }

    # Check if database already has data
    if not force:
        existing_orgs = db.list_organisations(limit=1)
        if existing_orgs:
            logger.info("Database already seeded (found existing organisations). Use force=True to reseed.")
            return {
                **results,
                "message": "Database already seeded",
                "skipped": True
            }

    # Seed organisations
    logger.info(f"Seeding {len(INITIAL_ORGANISATIONS)} organisations...")
    for org in INITIAL_ORGANISATIONS:
        try:
            org_id = org["organisation_id"]
            success = db.upsert_organisation(org)
            if success:
                # Check if it was an update or create
                existing = db.get_organisation(org_id)
                if existing:
                    results["organisations_updated"] += 1
                else:
                    results["organisations_created"] += 1
                logger.info(f"  ✓ {org['organisation_id']} ({org['organisation_type']})")
            else:
                results["errors"].append(f"Failed to seed organisation: {org_id}")
                logger.error(f"  ✗ Failed: {org_id}")
        except Exception as e:
            results["errors"].append(f"Error seeding organisation {org.get('organisation_id')}: {str(e)}")
            logger.error(f"  ✗ Error: {org.get('organisation_id')} - {e}")

    # Seed organisation members
    logger.info(f"Seeding {len(INITIAL_MEMBERS)} organisation members...")
    for member in INITIAL_MEMBERS:
        try:
            success = db.add_organisation_member(
                organisation_id=member["organisation_id"],
                username=member["username"],
                role=member["role"]
            )
            if success:
                results["members_created"] += 1
                logger.info(f"  ✓ {member['username']} → {member['organisation_id']} ({member['role']})")
            else:
                results["errors"].append(
                    f"Failed to add member: {member['username']} to {member['organisation_id']}"
                )
                logger.error(f"  ✗ Failed: {member['username']}")
        except Exception as e:
            results["errors"].append(
                f"Error adding member {member['username']} to {member['organisation_id']}: {str(e)}"
            )
            logger.error(f"  ✗ Error: {member['username']} - {e}")

    logger.info(
        f"Database seeding complete: {results['organisations_created']} orgs created, "
        f"{results['organisations_updated']} orgs updated, {results['members_created']} members added"
    )

    if results["errors"]:
        logger.warning(f"Seeding completed with {len(results['errors'])} errors")

    results["message"] = "Database seeded successfully"
    results["skipped"] = False
    return results


def check_seed_status(db: BaseFRANKDatabase) -> Dict[str, Any]:
    """
    Check if the database has been seeded with initial data.

    Args:
        db: Database instance to check

    Returns:
        Dictionary with seed status information
    """
    try:
        orgs = db.list_organisations()
        org_count = len(orgs)

        # Count total members across all organisations
        member_count = 0
        for org in orgs:
            members = db.get_organisation_members(org["organisation_id"])
            member_count += len(members)

        is_seeded = org_count > 0

        return {
            "is_seeded": is_seeded,
            "organisation_count": org_count,
            "member_count": member_count,
            "expected_organisations": len(INITIAL_ORGANISATIONS),
            "expected_members": len(INITIAL_MEMBERS),
            "fully_seeded": (
                org_count >= len(INITIAL_ORGANISATIONS) and
                member_count >= len(INITIAL_MEMBERS)
            )
        }
    except Exception as e:
        logger.error(f"Error checking seed status: {e}")
        return {
            "is_seeded": False,
            "error": str(e)
        }


def auto_seed_on_startup(db: BaseFRANKDatabase) -> None:
    """
    Automatically seed the database on startup if it's empty.

    This function is designed to be called during application initialization.
    It will only seed if the database is empty (no organisations exist).

    Args:
        db: Database instance to seed
    """
    try:
        status = check_seed_status(db)

        if not status.get("is_seeded"):
            logger.info("Database is empty - running automatic seeding...")
            result = seed_database(db, force=False)

            if result.get("errors"):
                logger.warning(f"Auto-seeding completed with errors: {result['errors']}")
            else:
                logger.info("Auto-seeding completed successfully")
        else:
            logger.info(
                f"Database already seeded: {status['organisation_count']} organisations, "
                f"{status['member_count']} members"
            )
    except Exception as e:
        logger.error(f"Error during auto-seed: {e}")
        # Don't fail the application startup if seeding fails
