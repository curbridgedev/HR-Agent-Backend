"""
Prompt management service.

Business logic for system prompt CRUD operations and versioning.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from supabase import Client
from app.models.prompts import (
    PromptCreate,
    PromptUpdate,
    PromptResponse,
    PromptListResponse,
)
from app.core.logging import get_logger
from app.db.supabase import get_supabase_client

logger = get_logger(__name__)


async def get_active_prompt(
    name: str,
    prompt_type: Optional[str] = None,
    db: Optional[Client] = None,
) -> Optional[PromptResponse]:
    """
    Get the active version of a prompt by name and type.

    Args:
        name: Prompt name (e.g., 'main_system_prompt')
        prompt_type: Optional prompt type filter
        db: Optional Supabase client (creates new if not provided)

    Returns:
        Active prompt or None if not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Use the database function for efficient retrieval
        response = (
            db.rpc(
                "get_active_prompt",
                {"prompt_name": name, "prompt_type_filter": prompt_type},
            )
            .execute()
        )

        if response.data and len(response.data) > 0:
            prompt_data = response.data[0]
            logger.debug(f"Retrieved active prompt: {name} (type: {prompt_type})")
            return PromptResponse(**prompt_data)

        logger.warning(f"No active prompt found: {name} (type: {prompt_type})")
        return None

    except Exception as e:
        logger.error(f"Failed to get active prompt: {e}", exc_info=True)
        raise


async def get_prompt_by_id(
    prompt_id: UUID,
    db: Optional[Client] = None,
) -> Optional[PromptResponse]:
    """
    Get a specific prompt version by ID.

    Args:
        prompt_id: Prompt UUID
        db: Optional Supabase client

    Returns:
        Prompt or None if not found
    """
    if db is None:
        db = get_supabase_client()

    try:
        response = db.table("prompts").select("*").eq("id", str(prompt_id)).execute()

        if response.data and len(response.data) > 0:
            logger.debug(f"Retrieved prompt by ID: {prompt_id}")
            return PromptResponse(**response.data[0])

        logger.warning(f"Prompt not found: {prompt_id}")
        return None

    except Exception as e:
        logger.error(f"Failed to get prompt by ID: {e}", exc_info=True)
        raise


async def list_prompts(
    prompt_type: Optional[str] = None,
    active_only: bool = False,
    page: int = 1,
    page_size: int = 50,
    db: Optional[Client] = None,
) -> PromptListResponse:
    """
    List prompts with filtering and pagination.

    Args:
        prompt_type: Filter by prompt type
        active_only: Only return active prompts
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Optional Supabase client

    Returns:
        Paginated list of prompts
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Build query
        query = db.table("prompts").select("*", count="exact")

        # Apply filters
        if prompt_type:
            query = query.eq("prompt_type", prompt_type)
        if active_only:
            query = query.eq("active", True)

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order("created_at", desc=True).range(offset, offset + page_size - 1)

        response = query.execute()

        prompts = [PromptResponse(**item) for item in response.data]
        total = response.count if response.count is not None else len(prompts)

        logger.info(
            f"Listed prompts: type={prompt_type}, active_only={active_only}, "
            f"page={page}, total={total}"
        )

        return PromptListResponse(
            prompts=prompts,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error(f"Failed to list prompts: {e}", exc_info=True)
        raise


async def get_prompt_history(
    name: str,
    prompt_type: str,
    db: Optional[Client] = None,
) -> List[PromptResponse]:
    """
    Get all versions of a prompt ordered by version number.

    Args:
        name: Prompt name
        prompt_type: Prompt type
        db: Optional Supabase client

    Returns:
        List of all prompt versions
    """
    if db is None:
        db = get_supabase_client()

    try:
        response = (
            db.table("prompts")
            .select("*")
            .eq("name", name)
            .eq("prompt_type", prompt_type)
            .order("version", desc=True)
            .execute()
        )

        prompts = [PromptResponse(**item) for item in response.data]
        logger.info(f"Retrieved {len(prompts)} versions for prompt: {name} ({prompt_type})")

        return prompts

    except Exception as e:
        logger.error(f"Failed to get prompt history: {e}", exc_info=True)
        raise


async def create_prompt_version(
    request: PromptCreate,
    db: Optional[Client] = None,
) -> PromptResponse:
    """
    Create a new version of a prompt.

    Uses the database function to auto-increment version number.

    Args:
        request: Prompt creation request
        db: Optional Supabase client

    Returns:
        Newly created prompt version
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Use database function for version management
        response = (
            db.rpc(
                "create_prompt_version",
                {
                    "prompt_name": request.name,
                    "prompt_type_input": request.prompt_type,
                    "content_input": request.content,
                    "tags_input": request.tags,
                    "metadata_input": request.metadata,
                    "created_by_input": request.created_by,
                    "notes_input": request.notes,
                    "activate_immediately": request.activate_immediately,
                },
            )
            .execute()
        )

        # Get the newly created prompt
        new_prompt_id = response.data
        prompt = await get_prompt_by_id(UUID(new_prompt_id), db)

        if prompt is None:
            raise Exception("Failed to retrieve newly created prompt")

        logger.info(
            f"Created new prompt version: {request.name} v{prompt.version} "
            f"(active: {prompt.active})"
        )

        return prompt

    except Exception as e:
        logger.error(f"Failed to create prompt version: {e}", exc_info=True)
        raise


