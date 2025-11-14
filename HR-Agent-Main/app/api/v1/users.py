"""
User Management API endpoints (Admin Dashboard).

Provides endpoints for user listing, role management, activation/deactivation,
and audit logging.
"""

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.dependencies import UserRole, require_admin, require_super_admin
from app.core.logging import get_logger
from app.models.users import (
    ActivateUserRequest,
    ActivateUserResponse,
    AuditLogListResponse,
    BulkRoleUpdateRequest,
    BulkRoleUpdateResponse,
    DeactivateUserRequest,
    DeactivateUserResponse,
    UpdateRoleRequest,
    UpdateRoleResponse,
    UserDetailsResponse,
    UserListResponse,
)
from app.services.users import (
    activate_user,
    bulk_update_user_roles,
    deactivate_user,
    get_audit_logs,
    get_user_details,
    list_users,
    update_user_role,
)

logger = get_logger(__name__)

router = APIRouter()


# ============================================================================
# User Management Endpoints
# ============================================================================


@router.get("", response_model=UserListResponse)
async def get_users(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    active_only: bool = Query(False, description="Only return active users"),
    user_data: tuple[UUID, UserRole] = Depends(require_admin()),
):
    """
    List users with pagination and filtering.

    **Authentication**: Requires admin or super_admin role

    **Query Parameters**:
    - limit: Maximum items per page (1-100, default: 50)
    - offset: Number of items to skip for pagination (default: 0)
    - role: Filter by role (super_admin, admin, viewer)
    - active_only: Only return active users (default: false)

    **Returns**:
    - Paginated list of users with basic information

    **Example**:
        GET /api/v1/admin/users?limit=20&offset=0&role=admin&active_only=true
    """
    try:
        admin_id, admin_role = user_data
        logger.info(
            f"Admin {admin_id} listing users: limit={limit}, offset={offset}, role={role}, active_only={active_only}"
        )

        users_response = await list_users(
            limit=limit, offset=offset, role_filter=role, active_only=active_only
        )

        return users_response

    except Exception as e:
        logger.error(f"Failed to list users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}",
        )


@router.get("/{user_id}", response_model=UserDetailsResponse)
async def get_user(
    user_id: UUID,
    request: Request,
    user_data: tuple[UUID, UserRole] = Depends(require_admin()),
):
    """
    Get detailed user information.

    Returns full user details including:
    - Basic user information
    - Role change history
    - Activity statistics (sessions, actions)

    **Authentication**: Requires admin or super_admin role

    **Args**:
    - user_id: User UUID

    **Returns**:
    - User details with role history

    **Error Handling**:
    - 404 Not Found: User doesn't exist

    **Example**:
        GET /api/v1/admin/users/550e8400-e29b-41d4-a716-446655440000
    """
    try:
        admin_id, admin_role = user_data
        logger.info(f"Admin {admin_id} fetching user details: {user_id}")

        user_details = await get_user_details(user_id)

        if not user_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: {user_id}",
            )

        return UserDetailsResponse(user=user_details)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user details: {str(e)}",
        )


# ============================================================================
# Role Management Endpoints
# ============================================================================


@router.patch("/{user_id}/role", response_model=UpdateRoleResponse)
async def update_user_role_endpoint(
    user_id: UUID,
    request: Request,
    role_request: UpdateRoleRequest,
    user_data: tuple[UUID, UserRole] = Depends(require_super_admin()),
):
    """
    Update user role (super_admin only).

    **Business Rules**:
    - Only super_admin can update roles
    - Cannot modify own role (prevent privilege escalation)
    - Cannot demote last super_admin
    - User sessions will be invalidated (force re-login)

    **Authentication**: Requires super_admin role

    **Args**:
    - user_id: User UUID
    - role_request: New role and optional reason

    **Returns**:
    - Updated role information

    **Error Handling**:
    - 403 Forbidden: Not super_admin, trying to modify own role, or demoting last super_admin
    - 404 Not Found: User doesn't exist

    **Example**:
        PATCH /api/v1/admin/users/550e8400-e29b-41d4-a716-446655440000/role
        {
          "new_role": "admin",
          "reason": "Promotion to admin role for project management"
        }
    """
    try:
        admin_id, admin_role = user_data
        logger.info(
            f"Admin {admin_id} updating role for user {user_id} to {role_request.new_role}"
        )

        # Get IP address and user agent for audit logging
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        result = await update_user_role(
            user_id=user_id,
            new_role=role_request.new_role,
            admin_user_id=admin_id,
            admin_role=admin_role,
            reason=role_request.reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user role",
            )

        logger.info(f"Successfully updated role for user {user_id}")
        return result

    except ValueError as e:
        logger.warning(f"Role update failed: {e}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user role: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user role: {str(e)}",
        )


