#!/usr/bin/env python3
"""
FRANK Platform - Management API Pydantic Models

Request and response models for organisation and user management.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from frank.core.enum import AccessTier

# ========== Organisation Models ==========

class OrganisationBase(BaseModel):
    """Base model for organisation data"""

    model_config = ConfigDict(
        extra="ignore",
        use_enum_values=True,
    )

    name: str = Field(..., min_length=1, max_length=255, description="Organisation name")
    organisation_type: str = Field(
        default="customer",
        description="Organisation type: 'cyber_partner' or 'customer'"
    )
    access_level: Optional[AccessTier] = Field(
        default=AccessTier.OBSERVER,
        description="Access tier level"
    )
    sector: Optional[str] = Field(None, max_length=100, description="Industry sector")
    region: Optional[str] = Field(None, max_length=100, description="Geographic region")
    client_count: Optional[int] = Field(default=0, ge=0, description="Number of protected clients")

    @field_validator("organisation_type")
    @classmethod
    def validate_org_type(cls, v: str) -> str:
        """Validate organisation type"""
        valid_types = ["cyber_partner", "customer"]
        if v not in valid_types:
            raise ValueError(f"organisation_type must be one of: {valid_types}")
        return v


class OrganisationCreate(OrganisationBase):
    """Model for creating a new organisation"""

    organisation_id: Optional[str] = Field(
        None,
        description="Optional custom organisation ID. Auto-generated if not provided."
    )


class OrganisationUpdate(BaseModel):
    """Model for updating an organisation"""

    model_config = ConfigDict(
        extra="ignore",
        use_enum_values=True,
    )

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Organisation name")
    organisation_type: Optional[str] = Field(None, description="Organisation type")
    access_level: Optional[AccessTier] = Field(None, description="Access tier level")
    sector: Optional[str] = Field(None, max_length=100, description="Industry sector")
    region: Optional[str] = Field(None, max_length=100, description="Geographic region")
    client_count: Optional[int] = Field(None, ge=0, description="Number of protected clients")

    @field_validator("organisation_type")
    @classmethod
    def validate_org_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate organisation type if provided"""
        if v is None:
            return None
        valid_types = ["cyber_partner", "customer"]
        if v not in valid_types:
            raise ValueError(f"organisation_type must be one of: {valid_types}")
        return v


class OrganisationResponse(BaseModel):
    """Response model for a single organisation"""

    model_config = ConfigDict(
        extra="ignore",
        use_enum_values=True,
    )

    organisation_id: str = Field(..., description="Unique organisation identifier")
    name: Optional[str] = Field(None, description="Organisation name")
    organisation_type: str = Field(..., description="Organisation type")
    access_level: Optional[str] = Field(None, description="Access tier level")
    sector: Optional[str] = Field(None, description="Industry sector")
    region: Optional[str] = Field(None, description="Geographic region")
    client_count: Optional[int] = Field(None, description="Number of protected clients")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_active: Optional[datetime] = Field(None, description="Last activity timestamp")
    contribution_score: Optional[int] = Field(None, description="Contribution score")

    @field_serializer("created_at", "last_active", when_used="always")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Serialize datetime as ISO string"""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return value.isoformat()


class OrganisationListResponse(BaseModel):
    """Response model for organisation list"""

    organisations: List[OrganisationResponse] = Field(
        default_factory=list,
        description="List of organisations"
    )
    total: int = Field(..., description="Total number of organisations")
    limit: int = Field(..., description="Maximum number of results returned")
    offset: int = Field(..., description="Number of results skipped")


# ========== User Models ==========

class UserBase(BaseModel):
    """Base model for user data (stored in Cognito)"""

    model_config = ConfigDict(
        extra="ignore",
    )

    email: str = Field(..., description="User email address")
    groups: List[str] = Field(
        default_factory=list,
        description="Cognito groups for access control"
    )


class UserCreate(UserBase):
    """Model for creating a new user in Cognito"""

    username: str = Field(
        ...,
        min_length=3,
        max_length=128,
        description="Unique username"
    )
    password: Optional[str] = Field(
        None,
        min_length=8,
        description="Initial password. If not provided, user must set on first login."
    )
    temporary_password: bool = Field(
        default=True,
        description="If True, user must change password on first login"
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format"""
        # Cognito username rules: alphanumeric, underscores, and hyphens
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation"""
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email format")
        return v.lower()


class UserUpdate(BaseModel):
    """Model for updating a user"""

    model_config = ConfigDict(
        extra="ignore",
    )

    email: Optional[str] = Field(None, description="User email address")
    groups: Optional[List[str]] = Field(None, description="Cognito groups")
    enabled: Optional[bool] = Field(None, description="Whether user account is enabled")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Basic email validation if provided"""
        if v is None:
            return None
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email format")
        return v.lower()


