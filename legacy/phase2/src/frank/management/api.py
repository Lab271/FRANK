#!/usr/bin/env python3
"""
FRANK Platform - Management API

FastAPI application for organisation and user management.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import logging
import secrets
import string
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

import frank
from frank.auth import TokenPayload, get_current_user, require_access_tier
from frank.auth.config import AuthConfig
from frank.auth.tokens import (
    ACCESS_TOKEN_LIFETIME_HOURS,
    decode_refresh_token,
    generate_access_token,
    generate_refresh_token,
    hash_token,
)
from frank.core.enum import AccessTier
from frank.management.cognito_service import (
    BaseCognitoService,
    CognitoServiceError,
    MFASetupError,
    MFAVerificationError,
    UserAlreadyExistsError,
    UserNotFoundError,
    get_cognito_service,
)
from frank.management.models import (
    LoginRequest,
    LoginResponse,
    MFASetupResponse,
    MFAStatusResponse,
    MFAVerifyRequest,
    OrganisationCreate,
    OrganisationListResponse,
    OrganisationMemberCreate,
    OrganisationMemberListResponse,
    OrganisationMemberResponse,
    OrganisationResponse,
    OrganisationUpdate,
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from frank.management.seed import check_seed_status, seed_database
from frank.storage.base import BaseFRANKDatabase
from frank.storage.exceptions import FRANKStorageError

logger = logging.getLogger(__name__)


def create_management_app(
    database: BaseFRANKDatabase = None,
    cognito_service: BaseCognitoService = None
) -> FastAPI:
    """
    Create and configure the Management API FastAPI application.

    Args:
        database: Database instance for organisation storage
        cognito_service: Cognito service for user management

    Returns:
        Configured FastAPI application
    """

    app = FastAPI(
        title="FRANK Management API",
        description="Organisation and user management API for the FRANK platform",
        version=frank.__version__,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store services in app state
    app.state.database = database
    app.state.cognito_service = cognito_service

    def get_database() -> BaseFRANKDatabase:
        """Dependency to get database instance"""
        if app.state.database is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured"
            )
        return app.state.database

    def get_cognito() -> BaseCognitoService:
        """Dependency to get Cognito service instance"""
        if app.state.cognito_service is None:
            # Lazy initialization
            app.state.cognito_service = get_cognito_service()
        return app.state.cognito_service

    # ========== Health Check ==========

    @app.get("/health", tags=["Health"])
    async def health_check() -> Dict[str, Any]:
        """Health check endpoint"""
        result = {
            "status": "healthy",
            "service": "frank-management-api",
            "version": frank.__version__,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Check database health if available
        if app.state.database:
            try:
                db_health = app.state.database.health_check()
                result["database"] = db_health.get("status", "unknown")
            except Exception as e:
                result["database"] = "unhealthy"
                result["database_error"] = str(e)

        return result

    # ========== Admin Endpoints ==========

    @app.get("/admin/seed/status", tags=["Admin"])
    async def get_seed_status(
        db: BaseFRANKDatabase = Depends(get_database)
    ) -> Dict[str, Any]:
        """
        Check database seed status.

        Returns information about whether the database has been seeded with initial data.
        """
        return check_seed_status(db)

    @app.post("/admin/seed", tags=["Admin"])
    async def seed_db(
        force: bool = False,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        db: BaseFRANKDatabase = Depends(get_database)
    ) -> Dict[str, Any]:
        """
        Seed the database with initial organisations and members.

        Requires CORE_MEMBER access level.

        Args:
            force: If true, reseed even if data exists (recreates all data)
        """
        result = seed_database(db, force=force)
        return result

    # ========== Organisation Endpoints ==========

    @app.post(
        "/v1/organisations",
        response_model=OrganisationResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Organisations"]
    )
    async def create_organisation(
        org_data: OrganisationCreate,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        db: BaseFRANKDatabase = Depends(get_database)
    ) -> OrganisationResponse:
        """
        Create a new organisation.

        Requires CORE_MEMBER access level.
        """
        try:
            result = db.create_organisation(org_data.model_dump(exclude_none=True))
            logger.info(f"Organisation created: {result.get('organisation_id')} by {current_user.username}")
            return OrganisationResponse(**result)
        except FRANKStorageError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )

    @app.get(
        "/v1/organisations",
        response_model=OrganisationListResponse,
        tags=["Organisations"]
    )
    async def list_organisations(
        organisation_type: str = None,
        access_level: str = None,
        sector: str = None,
        limit: int = 100,
        offset: int = 0,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.OBSERVER)),
        db: BaseFRANKDatabase = Depends(get_database)
    ) -> OrganisationListResponse:
        """
        List organisations with optional filtering.

        Requires OBSERVER access level.
        """
        organisations = db.list_organisations(
            organisation_type=organisation_type,
            access_level=access_level,
            sector=sector,
            limit=limit,
            offset=offset
        )
        return OrganisationListResponse(
            organisations=[OrganisationResponse(**org) for org in organisations],
            total=len(organisations),
            limit=limit,
            offset=offset
        )

    @app.get(
        "/v1/organisations/{organisation_id}",
        response_model=OrganisationResponse,
        tags=["Organisations"]
    )
    async def get_organisation(
        organisation_id: str,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.OBSERVER)),
        db: BaseFRANKDatabase = Depends(get_database)
    ) -> OrganisationResponse:
        """
        Get a specific organisation by ID.

        Requires OBSERVER access level.
        """
        result = db.get_organisation(organisation_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organisation not found: {organisation_id}"
            )
        return OrganisationResponse(**result)

    @app.put(
        "/v1/organisations/{organisation_id}",
        response_model=OrganisationResponse,
        tags=["Organisations"]
    )
    async def update_organisation(
        organisation_id: str,
        updates: OrganisationUpdate,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        db: BaseFRANKDatabase = Depends(get_database)
    ) -> OrganisationResponse:
        """
        Update an organisation.

        Requires CORE_MEMBER access level.
        """
        result = db.update_organisation(
            organisation_id,
            updates.model_dump(exclude_none=True)
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organisation not found: {organisation_id}"
            )
        logger.info(f"Organisation updated: {organisation_id} by {current_user.username}")
        return OrganisationResponse(**result)

    @app.delete(
        "/v1/organisations/{organisation_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["Organisations"]
    )
    async def delete_organisation(
        organisation_id: str,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        db: BaseFRANKDatabase = Depends(get_database)
    ):
        """
        Delete an organisation.

        Requires CORE_MEMBER access level.
        """
        if not db.delete_organisation(organisation_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organisation not found: {organisation_id}"
            )
        logger.info(f"Organisation deleted: {organisation_id} by {current_user.username}")

    # ========== Organisation Member Endpoints ==========

    @app.post(
        "/v1/organisations/{organisation_id}/members",
        response_model=OrganisationMemberResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Organisation Members"]
    )
    async def add_organisation_member(
        organisation_id: str,
        member_data: OrganisationMemberCreate,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        db: BaseFRANKDatabase = Depends(get_database)
    ) -> OrganisationMemberResponse:
        """
        Add a user to an organisation.

        Requires CORE_MEMBER access level or admin role in the organisation.
        """
        # Verify organisation exists
        if not db.get_organisation(organisation_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organisation not found: {organisation_id}"
            )

        try:
            result = db.add_organisation_member(
                organisation_id,
                member_data.username,
                member_data.role
            )
            logger.info(
                f"Member {member_data.username} added to {organisation_id} "
                f"by {current_user.username}"
            )
            return OrganisationMemberResponse(**result)
        except FRANKStorageError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )

    @app.get(
        "/v1/organisations/{organisation_id}/members",
        response_model=OrganisationMemberListResponse,
        tags=["Organisation Members"]
    )
    async def list_organisation_members(
        organisation_id: str,
        role: str = None,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.OBSERVER)),
        db: BaseFRANKDatabase = Depends(get_database)
    ) -> OrganisationMemberListResponse:
        """
        List members of an organisation.

        Requires OBSERVER access level.
        """
        # Verify organisation exists
        if not db.get_organisation(organisation_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organisation not found: {organisation_id}"
            )

        members = db.get_organisation_members(organisation_id, role=role)
        return OrganisationMemberListResponse(
            members=[OrganisationMemberResponse(**m) for m in members],
            total=len(members)
        )

    @app.delete(
        "/v1/organisations/{organisation_id}/members/{username}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["Organisation Members"]
    )
    async def remove_organisation_member(
        organisation_id: str,
        username: str,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        db: BaseFRANKDatabase = Depends(get_database)
    ):
        """
        Remove a user from an organisation.

        Requires CORE_MEMBER access level or admin role in the organisation.
        """
        if not db.remove_organisation_member(organisation_id, username):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Member {username} not found in organisation {organisation_id}"
            )
        logger.info(
            f"Member {username} removed from {organisation_id} "
            f"by {current_user.username}"
        )

    # ========== User Endpoints (Cognito) ==========

    @app.post(
        "/v1/organisations/{organisation_id}/users",
        response_model=UserResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Users"]
    )
    async def create_user(
        organisation_id: str,
        user_data: UserCreate,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        db: BaseFRANKDatabase = Depends(get_database),
        cognito: BaseCognitoService = Depends(get_cognito)
    ) -> UserResponse:
        """
        Create a new user and add them to the organisation.

        Service accounts: Use naming convention 'service-{org}-{purpose}' for service accounts.
        Service accounts are Cognito users that authenticate with JWT tokens for automated access.

        Requires CORE_MEMBER access level or admin role in the organisation.
        """
        # Verify organisation exists
        if not db.get_organisation(organisation_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organisation not found: {organisation_id}"
            )

        # Detect service account by naming convention
        is_service_account = user_data.username.startswith("service-")

        # Auto-generate secure password for service accounts if not provided
        password = user_data.password
        generated_password = None
        if is_service_account and not password:
            # Generate cryptographically secure random password (32 chars)
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            password = ''.join(secrets.choice(alphabet) for _ in range(32))
            generated_password = password  # Store for response
            logger.info(f"Auto-generated secure password for service account: {user_data.username}")

        try:
            # Create user in Cognito
            result = await cognito.create_user(
                username=user_data.username,
                email=user_data.email,
                password=password,
                groups=user_data.groups,
                temporary_password=user_data.temporary_password
            )

            # Add user to organisation as member
            try:
                db.add_organisation_member(organisation_id, user_data.username, "member")
            except FRANKStorageError:
                # User already a member, that's OK
                pass

            account_type = "service account" if is_service_account else "user"
            logger.info(
                f"{account_type.capitalize()} {user_data.username} created in org {organisation_id} "
                f"by {current_user.username}"
            )

            # Include generated password in response for service accounts
            response_data = {**result}
            if generated_password:
                response_data["generated_password"] = generated_password

            return UserResponse(**response_data)

        except UserAlreadyExistsError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e.message)
            )
        except CognitoServiceError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message
            )

    @app.get(
        "/v1/organisations/{organisation_id}/users",
        response_model=UserListResponse,
        tags=["Users"]
    )
    async def list_organisation_users(
        organisation_id: str,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.OBSERVER)),
        db: BaseFRANKDatabase = Depends(get_database),
        cognito: BaseCognitoService = Depends(get_cognito)
    ) -> UserListResponse:
        """
        List users in an organisation.

        Requires OBSERVER access level.
        """
        # Verify organisation exists
        if not db.get_organisation(organisation_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organisation not found: {organisation_id}"
            )

        # Get members from database
        members = db.get_organisation_members(organisation_id)

        # Fetch user details from Cognito for each member
        users = []
        for member in members:
            try:
                user = await cognito.get_user(member["username"])
                users.append(UserResponse(**user))
            except UserNotFoundError:
                # User exists in org but not in Cognito - skip
                logger.warning(f"User {member['username']} not found in Cognito")
                continue
            except CognitoServiceError as e:
                logger.warning(f"Error fetching user {member['username']}: {e}")
                continue

        return UserListResponse(users=users, total=len(users))

    @app.get(
        "/v1/users/{username}",
        response_model=UserResponse,
        tags=["Users"]
    )
    async def get_user(
        username: str,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.OBSERVER)),
        cognito: BaseCognitoService = Depends(get_cognito)
    ) -> UserResponse:
        """
        Get a user by username.

        Requires OBSERVER access level.
        """
        try:
            result = await cognito.get_user(username)
            return UserResponse(**result)
        except UserNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e.message)
            )
        except CognitoServiceError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message
            )

    @app.put(
        "/v1/users/{username}",
        response_model=UserResponse,
        tags=["Users"]
    )
    async def update_user(
        username: str,
        updates: UserUpdate,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        cognito: BaseCognitoService = Depends(get_cognito)
    ) -> UserResponse:
        """
        Update a user.

        Requires CORE_MEMBER access level.
        """
        try:
            result = await cognito.update_user(
                username=username,
                email=updates.email,
                enabled=updates.enabled
            )

            # Handle group updates if provided
            if updates.groups is not None:
                current_groups = await cognito.get_user_groups(username)

                # Remove from groups no longer in the list
                for group in current_groups:
                    if group not in updates.groups:
                        await cognito.remove_user_from_group(username, group)

                # Add to new groups
                for group in updates.groups:
                    if group not in current_groups:
                        await cognito.add_user_to_group(username, group)

                # Refresh user data
                result = await cognito.get_user(username)

            logger.info(f"User {username} updated by {current_user.username}")
            return UserResponse(**result)

        except UserNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e.message)
            )
        except CognitoServiceError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message
            )

    @app.delete(
        "/v1/users/{username}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["Users"]
    )
    async def delete_user(
        username: str,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        db: BaseFRANKDatabase = Depends(get_database),
        cognito: BaseCognitoService = Depends(get_cognito)
    ):
        """
        Delete a user.

        Removes from Cognito and all organisation memberships.
        Requires CORE_MEMBER access level.
        """
        try:
            # Remove from all organisations first
            user_orgs = db.get_user_organisations(username)
            for org in user_orgs:
                db.remove_organisation_member(org["organisation_id"], username)

            # Delete from Cognito
            await cognito.delete_user(username)
            logger.info(f"User {username} deleted by {current_user.username}")

        except UserNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e.message)
            )
        except CognitoServiceError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message
            )

    # ========== MFA Endpoints ==========

    @app.post(
        "/v1/users/{username}/mfa/setup",
        response_model=MFASetupResponse,
        tags=["MFA"]
    )
    async def setup_mfa(
        username: str,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        cognito: BaseCognitoService = Depends(get_cognito)
    ) -> MFASetupResponse:
        """
        Start MFA enrollment for a user.

        Generates a TOTP secret and returns data needed for QR code generation.
        Requires CORE_MEMBER access level or the user themselves.
        """
        try:
            result = await cognito.setup_mfa(username)
            logger.info(f"MFA setup initiated for user {username} by {current_user.username}")
            return MFASetupResponse(**result)
        except UserNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e.message)
            )
        except MFASetupError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e.message)
            )
        except CognitoServiceError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message
            )

    @app.post(
        "/v1/users/{username}/mfa/verify",
        status_code=status.HTTP_200_OK,
        tags=["MFA"]
    )
    async def verify_mfa_setup(
        username: str,
        verify_request: MFAVerifyRequest,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        cognito: BaseCognitoService = Depends(get_cognito)
    ) -> Dict[str, Any]:
        """
        Verify MFA setup with a TOTP code.

        Called after user scans QR code and enters verification code from authenticator app.
        Requires CORE_MEMBER access level or the user themselves.
        """
        try:
            await cognito.verify_mfa_setup(username, verify_request.totp_code)
            logger.info(f"MFA verified and enabled for user {username} by {current_user.username}")
            return {"message": "MFA enabled successfully", "username": username}
        except UserNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e.message)
            )
        except MFAVerificationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e.message)
            )
        except CognitoServiceError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message
            )

    @app.delete(
        "/v1/users/{username}/mfa",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["MFA"]
    )
    async def disable_mfa(
        username: str,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.CORE_MEMBER)),
        cognito: BaseCognitoService = Depends(get_cognito)
    ):
        """
        Disable MFA for a user.

        Requires CORE_MEMBER access level.
        """
        try:
            await cognito.disable_mfa(username)
            logger.info(f"MFA disabled for user {username} by {current_user.username}")
        except UserNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e.message)
            )
        except CognitoServiceError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message
            )

    @app.get(
        "/v1/users/{username}/mfa/status",
        response_model=MFAStatusResponse,
        tags=["MFA"]
    )
    async def get_mfa_status(
        username: str,
        current_user: TokenPayload = Depends(require_access_tier(AccessTier.OBSERVER)),
        cognito: BaseCognitoService = Depends(get_cognito)
    ) -> MFAStatusResponse:
        """
        Get MFA status for a user.

        Requires OBSERVER access level.
        """
        try:
            result = await cognito.get_mfa_status(username)
            return MFAStatusResponse(**result)
        except UserNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e.message)
            )
        except CognitoServiceError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message
            )

    # ========== Authentication Endpoints ==========

    @app.post(
        "/v1/auth/login",
        response_model=LoginResponse,
        tags=["Authentication"]
    )
    async def login(
        login_data: LoginRequest,
        cognito: BaseCognitoService = Depends(get_cognito),
        db: BaseFRANKDatabase = Depends(get_database)
    ) -> LoginResponse:
        """
        Authenticate user and return access + refresh tokens.

        Uses Cognito for authentication.
        """
        try:
            # Authenticate via Cognito (validates credentials)
            await cognito.authenticate_user(
                login_data.username,
                login_data.password
            )

            # Get user groups for access token
            groups = await cognito.get_user_groups(login_data.username)

            # Generate tokens
            config = AuthConfig.get()
            access_token = generate_access_token(
                username=login_data.username,
                groups=groups,
                secret=config.jwt_secret,
                algorithm=config.jwt_algorithm,
            )

            refresh_token = generate_refresh_token(
                username=login_data.username,
                secret=config.jwt_secret,
                algorithm=config.jwt_algorithm,
            )

            # Decode refresh token to get jti for storage
            refresh_payload = decode_refresh_token(
                refresh_token, config.jwt_secret, config.jwt_algorithm
            )
            if refresh_payload:
                token_id = refresh_payload.get("jti")
                expires_at = datetime.fromtimestamp(
                    refresh_payload["exp"], tz=timezone.utc
                ).isoformat()

                # Store refresh token hash
                db.store_refresh_token(
                    user_id=login_data.username,
                    token_id=token_id,
                    token_hash=hash_token(refresh_token),
                    expires_at=expires_at
                )

            logger.info(f"User {login_data.username} logged in successfully")
            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="Bearer",
                expires_in=ACCESS_TOKEN_LIFETIME_HOURS * 3600
            )

        except UserNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        except CognitoServiceError as e:
            if "NotAuthorizedException" in str(e) or "UserNotFoundException" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid username or password"
                )
            logger.error(f"Cognito service error during login for {login_data.username}: {e}")
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message
            )
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"Unexpected error during login for {login_data.username}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during authentication"
            )

    @app.post(
        "/v1/auth/refresh",
        response_model=RefreshTokenResponse,
        tags=["Authentication"]
    )
    async def refresh_token(
        refresh_data: RefreshTokenRequest,
        db: BaseFRANKDatabase = Depends(get_database)
    ) -> RefreshTokenResponse:
        """
        Exchange refresh token for new access token.

        The refresh token is validated and a new access token is issued.
        """
        config = AuthConfig.get()

        # Decode and validate refresh token
        payload = decode_refresh_token(
            refresh_data.refresh_token,
            config.jwt_secret,
            config.jwt_algorithm
        )

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        token_id = payload.get("jti")
        username = payload.get("username")

        # Verify token exists in database and not revoked
        stored_token = db.get_refresh_token(token_id)
        if not stored_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked or expired"
            )

        # Verify hash matches
        if stored_token.get("token_hash") != hash_token(refresh_data.refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        # Get user groups for new access token
        try:
            cognito = get_cognito_service()
            groups = await cognito.get_user_groups(username)
        except Exception:
            groups = []  # Fallback to empty groups

        # Generate new access token
        access_token = generate_access_token(
            username=username,
            groups=groups,
            secret=config.jwt_secret,
            algorithm=config.jwt_algorithm,
        )

        logger.info(f"Access token refreshed for user {username}")
        return RefreshTokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_LIFETIME_HOURS * 3600
        )

    @app.post(
        "/v1/auth/logout",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["Authentication"]
    )
    async def logout(
        current_user: TokenPayload = Depends(get_current_user),
        db: BaseFRANKDatabase = Depends(get_database)
    ):
        """
        Logout user by revoking all their refresh tokens.

        Requires authentication.
        """
        count = db.revoke_all_user_refresh_tokens(current_user.username)
        logger.info(f"User {current_user.username} logged out, {count} refresh tokens revoked")

    # ========== Root Endpoint ==========

    @app.get("/", tags=["Root"])
    async def root() -> Dict[str, Any]:
        """Root endpoint with API information"""
        return {
            "service": "FRANK Management API",
            "version": frank.__version__,
            "endpoints": {
                "health": "/health",
                "organisations": "/v1/organisations",
                "users": "/v1/users/{username}",
                "docs": "/docs"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    logger.info("Management API application created successfully")
    return app
