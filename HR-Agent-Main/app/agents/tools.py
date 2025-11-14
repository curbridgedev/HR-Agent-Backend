"""
Built-in tools for the Compaytence AI Agent.

Provides calculator, web search, and other utility tools that can be
invoked by the agent during query processing.
"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime
import math

from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.encryption import get_decrypted_config_value

logger = get_logger(__name__)


# ============================================================================
# Calculator Tools
# ============================================================================

@tool
async def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression safely.

    Args:
        expression: Mathematical expression to evaluate (e.g., "3 + 5 * 2")

    Returns:
        Result of the calculation as a string

    Examples:
        calculator("3 + 5 * 2") -> "13"
        calculator("sqrt(16)") -> "4.0"
        calculator("2 ** 8") -> "256"

    Supported operations:
        - Basic: +, -, *, /, //, %, **
        - Functions: sqrt, sin, cos, tan, log, log10, exp, abs, round
        - Constants: pi, e
    """
    try:
        # Safe evaluation context with math functions
        safe_context = {
            "__builtins__": {},
            "abs": abs,
            "round": round,
            "max": max,
            "min": min,
            "sum": sum,
            "pow": pow,
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
            "exp": math.exp,
            "pi": math.pi,
            "e": math.e,
        }

        # Evaluate expression safely
        result = eval(expression, safe_context, {})

        logger.info(f"Calculator: {expression} = {result}")
        return str(result)

    except ZeroDivisionError:
        error_msg = "Error: Division by zero"
        logger.warning(f"Calculator error: {error_msg}")
        return error_msg

    except Exception as e:
        error_msg = f"Error: Invalid expression - {str(e)}"
        logger.error(f"Calculator error: {error_msg}", exc_info=True)
        return error_msg


@tool
async def currency_converter(
    amount: float,
    from_currency: str,
    to_currency: str
) -> str:
    """
    Convert currency amounts (uses current exchange rates from query knowledge).

    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., "USD")
        to_currency: Target currency code (e.g., "EUR")

    Returns:
        Converted amount as a string

    Note:
        This is a placeholder that returns guidance to check exchange rates.
        In production, this would integrate with a real exchange rate API.
    """
    logger.info(f"Currency conversion requested: {amount} {from_currency} to {to_currency}")

    return (
        f"To convert {amount} {from_currency} to {to_currency}, please check current "
        f"exchange rates. I can help you find this information in our knowledge base "
        f"or you can use a real-time exchange rate service."
    )


# ============================================================================
# Web Search Tool
# ============================================================================

def get_web_search_tool(config: Optional[Dict[str, Any]] = None) -> Optional[TavilySearchResults]:
    """
    Get Tavily web search tool if API key is configured.

    Priority for API key:
    1. Encrypted/plain value in config dict (from database)
    2. Environment variable TAVILY_API_KEY

    Args:
        config: Optional configuration dict from database (tools.config)

    Returns:
        TavilySearchResults tool or None if not configured
    """
    # Get API key from config (database) or environment
    config_dict = config or {}
    tavily_api_key = get_decrypted_config_value(
        config_dict,
        "api_key",
        fallback_env_var="tavily_api_key"
    )

    if not tavily_api_key:
        logger.warning("Tavily API key not configured - web search tool unavailable")
        return None

    # Get tool configuration with defaults
    max_results = config_dict.get("max_results", 5)
    search_depth = config_dict.get("search_depth", "advanced")

    try:
        search_tool = TavilySearchResults(
            max_results=max_results,
            search_depth=search_depth,
            include_answer=True,
            include_raw_content=False,
            include_images=False,
            tavily_api_key=tavily_api_key,
        )

        logger.info(f"Tavily web search tool initialized (max_results={max_results}, search_depth={search_depth})")
        return search_tool

    except Exception as e:
        logger.error(f"Failed to initialize Tavily search tool: {e}", exc_info=True)
        return None


