"""
Supabase client initialization and database utilities.
"""

from typing import Optional
from supabase import create_client, Client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SupabaseClient:
    """
    Singleton Supabase client manager.
    Handles connection pooling and client lifecycle.
    """

    _instance: Optional[Client] = None

    @classmethod
    def get_client(cls) -> Client:
        """
        Get or create Supabase client instance.

        Returns:
            Supabase client instance
        """
        if cls._instance is None:
            try:
                cls._instance = create_client(
                    supabase_url=settings.supabase_url,
                    supabase_key=settings.supabase_service_role_key,
                )
                logger.info("Supabase client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                raise

        return cls._instance

    @classmethod
    async def close(cls) -> None:
        """Close Supabase client connection."""
        if cls._instance is not None:
            # Supabase client doesn't have explicit close method
            # but we reset the instance for cleanup
            cls._instance = None
            logger.info("Supabase client closed")


# Convenience function for dependency injection
def get_supabase_client() -> Client:
    """
    FastAPI dependency for Supabase client.

    Usage:
        @app.get("/endpoint")
        async def endpoint(db: Client = Depends(get_supabase_client)):
            result = await db.table("table_name").select("*").execute()
    """
    return SupabaseClient.get_client()
