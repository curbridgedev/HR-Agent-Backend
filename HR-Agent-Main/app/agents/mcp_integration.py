"""
MCP (Model Context Protocol) Integration for Compaytence AI Agent.

Provides integration with MCP servers to extend agent capabilities
with external tools and services.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class MCPServerConfig:
    """Configuration for an MCP server connection."""

    def __init__(
        self,
        name: str,
        transport: str,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        enabled: bool = True
    ):
        """
        Initialize MCP server configuration.

        Args:
            name: Server identifier
            transport: Transport type ("stdio" or "streamable_http")
            command: Command to start server (for stdio)
            args: Command arguments (for stdio)
            url: Server URL (for HTTP)
            headers: HTTP headers (for HTTP)
            enabled: Whether server is enabled
        """
        self.name = name
        self.transport = transport
        self.command = command
        self.args = args or []
        self.url = url
        self.headers = headers or {}
        self.enabled = enabled

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary format."""
        config = {
            "transport": self.transport,
        }

        if self.transport == "stdio":
            if self.command:
                config["command"] = self.command
            if self.args:
                config["args"] = self.args
        elif self.transport == "streamable_http":
            if self.url:
                config["url"] = self.url
            if self.headers:
                config["headers"] = self.headers

        return config


class MCPClientManager:
    """
    Manager for MCP server connections and tool discovery.

    Handles connections to multiple MCP servers and provides
    unified access to their tools.
    """

    def __init__(self):
        """Initialize the MCP client manager."""
        self._servers: Dict[str, MCPServerConfig] = {}
        self._client: Optional[Any] = None  # MultiServerMCPClient instance
        self._tools_cache: Optional[List[Any]] = None
        self._last_refresh: Optional[datetime] = None

    def register_server(self, config: MCPServerConfig):
        """
        Register an MCP server.

        Args:
            config: MCP server configuration
        """
        self._servers[config.name] = config
        self._tools_cache = None  # Invalidate cache

        logger.info(f"Registered MCP server: {config.name} ({config.transport})")

    def unregister_server(self, name: str):
        """
        Unregister an MCP server.

        Args:
            name: Server name
        """
        if name in self._servers:
            del self._servers[name]
            self._tools_cache = None  # Invalidate cache

            logger.info(f"Unregistered MCP server: {name}")

    def get_server(self, name: str) -> Optional[MCPServerConfig]:
        """
        Get MCP server configuration.

        Args:
            name: Server name

        Returns:
            Server configuration or None
        """
        return self._servers.get(name)

    def get_all_servers(self) -> List[MCPServerConfig]:
        """
        Get all registered servers.

        Returns:
            List of server configurations
        """
        return list(self._servers.values())

    def get_enabled_servers(self) -> List[MCPServerConfig]:
        """
        Get all enabled servers.

        Returns:
            List of enabled server configurations
        """
        return [config for config in self._servers.values() if config.enabled]

    async def initialize_client(self):
        """
        Initialize the MultiServerMCPClient with registered servers.

        This creates connections to all enabled MCP servers.
        """
        try:
            # Import here to avoid import errors if package not installed
            from langchain_mcp_adapters.client import MultiServerMCPClient

            # Build server config dict for MultiServerMCPClient
            enabled_servers = self.get_enabled_servers()

            if not enabled_servers:
                logger.info("No enabled MCP servers - skipping client initialization")
                return

            server_configs = {
                config.name: config.to_dict()
                for config in enabled_servers
            }

            # Initialize client
            self._client = MultiServerMCPClient(server_configs)

            logger.info(f"Initialized MCP client with {len(enabled_servers)} servers")

        except ImportError:
            logger.warning(
                "langchain-mcp-adapters not installed - MCP integration unavailable. "
                "Install with: uv add langchain-mcp-adapters"
            )
            self._client = None

        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}", exc_info=True)
            self._client = None

    async def get_tools(self, force_refresh: bool = False) -> List[Any]:
        """
        Get all tools from all registered MCP servers.

        Args:
            force_refresh: Force refresh tools from servers

        Returns:
            List of LangChain-compatible tools
        """
        # Return cached tools if available
        if not force_refresh and self._tools_cache is not None:
            logger.debug("Returning cached MCP tools")
            return self._tools_cache

        # Initialize client if needed
        if self._client is None:
            await self.initialize_client()

        # If still no client, return empty list
        if self._client is None:
            logger.warning("MCP client not available - returning empty tool list")
            return []

        try:
            # Get tools from all servers
            tools = await self._client.get_tools()

            # Cache the tools
            self._tools_cache = tools
            self._last_refresh = datetime.now()

            logger.info(f"Fetched {len(tools)} tools from MCP servers")
            return tools

        except Exception as e:
            logger.error(f"Failed to fetch MCP tools: {e}", exc_info=True)
            return []

    async def get_prompts(self) -> List[Any]:
        """
        Get all prompts from registered MCP servers.

        Returns:
            List of prompts from MCP servers
        """
        if self._client is None:
            await self.initialize_client()

        if self._client is None:
            return []

        try:
            prompts = await self._client.get_prompts()
            logger.info(f"Fetched {len(prompts)} prompts from MCP servers")
            return prompts

        except Exception as e:
            logger.error(f"Failed to fetch MCP prompts: {e}", exc_info=True)
            return []

    async def get_resources(self) -> List[Any]:
        """
        Get all resources from registered MCP servers.

        Returns:
            List of resources from MCP servers
        """
        if self._client is None:
            await self.initialize_client()

        if self._client is None:
            return []

        try:
            resources = await self._client.get_resources()
            logger.info(f"Fetched {len(resources)} resources from MCP servers")
            return resources

        except Exception as e:
            logger.error(f"Failed to fetch MCP resources: {e}", exc_info=True)
            return []

    def get_server_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered MCP servers.

        Returns:
            Dictionary of server information
        """
        server_info = {}

        for name, config in self._servers.items():
            server_info[name] = {
                "name": name,
                "transport": config.transport,
                "enabled": config.enabled,
                "command": config.command if config.transport == "stdio" else None,
                "url": config.url if config.transport == "streamable_http" else None,
            }

        return server_info


# Global MCP client manager instance
_mcp_client_manager: Optional[MCPClientManager] = None


def get_mcp_client_manager() -> MCPClientManager:
    """
    Get the global MCP client manager instance.

    Returns:
        MCPClientManager instance
    """
    global _mcp_client_manager

    if _mcp_client_manager is None:
        _mcp_client_manager = MCPClientManager()

    return _mcp_client_manager


# Example MCP server configurations
def register_example_servers():
    """
    Register example MCP servers for reference.

    These are example configurations - actual servers need to be
    configured based on your deployment.
    """
    manager = get_mcp_client_manager()

    # Example: Math server via stdio
    # manager.register_server(MCPServerConfig(
    #     name="math",
    #     transport="stdio",
    #     command="python",
    #     args=["/path/to/math_server.py"],
    #     enabled=False  # Disabled by default
    # ))

    # Example: Weather server via HTTP
    # manager.register_server(MCPServerConfig(
    #     name="weather",
    #     transport="streamable_http",
    #     url="http://localhost:8000/mcp",
    #     headers={"Authorization": "Bearer YOUR_TOKEN"},
    #     enabled=False  # Disabled by default
    # ))

    logger.info("Example MCP server configurations registered (disabled)")
