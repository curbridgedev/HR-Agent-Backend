"""
Agent configuration service.

Business logic for agent configuration CRUD operations, versioning, and caching.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from supabase import Client
from app.models.agent_config import (
    AgentConfigCreate,
    AgentConfigUpdate,
    AgentConfigResponse,
    AgentConfigListResponse,
    AgentConfigData,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.db.supabase import get_supabase_client

logger = get_logger(__name__)

# In-memory cache for configs
_config_cache: Dict[str, tuple[AgentConfigResponse, datetime]] = {}
_cache_ttl_seconds = 300  # 5 minutes


def _get_cache_key(name: str, environment: str) -> str:
    """Generate cache key for config."""
    return f"{name}:{environment}"


def _is_cache_valid(cached_at: datetime) -> bool:
    """Check if cache entry is still valid."""
    return (datetime.now() - cached_at).total_seconds() < _cache_ttl_seconds


def _clear_cache(name: Optional[str] = None, environment: Optional[str] = None):
    """Clear cache entries."""
    global _config_cache

    if name is None and environment is None:
        # Clear all cache
        _config_cache.clear()
        logger.debug("Cleared all config cache")
    else:
        # Clear specific entries
        keys_to_remove = []
        for key in _config_cache.keys():
            cached_name, cached_env = key.split(":", 1)
            if (name is None or cached_name == name) and (
                environment is None or cached_env == environment
            ):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del _config_cache[key]
            logger.debug(f"Cleared cache for: {key}")


async def get_active_config(
    name: str = "default_agent_config",
    environment: Optional[str] = None,
    use_cache: bool = True,
    db: Optional[Client] = None,
) -> Optional[AgentConfigResponse]:
    """
    Get the active version of a config by name and environment.

    Args:
        name: Config name (default: 'default_agent_config')
        environment: Target environment (defaults to current environment from settings)
        use_cache: Whether to use cached config
        db: Optional Supabase client

    Returns:
        Active config or None if not found
    """
    # Use current environment if not specified
    if environment is None:
        environment = settings.environment

    # Check cache first
    cache_key = _get_cache_key(name, environment)
    if use_cache and cache_key in _config_cache:
        cached_config, cached_at = _config_cache[cache_key]
        if _is_cache_valid(cached_at):
            logger.debug(f"Config cache hit: {cache_key}")
            return cached_config
        else:
            # Remove stale cache
            del _config_cache[cache_key]

    if db is None:
        db = get_supabase_client()

    try:
        # Use the database function for efficient retrieval
        response = (
            db.rpc(
                "get_active_config",
                {"config_name": name, "config_environment": environment},
            )
            .execute()
        )

        if response.data and len(response.data) > 0:
            config_data = response.data[0]

            # Parse config JSONB as AgentConfigData
            config_dict = config_data["config"]
            config_data["config"] = AgentConfigData(**config_dict)

            config = AgentConfigResponse(**config_data)

            # Cache the result
            _config_cache[cache_key] = (config, datetime.now())

            logger.debug(
                f"Retrieved active config: {name} (env: {environment}, v{config.version})"
            )
            return config

        logger.warning(f"No active config found: {name} (env: {environment})")
        return None

    except Exception as e:
        logger.error(f"Failed to get active config: {e}", exc_info=True)
        raise


async def get_config_by_id(
    config_id: UUID,
    db: Optional[Client] = None,
) -> Optional[AgentConfigResponse]:
    """
    Get a specific config version by ID.

    Args:
        config_id: Config UUID
        db: Optional Supabase client

    Returns:
        Config or None if not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        response = (
            db.table("agent_configs").select("*").eq("id", str(config_id)).execute()
        )

        if response.data and len(response.data) > 0:
            config_data = response.data[0]

            # Parse config JSONB
            config_dict = config_data["config"]
            config_data["config"] = AgentConfigData(**config_dict)

            logger.debug(f"Retrieved config by ID: {config_id}")
            return AgentConfigResponse(**config_data)

        logger.warning(f"Config not found: {config_id}")
        return None

    except Exception as e:
        logger.error(f"Failed to get config by ID: {e}", exc_info=True)
        raise


