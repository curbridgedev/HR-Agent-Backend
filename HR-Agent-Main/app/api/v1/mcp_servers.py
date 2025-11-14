"""
API endpoints for MCP server management.
"""

from fastapi import APIRouter, HTTPException, Query

from app.core.logging import get_logger
from app.models.base import SuccessResponse
from app.models.tools import (
    MCPServerCreateRequest,
    MCPServerInfo,
    MCPServerListResponse,
    MCPServerUpdateRequest,
)
from app.services.tool_management import get_mcp_service

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=MCPServerListResponse)
async def list_mcp_servers(
    enabled: bool | None = Query(None, description="Filter by enabled status"),
) -> MCPServerListResponse:
    """
    List all MCP servers with optional filtering.

    Query Parameters:
    - **enabled**: Filter by enabled status (true/false)

    Returns:
    - List of MCP servers with health status
    - Total count and enabled/disabled counts
    """
    try:
        service = get_mcp_service()
        return await service.list_servers(enabled=enabled)

    except Exception as e:
        logger.error(f"Failed to list MCP servers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list MCP servers: {str(e)}")


@router.get("/{server_name}", response_model=MCPServerInfo)
async def get_mcp_server(server_name: str) -> MCPServerInfo:
    """
    Get detailed information about a specific MCP server.

    Path Parameters:
    - **server_name**: Name of the MCP server

    Returns:
    - MCP server information including health status and connection metrics
    """
    try:
        service = get_mcp_service()
        server = await service.get_server(server_name)

        if not server:
            raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")

        return server

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCP server {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get MCP server: {str(e)}")


@router.post("/", response_model=MCPServerInfo, status_code=201)
async def create_mcp_server(
    create_request: MCPServerCreateRequest,
) -> MCPServerInfo:
    """
    Register a new remote MCP server (HTTP-only).

    **Security Note**: For security and scalability, only remote HTTP servers are supported.
    Users must host their own MCP servers or use cloud providers.

    Request Body:
    - **config**: MCP server configuration
      - **name**: Unique server name (required)
      - **url**: Server URL starting with http:// or https:// (required)
      - **description**: Server description (optional)
      - **enabled**: Whether server is enabled (default: true)
      - **headers**: HTTP headers for authentication (optional)
      - **config**: Additional configuration (optional)

    Returns:
    - Created MCP server information

    Example:
      ```json
      {
        "config": {
          "name": "weather-server",
          "url": "https://api.example.com/mcp",
          "headers": {
            "Authorization": "Bearer your-token-here",
            "X-API-Key": "your-api-key"
          },
          "description": "Weather information server",
          "enabled": true
        }
      }
      ```
    """
    try:
        service = get_mcp_service()

        # Check if server already exists
        existing = await service.get_server(create_request.config.name)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"MCP server '{create_request.config.name}' already exists",
            )

        server = await service.create_server(create_request)

        if not server:
            raise HTTPException(status_code=500, detail="Failed to create MCP server")

        return server

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create MCP server: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create MCP server: {str(e)}")


@router.patch("/{server_name}", response_model=MCPServerInfo)
async def update_mcp_server(
    server_name: str,
    update_request: MCPServerUpdateRequest,
) -> MCPServerInfo:
    """
    Update MCP server configuration.

    Path Parameters:
    - **server_name**: Name of the MCP server

    Request Body:
    - **enabled**: Enable/disable the server (optional)
    - **description**: Server description (optional)
    - **config**: Additional configuration (optional)

    Returns:
    - Updated MCP server information
    """
    try:
        service = get_mcp_service()
        server = await service.update_server(server_name, update_request)

        if not server:
            raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")

        return server

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update MCP server {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update MCP server: {str(e)}")


@router.delete("/{server_name}", response_model=SuccessResponse)
async def delete_mcp_server(server_name: str) -> SuccessResponse:
    """
    Delete an MCP server.

    Path Parameters:
    - **server_name**: Name of the MCP server

    Returns:
    - Success/failure response
    """
    try:
        service = get_mcp_service()
        success = await service.delete_server(server_name)

        if not success:
            raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")

        return SuccessResponse(
            success=True,
            message=f"MCP server '{server_name}' deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete MCP server {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete MCP server: {str(e)}")


@router.post("/{server_name}/enable", response_model=MCPServerInfo)
async def enable_mcp_server(server_name: str) -> MCPServerInfo:
    """
    Enable an MCP server.

    Path Parameters:
    - **server_name**: Name of the MCP server

    Returns:
    - Updated MCP server information
    """
    try:
        service = get_mcp_service()
        update_request = MCPServerUpdateRequest(enabled=True, description=None, config=None)
        server = await service.update_server(server_name, update_request)

        if not server:
            raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")

        return server

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable MCP server {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to enable MCP server: {str(e)}")


@router.post("/{server_name}/disable", response_model=MCPServerInfo)
async def disable_mcp_server(server_name: str) -> MCPServerInfo:
    """
    Disable an MCP server.

    Path Parameters:
    - **server_name**: Name of the MCP server

    Returns:
    - Updated MCP server information
    """
    try:
        service = get_mcp_service()
        update_request = MCPServerUpdateRequest(enabled=False, description=None, config=None)
        server = await service.update_server(server_name, update_request)

        if not server:
            raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")

        return server

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable MCP server {server_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to disable MCP server: {str(e)}")


@router.post("/{server_name}/refresh-tools", response_model=SuccessResponse)
async def refresh_mcp_server_tools(server_name: str) -> SuccessResponse:
    """
    Refresh tool discovery for an MCP server.

    Path Parameters:
    - **server_name**: Name of the MCP server

    Returns:
    - Success/failure response with tool count

    Note:
    This triggers a fresh tool discovery from the MCP server and updates the database.
    """
    try:
        service = get_mcp_service()

        # Check if server exists
        server = await service.get_server(server_name)
        if not server:
            raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")

        logger.info(f"Tool refresh requested for MCP server: {server_name}")

        # Refresh tools from the MCP server
        try:
            tool_count = await service.refresh_tools(server.id)

            logger.info(f"Successfully refreshed {tool_count} tools for MCP server: {server_name}")

            return SuccessResponse(
                success=True,
                message=f"Refreshed {tool_count} tool(s) for '{server_name}'",
                data={"tools_discovered": tool_count},
            )

        except ValueError as ve:
            # Server not found or not registered
            logger.error(f"Server validation error: {ve}")
            raise HTTPException(status_code=404, detail=str(ve))

        except Exception as refresh_error:
            logger.error(
                f"Failed to refresh tools for {server_name}: {refresh_error}", exc_info=True
            )
            raise HTTPException(
                status_code=500, detail=f"Failed to refresh tools: {str(refresh_error)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh tools for MCP server {server_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh tools: {str(e)}",
        )
