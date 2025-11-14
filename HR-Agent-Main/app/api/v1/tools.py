"""
API endpoints for tool management.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.tools import (
    ToolListResponse,
    ToolInfo,
    ToolUpdateRequest,
    ToolAnalytics,
)
from app.models.base import BaseResponse
from app.services.tool_management import get_tool_service
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=ToolListResponse)
async def list_tools(
    category: Optional[str] = Query(None, description="Filter by category"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
) -> ToolListResponse:
    """
    List all available tools with optional filtering.

    Query Parameters:
    - **category**: Filter by tool category (math, finance, search, utility)
    - **enabled**: Filter by enabled status (true/false)

    Returns:
    - List of tools with usage statistics
    - Total count and enabled/disabled counts
    """
    try:
        service = get_tool_service()
        return await service.list_tools(category=category, enabled=enabled)

    except Exception as e:
        logger.error(f"Failed to list tools: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list tools: {str(e)}")


@router.get("/{tool_name}", response_model=ToolInfo)
async def get_tool(tool_name: str) -> ToolInfo:
    """
    Get detailed information about a specific tool.

    Path Parameters:
    - **tool_name**: Name of the tool

    Returns:
    - Tool information including usage statistics
    """
    try:
        service = get_tool_service()
        tool = await service.get_tool(tool_name)

        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        return tool

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tool {tool_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get tool: {str(e)}")


@router.patch("/{tool_name}", response_model=ToolInfo)
async def update_tool(
    tool_name: str,
    update_request: ToolUpdateRequest,
) -> ToolInfo:
    """
    Update tool configuration.

    Path Parameters:
    - **tool_name**: Name of the tool

    Request Body:
    - **enabled**: Enable/disable the tool (optional)
    - **config**: Tool-specific configuration (optional)
    - **description**: Tool description (optional)

    Returns:
    - Updated tool information
    """
    try:
        service = get_tool_service()
        tool = await service.update_tool(tool_name, update_request)

        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        return tool

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update tool {tool_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update tool: {str(e)}")


@router.post("/{tool_name}/enable", response_model=ToolInfo)
async def enable_tool(tool_name: str) -> ToolInfo:
    """
    Enable a tool.

    Path Parameters:
    - **tool_name**: Name of the tool

    Returns:
    - Updated tool information
    """
    try:
        service = get_tool_service()
        update_request = ToolUpdateRequest(enabled=True, config=None, description=None)
        tool = await service.update_tool(tool_name, update_request)

        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        return tool

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable tool {tool_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to enable tool: {str(e)}")


@router.post("/{tool_name}/disable", response_model=ToolInfo)
async def disable_tool(tool_name: str) -> ToolInfo:
    """
    Disable a tool.

    Path Parameters:
    - **tool_name**: Name of the tool

    Returns:
    - Updated tool information
    """
    try:
        service = get_tool_service()
        update_request = ToolUpdateRequest(enabled=False, config=None, description=None)
        tool = await service.update_tool(tool_name, update_request)

        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        return tool

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable tool {tool_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to disable tool: {str(e)}")


@router.get("/analytics/usage", response_model=ToolAnalytics)
async def get_tool_analytics() -> ToolAnalytics:
    """
    Get tool usage analytics and statistics.

    Returns:
    - Overall tool usage statistics
    - Most used tools
    - Tools grouped by category
    """
    try:
        service = get_tool_service()
        analytics = await service.get_tool_analytics()

        if not analytics:
            raise HTTPException(status_code=500, detail="Failed to retrieve analytics")

        return analytics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tool analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")
