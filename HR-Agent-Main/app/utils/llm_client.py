"""
LangChain-based LLM client abstraction for multi-provider support.

Supports OpenAI, Anthropic, Google, and other providers through LangChain's
unified interface. Provides structured output capabilities and tool binding.
"""

from typing import Optional, Dict, Any, Type, List
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncio

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Cache for available models (TTL: 1 hour)
_model_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl = timedelta(hours=1)


class LLMClientManager:
    """
    Manager for LangChain chat models with provider abstraction.

    Supports multiple providers with consistent interface for:
    - Text generation
    - Structured outputs
    - Tool calling
    - Streaming
    """

    _instances: Dict[str, BaseChatModel] = {}

    @classmethod
    def get_chat_model(
        cls,
        provider: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> BaseChatModel:
        """
        Get or create a LangChain chat model instance.

        Args:
            provider: Provider name (openai, anthropic, google)
            model: Model name (e.g., gpt-4, claude-3-opus-20240229, gemini-pro)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            LangChain BaseChatModel instance

        Raises:
            ValueError: If provider is not supported
        """
        cache_key = f"{provider}:{model}:{temperature}:{max_tokens}"

        if cache_key in cls._instances:
            logger.debug(f"Reusing cached LLM client: {cache_key}")
            return cls._instances[cache_key]

        try:
            if provider == "openai":
                chat_model = cls._create_openai_model(model, temperature, max_tokens, **kwargs)
            elif provider == "anthropic":
                chat_model = cls._create_anthropic_model(model, temperature, max_tokens, **kwargs)
            elif provider == "google":
                chat_model = cls._create_google_model(model, temperature, max_tokens, **kwargs)
            else:
                raise ValueError(
                    f"Unsupported provider: {provider}. "
                    f"Supported providers: openai, anthropic, google"
                )

            cls._instances[cache_key] = chat_model
            logger.info(f"Created new LLM client: provider={provider}, model={model}")
            return chat_model

        except Exception as e:
            logger.error(f"Failed to create LLM client for {provider}/{model}: {e}")
            raise

    @classmethod
    def _create_openai_model(
        cls,
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ChatOpenAI:
        """Create OpenAI chat model."""
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.openai_api_key,
            timeout=settings.agent_timeout_seconds,
            **kwargs,
        )

    @classmethod
    def _create_anthropic_model(
        cls,
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ChatAnthropic:
        """Create Anthropic Claude chat model."""
        # Check if API key is available
        anthropic_api_key = getattr(settings, "anthropic_api_key", None)
        if not anthropic_api_key:
            raise ValueError(
                "Anthropic API key not configured. "
                "Set ANTHROPIC_API_KEY in environment variables."
            )

        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=anthropic_api_key,
            timeout=settings.agent_timeout_seconds,
            **kwargs,
        )

    @classmethod
    def _create_google_model(
        cls,
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ChatGoogleGenerativeAI:
        """Create Google Gemini chat model."""
        # Check if API key is available
        google_api_key = getattr(settings, "google_api_key", None)
        if not google_api_key:
            raise ValueError(
                "Google API key not configured. "
                "Set GOOGLE_API_KEY in environment variables."
            )

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            google_api_key=google_api_key,
            timeout=settings.agent_timeout_seconds,
            **kwargs,
        )

    @classmethod
    def get_structured_model(
        cls,
        provider: str,
        model: str,
        schema: Type[BaseModel],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> BaseChatModel:
        """
        Get chat model with structured output capability.

        Automatically binds Pydantic schema to model output for type-safe responses.

        Args:
            provider: Provider name
            model: Model name
            schema: Pydantic BaseModel class for output validation
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional parameters

        Returns:
            Chat model with structured output binding

        Example:
            class QueryAnalysis(BaseModel):
                intent: str
                entities: List[str]

            model = LLMClientManager.get_structured_model(
                provider="openai",
                model="gpt-4",
                schema=QueryAnalysis,
            )
            result = await model.ainvoke("What is Compaytence?")
            # result is automatically validated QueryAnalysis instance
        """
        base_model = cls.get_chat_model(provider, model, temperature, max_tokens, **kwargs)

        try:
            # Use LangChain's structured output binding
            structured_model = base_model.with_structured_output(schema)
            logger.debug(f"Created structured model with schema: {schema.__name__}")
            return structured_model
        except Exception as e:
            logger.warning(
                f"Structured output not supported for {provider}/{model}, "
                f"falling back to base model: {e}"
            )
            return base_model

    @classmethod
    def clear_cache(cls):
        """Clear all cached model instances."""
        cls._instances.clear()
        logger.info("Cleared LLM client cache")


# Dynamic Model Discovery Functions

async def fetch_openai_models() -> List[str]:
    """
    Fetch available models from OpenAI API.

    Returns:
        List of available OpenAI model IDs
    """
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        models_response = await client.models.list()

        # Filter for chat models (gpt-*, o1-*)
        chat_models = [
            model.id for model in models_response.data
            if model.id.startswith(("gpt-", "o1-"))
        ]

        logger.info(f"Fetched {len(chat_models)} OpenAI chat models")
        return sorted(chat_models, reverse=True)  # Newest first

    except Exception as e:
        logger.warning(f"Failed to fetch OpenAI models: {e}")
        # Fallback to known models
        return [
            # GPT-4o (Latest generation)
            "gpt-4o",
            "gpt-4o-2024-11-20",
            "gpt-4o-2024-08-06",
            "gpt-4o-2024-05-13",
            "gpt-4o-mini",
            "gpt-4o-mini-2024-07-18",
            # GPT-4 Turbo
            "gpt-4-turbo",
            "gpt-4-turbo-2024-04-09",
            "gpt-4-turbo-preview",
            # GPT-4
            "gpt-4",
            "gpt-4-0613",
            "gpt-4-0314",
            # GPT-3.5 Turbo
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-0125",
            "gpt-3.5-turbo-1106",
            # o1 (Reasoning models)
            "o1-preview",
            "o1-preview-2024-09-12",
            "o1-mini",
            "o1-mini-2024-09-12",
        ]


async def fetch_anthropic_models() -> List[str]:
    """
    Fetch available models from Anthropic API.

    Returns:
        List of available Anthropic model IDs
    """
    try:
        import anthropic

        # Check if API key is available
        anthropic_api_key = getattr(settings, "anthropic_api_key", None)
        if not anthropic_api_key:
            logger.warning("Anthropic API key not configured")
            raise ValueError("Anthropic API key not available")

        client = anthropic.Anthropic(api_key=anthropic_api_key)

        # Anthropic doesn't have a public models endpoint yet
        # Use known models with version checking
        # TODO: Update when Anthropic adds a models API endpoint
        models = [
            # Claude 3.5 (Latest generation)
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            # Claude 3 (Previous generation)
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            # Claude 2.1 (Legacy)
            "claude-2.1",
            "claude-2.0",
            # Claude Instant (Fast, legacy)
            "claude-instant-1.2",
        ]

        logger.info(f"Using {len(models)} known Anthropic models")
        return models

    except Exception as e:
        logger.warning(f"Failed to fetch Anthropic models: {e}")
        # Fallback to known models
        return [
            # Claude 3.5 (Latest generation)
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            # Claude 3 (Previous generation)
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            # Claude 2.1 (Legacy)
            "claude-2.1",
            "claude-2.0",
            # Claude Instant (Fast, legacy)
            "claude-instant-1.2",
        ]


async def fetch_google_models() -> List[str]:
    """
    Fetch available models from Google Generative AI API.

    Returns:
        List of available Google model IDs
    """
    try:
        import google.generativeai as genai

        # Check if API key is available
        google_api_key = getattr(settings, "google_api_key", None)
        if not google_api_key:
            logger.warning("Google API key not configured")
            raise ValueError("Google API key not available")

        genai.configure(api_key=google_api_key)

        # List available models
        models_response = genai.list_models()

        # Filter for generative models (gemini-*)
        gemini_models = [
            model.name.replace("models/", "")
            for model in models_response
            if "gemini" in model.name.lower() and "generateContent" in model.supported_generation_methods
        ]

        logger.info(f"Fetched {len(gemini_models)} Google Gemini models")
        return sorted(gemini_models, reverse=True)  # Newest first

    except Exception as e:
        logger.warning(f"Failed to fetch Google models: {e}")
        # Fallback to known models
        return [
            # Gemini 2.0 (Latest - Experimental)
            "gemini-2.0-flash-exp",
            # Gemini 1.5 (Current generation)
            "gemini-1.5-pro-latest",
            "gemini-1.5-pro",
            "gemini-1.5-pro-exp-0827",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            # Gemini 1.0 (Previous generation)
            "gemini-pro",
            "gemini-pro-vision",
        ]


async def get_available_models(provider: str, force_refresh: bool = False) -> List[str]:
    """
    Get available models for a provider with caching.

    Args:
        provider: Provider name (openai, anthropic, google)
        force_refresh: Force refresh cache

    Returns:
        List of available model IDs
    """
    cache_key = f"{provider}_models"

    # Check cache
    if not force_refresh and cache_key in _model_cache:
        cached_data = _model_cache[cache_key]
        if datetime.now() - cached_data["timestamp"] < _cache_ttl:
            logger.debug(f"Using cached models for {provider}")
            return cached_data["models"]

    # Fetch fresh models
    logger.info(f"Fetching available models for {provider}")

    if provider == "openai":
        models = await fetch_openai_models()
    elif provider == "anthropic":
        models = await fetch_anthropic_models()
    elif provider == "google":
        models = await fetch_google_models()
    else:
        logger.error(f"Unknown provider: {provider}")
        return []

    # Update cache
    _model_cache[cache_key] = {
        "models": models,
        "timestamp": datetime.now()
    }

    return models


def clear_model_cache():
    """Clear the model cache."""
    _model_cache.clear()
    logger.info("Cleared model cache")


# Convenience function for dependency injection
def get_chat_model(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Get LangChain chat model using configuration or defaults.

    Uses settings from environment or agent configuration.
    This is the main entry point for getting chat models.

    Args:
        provider: Provider name (defaults to "openai")
        model: Model name (defaults to settings.openai_model)
        temperature: Temperature (defaults to settings.openai_temperature)
        max_tokens: Max tokens (defaults to settings.openai_max_tokens)
        **kwargs: Additional provider-specific parameters (top_p, frequency_penalty, etc.)

    Returns:
        LangChain chat model instance

    Example:
        # Use defaults from settings
        model = get_chat_model()

        # Override with specific model
        model = get_chat_model(provider="anthropic", model="claude-3-opus-20240229")

        # With additional parameters
        model = get_chat_model(
            provider="openai",
            model="gpt-4",
            top_p=0.9,
            frequency_penalty=0.5,
        )

        # Use in agent
        response = await model.ainvoke([
            SystemMessage(content="You are a helpful assistant"),
            HumanMessage(content="What is Compaytence?"),
        ])
    """
    # Use defaults from settings
    provider = provider or "openai"
    model = model or settings.openai_model
    temperature = temperature if temperature is not None else settings.openai_temperature
    max_tokens = max_tokens if max_tokens is not None else settings.openai_max_tokens

    return LLMClientManager.get_chat_model(
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )


def get_structured_chat_model(
    schema: Type[BaseModel],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Get chat model with structured output validation.

    Args:
        schema: Pydantic model class for output validation
        provider: Provider name (defaults to "openai")
        model: Model name (defaults to settings.openai_model)
        temperature: Temperature (defaults to settings.openai_temperature)
        max_tokens: Max tokens (defaults to settings.openai_max_tokens)
        **kwargs: Additional provider-specific parameters

    Returns:
        Chat model with structured output binding

    Example:
        class Answer(BaseModel):
            answer: str
            confidence: float

        model = get_structured_chat_model(Answer)
        result = await model.ainvoke("What is 2+2?")
        # result.answer == "4"
        # result.confidence == 0.99
    """
    provider = provider or "openai"
    model = model or settings.openai_model
    temperature = temperature if temperature is not None else settings.openai_temperature
    max_tokens = max_tokens if max_tokens is not None else settings.openai_max_tokens

    return LLMClientManager.get_structured_model(
        provider=provider,
        model=model,
        schema=schema,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )


# Provider capability matrix
PROVIDER_CAPABILITIES = {
    "openai": {
        "structured_output": True,
        "tool_calling": True,
        "streaming": True,
        "json_mode": True,
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "o1-preview",
            "o1-mini",
        ],
    },
    "anthropic": {
        "structured_output": True,
        "tool_calling": True,
        "streaming": True,
        "json_mode": False,
        "models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ],
    },
    "google": {
        "structured_output": True,
        "tool_calling": True,
        "streaming": True,
        "json_mode": True,
        "models": [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-pro",
        ],
    },
}


def get_provider_capabilities(provider: str) -> Dict[str, Any]:
    """
    Get capability information for a provider.

    Args:
        provider: Provider name

    Returns:
        Dictionary of provider capabilities

    Example:
        caps = get_provider_capabilities("openai")
        if caps["structured_output"]:
            # Use structured output
            pass
    """
    return PROVIDER_CAPABILITIES.get(provider, {})
