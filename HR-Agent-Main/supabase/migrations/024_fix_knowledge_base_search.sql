-- Fix search functions to use knowledge_base table instead of documents
-- This is where chunks are actually stored!

-- Drop old functions if they exist (to avoid signature conflicts)
DROP FUNCTION IF EXISTS match_documents(vector(1536), float, int);
DROP FUNCTION IF EXISTS hybrid_search(vector(1536), text, float, int);
DROP FUNCTION IF EXISTS hybrid_search(text, vector(1536), int, text, text);

-- Function: Vector similarity search on knowledge_base
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.75,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    content TEXT,
    source TEXT,
    doc_timestamp TIMESTAMPTZ,
    metadata JSONB,
    similarity float
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
        1 - (kb.embedding <=> query_embedding) AS similarity
    FROM knowledge_base kb
    WHERE
        kb.embedding IS NOT NULL
        AND 1 - (kb.embedding <=> query_embedding) > match_threshold
    ORDER BY kb.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Function: Hybrid search (vector + keyword) on knowledge_base
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text text,
    match_threshold float DEFAULT 0.70,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    content TEXT,
    source TEXT,
    doc_timestamp TIMESTAMPTZ,
    metadata JSONB,
    similarity float
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
        CASE 
            WHEN kb.embedding IS NOT NULL THEN
                (1 - (kb.embedding <=> query_embedding)) * 0.7 +
                CASE 
                    WHEN kb.content ILIKE '%' || query_text || '%' THEN 0.3
                    ELSE 0.0
                END
            ELSE 0.0
        END AS similarity
    FROM knowledge_base kb
    WHERE
        kb.embedding IS NOT NULL
        AND (
            1 - (kb.embedding <=> query_embedding) > match_threshold
            OR kb.content ILIKE '%' || query_text || '%'
        )
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

-- Add helpful comments
COMMENT ON FUNCTION match_documents(vector(1536), float, int) IS 
    'Vector similarity search on knowledge_base table using cosine distance';

COMMENT ON FUNCTION hybrid_search(vector(1536), text, float, int) IS 
    'Hybrid search combining vector similarity (70%) and keyword matching (30%) on knowledge_base table';

