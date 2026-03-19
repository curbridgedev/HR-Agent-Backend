-- Add project filter to hybrid_search for project-based RAG
-- When filter_project_id is set: include project docs + global KB (d.project_id = X OR d.project_id IS NULL)
-- When filter_project_id is NULL: no project filtering (current behavior)

-- Drop all existing versions of the function
DROP FUNCTION IF EXISTS hybrid_search(vector(1536), text, float, int);
DROP FUNCTION IF EXISTS hybrid_search(vector(1536), text, float, int, text);

-- Create hybrid_search with province and project filters
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text text,
    match_threshold float DEFAULT 0.45,
    match_count int DEFAULT 15,
    filter_province TEXT DEFAULT NULL,
    filter_project_id UUID DEFAULT NULL
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
        CASE 
            WHEN kb.embedding IS NOT NULL THEN
                LEAST(1.0, GREATEST(0.0, (1 - (kb.embedding <=> query_embedding)) * 1.2)) * 0.6 +
                CASE 
                    WHEN kb.content ILIKE '%' || query_text || '%' THEN 0.4
                    WHEN kb.title ILIKE '%' || query_text || '%' THEN 0.35
                    WHEN kb.content ~* ('\y' || query_text || '\y') THEN 0.3
                    WHEN kb.content ILIKE '%' || LOWER(query_text) || '%' THEN 0.25
                    WHEN kb.content ILIKE '%' || UPPER(query_text) || '%' THEN 0.25
                    ELSE 0.0
                END
            ELSE 0.0
        END AS similarity,
        COALESCE(d.title, d.filename, d.original_filename, 'Unknown Document') AS document_title,
        COALESCE(d.original_filename, d.filename, 'Unknown') AS document_filename
    FROM knowledge_base kb
    LEFT JOIN documents d ON kb.document_id = d.id
    WHERE
        kb.embedding IS NOT NULL
        AND (
            kb.content ILIKE '%' || query_text || '%'
            OR kb.title ILIKE '%' || query_text || '%'
            OR kb.content ~* ('\y' || query_text || '\y')
            OR kb.content ILIKE '%' || LOWER(query_text) || '%'
            OR kb.content ILIKE '%' || UPPER(query_text) || '%'
            OR 1 - (kb.embedding <=> query_embedding) > (match_threshold * 0.75)
        )
        -- Province filtering
        AND (
            filter_province IS NULL
            OR (
                d.province = filter_province
                OR d.province = 'ALL'
            )
        )
        -- Project filtering: include project docs + global KB (project_id IS NULL)
        AND (
            filter_project_id IS NULL
            OR (
                d.project_id = filter_project_id
                OR d.project_id IS NULL
            )
        )
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION hybrid_search(vector(1536), text, float, int, text, uuid) IS 
    'Hybrid search with province and project filters. When filter_project_id is set, returns project docs + global KB.';
