"""
Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.error_handler import setup_error_monitoring
from app.api.v1 import api_router

# Initialize logging
setup_logging()
logger = get_logger(__name__)


def _initialize_pii_sync():
    """Synchronous PII initialization to run in executor."""
    from app.services.pii import initialize_pii_service

    initialize_pii_service()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize PII service in background (non-blocking)
    if settings.pii_anonymization_enabled:
        logger.info("PII anonymization is enabled, loading models in background...")

        # Use asyncio to schedule the task in the running event loop
        import asyncio

        async def load_pii_models():
            """Load PII models in background to avoid blocking startup."""
            try:
                # Run in executor to avoid blocking the event loop
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, _initialize_pii_sync)
                logger.info("PII models loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load PII models: {e}", exc_info=True)

        # Schedule the background task
        asyncio.create_task(load_pii_models())

    # Initialize MCP client manager and register servers from database
    logger.info("Initializing MCP client connections...")
    try:
        from app.agents.mcp_integration import get_mcp_client_manager, MCPServerConfig
        from app.db.supabase import get_supabase_client

        mcp_manager = get_mcp_client_manager()

        # Load MCP servers from database and register them
        supabase = get_supabase_client()
        response = supabase.table("mcp_servers").select("*").eq("enabled", True).execute()

        for server_data in response.data:
            config = MCPServerConfig(
                name=server_data["name"],
                transport=server_data["transport"],
                command=server_data.get("command"),
                args=server_data.get("args"),
                url=server_data.get("url"),
                headers=server_data.get("headers", {}),
                enabled=True,
            )
            mcp_manager.register_server(config)
            logger.info(f"Registered MCP server: {server_data['name']}")

        # Initialize the MCP client to connect to all servers
        await mcp_manager.initialize_client()
        logger.info("MCP servers initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize MCP servers (non-critical): {e}")
        logger.info("Application will continue without MCP servers")

    # TODO: Initialize database connections
    # TODO: Initialize OpenAI client
    # TODO: Initialize LangFuse client
    # TODO: Initialize Inngest client
    # TODO: Warm up agent graph

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application")

    # MCP servers cleanup (no explicit disconnect needed for langchain-mcp-adapters)
    logger.info("MCP servers cleanup complete")

    # TODO: Close database connections
    # TODO: Flush LangFuse traces
    # TODO: Close Inngest client

    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="HR Agent - Canadian Employment Standards Assistant",
    version=settings.app_version,
    description="Canadian Employment Standards HR Agent - AI-powered Q&A assistant for provincial employment law and HR policies with RAG capabilities",
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url=f"{settings.api_v1_prefix}/openapi.json" if settings.enable_api_docs else None,
    lifespan=lifespan,
    contact={
        "name": "Curbridge HR Agent",
        "url": "https://curbridge.com",
    },
    license_info={
        "name": "Proprietary",
    },
    # OpenAPI metadata
    openapi_tags=[
        {
            "name": "Chat",
            "description": "Chat endpoints for interacting with the HR Agent",
        },
        {
            "name": "Documents",
            "description": "Document upload and management endpoints",
        },
        {
            "name": "Health",
            "description": "Health check and monitoring endpoints",
        },
    ],
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods_list,
    allow_headers=[settings.cors_headers],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Setup error monitoring and Telegram notifications
setup_error_monitoring(app)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """
    Health check endpoint for monitoring.
    """
    return JSONResponse(
        content={
            "status": "healthy",
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }
    )


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> JSONResponse:
    """
    Root endpoint with API information.
    """
    return JSONResponse(
        content={
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": f"{settings.api_v1_prefix}/docs" if settings.enable_api_docs else None,
        }
    )


# Include API router
app.include_router(api_router, prefix=settings.api_v1_prefix)

# Note: Global exception handlers are registered by setup_error_monitoring()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.enable_reload and settings.is_development,
        log_level=settings.log_level.lower(),
    )
