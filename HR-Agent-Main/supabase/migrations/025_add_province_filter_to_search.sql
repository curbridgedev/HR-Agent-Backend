-- Update hybrid_search function to support province filtering
-- This allows filtering knowledge_base chunks by province (MB, ON, SK, AB, BC, or ALL)

-- Drop all existing versions of the function
DROP FUNCTION IF EXISTS hybrid_search(vector(1536), text, float, int);
DROP FUNCTION IF EXISTS hybrid_search(vector(1536), text, float, int, text);

-- Function: Hybrid search (vector + keyword) on knowledge_base with province filter
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text text,
    match_threshold float DEFAULT 0.70,
    match_count int DEFAULT 10,
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
        -- Combine vector similarity (70%) + text match (30%)
        -- MUST be column 7 to match RETURNS TABLE
        CASE 
            WHEN kb.embedding IS NOT NULL THEN
                (1 - (kb.embedding <=> query_embedding)) * 0.7 +
                CASE 
                    WHEN kb.content ILIKE '%' || query_text || '%' THEN 0.3
                    ELSE 0.0
                END
            ELSE 0.0
        END AS similarity,
        -- Include document title and filename for better source display
        -- Columns 8 and 9
        COALESCE(d.title, d.filename, d.original_filename, 'Unknown Document') AS document_title,
        COALESCE(d.original_filename, d.filename, 'Unknown') AS document_filename
    FROM knowledge_base kb
    LEFT JOIN documents d ON kb.document_id = d.id
    WHERE
        kb.embedding IS NOT NULL
        AND (
            1 - (kb.embedding <=> query_embedding) > match_threshold
            OR kb.content ILIKE '%' || query_text || '%'
        )
        -- Province filtering: match province or 'ALL' (for federal/multi-province docs)
        -- When filter_province is provided, only include:
        --   1. Documents matching the filter_province
        --   2. Documents tagged as 'ALL' (federal/multi-province)
        -- When filter_province is NULL, include all documents (no filtering)
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
    'Hybrid search combining vector similarity (70%) and keyword matching (30%) on knowledge_base table with optional province filtering. Returns document_title and document_filename for better source display.';

