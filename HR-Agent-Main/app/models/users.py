"""
Pydantic models for User Management API (Admin Dashboard).

Provides models for user listing, role management, activation/deactivation,
and audit logging.
"""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.base import BaseRequest, BaseResponse


# ============================================================================
# User Role Types
# ============================================================================

UserRole = Literal["super_admin", "admin", "viewer"]

# Role hierarchy for authorization checks
ROLE_HIERARCHY = {
    "super_admin": 3,
    "admin": 2,
    "viewer": 1,
}


# ============================================================================
# User Models
# ============================================================================


class UserBase(BaseModel):
    """Base user information from Supabase Auth."""

    id: UUID = Field(..., description="User ID from Supabase Auth")
    email: EmailStr = Field(..., description="User email address")
    role: UserRole = Field(..., description="User role: super_admin, admin, or viewer")
    created_at: datetime = Field(..., description="When user was created")
    last_sign_in_at: Optional[datetime] = Field(
        None, description="Last sign-in timestamp"
    )
    is_active: bool = Field(True, description="Whether user is active")


class UserListItem(UserBase):
    """User information for list view."""

    # Inherits all UserBase fields
    pass


class UserDetails(UserBase):
    """Detailed user information including role history."""

    role_history: List["RoleHistoryItem"] = Field(
        default_factory=list, description="User's role change history"
    )
    total_sessions: int = Field(0, description="Total number of sessions")
    total_actions: int = Field(0, description="Total number of actions performed")


class RoleHistoryItem(BaseModel):
    """Single role change history entry."""

    timestamp: datetime = Field(..., description="When role was changed")
    old_role: Optional[UserRole] = Field(None, description="Previous role")
    new_role: UserRole = Field(..., description="New role assigned")
    changed_by: UUID = Field(..., description="Admin who made the change")
    changed_by_email: str = Field(..., description="Email of admin who made the change")
    reason: Optional[str] = Field(None, description="Reason for role change")


# ============================================================================
# Request Models
# ============================================================================


class UpdateRoleRequest(BaseRequest):
    """Request to update user role."""

    new_role: UserRole = Field(..., description="New role to assign")
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional reason for role change (max 500 chars)",
    )


class BulkRoleUpdateRequest(BaseRequest):
    """Request to update multiple users' roles."""

    user_ids: List[UUID] = Field(
        ..., min_length=1, max_length=100, description="List of user IDs (1-100)"
    )
    new_role: UserRole = Field(..., description="New role to assign to all users")
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional reason for bulk role change (max 500 chars)",
    )


class DeactivateUserRequest(BaseRequest):
    """Request to deactivate user."""

    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional reason for deactivation (max 500 chars)",
    )


class ActivateUserRequest(BaseRequest):
    """Request to activate user."""

    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional reason for activation (max 500 chars)",
    )


# ============================================================================
# Response Models
# ============================================================================


class UserListResponse(BaseResponse):
    """Paginated list of users."""

    users: List[UserListItem] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users matching filters")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Number of items skipped")


class UserDetailsResponse(BaseResponse):
    """Detailed user information response."""

    user: UserDetails = Field(..., description="Detailed user information")


class UpdateRoleResponse(BaseResponse):
    """Response after role update."""

    user_id: UUID = Field(..., description="User ID")
    old_role: UserRole = Field(..., description="Previous role")
    new_role: UserRole = Field(..., description="New role assigned")
    changed_by: UUID = Field(..., description="Admin who made the change")
    reason: Optional[str] = Field(None, description="Reason for change")
    session_invalidated: bool = Field(
        ..., description="Whether user's sessions were invalidated"
    )


class BulkRoleUpdateResponse(BaseResponse):
    """Response after bulk role update."""

    success_count: int = Field(..., description="Number of successfully updated users")
    failed_count: int = Field(..., description="Number of failed updates")
    updated_user_ids: List[UUID] = Field(..., description="List of successfully updated user IDs")
    failed_user_ids: List[UUID] = Field(
        default_factory=list, description="List of failed user IDs"
    )
    errors: List[str] = Field(
        default_factory=list, description="List of error messages for failed updates"
    )


class DeactivateUserResponse(BaseResponse):
    """Response after user deactivation."""

    user_id: UUID = Field(..., description="Deactivated user ID")
    email: str = Field(..., description="Deactivated user email")
    deactivated_at: datetime = Field(..., description="When user was deactivated")
    deactivated_by: UUID = Field(..., description="Admin who deactivated the user")
    reason: Optional[str] = Field(None, description="Reason for deactivation")
    session_invalidated: bool = Field(
        ..., description="Whether user's sessions were invalidated"
    )


class ActivateUserResponse(BaseResponse):
    """Response after user activation."""

    user_id: UUID = Field(..., description="Activated user ID")
    email: str = Field(..., description="Activated user email")
    activated_at: datetime = Field(..., description="When user was activated")
    activated_by: UUID = Field(..., description="Admin who activated the user")
    reason: Optional[str] = Field(None, description="Reason for activation")


# ============================================================================
# Audit Log Models
# ============================================================================


class AuditLogEntry(BaseModel):
    """Single audit log entry."""

    log_id: UUID = Field(..., description="Unique log entry ID")
    timestamp: datetime = Field(..., description="When action was performed")
    action: Literal["role_change", "deactivate", "activate", "bulk_role_change"] = Field(
        ..., description="Type of action performed"
    )
    performed_by: UUID = Field(..., description="Admin who performed the action")
    performed_by_email: str = Field(..., description="Email of admin who performed the action")
    affected_user: UUID = Field(..., description="User who was affected")
    affected_user_email: str = Field(..., description="Email of affected user")
    old_value: Optional[str] = Field(None, description="Previous value (role or status)")
    new_value: Optional[str] = Field(None, description="New value (role or status)")
    reason: Optional[str] = Field(None, description="Reason for action")
    ip_address: Optional[str] = Field(None, description="IP address of admin")
    user_agent: Optional[str] = Field(None, description="User agent of admin")


class AuditLogListResponse(BaseResponse):
    """Paginated list of audit logs."""

    logs: List[AuditLogEntry] = Field(..., description="List of audit log entries")
    total: int = Field(..., description="Total number of logs matching filters")
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Number of items skipped")
