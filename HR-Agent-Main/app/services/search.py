"""
Hybrid search service combining vector similarity and keyword matching.

Features:
- Vector similarity search (OpenAI embeddings)
- Full-text keyword search (PostgreSQL tsvector)
- Cohere reranking for improved relevance
- Metadata filtering (source, author, conversation, dates)
- Configurable scoring weights
"""

import asyncio
from datetime import datetime
from typing import Any

import cohere
from app.core.config import settings
from app.core.logging import get_logger
from app.models.search import SearchFilters, SearchRequest, SearchResponse, SearchResult
from app.services.embedding import generate_embedding
from app.db.supabase import get_supabase_client

logger = get_logger(__name__)

# Initialize Cohere client
_cohere_client: cohere.AsyncClient | None = None


def _get_cohere_client() -> cohere.AsyncClient:
    """Get or create Cohere async client."""
    global _cohere_client
    if _cohere_client is None:
        _cohere_client = cohere.AsyncClient(api_key=settings.cohere_api_key)
        logger.info("Cohere reranking client initialized")
    return _cohere_client


def _prepare_query_text(query: str) -> str:
    """
    Prepare query text for PostgreSQL full-text search.

    Converts natural language query to tsquery format.
    Example: "what is payment fee" -> "payment & fee"
    """
    # Remove special characters
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in query)

    # Split into words and remove stop words
    words = cleaned.lower().split()
    stop_words = {"is", "are", "the", "a", "an", "what", "how", "why", "when", "where", "who"}
    meaningful_words = [w for w in words if w not in stop_words and len(w) > 2]

    # Join with AND operator
    if not meaningful_words:
        return " & ".join(words)  # Fallback to all words

    return " & ".join(meaningful_words)


async def hybrid_search(request: SearchRequest) -> SearchResponse:
    """
    Perform hybrid search combining vector similarity and keyword matching.

    Workflow:
    1. Generate embedding for query
    2. Execute hybrid_search function (vector + keyword)
    3. Apply Cohere reranking if enabled
    4. Return ranked results

    Args:
        request: Search request with query, weights, and filters

    Returns:
        SearchResponse with ranked results and metadata
    """
    start_time = datetime.now()
    supabase = get_supabase_client()

    try:
        # Step 1: Generate query embedding
        logger.info(f"Generating embedding for query: '{request.query}'")
        query_embedding = await generate_embedding(request.query)

        # Step 2: Prepare query text for full-text search
        query_text = _prepare_query_text(request.query)
        logger.debug(f"Prepared tsquery text: '{query_text}'")

        # Step 3: Build filter parameters
        filters = request.filters or SearchFilters()
        filter_params = {
            "query_text": query_text,
            "query_embedding": query_embedding,
            "match_threshold": request.match_threshold,
            "match_count": request.match_count,
            "semantic_weight": request.semantic_weight,
            "keyword_weight": request.keyword_weight,
            "filter_source": filters.source,
            "filter_author_id": filters.author_id,
            "filter_conversation_id": filters.conversation_id,
            "filter_start_date": filters.start_date.isoformat() if filters.start_date else None,
            "filter_end_date": filters.end_date.isoformat() if filters.end_date else None,
        }

        # Step 4: Execute hybrid search function
        logger.info(
            f"Executing hybrid search: threshold={request.match_threshold}, "
            f"weights=({request.semantic_weight}/{request.keyword_weight})"
        )
        response = supabase.rpc("hybrid_search", filter_params).execute()

        if not response.data:
            logger.info("No results found")
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return SearchResponse(
                results=[],
                total_results=0,
                query=request.query,
                execution_time_ms=execution_time,
                reranking_applied=False,
            )

        # Step 5: Convert to SearchResult models
        results = [
            SearchResult(
                id=row["id"],
                title=row["title"] or "",
                content=row["content"] or "",
                source=row["source"],
                author_name=row["author_name"],
                conversation_name=row["conversation_name"],
                timestamp=row["normalized_timestamp"],
                semantic_score=row["semantic_score"],
                keyword_score=row["keyword_score"],
                combined_score=row["combined_score"],
                metadata=row["metadata"] or {},
            )
            for row in response.data
        ]

        logger.info(f"Found {len(results)} results before reranking")

        # Step 6: Apply Cohere reranking if enabled
        reranking_applied = False
        if request.use_reranking and settings.cohere_api_key and len(results) > 1:
            logger.info("Applying Cohere reranking")
            results = await _rerank_results(request.query, results)
            reranking_applied = True
            logger.info(f"Reranking complete: top result score={results[0].rerank_score:.4f}")

        # Step 7: Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"Search complete: {len(results)} results in {execution_time:.2f}ms "
            f"(reranking={'enabled' if reranking_applied else 'disabled'})"
        )

        return SearchResponse(
            results=results,
            total_results=len(results),
            query=request.query,
            execution_time_ms=execution_time,
            reranking_applied=reranking_applied,
        )

    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"Search failed after {execution_time:.2f}ms: {e}")
        raise


async def _rerank_results(query: str, results: list[SearchResult]) -> list[SearchResult]:
    """
    Rerank search results using Cohere's rerank model.

    Cohere's rerank models are specifically trained to improve search relevance
    by understanding the semantic relationship between query and documents.

    Args:
        query: Original search query
        results: Initial search results from hybrid search

    Returns:
        Reranked list of SearchResult objects with rerank_score populated
    """
    if not results:
        return results

    try:
        client = _get_cohere_client()

        # Prepare documents for reranking
        # Combine title and content for better context
        documents = [
            f"{result.title}\n\n{result.content[:500]}"  # Limit content length
            for result in results
        ]

        # Call Cohere rerank API
        logger.debug(f"Reranking {len(documents)} documents with query: '{query}'")
        rerank_response = await client.rerank(
            model=settings.cohere_rerank_model,
            query=query,
            documents=documents,
            top_n=len(documents),  # Rerank all results
            return_documents=False,  # We already have the documents
        )

        # Map rerank scores back to results
        reranked_results = []
        for rerank_result in rerank_response.results:
            original_index = rerank_result.index
            result = results[original_index]
            result.rerank_score = rerank_result.relevance_score
            reranked_results.append(result)

        logger.info(
            f"Reranking complete: score range [{reranked_results[-1].rerank_score:.4f}, "
            f"{reranked_results[0].rerank_score:.4f}]"
        )

        return reranked_results

    except Exception as e:
        logger.warning(f"Reranking failed, returning original order: {e}")
        # Return original results if reranking fails
        return results


async def simple_vector_search(
    query: str,
    match_count: int = 10,
    match_threshold: float = 0.7,
    filters: SearchFilters | None = None,
) -> list[SearchResult]:
    """
    Simple vector similarity search without keyword matching or reranking.

    Useful for:
    - Quick semantic search
    - When keyword matching is not needed
    - Testing and debugging

    Args:
        query: Search query text
        match_count: Maximum number of results
        match_threshold: Minimum similarity score
        filters: Optional metadata filters

    Returns:
        List of SearchResult objects ordered by semantic similarity
    """
    # Reuse hybrid search with keyword weight = 0
    request = SearchRequest(
        query=query,
        match_count=match_count,
        match_threshold=match_threshold,
        semantic_weight=1.0,
        keyword_weight=0.0,
        use_reranking=False,
        filters=filters,
    )

    response = await hybrid_search(request)
    return response.results
