-- Debug queries to diagnose search issues
-- Run these in Supabase SQL Editor to see what's happening

-- 1. Check if chunks exist
SELECT 
    COUNT(*) as total_chunks,
    COUNT(DISTINCT document_id) as unique_documents,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as chunks_with_embeddings
FROM knowledge_base;

-- 2. Sample some chunks to verify content
SELECT 
    id,
    title,
    LEFT(content, 100) as content_preview,
    chunk_index,
    tokens,
    CASE WHEN embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_embedding,
    created_at
FROM knowledge_base
ORDER BY created_at DESC
LIMIT 5;

-- 3. Check documents table (should have parent records)
SELECT 
    id,
    filename,
    processing_status,
    chunk_count,
    created_at
FROM documents
ORDER BY created_at DESC
LIMIT 5;

-- 4. Test the hybrid_search function with a simple query
-- This tests if the function itself works
SELECT 
    id,
    title,
    LEFT(content, 100) as content_preview,
    similarity
FROM hybrid_search(
    query_embedding := (SELECT embedding FROM knowledge_base LIMIT 1), -- Use an existing embedding
    query_text := 'employee',
    match_threshold := 0.01, -- Very low threshold to see ANY results
    match_count := 5
);

-- 5. Check embedding dimensions
SELECT 
    id,
    title,
    array_length(embedding, 1) as embedding_dimensions
FROM knowledge_base
WHERE embedding IS NOT NULL
LIMIT 3;