@router.post("/bulk/role", response_model=BulkRoleUpdateResponse)
async def bulk_update_roles(
    request: Request,
    bulk_request: BulkRoleUpdateRequest,
    user_data: tuple[UUID, UserRole] = Depends(require_super_admin()),
):
    """
    Bulk update multiple users' roles (super_admin only).

    Same business rules as single role update apply.

    **Authentication**: Requires super_admin role

    **Args**:
    - bulk_request: List of user IDs, new role, and optional reason

    **Returns**:
    - Success/failure counts and lists of updated/failed user IDs

    **Error Handling**:
    - Partial success: Some users updated, some failed (returns details)
    - 403 Forbidden: Not super_admin

    **Example**:
        POST /api/v1/admin/users/bulk/role
        {
          "user_ids": [
            "550e8400-e29b-41d4-a716-446655440000",
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
          ],
          "new_role": "admin",
          "reason": "Batch promotion to admin role"
        }
    """
    try:
        admin_id, admin_role = user_data
        logger.info(
            f"Admin {admin_id} bulk updating roles for {len(bulk_request.user_ids)} users to {bulk_request.new_role}"
        )

        # Get IP address and user agent for audit logging
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        result = await bulk_update_user_roles(
            user_ids=bulk_request.user_ids,
            new_role=bulk_request.new_role,
            admin_user_id=admin_id,
            admin_role=admin_role,
            reason=bulk_request.reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            f"Bulk role update completed: {result.success_count} succeeded, {result.failed_count} failed"
        )
        return result

    except Exception as e:
        logger.error(f"Failed to bulk update roles: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk update roles: {str(e)}",
        )


# ============================================================================
# User Activation/Deactivation Endpoints
# ============================================================================


@router.post("/{user_id}/deactivate", response_model=DeactivateUserResponse)
async def deactivate_user_endpoint(
    user_id: UUID,
    request: Request,
    deactivate_request: DeactivateUserRequest,
    user_data: tuple[UUID, UserRole] = Depends(require_admin()),
):
    """
    Deactivate user (prevent login).

    **Business Rules**:
    - Cannot deactivate own account
    - User sessions will be invalidated (force logout)
    - User will not be able to log in until reactivated

    **Authentication**: Requires admin or super_admin role

    **Args**:
    - user_id: User UUID
    - deactivate_request: Optional reason for deactivation

    **Returns**:
    - Deactivation confirmation

    **Error Handling**:
    - 403 Forbidden: Trying to deactivate own account
    - 404 Not Found: User doesn't exist

    **Example**:
        POST /api/v1/admin/users/550e8400-e29b-41d4-a716-446655440000/deactivate
        {
          "reason": "Account suspended pending investigation"
        }
    """
    try:
        admin_id, admin_role = user_data
        logger.info(f"Admin {admin_id} deactivating user {user_id}")

        # Get IP address and user agent for audit logging
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        result = await deactivate_user(
            user_id=user_id,
            admin_user_id=admin_id,
            admin_role=admin_role,
            reason=deactivate_request.reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to deactivate user",
            )

        logger.info(f"Successfully deactivated user {user_id}")
        return result

    except ValueError as e:
        logger.warning(f"User deactivation failed: {e}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate user: {str(e)}",
        )


@router.post("/{user_id}/activate", response_model=ActivateUserResponse)
async def activate_user_endpoint(
    user_id: UUID,
    request: Request,
    activate_request: ActivateUserRequest,
    user_data: tuple[UUID, UserRole] = Depends(require_admin()),
):
    """
    Activate user (allow login).

    **Authentication**: Requires admin or super_admin role

    **Args**:
    - user_id: User UUID
    - activate_request: Optional reason for activation

    **Returns**:
    - Activation confirmation

    **Error Handling**:
    - 404 Not Found: User doesn't exist

    **Example**:
        POST /api/v1/admin/users/550e8400-e29b-41d4-a716-446655440000/activate
        {
          "reason": "Investigation completed, account restored"
        }
    """
    try:
        admin_id, admin_role = user_data
        logger.info(f"Admin {admin_id} activating user {user_id}")

        # Get IP address and user agent for audit logging
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        result = await activate_user(
            user_id=user_id,
            admin_user_id=admin_id,
            admin_role=admin_role,
            reason=activate_request.reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to activate user",
            )

        logger.info(f"Successfully activated user {user_id}")
        return result

    except ValueError as e:
        logger.warning(f"User activation failed: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate user: {str(e)}",
        )


# ============================================================================
# Audit Log Endpoint
# ============================================================================


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs_endpoint(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    action: Optional[
        Literal["role_change", "deactivate", "activate", "bulk_role_change"]
    ] = Query(None, description="Filter by action type"),
    affected_user: Optional[UUID] = Query(None, description="Filter by affected user"),
    performed_by: Optional[UUID] = Query(None, description="Filter by admin who performed action"),
    user_data: tuple[UUID, UserRole] = Depends(require_admin()),
):
    """
    Get audit logs with pagination and filtering.

    **Authentication**: Requires admin or super_admin role

    **Query Parameters**:
    - limit: Maximum items per page (1-100, default: 50)
    - offset: Number of items to skip for pagination (default: 0)
    - action: Filter by action type (role_change, deactivate, activate, bulk_role_change)
    - affected_user: Filter by user who was affected
    - performed_by: Filter by admin who performed the action

    **Returns**:
    - Paginated list of audit log entries

    **Example**:
        GET /api/v1/admin/audit-logs?limit=20&action=role_change&affected_user=550e8400-e29b-41d4-a716-446655440000
    """
    try:
        admin_id, admin_role = user_data
        logger.info(f"Admin {admin_id} fetching audit logs")

        logs_response = await get_audit_logs(
            limit=limit,
            offset=offset,
            action_filter=action,
            affected_user_filter=affected_user,
            performed_by_filter=performed_by,
        )

        return logs_response

    except Exception as e:
        logger.error(f"Failed to get audit logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit logs: {str(e)}",
        )
