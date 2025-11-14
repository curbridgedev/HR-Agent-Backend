"""
FastAPI dependencies for authentication and authorization.
"""

from typing import Literal, Optional
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, Request

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Type alias for user roles
UserRole = Literal["super_admin", "admin", "viewer"]


async def get_current_user_id(
    request: Request,
    authorization: Optional[str] = Header(None),
    sb_access_token: Optional[str] = Cookie(None),
) -> str:
    """
    Extract authenticated user ID from Supabase Auth session.

    Checks for auth token in:
    1. Authorization header (Bearer token)
    2. Cookie (sb-access-token from Supabase Auth)

    Args:
        request: FastAPI request object
        authorization: Optional Authorization header
        sb_access_token: Optional Supabase access token from cookie

    Returns:
        User ID string

    Raises:
        HTTPException: 401 if not authenticated or token invalid
    """
    # Extract token from Authorization header or cookie
    auth_token = None

    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.replace("Bearer ", "")
    elif sb_access_token:
        auth_token = sb_access_token

    if not auth_token:
        logger.warning("No authentication token provided")
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please provide authentication token.",
        )

    # Verify token with Supabase Auth
    try:
        from app.db.supabase import get_supabase_client

        supabase = get_supabase_client()

        # Get user from token
        user_response = supabase.auth.get_user(auth_token)

        if not user_response or not user_response.user:
            logger.warning("Invalid or expired authentication token")
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired authentication token",
            )

        user = user_response.user
        user_id = user.id

        # Check if user is active (security: deactivated users cannot access system)
        user_metadata = user.user_metadata or {}
        is_active = user_metadata.get("is_active", True)
        if not is_active:
            logger.warning(f"Inactive user attempted access: {user_id}")
            raise HTTPException(
                status_code=403,
                detail="Your account has been deactivated. Please contact an administrator.",
            )

        logger.debug(f"Authenticated user: {user_id}")

        return user_id

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail="Authentication failed. Please log in again.",
        )


async def get_optional_user_id(
    request: Request,
    authorization: Optional[str] = Header(None),
    sb_access_token: Optional[str] = Cookie(None),
) -> Optional[str]:
    """
    Extract authenticated user ID if available, but don't require it.

    Useful for endpoints that work with or without authentication.

    Args:
        request: FastAPI request object
        authorization: Optional Authorization header
        sb_access_token: Optional Supabase access token from cookie

    Returns:
        User ID string if authenticated, None otherwise
    """
    try:
        return await get_current_user_id(request, authorization, sb_access_token)
    except HTTPException:
        return None


# ============================================================================
# Role-Based Authorization
# ============================================================================


async def get_current_user_with_role(
    request: Request,
    authorization: Optional[str] = Header(None),
    sb_access_token: Optional[str] = Cookie(None),
) -> tuple[UUID, UserRole]:
    """
    Get authenticated user ID and role from Supabase Auth.

    Args:
        request: FastAPI request object
        authorization: Optional Authorization header
        sb_access_token: Optional Supabase access token from cookie

    Returns:
        Tuple of (user_id, user_role)

    Raises:
        HTTPException: 401 if not authenticated or token invalid
    """
    # Extract token from Authorization header or cookie
    auth_token = None

    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.replace("Bearer ", "")
    elif sb_access_token:
        auth_token = sb_access_token

    if not auth_token:
        logger.warning("No authentication token provided")
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please provide authentication token.",
        )

    # Verify token with Supabase Auth
    try:
        from app.db.supabase import get_supabase_client

        supabase = get_supabase_client()

        # Get user from token
        user_response = supabase.auth.get_user(auth_token)

        if not user_response or not user_response.user:
            logger.warning("Invalid or expired authentication token")
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired authentication token",
            )

        user = user_response.user
        user_id = UUID(user.id)

        # Extract role from user metadata
        user_metadata = user.user_metadata or {}
        role = user_metadata.get("role", "viewer")

        # Validate role
        if role not in ["super_admin", "admin", "viewer"]:
            logger.warning(
                f"Invalid role '{role}' for user {user_id}, defaulting to viewer"
            )
            role = "viewer"

        # Check if user is active
        is_active = user_metadata.get("is_active", True)
        if not is_active:
            logger.warning(f"Inactive user attempted access: {user_id}")
            raise HTTPException(
                status_code=403,
                detail="Your account has been deactivated. Please contact an administrator.",
            )

        logger.debug(f"Authenticated user: {user_id} with role: {role}")

        return user_id, role

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail="Authentication failed. Please log in again.",
        )


def require_role(
    *allowed_roles: UserRole,
) -> callable:
    """
    Dependency factory for role-based authorization.

    Usage:
        @router.get("/endpoint")
        async def endpoint(
            user_data: tuple[UUID, UserRole] = Depends(require_role("super_admin", "admin"))
        ):
            user_id, user_role = user_data
            # Endpoint logic

    Args:
        *allowed_roles: Roles that are allowed to access the endpoint

    Returns:
        FastAPI dependency that checks user role
    """

    async def _check_role(
        user_data: tuple[UUID, UserRole] = Depends(get_current_user_with_role),
    ) -> tuple[UUID, UserRole]:
        """Check if user has required role."""
        user_id, user_role = user_data

        if user_role not in allowed_roles:
            logger.warning(
                f"User {user_id} with role '{user_role}' attempted to access endpoint requiring {allowed_roles}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}",
            )

        return user_id, user_role

    return _check_role


def require_super_admin() -> callable:
    """
    Dependency for super_admin-only endpoints.

    Usage:
        @router.patch("/users/{user_id}/role")
        async def update_role(
            user_data: tuple[UUID, UserRole] = Depends(require_super_admin())
        ):
            admin_id, admin_role = user_data
            # Endpoint logic
    """
    return require_role("super_admin")


def require_admin() -> callable:
    """
    Dependency for admin and super_admin endpoints.

    Usage:
        @router.get("/admin/users")
        async def list_users(
            user_data: tuple[UUID, UserRole] = Depends(require_admin())
        ):
            user_id, user_role = user_data
            # Endpoint logic
    """
    return require_role("super_admin", "admin")