async def list_configs(
    environment: Optional[str] = None,
    active_only: bool = False,
    page: int = 1,
    page_size: int = 50,
    db: Optional[Client] = None,
) -> AgentConfigListResponse:
    """
    List configs with filtering and pagination.

    Args:
        environment: Filter by environment
        active_only: Only return active configs
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Optional Supabase client

    Returns:
        Paginated list of configs
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Build query
        query = db.table("agent_configs").select("*", count="exact")

        # Apply filters
        if environment:
            query = query.eq("environment", environment)
        if active_only:
            query = query.eq("active", True)

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order("created_at", desc=True).range(
            offset, offset + page_size - 1
        )

        response = query.execute()

        # Parse configs
        configs = []
        for item in response.data:
            config_dict = item["config"]
            item["config"] = AgentConfigData(**config_dict)
            configs.append(AgentConfigResponse(**item))

        total = response.count if response.count is not None else len(configs)

        logger.info(
            f"Listed configs: env={environment}, active_only={active_only}, "
            f"page={page}, total={total}"
        )

        return AgentConfigListResponse(
            configs=configs,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error(f"Failed to list configs: {e}", exc_info=True)
        raise


async def get_config_history(
    name: str,
    environment: str,
    db: Optional[Client] = None,
) -> List[AgentConfigResponse]:
    """
    Get all versions of a config ordered by version number.

    Args:
        name: Config name
        environment: Environment
        db: Optional Supabase client

    Returns:
        List of all config versions
    """
    if db is None:
        db = get_supabase_client()

    try:
        response = (
            db.table("agent_configs")
            .select("*")
            .eq("name", name)
            .eq("environment", environment)
            .order("version", desc=True)
            .execute()
        )

        configs = []
        for item in response.data:
            config_dict = item["config"]
            item["config"] = AgentConfigData(**config_dict)
            configs.append(AgentConfigResponse(**item))

        logger.info(
            f"Retrieved {len(configs)} versions for config: {name} ({environment})"
        )

        return configs

    except Exception as e:
        logger.error(f"Failed to get config history: {e}", exc_info=True)
        raise


async def create_config_version(
    request: AgentConfigCreate,
    db: Optional[Client] = None,
) -> AgentConfigResponse:
    """
    Create a new version of a config.

    Uses the database function to auto-increment version number.

    Args:
        request: Config creation request
        db: Optional Supabase client

    Returns:
        Newly created config version
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Convert config to dict for JSONB storage
        config_dict = request.config.model_dump()

        # Use database function for version management
        response = (
            db.rpc(
                "create_config_version",
                {
                    "config_name": request.name,
                    "config_environment": request.environment,
                    "config_data": config_dict,
                    "description_input": request.description,
                    "tags_input": request.tags,
                    "created_by_input": request.created_by,
                    "notes_input": request.notes,
                    "activate_immediately": request.activate_immediately,
                },
            )
            .execute()
        )

        # Get the newly created config
        new_config_id = response.data
        config = await get_config_by_id(UUID(new_config_id), db)

        if config is None:
            raise Exception("Failed to retrieve newly created config")

        # Clear cache for this name+environment
        _clear_cache(request.name, request.environment)

        logger.info(
            f"Created new config version: {request.name} ({request.environment}) "
            f"v{config.version} (active: {config.active})"
        )

        return config

    except Exception as e:
        logger.error(f"Failed to create config version: {e}", exc_info=True)
        raise


