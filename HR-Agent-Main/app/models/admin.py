"""
Admin dashboard API models.

Pydantic models for admin dashboard endpoints matching frontend requirements.
These models bridge the gap between existing database schema and frontend expectations.
"""

from datetime import datetime
from typing import Optional, List, Literal
from uuid import UUID
from pydantic import Field, ConfigDict
from app.models.base import BaseRequest, BaseResponse


# ============================================================================
# Agent Configuration Models (simplified for frontend)
# ============================================================================

class AgentConfigResponse(BaseResponse):
    """
    Simplified agent configuration response for admin dashboard.

    Maps from existing agent_configs.config JSONB to flat structure.
    """

    id: UUID = Field(..., description="Config UUID")
    model_provider: Literal["openai", "anthropic", "google"] = Field(
        ..., description="LLM provider"
    )
    model_name: str = Field(..., description="Model identifier (e.g., gpt-4-turbo)")
    temperature: float = Field(..., ge=0.0, le=2.0, description="Sampling temperature")
    confidence_threshold: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence threshold for escalation"
    )
    active_system_prompt: "SystemPromptSummary" = Field(
        ..., description="Currently active system prompt"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class AgentConfigUpdateRequest(BaseRequest):
    """Request model for updating agent configuration."""

    model_provider: Optional[Literal["openai", "anthropic", "google"]] = Field(
        None, description="Update LLM provider"
    )
    model_name: Optional[str] = Field(None, description="Update model name")
    temperature: Optional[float] = Field(
        None, ge=0.0, le=2.0, description="Update temperature"
    )
    confidence_threshold: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Update confidence threshold"
    )


# ============================================================================
# System Prompt Models (simplified for frontend)
# ============================================================================

class SystemPromptSummary(BaseResponse):
    """Summary of active system prompt embedded in agent config response."""

    id: UUID = Field(..., description="Prompt UUID")
    version: int = Field(..., description="Prompt version number")
    content: str = Field(..., description="Prompt text content")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class SystemPromptResponse(BaseResponse):
    """Full system prompt response for listing."""

    id: UUID = Field(..., description="Prompt UUID")
    version: int = Field(..., description="Prompt version number")
    content: str = Field(..., description="Prompt text content")
    created_by: Optional[str] = Field(None, description="Creator (Supabase user ID)")
    created_at: datetime = Field(..., description="Creation timestamp")
    is_active: bool = Field(..., description="Whether this version is currently active")
    performance_notes: Optional[str] = Field(
        None, description="Notes about this version's performance"
    )

    model_config = ConfigDict(from_attributes=True)


class SystemPromptListResponse(BaseResponse):
    """Response model for listing system prompts with pagination."""

    prompts: List[SystemPromptResponse] = Field(..., description="List of prompts")
    total_count: int = Field(..., description="Total number of prompts")
    pagination: "PaginationInfo" = Field(..., description="Pagination metadata")


class SystemPromptCreateRequest(BaseRequest):
    """Request model for creating new system prompt version."""

    content: str = Field(..., min_length=10, description="Prompt text content (required)")
    performance_notes: Optional[str] = Field(
        None, description="Optional notes about this version"
    )


class PaginationInfo(BaseResponse):
    """Pagination metadata."""

    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Number of items skipped")
    has_more: bool = Field(..., description="Whether more items exist")


# Update forward references
AgentConfigResponse.model_rebuild()
SystemPromptListResponse.model_rebuild()
