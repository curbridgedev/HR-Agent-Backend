"""
Public Widget Configuration API endpoint.

Provides PUBLIC endpoint for widget to fetch configuration using API key.
This is the only endpoint in this router and is intentionally separated
from admin endpoints for security and clarity.
"""

from fastapi import APIRouter, HTTPException, status

from app.core.logging import get_logger
from app.models.customers import WidgetConfigPublicResponse
from app.services.customers import get_widget_config_by_api_key

logger = get_logger(__name__)

router = APIRouter()


# ============================================================================
# Public Widget Configuration Endpoint
# ============================================================================

@router.get("/by-api-key/{api_key}", response_model=WidgetConfigPublicResponse)
async def get_widget_config_by_api_key_endpoint(api_key: str):
    """
    Get widget configuration by API key (PUBLIC endpoint).

    This is a PUBLIC endpoint used by the embedded widget to fetch configuration.
    Returns only public widget settings (no sensitive customer data like IDs).

    **Security**:
    - No admin authentication required (PUBLIC)
    - API key validated by SHA-256 hash comparison
    - Checks API key enabled status and expiration
    - No sensitive data returned (no customer ID, no internal IDs)

    Args:
        api_key: Full API key (e.g., "cp_live_abc123...")

    Returns:
        Public widget configuration (theme, position, messages, etc.)

    Error Handling:
        - 404 Not Found: API key invalid, disabled, or no widget config

    Example:
        GET /api/v1/widget-config/by-api-key/cp_live_abc123...

        Response:
        {
          "position": "bottom-right",
          "auto_open": true,
          "auto_open_delay": 5,
          "theme_config": {
            "primaryColor": "#3B82F6",
            "fontFamily": "Inter, sans-serif",
            ...
          },
          "greeting_message": "Hello! How can we help?",
          "placeholder_text": "Type your message...",
          ...
        }
    """
    try:
        logger.info("Fetching widget config by API key (public)")

        widget_config = await get_widget_config_by_api_key(api_key)

        if not widget_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Widget configuration not found or API key invalid"
            )

        return widget_config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get widget config by API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get widget config: {str(e)}"
        )
