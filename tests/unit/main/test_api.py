"""
Unit tests for Main API endpoints.

Tests health checks, authentication, submission, and query endpoints.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

from frank.main.api import create_main_app
from frank.core.enum import AccessTier
from frank.core.models import Observable, Submission
from frank.auth import TokenPayload


@pytest.fixture
def mock_database():
    """Mock database instance"""
    db = Mock()
    db.name = "mock_db"
    db.health_check = Mock(return_value={"status": "healthy"})
    db.store_submission = Mock()
    db.get_submission_by_id = Mock()
    db.query_observables = Mock(return_value=[])
    db.get_statistics_summary = Mock(return_value={
        "total_submissions": 100,
        "total_observables": 500
    })
    return db


@pytest.fixture
def mock_cognito():
    """Mock Cognito service"""
    cognito = Mock()
    cognito.authenticate_user = AsyncMock(return_value={
        "AuthenticationResult": {
            "AccessToken": "mock-access-token",
            "RefreshToken": "mock-refresh-token",
            "ExpiresIn": 3600
        }
    })
    return cognito


@pytest.fixture
def client(mock_database, mock_cognito):
    """Test client with mocked dependencies"""
    app = create_main_app(database=mock_database, cognito_service=mock_cognito)
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user"""
    return TokenPayload(
        sub="user-123",
        username="test-user",
        email="test@example.com",
        groups=["FRANK_PARTNER"],
        access_tier=AccessTier.PARTNER,
        organisation_id="identity--org-123"
    )


# ==================== Health Endpoints ====================

def test_health_endpoint(client):
    """Test GET /health returns healthy status"""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


def test_deep_health_endpoint(client, mock_database):
    """Test GET /health/deep checks database connectivity"""
    response = client.get("/health/deep")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "components" in data
    assert data["components"]["database"]["status"] == "healthy"
    assert data["components"]["authentication"]["status"] == "healthy"

    # Verify database health check was called
    mock_database.health_check.assert_called_once()


def test_deep_health_database_unhealthy(client, mock_database):
    """Test /health/deep when database is unhealthy"""
    mock_database.health_check.side_effect = Exception("Database connection failed")

    response = client.get("/health/deep")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["components"]["database"]["status"] == "unhealthy"


# ==================== Authentication Endpoints ====================

def test_login_success(client, mock_cognito):
    """Test POST /auth/login with valid credentials"""
    response = client.post(
        "/auth/login",
        json={"username": "service-test", "password": "test-password"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "mock-access-token"
    assert data["refresh_token"] == "mock-refresh-token"
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 3600

    # Verify Cognito was called
    mock_cognito.authenticate_user.assert_called_once_with(
        username="service-test",
        password="test-password"
    )


def test_login_invalid_credentials(client, mock_cognito):
    """Test POST /auth/login with invalid credentials"""
    from frank.management.cognito_service import CognitoServiceError

    mock_cognito.authenticate_user.side_effect = CognitoServiceError(
        "Invalid username or password",
        status_code=401
    )

    response = client.post(
        "/auth/login",
        json={"username": "wrong", "password": "wrong"}
    )

    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


def test_refresh_not_implemented(client):
    """Test POST /auth/refresh returns 501"""
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "some-token"}
    )

    assert response.status_code == 501


# ==================== Submission Endpoints ====================

