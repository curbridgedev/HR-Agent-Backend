"""
User settings API - API keys and system preferences.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Body
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user_id
from app.models.user_settings import (
    UserSettingsResponse,
    UserSettingsUpdate,
    UserAPIKeyCreateResponse,
    UserAPIKeyListItem,
)
from app.services.user_settings import (
    get_user_settings_for_user,
    upsert_user_settings,
)
from app.services.user_api_keys import (
    create_user_api_key,
    list_user_api_keys,
    revoke_user_api_key,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================================================
# User Settings (model + system prompt)
# ============================================================================

@router.get("/", response_model=UserSettingsResponse)
async def get_settings(current_user_id: str = Depends(get_current_user_id)):
    """Get current user's settings (model and system prompt overrides)."""
    try:
        settings = await get_user_settings_for_user(current_user_id)
        if settings is None:
            return UserSettingsResponse(model_override=None, system_prompt_override=None)
        return settings
    except Exception as e:
        logger.error(f"Failed to get user settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get settings")


@router.put("/", response_model=UserSettingsResponse)
async def update_settings(
    update: UserSettingsUpdate,
    current_user_id: str = Depends(get_current_user_id),
):
    """Update current user's settings."""
    try:
        return await upsert_user_settings(current_user_id, update)
    except Exception as e:
        logger.error(f"Failed to update user settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update settings")


# ============================================================================
# API Keys
# ============================================================================

class APIKeyCreateBody(BaseModel):
    """Request body for creating an API key."""
    name: Optional[str] = Field("Personal API Key", description="Display name for the key")


@router.post("/api-keys", response_model=UserAPIKeyCreateResponse)
async def create_api_key(
    body: Optional[APIKeyCreateBody] = Body(default=None),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Create a new API key. The full key is returned ONLY ONCE - save it securely.
    Use the key in the X-API-Key header for programmatic access to the chat API.
    """
    name = (body.name if body else None) or "Personal API Key"
    try:
        return await create_user_api_key(current_user_id, name=name)
    except Exception as e:
        logger.error(f"Failed to create API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.get("/api-keys")
async def list_api_keys(current_user_id: str = Depends(get_current_user_id)):
    """List API keys for the current user (full keys are never returned)."""
    try:
        return {"api_keys": await list_user_api_keys(current_user_id)}
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    """Revoke (delete) an API key."""
    try:
        deleted = await revoke_user_api_key(current_user_id, key_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="API key not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to revoke API key")
