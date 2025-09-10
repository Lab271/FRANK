#!/usr/bin/env python3
"""
FRANK Platform - Submission Generation and Parsing Library
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This modules provides an abstract base class defining the interface for
FRANK database operations, supporting both SQLite and DynamoDB implementations
with a consistent API.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from frank.core.models import Submission, Observable
from frank.core.enum import ObservableType, TierLevel
from frank.utils import NullLogger

class BaseFRANKDatabase(ABC):
    """
    Abstract base class defining the interface for FRANK database operations.
    Supports both SQLite and DynamoDB implementations with consistent API.
    """
    
    def __init__(self, connection_params: Dict[str, Any], logger: Optional[logging.Logger] = None):
        self.connection_params = connection_params
        self.logger = logger or NullLogger()
        self.initialize()
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize database connection and schema."""
        pass

    @abstractmethod
    def upsert_organization(self, org_data: Dict[str, Any]) -> bool:
        """Insert or update organization information."""
        pass
    
    @abstractmethod
    def store_submission(self, submission: Submission) -> bool:
        """Store a complete submission in the database."""
        pass
    
    @abstractmethod
    def get_submission_by_id(self, submission_id: str, org_id: str, access_level: TierLevel = TierLevel.CONTRIBUTOR) -> Optional[Submission]:
        """Retrieve a specific submission with access level filtering."""
        pass
    
    @abstractmethod
    def query_observables(self, org_id: str, observable_type: ObservableType = None, 
                         limit: int = 100, access_level: TierLevel = TierLevel.CONTRIBUTOR) -> List[Observable]:
        """Query observables with access level filtering."""
        pass
    
    @abstractmethod
    def get_statistics_summary(self, org_id: str, days: int = 30) -> Dict[str, Any]:
        """Get platform statistics summary."""
        pass

    @abstractmethod
    def log_access(self, org_id: str, action: str, 
                   resource_type: str = None, resource_id: str = None, 
                   details: Dict[str, Any] = None) -> bool:
        """Log an access event for auditing purposes."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the database."""
        pass
     
    def hash_observable(self, observable_type: str, observable_value: str) -> str:
        """Create a hash for observable deduplication and quick lookups."""
        combined = f"{observable_type}:{observable_value}".lower()
        return hashlib.sha256(combined.encode()).hexdigest()
    


