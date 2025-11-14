"""
Prompts API endpoints for managing system prompts with versioning.

Provides endpoints for:
- Listing prompts by type
- Getting available prompt types
- Creating new prompt versions
- Activating prompt versions
- Getting prompt history
"""

from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field

from app.core.logging import get_logger
from app.models.prompts import (
    PromptCreate,
    PromptUpdate,
    PromptResponse,
    PromptListResponse,
    PromptVersionCreateResponse,
)
from app.models.base import BaseResponse
from app.services.prompts import (
    list_prompts,
    get_prompt_by_id,
    get_prompt_history,
    create_prompt_version,
    activate_prompt,
    update_prompt,
)

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=PromptListResponse)
async def list_prompts_endpoint(
    prompt_type: Optional[str] = Query(None, description="Filter by prompt type (system, confidence, retrieval, analysis)"),
    active_only: bool = Query(False, description="Only return active prompts"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
):
    """
    List prompts with filtering and pagination.

    Args:
        prompt_type: Filter by prompt type (optional)
        active_only: Only return active prompts (default: False)
        page: Page number (1-indexed)
        page_size: Number of items per page

    Returns:
        Paginated list of prompts

    Example:
        GET /api/v1/prompts
        GET /api/v1/prompts?prompt_type=system
        GET /api/v1/prompts?prompt_type=confidence&active_only=true
    """
    try:
        logger.info(
            f"Listing prompts: type={prompt_type}, active_only={active_only}, "
            f"page={page}, page_size={page_size}"
        )

        result = await list_prompts(
            prompt_type=prompt_type,
            active_only=active_only,
            page=page,
            page_size=page_size,
        )

        return result

    except Exception as e:
        logger.error(f"Failed to list prompts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list prompts: {str(e)}",
        )


# Response model for prompt types endpoint
class PromptTypeInfo(BaseResponse):
    """Information about a prompt type."""
    prompt_type: str = Field(..., description="The prompt type identifier")
    description: str = Field(..., description="Human-readable description")
    category: str = Field(..., description="Category for UI grouping")
    active_count: int = Field(..., description="Number of active prompts of this type")
    total_count: int = Field(..., description="Total prompts of this type (all versions)")
    example_name: Optional[str] = Field(None, description="Example prompt name of this type")


class PromptTypesResponse(BaseResponse):
    """Response containing all available prompt types."""
    types: List[PromptTypeInfo] = Field(..., description="List of available prompt types")
    total_types: int = Field(..., description="Total number of distinct types")


@router.get("/types/list", response_model=PromptTypesResponse)
async def get_prompt_types():
    """
    Get all available prompt types with metadata.

    Returns dynamic list of all prompt types in the system with descriptions
    and counts. Frontend can use this to build dynamic UI without hardcoding types.

    Returns:
        List of prompt types with metadata

    Example:
        GET /api/v1/prompts/types/list
    """
    try:
        from app.db.supabase import get_supabase_client

        logger.info("Fetching all available prompt types")

        supabase = get_supabase_client()

        # Query distinct types with counts directly
        # (RPC function can be added later for optimization)
        query_response = supabase.from_("prompts").select(
            "prompt_type, name, active",
            count="exact"
        ).execute()

        # Group by type
        types_data: Dict[str, Dict[str, Any]] = {}
        for row in query_response.data:
            ptype = row["prompt_type"]
            if ptype not in types_data:
                types_data[ptype] = {
                    "active_count": 0,
                    "total_count": 0,
                    "example_name": row["name"]
                }
            types_data[ptype]["total_count"] += 1
            if row["active"]:
                types_data[ptype]["active_count"] += 1

        # Define metadata for each type
        type_metadata = {
            "system": {
                "description": "Main AI assistant identity - defines Compaytence AI persona and guidelines",
                "category": "Core"
            },
            "query_analysis_system": {
                "description": "Query analyzer identity - instructs to classify user queries as JSON",
                "category": "Analysis"
            },
            "tool_invocation": {
                "description": "Tool selector identity - guides selection of appropriate tools",
                "category": "Tools"
            },
            "retrieval": {
                "description": "RAG context formatting - templates retrieved context with user query",
                "category": "RAG"
            },
            "confidence": {
                "description": "Confidence scoring - evaluates response quality and certainty",
                "category": "Quality"
            },
            "analysis": {
                "description": "Query classification - extracts intent, entities, and urgency",
                "category": "Analysis"
            }
        }

        # Build response
        types_list = []
        for ptype, data in types_data.items():
            metadata = type_metadata.get(ptype, {
                "description": f"Prompt type: {ptype}",
                "category": "Other"
            })

            types_list.append(PromptTypeInfo(
                prompt_type=ptype,
                description=metadata["description"],
                category=metadata["category"],
                active_count=data["active_count"],
                total_count=data["total_count"],
                example_name=data["example_name"]
            ))

        # Sort by category then type
        types_list.sort(key=lambda x: (x.category, x.prompt_type))

        return PromptTypesResponse(
            types=types_list,
            total_types=len(types_list)
        )

    except Exception as e:
        logger.error(f"Failed to get prompt types: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prompt types: {str(e)}",
        )


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt_endpoint(prompt_id: UUID):
    """
    Get a specific prompt by ID.

    Args:
        prompt_id: Prompt UUID

    Returns:
        Prompt details

    Example:
        GET /api/v1/prompts/550e8400-e29b-41d4-a716-446655440000
    """
    try:
        logger.info(f"Getting prompt: {prompt_id}")

        prompt = await get_prompt_by_id(prompt_id)

        if prompt is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt {prompt_id} not found",
            )

        return prompt

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get prompt {prompt_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prompt: {str(e)}",
        )