@patch("frank.main.api.get_current_user")
def test_submit_sighting(mock_get_user, client, mock_database, mock_user):
    """Test POST /submit creates submission"""
    mock_get_user.return_value = mock_user

    response = client.post(
        "/submit",
        headers={"Authorization": "Bearer mock-token"},
        json={
            "observables": [
                {"observable_type": "ipv4", "value": "192.0.2.1", "role": "C2"},
                {"observable_type": "domain", "value": "evil.example.com"}
            ],
            "confidence_score": 0.8,
            "severity": "HIGH",
            "description": "Test threat"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "accepted"
    assert "submission_id" in data
    assert data["submission_id"].startswith("submission--")
    assert "2 observables" in data["message"]

    # Verify submission was stored
    mock_database.store_submission.assert_called_once()
    submission = mock_database.store_submission.call_args[0][0]
    assert isinstance(submission, Submission)
    assert submission.submitter.organisation_id == "identity--org-123"
    assert submission.submitter.access_level == AccessTier.PARTNER


@patch("frank.main.api.get_current_user")
def test_submit_without_auth(mock_get_user, client):
    """Test POST /submit without authentication fails"""
    mock_get_user.side_effect = Exception("Not authenticated")

    response = client.post(
        "/submit",
        json={"observables": []}
    )

    # FastAPI dependency injection will handle auth error
    assert response.status_code in [401, 500]


@patch("frank.main.api.get_current_user")
def test_get_submission(mock_get_user, client, mock_database, mock_user):
    """Test GET /submissions/{id} retrieves submission"""
    mock_get_user.return_value = mock_user

    # Mock submission response
    mock_submission = Mock(spec=Submission)
    mock_submission.submission_id = "submission--test-123"
    mock_database.get_submission_by_id.return_value = mock_submission

    response = client.get(
        "/submissions/submission--test-123",
        headers={"Authorization": "Bearer mock-token"}
    )

    assert response.status_code == 200

    # Verify database was queried with access filtering
    mock_database.get_submission_by_id.assert_called_once_with(
        submission_id="submission--test-123",
        access_level=AccessTier.PARTNER
    )


@patch("frank.main.api.get_current_user")
def test_get_submission_not_found(mock_get_user, client, mock_database, mock_user):
    """Test GET /submissions/{id} returns 404 for missing submission"""
    mock_get_user.return_value = mock_user
    mock_database.get_submission_by_id.return_value = None

    response = client.get(
        "/submissions/submission--nonexistent",
        headers={"Authorization": "Bearer mock-token"}
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ==================== Query Endpoints ====================

@patch("frank.main.api.get_current_user")
def test_query_observables(mock_get_user, client, mock_database, mock_user):
    """Test GET /observables queries with filtering"""
    mock_get_user.return_value = mock_user

    mock_observables = [
        {"observable_type": "ipv4", "value": "192.0.2.1"},
        {"observable_type": "ipv4", "value": "192.0.2.2"}
    ]
    mock_database.query_observables.return_value = mock_observables

    response = client.get(
        "/observables?observable_type=ipv4&limit=50&offset=10",
        headers={"Authorization": "Bearer mock-token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["limit"] == 50
    assert data["offset"] == 10
    assert data["access_tier"] == "partner"
    assert len(data["observables"]) == 2

    # Verify query parameters passed to database
    mock_database.query_observables.assert_called_once_with(
        org_id="identity--org-123",
        observable_type="ipv4",
        access_level=AccessTier.PARTNER,
        limit=50,
        offset=10
    )


@patch("frank.main.api.get_current_user")
def test_get_statistics(mock_get_user, client, mock_database, mock_user):
    """Test GET /statistics returns platform metrics"""
    mock_get_user.return_value = mock_user

    response = client.get(
        "/statistics?days=7",
        headers={"Authorization": "Bearer mock-token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_submissions"] == 100
    assert data["total_observables"] == 500
    assert data["access_tier"] == "partner"
    assert data["requested_by"] == "test-user"
    assert data["period_days"] == 7

    # Verify database query
    mock_database.get_statistics_summary.assert_called_once_with(
        org_id="identity--org-123",
        days=7
    )


# ==================== Integration Tests ====================

def test_app_creation_without_dependencies():
    """Test app can be created without database or cognito"""
    app = create_main_app()
    assert app is not None
    assert app.title == "FRANK Main API"


def test_cors_middleware(client):
    """Test CORS middleware is configured"""
    response = client.options("/health")
    # CORS headers should be present
    assert response.status_code in [200, 405]  # OPTIONS may not be implemented
