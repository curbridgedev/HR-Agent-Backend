"""
MCP (Model Context Protocol) client manager.

Handles connections to user's MCP servers and tool discovery.
"""

from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from langchain_core.tools import StructuredTool

from app.core.logging import get_logger
from app.db.supabase import get_supabase_client

logger = get_logger(__name__)


class MCPClient:
    """
    MCP client for a single remote HTTP server connection.

    Manages connection lifecycle and tool discovery for one MCP server.
    Only supports remote HTTP transport for security and scalability.
    """

    def __init__(self, server_id: str, config: Dict[str, Any]):
        """
        Initialize MCP client.

        Args:
            server_id: Database ID of the MCP server
            config: Server configuration (url, headers, etc.)
        """
        self.server_id = server_id
        self.config = config
        self.session: Optional[ClientSession] = None
        self.http_context = None  # Store HTTP context manager
        self.session_context = None  # Store session context manager
        self.tools: Dict[str, StructuredTool] = {}
        self.connected = False

    async def connect(self) -> bool:
        """
        Connect to the remote MCP server via HTTP.

        Returns:
            True if connection successful
        """
        try:
            # Get URL and headers from config
            url = self.config.get("url")
            headers = self.config.get("headers", {})

            if not url:
                logger.error(f"MCP server {self.server_id}: No URL specified")
                return False

            # Validate URL
            if not url.startswith(("http://", "https://")):
                logger.error(f"MCP server {self.server_id}: Invalid URL - must start with http:// or https://")
                return False

            logger.info(f"MCP server {self.server_id}: Connecting to {url}")

            # Create and enter HTTP context manager
            self.http_context = streamablehttp_client(url, headers=headers)
            read, write, _ = await self.http_context.__aenter__()

            # Create and enter session context manager
            self.session_context = ClientSession(read, write)
            self.session = await self.session_context.__aenter__()

            # Initialize the session
            await self.session.initialize()

            self.connected = True
            logger.info(f"MCP server {self.server_id} connected via HTTP to {url}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.server_id}: {e}", exc_info=True)
            self.connected = False
            return False

    async def disconnect(self):
        """Disconnect from the MCP server."""
        try:
            # Exit session context manager if exists
            if self.session_context:
                await self.session_context.__aexit__(None, None, None)

            # Exit HTTP context manager if exists
            if self.http_context:
                await self.http_context.__aexit__(None, None, None)

            logger.info(f"MCP server {self.server_id} disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting from MCP server {self.server_id}: {e}")
        finally:
            self.session = None
            self.session_context = None
            self.http_context = None
            self.connected = False

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """
        Discover tools from the MCP server.

        Returns:
            List of tool definitions
        """
        if not self.connected or not self.session:
            logger.warning(f"MCP server {self.server_id} not connected")
            return []

        try:
            # List available tools
            tools_response = await self.session.list_tools()

            discovered_tools = []
            for tool in tools_response.tools:
                tool_def = {
                    "name": tool.name,
                    "description": tool.description or "",
                    "schema": tool.inputSchema if hasattr(tool, "inputSchema") else {}
                }
                discovered_tools.append(tool_def)

            logger.info(f"Discovered {len(discovered_tools)} tools from MCP server {self.server_id}")
            return discovered_tools

        except Exception as e:
            logger.error(f"Failed to discover tools from MCP server {self.server_id}: {e}", exc_info=True)
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if not self.connected or not self.session:
            raise RuntimeError(f"MCP server {self.server_id} not connected")

        try:
            # Call the tool
            result = await self.session.call_tool(tool_name, arguments)
            return result

        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on MCP server {self.server_id}: {e}", exc_info=True)
            raise

    def create_langchain_tool(self, tool_def: Dict[str, Any]) -> StructuredTool:
        """
        Convert MCP tool definition to LangChain StructuredTool.

        Args:
            tool_def: MCP tool definition

        Returns:
            LangChain StructuredTool
        """
        tool_name = tool_def["name"]
        tool_description = tool_def["description"]

        # Create async function that calls the MCP tool
        async def tool_func(**kwargs) -> str:
            """Dynamically created tool function."""
            result = await self.call_tool(tool_name, kwargs)
            # MCP returns content array, extract text
            if hasattr(result, "content") and result.content:
                return "\n".join([c.text for c in result.content if hasattr(c, "text")])
            return str(result)

        # Create LangChain tool
        langchain_tool = StructuredTool.from_function(
            func=tool_func,
            name=f"mcp_{self.server_id}_{tool_name}",
            description=tool_description,
            coroutine=tool_func,  # Use async function
        )

        return langchain_tool


