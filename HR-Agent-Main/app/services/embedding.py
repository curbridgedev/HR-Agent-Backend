"""
Embedding generation service using OpenAI with rate limiting and cost tracking.

Features:
- Rate limiting (requests per minute, tokens per minute)
- Retry logic with exponential backoff and jitter
- Cost tracking per operation
- Usage metrics logging
"""

import asyncio
import random
from typing import List, Dict, Any
from datetime import datetime
import tiktoken
from openai import RateLimitError, APIError, APIConnectionError, Timeout

from app.utils.openai_client import get_openai_client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Rate limiting: Semaphore for requests per minute
_rate_limit_semaphore: asyncio.Semaphore | None = None
_token_bucket: Dict[str, Any] = {
    "tokens": 0,
    "max_tokens": 0,
    "last_refill": datetime.now(),
}

# OpenAI embedding model pricing (as of 2025)
# Source: https://openai.com/api/pricing/
EMBEDDING_MODEL_PRICING = {
    "text-embedding-3-small": 0.00000002,   # $0.02 per 1M tokens
    "text-embedding-3-large": 0.00000013,   # $0.13 per 1M tokens
    "text-embedding-ada-002": 0.0000001,    # $0.10 per 1M tokens (legacy)
}


def _get_cost_per_token(model: str) -> float:
    """
    Get cost per token for a specific embedding model.

    Args:
        model: Model name (e.g., "text-embedding-3-large")

    Returns:
        Cost per token in USD
    """
    cost = EMBEDDING_MODEL_PRICING.get(model)
    if cost is None:
        logger.warning(f"Unknown model '{model}', using text-embedding-3-small pricing as fallback")
        cost = EMBEDDING_MODEL_PRICING["text-embedding-3-small"]
    return cost


def _initialize_rate_limiter() -> None:
    """Initialize rate limiting semaphore if not already initialized."""
    global _rate_limit_semaphore, _token_bucket

    if _rate_limit_semaphore is None and settings.rate_limit_enabled:
        _rate_limit_semaphore = asyncio.Semaphore(settings.rate_limit_per_minute)
        _token_bucket["max_tokens"] = settings.rate_limit_per_minute * 8192  # Max tokens per minute
        _token_bucket["tokens"] = _token_bucket["max_tokens"]

        # Log rate limiter configuration
        cost_per_token = _get_cost_per_token(settings.openai_embedding_model)
        cost_per_1m = cost_per_token * 1_000_000
        logger.info(
            f"Embedding service initialized: model={settings.openai_embedding_model}, "
            f"cost=${cost_per_1m:.2f}/1M tokens, "
            f"rate_limit={settings.rate_limit_per_minute} req/min, "
            f"token_limit={_token_bucket['max_tokens']} tokens/min"
        )


async def _wait_for_token_bucket(tokens_needed: int) -> None:
    """
    Wait until enough tokens are available in the token bucket.
    Implements token bucket algorithm for rate limiting.
    """
    global _token_bucket

    if not settings.rate_limit_enabled:
        return

    while True:
        # Refill bucket based on time elapsed
        now = datetime.now()
        time_passed = (now - _token_bucket["last_refill"]).total_seconds()
        refill_rate = _token_bucket["max_tokens"] / 60  # Tokens per second

        _token_bucket["tokens"] = min(
            _token_bucket["max_tokens"], _token_bucket["tokens"] + (refill_rate * time_passed)
        )
        _token_bucket["last_refill"] = now

        # Check if enough tokens available
        if _token_bucket["tokens"] >= tokens_needed:
            _token_bucket["tokens"] -= tokens_needed
            break

        # Wait before checking again
        await asyncio.sleep(0.1)


def _calculate_cost(token_count: int, model: str | None = None) -> float:
    """
    Calculate cost in USD based on token count and model.

    Args:
        token_count: Number of tokens processed
        model: Model name (defaults to settings.openai_embedding_model)

    Returns:
        Cost in USD
    """
    if model is None:
        model = settings.openai_embedding_model

    cost_per_token = _get_cost_per_token(model)
    return token_count * cost_per_token


def _log_usage(operation: str, tokens: int, cost: float, duration_ms: float) -> None:
    """Log embedding usage for monitoring."""
    logger.info(
        f"Embedding usage: operation={operation} tokens={tokens} "
        f"cost_usd={cost:.6f} duration_ms={duration_ms:.2f}"
    )


