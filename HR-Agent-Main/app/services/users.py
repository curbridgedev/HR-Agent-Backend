"""
User Management Service Layer.

Handles user listing, role management, activation/deactivation,
audit logging, and integration with Supabase Auth.
"""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from postgrest.exceptions import APIError
from supabase import AuthApiError, Client

from app.core.config import settings
from app.core.logging import get_logger
from app.db.supabase import get_supabase_client
from app.models.users import (
    ROLE_HIERARCHY,
    ActivateUserResponse,
    AuditLogEntry,
    AuditLogListResponse,
    BulkRoleUpdateResponse,
    DeactivateUserResponse,
    RoleHistoryItem,
    UpdateRoleResponse,
    UserDetails,
    UserListItem,
    UserListResponse,
    UserRole,
)

logger = get_logger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================


def _has_higher_role(role1: UserRole, role2: UserRole) -> bool:
    """Check if role1 has higher privileges than role2."""
    return ROLE_HIERARCHY[role1] > ROLE_HIERARCHY[role2]


async def _get_user_role_from_metadata(
    user_id: UUID, db: Optional[Client] = None
) -> Optional[UserRole]:
    """Get user role from Supabase Auth user metadata."""
    if db is None:
        db = get_supabase_client()

    try:
        # Get user from Supabase Auth Admin API
        # Note: This requires service role key
        user_response = db.auth.admin.get_user_by_id(str(user_id))

        if not user_response or not user_response.user:
            return None

        # Extract role from user metadata
        user_metadata = user_response.user.user_metadata or {}
        role = user_metadata.get("role", "viewer")

        # Validate role
        if role not in ["super_admin", "admin", "viewer"]:
            logger.warning(f"Invalid role '{role}' for user {user_id}, defaulting to viewer")
            return "viewer"

        return role

    except AuthApiError as e:
        logger.error(f"Failed to get user role from metadata: {e}")
        return None


async def _update_user_role_in_metadata(
    user_id: UUID, new_role: UserRole, db: Optional[Client] = None
) -> bool:
    """Update user role in Supabase Auth user metadata."""
    if db is None:
        db = get_supabase_client()

    try:
        # Update user metadata via Supabase Auth Admin API
        db.auth.admin.update_user_by_id(
            str(user_id), {"user_metadata": {"role": new_role}}
        )
        return True

    except AuthApiError as e:
        logger.error(f"Failed to update user role in metadata: {e}")
        return False


async def _invalidate_user_sessions(
    user_id: UUID, db: Optional[Client] = None
) -> bool:
    """Invalidate all sessions for a user (force re-login)."""
    if db is None:
        db = get_supabase_client()

    try:
        # Sign out user from all devices via Supabase Auth Admin API
        db.auth.admin.sign_out(str(user_id))
        return True

    except AuthApiError as e:
        logger.error(f"Failed to invalidate user sessions: {e}")
        return False


async def _log_audit_action(
    action: Literal["role_change", "deactivate", "activate", "bulk_role_change"],
    performed_by: UUID,
    affected_user: UUID,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db: Optional[Client] = None,
) -> None:
    """Log user management action to audit trail."""
    if db is None:
        db = get_supabase_client()

    try:
        db.table("user_audit_logs").insert(
            {
                "action": action,
                "performed_by": str(performed_by),
                "affected_user": str(affected_user),
                "old_value": old_value,
                "new_value": new_value,
                "reason": reason,
                "ip_address": ip_address,
                "user_agent": user_agent,
            }
        ).execute()

        logger.info(
            f"Audit log created: {action} on user {affected_user} by {performed_by}"
        )

    except APIError as e:
        logger.error(f"Failed to create audit log: {e}")
        # Don't fail the operation if audit logging fails


# ============================================================================
# User Listing
# ============================================================================


