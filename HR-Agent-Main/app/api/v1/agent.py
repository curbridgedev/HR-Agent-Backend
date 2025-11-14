"""
Agent configuration API endpoints for admin dashboard.

Provides endpoints for:
- Viewing and updating agent configuration (model, temperature, confidence threshold)
- Managing system prompt versions (CRUD operations)
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.core.logging import get_logger
from app.models.admin import (
    SystemPromptCreateRequest,
    SystemPromptListResponse,
    SystemPromptResponse,
)
from app.models.agent_config import (
    AgentConfigResponse,
    AgentConfigUpdate,
)
from app.services.admin import (
    activate_system_prompt,
    create_system_prompt,
    delete_system_prompt,
    list_system_prompts,
)
from app.services.agent_config import (
    get_active_config,
    update_config,
)

logger = get_logger(__name__)

router = APIRouter()


# ============================================================================
# Agent Configuration Endpoints
# ============================================================================

@router.get("/config", response_model=AgentConfigResponse)
async def get_agent_config(
    environment: str = Query(
        None,
        description="Target environment (all, development, uat, production). Defaults to current environment from settings."
    )
):
    """
    Get the currently active agent configuration.

    Returns full agent config including confidence_calculation settings,
    model settings, thresholds, and all configuration data.

    Args:
        environment: Target environment (defaults to current environment from settings)

    Returns:
        Active agent configuration with full details

    Example:
        GET /api/v1/agent/config
        GET /api/v1/agent/config?environment=production
    """
    try:
        logger.info(f"Fetching active agent config for environment: {environment or 'current'}")

        config = await get_active_config(environment=environment)

        if not config:
            env_name = environment or "current"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active agent config found for environment: {env_name}"
            )

        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch agent config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch agent config: {str(e)}"
        )


@router.put("/config", response_model=AgentConfigResponse)
async def update_agent_config_endpoint(
    update_request: AgentConfigUpdate,
    environment: str = Query(
        None,
        description="Target environment (all, development, uat, production). Defaults to current environment from settings."
    )
):
    """
    Update the active agent configuration.

    Supports updating any part of the configuration including:
    - config.confidence_calculation (method, hybrid_settings, llm_settings, formula_weights)
    - config.model_settings (provider, model, temperature)
    - config.confidence_thresholds (escalation, high, medium, low)
    - description, tags, notes

    All fields are optional - only provided fields will be updated.

    Args:
        update_request: Update request with optional fields
        environment: Target environment (defaults to current environment from settings)

    Returns:
        Updated agent configuration

    Example:
        PUT /api/v1/agent/config
        {
          "config": {
            "confidence_calculation": {
              "method": "hybrid",
              "hybrid_settings": {
                "formula_weight": 0.60,
                "llm_weight": 0.40
              }
            }
          }
        }
    """
    try:
        logger.info(f"Updating agent config for environment: {environment or 'current'}")

        # Get current active config
        current_config = await get_active_config(environment=environment)
        if not current_config:
            env_name = environment or "current"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active agent config found for environment: {env_name}"
            )

        # Update the config
        updated_config = await update_config(
            config_id=current_config.id,
            request=update_request
        )

        logger.info(f"Successfully updated agent config: {updated_config.id}")
        return updated_config

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid update request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update agent config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent config: {str(e)}"
        )


# ============================================================================
# System Prompt Endpoints
# ============================================================================

@router.get("/prompts", response_model=SystemPromptListResponse)
async def get_system_prompts(
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip")
):
    """
    List all system prompt versions with pagination.

    Returns all versions of the main system prompt, ordered by version (newest first).

    Args:
        limit: Maximum items per page (default: 50, max: 100)
        offset: Number of items to skip for pagination (default: 0)

    Returns:
        List of system prompts with pagination info

    Example:
        GET /api/v1/agent/prompts
        GET /api/v1/agent/prompts?limit=20&offset=40
    """
    try:
        logger.info(f"Fetching system prompts (limit={limit}, offset={offset})")

        prompts_response = await list_system_prompts(limit=limit, offset=offset)

        logger.info(f"Retrieved {len(prompts_response.prompts)} prompts")
        return prompts_response

    except Exception as e:
        logger.error(f"Failed to list system prompts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list system prompts: {str(e)}"
        )


@router.post(
    "/prompts",
    response_model=SystemPromptResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_system_prompt_endpoint(
    request: SystemPromptCreateRequest,
    # TODO: Extract created_by from Supabase JWT token when auth is implemented
    # created_by: str = Depends(get_current_admin_user)
):
    """
    Create a new system prompt version.

    Auto-increments version number and sets active=False by default.
    Must use separate activate endpoint to make this prompt active.

    Args:
        request: Prompt creation request with content and optional notes

    Returns:
        Created system prompt (inactive by default)

    Example:
        POST /api/v1/agent/prompts
        {
          "content": "You are a helpful AI assistant...",
          "performance_notes": "Testing friendlier tone"
        }
    """
    try:
        logger.info("Creating new system prompt version")

        # TODO: Extract created_by from JWT token when auth is implemented
        created_by = None

        new_prompt = await create_system_prompt(
            request=request,
            created_by=created_by
        )

        logger.info(f"Created system prompt: {new_prompt.id} (version {new_prompt.version})")
        return new_prompt

    except ValueError as e:
        logger.warning(f"Invalid prompt creation request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create system prompt: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create system prompt: {str(e)}"
        )


@router.patch("/prompts/{prompt_id}/activate", response_model=SystemPromptResponse)
async def activate_system_prompt_endpoint(
    prompt_id: UUID
):
    """
    Activate a specific system prompt version.

    Deactivates all other prompts and activates the specified version.
    The activated prompt will be used by the agent immediately.

    Args:
        prompt_id: UUID of prompt version to activate

    Returns:
        Activated system prompt

    Example:
        PATCH /api/v1/agent/prompts/550e8400-e29b-41d4-a716-446655440000/activate
    """
    try:
        logger.info(f"Activating system prompt: {prompt_id}")

        activated_prompt = await activate_system_prompt(prompt_id=prompt_id)

        logger.info(f"Successfully activated prompt: {prompt_id} (version {activated_prompt.version})")
        return activated_prompt

    except ValueError as e:
        logger.warning(f"Failed to activate prompt: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to activate system prompt: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate system prompt: {str(e)}"
        )


@router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_prompt_endpoint(
    prompt_id: UUID
):
    """
    Delete a system prompt version.

    IMPORTANT: Cannot delete the currently active prompt.
    Activate another prompt first before deleting.

    Args:
        prompt_id: UUID of prompt version to delete

    Returns:
        No content (204) on success

    Example:
        DELETE /api/v1/agent/prompts/550e8400-e29b-41d4-a716-446655440000
    """
    try:
        logger.info(f"Deleting system prompt: {prompt_id}")

        await delete_system_prompt(prompt_id=prompt_id)

        logger.info(f"Successfully deleted prompt: {prompt_id}")
        # FastAPI automatically returns 204 No Content

    except ValueError as e:
        # Prompt not found or is active
        error_msg = str(e)
        if "Cannot delete active prompt" in error_msg:
            logger.warning(f"Attempted to delete active prompt: {prompt_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        else:
            logger.warning(f"Prompt not found: {prompt_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
    except Exception as e:
        logger.error(f"Failed to delete system prompt: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete system prompt: {str(e)}"
        )