@router.get("/{name}/history", response_model=PromptListResponse)
async def get_prompt_history_endpoint(
    name: str,
    prompt_type: str = Query(..., description="Prompt type (system, confidence, etc.)"),
):
    """
    Get version history for a specific prompt.

    Args:
        name: Prompt name (e.g., 'main_system_prompt')
        prompt_type: Prompt type

    Returns:
        List of all versions ordered by version number (newest first)

    Example:
        GET /api/v1/prompts/main_system_prompt/history?prompt_type=system
    """
    try:
        logger.info(f"Getting history for prompt: {name} (type: {prompt_type})")

        history = await get_prompt_history(name=name, prompt_type=prompt_type)

        return PromptListResponse(
            prompts=history,
            total=len(history),
            page=1,
            page_size=len(history),
        )

    except Exception as e:
        logger.error(f"Failed to get prompt history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prompt history: {str(e)}",
        )


@router.post("/versions", response_model=PromptVersionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_version_endpoint(request: PromptCreate):
    """
    Create a new version of a prompt.

    Auto-increments version number for the (name, prompt_type) combination.

    Args:
        request: Prompt creation request

    Returns:
        Created prompt version info

    Example:
        POST /api/v1/prompts/versions
        {
          "name": "main_system_prompt",
          "prompt_type": "system",
          "content": "You are...",
          "tags": ["v2", "production"],
          "notes": "Improved clarity",
          "activate_immediately": false
        }
    """
    try:
        logger.info(
            f"Creating new prompt version: {request.name} (type: {request.prompt_type})"
        )

        prompt = await create_prompt_version(request)

        return PromptVersionCreateResponse(
            prompt_id=prompt.id,
            version=prompt.version,
            active=prompt.active,
        )

    except Exception as e:
        logger.error(f"Failed to create prompt version: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create prompt version: {str(e)}",
        )


@router.post("/{prompt_id}/activate", response_model=PromptResponse)
async def activate_prompt_endpoint(prompt_id: UUID):
    """
    Activate a specific prompt version.

    Deactivates all other versions with the same (name, prompt_type).

    Args:
        prompt_id: ID of prompt version to activate

    Returns:
        Activated prompt

    Example:
        POST /api/v1/prompts/550e8400-e29b-41d4-a716-446655440000/activate
    """
    try:
        logger.info(f"Activating prompt: {prompt_id}")

        prompt = await activate_prompt(prompt_id)

        return prompt

    except Exception as e:
        logger.error(f"Failed to activate prompt {prompt_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate prompt: {str(e)}",
        )


@router.patch("/{prompt_id}", response_model=PromptResponse)
async def update_prompt_endpoint(prompt_id: UUID, request: PromptUpdate):
    """
    Update a prompt's metadata or content.

    Note: For content changes, consider creating a new version instead.

    Args:
        prompt_id: Prompt UUID
        request: Update request

    Returns:
        Updated prompt

    Example:
        PATCH /api/v1/prompts/550e8400-e29b-41d4-a716-446655440000
        {
          "tags": ["production", "v2", "tested"],
          "notes": "Updated tags after successful testing"
        }
    """
    try:
        logger.info(f"Updating prompt: {prompt_id}")

        prompt = await update_prompt(prompt_id, request)

        return prompt

    except Exception as e:
        logger.error(f"Failed to update prompt {prompt_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update prompt: {str(e)}",
        )