async def activate_prompt(
    prompt_id: UUID,
    db: Optional[Client] = None,
) -> PromptResponse:
    """
    Activate a specific prompt version.

    Deactivates all other versions with the same name and type.

    Args:
        prompt_id: ID of prompt version to activate
        db: Optional Supabase client

    Returns:
        Activated prompt
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Use database function to handle activation logic
        db.rpc("activate_prompt_version", {"prompt_id_to_activate": str(prompt_id)}).execute()

        # Get the activated prompt
        prompt = await get_prompt_by_id(prompt_id, db)

        if prompt is None:
            raise Exception("Failed to retrieve activated prompt")

        logger.info(f"Activated prompt: {prompt.name} v{prompt.version}")

        return prompt

    except Exception as e:
        logger.error(f"Failed to activate prompt: {e}", exc_info=True)
        raise


async def update_prompt(
    prompt_id: UUID,
    request: PromptUpdate,
    db: Optional[Client] = None,
) -> PromptResponse:
    """
    Update a prompt's metadata or content.

    Note: For content changes, consider creating a new version instead.

    Args:
        prompt_id: Prompt UUID
        request: Update request
        db: Optional Supabase client

    Returns:
        Updated prompt
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Build update payload
        update_data: Dict[str, Any] = {}
        if request.content is not None:
            update_data["content"] = request.content
        if request.tags is not None:
            update_data["tags"] = request.tags
        if request.metadata is not None:
            update_data["metadata"] = request.metadata
        if request.notes is not None:
            update_data["notes"] = request.notes

        if not update_data:
            # Nothing to update
            return await get_prompt_by_id(prompt_id, db)

        # Perform update
        response = (
            db.table("prompts")
            .update(update_data)
            .eq("id", str(prompt_id))
            .execute()
        )

        if not response.data or len(response.data) == 0:
            raise Exception("Prompt not found or update failed")

        updated_prompt = PromptResponse(**response.data[0])
        logger.info(f"Updated prompt: {updated_prompt.name} v{updated_prompt.version}")

        return updated_prompt

    except Exception as e:
        logger.error(f"Failed to update prompt: {e}", exc_info=True)
        raise


