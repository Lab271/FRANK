#!/usr/bin/env python3
"""
Tests for FRANK Admin Data Transfer Objects.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""



from frank.admin.models import (
    HealthStatus,
    MemberDTO,
    MemberListResult,
    OrganisationDTO,
    OrganisationListResult,
    UserDTO,
    UserListResult,
)


class TestOrganisationDTO:
    """Tests for OrganisationDTO."""

    def test_from_dict_complete(self):
        """Test creating DTO from complete dict."""
        data = {
            "organisation_id": "org-123",
            "name": "Test Org",
            "organisation_type": "customer",
            "sector": "Technology",
            "region": "EU",
            "client_count": 5,
            "created_at": "2025-01-15T10:30:00",
        }

        dto = OrganisationDTO.from_dict(data)

        assert dto.organisation_id == "org-123"
        assert dto.name == "Test Org"
        assert dto.organisation_type == "customer"
        assert dto.sector == "Technology"
        assert dto.region == "EU"
        assert dto.client_count == 5
        assert dto.created_at is not None

    def test_from_dict_minimal(self):
        """Test creating DTO from minimal dict."""
        data = {"organisation_id": "org-123", "name": "Test Org"}

        dto = OrganisationDTO.from_dict(data)

        assert dto.organisation_id == "org-123"
        assert dto.name == "Test Org"
        assert dto.organisation_type == ""
        assert dto.sector is None
        assert dto.region is None
        assert dto.client_count == 0

    def test_from_dict_empty(self):
        """Test creating DTO from empty dict."""
        dto = OrganisationDTO.from_dict({})

        assert dto.organisation_id == ""
        assert dto.name == ""

    def test_to_dict(self):
        """Test converting DTO to dict."""
        dto = OrganisationDTO(
            organisation_id="org-123",
            name="Test Org",
            organisation_type="customer",
            sector="Technology",
            region="EU",
        )

        result = dto.to_dict()

        assert result["name"] == "Test Org"
        assert result["organisation_type"] == "customer"
        assert result["sector"] == "Technology"
        assert result["region"] == "EU"
        assert "organisation_id" not in result  # Not included in request

    def test_to_dict_minimal(self):
        """Test converting DTO with minimal data."""
        dto = OrganisationDTO(
            organisation_id="org-123",
            name="Test Org",
            organisation_type="customer",
        )

        result = dto.to_dict()

        assert result["name"] == "Test Org"
        assert "sector" not in result
        assert "region" not in result


class TestOrganisationListResult:
    """Tests for OrganisationListResult."""

    def test_from_dict(self):
        """Test creating list result from dict."""
        data = {
            "organisations": [
                {"organisation_id": "org-1", "name": "Org 1"},
                {"organisation_id": "org-2", "name": "Org 2"},
            ],
            "total": 2,
        }

        result = OrganisationListResult.from_dict(data)

        assert len(result.organisations) == 2
        assert result.total == 2
        assert result.organisations[0].name == "Org 1"

    def test_from_dict_empty(self):
        """Test creating list result from empty dict."""
        result = OrganisationListResult.from_dict({})

        assert len(result.organisations) == 0
        assert result.total == 0


class TestMemberDTO:
    """Tests for MemberDTO."""

    def test_from_dict_complete(self):
        """Test creating DTO from complete dict."""
        data = {
            "username": "testuser",
            "role": "admin",
            "joined_at": "2025-01-15T10:30:00",
        }

        dto = MemberDTO.from_dict(data)

        assert dto.username == "testuser"
        assert dto.role == "admin"
        assert dto.joined_at is not None

    def test_from_dict_minimal(self):
        """Test creating DTO from minimal dict."""
        dto = MemberDTO.from_dict({"username": "testuser"})

        assert dto.username == "testuser"
        assert dto.role == "member"
        assert dto.joined_at is None


class TestMemberListResult:
    """Tests for MemberListResult."""

    def test_from_dict(self):
        """Test creating list result from dict."""
        data = {
            "members": [
                {"username": "user1", "role": "admin"},
                {"username": "user2", "role": "member"},
            ],
            "total": 2,
        }

        result = MemberListResult.from_dict(data)

        assert len(result.members) == 2
        assert result.total == 2


class TestUserDTO:
    """Tests for UserDTO."""

    def test_from_dict_complete(self):
        """Test creating DTO from complete dict."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "groups": ["FRANK_OBSERVER", "FRANK_CONTRIBUTOR"],
            "enabled": True,
            "created_at": "2025-01-15T10:30:00",
        }

        dto = UserDTO.from_dict(data)

        assert dto.username == "testuser"
        assert dto.email == "test@example.com"
        assert len(dto.groups) == 2
        assert dto.enabled is True

    def test_from_dict_minimal(self):
        """Test creating DTO from minimal dict."""
        dto = UserDTO.from_dict({"username": "testuser"})

        assert dto.username == "testuser"
        assert dto.email == ""
        assert dto.groups == []
        assert dto.enabled is True


class TestUserListResult:
    """Tests for UserListResult."""

    def test_from_dict(self):
        """Test creating list result from dict."""
        data = {
            "users": [
                {"username": "user1", "email": "user1@example.com"},
                {"username": "user2", "email": "user2@example.com"},
            ],
            "total": 2,
        }

        result = UserListResult.from_dict(data)

        assert len(result.users) == 2
        assert result.total == 2


class TestHealthStatus:
    """Tests for HealthStatus."""

    def test_from_dict(self):
        """Test creating health status from dict."""
        data = {"status": "healthy", "database": "healthy"}

        status = HealthStatus.from_dict(data)

        assert status.status == "healthy"
        assert status.database == "healthy"

    def test_is_healthy_true(self):
        """Test is_healthy when all healthy."""
        status = HealthStatus(status="healthy", database="healthy")

        assert status.is_healthy is True

    def test_is_healthy_false_api(self):
        """Test is_healthy when API unhealthy."""
        status = HealthStatus(status="error", database="healthy")

        assert status.is_healthy is False

    def test_is_healthy_false_db(self):
        """Test is_healthy when database unhealthy."""
        status = HealthStatus(status="healthy", database="error")

        assert status.is_healthy is False

    def test_from_dict_unknown(self):
        """Test creating health status from empty dict."""
        status = HealthStatus.from_dict({})

        assert status.status == "unknown"
        assert status.database == "unknown"
