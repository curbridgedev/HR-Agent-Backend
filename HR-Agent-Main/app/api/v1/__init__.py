"""
API v1 Router
All v1 endpoints are registered here.
"""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    agent,
    agent_graph,
    analytics,
    chat,
    customers,
    documents,
    escalate,
    mcp_servers,
    models,
    prompts,
    tools,
    upload,
    users,
    widget,
)

api_router = APIRouter()

# Register chat endpoints
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])

# Register document management endpoints
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])

# Register models/providers endpoints
api_router.include_router(models.router, prefix="/models", tags=["Models"])

# Register prompts management endpoints
api_router.include_router(prompts.router, prefix="/prompts", tags=["Prompts"])

# Register escalation endpoints (HR Agent escalations to human specialists)
api_router.include_router(escalate.router, prefix="/escalate", tags=["Escalations"])

# Register upload endpoints (for manual data ingestion)
api_router.include_router(upload.router, prefix="/upload", tags=["Upload"])

# Register tool management endpoints
api_router.include_router(tools.router, prefix="/tools", tags=["Tools"])

# Register MCP server management endpoints
api_router.include_router(mcp_servers.router, prefix="/mcp-servers", tags=["MCP Servers"])

# Register agent configuration endpoints (admin dashboard)
api_router.include_router(agent.router, prefix="/agent", tags=["Agent Configuration"])

# Register analytics endpoints (admin dashboard)
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

# Register customer management endpoints (admin dashboard - Phase 3)
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])

# Register public widget config endpoint (PUBLIC - no auth required)
api_router.include_router(widget.router, prefix="/widget-config", tags=["Widget (Public)"])

# Register user management endpoints (admin dashboard - requires admin/super_admin role)
api_router.include_router(users.router, prefix="/admin/users", tags=["User Management"])

# Register agent graph visualization endpoints (admin dashboard)
api_router.include_router(agent_graph.router, prefix="/admin/agent", tags=["Agent Graph"])

# Register admin-specific endpoints (LLM models with pricing, etc.)
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])


# Placeholder endpoint for initial testing
@api_router.get("/ping")
async def ping() -> dict:
    """
    Simple ping endpoint for testing API is working.
    """
    return {"message": "pong", "status": "ok"}
