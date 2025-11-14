"""
Admin dashboard service layer.

Bridges the gap between existing database schema and frontend requirements.
Maps complex JSONB configs to simplified flat structures expected by frontend.
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from supabase import Client

from app.core.logging import get_logger
from app.db.supabase import get_supabase_client
from app.models.admin import (
    AgentConfigResponse,
    AgentConfigUpdateRequest,
    SystemPromptSummary,
    SystemPromptResponse,
    SystemPromptListResponse,
    SystemPromptCreateRequest,
    PaginationInfo,
)

logger = get_logger(__name__)


# ============================================================================
# Agent Configuration Service Functions
# ============================================================================

async def get_active_agent_config(
    environment: str = "all",
    db: Optional[Client] = None,
) -> Optional[AgentConfigResponse]:
    """
    Get the currently active agent configuration.

    Maps from agent_configs table (with JSONB config) to simplified flat structure.

    Args:
        environment: Target environment ('all', 'development', 'uat', 'production')
        db: Optional Supabase client

    Returns:
        Simplified agent config response or None if not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Get active agent config using database function
        config_response = db.rpc(
            "get_active_config",
            {
                "config_name": "default_agent_config",
                "config_environment": environment
            }
        ).execute()

        if not config_response.data or len(config_response.data) == 0:
            logger.warning(f"No active agent config found for environment: {environment}")
            return None

        config_data = config_response.data[0]
        config_json = config_data["config"]

        # Get active system prompt
        prompt_response = db.table("prompts").select("*").eq(
            "name", "main_system_prompt"
        ).eq("prompt_type", "system").eq("active", True).execute()

        if not prompt_response.data or len(prompt_response.data) == 0:
            logger.error("No active system prompt found - this should not happen!")
            # Fallback: create a dummy prompt response
            active_prompt = SystemPromptSummary(
                id=UUID("00000000-0000-0000-0000-000000000000"),
                version=0,
                content="No active prompt configured",
                created_at=datetime.now()
            )
        else:
            prompt_data = prompt_response.data[0]
            active_prompt = SystemPromptSummary(
                id=UUID(prompt_data["id"]),
                version=prompt_data["version"],
                content=prompt_data["content"],
                created_at=datetime.fromisoformat(prompt_data["created_at"].replace("Z", "+00:00"))
            )

        # Map complex JSONB to flat structure
        model_settings = config_json.get("model_settings", {})
        confidence_thresholds = config_json.get("confidence_thresholds", {})

        return AgentConfigResponse(
            id=UUID(config_data["id"]),
            model_provider=model_settings.get("provider", "openai"),
            model_name=model_settings.get("model", "gpt-4"),
            temperature=model_settings.get("temperature", 0.7),
            confidence_threshold=confidence_thresholds.get("escalation", 0.95),
            active_system_prompt=active_prompt,
            created_at=datetime.fromisoformat(config_data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(config_data["updated_at"].replace("Z", "+00:00"))
        )

    except Exception as e:
        logger.error(f"Failed to get active agent config: {e}", exc_info=True)
        raise


async def update_agent_config(
    update_request: AgentConfigUpdateRequest,
    environment: str = "all",
    db: Optional[Client] = None,
) -> AgentConfigResponse:
    """
    Update the active agent configuration.

    Updates the JSONB config with provided values and returns simplified response.

    Args:
        update_request: Update request with optional fields
        environment: Target environment
        db: Optional Supabase client

    Returns:
        Updated agent config response

    Raises:
        ValueError: If no active config found
    """
    if db is None:
        db = get_supabase_client()

    try:
        # First, get the current active config
        active_config = await get_active_agent_config(environment=environment, db=db)
        if not active_config:
            raise ValueError(f"No active agent config found for environment: {environment}")

        # Get the full config from database to update JSONB
        config_response = db.table("agent_configs").select("*").eq(
            "id", str(active_config.id)
        ).execute()

        if not config_response.data:
            raise ValueError(f"Config not found: {active_config.id}")

        current_config_data = config_response.data[0]
        config_json = current_config_data["config"]

        # Update only provided fields in JSONB
        if update_request.model_provider is not None:
            if "model_settings" not in config_json:
                config_json["model_settings"] = {}
            config_json["model_settings"]["provider"] = update_request.model_provider

        if update_request.model_name is not None:
            if "model_settings" not in config_json:
                config_json["model_settings"] = {}
            config_json["model_settings"]["model"] = update_request.model_name

        if update_request.temperature is not None:
            if "model_settings" not in config_json:
                config_json["model_settings"] = {}
            config_json["model_settings"]["temperature"] = update_request.temperature

        if update_request.confidence_threshold is not None:
            if "confidence_thresholds" not in config_json:
                config_json["confidence_thresholds"] = {}
            config_json["confidence_thresholds"]["escalation"] = update_request.confidence_threshold

        # Update the config in database
        update_response = db.table("agent_configs").update({
            "config": config_json,
            "updated_at": datetime.now().isoformat()
        }).eq("id", str(active_config.id)).execute()

        if not update_response.data:
            raise ValueError("Failed to update config")

        logger.info(f"Updated agent config: {active_config.id}")

        # Return updated config
        return await get_active_agent_config(environment=environment, db=db)

    except Exception as e:
        logger.error(f"Failed to update agent config: {e}", exc_info=True)
        raise


# ============================================================================
# System Prompt Service Functions
# ============================================================================

async def list_system_prompts(
    limit: int = 50,
    offset: int = 0,
    db: Optional[Client] = None,
) -> SystemPromptListResponse:
    """
    List all system prompt versions with pagination.

    Args:
        limit: Max results per page
        offset: Number of results to skip
        db: Optional Supabase client

    Returns:
        List of system prompts with pagination info
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Query system prompts (main_system_prompt, type=system)
        query = db.table("prompts").select("*", count="exact").eq(
            "name", "main_system_prompt"
        ).eq("prompt_type", "system").order("version", desc=True)

        # Apply pagination
        response = query.range(offset, offset + limit - 1).execute()

        prompts = [
            SystemPromptResponse(
                id=UUID(prompt["id"]),
                version=prompt["version"],
                content=prompt["content"],
                created_by=prompt.get("created_by"),
                created_at=datetime.fromisoformat(prompt["created_at"].replace("Z", "+00:00")),
                is_active=prompt["active"],
                performance_notes=prompt.get("notes")
            )
            for prompt in response.data
        ]

        total_count = response.count if response.count is not None else len(prompts)
        has_more = (offset + len(prompts)) < total_count

        return SystemPromptListResponse(
            prompts=prompts,
            total_count=total_count,
            pagination=PaginationInfo(
                limit=limit,
                offset=offset,
                has_more=has_more
            )
        )

    except Exception as e:
        logger.error(f"Failed to list system prompts: {e}", exc_info=True)
        raise


async def create_system_prompt(
    request: SystemPromptCreateRequest,
    created_by: Optional[str] = None,
    db: Optional[Client] = None,
) -> SystemPromptResponse:
    """
    Create a new system prompt version.

    Auto-increments version number and sets active=False by default.

    Args:
        request: Prompt creation request
        created_by: Optional creator ID (Supabase user ID)
        db: Optional Supabase client

    Returns:
        Created system prompt response
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Use database function to create new version
        response = db.rpc(
            "create_prompt_version",
            {
                "prompt_name": "main_system_prompt",
                "prompt_type_input": "system",
                "content_input": request.content,
                "tags_input": ["admin-created"],
                "metadata_input": {},
                "created_by_input": created_by,
                "notes_input": request.performance_notes,
                "activate_immediately": False
            }
        ).execute()

        if not response.data:
            raise ValueError("Failed to create prompt version")

        new_prompt_id = UUID(response.data)
        logger.info(f"Created new system prompt version: {new_prompt_id}")

        # Retrieve and return the created prompt
        prompt_response = db.table("prompts").select("*").eq("id", str(new_prompt_id)).execute()

        if not prompt_response.data:
            raise ValueError("Failed to retrieve created prompt")

        prompt_data = prompt_response.data[0]
        return SystemPromptResponse(
            id=UUID(prompt_data["id"]),
            version=prompt_data["version"],
            content=prompt_data["content"],
            created_by=prompt_data.get("created_by"),
            created_at=datetime.fromisoformat(prompt_data["created_at"].replace("Z", "+00:00")),
            is_active=prompt_data["active"],
            performance_notes=prompt_data.get("notes")
        )

    except Exception as e:
        logger.error(f"Failed to create system prompt: {e}", exc_info=True)
        raise


async def activate_system_prompt(
    prompt_id: UUID,
    db: Optional[Client] = None,
) -> SystemPromptResponse:
    """
    Activate a specific system prompt version.

    Deactivates all other prompts with same name/type and activates this one.

    Args:
        prompt_id: UUID of prompt to activate
        db: Optional Supabase client

    Returns:
        Activated system prompt response

    Raises:
        ValueError: If prompt not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Use database function to activate
        db.rpc("activate_prompt_version", {"prompt_id_to_activate": str(prompt_id)}).execute()

        logger.info(f"Activated system prompt: {prompt_id}")

        # Retrieve and return the activated prompt
        prompt_response = db.table("prompts").select("*").eq("id", str(prompt_id)).execute()

        if not prompt_response.data:
            raise ValueError(f"Prompt not found: {prompt_id}")

        prompt_data = prompt_response.data[0]
        return SystemPromptResponse(
            id=UUID(prompt_data["id"]),
            version=prompt_data["version"],
            content=prompt_data["content"],
            created_by=prompt_data.get("created_by"),
            created_at=datetime.fromisoformat(prompt_data["created_at"].replace("Z", "+00:00")),
            is_active=prompt_data["active"],
            performance_notes=prompt_data.get("notes")
        )

    except Exception as e:
        logger.error(f"Failed to activate system prompt: {e}", exc_info=True)
        raise


async def delete_system_prompt(
    prompt_id: UUID,
    db: Optional[Client] = None,
) -> None:
    """
    Delete a system prompt version.

    IMPORTANT: Cannot delete active prompt - will raise ValueError.

    Args:
        prompt_id: UUID of prompt to delete
        db: Optional Supabase client

    Raises:
        ValueError: If prompt is active or not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Check if prompt exists and is not active
        prompt_response = db.table("prompts").select("*").eq("id", str(prompt_id)).execute()

        if not prompt_response.data:
            raise ValueError(f"Prompt not found: {prompt_id}")

        prompt_data = prompt_response.data[0]
        if prompt_data["active"]:
            raise ValueError("Cannot delete active prompt - activate another prompt first")

        # Delete the prompt
        db.table("prompts").delete().eq("id", str(prompt_id)).execute()

        logger.info(f"Deleted system prompt: {prompt_id}")

    except Exception as e:
        logger.error(f"Failed to delete system prompt: {e}", exc_info=True)
        raise
