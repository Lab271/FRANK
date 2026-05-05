#!/usr/bin/env python3
"""
FRANK API Client for Demo

Handles communication with FRANK backend.
"""

import httpx
from typing import Optional
from dataclasses import dataclass


@dataclass
class FRANKConfig:
    """FRANK API configuration."""
    base_url: str = "http://localhost:8000"
    api_version: str = "v1"
    timeout: float = 10.0


class FRANKClient:
    """Client for FRANK API calls."""

    def __init__(self, config: Optional[FRANKConfig] = None):
        self.config = config or FRANKConfig()
        self._token: Optional[str] = None

    @property
    def api_url(self) -> str:
        return f"{self.config.base_url}/{self.config.api_version}"

    async def login(self, username: str, password: str) -> str:
        """Authenticate and get access token."""
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(
                f"{self.api_url}/auth/login",
                json={"username": username, "password": password}
            )
            response.raise_for_status()
            data = response.json()
            self._token = data["access_token"]
            return self._token

    def _headers(self) -> dict:
        """Get headers with auth token."""
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def query_ioc(self, ioc: str) -> dict:
        """
        Query FRANK for an IoC.

        Returns sighting count, sectors, and metadata.
        """
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(
                f"{self.api_url}/observables",
                params={"q": ioc},
                headers=self._headers()
            )
            response.raise_for_status()
            return response.json()

    async def submit_sighting(
        self,
        observables: list[dict],
        confidence: float = 0.8,
        description: str = ""
    ) -> dict:
        """
        Submit a sighting to FRANK.

        Args:
            observables: List of observable dicts with type and value
            confidence: Confidence score (0-1)
            description: Optional description

        Returns:
            Submission confirmation with ID
        """
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(
                f"{self.api_url}/submit",
                json={
                    "observables": observables,
                    "confidence_score": confidence,
                    "description": description
                },
                headers=self._headers()
            )
            response.raise_for_status()
            return response.json()

    async def get_statistics(self, days: int = 30) -> dict:
        """Get platform statistics."""
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(
                f"{self.api_url}/statistics",
                params={"days": days},
                headers=self._headers()
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> dict:
        """Check FRANK backend health."""
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(f"{self.config.base_url}/health")
            response.raise_for_status()
            return response.json()


# Convenience functions for sync usage in Marimo
def create_client(base_url: str = "http://localhost:8000") -> FRANKClient:
    """Create a configured FRANK client."""
    return FRANKClient(FRANKConfig(base_url=base_url))
