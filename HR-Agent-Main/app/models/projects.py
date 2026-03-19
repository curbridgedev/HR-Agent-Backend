"""
Project-related Pydantic models for request/response validation.
"""

from typing import List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import Field

from app.models.base import BaseRequest, BaseResponse, TimestampMixin


class ProjectCreate(BaseRequest):
    """Request body for creating a project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Optional project description")


class ProjectUpdate(BaseRequest):
    """Request body for updating a project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")


class ProjectSummary(BaseResponse, TimestampMixin):
    """Summary of a project for list responses."""

    id: str = Field(..., description="Project UUID")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ProjectDetail(ProjectSummary):
    """Full project details."""

    pass


class ProjectsListResponse(BaseResponse):
    """Paginated list of projects."""

    projects: List[ProjectSummary] = Field(..., description="List of projects")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total pages")
