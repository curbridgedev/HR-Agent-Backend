#!/usr/bin/env python
"""
Simple HTTP MCP Server for Testing.

Runs a minimal MCP server with HTTP transport for testing the HTTP-only client.
"""

import asyncio
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import Response
import uvicorn


# Create MCP server instance
mcp_server = Server("test-http-mcp")


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="echo",
            description="Echo back the input message",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo back"
                    }
                },
                "required": ["message"]
            }
        ),
        Tool(
            name="add_numbers",
            description="Add two numbers together",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        ),
        Tool(
            name="get_time",
            description="Get current server time",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name == "echo":
        message = arguments.get("message", "")
        return [TextContent(type="text", text=f"Echo: {message}")]

    elif name == "add_numbers":
        a = arguments.get("a", 0)
        b = arguments.get("b", 0)
        result = a + b
        return [TextContent(type="text", text=f"{a} + {b} = {result}")]

    elif name == "get_time":
        from datetime import datetime
        current_time = datetime.now().isoformat()
        return [TextContent(type="text", text=f"Server time: {current_time}")]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_sse(request):
    """Handle SSE endpoint for MCP."""
    from starlette.responses import StreamingResponse

    async def event_generator():
        async with SseServerTransport("/messages") as transport:
            async with mcp_server.session(transport.read_stream, transport.write_stream):
                await asyncio.sleep(100)  # Keep connection alive
                yield ""

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# Create Starlette app
app = Starlette(
    debug=True,
    routes=[
        Route("/mcp", endpoint=handle_sse),
    ]
)


if __name__ == "__main__":
    print("=" * 60)
    print("SIMPLE HTTP MCP SERVER")
    print("=" * 60)
    print("\nServer URL: http://localhost:3000/mcp")
    print("\nAvailable Tools:")
    print("  - echo: Echo back a message")
    print("  - add_numbers: Add two numbers")
    print("  - get_time: Get current server time")
    print("\nPress Ctrl+C to stop")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=3000, log_level="info")
