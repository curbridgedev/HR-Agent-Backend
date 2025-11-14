"""
Models API endpoints for LLM provider model discovery.

Provides endpoints to list available models from different LLM providers
with caching and dynamic discovery.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Query, HTTPException

from app.models.base import BaseResponse
from app.utils.llm_client import get_available_models, clear_model_cache
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class AvailableModelsResponse(BaseResponse):
    """Response model for available models listing."""

    provider: str
    models: List[str]
    cached: bool
    count: int


class AllModelsResponse(BaseResponse):
    """Response model for all providers' models."""

    providers: Dict[str, List[str]]
    total_count: int


class SupportedProvidersResponse(BaseResponse):
    """Response model for supported providers listing."""

    providers: List[str]
    count: int


@router.get("/providers", response_model=SupportedProvidersResponse)
async def get_supported_providers():
    """
    Get list of supported LLM providers.

    Returns:
        List of provider names that are supported by the backend

    Example:
        GET /api/v1/models/providers
    """
    try:
        logger.info("Fetching supported providers")

        # Currently only OpenAI is supported (only provider with API key)
        supported_providers = ["openai"]

        return SupportedProvidersResponse(
            providers=supported_providers,
            count=len(supported_providers)
        )

    except Exception as e:
        logger.error(f"Failed to fetch supported providers: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch supported providers: {str(e)}"
        )


@router.get("/providers/{provider}/models", response_model=AvailableModelsResponse)
async def get_provider_models(
    provider: str,
    force_refresh: bool = Query(False, description="Force refresh cache")
):
    """
    Get available models for a specific provider.

    Args:
        provider: Provider name (only openai is supported)
        force_refresh: Force refresh cache (default: False)

    Returns:
        List of available models for the provider

    Example:
        GET /api/v1/models/providers/openai/models
        GET /api/v1/models/providers/openai/models?force_refresh=true
    """
    try:
        # Validate provider
        valid_providers = ["openai"]
        if provider not in valid_providers:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
            )

        logger.info(f"Fetching models for provider: {provider}, force_refresh={force_refresh}")

        # Get models with caching
        models = await get_available_models(provider, force_refresh=force_refresh)

        return AvailableModelsResponse(
            provider=provider,
            models=models,
            cached=not force_refresh,
            count=len(models)
        )

    except Exception as e:
        logger.error(f"Failed to fetch models for {provider}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch models: {str(e)}"
        )


@router.get("/providers/all/models", response_model=AllModelsResponse)
async def get_all_provider_models(
    force_refresh: bool = Query(False, description="Force refresh cache")
):
    """
    Get available models for all providers.

    Args:
        force_refresh: Force refresh cache (default: False)

    Returns:
        Dictionary of all providers and their available models

    Example:
        GET /api/v1/models/providers/all/models
        GET /api/v1/models/providers/all/models?force_refresh=true
    """
    try:
        logger.info(f"Fetching models for all providers, force_refresh={force_refresh}")

        # Fetch models for all providers
        providers_data = {}
        for provider in ["openai"]:
            try:
                models = await get_available_models(provider, force_refresh=force_refresh)
                providers_data[provider] = models
            except Exception as e:
                logger.warning(f"Failed to fetch models for {provider}: {e}")
                providers_data[provider] = []

        total_count = sum(len(models) for models in providers_data.values())

        return AllModelsResponse(
            providers=providers_data,
            total_count=total_count
        )

    except Exception as e:
        logger.error(f"Failed to fetch all provider models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch all provider models: {str(e)}"
        )


@router.post("/cache/clear")
async def clear_models_cache():
    """
    Clear the models cache for all providers.

    This forces a fresh fetch on the next model listing request.

    Returns:
        Success message

    Example:
        POST /api/v1/models/cache/clear
    """
    try:
        logger.info("Clearing models cache")
        clear_model_cache()

        return {"message": "Models cache cleared successfully"}

    except Exception as e:
        logger.error(f"Failed to clear models cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )
