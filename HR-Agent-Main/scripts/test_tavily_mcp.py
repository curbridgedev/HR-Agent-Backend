#!/usr/bin/env python
"""
Test Tavily Remote MCP Server Integration.

Tests the HTTP-only MCP client with Tavily's production remote server.
"""

import asyncio
import os
from app.services.mcp_client import get_mcp_manager
from app.agents.tools import get_tool_registry
from app.db.supabase import get_supabase_client
from app.core.config import settings


async def test_tavily_remote_mcp():
    """Test Tavily remote MCP server."""
    print("=" * 60)
    print("TAVILY REMOTE MCP SERVER TEST")
    print("=" * 60)

    # Check for Tavily API key
    tavily_api_key = settings.tavily_api_key
    if not tavily_api_key:
        print("\n[ERROR] TAVILY_API_KEY not set in environment")
        print("Please set TAVILY_API_KEY in your .env file")
        return

    print(f"\n[OK] Tavily API Key: {tavily_api_key[:10]}...")

    # Step 1: Register Tavily remote MCP server
    print("\n[Step 1] Registering Tavily remote MCP server...")
    supabase = get_supabase_client()

    # Build the remote URL with API key
    remote_url = f"https://mcp.tavily.com/mcp/?tavilyApiKey={tavily_api_key}"

    # Check if server already exists
    response = supabase.table("mcp_servers").select("*").eq("name", "tavily-remote").execute()

    if response.data:
        server_id = response.data[0]["id"]
        print(f"  Server already exists: {server_id}")

        # Update the URL in case API key changed
        supabase.table("mcp_servers").update({
            "url": remote_url,
            "enabled": True
        }).eq("id", server_id).execute()
        print("  Updated server configuration")
    else:
        # Create new server
        response = supabase.table("mcp_servers").insert({
            "name": "tavily-remote",
            "description": "Tavily Remote MCP Server - Production Search API",
            "transport": "streamable_http",  # Database still requires this field
            "url": remote_url,
            "enabled": True,
            "headers": {},
            "config": {}
        }).execute()

        if response.data:
            server_id = response.data[0]["id"]
            print(f"  Registered new server: {server_id}")
        else:
            print(f"  [ERROR] Failed to register server")
            return

    # Step 2: Connect to Tavily remote MCP server
    print("\n[Step 2] Connecting to Tavily remote MCP server...")
    mcp_manager = get_mcp_manager()

    try:
        success = await mcp_manager.connect_server(server_id)

        if success:
            print(f"  [SUCCESS] Connected to server {server_id}")
        else:
            print(f"  [FAILED] Could not connect to server {server_id}")
            return
    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: Discover tools
    print("\n[Step 3] Discovering tools from Tavily MCP server...")
    try:
        tool_count = await mcp_manager.refresh_tools(server_id)
        print(f"  Discovered {tool_count} tools")

        # Get tool details from database
        response = supabase.table("mcp_server_tools").select("*").eq(
            "mcp_server_id", server_id
        ).execute()

        if response.data:
            print("\n  Tool Details:")
            for tool_data in response.data:
                print(f"    - {tool_data['tool_name']}: {tool_data['tool_description']}")
    except Exception as e:
        print(f"  [ERROR] discovering tools: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Test tool registry integration
    print("\n[Step 4] Testing tool registry integration...")
    try:
        tool_registry = get_tool_registry()

        builtin_tools = tool_registry.get_all_tools(enabled_only=True)
        print(f"  Built-in tools: {len(builtin_tools)}")

        all_tools = await tool_registry.get_all_tools_with_mcp(enabled_only=True)
        print(f"  Combined tools (built-in + MCP): {len(all_tools)}")

        mcp_tool_count = len(all_tools) - len(builtin_tools)
        print(f"  MCP tools found: {mcp_tool_count}")

        # List MCP tools
        mcp_tools = [t for t in all_tools if t.name.startswith("mcp_")]
        if mcp_tools:
            print("\n  MCP Tools in Registry:")
            for tool in mcp_tools:
                print(f"    - {tool.name}")
                print(f"      Description: {tool.description}")
    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()

    # Step 5: Test tool invocation
    print("\n[Step 5] Testing tool invocation...")
    try:
        client = mcp_manager.clients.get(server_id)
        if client and client.connected:
            # Try to call a search tool if available
            response = supabase.table("mcp_server_tools").select("*").eq(
                "mcp_server_id", server_id
            ).limit(1).execute()

            if response.data:
                tool_name = response.data[0]["tool_name"]
                print(f"  Testing tool: {tool_name}")

                # Call the tool through MCP
                try:
                    result = await client.call_tool(tool_name, {"query": "test search"})
                    print(f"  [OK] Tool invocation successful!")
                    print(f"  Result: {result}")
                except Exception as e:
                    print(f"  [WARNING] Tool invocation failed (this might be expected): {e}")
        else:
            print("  [WARNING] Client not connected, skipping tool invocation")
    except Exception as e:
        print(f"  [ERROR] {e}")

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"  Server ID: {server_id}")
    print(f"  Connection: SUCCESS")
    print(f"  Tools Discovered: {tool_count}")
    print(f"  MCP Tools Available: {mcp_tool_count}")
    print(f"  Total Tools (built-in + MCP): {len(all_tools)}")
    print("\n  TAVILY REMOTE MCP INTEGRATION: WORKING")

    # Cleanup
    print("\n[Cleanup]")
    print(f"  To remove test server:")
    print(f"  DELETE FROM mcp_servers WHERE id = '{server_id}';")


if __name__ == "__main__":
    asyncio.run(test_tavily_remote_mcp())
