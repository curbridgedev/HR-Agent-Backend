"""
OpenAI client initialization and utilities.
"""

from typing import Optional
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    """
    Singleton OpenAI client manager.
    Handles client lifecycle and configuration.
    """

    _instance: Optional[AsyncOpenAI] = None

    @classmethod
    def get_client(cls) -> AsyncOpenAI:
        """
        Get or create OpenAI client instance.

        Returns:
            AsyncOpenAI client instance
        """
        if cls._instance is None:
            try:
                cls._instance = AsyncOpenAI(
                    api_key=settings.openai_api_key,
                    timeout=settings.agent_timeout_seconds,
                )
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                raise

        return cls._instance

    @classmethod
    async def close(cls) -> None:
        """Close OpenAI client connection."""
        if cls._instance is not None:
            await cls._instance.close()
            cls._instance = None
            logger.info("OpenAI client closed")


# Convenience function for dependency injection
def get_openai_client() -> AsyncOpenAI:
    """
    FastAPI dependency for OpenAI client.

    Usage:
        @app.get("/endpoint")
        async def endpoint(openai: AsyncOpenAI = Depends(get_openai_client)):
            response = await openai.chat.completions.create(...)
    """
    return OpenAIClient.get_client()
