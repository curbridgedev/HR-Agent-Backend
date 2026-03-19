"""User settings service - model and system prompt overrides."""

from datetime import datetime
from typing import Optional
from supabase import Client

from app.core.logging import get_logger
from app.db.supabase import get_supabase_client
from app.models.user_settings import UserSettingsResponse, UserSettingsUpdate

logger = get_logger(__name__)


async def get_user_settings_for_user(user_id: str, db: Optional[Client] = None) -> Optional[UserSettingsResponse]:
    """
    Get user settings for a user. Returns None if no settings exist.
    """
    if db is None:
        db = get_supabase_client()

    try:
        result = (
            db.table("user_settings")
            .select("model_override, system_prompt_override")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if result.data:
            return UserSettingsResponse(
                model_override=result.data.get("model_override"),
                system_prompt_override=result.data.get("system_prompt_override"),
            )
        return None
    except Exception as e:
        logger.debug(f"No user settings for {user_id}: {e}")
        return None


async def upsert_user_settings(
    user_id: str,
    update: UserSettingsUpdate,
    db: Optional[Client] = None,
) -> UserSettingsResponse:
    """
    Create or update user settings.
    """
    if db is None:
        db = get_supabase_client()

    try:
        existing = await get_user_settings_for_user(user_id, db)
        data: dict = {
            "user_id": user_id,
            "updated_at": datetime.utcnow().isoformat(),
            "model_override": update.model_override if update.model_override is not None else (existing.model_override if existing else None),
            "system_prompt_override": update.system_prompt_override if update.system_prompt_override is not None else (existing.system_prompt_override if existing else None),
        }

        result = (
            db.table("user_settings")
            .upsert(data, on_conflict="user_id")
            .execute()
        )

        row = result.data[0] if result.data else {}
        return UserSettingsResponse(
            model_override=row.get("model_override"),
            system_prompt_override=row.get("system_prompt_override"),
        )
    except Exception as e:
        logger.error(f"Failed to upsert user settings: {e}", exc_info=True)
        raise
