"""
LangFuse observability integration.

Provides callback handlers for automatic tracing of LangGraph agent executions.
"""

from typing import Optional, Dict, Any, List
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global LangFuse client instance
_langfuse_client: Optional[Langfuse] = None


def get_langfuse_client() -> Optional[Langfuse]:
    """
    Get or initialize the global LangFuse client.

    Returns:
        Langfuse client instance or None if disabled
    """
    global _langfuse_client

    if not settings.langfuse_enabled:
        logger.debug("LangFuse is disabled via configuration")
        return None

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning("LangFuse credentials not configured, observability disabled")
        return None

    if _langfuse_client is None:
        try:
            _langfuse_client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                flush_interval=settings.langfuse_flush_interval,
            )
            logger.info(f"LangFuse client initialized: host={settings.langfuse_host}")
        except Exception as e:
            logger.error(f"Failed to initialize LangFuse client: {e}", exc_info=True)
            return None

    return _langfuse_client


def create_callback_handler(
    session_id: str,
    user_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[CallbackHandler]:
    """
    Create a LangFuse callback handler for agent tracing.

    Note: Session ID and user ID should be passed via config metadata when invoking:
    ```python
    config = {
        "callbacks": [handler],
        "metadata": {
            "langfuse_session_id": session_id,
            "langfuse_user_id": user_id,
        }
    }
    ```

    Args:
        session_id: Session identifier (passed to caller for metadata)
        user_id: User identifier (passed to caller for metadata)
        tags: Optional list of tags (stored in custom metadata)
        metadata: Optional additional metadata

    Returns:
        CallbackHandler instance or None if LangFuse is disabled
    """
    client = get_langfuse_client()
    if client is None:
        return None

    try:
        # Create callback handler
        # Session/user tracking happens via metadata in chain.invoke() config
        handler = CallbackHandler()

        logger.debug(
            f"LangFuse callback handler created: will track session={session_id}, user={user_id}"
        )

        return handler

    except Exception as e:
        logger.error(f"Failed to create LangFuse callback handler: {e}", exc_info=True)
        return None


def flush_langfuse():
    """
    Flush pending LangFuse traces.

    Call this during application shutdown or after critical operations.
    """
    client = get_langfuse_client()
    if client:
        try:
            client.flush()
            logger.debug("LangFuse traces flushed")
        except Exception as e:
            logger.error(f"Failed to flush LangFuse traces: {e}", exc_info=True)


def shutdown_langfuse():
    """
    Shutdown LangFuse client and flush remaining traces.

    Call this during application shutdown.
    """
    global _langfuse_client

    if _langfuse_client:
        try:
            _langfuse_client.flush()
            logger.info("LangFuse client shutdown complete")
        except Exception as e:
            logger.error(f"Error during LangFuse shutdown: {e}", exc_info=True)
        finally:
            _langfuse_client = None
