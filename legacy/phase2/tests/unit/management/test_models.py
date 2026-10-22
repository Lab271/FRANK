#!/usr/bin/env python3
"""
Tests for frank.management.models module.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import pytest
from pydantic import ValidationError

from frank.core.enum import AccessTier
from frank.management.models import (
    OrganisationCreate,
    OrganisationMemberCreate,
    OrganisationMemberResponse,
    OrganisationResponse,
    OrganisationUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)


class TestOrganisationCreate:
    """Tests for OrganisationCreate model"""

    def test_minimal_create(self):
        """Test creating organisation with minimal data"""
        org = OrganisationCreate(name="Test Org")

        assert org.name == "Test Org"
        assert org.organisation_type == "customer"
        assert org.access_level == AccessTier.OBSERVER
        assert org.organisation_id is None

    def test_full_create(self):
        """Test creating organisation with all fields"""
        org = OrganisationCreate(
            name="Full Org",
            organisation_id="identity--123",
            organisation_type="cyber_partner",
            access_level=AccessTier.PARTNER,
            sector="financial",
            region="eu-west-1",
            client_count=50
        )

        assert org.name == "Full Org"
        assert org.organisation_id == "identity--123"
        assert org.organisation_type == "cyber_partner"
        assert org.access_level == AccessTier.PARTNER
        assert org.sector == "financial"
        assert org.region == "eu-west-1"
        assert org.client_count == 50

    def test_invalid_organisation_type(self):
        """Test invalid organisation type raises error"""
        with pytest.raises(ValidationError) as exc_info:
            OrganisationCreate(name="Test", organisation_type="invalid")

        assert "organisation_type must be one of" in str(exc_info.value)

    def test_empty_name_raises_error(self):
        """Test empty name raises validation error"""
        with pytest.raises(ValidationError):
            OrganisationCreate(name="")

    def test_negative_client_count_raises_error(self):
        """Test negative client count raises error"""
        with pytest.raises(ValidationError):
            OrganisationCreate(name="Test", client_count=-1)


class TestOrganisationUpdate:
    """Tests for OrganisationUpdate model"""

    def test_empty_update(self):
        """Test update with no fields"""
        update = OrganisationUpdate()

        assert update.name is None
        assert update.organisation_type is None
        assert update.access_level is None

    def test_partial_update(self):
        """Test partial update"""
        update = OrganisationUpdate(name="New Name", sector="technology")

        assert update.name == "New Name"
        assert update.sector == "technology"
        assert update.organisation_type is None

    def test_invalid_org_type_in_update(self):
        """Test invalid organisation type in update"""
        with pytest.raises(ValidationError):
            OrganisationUpdate(organisation_type="invalid")


class TestOrganisationResponse:
    """Tests for OrganisationResponse model"""

    def test_response_serialization(self):
        """Test response serializes correctly"""
        response = OrganisationResponse(
            organisation_id="identity--123",
            organisation_type="customer",
            name="Test Org"
        )

        data = response.model_dump()
        assert data["organisation_id"] == "identity--123"
        assert data["name"] == "Test Org"

    def test_datetime_serialization(self):
        """Test datetime fields serialize as ISO strings"""
        from datetime import datetime, timezone

        response = OrganisationResponse(
            organisation_id="identity--123",
            organisation_type="customer",
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        data = response.model_dump()
        assert data["created_at"] == "2025-01-01T12:00:00+00:00"


class TestUserCreate:
    """Tests for UserCreate model"""

    def test_minimal_create(self):
        """Test creating user with minimal data"""
        user = UserCreate(
            username="testuser",
            email="test@example.com"
        )

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.temporary_password is True
        assert user.groups == []

    def test_full_create(self):
        """Test creating user with all fields"""
        user = UserCreate(
            username="admin_user",
            email="admin@example.com",
            password="SecurePass123!",
            groups=["core_member", "admin"],
            temporary_password=False
        )

        assert user.username == "admin_user"
        assert user.email == "admin@example.com"
        assert user.password == "SecurePass123!"
        assert user.groups == ["core_member", "admin"]
        assert user.temporary_password is False

    def test_invalid_username(self):
        """Test invalid username characters raise error"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(username="user@domain", email="test@example.com")

        assert "Username can only contain" in str(exc_info.value)

    def test_invalid_email(self):
        """Test invalid email raises error"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(username="testuser", email="invalid-email")

        assert "Invalid email format" in str(exc_info.value)

    def test_email_normalized_to_lowercase(self):
        """Test email is normalized to lowercase"""
        user = UserCreate(
            username="testuser",
            email="Test@EXAMPLE.COM"
        )

        assert user.email == "test@example.com"

    def test_short_username(self):
        """Test short username raises error"""
        with pytest.raises(ValidationError):
            UserCreate(username="ab", email="test@example.com")

    def test_short_password(self):
        """Test short password raises error"""
        with pytest.raises(ValidationError):
            UserCreate(username="testuser", email="test@example.com", password="short")


class TestUserUpdate:
    """Tests for UserUpdate model"""

    def test_empty_update(self):
        """Test update with no fields"""
        update = UserUpdate()

        assert update.email is None
        assert update.groups is None
        assert update.enabled is None

    def test_partial_update(self):
        """Test partial update"""
        update = UserUpdate(enabled=False, groups=["observer"])

        assert update.enabled is False
        assert update.groups == ["observer"]
        assert update.email is None


class TestUserResponse:
    """Tests for UserResponse model"""

    def test_response_serialization(self):
        """Test response serializes correctly"""
        response = UserResponse(
            username="testuser",
            email="test@example.com",
            groups=["observer"],
            enabled=True
        )

        data = response.model_dump()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["groups"] == ["observer"]
        assert data["enabled"] is True


class TestOrganisationMemberCreate:
    """Tests for OrganisationMemberCreate model"""

    def test_minimal_create(self):
        """Test creating member with defaults"""
        member = OrganisationMemberCreate(username="testuser")

        assert member.username == "testuser"
        assert member.role == "member"

    def test_admin_role(self):
        """Test creating member with admin role"""
        member = OrganisationMemberCreate(username="adminuser", role="admin")

        assert member.role == "admin"

    def test_owner_role(self):
        """Test creating member with owner role"""
        member = OrganisationMemberCreate(username="owner", role="owner")

        assert member.role == "owner"

    def test_invalid_role(self):
        """Test invalid role raises error"""
        with pytest.raises(ValidationError) as exc_info:
            OrganisationMemberCreate(username="user", role="superadmin")

        assert "role must be one of" in str(exc_info.value)


class TestOrganisationMemberResponse:
    """Tests for OrganisationMemberResponse model"""

    def test_response_serialization(self):
        """Test response serializes correctly"""
        response = OrganisationMemberResponse(
            organisation_id="identity--123",
            username="testuser",
            role="member"
        )

        data = response.model_dump()
        assert data["organisation_id"] == "identity--123"
        assert data["username"] == "testuser"
        assert data["role"] == "member"


class TestOrganisationValidators:
    """Tests for Organisation model validators."""

    def test_organisation_type_none_accepted(self):
        """Test that None organisation_type is accepted in updates."""
        # This should not raise an error
        update = OrganisationUpdate(name="Test", organisation_type=None)
        assert update.organisation_type is None


class TestUserCreateValidators:
    """Tests for UserCreate model validators."""

    def test_email_invalid_missing_at(self):
        """Test invalid email without @ symbol."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="testuser",
                password="SecurePass123!",
                email="invalidemail.com"
            )
        assert "Invalid email format" in str(exc_info.value)

    def test_email_invalid_missing_dot(self):
        """Test invalid email without dot."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="testuser",
                password="SecurePass123!",
                email="invalid@emailcom"
            )
        assert "Invalid email format" in str(exc_info.value)

    def test_email_normalized_to_lowercase(self):
        """Test email is normalized to lowercase."""
        user = UserCreate(
            username="testuser",
            password="SecurePass123!",
            email="Test.User@EXAMPLE.COM"
        )
        assert user.email == "test.user@example.com"


class TestUserUpdateValidators:
    """Tests for UserUpdate model validators."""

    def test_email_none_in_update(self):
        """Test that None email is accepted in updates."""
        update = UserUpdate(email=None)
        assert update.email is None

    def test_email_validation_in_update(self):
        """Test email validation in update model."""
        with pytest.raises(ValidationError) as exc_info:
            UserUpdate(email="not-an-email")
        assert "Invalid email format" in str(exc_info.value)