async def list_users(
    limit: int = 50,
    offset: int = 0,
    role_filter: Optional[UserRole] = None,
    active_only: bool = False,
    db: Optional[Client] = None,
) -> UserListResponse:
    """
    List users with pagination and filtering.

    Args:
        limit: Maximum items per page (1-100)
        offset: Number of items to skip
        role_filter: Filter by role (optional)
        active_only: Only return active users (optional)
        db: Optional database client

    Returns:
        Paginated list of users
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Get users from Supabase Auth Admin API
        # Note: list_users() returns a list of User objects directly (not wrapped in response object)
        users_list = db.auth.admin.list_users(page=offset // limit + 1, per_page=limit)

        if not users_list:
            return UserListResponse(users=[], total=0, limit=limit, offset=offset)

        # Map to UserListItem
        users = []
        for user in users_list:
            # Extract role from metadata
            role = user.user_metadata.get("role", "viewer")

            # Apply filters
            if role_filter and role != role_filter:
                continue

            if active_only and user.user_metadata.get("is_active", True) is False:
                continue

            users.append(
                UserListItem(
                    id=UUID(user.id),
                    email=user.email,
                    role=role,
                    # Supabase returns datetime objects directly, not strings
                    created_at=user.created_at,
                    last_sign_in_at=user.last_sign_in_at,
                    is_active=user.user_metadata.get("is_active", True),
                )
            )

        # TODO: Get accurate total count from Supabase Auth
        # For now, estimate based on current page
        total = len(users) + offset

        return UserListResponse(users=users, total=total, limit=limit, offset=offset)

    except AuthApiError as e:
        logger.error(f"Failed to list users: {e}", exc_info=True)
        raise ValueError(f"Failed to list users: {str(e)}")


# ============================================================================
# User Details
# ============================================================================


async def get_user_details(
    user_id: UUID, db: Optional[Client] = None
) -> Optional[UserDetails]:
    """
    Get detailed user information including role history.

    Args:
        user_id: User UUID
        db: Optional database client

    Returns:
        User details or None if not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Get user from Supabase Auth Admin API
        user_response = db.auth.admin.get_user_by_id(str(user_id))

        if not user_response or not user_response.user:
            return None

        user = user_response.user

        # Extract role from metadata
        role = user.user_metadata.get("role", "viewer")

        # Get role history from audit logs
        role_history_response = (
            db.table("user_audit_logs")
            .select(
                "timestamp,old_value,new_value,performed_by,reason,"
                "performed_by_user:auth.users!performed_by(email)"
            )
            .eq("affected_user", str(user_id))
            .eq("action", "role_change")
            .order("timestamp", desc=True)
            .limit(50)
            .execute()
        )

        role_history = []
        for log in role_history_response.data:
            performed_by_email = (
                log.get("performed_by_user", {}).get("email", "Unknown")
                if log.get("performed_by_user")
                else "Unknown"
            )

            role_history.append(
                RoleHistoryItem(
                    timestamp=datetime.fromisoformat(log["timestamp"]),
                    old_role=log.get("old_value"),
                    new_role=log["new_value"],
                    changed_by=UUID(log["performed_by"]),
                    changed_by_email=performed_by_email,
                    reason=log.get("reason"),
                )
            )

        # Get session count (approximate)
        sessions_response = (
            db.table("chat_sessions")
            .select("id", count="exact")
            .eq("user_id", str(user_id))
            .execute()
        )
        total_sessions = sessions_response.count or 0

        # Get action count from audit logs
        actions_response = (
            db.table("user_audit_logs")
            .select("log_id", count="exact")
            .eq("performed_by", str(user_id))
            .execute()
        )
        total_actions = actions_response.count or 0

        return UserDetails(
            id=UUID(user.id),
            email=user.email,
            role=role,
            created_at=datetime.fromisoformat(user.created_at.replace("Z", "+00:00")),
            last_sign_in_at=(
                datetime.fromisoformat(user.last_sign_in_at.replace("Z", "+00:00"))
                if user.last_sign_in_at
                else None
            ),
            is_active=user.user_metadata.get("is_active", True),
            role_history=role_history,
            total_sessions=total_sessions,
            total_actions=total_actions,
        )

    except AuthApiError as e:
        logger.error(f"Failed to get user details: {e}", exc_info=True)
        return None


# ============================================================================
# Role Management
# ============================================================================