# ============================================================================
# Time and Date Tools
# ============================================================================

@tool
async def get_current_time(timezone: str = "UTC") -> str:
    """
    Get the current time and date.

    Args:
        timezone: Timezone for the time (default: "UTC")

    Returns:
        Current time and date as a formatted string

    Examples:
        get_current_time() -> "2025-01-31 18:30:45 UTC"
        get_current_time("America/New_York") -> "2025-01-31 13:30:45 EST"
    """
    try:
        # For now, return UTC time
        # In production, this would handle timezone conversion
        current_time = datetime.now()

        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        result = f"{formatted_time} {timezone}"

        logger.info(f"Current time requested: {result}")
        return result

    except Exception as e:
        error_msg = f"Error getting current time: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


# ============================================================================
# Tool Registry
# ============================================================================

class ToolRegistry:
    """
    Central registry for managing available tools.

    Provides methods to register, retrieve, and manage tools
    that can be invoked by the agent.
    """

    def __init__(self):
        """Initialize the tool registry with built-in tools."""
        self._tools: Dict[str, Any] = {}
        self._tool_metadata: Dict[str, Dict[str, Any]] = {}

        # Register built-in tools
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """Register all built-in tools."""
        # Math tools
        self.register_tool(
            calculator,
            category="math",
            description="Evaluate mathematical expressions safely",
            enabled=True
        )

        self.register_tool(
            currency_converter,
            category="finance",
            description="Convert between currencies",
            enabled=True
        )

        # Time tools
        self.register_tool(
            get_current_time,
            category="utility",
            description="Get current time and date",
            enabled=True
        )

        # Web search tool - load config from database
        try:
            from app.db.supabase import get_supabase_client

            supabase = get_supabase_client()
            response = supabase.table("tools").select("*").eq("name", "tavily_search").execute()

            if response.data:
                tool_data = response.data[0]
                config = tool_data.get("config", {})
                enabled = tool_data.get("enabled", False)

                web_search = get_web_search_tool(config)
                if web_search:
                    self.register_tool(
                        web_search,
                        category="search",
                        description="Search the web for real-time information",
                        enabled=enabled
                    )
                    logger.info("Registered tavily_search tool from database config")
            else:
                # Fallback to environment variable if no database config
                web_search = get_web_search_tool()
                if web_search:
                    self.register_tool(
                        web_search,
                        category="search",
                        description="Search the web for real-time information",
                        enabled=True
                    )
                    logger.info("Registered tavily_search tool from environment variable")

        except Exception as e:
            logger.error(f"Failed to load tavily_search from database: {e}", exc_info=True)
            # Fallback to environment variable
            web_search = get_web_search_tool()
            if web_search:
                self.register_tool(
                    web_search,
                    category="search",
                    description="Search the web for real-time information",
                    enabled=True
                )

        logger.info(f"Registered {len(self._tools)} built-in tools")

    def register_tool(
        self,
        tool: Any,
        category: str = "general",
        description: Optional[str] = None,
        enabled: bool = True
    ):
        """
        Register a tool in the registry.

        Args:
            tool: The tool instance (LangChain tool)
            category: Tool category (math, finance, search, utility, etc.)
            description: Optional description override
            enabled: Whether the tool is enabled
        """
        tool_name = tool.name

        self._tools[tool_name] = tool
        self._tool_metadata[tool_name] = {
            "category": category,
            "description": description or getattr(tool, "description", ""),
            "enabled": enabled,
            "registered_at": datetime.now().isoformat()
        }

        logger.debug(f"Registered tool: {tool_name} (category: {category})")

    def get_tool(self, name: str) -> Optional[Any]:
        """
        Get a specific tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def get_all_tools(self, enabled_only: bool = True) -> List[Any]:
        """
        Get all registered tools (built-in only).

        Args:
            enabled_only: Only return enabled tools

        Returns:
            List of tool instances
        """
        if not enabled_only:
            return list(self._tools.values())

        enabled_tools = [
            tool for name, tool in self._tools.items()
            if self._tool_metadata[name]["enabled"]
        ]

        return enabled_tools

    async def get_all_tools_with_mcp(self, enabled_only: bool = True) -> List[Any]:
        """
        Get all tools including built-in and MCP tools.

        Args:
            enabled_only: Only return enabled tools

        Returns:
            List of tool instances (built-in + MCP)
        """
        # Get built-in tools
        builtin_tools = self.get_all_tools(enabled_only)

        # Get MCP tools
        try:
            from app.services.mcp_client import get_mcp_manager

            mcp_manager = get_mcp_manager()
            mcp_tools = await mcp_manager.get_all_tools()

            # Combine both
            all_tools = builtin_tools + mcp_tools
            logger.info(f"Combined tools: {len(builtin_tools)} built-in + {len(mcp_tools)} MCP = {len(all_tools)} total")

            return all_tools

        except Exception as e:
            logger.error(f"Failed to get MCP tools: {e}", exc_info=True)
            # Return only built-in tools if MCP fails
            return builtin_tools

    def get_tools_by_category(self, category: str) -> List[Any]:
        """
        Get all tools in a specific category.

        Args:
            category: Tool category

        Returns:
            List of tool instances in the category
        """
        tools = [
            tool for name, tool in self._tools.items()
            if self._tool_metadata[name]["category"] == category
            and self._tool_metadata[name]["enabled"]
        ]

        return tools

    def enable_tool(self, name: str):
        """Enable a tool."""
        if name in self._tool_metadata:
            self._tool_metadata[name]["enabled"] = True
            logger.info(f"Enabled tool: {name}")

    def disable_tool(self, name: str):
        """Disable a tool."""
        if name in self._tool_metadata:
            self._tool_metadata[name]["enabled"] = False
            logger.info(f"Disabled tool: {name}")

    def get_tool_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered tools.

        Returns:
            Dictionary of tool information
        """
        tool_info = {}

        for name, tool in self._tools.items():
            metadata = self._tool_metadata[name]
            tool_info[name] = {
                "name": name,
                "category": metadata["category"],
                "description": metadata["description"],
                "enabled": metadata["enabled"],
                "registered_at": metadata["registered_at"],
            }

        return tool_info

    async def refresh_tool_from_db(self, tool_name: str):
        """
        Refresh a specific tool with latest database configuration.

        Queries the database for the tool's config and re-initializes it.
        This allows dynamic updates when API keys or config changes.

        Args:
            tool_name: Name of the tool to refresh
        """
        try:
            from app.db.supabase import get_supabase_client

            supabase = get_supabase_client()

            # Query database for tool config
            response = supabase.table("tools").select("*").eq("name", tool_name).execute()

            if not response.data:
                logger.warning(f"Tool {tool_name} not found in database")
                return

            tool_data = response.data[0]
            config = tool_data.get("config", {})
            enabled = tool_data.get("enabled", False)

            # Re-initialize tool based on type
            if tool_name == "tavily_search":
                # Remove old tool if exists
                if tool_name in self._tools:
                    del self._tools[tool_name]
                    del self._tool_metadata[tool_name]

                # Re-initialize with database config
                web_search = get_web_search_tool(config)
                if web_search:
                    self.register_tool(
                        web_search,
                        category="search",
                        description="Search the web for real-time information",
                        enabled=enabled
                    )
                    logger.info(f"Refreshed tool {tool_name} from database config")
                else:
                    logger.warning(f"Failed to initialize {tool_name} with database config")

        except Exception as e:
            logger.error(f"Failed to refresh tool {tool_name} from database: {e}", exc_info=True)


# Global tool registry instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry instance.

    Returns:
        ToolRegistry instance
    """
    global _tool_registry

    if _tool_registry is None:
        _tool_registry = ToolRegistry()

    return _tool_registry
