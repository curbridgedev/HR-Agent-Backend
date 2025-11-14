"""
Service layer for tool and MCP server management.
"""

import uuid
from datetime import datetime
from typing import Any

from app.agents.mcp_integration import MCPServerConfig as MCPConfig
from app.agents.mcp_integration import get_mcp_client_manager
from app.agents.tools import get_tool_registry
from app.core.logging import get_logger
from app.db.supabase import get_supabase_client
from app.models.tools import (
    MCPServerCreateRequest,
    MCPServerInfo,
    MCPServerListResponse,
    MCPServerUpdateRequest,
    ToolAnalytics,
    ToolInfo,
    ToolListResponse,
    ToolUpdateRequest,
)

logger = get_logger(__name__)


# ============================================================================
# Tool Management Service
# ============================================================================


class ToolManagementService:
    """Service for managing tools and their configurations."""

    def __init__(self):
        """Initialize tool management service."""
        self.supabase = get_supabase_client()
        self.tool_registry = get_tool_registry()

    async def list_tools(
        self, category: str | None = None, enabled: bool | None = None
    ) -> ToolListResponse:
        """
        List all tools with optional filtering.

        Args:
            category: Filter by category
            enabled: Filter by enabled status

        Returns:
            ToolListResponse with tool list and statistics
        """
        try:
            # Build query
            query = self.supabase.table("tools").select("*")

            if category:
                query = query.eq("category", category)

            if enabled is not None:
                query = query.eq("enabled", enabled)

            # Execute query
            response = query.execute()

            if not response.data:
                return ToolListResponse(
                    tools=[],
                    total=0,
                    enabled_count=0,
                    disabled_count=0,
                )

            # Parse tools
            tools = []
            enabled_count = 0
            disabled_count = 0

            for row in response.data:
                # Calculate success rate
                success_rate = None
                if row.get("invocation_count", 0) > 0:
                    success_rate = (row.get("success_count", 0) / row["invocation_count"]) * 100

                tool = ToolInfo(
                    id=row["id"],
                    name=row["name"],
                    category=row["category"],
                    description=row.get("description"),
                    enabled=row["enabled"],
                    config=row.get("config", {}),
                    invocation_count=row.get("invocation_count", 0),
                    success_count=row.get("success_count", 0),
                    failure_count=row.get("failure_count", 0),
                    success_rate_percent=success_rate,
                    avg_execution_time_ms=row.get("avg_execution_time_ms"),
                    last_invoked_at=row.get("last_invoked_at"),
                    last_error=row.get("last_error"),
                    last_error_at=row.get("last_error_at"),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

                tools.append(tool)

                if row["enabled"]:
                    enabled_count += 1
                else:
                    disabled_count += 1

            return ToolListResponse(
                tools=tools,
                total=len(tools),
                enabled_count=enabled_count,
                disabled_count=disabled_count,
            )

        except Exception as e:
            logger.error(f"Failed to list tools: {e}", exc_info=True)
            # Re-raise to let API layer handle with HTTP exception
            raise

    async def get_tool(self, tool_name: str) -> ToolInfo | None:
        """
        Get tool by name.

        Args:
            tool_name: Tool name

        Returns:
            ToolInfo or None if not found
        """
        try:
            response = self.supabase.table("tools").select("*").eq("name", tool_name).execute()

            if not response.data:
                return None

            row = response.data[0]

            # Calculate success rate
            success_rate = None
            if row.get("invocation_count", 0) > 0:
                success_rate = (row.get("success_count", 0) / row["invocation_count"]) * 100

            return ToolInfo(
                id=row["id"],
                name=row["name"],
                category=row["category"],
                description=row.get("description"),
                enabled=row["enabled"],
                config=row.get("config", {}),
                invocation_count=row.get("invocation_count", 0),
                success_count=row.get("success_count", 0),
                failure_count=row.get("failure_count", 0),
                success_rate_percent=success_rate,
                avg_execution_time_ms=row.get("avg_execution_time_ms"),
                last_invoked_at=row.get("last_invoked_at"),
                last_error=row.get("last_error"),
                last_error_at=row.get("last_error_at"),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        except Exception as e:
            logger.error(f"Failed to get tool {tool_name}: {e}", exc_info=True)
            return None

    async def update_tool(
        self, tool_name: str, update_request: ToolUpdateRequest
    ) -> ToolInfo | None:
        """
        Update tool configuration.

        Automatically encrypts sensitive configuration values (API keys, tokens, etc.)
        before saving to database. After update, refreshes tool in registry with new config.

        Args:
            tool_name: Tool name
            update_request: Update request with new configuration

        Returns:
            Updated ToolInfo or None if failed
        """
        try:
            from app.utils.encryption import encrypt_value, is_encrypted

            # Build update data
            update_data: dict[str, Any] = {}

            if update_request.enabled is not None:
                update_data["enabled"] = update_request.enabled

            if update_request.config is not None:
                # Encrypt sensitive config values before saving
                encrypted_config = {}
                sensitive_keys = ["api_key", "api_secret", "password", "token", "secret"]

                for key, value in update_request.config.items():
                    # Encrypt if it's a sensitive key and not already encrypted
                    if isinstance(value, str) and any(
                        sensitive in key.lower() for sensitive in sensitive_keys
                    ):
                        if not is_encrypted(value) and value.strip():
                            try:
                                encrypted_config[key] = encrypt_value(value)
                                logger.debug(f"Encrypted sensitive config key: {key}")
                            except Exception as e:
                                logger.error(f"Failed to encrypt {key}: {e}")
                                encrypted_config[key] = value
                        else:
                            encrypted_config[key] = value
                    else:
                        encrypted_config[key] = value

                update_data["config"] = encrypted_config

            if update_request.description is not None:
                update_data["description"] = update_request.description

            if not update_data:
                logger.warning("No updates provided")
                return await self.get_tool(tool_name)

            # Update in database
            response = (
                self.supabase.table("tools").update(update_data).eq("name", tool_name).execute()
            )

            if not response.data:
                logger.error(f"Tool {tool_name} not found")
                return None

            # If enabled status changed, update tool registry
            if update_request.enabled is not None:
                if update_request.enabled:
                    self.tool_registry.enable_tool(tool_name)
                else:
                    self.tool_registry.disable_tool(tool_name)

            # If config changed, refresh tool in registry
            if update_request.config is not None:
                await self.tool_registry.refresh_tool_from_db(tool_name)
                logger.info(f"Refreshed tool {tool_name} with new configuration")

            logger.info(f"Updated tool {tool_name}")

            return await self.get_tool(tool_name)

        except Exception as e:
            logger.error(f"Failed to update tool {tool_name}: {e}", exc_info=True)
            return None

    async def get_tool_analytics(self) -> ToolAnalytics | None:
        """
        Get tool usage analytics.

        Returns:
            ToolAnalytics with usage statistics
        """
        try:
            # Get all tools
            tools_response = await self.list_tools()

            if not tools_response or not tools_response.tools:
                return None

            tools = tools_response.tools

            # Calculate totals
            total_invocations = sum(t.invocation_count for t in tools)
            successful_invocations = sum(t.success_count for t in tools)
            failed_invocations = sum(t.failure_count for t in tools)

            overall_success_rate = 0.0
            if total_invocations > 0:
                overall_success_rate = (successful_invocations / total_invocations) * 100

            # Get most used tools
            most_used = sorted(tools, key=lambda t: t.invocation_count, reverse=True)[:10]
            most_used_stats = [
                {
                    "tool_name": t.name,
                    "category": t.category,
                    "invocation_count": t.invocation_count,
                    "success_count": t.success_count,
                    "failure_count": t.failure_count,
                    "success_rate_percent": t.success_rate_percent or 0.0,
                    "avg_execution_time_ms": t.avg_execution_time_ms,
                }
                for t in most_used
            ]

            # Group by category
            tools_by_category: dict[str, int] = {}
            for tool in tools:
                tools_by_category[tool.category] = tools_by_category.get(tool.category, 0) + 1

            return ToolAnalytics(
                total_tools=tools_response.total,
                enabled_tools=tools_response.enabled_count,
                total_invocations=total_invocations,
                successful_invocations=successful_invocations,
                failed_invocations=failed_invocations,
                overall_success_rate=overall_success_rate,
                most_used_tools=most_used_stats,
                tools_by_category=tools_by_category,
            )

        except Exception as e:
            logger.error(f"Failed to get tool analytics: {e}", exc_info=True)
            return None


# ============================================================================
# MCP Server Management Service
# ============================================================================


class MCPServerManagementService:
    """Service for managing MCP servers."""

    def __init__(self):
        """Initialize MCP server management service."""
        self.supabase = get_supabase_client()
        self.mcp_manager = get_mcp_client_manager()

    async def list_servers(self, enabled: bool | None = None) -> MCPServerListResponse:
        """
        List all MCP servers.

        Args:
            enabled: Filter by enabled status

        Returns:
            MCPServerListResponse with server list
        """
        try:
            # Build query
            query = self.supabase.table("mcp_servers").select("*")

            if enabled is not None:
                query = query.eq("enabled", enabled)

            # Execute query
            response = query.execute()

            if not response.data:
                return MCPServerListResponse(
                    servers=[],
                    total=0,
                    enabled_count=0,
                    disabled_count=0,
                )

            # Parse servers
            servers = []
            enabled_count = 0
            disabled_count = 0

            for row in response.data:
                # Calculate connection success rate
                conn_success_rate = None
                if row.get("connection_attempts", 0) > 0:
                    conn_success_rate = (
                        row.get("successful_connections", 0) / row["connection_attempts"]
                    ) * 100

                server = MCPServerInfo(
                    id=row["id"],
                    name=row["name"],
                    description=row.get("description"),
                    enabled=row["enabled"],
                    transport=row["transport"],
                    command=row.get("command"),
                    args=row.get("args"),
                    url=row.get("url"),
                    tools_discovered=row.get("tools_discovered", 0),
                    last_connected_at=row.get("last_connected_at"),
                    last_connection_error=row.get("last_connection_error"),
                    last_connection_error_at=row.get("last_connection_error_at"),
                    connection_attempts=row.get("connection_attempts", 0),
                    successful_connections=row.get("successful_connections", 0),
                    connection_success_rate_percent=conn_success_rate,
                    last_tool_refresh_at=row.get("last_tool_refresh_at"),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

                servers.append(server)

                if row["enabled"]:
                    enabled_count += 1
                else:
                    disabled_count += 1

            return MCPServerListResponse(
                servers=servers,
                total=len(servers),
                enabled_count=enabled_count,
                disabled_count=disabled_count,
            )

        except Exception as e:
            logger.error(f"Failed to list MCP servers: {e}", exc_info=True)
            # Re-raise to let API layer handle with HTTP exception
            raise

    async def get_server(self, server_name: str) -> MCPServerInfo | None:
        """
        Get MCP server by name.

        Args:
            server_name: Server name

        Returns:
            MCPServerInfo or None if not found
        """
        try:
            response = (
                self.supabase.table("mcp_servers").select("*").eq("name", server_name).execute()
            )

            if not response.data:
                return None

            row = response.data[0]

            # Calculate connection success rate
            conn_success_rate = None
            if row.get("connection_attempts", 0) > 0:
                conn_success_rate = (
                    row.get("successful_connections", 0) / row["connection_attempts"]
                ) * 100

            return MCPServerInfo(
                id=row["id"],
                name=row["name"],
                description=row.get("description"),
                enabled=row["enabled"],
                transport=row["transport"],
                command=row.get("command"),
                args=row.get("args"),
                url=row.get("url"),
                tools_discovered=row.get("tools_discovered", 0),
                last_connected_at=row.get("last_connected_at"),
                last_connection_error=row.get("last_connection_error"),
                last_connection_error_at=row.get("last_connection_error_at"),
                connection_attempts=row.get("connection_attempts", 0),
                successful_connections=row.get("successful_connections", 0),
                connection_success_rate_percent=conn_success_rate,
                last_tool_refresh_at=row.get("last_tool_refresh_at"),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        except Exception as e:
            logger.error(f"Failed to get MCP server {server_name}: {e}", exc_info=True)
            return None

    async def create_server(self, create_request: MCPServerCreateRequest) -> MCPServerInfo | None:
        """
        Register a new MCP server.

        Args:
            create_request: Server configuration

        Returns:
            Created MCPServerInfo or None if failed
        """
        try:
            config = create_request.config

            # MCPServerConfig is HTTP-only (has 'url' field, no 'transport' field)
            # Always use streamable_http transport for HTTP-based servers
            transport = "streamable_http"

            # Build insert data
            insert_data = {
                "id": str(uuid.uuid4()),
                "name": config.name,
                "description": config.description,
                "enabled": config.enabled,
                "transport": transport,  # Always "streamable_http" for HTTP servers
                "config": config.config,
                "url": config.url,  # HTTP endpoint (required in MCPServerConfig)
                "headers": config.headers or {},  # HTTP headers
            }

            # Insert into database
            response = self.supabase.table("mcp_servers").insert(insert_data).execute()

            if not response.data:
                logger.error("Failed to insert MCP server")
                return None

            # Register in MCP manager (HTTP-only server)
            mcp_config = MCPConfig(
                name=config.name,
                transport=transport,  # Use the hardcoded "streamable_http"
                command=None,  # Not applicable for HTTP servers
                args=None,  # Not applicable for HTTP servers
                url=config.url,
                headers=config.headers,
                enabled=config.enabled,
            )
            self.mcp_manager.register_server(mcp_config)

            logger.info(f"Registered MCP server: {config.name}")

            return await self.get_server(config.name)

        except Exception as e:
            logger.error(f"Failed to create MCP server: {e}", exc_info=True)
            return None

    async def update_server(
        self, server_name: str, update_request: MCPServerUpdateRequest
    ) -> MCPServerInfo | None:
        """
        Update MCP server configuration.

        Args:
            server_name: Server name
            update_request: Update request

        Returns:
            Updated MCPServerInfo or None if failed
        """
        try:
            # Build update data
            update_data: dict[str, Any] = {}

            if update_request.enabled is not None:
                update_data["enabled"] = update_request.enabled

            if update_request.description is not None:
                update_data["description"] = update_request.description

            if update_request.config is not None:
                update_data["config"] = update_request.config

            if not update_data:
                logger.warning("No updates provided")
                return await self.get_server(server_name)

            # Update in database
            response = (
                self.supabase.table("mcp_servers")
                .update(update_data)
                .eq("name", server_name)
                .execute()
            )

            if not response.data:
                logger.error(f"MCP server {server_name} not found")
                return None

            logger.info(f"Updated MCP server {server_name}")

            return await self.get_server(server_name)

        except Exception as e:
            logger.error(f"Failed to update MCP server {server_name}: {e}", exc_info=True)
            return None

    async def delete_server(self, server_name: str) -> bool:
        """
        Delete MCP server.

        Args:
            server_name: Server name

        Returns:
            True if deleted successfully
        """
        try:
            # Delete from database
            response = self.supabase.table("mcp_servers").delete().eq("name", server_name).execute()

            if not response.data:
                logger.error(f"MCP server {server_name} not found")
                return False

            # Unregister from MCP manager
            self.mcp_manager.unregister_server(server_name)

            logger.info(f"Deleted MCP server: {server_name}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete MCP server {server_name}: {e}", exc_info=True)
            return False

    async def refresh_tools(self, server_id: str) -> int:
        """
        Refresh tools from an MCP server.

        Connects to the MCP server, discovers available tools, and updates the database.

        Args:
            server_id: Server ID (UUID)

        Returns:
            Number of tools discovered

        Raises:
            Exception: If tool discovery or database update fails
        """
        try:
            # Get server from database
            response = self.supabase.table("mcp_servers").select("*").eq("id", server_id).execute()

            if not response.data:
                logger.error(f"MCP server {server_id} not found in database")
                raise ValueError(f"MCP server {server_id} not found")

            server_data = response.data[0]
            server_name = server_data["name"]

            logger.info(f"Refreshing tools for MCP server: {server_name}")

            # Create a temporary MCP client for ONLY this server to get its tools
            from langchain_mcp_adapters.client import MultiServerMCPClient
            from app.agents.mcp_integration import MCPServerConfig

            # Get server config
            server_config = MCPServerConfig(
                name=server_name,
                transport=server_data["transport"],
                command=server_data.get("command"),
                args=server_data.get("args"),
                url=server_data.get("url"),
                headers=server_data.get("headers", {}),
                enabled=True,
            )

            # Create a temporary client with ONLY this server
            temp_client = MultiServerMCPClient({server_name: server_config.to_dict()})

            # Get tools from this specific server
            server_tools = await temp_client.get_tools()

            # Debug: Log tool names
            logger.info(
                f"Tools from {server_name}: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in server_tools]}"
            )

            logger.info(f"Discovered {len(server_tools)} tools from MCP server {server_name}")

            # Delete old tools for this server
            self.supabase.table("mcp_server_tools").delete().eq(
                "mcp_server_id", server_id
            ).execute()

            # Insert discovered tools
            for tool in server_tools:
                # Tool name is the actual tool name (no server prefix when using single-server client)
                tool_name = tool.name if hasattr(tool, "name") else str(tool)
                tool_description = tool.description if hasattr(tool, "description") else ""

                self.supabase.table("mcp_server_tools").insert(
                    {
                        "mcp_server_id": server_id,
                        "tool_name": tool_name,
                        "tool_description": tool_description,
                        "tool_schema": {},  # Schema not available from langchain-mcp-adapters
                        "discovered_at": datetime.now().isoformat(),
                        "last_seen_at": datetime.now().isoformat(),
                    }
                ).execute()

            # Update server stats
            self.supabase.table("mcp_servers").update(
                {
                    "tools_discovered": len(server_tools),
                    "last_tool_refresh_at": datetime.now().isoformat(),
                }
            ).eq("id", server_id).execute()

            logger.info(
                f"Successfully refreshed {len(server_tools)} tools for MCP server {server_name}"
            )
            return len(server_tools)

        except Exception as e:
            logger.error(f"Failed to refresh tools for MCP server {server_id}: {e}", exc_info=True)
            raise


# Singleton instances
_tool_service: ToolManagementService | None = None
_mcp_service: MCPServerManagementService | None = None


def get_tool_service() -> ToolManagementService:
    """Get tool management service instance."""
    global _tool_service
    if _tool_service is None:
        _tool_service = ToolManagementService()
    return _tool_service


def get_mcp_service() -> MCPServerManagementService:
    """Get MCP server management service instance."""
    global _mcp_service
    if _mcp_service is None:
        _mcp_service = MCPServerManagementService()
    return _mcp_service