async def increment_prompt_usage(
    prompt_id: UUID,
    confidence_score: Optional[float] = None,
    escalated: bool = False,
    db: Optional[Client] = None,
) -> None:
    """
    Increment usage statistics for a prompt.

    Called after each agent execution using this prompt.

    Args:
        prompt_id: Prompt UUID
        confidence_score: Optional confidence score to track
        escalated: Whether the response was escalated
        db: Optional Supabase client
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Get current prompt
        prompt = await get_prompt_by_id(prompt_id, db)
        if prompt is None:
            logger.warning(f"Prompt not found for usage tracking: {prompt_id}")
            return

        # Calculate new statistics
        new_usage_count = prompt.usage_count + 1

        update_data: Dict[str, Any] = {"usage_count": new_usage_count}

        # Update average confidence if provided
        if confidence_score is not None:
            if prompt.avg_confidence is None:
                new_avg_confidence = confidence_score
            else:
                # Running average
                total = prompt.avg_confidence * prompt.usage_count + confidence_score
                new_avg_confidence = total / new_usage_count
            update_data["avg_confidence"] = new_avg_confidence

        # Update escalation rate if tracking
        if prompt.escalation_rate is None:
            escalation_rate = 1.0 if escalated else 0.0
        else:
            # Running average
            total_escalations = prompt.escalation_rate * prompt.usage_count + (
                1.0 if escalated else 0.0
            )
            escalation_rate = total_escalations / new_usage_count
        update_data["escalation_rate"] = escalation_rate

        # Update database
        db.table("prompts").update(update_data).eq("id", str(prompt_id)).execute()

        logger.debug(
            f"Updated prompt usage: {prompt.name} (usage: {new_usage_count}, "
            f"avg_confidence: {update_data.get('avg_confidence')}, "
            f"escalation_rate: {escalation_rate:.2%})"
        )

    except Exception as e:
        logger.error(f"Failed to increment prompt usage: {e}", exc_info=True)
        # Don't raise - this is a non-critical operation


async def get_formatted_prompt(
    name: str,
    prompt_type: str,
    variables: Dict[str, Any],
    fallback: Optional[str] = None,
    db: Optional[Client] = None,
) -> tuple[str, Optional[int]]:
    """
    Get active prompt and format with variables.

    This helper combines prompt retrieval and template formatting with
    proper error handling and fallback support.

    Args:
        name: Prompt identifier (e.g., 'query_analysis_user')
        prompt_type: Type of prompt (system, retrieval, analysis, etc.)
        variables: Dictionary of template variables to format (e.g., {'query': 'user question'})
        fallback: Optional fallback content if prompt not found
        db: Optional Supabase client

    Returns:
        Tuple of (formatted_content, version_number)
        If prompt not found and no fallback, raises ValueError
        If template formatting fails, uses fallback if provided

    Example:
        >>> content, version = await get_formatted_prompt(
        ...     name="query_analysis_user",
        ...     prompt_type="analysis",
        ...     variables={"query": "What is my balance?"},
        ...     fallback="Analyze this query: {query}"
        ... )
        >>> print(f"Using prompt v{version}: {content}")
    """
    if db is None:
        db = get_supabase_client()

    try:
        # Try to get prompt from database
        prompt_obj = await get_active_prompt(name=name, prompt_type=prompt_type, db=db)

        if prompt_obj:
            try:
                # Format template with provided variables
                formatted = prompt_obj.content.format(**variables)
                logger.info(
                    f"Formatted prompt '{name}' v{prompt_obj.version} "
                    f"with variables: {list(variables.keys())}"
                )

                # Track usage (non-blocking)
                await increment_prompt_usage(prompt_obj.id, db=db)

                return formatted, prompt_obj.version

            except KeyError as e:
                # Missing template variable
                missing_var = str(e).strip("'")
                logger.error(
                    f"Missing template variable '{missing_var}' in prompt '{name}'. "
                    f"Required variables: {list(variables.keys())}"
                )
                if fallback:
                    logger.warning(f"Using fallback for prompt '{name}' due to template error")
                    return fallback.format(**variables), None
                raise ValueError(
                    f"Prompt '{name}' requires variable '{missing_var}' which was not provided"
                )

            except Exception as e:
                # Other formatting errors
                logger.error(f"Failed to format prompt '{name}': {e}", exc_info=True)
                if fallback:
                    logger.warning(f"Using fallback for prompt '{name}' due to formatting error")
                    return fallback.format(**variables), None
                raise

        else:
            # Prompt not found in database
            logger.warning(
                f"Prompt '{name}' (type: {prompt_type}) not found in database"
            )
            if fallback:
                logger.info(f"Using fallback for prompt '{name}'")
                # Use safe formatting that handles JSON braces
                try:
                    return fallback.format(**variables), None
                except KeyError as e:
                    # If format fails (e.g., JSON braces in prompt), use simple replacement
                    logger.debug(f"Format failed for fallback prompt, using simple replacement: {e}")
                    formatted = fallback
                    for key, value in variables.items():
                        formatted = formatted.replace(f"{{{key}}}", str(value))
                    return formatted, None
            raise ValueError(
                f"Prompt '{name}' not found and no fallback provided. "
                f"Check that the prompt exists and is active in the database."
            )

    except Exception as e:
        # Database or connection errors
        logger.error(f"Error retrieving prompt '{name}': {e}", exc_info=True)
        if fallback:
            logger.warning(
                f"Using fallback for prompt '{name}' due to database error"
            )
            # Use safe formatting that handles JSON braces
            try:
                return fallback.format(**variables), None
            except KeyError as format_error:
                # If format fails (e.g., JSON braces in prompt), use simple replacement
                logger.debug(f"Format failed for fallback prompt, using simple replacement: {format_error}")
                formatted = fallback
                for key, value in variables.items():
                    formatted = formatted.replace(f"{{{key}}}", str(value))
                return formatted, None
        raise