class UserResponse(BaseModel):
    """Response model for a single user"""

    model_config = ConfigDict(
        extra="ignore",
    )

    username: str = Field(..., description="Unique username")
    email: str = Field(..., description="User email address")
    groups: List[str] = Field(default_factory=list, description="Cognito groups")
    enabled: bool = Field(default=True, description="Whether user account is enabled")
    user_status: Optional[str] = Field(None, description="User status in Cognito")
    created_at: Optional[datetime] = Field(None, description="User creation timestamp")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")

    @field_serializer("created_at", "last_modified", when_used="always")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Serialize datetime as ISO string"""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return value.isoformat()


class UserListResponse(BaseModel):
    """Response model for user list"""

    users: List[UserResponse] = Field(default_factory=list, description="List of users")
    total: int = Field(..., description="Total number of users")


# ========== Organisation Member Models ==========

class OrganisationMemberCreate(BaseModel):
    """Model for adding a user to an organisation"""

    model_config = ConfigDict(
        extra="ignore",
    )

    username: str = Field(..., description="Cognito username to add")
    role: str = Field(
        default="member",
        description="Role in organisation: 'member', 'admin', or 'owner'"
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate member role"""
        valid_roles = ["member", "admin", "owner"]
        if v not in valid_roles:
            raise ValueError(f"role must be one of: {valid_roles}")
        return v


class OrganisationMemberResponse(BaseModel):
    """Response model for organisation membership"""

    model_config = ConfigDict(
        extra="ignore",
    )

    organisation_id: str = Field(..., description="Organisation identifier")
    username: str = Field(..., description="Cognito username")
    role: str = Field(..., description="Role in organisation")
    joined_at: Optional[datetime] = Field(None, description="When user joined the organisation")

    @field_serializer("joined_at", when_used="always")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Serialize datetime as ISO string"""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return value.isoformat()


class OrganisationMemberListResponse(BaseModel):
    """Response model for organisation members list"""

    members: List[OrganisationMemberResponse] = Field(
        default_factory=list,
        description="List of organisation members"
    )
    total: int = Field(..., description="Total number of members")


# ========== MFA Models ==========

class MFASetupResponse(BaseModel):
    """Response model for MFA setup initiation"""

    model_config = ConfigDict(
        extra="ignore",
    )

    secret: str = Field(..., description="TOTP secret key (base32 encoded)")
    qr_code_uri: str = Field(..., description="otpauth:// URI for QR code generation")
    issuer: str = Field(..., description="Issuer name for authenticator app")


class MFAVerifyRequest(BaseModel):
    """Request model for verifying MFA setup"""

    model_config = ConfigDict(
        extra="ignore",
    )

    totp_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit TOTP code from authenticator app"
    )

    @field_validator("totp_code")
    @classmethod
    def validate_totp_code(cls, v: str) -> str:
        """Validate TOTP code is numeric"""
        if not v.isdigit():
            raise ValueError("TOTP code must contain only digits")
        return v


class MFAStatusResponse(BaseModel):
    """Response model for MFA status"""

    model_config = ConfigDict(
        extra="ignore",
    )

    enabled: bool = Field(..., description="Whether MFA is enabled for the user")
    mfa_type: Optional[str] = Field(None, description="Type of MFA (e.g., 'TOTP') or None if disabled")


# ========== Authentication Models ==========

class LoginRequest(BaseModel):
    """Request model for user login"""

    model_config = ConfigDict(extra="ignore")

    username: str = Field(..., min_length=1, description="Username or email")
    password: str = Field(..., min_length=1, description="User password")


class LoginResponse(BaseModel):
    """Response model for successful login"""

    model_config = ConfigDict(extra="ignore")

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class RefreshTokenRequest(BaseModel):
    """Request model for token refresh"""

    model_config = ConfigDict(extra="ignore")

    refresh_token: str = Field(..., description="The refresh token to exchange")


class RefreshTokenResponse(BaseModel):
    """Response model for token refresh"""

    model_config = ConfigDict(extra="ignore")

    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Access token lifetime in seconds")


# ========== API Key Models ==========

class ApiKeyCreate(BaseModel):
    """Request model for creating an API key"""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable name for the API key"
    )
    expires_in_days: Optional[int] = Field(
        default=365,
        ge=1,
        le=730,
        description="Key lifetime in days (default: 365, max: 730)"
    )


class ApiKeyResponse(BaseModel):
    """Response model for an API key (returned at creation with full key)"""

    model_config = ConfigDict(extra="ignore")

    key_id: str = Field(..., description="Unique key identifier")
    key: Optional[str] = Field(None, description="The API key (only shown at creation)")
    key_prefix: str = Field(..., description="Key prefix for identification")
    name: str = Field(..., description="Human-readable key name")
    user_id: str = Field(..., description="Owner user ID")
    expires_at: Optional[str] = Field(None, description="Expiration datetime (ISO format)")
    created_at: str = Field(..., description="Creation datetime (ISO format)")
    last_used_at: Optional[str] = Field(None, description="Last usage datetime (ISO format)")


class ApiKeyListResponse(BaseModel):
    """Response model for listing API keys"""

    model_config = ConfigDict(extra="ignore")

    api_keys: List[ApiKeyResponse] = Field(
        default_factory=list,
        description="List of API keys"
    )
    total: int = Field(..., description="Total number of keys")


class ApiKeyUpdate(BaseModel):
    """Request model for updating an API key"""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="New name for the API key"
    )
    expires_at: Optional[str] = Field(
        None,
        description="New expiration datetime (ISO format)"
    )