async def activate_config(
    config_id: UUID,
    db: Optional[Client] = None,
) -> AgentConfigResponse:
    """
    Activate a specific config version.

    Deactivates all other versions with the same name and environment.

    Args:
        config_id: ID of config version to activate
        db: Optional Supabase client

    Returns:
        Activated config
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Use database function to handle activation logic
        db.rpc("activate_config_version", {"config_id_to_activate": str(config_id)}).execute()

        # Get the activated config
        config = await get_config_by_id(config_id, db)

        if config is None:
            raise Exception("Failed to retrieve activated config")

        # Clear cache for this name+environment
        _clear_cache(config.name, config.environment)

        logger.info(
            f"Activated config: {config.name} ({config.environment}) v{config.version}"
        )

        return config

    except Exception as e:
        logger.error(f"Failed to activate config: {e}", exc_info=True)
        raise


async def update_config(
    config_id: UUID,
    request: AgentConfigUpdate,
    db: Optional[Client] = None,
) -> AgentConfigResponse:
    """
    Update a config's metadata or configuration data.

    Note: For config data changes, consider creating a new version instead.

    Args:
        config_id: Config UUID
        request: Update request
        db: Optional Supabase client

    Returns:
        Updated config
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Build update payload
        update_data: Dict[str, Any] = {}

        if request.config is not None:
            update_data["config"] = request.config.model_dump()
        if request.description is not None:
            update_data["description"] = request.description
        if request.tags is not None:
            update_data["tags"] = request.tags
        if request.notes is not None:
            update_data["notes"] = request.notes

        if not update_data:
            # Nothing to update
            return await get_config_by_id(config_id, db)

        # Perform update
        response = (
            db.table("agent_configs")
            .update(update_data)
            .eq("id", str(config_id))
            .execute()
        )

        if not response.data or len(response.data) == 0:
            raise Exception("Config not found or update failed")

        config_data = response.data[0]
        config_dict = config_data["config"]
        config_data["config"] = AgentConfigData(**config_dict)

        updated_config = AgentConfigResponse(**config_data)

        # Clear cache
        _clear_cache(updated_config.name, updated_config.environment)

        logger.info(
            f"Updated config: {updated_config.name} ({updated_config.environment}) "
            f"v{updated_config.version}"
        )

        return updated_config

    except Exception as e:
        logger.error(f"Failed to update config: {e}", exc_info=True)
        raise


async def increment_config_usage(
    config_id: UUID,
    response_time_ms: float,
    confidence_score: Optional[float] = None,
    escalated: bool = False,
    success: bool = True,
    db: Optional[Client] = None,
) -> None:
    """
    Increment usage statistics for a config.

    Called after each agent execution using this config.

    Args:
        config_id: Config UUID
        response_time_ms: Response time in milliseconds
        confidence_score: Optional confidence score
        escalated: Whether the response was escalated
        success: Whether the request was successful
        db: Optional Supabase client
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Get current config
        config = await get_config_by_id(config_id, db)
        if config is None:
            logger.warning(f"Config not found for usage tracking: {config_id}")
            return

        # Calculate new statistics
        new_usage_count = config.usage_count + 1

        update_data: Dict[str, Any] = {"usage_count": new_usage_count}

        # Update average response time
        if config.avg_response_time_ms is None:
            new_avg_response_time = response_time_ms
        else:
            total = config.avg_response_time_ms * config.usage_count + response_time_ms
            new_avg_response_time = total / new_usage_count
        update_data["avg_response_time_ms"] = new_avg_response_time

        # Update average confidence if provided
        if confidence_score is not None:
            if config.avg_confidence is None:
                new_avg_confidence = confidence_score
            else:
                total = config.avg_confidence * config.usage_count + confidence_score
                new_avg_confidence = total / new_usage_count
            update_data["avg_confidence"] = new_avg_confidence

        # Update escalation rate
        if config.escalation_rate is None:
            escalation_rate = 1.0 if escalated else 0.0
        else:
            total_escalations = config.escalation_rate * config.usage_count + (
                1.0 if escalated else 0.0
            )
            escalation_rate = total_escalations / new_usage_count
        update_data["escalation_rate"] = escalation_rate

        # Update success rate
        if config.success_rate is None:
            success_rate = 1.0 if success else 0.0
        else:
            total_successes = config.success_rate * config.usage_count + (
                1.0 if success else 0.0
            )
            success_rate = total_successes / new_usage_count
        update_data["success_rate"] = success_rate

        # Update database
        db.table("agent_configs").update(update_data).eq("id", str(config_id)).execute()

        logger.debug(
            f"Updated config usage: {config.name} (usage: {new_usage_count}, "
            f"avg_time: {new_avg_response_time:.0f}ms, "
            f"avg_confidence: {update_data.get('avg_confidence', 0):.2f}, "
            f"escalation_rate: {escalation_rate:.2%}, "
            f"success_rate: {success_rate:.2%})"
        )

    except Exception as e:
        logger.error(f"Failed to increment config usage: {e}", exc_info=True)
        # Don't raise - this is a non-critical operation


def clear_config_cache():
    """Clear all config cache. Useful for testing or manual cache invalidation."""
    _clear_cache()
