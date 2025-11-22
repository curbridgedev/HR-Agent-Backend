-- Migration: Improve vector search accuracy
-- This migration updates the hybrid_search function to:
-- 1. Lower the default threshold for better recall
-- 2. Improve keyword matching (title + content)
-- 3. Adjust similarity scoring weights (60% vector, 40% keyword)
-- 4. More lenient filtering to capture more relevant results

-- Drop existing function
DROP FUNCTION IF EXISTS hybrid_search(vector(1536), text, float, int, text);

-- Create improved hybrid_search function
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text text,
    match_threshold float DEFAULT 0.45,  -- Lower default for better recall
    match_count int DEFAULT 15,  -- Increased from 10 to get more candidates
    filter_province TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    content TEXT,
    source TEXT,
    doc_timestamp TIMESTAMPTZ,
    metadata JSONB,
    similarity float,
    document_title TEXT,
    document_filename TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        kb.id,
        kb.title,
        kb.content,
        kb.source_type AS source,
        kb.created_at AS doc_timestamp,
        kb.metadata,
        -- Improved similarity scoring optimized for large chunks
        -- Use cosine distance (<=>) which is normalized and works better for large chunks
        -- Normalize vector similarity to 0-1 range, then combine with keyword matching
        CASE 
            WHEN kb.embedding IS NOT NULL THEN
                -- Vector similarity: use 1 - cosine_distance (normalized, works well for large chunks)
                -- Scale to 0-1 range for better comparison
                LEAST(1.0, GREATEST(0.0, (1 - (kb.embedding <=> query_embedding)) * 1.2)) * 0.6 +
                CASE 
                    -- Exact keyword matches get highest boost
                    WHEN kb.content ILIKE '%' || query_text || '%' THEN 0.4
                    WHEN kb.title ILIKE '%' || query_text || '%' THEN 0.35  -- Boost title matches
                    -- Partial matches (word boundaries)
                    WHEN kb.content ~* ('\y' || query_text || '\y') THEN 0.3  -- Word boundary match
                    WHEN kb.content ILIKE '%' || LOWER(query_text) || '%' THEN 0.25  -- Case-insensitive partial
                    WHEN kb.content ILIKE '%' || UPPER(query_text) || '%' THEN 0.25  -- Case-insensitive partial
                    ELSE 0.0
                END
            ELSE 0.0
        END AS similarity,
        -- Include document title and filename for better source display
        COALESCE(d.title, d.filename, d.original_filename, 'Unknown Document') AS document_title,
        COALESCE(d.original_filename, d.filename, 'Unknown') AS document_filename
    FROM knowledge_base kb
    LEFT JOIN documents d ON kb.document_id = d.id
    WHERE
        kb.embedding IS NOT NULL
        AND (
            -- Keyword matches bypass vector threshold entirely for better recall
            -- This ensures exact term matches (like "Apportionment") are always found
            -- Use word boundary matching for better precision
            kb.content ILIKE '%' || query_text || '%'
            OR kb.title ILIKE '%' || query_text || '%'
            OR kb.content ~* ('\y' || query_text || '\y')  -- Word boundary regex match
            OR kb.content ILIKE '%' || LOWER(query_text) || '%'
            OR kb.content ILIKE '%' || UPPER(query_text) || '%'
            -- OR vector similarity meets threshold (optimized for large chunks: 75% of threshold)
            -- Cosine distance works well for large chunks, so we can be more lenient
            OR 1 - (kb.embedding <=> query_embedding) > (match_threshold * 0.75)
        )
        -- Province filtering: match province or 'ALL' (for federal/multi-province docs)
        AND (
            filter_province IS NULL  -- No filter: include all documents
            OR (
                d.province = filter_province  -- Match specific province
                OR d.province = 'ALL'  -- Include federal/multi-province documents
            )
        )
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION hybrid_search(vector(1536), text, float, int, text) IS 
    'Improved hybrid search with better accuracy: 60% vector similarity + 40% keyword matching. Lower default threshold (0.45) and increased result count (15) for better recall. Matches on both content and title.';

