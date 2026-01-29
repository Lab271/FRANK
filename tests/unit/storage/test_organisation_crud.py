#!/usr/bin/env python3
"""
Tests for organisation CRUD operations in frank.storage.sqlite module.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
import os
import tempfile
import pytest

from frank.storage.sqlite import create_sqlite_database
from frank.storage.exceptions import FRANKStorageError


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    logger = logging.getLogger(__name__)
    db = create_sqlite_database(db_path, logger=logger)

    yield db

    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


class TestOrganisationCRUD:
    """Tests for organisation CRUD operations"""

    def test_create_organisation(self, test_db):
        """Test creating an organisation"""
        org_data = {
            "name": "Test Organisation",
            "organisation_type": "customer",
            "access_level": "observer",
            "sector": "financial",
            "region": "eu-west-1"
        }

        result = test_db.create_organisation(org_data)

        assert result is not None
        assert result["name"] == "Test Organisation"
        assert result["organisation_type"] == "customer"
        assert result["sector"] == "financial"
        assert "organisation_id" in result

    def test_create_organisation_auto_id(self, test_db):
        """Test that organisation_id is auto-generated"""
        org_data = {"name": "Auto ID Org"}

        result = test_db.create_organisation(org_data)

        assert result["organisation_id"].startswith("identity--")

    def test_create_organisation_custom_id(self, test_db):
        """Test creating organisation with custom ID"""
        org_data = {
            "name": "Custom ID Org",
            "organisation_id": "identity--custom-123"
        }

        result = test_db.create_organisation(org_data)

        assert result["organisation_id"] == "identity--custom-123"

    def test_create_duplicate_organisation_fails(self, test_db):
        """Test creating duplicate organisation raises error"""
        org_data = {
            "name": "Duplicate Org",
            "organisation_id": "identity--duplicate"
        }

        test_db.create_organisation(org_data)

        with pytest.raises(FRANKStorageError):
            test_db.create_organisation(org_data)

    def test_get_organisation(self, test_db):
        """Test retrieving an organisation"""
        org_data = {
            "name": "Get Test Org",
            "organisation_id": "identity--get-test"
        }
        test_db.create_organisation(org_data)

        result = test_db.get_organisation("identity--get-test")

        assert result is not None
        assert result["name"] == "Get Test Org"
        assert result["organisation_id"] == "identity--get-test"

    def test_get_nonexistent_organisation(self, test_db):
        """Test getting non-existent organisation returns None"""
        result = test_db.get_organisation("identity--nonexistent")

        assert result is None

    def test_list_organisations(self, test_db):
        """Test listing organisations"""
        # Create multiple organisations
        for i in range(3):
            test_db.create_organisation({
                "name": f"List Org {i}",
                "organisation_id": f"identity--list-{i}"
            })

        result = test_db.list_organisations()

        assert len(result) == 3

    def test_list_organisations_with_filter(self, test_db):
        """Test listing organisations with type filter"""
        test_db.create_organisation({
            "name": "Customer Org",
            "organisation_type": "customer"
        })
        test_db.create_organisation({
            "name": "Partner Org",
            "organisation_type": "cyber_partner"
        })

        customers = test_db.list_organisations(organisation_type="customer")
        partners = test_db.list_organisations(organisation_type="cyber_partner")

        assert len(customers) == 1
        assert len(partners) == 1
        assert customers[0]["name"] == "Customer Org"
        assert partners[0]["name"] == "Partner Org"

    def test_list_organisations_with_limit(self, test_db):
        """Test listing organisations with limit"""
        for i in range(5):
            test_db.create_organisation({
                "name": f"Limit Org {i}",
                "organisation_id": f"identity--limit-{i}"
            })

        result = test_db.list_organisations(limit=2)

        assert len(result) == 2

    def test_update_organisation(self, test_db):
        """Test updating an organisation"""
        org_data = {
            "name": "Update Test Org",
            "organisation_id": "identity--update-test",
            "sector": "financial"
        }
        test_db.create_organisation(org_data)

        result = test_db.update_organisation(
            "identity--update-test",
            {"sector": "technology", "name": "Updated Org"}
        )

        assert result is not None
        assert result["sector"] == "technology"
        assert result["name"] == "Updated Org"

    def test_update_nonexistent_organisation(self, test_db):
        """Test updating non-existent organisation returns None"""
        result = test_db.update_organisation(
            "identity--nonexistent",
            {"sector": "technology"}
        )

        assert result is None

    def test_delete_organisation(self, test_db):
        """Test deleting an organisation"""
        org_data = {
            "name": "Delete Test Org",
            "organisation_id": "identity--delete-test"
        }
        test_db.create_organisation(org_data)

        result = test_db.delete_organisation("identity--delete-test")

        assert result is True
        assert test_db.get_organisation("identity--delete-test") is None

    def test_delete_nonexistent_organisation(self, test_db):
        """Test deleting non-existent organisation returns False"""
        result = test_db.delete_organisation("identity--nonexistent")

        assert result is False


class TestOrganisationMembers:
    """Tests for organisation member operations"""

    def test_add_member(self, test_db):
        """Test adding a member to an organisation"""
        # Create organisation first
        test_db.create_organisation({
            "name": "Member Test Org",
            "organisation_id": "identity--member-test"
        })

        result = test_db.add_organisation_member(
            "identity--member-test",
            "testuser",
            "member"
        )

        assert result["organisation_id"] == "identity--member-test"
        assert result["username"] == "testuser"
        assert result["role"] == "member"

    def test_add_member_with_admin_role(self, test_db):
        """Test adding a member with admin role"""
        test_db.create_organisation({
            "name": "Admin Test Org",
            "organisation_id": "identity--admin-test"
        })

        result = test_db.add_organisation_member(
            "identity--admin-test",
            "adminuser",
            "admin"
        )

        assert result["role"] == "admin"

    def test_add_duplicate_member_fails(self, test_db):
        """Test adding duplicate member raises error"""
        test_db.create_organisation({
            "name": "Duplicate Member Org",
            "organisation_id": "identity--dup-member"
        })
        test_db.add_organisation_member("identity--dup-member", "user1", "member")

        with pytest.raises(FRANKStorageError):
            test_db.add_organisation_member("identity--dup-member", "user1", "member")

    def test_add_member_invalid_role(self, test_db):
        """Test adding member with invalid role fails"""
        test_db.create_organisation({
            "name": "Invalid Role Org",
            "organisation_id": "identity--invalid-role"
        })

        with pytest.raises(FRANKStorageError):
            test_db.add_organisation_member("identity--invalid-role", "user1", "superadmin")

    def test_remove_member(self, test_db):
        """Test removing a member from an organisation"""
        test_db.create_organisation({
            "name": "Remove Member Org",
            "organisation_id": "identity--remove-member"
        })
        test_db.add_organisation_member("identity--remove-member", "user1", "member")

        result = test_db.remove_organisation_member("identity--remove-member", "user1")

        assert result is True

    def test_remove_nonexistent_member(self, test_db):
        """Test removing non-existent member returns False"""
        test_db.create_organisation({
            "name": "No Member Org",
            "organisation_id": "identity--no-member"
        })

        result = test_db.remove_organisation_member("identity--no-member", "nonexistent")

        assert result is False

    def test_get_organisation_members(self, test_db):
        """Test getting all members of an organisation"""
        test_db.create_organisation({
            "name": "Members List Org",
            "organisation_id": "identity--members-list"
        })
        test_db.add_organisation_member("identity--members-list", "user1", "member")
        test_db.add_organisation_member("identity--members-list", "user2", "admin")
        test_db.add_organisation_member("identity--members-list", "user3", "member")

        result = test_db.get_organisation_members("identity--members-list")

        assert len(result) == 3

    def test_get_organisation_members_filtered_by_role(self, test_db):
        """Test getting members filtered by role"""
        test_db.create_organisation({
            "name": "Role Filter Org",
            "organisation_id": "identity--role-filter"
        })
        test_db.add_organisation_member("identity--role-filter", "member1", "member")
        test_db.add_organisation_member("identity--role-filter", "admin1", "admin")
        test_db.add_organisation_member("identity--role-filter", "member2", "member")

        members = test_db.get_organisation_members("identity--role-filter", role="member")
        admins = test_db.get_organisation_members("identity--role-filter", role="admin")

        assert len(members) == 2
        assert len(admins) == 1

    def test_get_user_organisations(self, test_db):
        """Test getting all organisations a user belongs to"""
        test_db.create_organisation({
            "name": "User Org 1",
            "organisation_id": "identity--user-org-1"
        })
        test_db.create_organisation({
            "name": "User Org 2",
            "organisation_id": "identity--user-org-2"
        })

        test_db.add_organisation_member("identity--user-org-1", "multiuser", "member")
        test_db.add_organisation_member("identity--user-org-2", "multiuser", "admin")

        result = test_db.get_user_organisations("multiuser")

        assert len(result) == 2

    def test_get_organisation_member(self, test_db):
        """Test getting a specific organisation member"""
        test_db.create_organisation({
            "name": "Specific Member Org",
            "organisation_id": "identity--specific-member"
        })
        test_db.add_organisation_member("identity--specific-member", "specificuser", "admin")

        result = test_db.get_organisation_member("identity--specific-member", "specificuser")

        assert result is not None
        assert result["username"] == "specificuser"
        assert result["role"] == "admin"

    def test_get_nonexistent_organisation_member(self, test_db):
        """Test getting non-existent member returns None"""
        test_db.create_organisation({
            "name": "No Specific Member Org",
            "organisation_id": "identity--no-specific"
        })

        result = test_db.get_organisation_member("identity--no-specific", "nonexistent")

        assert result is None
