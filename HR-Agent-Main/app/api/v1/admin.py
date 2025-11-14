"""
Admin-specific API endpoints.

Provides endpoints for:
- LLM model details with pricing information
- Admin configuration management
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from app.core.logging import get_logger
from app.models.base import BaseResponse

logger = get_logger(__name__)

router = APIRouter()


# ============================================================================
# Models
# ============================================================================


class LLMModelDetail(BaseResponse):
    """Detailed LLM model information including pricing."""

    model: str = Field(..., description="Model identifier")
    display_name: str = Field(..., description="Human-readable model name")
    provider: Literal["openai"] = Field(
        ..., description="LLM provider"
    )
    input_price_per_1k: float = Field(
        ..., description="Price per 1000 input tokens (USD)"
    )
    output_price_per_1k: float = Field(
        ..., description="Price per 1000 output tokens (USD)"
    )
    context_window: int = Field(..., description="Maximum context window size (tokens)")
    recommended_for: str = Field(..., description="Recommended use case")
    supports_streaming: bool = Field(True, description="Whether model supports streaming")


class LLMModelsResponse(BaseResponse):
    """Response model for LLM models listing with pricing."""

    provider: str = Field(..., description="Provider name")
    models: list[LLMModelDetail] = Field(..., description="List of models")
    total_count: int = Field(..., description="Total number of models")


# Model pricing data (as of January 2025)
# Source: Official OpenAI pricing pages
MODEL_CATALOG = {
    "openai": [
        LLMModelDetail(
            model="gpt-4o",
            display_name="GPT-4o",
            provider="openai",
            input_price_per_1k=0.0025,
            output_price_per_1k=0.010,
            context_window=128000,
            recommended_for="Complex reasoning, coding, analysis",
            supports_streaming=True,
        ),
        LLMModelDetail(
            model="gpt-4o-mini",
            display_name="GPT-4o Mini",
            provider="openai",
            input_price_per_1k=0.00015,
            output_price_per_1k=0.0006,
            context_window=128000,
            recommended_for="Fast, cost-effective tasks (recommended for confidence evaluation)",
            supports_streaming=True,
        ),
        LLMModelDetail(
            model="gpt-4-turbo",
            display_name="GPT-4 Turbo",
            provider="openai",
            input_price_per_1k=0.01,
            output_price_per_1k=0.03,
            context_window=128000,
            recommended_for="High-quality reasoning with latest training data",
            supports_streaming=True,
        ),
        LLMModelDetail(
            model="gpt-4",
            display_name="GPT-4",
            provider="openai",
            input_price_per_1k=0.03,
            output_price_per_1k=0.06,
            context_window=8192,
            recommended_for="Legacy GPT-4 (use GPT-4 Turbo for better performance)",
            supports_streaming=True,
        ),
        LLMModelDetail(
            model="gpt-3.5-turbo",
            display_name="GPT-3.5 Turbo",
            provider="openai",
            input_price_per_1k=0.0005,
            output_price_per_1k=0.0015,
            context_window=16385,
            recommended_for="Fast, simple tasks (not recommended for main agent)",
            supports_streaming=True,
        ),
    ],
}


@router.get("/llm/models", response_model=LLMModelsResponse)
async def get_llm_models_with_pricing(
    provider: Literal["openai"] = Query(
        ..., description="LLM provider to fetch models for"
    )
):
    """
    Get detailed LLM model information including pricing.

    Returns comprehensive model details including:
    - Model identifiers and display names
    - Pricing per 1000 tokens (input and output)
    - Context window sizes
    - Recommended use cases
    - Streaming support

    This endpoint is used by the admin UI to display available models
    with pricing information for configuration decisions.

    Args:
        provider: LLM provider (openai, anthropic, azure, google)

    Returns:
        List of models with detailed pricing information

    Example:
        GET /api/v1/admin/llm/models?provider=openai
    """
    try:
        logger.info(f"Fetching LLM models with pricing for provider: {provider}")

        # Get models for the provider
        models = MODEL_CATALOG.get(provider, [])

        if not models:
            raise HTTPException(
                status_code=404,
                detail=f"No models found for provider: {provider}",
            )

        return LLMModelsResponse(
            provider=provider,
            models=models,
            total_count=len(models),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch LLM models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch LLM models: {str(e)}",
        )
