"""
Vector search operations with Supabase pgvector.
"""

import re
from typing import List, Dict, Any, Optional
from supabase import Client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def sanitize_text_for_tsquery(text: str) -> str:
    """
    Sanitize text for PostgreSQL full-text search (tsquery).

    Formats text for to_tsquery() by joining words with & (AND operator).
    Example: "What is Compaytence?" -> "What & is & Compaytence"

    Args:
        text: Raw query text

    Returns:
        Sanitized text formatted for to_tsquery()
    """
    # Remove special tsquery characters
    # Keep alphanumeric, spaces, and hyphens
    sanitized = re.sub(r'[&|!()<>:*?\'",.]', ' ', text)

    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)

    # Trim whitespace
    sanitized = sanitized.strip()

    # If empty after sanitization, return a safe default
    if not sanitized:
        return "search"

    # Split into words and filter out common stop words for better search
    # (Optional: keep stop words for more accurate phrase matching)
    words = sanitized.split()

    # Filter out very short words (1-2 chars) that might cause issues
    # But keep meaningful short words
    meaningful_words = [w for w in words if len(w) >= 2 or w.lower() in {'a', 'i'}]

    # If no words left after filtering, use original words
    if not meaningful_words:
        meaningful_words = words

    # Join with & for AND operation in tsquery
    tsquery_format = " & ".join(meaningful_words)

    return tsquery_format


async def vector_search(
    db: Client,
    query_embedding: List[float],
    table_name: str = "documents",
    match_threshold: Optional[float] = None,
    match_count: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Perform vector similarity search using pgvector.

    Args:
        db: Supabase client instance
        query_embedding: Query vector embedding
        table_name: Table to search in
        match_threshold: Similarity threshold (0-1), defaults to settings
        match_count: Number of results to return, defaults to settings

    Returns:
        List of matching documents with similarity scores
    """
    threshold = match_threshold or settings.vector_similarity_threshold
    count = match_count or settings.vector_max_results

    try:
        # Use Supabase RPC function for vector search
        # This function should be created in Supabase:
        # CREATE FUNCTION match_documents(query_embedding vector(1536), match_threshold float, match_count int)
        response = (
            db.rpc(
                "match_documents",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": count,
                },
            )
            .execute()
        )

        return response.data if response.data else []

    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise


async def hybrid_search(
    db: Client,
    query_embedding: List[float],
    query_text: str,
    table_name: str = "documents",
    match_threshold: Optional[float] = None,
    match_count: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search (vector + keyword) for better results.

    Combines vector similarity with full-text search for optimal retrieval.

    Args:
        db: Supabase client instance
        query_embedding: Query vector embedding
        query_text: Query text for keyword search
        table_name: Table to search in
        match_threshold: Similarity threshold (0-1)
        match_count: Number of results to return

    Returns:
        List of matching documents with combined scores
    """
    threshold = match_threshold or settings.vector_similarity_threshold
    count = match_count or settings.vector_max_results

    try:
        # Sanitize query text for PostgreSQL full-text search
        sanitized_query = sanitize_text_for_tsquery(query_text)

        logger.debug(f"Hybrid search: original='{query_text}', sanitized='{sanitized_query}'")

        # Use Supabase RPC function for hybrid search
        # This combines vector similarity with PostgreSQL full-text search
        response = (
            db.rpc(
                "hybrid_search",
                {
                    "query_embedding": query_embedding,
                    "query_text": sanitized_query,
                    "match_threshold": threshold,
                    "match_count": count,
                },
            )
            .execute()
        )

        logger.info(f"Hybrid search successful: {len(response.data) if response.data else 0} results")
        return response.data if response.data else []

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        # Fallback to vector-only search if hybrid fails
        logger.warning("Falling back to vector-only search")
        return await vector_search(db, query_embedding, table_name, match_threshold, match_count)


async def insert_document(
    db: Client,
    content: str,
    embedding: List[float],
    metadata: Dict[str, Any],
    table_name: str = "documents",
) -> Dict[str, Any]:
    """
    Insert a document with its embedding into the vector store.

    Args:
        db: Supabase client instance
        content: Document content
        embedding: Document vector embedding
        metadata: Document metadata (source, timestamp, etc.)
        table_name: Table to insert into

    Returns:
        Inserted document record
    """
    try:
        response = (
            db.table(table_name)
            .insert(
                {
                    "content": content,
                    "embedding": embedding,
                    "metadata": metadata,
                }
            )
            .execute()
        )

        if response.data:
            logger.info(f"Document inserted successfully: {response.data[0].get('id')}")
            return response.data[0]
        else:
            raise Exception("No data returned from insert operation")

    except Exception as e:
        logger.error(f"Document insertion failed: {e}")
        raise


async def delete_document(
    db: Client,
    document_id: str,
    table_name: str = "documents",
) -> bool:
    """
    Delete a document from the vector store.

    Args:
        db: Supabase client instance
        document_id: Document ID to delete
        table_name: Table to delete from

    Returns:
        True if deletion successful
    """
    try:
        response = (
            db.table(table_name)
            .delete()
            .eq("id", document_id)
            .execute()
        )

        logger.info(f"Document deleted: {document_id}")
        return True

    except Exception as e:
        logger.error(f"Document deletion failed: {e}")
        raise