async def update_user_role(
    user_id: UUID,
    new_role: UserRole,
    admin_user_id: UUID,
    admin_role: UserRole,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db: Optional[Client] = None,
) -> Optional[UpdateRoleResponse]:
    """
    Update user role (super_admin only).

    Business rules:
    - Only super_admin can update roles
    - Cannot modify own role (prevent privilege escalation)
    - Cannot demote last super_admin
    - Invalidate sessions after role change

    Args:
        user_id: User to update
        new_role: New role to assign
        admin_user_id: Admin performing the action
        admin_role: Role of admin performing the action
        reason: Optional reason for change
        ip_address: IP address of admin
        user_agent: User agent of admin
        db: Optional database client

    Returns:
        UpdateRoleResponse or None if failed
    """
    if db is None:
        db = get_supabase_client()

    # Validate: Only super_admin can update roles
    if admin_role != "super_admin":
        raise ValueError("Only super_admin can update user roles")

    # Validate: Cannot modify own role
    if user_id == admin_user_id:
        raise ValueError("Cannot modify your own role")

    # Get current role
    old_role = await _get_user_role_from_metadata(user_id, db)
    if not old_role:
        raise ValueError(f"User not found: {user_id}")

    # Validate: Cannot demote last super_admin
    if old_role == "super_admin" and new_role != "super_admin":
        # Count super_admins
        users_response = db.auth.admin.list_users()
        super_admin_count = sum(
            1
            for u in users_response.users
            if u.user_metadata.get("role") == "super_admin"
        )

        if super_admin_count <= 1:
            raise ValueError("Cannot demote the last super_admin")

    # Update role in metadata
    success = await _update_user_role_in_metadata(user_id, new_role, db)
    if not success:
        raise ValueError("Failed to update user role")

    # Invalidate sessions (force re-login)
    session_invalidated = await _invalidate_user_sessions(user_id, db)

    # Log audit action
    await _log_audit_action(
        action="role_change",
        performed_by=admin_user_id,
        affected_user=user_id,
        old_value=old_role,
        new_value=new_role,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
        db=db,
    )

    return UpdateRoleResponse(
        user_id=user_id,
        old_role=old_role,
        new_role=new_role,
        changed_by=admin_user_id,
        reason=reason,
        session_invalidated=session_invalidated,
    )


async def bulk_update_user_roles(
    user_ids: List[UUID],
    new_role: UserRole,
    admin_user_id: UUID,
    admin_role: UserRole,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db: Optional[Client] = None,
) -> BulkRoleUpdateResponse:
    """
    Bulk update multiple users' roles.

    Same business rules as update_user_role apply.

    Args:
        user_ids: List of users to update
        new_role: New role to assign
        admin_user_id: Admin performing the action
        admin_role: Role of admin performing the action
        reason: Optional reason for change
        ip_address: IP address of admin
        user_agent: User agent of admin
        db: Optional database client

    Returns:
        BulkRoleUpdateResponse with success/failure counts
    """
    if db is None:
        db = get_supabase_client()

    success_count = 0
    failed_count = 0
    updated_user_ids = []
    failed_user_ids = []
    errors = []

    for user_id in user_ids:
        try:
            result = await update_user_role(
                user_id=user_id,
                new_role=new_role,
                admin_user_id=admin_user_id,
                admin_role=admin_role,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
                db=db,
            )

            if result:
                success_count += 1
                updated_user_ids.append(user_id)
            else:
                failed_count += 1
                failed_user_ids.append(user_id)
                errors.append(f"User {user_id}: Update failed")

        except ValueError as e:
            failed_count += 1
            failed_user_ids.append(user_id)
            errors.append(f"User {user_id}: {str(e)}")

    return BulkRoleUpdateResponse(
        success_count=success_count,
        failed_count=failed_count,
        updated_user_ids=updated_user_ids,
        failed_user_ids=failed_user_ids,
        errors=errors,
    )


# ============================================================================
# User Activation/Deactivation
# ============================================================================


async def deactivate_user(
    user_id: UUID,
    admin_user_id: UUID,
    admin_role: UserRole,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db: Optional[Client] = None,
) -> Optional[DeactivateUserResponse]:
    """
    Deactivate user (prevent login).

    Args:
        user_id: User to deactivate
        admin_user_id: Admin performing the action
        admin_role: Role of admin performing the action
        reason: Optional reason for deactivation
        ip_address: IP address of admin
        user_agent: User agent of admin
        db: Optional database client

    Returns:
        DeactivateUserResponse or None if failed
    """
    if db is None:
        db = get_supabase_client()

    # Validate: Cannot deactivate own account
    if user_id == admin_user_id:
        raise ValueError("Cannot deactivate your own account")

    try:
        # Get user details
        user_response = db.auth.admin.get_user_by_id(str(user_id))
        if not user_response or not user_response.user:
            raise ValueError(f"User not found: {user_id}")

        user = user_response.user

        # Update user metadata to mark as inactive
        db.auth.admin.update_user_by_id(
            str(user_id), {"user_metadata": {"is_active": False}}
        )

        # Invalidate sessions (force logout)
        session_invalidated = await _invalidate_user_sessions(user_id, db)

        # Log audit action
        await _log_audit_action(
            action="deactivate",
            performed_by=admin_user_id,
            affected_user=user_id,
            old_value="active",
            new_value="inactive",
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            db=db,
        )

        return DeactivateUserResponse(
            user_id=user_id,
            email=user.email,
            deactivated_at=datetime.utcnow(),
            deactivated_by=admin_user_id,
            reason=reason,
            session_invalidated=session_invalidated,
        )

    except AuthApiError as e:
        logger.error(f"Failed to deactivate user: {e}", exc_info=True)
        raise ValueError(f"Failed to deactivate user: {str(e)}")


