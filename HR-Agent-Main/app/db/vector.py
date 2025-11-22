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
    province: Optional[str] = None,  # Filter by province (MB, ON, SK, AB, BC, or None for all)
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
        # NOTE: Do NOT sanitize query_text for ILIKE search
        # The hybrid_search function uses ILIKE which needs plain text, not tsquery format
        # Sanitization would break pattern matching

        logger.debug(f"Hybrid search: query='{query_text}', threshold={threshold}")
        logger.debug(f"Search params: threshold={threshold}, count={count}, embedding_len={len(query_embedding)}")
        logger.debug(f"Embedding type: {type(query_embedding)}, first 3 values: {query_embedding[:3] if len(query_embedding) > 0 else 'empty'}")

        # Count total available chunks before filtering
        try:
            count_query = db.table("knowledge_base").select("id", count="exact")
            if province:
                # Join with documents to filter by province
                count_query = (
                    db.table("knowledge_base")
                    .select("id", count="exact")
                    .eq("embedding", None, invert=True)  # Has embedding
                )
                # Get count via a separate query that joins with documents
                doc_ids_response = (
                    db.table("documents")
                    .select("id")
                    .in_("province", [province, "ALL"])
                    .execute()
                )
                if doc_ids_response.data:
                    doc_ids = [doc["id"] for doc in doc_ids_response.data]
                    count_response = (
                        db.table("knowledge_base")
                        .select("id", count="exact")
                        .in_("document_id", doc_ids)
                        .not_.is_("embedding", "null")
                        .execute()
                    )
                    total_chunks = count_response.count if hasattr(count_response, 'count') else len(count_response.data) if count_response.data else 0
                else:
                    total_chunks = 0
            else:
                count_response = (
                    db.table("knowledge_base")
                    .select("id", count="exact")
                    .not_.is_("embedding", "null")
                    .execute()
                )
                total_chunks = count_response.count if hasattr(count_response, 'count') else len(count_response.data) if count_response.data else 0
            
            logger.info(f"📊 Total available chunks in knowledge_base: {total_chunks} (province filter: {province or 'NONE'})")
        except Exception as count_error:
            logger.warning(f"Could not count available chunks: {count_error}")
            total_chunks = "unknown"

        # Use Supabase RPC function for hybrid search
        # Pass original query text for ILIKE matching
        rpc_params = {
            "query_embedding": query_embedding,
            "query_text": query_text,  # Use original text, not sanitized
            "match_threshold": threshold,
            "match_count": count,
        }
        
        # Add province filter if provided
        if province:
            rpc_params["filter_province"] = province
            logger.info(f"🔍 Province filter applied: {province}")
        else:
            logger.warning("⚠️ No province filter provided - will return documents from all provinces")
        
        logger.debug(f"RPC params: query_text='{query_text}', threshold={threshold}, count={count}, province={province}")
        
        response = (
            db.rpc("hybrid_search", rpc_params)
            .execute()
        )

        # Log province info for returned documents
        if response.data and len(response.data) > 0:
            provinces_found = set()
            for doc in response.data:
                # Try to get province from metadata or document info
                doc_province = doc.get("metadata", {}).get("province") or "unknown"
                provinces_found.add(doc_province)
            logger.info(f"✅ Hybrid search successful: {len(response.data)} results")
            if province:
                logger.info(f"   Expected province: {province}, Found provinces in results: {provinces_found}")
                if province not in provinces_found and "ALL" not in provinces_found:
                    logger.warning(f"⚠️ WARNING: Province filter '{province}' applied but results contain provinces: {provinces_found}")
        else:
            logger.info(f"Hybrid search successful: {len(response.data) if response.data else 0} results")
        logger.debug(f"Response data type: {type(response.data)}, Response count: {response.count if hasattr(response, 'count') else 'N/A'}")
        
        # Add detailed logging when no results
        if not response.data or len(response.data) == 0:
            logger.warning(f"❌ Hybrid search returned 0 results!")
            logger.warning(f"   Query: '{query_text}'")
            logger.warning(f"   Threshold: {threshold} (effective: {threshold * 0.75:.3f} for vector)")
            logger.warning(f"   Total available chunks: {total_chunks if 'total_chunks' in locals() else 'unknown'}")
            logger.warning(f"   Province filter: {province or 'NONE'}")
            logger.warning(f"   Embedding length: {len(query_embedding)}")
            
            # Check if keyword exists in any chunks (for debugging)
            try:
                keyword_check = (
                    db.table("knowledge_base")
                    .select("id, title, content", count="exact")
                    .or_(f"content.ilike.%{query_text}%,title.ilike.%{query_text}%")
                    .limit(5)
                    .execute()
                )
                keyword_matches = keyword_check.count if hasattr(keyword_check, 'count') else len(keyword_check.data) if keyword_check.data else 0
                logger.warning(f"   Keyword matches (no filters): {keyword_matches}")
                if keyword_check.data:
                    logger.warning(f"   Sample matches: {[doc.get('title', 'no title')[:50] for doc in keyword_check.data[:3]]}")
            except Exception as kw_error:
                logger.debug(f"   Could not check keyword matches: {kw_error}")
            
            logger.warning(f"   💡 Suggestions:")
            logger.warning(f"      - Lower VECTOR_SIMILARITY_THRESHOLD (current: {threshold})")
            logger.warning(f"      - Check if chunks exist for province: {province or 'ALL'}")
            logger.warning(f"      - Verify keyword '{query_text}' exists in knowledge_base")
        
        return response.data if response.data else []

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}", exc_info=True)
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
