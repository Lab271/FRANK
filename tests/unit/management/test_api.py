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
