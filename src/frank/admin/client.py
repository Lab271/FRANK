#!/usr/bin/env python3
"""
FRANK Platform - Admin API Client

HTTP client for communicating with the Management API.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from frank.admin.auth import TokenManager
from frank.admin.config import AdminConfig

logger = logging.getLogger(__name__)


class AdminClientError(Exception):
    """Base exception for admin client errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(AdminClientError):
    """Authentication failed."""

    pass


class NotFoundError(AdminClientError):
    """Resource not found."""

    pass


class ConflictError(AdminClientError):
    """Resource conflict (e.g., already exists)."""

    pass


class AdminClient:
    """
    Async HTTP client for the FRANK Management API.

    Handles authentication, token refresh, and API calls.
    """

    def __init__(
        self,
        api_endpoint: Optional[str] = None,
        config: Optional[AdminConfig] = None,
    ):
        """
        Initialize the admin client.

        Args:
            api_endpoint: Override API endpoint (uses config if not provided)
            config: Admin configuration (uses singleton if not provided)
        """
        self.config = config or AdminConfig.get()
        self.api_endpoint = api_endpoint or self.config.api_endpoint
        self.token_manager = TokenManager(self.config)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "AdminClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.config.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}

        token = self.token_manager.get_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an authenticated API request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (e.g., /v1/organisations)
            json: Request body for POST/PUT
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            AuthenticationError: If authentication fails
            NotFoundError: If resource not found
            ConflictError: If resource conflict
            AdminClientError: For other errors
        """
        if not self._client:
            self._client = httpx.AsyncClient(timeout=self.config.timeout)

        url = f"{self.api_endpoint}{path}"
        headers = self._get_headers()

        try:
            response = await self._client.request(
                method=method,
                url=url,
                json=json,
                params=params,
                headers=headers,
            )

            if response.status_code == 401:
                raise AuthenticationError("Authentication required", 401)
            elif response.status_code == 403:
                raise AuthenticationError("Access denied", 403)
            elif response.status_code == 404:
                raise NotFoundError("Resource not found", 404)
            elif response.status_code == 409:
                error_detail = response.json().get("detail", "Resource conflict")
                raise ConflictError(error_detail, 409)
            elif response.status_code >= 400:
                error_detail = response.json().get("detail", "Request failed")
                raise AdminClientError(error_detail, response.status_code)

            # Return empty dict for 204 No Content
            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise AdminClientError(f"Connection error: {e}")

    # ========== Authentication ==========

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate with username and password.

        Args:
            username: User's username
            password: User's password

        Returns:
            Token response with access_token, expires_in, etc.

        Raises:
            AuthenticationError: If credentials are invalid
        """
        # Call Mock Cognito's token endpoint
        cognito_url = self.api_endpoint.replace(":8001", ":8100")

        try:
            response = await self._client.post(
                f"{cognito_url}/oauth2/token",
                data={
                    "grant_type": "password",
                    "username": username,
                    "password": password,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                raise AuthenticationError("Invalid credentials", response.status_code)

            data = response.json()

            # Store tokens
            self.token_manager.store_tokens(
                access_token=data["access_token"],
                username=username,
                expires_in=data.get("expires_in", 3600),
                refresh_token=data.get("refresh_token"),
            )

            return data

        except httpx.RequestError as e:
            raise AdminClientError(f"Connection error: {e}")

    async def logout(self) -> None:
        """Clear stored tokens and logout."""
        self.token_manager.clear_tokens()

    # ========== Health Check ==========

    async def health_check(self) -> Dict[str, Any]:
        """Get API health status."""
        return await self._request("GET", "/health")

    # ========== Organisations ==========

    async def list_organisations(
        self,
        organisation_type: Optional[str] = None,
        sector: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List organisations with optional filtering.

        Args:
            organisation_type: Filter by type (cyber_partner, customer)
            sector: Filter by sector
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Dict with organisations list and total count
        """
        params = {"limit": limit, "offset": offset}
        if organisation_type:
            params["organisation_type"] = organisation_type
        if sector:
            params["sector"] = sector

        return await self._request("GET", "/v1/organisations", params=params)

    async def get_organisation(self, organisation_id: str) -> Dict[str, Any]:
        """Get a specific organisation."""
        return await self._request("GET", f"/v1/organisations/{organisation_id}")

    async def create_organisation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new organisation.

        Args:
            data: Organisation data (name, organisation_type, sector, etc.)

        Returns:
            Created organisation data
        """
        return await self._request("POST", "/v1/organisations", json=data)

    async def update_organisation(self, organisation_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an organisation."""
        return await self._request("PUT", f"/v1/organisations/{organisation_id}", json=data)

    async def delete_organisation(self, organisation_id: str) -> None:
        """Delete an organisation."""
        await self._request("DELETE", f"/v1/organisations/{organisation_id}")

    # ========== Organisation Members ==========

    async def list_members(self, organisation_id: str, role: Optional[str] = None) -> Dict[str, Any]:
        """List members of an organisation."""
        params = {}
        if role:
            params["role"] = role
        return await self._request("GET", f"/v1/organisations/{organisation_id}/members", params=params)

    async def add_member(self, organisation_id: str, username: str, role: str = "member") -> Dict[str, Any]:
        """Add a member to an organisation."""
        return await self._request(
            "POST",
            f"/v1/organisations/{organisation_id}/members",
            json={"username": username, "role": role},
        )

    async def remove_member(self, organisation_id: str, username: str) -> None:
        """Remove a member from an organisation."""
        await self._request("DELETE", f"/v1/organisations/{organisation_id}/members/{username}")

    # ========== Users ==========

    async def list_users(self, organisation_id: str) -> Dict[str, Any]:
        """List users in an organisation."""
        return await self._request("GET", f"/v1/organisations/{organisation_id}/users")

    async def get_user(self, username: str) -> Dict[str, Any]:
        """Get a specific user."""
        return await self._request("GET", f"/v1/users/{username}")

    async def create_user(
        self,
        organisation_id: str,
        username: str,
        email: str,
        password: Optional[str] = None,
        groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new user and add to organisation.

        Args:
            organisation_id: Organisation to add user to
            username: New username
            email: User's email
            password: Initial password (optional)
            groups: Groups to add user to

        Returns:
            Created user data
        """
        data = {"username": username, "email": email}
        if password:
            data["password"] = password
        if groups:
            data["groups"] = groups

        return await self._request("POST", f"/v1/organisations/{organisation_id}/users", json=data)

    async def update_user(
        self,
        username: str,
        email: Optional[str] = None,
        enabled: Optional[bool] = None,
        groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Update a user."""
        data = {}
        if email is not None:
            data["email"] = email
        if enabled is not None:
            data["enabled"] = enabled
        if groups is not None:
            data["groups"] = groups

        return await self._request("PUT", f"/v1/users/{username}", json=data)

    async def delete_user(self, username: str) -> None:
        """Delete a user."""
        await self._request("DELETE", f"/v1/users/{username}")
