"""Pydantic models for user settings and API keys."""

from typing import Optional
from pydantic import BaseModel, Field


class UserSettingsResponse(BaseModel):
    """User settings (model and system prompt overrides)."""
    model_override: Optional[str] = Field(None, description="Override AI model")
    system_prompt_override: Optional[str] = Field(None, description="Override system prompt")


class UserSettingsUpdate(BaseModel):
    """Request to update user settings."""
    model_override: Optional[str] = Field(None, description="Override AI model")
    system_prompt_override: Optional[str] = Field(None, description="Override system prompt")


class UserAPIKeyCreateResponse(BaseModel):
    """Response when creating API key - full key shown only once."""
    id: str
    key: str = Field(..., description="Full API key - SAVE THIS, shown only once!")
    key_prefix: str
    name: str
    created_at: str


class UserAPIKeyListItem(BaseModel):
    """API key list item (no full key)."""
    id: str
    key_prefix: str
    name: str
    last_used_at: Optional[str] = None
    created_at: str
    enabled: bool
