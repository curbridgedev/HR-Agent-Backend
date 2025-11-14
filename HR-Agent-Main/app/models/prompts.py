"""
Prompt management models.

Pydantic models for system prompt management with versioning.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import Field, ConfigDict
from app.models.base import BaseRequest, BaseResponse


# Enums for prompt types
class PromptType:
    """Valid prompt types."""

    SYSTEM = "system"
    RETRIEVAL = "retrieval"
    GENERATION = "generation"
    CONFIDENCE = "confidence"
    ESCALATION = "escalation"


class PromptBase(BaseRequest):
    """Base prompt model with common fields."""

    name: str = Field(..., description="Unique identifier for the prompt")
    prompt_type: str = Field(..., description="Type of prompt (system, retrieval, etc.)")
    content: str = Field(..., description="The prompt content/text")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional configuration (temperature, max_tokens, etc.)",
    )
    notes: Optional[str] = Field(None, description="Change notes or description")


class PromptCreate(PromptBase):
    """Model for creating a new prompt version."""

    created_by: Optional[str] = Field(None, description="User who created this version")
    activate_immediately: bool = Field(
        False, description="Whether to activate this version immediately"
    )


class PromptUpdate(BaseRequest):
    """Model for updating a prompt."""

    content: Optional[str] = Field(None, description="Updated prompt content")
    tags: Optional[List[str]] = Field(None, description="Updated tags")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")
    notes: Optional[str] = Field(None, description="Update notes")


class PromptResponse(BaseResponse):
    """Model for prompt response."""

    id: UUID = Field(..., description="Prompt UUID")
    name: str = Field(..., description="Prompt name")
    prompt_type: str = Field(..., description="Prompt type")
    version: int = Field(..., description="Version number")
    content: str = Field(..., description="Prompt content")
    active: bool = Field(..., description="Whether this version is active")
    tags: List[str] = Field(default_factory=list, description="Tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata")

    # Performance tracking
    usage_count: int = Field(0, description="Number of times used")
    avg_confidence: Optional[float] = Field(None, description="Average confidence score")
    escalation_rate: Optional[float] = Field(
        None, description="Rate of escalations when using this prompt"
    )

    # Audit
    created_by: Optional[str] = Field(None, description="Creator")
    notes: Optional[str] = Field(None, description="Version notes")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class PromptListResponse(BaseResponse):
    """Model for listing prompts."""

    prompts: List[PromptResponse] = Field(..., description="List of prompts")
    total: int = Field(..., description="Total number of prompts")
    page: int = Field(1, description="Current page")
    page_size: int = Field(50, description="Page size")


class PromptActivateRequest(BaseRequest):
    """Model for activating a prompt version."""

    prompt_id: UUID = Field(..., description="ID of prompt version to activate")


class PromptVersionCreateResponse(BaseResponse):
    """Model for prompt version creation response."""

    prompt_id: UUID = Field(..., description="ID of newly created prompt version")
    version: int = Field(..., description="Version number")
    active: bool = Field(..., description="Whether version was activated")