class MCPClientManager:
    """
    Manager for all MCP client connections.

    Handles multiple MCP servers and aggregates their tools.
    """

    def __init__(self):
        """Initialize MCP client manager."""
        self.clients: Dict[str, MCPClient] = {}
        self.supabase = get_supabase_client()

    async def connect_server(self, server_id: str) -> bool:
        """
        Connect to an MCP server.

        Args:
            server_id: Database ID of the server

        Returns:
            True if connection successful
        """
        try:
            # Get server config from database
            response = self.supabase.table("mcp_servers").select("*").eq("id", server_id).execute()

            if not response.data:
                logger.error(f"MCP server {server_id} not found in database")
                return False

            server_data = response.data[0]

            # Check if enabled
            if not server_data.get("enabled", False):
                logger.info(f"MCP server {server_id} is disabled")
                return False

            # Build config (HTTP-only)
            config = {
                "url": server_data.get("url"),
                "headers": server_data.get("headers", {}),
                **server_data.get("config", {})
            }

            # Create and connect client
            client = MCPClient(server_id, config)
            success = await client.connect()

            if success:
                self.clients[server_id] = client

                # Update database
                self.supabase.table("mcp_servers").update({
                    "last_connected_at": datetime.now().isoformat(),
                    "connection_attempts": server_data.get("connection_attempts", 0) + 1,
                    "successful_connections": server_data.get("successful_connections", 0) + 1
                }).eq("id", server_id).execute()

                return True
            else:
                # Update error in database
                self.supabase.table("mcp_servers").update({
                    "last_connection_error": "Failed to connect",
                    "last_connection_error_at": datetime.now().isoformat(),
                    "connection_attempts": server_data.get("connection_attempts", 0) + 1
                }).eq("id", server_id).execute()

                return False

        except Exception as e:
            logger.error(f"Failed to connect MCP server {server_id}: {e}", exc_info=True)
            return False

    async def disconnect_server(self, server_id: str):
        """Disconnect from an MCP server."""
        if server_id in self.clients:
            await self.clients[server_id].disconnect()
            del self.clients[server_id]

    async def refresh_tools(self, server_id: str) -> int:
        """
        Refresh tools from an MCP server.

        Args:
            server_id: Server ID

        Returns:
            Number of tools discovered
        """
        if server_id not in self.clients:
            logger.warning(f"MCP server {server_id} not connected")
            return 0

        client = self.clients[server_id]

        # Discover tools
        tools = await client.discover_tools()

        # Update database
        try:
            # Delete old tools for this server
            self.supabase.table("mcp_server_tools").delete().eq("mcp_server_id", server_id).execute()

            # Insert discovered tools
            for tool in tools:
                self.supabase.table("mcp_server_tools").insert({
                    "mcp_server_id": server_id,
                    "tool_name": tool["name"],
                    "tool_description": tool["description"],
                    "tool_schema": tool["schema"],
                    "discovered_at": datetime.now().isoformat(),
                    "last_seen_at": datetime.now().isoformat()
                }).execute()

            # Update server stats
            self.supabase.table("mcp_servers").update({
                "tools_discovered": len(tools),
                "last_tool_refresh_at": datetime.now().isoformat()
            }).eq("id", server_id).execute()

            logger.info(f"Refreshed {len(tools)} tools from MCP server {server_id}")
            return len(tools)

        except Exception as e:
            logger.error(f"Failed to save tools for MCP server {server_id}: {e}", exc_info=True)
            return 0

    async def get_all_tools(self) -> List[StructuredTool]:
        """
        Get all LangChain tools from all connected MCP servers.

        Returns:
            List of LangChain tools
        """
        all_tools = []

        for server_id, client in self.clients.items():
            try:
                # Get tools from database
                response = self.supabase.table("mcp_server_tools").select("*").eq(
                    "mcp_server_id", server_id
                ).execute()

                for tool_data in response.data:
                    tool_def = {
                        "name": tool_data["tool_name"],
                        "description": tool_data["tool_description"],
                        "schema": tool_data.get("tool_schema", {})
                    }

                    # Convert to LangChain tool
                    langchain_tool = client.create_langchain_tool(tool_def)
                    all_tools.append(langchain_tool)

            except Exception as e:
                logger.error(f"Failed to get tools from MCP server {server_id}: {e}", exc_info=True)

        return all_tools

    async def connect_all_enabled_servers(self):
        """Connect to all enabled MCP servers in the database."""
        try:
            response = self.supabase.table("mcp_servers").select("id").eq("enabled", True).execute()

            for server in response.data:
                server_id = server["id"]
                await self.connect_server(server_id)

        except Exception as e:
            logger.error(f"Failed to connect to MCP servers: {e}", exc_info=True)

    async def shutdown(self):
        """Disconnect all MCP servers."""
        for server_id in list(self.clients.keys()):
            await self.disconnect_server(server_id)


# Global MCP client manager instance
_mcp_manager: Optional[MCPClientManager] = None


def get_mcp_manager() -> MCPClientManager:
    """
    Get the global MCP client manager instance.

    Returns:
        MCPClientManager instance
    """
    global _mcp_manager

    if _mcp_manager is None:
        _mcp_manager = MCPClientManager()

    return _mcp_manager
