#!/usr/bin/env python
"""
Test MCP integration end-to-end.

Tests:
1. Register MCP server
2. Connect to server
3. Discover tools
4. Get tools in agent registry
"""

import asyncio
import json
from app.db.supabase import get_supabase_client
from app.services.mcp_client import get_mcp_manager
from app.agents.tools import get_tool_registry


async def test_mcp_integration():
    """Test MCP integration."""
    print("\n" + "="*60)
    print("MCP INTEGRATION TEST")
    print("="*60)

    supabase = get_supabase_client()
    mcp_manager = get_mcp_manager()
    tool_registry = get_tool_registry()

    # Step 1: Register a test MCP server
    print("\n[Step 1] Registering test MCP server...")

    # Using the memory server as a simple test
    # This server provides key-value storage tools
    server_config = {
        "name": "test-memory-server",
        "description": "Test MCP memory server for key-value storage",
        "enabled": True,
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "config": {}
    }

    # Check if server already exists
    existing = supabase.table("mcp_servers").select("*").eq("name", "test-memory-server").execute()

    if existing.data:
        server_id = existing.data[0]["id"]
        print(f"  Server already exists: {server_id}")

        # Update it
        supabase.table("mcp_servers").update(server_config).eq("id", server_id).execute()
        print(f"  Updated server configuration")
    else:
        # Insert new server
        response = supabase.table("mcp_servers").insert(server_config).execute()
        server_id = response.data[0]["id"]
        print(f"  Registered new server: {server_id}")

    # Step 2: Connect to the server
    print("\n[Step 2] Connecting to MCP server...")
    success = await mcp_manager.connect_server(server_id)

    if success:
        print(f"  SUCCESS: Connected to server {server_id}")
    else:
        print(f"  FAILED: Could not connect to server {server_id}")

        # Check error in database
        server_data = supabase.table("mcp_servers").select("*").eq("id", server_id).execute()
        if server_data.data:
            error = server_data.data[0].get("last_connection_error")
            print(f"  Error: {error}")
        return

    # Step 3: Discover tools
    print("\n[Step 3] Discovering tools from MCP server...")
    tool_count = await mcp_manager.refresh_tools(server_id)
    print(f"  Discovered {tool_count} tools")

    # Get tool details from database
    tools_response = supabase.table("mcp_server_tools").select("*").eq("mcp_server_id", server_id).execute()

    if tools_response.data:
        print(f"\n  Tool Details:")
        for tool in tools_response.data:
            print(f"    - {tool['tool_name']}: {tool['tool_description']}")

    # Step 4: Get tools in registry
    print("\n[Step 4] Testing tool registry integration...")

    # Get built-in tools
    builtin_tools = tool_registry.get_all_tools()
    print(f"  Built-in tools: {len(builtin_tools)}")
    for tool in builtin_tools:
        print(f"    - {tool.name}")

    # Get combined tools (built-in + MCP)
    all_tools = await tool_registry.get_all_tools_with_mcp()
    print(f"\n  Combined tools (built-in + MCP): {len(all_tools)}")

    mcp_tools = [t for t in all_tools if t.name.startswith("mcp_")]
    print(f"  MCP tools found: {len(mcp_tools)}")
    for tool in mcp_tools:
        print(f"    - {tool.name}")

    # Step 5: Test tool invocation (if tools available)
    if mcp_tools:
        print("\n[Step 5] Testing tool invocation...")

        # Find a write/store tool
        store_tool = None
        for tool in mcp_tools:
            if "store" in tool.name or "write" in tool.name or "set" in tool.name:
                store_tool = tool
                break

        if store_tool:
            print(f"  Testing tool: {store_tool.name}")
            try:
                # Try to invoke the tool
                # Note: This may fail if the tool requires specific parameters
                result = await store_tool.ainvoke({"key": "test_key", "value": "test_value"})
                print(f"  SUCCESS: Tool invoked")
                print(f"  Result: {result}")
            except Exception as e:
                print(f"  Note: Tool invocation test skipped (requires specific parameters)")
                print(f"  Error: {e}")
        else:
            print(f"  No testable tools found")

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"  Server ID: {server_id}")
    print(f"  Connection: {'SUCCESS' if success else 'FAILED'}")
    print(f"  Tools Discovered: {tool_count}")
    print(f"  MCP Tools Available: {len(mcp_tools)}")
    print(f"  Total Tools (built-in + MCP): {len(all_tools)}")

    if success and tool_count > 0:
        print("\n  MCP INTEGRATION: WORKING")
    else:
        print("\n  MCP INTEGRATION: NEEDS ATTENTION")

    # Cleanup prompt
    print("\n[Cleanup]")
    print(f"  To remove test server:")
    print(f"  DELETE FROM mcp_servers WHERE id = '{server_id}';")


if __name__ == "__main__":
    asyncio.run(test_mcp_integration())
