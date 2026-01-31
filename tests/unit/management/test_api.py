#!/usr/bin/env python3
"""
Tests for FRANK Management API endpoints.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from frank.auth import TokenPayload
from frank.core.enum import AccessTier
from frank.management.api import create_management_app
from frank.management.cognito_service import (
    BaseCognitoService,
    CognitoServiceError,
    MFASetupError,
    MFAVerificationError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from frank.storage.base import BaseFRANKDatabase
from frank.storage.exceptions import FRANKStorageError


@pytest.fixture
def mock_database():
    """Create a mock database for testing."""
    db = MagicMock(spec=BaseFRANKDatabase)
    db.health_check.return_value = {"status": "healthy"}
    return db


@pytest.fixture
def mock_cognito():
    """Create a mock Cognito service for testing."""
    cognito = AsyncMock(spec=BaseCognitoService)
    return cognito


@pytest.fixture
def core_member_user():
    """Create a CORE_MEMBER user token payload."""
    return TokenPayload(
        username="admin_user",
        groups=["FRANK_CORE_MEMBER"],
        access_tier=AccessTier.CORE_MEMBER,
        organisation_id="org-test-123",
        validation_source="test"
    )


@pytest.fixture
def observer_user():
    """Create an OBSERVER user token payload."""
    return TokenPayload(
        username="observer_user",
        groups=["FRANK_OBSERVER"],
        access_tier=AccessTier.OBSERVER,
        organisation_id="org-test-123",
        validation_source="test"
    )


def create_test_app(mock_database, mock_cognito, user):
    """Create a test app with overridden auth dependencies."""
    from frank.auth.dependencies import get_current_user

    app = create_management_app(
        database=mock_database,
        cognito_service=mock_cognito
    )

    # Override the get_current_user dependency to return our test user
    app.dependency_overrides[get_current_user] = lambda: user

    return app


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_returns_healthy(self, mock_database, mock_cognito):
        """Test health check returns healthy status."""
        app = create_management_app(database=mock_database, cognito_service=mock_cognito)
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "frank-management-api"
        assert "version" in data
        assert "timestamp" in data
        assert data["database"] == "healthy"

    def test_health_check_without_database(self, mock_cognito):
        """Test health check without database configured."""
        app = create_management_app(database=None, cognito_service=mock_cognito)
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" not in data

    def test_health_check_with_unhealthy_database(self, mock_database, mock_cognito):
        """Test health check when database is unhealthy."""
        mock_database.health_check.side_effect = Exception("DB connection failed")
        app = create_management_app(database=mock_database, cognito_service=mock_cognito)
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["database"] == "unhealthy"
        assert "database_error" in data


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_returns_api_info(self, mock_database, mock_cognito):
        """Test root endpoint returns API information."""
        app = create_management_app(database=mock_database, cognito_service=mock_cognito)
        client = TestClient(app)

        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "FRANK Management API"
        assert "version" in data
        assert "endpoints" in data
        assert "timestamp" in data


class TestOrganisationEndpoints:
    """Tests for organisation CRUD endpoints."""

    def test_create_organisation_success(self, mock_database, mock_cognito, core_member_user):
        """Test creating an organisation."""
        mock_database.create_organisation.return_value = {
            "organisation_id": "org-123",
            "name": "Test Org",
            "organisation_type": "customer",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/organisations",
            json={"name": "Test Org", "organisation_type": "customer"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["organisation_id"] == "org-123"
        assert data["name"] == "Test Org"

    def test_create_organisation_conflict(self, mock_database, mock_cognito, core_member_user):
        """Test creating organisation when name already exists."""
        mock_database.create_organisation.side_effect = FRANKStorageError("Organisation already exists")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/organisations",
            json={"name": "Existing Org", "organisation_type": "customer"}
        )

        assert response.status_code == 409

    def test_list_organisations(self, mock_database, mock_cognito, core_member_user):
        """Test listing organisations."""
        mock_database.list_organisations.return_value = [
            {"organisation_id": "org-1", "name": "Org 1", "organisation_type": "customer"},
            {"organisation_id": "org-2", "name": "Org 2", "organisation_type": "cyber_partner"}
        ]

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/organisations")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["organisations"]) == 2

    def test_list_organisations_with_filters(self, mock_database, mock_cognito, core_member_user):
        """Test listing organisations with query filters."""
        mock_database.list_organisations.return_value = []

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get(
            "/v1/organisations",
            params={"organisation_type": "customer", "sector": "finance", "limit": 50}
        )

        assert response.status_code == 200
        mock_database.list_organisations.assert_called_once_with(
            organisation_type="customer",
            access_level=None,
            sector="finance",
            limit=50,
            offset=0
        )

    def test_get_organisation_success(self, mock_database, mock_cognito, core_member_user):
        """Test getting a specific organisation."""
        mock_database.get_organisation.return_value = {
            "organisation_id": "org-123",
            "name": "Test Org",
            "organisation_type": "customer"
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/organisations/org-123")

        assert response.status_code == 200
        data = response.json()
        assert data["organisation_id"] == "org-123"

    def test_get_organisation_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test getting non-existent organisation."""
        mock_database.get_organisation.return_value = None

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/organisations/nonexistent")

        assert response.status_code == 404

    def test_update_organisation_success(self, mock_database, mock_cognito, core_member_user):
        """Test updating an organisation."""
        mock_database.update_organisation.return_value = {
            "organisation_id": "org-123",
            "name": "Updated Org",
            "organisation_type": "customer"
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.put(
            "/v1/organisations/org-123",
            json={"name": "Updated Org"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Org"

    def test_update_organisation_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test updating non-existent organisation."""
        mock_database.update_organisation.return_value = None

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.put(
            "/v1/organisations/nonexistent",
            json={"name": "Updated Org"}
        )

        assert response.status_code == 404

    def test_delete_organisation_success(self, mock_database, mock_cognito, core_member_user):
        """Test deleting an organisation."""
        mock_database.delete_organisation.return_value = True

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.delete("/v1/organisations/org-123")

        assert response.status_code == 204

    def test_delete_organisation_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test deleting non-existent organisation."""
        mock_database.delete_organisation.return_value = False

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.delete("/v1/organisations/nonexistent")

        assert response.status_code == 404


class TestOrganisationMemberEndpoints:
    """Tests for organisation member endpoints."""

    def test_add_member_success(self, mock_database, mock_cognito, core_member_user):
        """Test adding member to organisation."""
        mock_database.get_organisation.return_value = {"organisation_id": "org-123", "name": "Test Org"}
        mock_database.add_organisation_member.return_value = {
            "organisation_id": "org-123",
            "username": "newuser",
            "role": "member",
            "joined_at": datetime.now(timezone.utc).isoformat()
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/organisations/org-123/members",
            json={"username": "newuser", "role": "member"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["role"] == "member"

    def test_add_member_organisation_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test adding member to non-existent organisation."""
        mock_database.get_organisation.return_value = None

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/organisations/nonexistent/members",
            json={"username": "user1", "role": "member"}
        )

        assert response.status_code == 404

    def test_add_member_conflict(self, mock_database, mock_cognito, core_member_user):
        """Test adding member who is already a member."""
        mock_database.get_organisation.return_value = {"organisation_id": "org-123", "name": "Test Org"}
        mock_database.add_organisation_member.side_effect = FRANKStorageError("Member already exists")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/organisations/org-123/members",
            json={"username": "existinguser", "role": "member"}
        )

        assert response.status_code == 409

    def test_list_organisation_members(self, mock_database, mock_cognito, core_member_user):
        """Test listing organisation members."""
        mock_database.get_organisation.return_value = {"organisation_id": "org-123", "name": "Test Org"}
        mock_database.get_organisation_members.return_value = [
            {"organisation_id": "org-123", "username": "user1", "role": "member"},
            {"organisation_id": "org-123", "username": "user2", "role": "admin"}
        ]

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/organisations/org-123/members")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["members"]) == 2

    def test_list_members_organisation_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test listing members of non-existent organisation."""
        mock_database.get_organisation.return_value = None

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/organisations/nonexistent/members")

        assert response.status_code == 404

    def test_remove_member_success(self, mock_database, mock_cognito, core_member_user):
        """Test removing member from organisation."""
        mock_database.remove_organisation_member.return_value = True

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.delete("/v1/organisations/org-123/members/user1")

        assert response.status_code == 204

    def test_remove_member_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test removing non-existent member."""
        mock_database.remove_organisation_member.return_value = False

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.delete("/v1/organisations/org-123/members/nonexistent")

        assert response.status_code == 404


class TestUserEndpoints:
    """Tests for user CRUD endpoints via Cognito."""

    def test_create_user_success(self, mock_database, mock_cognito, core_member_user):
        """Test creating a user."""
        mock_database.get_organisation.return_value = {"organisation_id": "org-123", "name": "Test Org"}
        mock_cognito.create_user.return_value = {
            "username": "newuser",
            "email": "new@example.com",
            "groups": ["FRANK_OBSERVER"],
            "enabled": True
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/organisations/org-123/users",
            json={"username": "newuser", "email": "new@example.com", "password": "SecurePass123!"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"

    def test_create_user_organisation_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test creating user in non-existent organisation."""
        mock_database.get_organisation.return_value = None

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/organisations/nonexistent/users",
            json={"username": "newuser", "email": "new@example.com", "password": "SecurePass123!"}
        )

        assert response.status_code == 404

    def test_create_user_already_exists(self, mock_database, mock_cognito, core_member_user):
        """Test creating user that already exists."""
        mock_database.get_organisation.return_value = {"organisation_id": "org-123", "name": "Test Org"}
        mock_cognito.create_user.side_effect = UserAlreadyExistsError("existinguser")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/organisations/org-123/users",
            json={"username": "existinguser", "email": "existing@example.com", "password": "SecurePass123!"}
        )

        assert response.status_code == 409

    def test_create_user_cognito_error(self, mock_database, mock_cognito, core_member_user):
        """Test creating user with Cognito error."""
        mock_database.get_organisation.return_value = {"organisation_id": "org-123", "name": "Test Org"}
        mock_cognito.create_user.side_effect = CognitoServiceError("Service unavailable", status_code=503)

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/organisations/org-123/users",
            json={"username": "newuser", "email": "new@example.com", "password": "SecurePass123!"}
        )

        assert response.status_code == 503

    def test_create_user_already_member(self, mock_database, mock_cognito, core_member_user):
        """Test creating user who is already a member of the organisation."""
        mock_database.get_organisation.return_value = {"organisation_id": "org-123", "name": "Test Org"}
        mock_cognito.create_user.return_value = {
            "username": "existinguser",
            "email": "existing@example.com",
            "groups": ["FRANK_OBSERVER"],
            "enabled": True
        }
        # User creation succeeds but adding as member fails (already exists)
        mock_database.add_organisation_member.side_effect = FRANKStorageError("User already a member")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/organisations/org-123/users",
            json={"username": "existinguser", "email": "existing@example.com", "password": "SecurePass123!"}
        )

        # Should succeed - the exception is caught and ignored
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "existinguser"

    def test_list_organisation_users(self, mock_database, mock_cognito, core_member_user):
        """Test listing users in organisation."""
        mock_database.get_organisation.return_value = {"organisation_id": "org-123", "name": "Test Org"}
        mock_database.get_organisation_members.return_value = [
            {"organisation_id": "org-123", "username": "user1", "role": "member"}
        ]
        mock_cognito.get_user.return_value = {
            "username": "user1",
            "email": "user1@example.com",
            "groups": ["FRANK_OBSERVER"],
            "enabled": True
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/organisations/org-123/users")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_list_users_organisation_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test listing users in non-existent organisation."""
        mock_database.get_organisation.return_value = None

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/organisations/nonexistent/users")

        assert response.status_code == 404

    def test_list_users_skips_missing_cognito_users(self, mock_database, mock_cognito, core_member_user):
        """Test that missing Cognito users are skipped when listing."""
        mock_database.get_organisation.return_value = {"organisation_id": "org-123", "name": "Test Org"}
        mock_database.get_organisation_members.return_value = [
            {"organisation_id": "org-123", "username": "missinguser", "role": "member"}
        ]
        mock_cognito.get_user.side_effect = UserNotFoundError("missinguser")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/organisations/org-123/users")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_get_user_success(self, mock_database, mock_cognito, core_member_user):
        """Test getting a user."""
        mock_cognito.get_user.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "groups": ["FRANK_OBSERVER"],
            "enabled": True
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/users/testuser")

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"

    def test_get_user_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test getting non-existent user."""
        mock_cognito.get_user.side_effect = UserNotFoundError("nonexistent")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/users/nonexistent")

        assert response.status_code == 404

    def test_update_user_success(self, mock_database, mock_cognito, core_member_user):
        """Test updating a user."""
        mock_cognito.update_user.return_value = {
            "username": "testuser",
            "email": "newemail@example.com",
            "groups": ["FRANK_OBSERVER"],
            "enabled": True
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.put(
            "/v1/users/testuser",
            json={"email": "newemail@example.com"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newemail@example.com"

    def test_update_user_with_groups(self, mock_database, mock_cognito, core_member_user):
        """Test updating user groups."""
        mock_cognito.update_user.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "groups": ["FRANK_ADMIN"],
            "enabled": True
        }
        mock_cognito.get_user_groups.return_value = ["FRANK_OBSERVER"]
        mock_cognito.get_user.return_value = {
            "username": "testuser",
            "email": "test@example.com",
            "groups": ["FRANK_ADMIN"],
            "enabled": True
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.put(
            "/v1/users/testuser",
            json={"groups": ["FRANK_ADMIN"]}
        )

        assert response.status_code == 200
        mock_cognito.remove_user_from_group.assert_called_once()
        mock_cognito.add_user_to_group.assert_called_once()

    def test_update_user_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test updating non-existent user."""
        mock_cognito.update_user.side_effect = UserNotFoundError("nonexistent")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.put(
            "/v1/users/nonexistent",
            json={"email": "new@example.com"}
        )

        assert response.status_code == 404

    def test_delete_user_success(self, mock_database, mock_cognito, core_member_user):
        """Test deleting a user."""
        mock_database.get_user_organisations.return_value = [
            {"organisation_id": "org-1"},
            {"organisation_id": "org-2"}
        ]
        mock_cognito.delete_user.return_value = True

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.delete("/v1/users/testuser")

        assert response.status_code == 204
        # Should remove from all organisations
        assert mock_database.remove_organisation_member.call_count == 2

    def test_delete_user_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test deleting non-existent user."""
        mock_database.get_user_organisations.return_value = []
        mock_cognito.delete_user.side_effect = UserNotFoundError("nonexistent")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.delete("/v1/users/nonexistent")

        assert response.status_code == 404


class TestAppCreation:
    """Tests for app factory function."""

    def test_create_app_with_defaults(self):
        """Test creating app with default parameters."""
        app = create_management_app()

        assert app.title == "FRANK Management API"
        assert app.state.database is None
        assert app.state.cognito_service is None

    def test_create_app_with_dependencies(self, mock_database, mock_cognito):
        """Test creating app with provided dependencies."""
        app = create_management_app(
            database=mock_database,
            cognito_service=mock_cognito
        )

        assert app.state.database is mock_database
        assert app.state.cognito_service is mock_cognito

    def test_cors_middleware_added(self, mock_database, mock_cognito):
        """Test that CORS middleware is configured."""
        app = create_management_app(database=mock_database, cognito_service=mock_cognito)

        middleware_names = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_names


class TestDatabaseNotConfigured:
    """Tests for database not configured scenarios."""

    def test_database_not_configured_returns_503(self, mock_cognito, core_member_user):
        """Test endpoints fail when database not configured."""
        from frank.auth.dependencies import get_current_user

        app = create_management_app(database=None, cognito_service=mock_cognito)
        app.dependency_overrides[get_current_user] = lambda: core_member_user

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/v1/organisations")
        assert response.status_code == 503
        assert "Database not configured" in response.json()["detail"]


class TestMFAEndpoints:
    """Tests for MFA endpoints."""

    def test_setup_mfa_success(self, mock_database, mock_cognito, core_member_user):
        """Test initiating MFA setup."""
        mock_cognito.setup_mfa.return_value = {
            "secret": "JBSWY3DPEHPK3PXP",
            "qr_code_uri": "otpauth://totp/FRANK:testuser?secret=JBSWY3DPEHPK3PXP&issuer=FRANK",
            "issuer": "FRANK"
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post("/v1/users/testuser/mfa/setup")

        assert response.status_code == 200
        data = response.json()
        assert data["secret"] == "JBSWY3DPEHPK3PXP"
        assert "qr_code_uri" in data
        assert data["issuer"] == "FRANK"

    def test_setup_mfa_user_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test MFA setup for non-existent user."""
        mock_cognito.setup_mfa.side_effect = UserNotFoundError("nonexistent")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post("/v1/users/nonexistent/mfa/setup")

        assert response.status_code == 404

    def test_setup_mfa_error(self, mock_database, mock_cognito, core_member_user):
        """Test MFA setup failure."""
        mock_cognito.setup_mfa.side_effect = MFASetupError("Failed to generate secret")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post("/v1/users/testuser/mfa/setup")

        assert response.status_code == 400
        assert "MFA setup failed" in response.json()["detail"]

    def test_verify_mfa_setup_success(self, mock_database, mock_cognito, core_member_user):
        """Test verifying MFA setup with valid code."""
        mock_cognito.verify_mfa_setup.return_value = True

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/users/testuser/mfa/verify",
            json={"totp_code": "123456"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "MFA enabled successfully"
        assert data["username"] == "testuser"

    def test_verify_mfa_user_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test MFA verification for non-existent user."""
        mock_cognito.verify_mfa_setup.side_effect = UserNotFoundError("nonexistent")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/users/nonexistent/mfa/verify",
            json={"totp_code": "123456"}
        )

        assert response.status_code == 404

    def test_verify_mfa_invalid_code(self, mock_database, mock_cognito, core_member_user):
        """Test MFA verification with invalid code."""
        mock_cognito.verify_mfa_setup.side_effect = MFAVerificationError("Invalid TOTP code")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/users/testuser/mfa/verify",
            json={"totp_code": "000000"}
        )

        assert response.status_code == 400
        assert "MFA verification failed" in response.json()["detail"]

    def test_verify_mfa_invalid_code_format(self, mock_database, mock_cognito, core_member_user):
        """Test MFA verification with non-numeric code."""
        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/users/testuser/mfa/verify",
            json={"totp_code": "abcdef"}
        )

        assert response.status_code == 422  # Validation error

    def test_disable_mfa_success(self, mock_database, mock_cognito, core_member_user):
        """Test disabling MFA."""
        mock_cognito.disable_mfa.return_value = True

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.delete("/v1/users/testuser/mfa")

        assert response.status_code == 204

    def test_disable_mfa_user_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test disabling MFA for non-existent user."""
        mock_cognito.disable_mfa.side_effect = UserNotFoundError("nonexistent")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.delete("/v1/users/nonexistent/mfa")

        assert response.status_code == 404

    def test_disable_mfa_service_error(self, mock_database, mock_cognito, core_member_user):
        """Test disabling MFA with service error."""
        mock_cognito.disable_mfa.side_effect = CognitoServiceError("Service error", status_code=500)

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.delete("/v1/users/testuser/mfa")

        assert response.status_code == 500

    def test_get_mfa_status_enabled(self, mock_database, mock_cognito, core_member_user):
        """Test getting MFA status when enabled."""
        mock_cognito.get_mfa_status.return_value = {
            "enabled": True,
            "mfa_type": "TOTP"
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/users/testuser/mfa/status")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["mfa_type"] == "TOTP"

    def test_get_mfa_status_disabled(self, mock_database, mock_cognito, core_member_user):
        """Test getting MFA status when disabled."""
        mock_cognito.get_mfa_status.return_value = {
            "enabled": False,
            "mfa_type": None
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/users/testuser/mfa/status")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["mfa_type"] is None

    def test_get_mfa_status_user_not_found(self, mock_database, mock_cognito, core_member_user):
        """Test getting MFA status for non-existent user."""
        mock_cognito.get_mfa_status.side_effect = UserNotFoundError("nonexistent")

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/users/nonexistent/mfa/status")

        assert response.status_code == 404

    def test_get_mfa_status_observer_access(self, mock_database, mock_cognito, observer_user):
        """Test that OBSERVER can view MFA status."""
        mock_cognito.get_mfa_status.return_value = {
            "enabled": False,
            "mfa_type": None
        }

        app = create_test_app(mock_database, mock_cognito, observer_user)
        client = TestClient(app)

        response = client.get("/v1/users/testuser/mfa/status")

        assert response.status_code == 200

    def test_setup_mfa_cognito_service_error(self, mock_database, mock_cognito, core_member_user):
        """Test MFA setup with generic Cognito service error."""
        mock_cognito.setup_mfa.side_effect = CognitoServiceError(
            "Service temporarily unavailable",
            status_code=503
        )

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post("/v1/users/testuser/mfa/setup")

        assert response.status_code == 503
        assert "Service temporarily unavailable" in response.json()["detail"]

    def test_verify_mfa_cognito_service_error(self, mock_database, mock_cognito, core_member_user):
        """Test MFA verification with generic Cognito service error."""
        from frank.management.models import MFAVerifyRequest

        mock_cognito.verify_mfa_setup.side_effect = CognitoServiceError(
            "Internal service error",
            status_code=500
        )

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post(
            "/v1/users/testuser/mfa/verify",
            json={"totp_code": "123456"}
        )

        assert response.status_code == 500
        assert "Internal service error" in response.json()["detail"]

    def test_get_mfa_status_cognito_service_error(self, mock_database, mock_cognito, core_member_user):
        """Test MFA status retrieval with generic Cognito service error."""
        mock_cognito.get_mfa_status.side_effect = CognitoServiceError(
            "Connection timeout",
            status_code=504
        )

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.get("/v1/users/testuser/mfa/status")

        assert response.status_code == 504
        assert "Connection timeout" in response.json()["detail"]


class TestAuthenticationEndpoints:
    """Tests for authentication endpoints (login, refresh, logout)."""

    def test_login_success(self, mock_database, mock_cognito):
        """Test successful login returns access and refresh tokens."""
        with patch("frank.management.api.generate_access_token") as mock_access, \
             patch("frank.management.api.generate_refresh_token") as mock_refresh, \
             patch("frank.management.api.decode_refresh_token") as mock_decode:

            mock_cognito.authenticate_user.return_value = True
            mock_cognito.get_user_groups.return_value = ["FRANK_OBSERVER"]
            mock_database.store_refresh_token.return_value = None

            mock_access.return_value = "mock_access_token"
            mock_refresh.return_value = "mock_refresh_token"
            mock_decode.return_value = {
                "jti": "token-id-123",
                "exp": 1738281600,  # 2026-01-31
                "username": "testuser"
            }

            app = create_management_app(database=mock_database, cognito_service=mock_cognito)
            client = TestClient(app)

            response = client.post(
                "/v1/auth/login",
                json={"username": "testuser", "password": "SecurePass123!"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == "mock_access_token"
            assert data["refresh_token"] == "mock_refresh_token"
            assert data["token_type"] == "Bearer"
            assert data["expires_in"] == 3600  # 1 hour in seconds
            mock_cognito.authenticate_user.assert_called_once_with("testuser", "SecurePass123!")
            mock_database.store_refresh_token.assert_called_once()

    def test_login_invalid_credentials(self, mock_database, mock_cognito):
        """Test login with invalid credentials returns 401."""
        mock_cognito.authenticate_user.side_effect = CognitoServiceError(
            "NotAuthorizedException: Incorrect username or password",
            status_code=401
        )

        app = create_management_app(database=mock_database, cognito_service=mock_cognito)
        client = TestClient(app)

        response = client.post(
            "/v1/auth/login",
            json={"username": "testuser", "password": "wrongpassword"}
        )

        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    def test_login_user_not_found(self, mock_database, mock_cognito):
        """Test login with non-existent user."""
        mock_cognito.authenticate_user.side_effect = UserNotFoundError("testuser")

        app = create_management_app(database=mock_database, cognito_service=mock_cognito)
        client = TestClient(app)

        response = client.post(
            "/v1/auth/login",
            json={"username": "nonexistent", "password": "anypassword"}
        )

        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    def test_refresh_token_success(self, mock_database, mock_cognito):
        """Test successful token refresh."""
        with patch("frank.management.api.decode_refresh_token") as mock_decode, \
             patch("frank.management.api.hash_token") as mock_hash, \
             patch("frank.management.api.generate_access_token") as mock_access, \
             patch("frank.management.api.get_cognito_service") as mock_get_cognito:

            refresh_token = "valid.refresh.token"
            username = "testuser"

            mock_decode.return_value = {
                "jti": "test-token-id",
                "username": username,
                "exp": 1738281600
            }
            mock_hash.return_value = "token_hash_123"
            mock_access.return_value = "new_access_token"
            mock_get_cognito.return_value = mock_cognito
            mock_cognito.get_user_groups.return_value = ["FRANK_OBSERVER"]

            # Mock database returning valid stored token
            mock_database.get_refresh_token.return_value = {
                "token_id": "test-token-id",
                "user_id": username,
                "token_hash": "token_hash_123",
                "expires_at": "2026-02-28T00:00:00Z"
            }

            app = create_management_app(database=mock_database, cognito_service=mock_cognito)
            client = TestClient(app)

            response = client.post(
                "/v1/auth/refresh",
                json={"refresh_token": refresh_token}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == "new_access_token"
            assert data["token_type"] == "Bearer"
            assert data["expires_in"] == 3600

    def test_refresh_token_invalid(self, mock_database, mock_cognito):
        """Test refresh with invalid token."""
        with patch("frank.management.api.decode_refresh_token") as mock_decode:
            mock_decode.return_value = None  # Invalid token returns None

            app = create_management_app(database=mock_database, cognito_service=mock_cognito)
            client = TestClient(app)

            response = client.post(
                "/v1/auth/refresh",
                json={"refresh_token": "invalid.token.here"}
            )

            assert response.status_code == 401
            assert "Invalid or expired refresh token" in response.json()["detail"]

    def test_refresh_token_revoked(self, mock_database, mock_cognito):
        """Test refresh with revoked token."""
        with patch("frank.management.api.decode_refresh_token") as mock_decode:
            mock_decode.return_value = {
                "jti": "revoked-token-id",
                "username": "testuser",
                "exp": 1738281600
            }

            # Token not found in database (revoked)
            mock_database.get_refresh_token.return_value = None

            app = create_management_app(database=mock_database, cognito_service=mock_cognito)
            client = TestClient(app)

            response = client.post(
                "/v1/auth/refresh",
                json={"refresh_token": "valid.but.revoked.token"}
            )

            assert response.status_code == 401
            assert "revoked or expired" in response.json()["detail"]

    def test_refresh_token_hash_mismatch(self, mock_database, mock_cognito):
        """Test refresh when stored hash doesn't match."""
        with patch("frank.management.api.decode_refresh_token") as mock_decode, \
             patch("frank.management.api.hash_token") as mock_hash:

            mock_decode.return_value = {
                "jti": "test-token-id",
                "username": "testuser",
                "exp": 1738281600
            }
            mock_hash.return_value = "actual_hash_value"

            # Mock database with mismatched hash
            mock_database.get_refresh_token.return_value = {
                "token_id": "test-token-id",
                "user_id": "testuser",
                "token_hash": "wrong-hash-value",
                "expires_at": "2026-02-28T00:00:00Z"
            }

            app = create_management_app(database=mock_database, cognito_service=mock_cognito)
            client = TestClient(app)

            response = client.post(
                "/v1/auth/refresh",
                json={"refresh_token": "valid.token.wrong.hash"}
            )

            assert response.status_code == 401
            assert "Invalid refresh token" in response.json()["detail"]

    def test_logout_success(self, mock_database, mock_cognito, core_member_user):
        """Test successful logout revokes tokens."""
        mock_database.revoke_all_user_refresh_tokens.return_value = 3  # 3 tokens revoked

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post("/v1/auth/logout")

        assert response.status_code == 204
        mock_database.revoke_all_user_refresh_tokens.assert_called_once_with(core_member_user.username)

    def test_logout_no_tokens(self, mock_database, mock_cognito, core_member_user):
        """Test logout when user has no refresh tokens."""
        mock_database.revoke_all_user_refresh_tokens.return_value = 0

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        response = client.post("/v1/auth/logout")

        assert response.status_code == 204


class TestServiceAccountCreation:
    """Tests for service account creation via user endpoints."""

    def test_create_service_account_auto_password(self, mock_database, mock_cognito, core_member_user):
        """Test creating service account with auto-generated password."""
        # Mock organisation exists
        mock_database.get_organisation.return_value = {"organisation_id": "identity--rabobank"}

        # Mock Cognito user creation
        mock_cognito.create_user.return_value = {
            "username": "service-rabobank-ingestion",
            "email": "service-rabobank@example.com",
            "enabled": True
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        # Create service account without password (should auto-generate)
        response = client.post(
            "/v1/organisations/identity--rabobank/users",
            json={
                "username": "service-rabobank-ingestion",
                "email": "service-rabobank@example.com",
                "groups": ["contributor"]
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "service-rabobank-ingestion"

        # Verify Cognito create_user was called with auto-generated password
        mock_cognito.create_user.assert_called_once()
        call_kwargs = mock_cognito.create_user.call_args[1]
        assert call_kwargs["username"] == "service-rabobank-ingestion"
        assert call_kwargs["password"] is not None  # Password was auto-generated
        assert len(call_kwargs["password"]) >= 32  # Strong password

    def test_create_service_account_explicit_password(self, mock_database, mock_cognito, core_member_user):
        """Test creating service account with explicit password."""
        mock_database.get_organisation.return_value = {"organisation_id": "identity--ing"}

        mock_cognito.create_user.return_value = {
            "username": "service-ing-scanner",
            "email": "service-ing@example.com",
            "enabled": True
        }

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        # Create service account with explicit password
        response = client.post(
            "/v1/organisations/identity--ing/users",
            json={
                "username": "service-ing-scanner",
                "email": "service-ing@example.com",
                "password": "ExplicitPassword123!",
                "groups": ["observer"]
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "service-ing-scanner"

        # Verify explicit password was used
        mock_cognito.create_user.assert_called_once()
        call_kwargs = mock_cognito.create_user.call_args[1]
        assert call_kwargs["password"] == "ExplicitPassword123!"

    def test_create_regular_user_requires_password(self, mock_database, mock_cognito, core_member_user):
        """Test creating regular user without password should fail at Cognito level."""
        mock_database.get_organisation.return_value = {"organisation_id": "identity--kpn"}

        # Cognito will reject user creation without password
        mock_cognito.create_user.side_effect = CognitoServiceError(
            "Password required for user creation",
            status_code=400
        )

        app = create_test_app(mock_database, mock_cognito, core_member_user)
        client = TestClient(app)

        # Try to create regular user without password
        response = client.post(
            "/v1/organisations/identity--kpn/users",
            json={
                "username": "regular_user",
                "email": "regular@example.com",
                "groups": ["observer"]
            }
        )

        # Should fail
        assert response.status_code == 400
