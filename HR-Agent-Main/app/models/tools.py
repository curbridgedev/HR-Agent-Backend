"""
Pydantic models for tool management API.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo
from app.models.base import BaseRequest, BaseResponse


# ============================================================================
# Tool Models
# ============================================================================


class ToolConfig(BaseModel):
    """Tool configuration."""

    name: str = Field(..., description="Tool name")
    category: str = Field(..., description="Tool category (math, finance, search, utility)")
    description: Optional[str] = Field(None, description="Tool description")
    enabled: bool = Field(True, description="Whether tool is enabled")
    config: Dict[str, Any] = Field(default_factory=dict, description="Tool-specific configuration")


class ToolInfo(BaseModel):
    """Tool information with usage statistics."""

    id: str = Field(..., description="Tool ID")
    name: str = Field(..., description="Tool name")
    category: str = Field(..., description="Tool category")
    description: Optional[str] = Field(None, description="Tool description")
    enabled: bool = Field(..., description="Whether tool is enabled")
    config: Dict[str, Any] = Field(default_factory=dict, description="Tool configuration")

    # Usage statistics
    invocation_count: int = Field(0, description="Total invocations")
    success_count: int = Field(0, description="Successful invocations")
    failure_count: int = Field(0, description="Failed invocations")
    success_rate_percent: Optional[float] = Field(None, description="Success rate percentage")
    avg_execution_time_ms: Optional[float] = Field(None, description="Average execution time")
    last_invoked_at: Optional[datetime] = Field(None, description="Last invocation time")
    last_error: Optional[str] = Field(None, description="Last error message")
    last_error_at: Optional[datetime] = Field(None, description="Last error time")

    # Audit
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @model_validator(mode="after")
    def mask_sensitive_config(self) -> "ToolInfo":
        """Mask sensitive configuration values in API responses."""
        if self.config:
            from app.utils.encryption import mask_sensitive_value, is_encrypted

            masked_config = {}
            sensitive_keys = ["api_key", "api_secret", "password", "token", "secret"]

            for key, value in self.config.items():
                if isinstance(value, str) and any(sensitive in key.lower() for sensitive in sensitive_keys):
                    # Mask the value
                    if is_encrypted(value):
                        masked_config[key] = "encrypted:****"
                    else:
                        masked_config[key] = mask_sensitive_value(value)
                else:
                    masked_config[key] = value

            self.config = masked_config

        return self


class ToolListResponse(BaseResponse):
    """Response for list tools endpoint."""

    tools: List[ToolInfo] = Field(..., description="List of tools")
    total: int = Field(..., description="Total number of tools")
    enabled_count: int = Field(..., description="Number of enabled tools")
    disabled_count: int = Field(..., description="Number of disabled tools")


class ToolUpdateRequest(BaseRequest):
    """Request to update tool configuration."""

    enabled: Optional[bool] = Field(None, description="Enable/disable tool")
    config: Optional[Dict[str, Any]] = Field(None, description="Tool configuration")
    description: Optional[str] = Field(None, description="Tool description")


class ToolUsageStats(BaseModel):
    """Tool usage statistics."""

    tool_name: str = Field(..., description="Tool name")
    category: str = Field(..., description="Tool category")
    invocation_count: int = Field(..., description="Total invocations")
    success_count: int = Field(..., description="Successful invocations")
    failure_count: int = Field(..., description="Failed invocations")
    success_rate_percent: float = Field(..., description="Success rate percentage")
    avg_execution_time_ms: Optional[float] = Field(None, description="Average execution time")


# ============================================================================
# MCP Server Models
# ============================================================================


class MCPServerConfig(BaseModel):
    """
    MCP server configuration (remote HTTP-only).

    For security and scalability, only remote HTTP servers are supported.
    Users must host their own MCP servers or use cloud providers.
    """

    name: str = Field(..., description="Server name")
    description: Optional[str] = Field(None, description="Server description")
    enabled: bool = Field(True, description="Whether server is enabled")

    # Remote HTTP transport only
    url: str = Field(..., description="Server URL (must be HTTP/HTTPS)")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers for authentication")

    # Additional config
    config: Dict[str, Any] = Field(default_factory=dict, description="Additional configuration")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @model_validator(mode="after")
    def mask_sensitive_values(self) -> "MCPServerConfig":
        """Mask sensitive values in headers and config."""
        from app.utils.encryption import mask_sensitive_value, is_encrypted

        sensitive_keys = ["authorization", "api_key", "api_secret", "password", "token", "secret", "bearer"]

        # Mask sensitive headers
        if self.headers:
            masked_headers = {}
            for key, value in self.headers.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    if is_encrypted(value):
                        masked_headers[key] = "encrypted:****"
                    else:
                        masked_headers[key] = mask_sensitive_value(value)
                else:
                    masked_headers[key] = value
            self.headers = masked_headers

        # Mask sensitive config values
        if self.config:
            masked_config = {}
            for key, value in self.config.items():
                if isinstance(value, str) and any(sensitive in key.lower() for sensitive in sensitive_keys):
                    if is_encrypted(value):
                        masked_config[key] = "encrypted:****"
                    else:
                        masked_config[key] = mask_sensitive_value(value)
                else:
                    masked_config[key] = value
            self.config = masked_config

        return self


class MCPServerInfo(BaseModel):
    """MCP server information with health status."""

    id: str = Field(..., description="Server ID")
    name: str = Field(..., description="Server name")
    description: Optional[str] = Field(None, description="Server description")
    enabled: bool = Field(..., description="Whether server is enabled")
    transport: str = Field(..., description="Transport protocol")

    # Connection details
    command: Optional[str] = Field(None, description="Command (stdio)")
    args: Optional[List[str]] = Field(None, description="Arguments (stdio)")
    url: Optional[str] = Field(None, description="URL (HTTP)")

    # Health status
    tools_discovered: int = Field(0, description="Number of tools discovered")
    last_connected_at: Optional[datetime] = Field(None, description="Last connection time")
    last_connection_error: Optional[str] = Field(None, description="Last connection error")
    last_connection_error_at: Optional[datetime] = Field(None, description="Last error time")
    connection_attempts: int = Field(0, description="Total connection attempts")
    successful_connections: int = Field(0, description="Successful connections")
    connection_success_rate_percent: Optional[float] = Field(
        None, description="Connection success rate"
    )
    last_tool_refresh_at: Optional[datetime] = Field(None, description="Last tool refresh time")

    # Audit
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class MCPServerListResponse(BaseResponse):
    """Response for list MCP servers endpoint."""

    servers: List[MCPServerInfo] = Field(..., description="List of MCP servers")
    total: int = Field(..., description="Total number of servers")
    enabled_count: int = Field(..., description="Number of enabled servers")
    disabled_count: int = Field(..., description="Number of disabled servers")


class MCPServerCreateRequest(BaseRequest):
    """Request to register MCP server."""

    config: MCPServerConfig = Field(..., description="Server configuration")


class MCPServerUpdateRequest(BaseRequest):
    """Request to update MCP server configuration."""

    enabled: Optional[bool] = Field(None, description="Enable/disable server")
    description: Optional[str] = Field(None, description="Server description")
    config: Optional[Dict[str, Any]] = Field(None, description="Additional configuration")


class MCPServerToolInfo(BaseModel):
    """Tool discovered from MCP server."""

    id: str = Field(..., description="Tool ID")
    mcp_server_id: str = Field(..., description="MCP server ID")
    tool_name: str = Field(..., description="Tool name")
    tool_description: Optional[str] = Field(None, description="Tool description")
    tool_schema: Optional[Dict[str, Any]] = Field(None, description="Tool parameter schema")

    # Usage statistics
    invocation_count: int = Field(0, description="Total invocations")
    success_count: int = Field(0, description="Successful invocations")
    failure_count: int = Field(0, description="Failed invocations")
    avg_execution_time_ms: Optional[float] = Field(None, description="Average execution time")

    # Discovery tracking
    discovered_at: datetime = Field(..., description="Discovery timestamp")
    last_seen_at: datetime = Field(..., description="Last seen timestamp")


# ============================================================================
# Tool Invocation Models
# ============================================================================


class ToolInvocationLog(BaseModel):
    """Tool invocation log entry."""

    id: str = Field(..., description="Log entry ID")
    tool_name: str = Field(..., description="Tool name")
    tool_type: str = Field(..., description="Tool type (builtin or mcp)")
    session_id: Optional[str] = Field(None, description="Session ID")
    query: Optional[str] = Field(None, description="Query that triggered invocation")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    success: bool = Field(..., description="Whether invocation succeeded")
    result: Optional[str] = Field(None, description="Tool result")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time_ms: Optional[int] = Field(None, description="Execution time")
    invoked_at: datetime = Field(..., description="Invocation timestamp")


class ToolInvocationLogsResponse(BaseResponse):
    """Response for tool invocation logs endpoint."""

    logs: List[ToolInvocationLog] = Field(..., description="List of invocation logs")
    total: int = Field(..., description="Total number of logs")
    success_count: int = Field(..., description="Number of successful invocations")
    failure_count: int = Field(..., description="Number of failed invocations")


# ============================================================================
# Analytics Models
# ============================================================================


class ToolAnalytics(BaseModel):
    """Tool usage analytics."""

    total_tools: int = Field(..., description="Total number of tools")
    enabled_tools: int = Field(..., description="Number of enabled tools")
    total_invocations: int = Field(..., description="Total invocations")
    successful_invocations: int = Field(..., description="Successful invocations")
    failed_invocations: int = Field(..., description="Failed invocations")
    overall_success_rate: float = Field(..., description="Overall success rate")

    # Top tools
    most_used_tools: List[ToolUsageStats] = Field(..., description="Most frequently used tools")
    tools_by_category: Dict[str, int] = Field(..., description="Tool count by category")


class MCPServerAnalytics(BaseModel):
    """MCP server analytics."""

    total_servers: int = Field(..., description="Total number of servers")
    enabled_servers: int = Field(..., description="Number of enabled servers")
    total_tools_discovered: int = Field(..., description="Total tools discovered")
    total_connection_attempts: int = Field(..., description="Total connection attempts")
    successful_connections: int = Field(..., description="Successful connections")
    overall_connection_success_rate: float = Field(
        ..., description="Overall connection success rate"
    )