async def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for a single text with rate limiting and cost tracking.

    Args:
        text: Input text to embed

    Returns:
        List of floats representing the embedding vector
    """
    _initialize_rate_limiter()
    start_time = datetime.now()

    try:
        # Count tokens for rate limiting and cost tracking
        token_count = count_tokens(text, settings.openai_embedding_model)

        # Rate limiting: Wait for tokens and request slot
        await _wait_for_token_bucket(token_count)

        # Acquire semaphore for request-level rate limiting
        if _rate_limit_semaphore is not None:
            async with _rate_limit_semaphore:
                client = get_openai_client()

                response = await client.embeddings.create(
                    model=settings.openai_embedding_model,
                    input=text,
                    dimensions=settings.openai_embedding_dimensions,
                )
        else:
            client = get_openai_client()
            response = await client.embeddings.create(
                model=settings.openai_embedding_model,
                input=text,
                dimensions=settings.openai_embedding_dimensions,
            )

        embedding = response.data[0].embedding

        # Calculate metrics
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        actual_tokens = response.usage.total_tokens
        cost = _calculate_cost(actual_tokens, settings.openai_embedding_model)

        # Log usage
        _log_usage("generate_embedding", actual_tokens, cost, duration_ms)

        logger.debug(
            f"Generated embedding: dimension={len(embedding)}, tokens={actual_tokens}, "
            f"cost=${cost:.6f}, model={settings.openai_embedding_model}"
        )

        return embedding

    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in a single API call with rate limiting and cost tracking.

    More efficient for batch processing (e.g., document chunking).
    OpenAI limits: Max 2048 inputs per request, max 300K tokens per request.

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors
    """
    _initialize_rate_limiter()
    start_time = datetime.now()

    try:
        # OpenAI API batch size limit
        batch_size = 2048
        max_tokens_per_request = 300000

        # Count total tokens
        total_tokens = sum(count_tokens(text, settings.openai_embedding_model) for text in texts)

        # Wait for token bucket
        await _wait_for_token_bucket(total_tokens)

        client = get_openai_client()

        if len(texts) <= batch_size and total_tokens <= max_tokens_per_request:
            # Single batch request
            if _rate_limit_semaphore is not None:
                async with _rate_limit_semaphore:
                    response = await client.embeddings.create(
                        model=settings.openai_embedding_model,
                        input=texts,
                        dimensions=settings.openai_embedding_dimensions,
                    )
            else:
                response = await client.embeddings.create(
                    model=settings.openai_embedding_model,
                    input=texts,
                    dimensions=settings.openai_embedding_dimensions,
                )

            embeddings = [item.embedding for item in response.data]

            # Calculate metrics
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            actual_tokens = response.usage.total_tokens
            cost = _calculate_cost(actual_tokens, settings.openai_embedding_model)

            _log_usage("generate_embeddings_batch", actual_tokens, cost, duration_ms)

            logger.info(
                f"Generated {len(embeddings)} embeddings in batch: tokens={actual_tokens}, "
                f"cost=${cost:.6f}, model={settings.openai_embedding_model}"
            )
            return embeddings
        else:
            # Process in chunks if too many texts or tokens
            all_embeddings = []
            batch_count = 0

            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]

                # Check token limit for this batch
                batch_tokens = sum(count_tokens(text, settings.openai_embedding_model) for text in batch)
                if batch_tokens > max_tokens_per_request:
                    # Further split if single batch exceeds token limit
                    logger.warning(f"Batch {i // batch_size + 1} exceeds token limit, splitting further")
                    # Process texts one by one
                    for text in batch:
                        embedding = await generate_embedding(text)
                        all_embeddings.append(embedding)
                    continue

                if _rate_limit_semaphore is not None:
                    async with _rate_limit_semaphore:
                        response = await client.embeddings.create(
                            model=settings.openai_embedding_model,
                            input=batch,
                            dimensions=settings.openai_embedding_dimensions,
                        )
                else:
                    response = await client.embeddings.create(
                        model=settings.openai_embedding_model,
                        input=batch,
                        dimensions=settings.openai_embedding_dimensions,
                    )

                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                batch_count += 1

                # Log this batch
                actual_tokens = response.usage.total_tokens
                cost = _calculate_cost(actual_tokens, settings.openai_embedding_model)
                logger.info(
                    f"Batch {batch_count}: {len(batch_embeddings)} embeddings, "
                    f"tokens={actual_tokens}, cost=${cost:.6f}"
                )

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            total_cost = _calculate_cost(total_tokens, settings.openai_embedding_model)
            _log_usage("generate_embeddings_batch_multi", total_tokens, total_cost, duration_ms)

            logger.info(f"Generated {len(all_embeddings)} embeddings in {batch_count} batches")
            return all_embeddings

    except Exception as e:
        logger.error(f"Batch embedding generation failed: {e}")
        raise


