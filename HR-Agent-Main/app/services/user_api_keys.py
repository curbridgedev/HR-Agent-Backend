"""User API keys service - personal API keys for programmatic access."""

import hashlib
import secrets
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from supabase import Client

from app.core.logging import get_logger
from app.db.supabase import get_supabase_client
from app.models.user_settings import (
    UserAPIKeyCreateResponse,
    UserAPIKeyListItem,
)

logger = get_logger(__name__)


def _generate_user_api_key() -> tuple[str, str, str]:
    """Generate API key. Returns (full_key, key_prefix, key_hash)."""
    random_suffix = secrets.token_hex(16)
    full_key = f"hr_{random_suffix}"
    key_prefix = full_key[:20]
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_prefix, key_hash


async def create_user_api_key(
    user_id: str,
    name: str = "Personal API Key",
    db: Optional[Client] = None,
) -> UserAPIKeyCreateResponse:
    """
    Create a new API key for the user. Full key is returned only once.
    """
    if db is None:
        db = get_supabase_client()

    full_key, key_prefix, key_hash = _generate_user_api_key()

    try:
        result = (
            db.table("user_api_keys")
            .insert({
                "user_id": user_id,
                "key_hash": key_hash,
                "key_prefix": key_prefix,
                "name": name,
                "enabled": True,
            })
            .execute()
        )
        row = result.data[0]
        return UserAPIKeyCreateResponse(
            id=str(row["id"]),
            key=full_key,
            key_prefix=key_prefix,
            name=row.get("name", name),
            created_at=row["created_at"],
        )
    except Exception as e:
        logger.error(f"Failed to create user API key: {e}", exc_info=True)
        raise


async def list_user_api_keys(
    user_id: str,
    db: Optional[Client] = None,
) -> List[UserAPIKeyListItem]:
    """List API keys for user (no full keys)."""
    if db is None:
        db = get_supabase_client()

    try:
        result = (
            db.table("user_api_keys")
            .select("id, key_prefix, name, last_used_at, created_at, enabled")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [
            UserAPIKeyListItem(
                id=str(r["id"]),
                key_prefix=r["key_prefix"],
                name=r.get("name", "API Key"),
                last_used_at=r.get("last_used_at"),
                created_at=r["created_at"],
                enabled=r.get("enabled", True),
            )
            for r in (result.data or [])
        ]
    except Exception as e:
        logger.error(f"Failed to list user API keys: {e}", exc_info=True)
        raise


async def revoke_user_api_key(
    user_id: str,
    key_id: str,
    db: Optional[Client] = None,
) -> bool:
    """Revoke (delete) an API key. Returns True if deleted."""
    if db is None:
        db = get_supabase_client()

    try:
        result = (
            db.table("user_api_keys")
            .delete()
            .eq("id", key_id)
            .eq("user_id", user_id)
            .execute()
        )
        return len(result.data or []) > 0
    except Exception as e:
        logger.error(f"Failed to revoke user API key: {e}", exc_info=True)
        raise


async def get_user_id_from_api_key(api_key: str, db: Optional[Client] = None) -> Optional[str]:
    """
    Resolve API key to user_id. Returns None if invalid.
    Updates last_used_at on success.
    """
    if db is None:
        db = get_supabase_client()

    if not api_key or not api_key.startswith("hr_"):
        return None

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    try:
        result = (
            db.table("user_api_keys")
            .select("id, user_id")
            .eq("key_hash", key_hash)
            .eq("enabled", True)
            .execute()
        )
        if result.data:
            row = result.data[0]
            user_id = row["user_id"]
            # Update last_used_at (fire and forget)
            try:
                db.table("user_api_keys").update({
                    "last_used_at": datetime.utcnow().isoformat(),
                }).eq("id", row["id"]).execute()
            except Exception:
                pass
            return user_id
        return None
    except Exception as e:
        logger.warning(f"API key lookup failed: {e}")
        return None