async def activate_user(
    user_id: UUID,
    admin_user_id: UUID,
    admin_role: UserRole,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db: Optional[Client] = None,
) -> Optional[ActivateUserResponse]:
    """
    Activate user (allow login).

    Args:
        user_id: User to activate
        admin_user_id: Admin performing the action
        admin_role: Role of admin performing the action
        reason: Optional reason for activation
        ip_address: IP address of admin
        user_agent: User agent of admin
        db: Optional database client

    Returns:
        ActivateUserResponse or None if failed
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Get user details
        user_response = db.auth.admin.get_user_by_id(str(user_id))
        if not user_response or not user_response.user:
            raise ValueError(f"User not found: {user_id}")

        user = user_response.user

        # Update user metadata to mark as active
        db.auth.admin.update_user_by_id(
            str(user_id), {"user_metadata": {"is_active": True}}
        )

        # Log audit action
        await _log_audit_action(
            action="activate",
            performed_by=admin_user_id,
            affected_user=user_id,
            old_value="inactive",
            new_value="active",
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            db=db,
        )

        return ActivateUserResponse(
            user_id=user_id,
            email=user.email,
            activated_at=datetime.utcnow(),
            activated_by=admin_user_id,
            reason=reason,
        )

    except AuthApiError as e:
        logger.error(f"Failed to activate user: {e}", exc_info=True)
        raise ValueError(f"Failed to activate user: {str(e)}")


# ============================================================================
# Audit Logs
# ============================================================================


async def get_audit_logs(
    limit: int = 50,
    offset: int = 0,
    action_filter: Optional[
        Literal["role_change", "deactivate", "activate", "bulk_role_change"]
    ] = None,
    affected_user_filter: Optional[UUID] = None,
    performed_by_filter: Optional[UUID] = None,
    db: Optional[Client] = None,
) -> AuditLogListResponse:
    """
    Get audit logs with pagination and filtering.

    Args:
        limit: Maximum items per page (1-100)
        offset: Number of items to skip
        action_filter: Filter by action type (optional)
        affected_user_filter: Filter by affected user (optional)
        performed_by_filter: Filter by admin who performed action (optional)
        db: Optional database client

    Returns:
        Paginated list of audit logs
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Build query
        query = db.table("user_audit_logs").select(
            "*,"
            "performed_by_user:auth.users!performed_by(email),"
            "affected_user_user:auth.users!affected_user(email)",
            count="exact",
        )

        # Apply filters
        if action_filter:
            query = query.eq("action", action_filter)

        if affected_user_filter:
            query = query.eq("affected_user", str(affected_user_filter))

        if performed_by_filter:
            query = query.eq("performed_by", str(performed_by_filter))

        # Execute query with pagination
        logs_response = (
            query.order("timestamp", desc=True).range(offset, offset + limit - 1).execute()
        )

        # Map to AuditLogEntry
        logs = []
        for log in logs_response.data:
            performed_by_email = (
                log.get("performed_by_user", {}).get("email", "Unknown")
                if log.get("performed_by_user")
                else "Unknown"
            )
            affected_user_email = (
                log.get("affected_user_user", {}).get("email", "Unknown")
                if log.get("affected_user_user")
                else "Unknown"
            )

            logs.append(
                AuditLogEntry(
                    log_id=UUID(log["log_id"]),
                    timestamp=datetime.fromisoformat(log["timestamp"]),
                    action=log["action"],
                    performed_by=UUID(log["performed_by"]),
                    performed_by_email=performed_by_email,
                    affected_user=UUID(log["affected_user"]),
                    affected_user_email=affected_user_email,
                    old_value=log.get("old_value"),
                    new_value=log.get("new_value"),
                    reason=log.get("reason"),
                    ip_address=log.get("ip_address"),
                    user_agent=log.get("user_agent"),
                )
            )

        total = logs_response.count or 0

        return AuditLogListResponse(logs=logs, total=total, limit=limit, offset=offset)

    except APIError as e:
        logger.error(f"Failed to get audit logs: {e}", exc_info=True)
        raise ValueError(f"Failed to get audit logs: {str(e)}")