def count_tokens(text: str, model: str = "text-embedding-3-small") -> int:
    """
    Count tokens in text for cost estimation.

    Args:
        text: Input text
        model: Model name for tokenizer

    Returns:
        Number of tokens
    """
    try:
        # Get appropriate tokenizer
        encoding = tiktoken.encoding_for_model(model)
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception as e:
        logger.warning(f"Token counting failed: {e}, using rough estimate")
        # Rough estimate: ~4 characters per token
        return len(text) // 4


async def generate_embedding_with_retry(
    text: str, max_retries: int = 3
) -> List[float]:
    """
    Generate embedding with enhanced retry logic (exponential backoff + jitter).

    Handles transient API errors, rate limits, and connection issues.

    Args:
        text: Input text to embed
        max_retries: Maximum number of retry attempts

    Returns:
        Embedding vector

    Raises:
        Exception: After all retries exhausted
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await generate_embedding(text)

        except RateLimitError as e:
            # Rate limit hit - use longer backoff
            if attempt == max_retries - 1:
                logger.error(f"Rate limit hit after {max_retries} attempts: {e}")
                raise

            base_wait = 2 ** (attempt + 2)  # Longer backoff for rate limits: 4s, 8s, 16s
            jitter = random.uniform(0, 1)  # Add jitter to prevent thundering herd
            wait_time = base_wait + jitter

            logger.warning(
                f"Rate limit hit (attempt {attempt + 1}/{max_retries}), "
                f"retrying in {wait_time:.2f}s"
            )
            await asyncio.sleep(wait_time)
            last_exception = e

        except (APIConnectionError, Timeout) as e:
            # Connection/timeout errors - use medium backoff
            if attempt == max_retries - 1:
                logger.error(f"Connection/timeout error after {max_retries} attempts: {e}")
                raise

            base_wait = 2**attempt  # Exponential backoff: 1s, 2s, 4s
            jitter = random.uniform(0, 0.5)
            wait_time = base_wait + jitter

            logger.warning(
                f"Connection error (attempt {attempt + 1}/{max_retries}), "
                f"retrying in {wait_time:.2f}s: {e}"
            )
            await asyncio.sleep(wait_time)
            last_exception = e

        except APIError as e:
            # API errors - some might be retryable
            if attempt == max_retries - 1:
                logger.error(f"API error after {max_retries} attempts: {e}")
                raise

            # Check if error is retryable (5xx errors)
            if hasattr(e, 'status_code') and 500 <= e.status_code < 600:
                base_wait = 2**attempt
                jitter = random.uniform(0, 0.5)
                wait_time = base_wait + jitter

                logger.warning(
                    f"Server error {e.status_code} (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {wait_time:.2f}s"
                )
                await asyncio.sleep(wait_time)
                last_exception = e
            else:
                # Non-retryable API error (4xx)
                logger.error(f"Non-retryable API error: {e}")
                raise

        except Exception as e:
            # Unknown error
            if attempt == max_retries - 1:
                logger.error(f"Embedding generation failed after {max_retries} attempts: {e}")
                raise

            base_wait = 2**attempt
            jitter = random.uniform(0, 0.5)
            wait_time = base_wait + jitter

            logger.warning(
                f"Unexpected error (attempt {attempt + 1}/{max_retries}), "
                f"retrying in {wait_time:.2f}s: {e}"
            )
            await asyncio.sleep(wait_time)
            last_exception = e

    # Should never reach here, but just in case
    raise last_exception or Exception("Unexpected error in retry logic")
