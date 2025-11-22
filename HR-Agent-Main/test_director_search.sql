-- Test 1: Check if document exists and what province it's tagged with
SELECT 
    d.id,
    d.filename,
    d.province,
    d.processing_status,
    COUNT(kb.id) as chunk_count
FROM documents d
LEFT JOIN knowledge_base kb ON kb.document_id = d.id
WHERE d.filename ILIKE '%collection%' 
   OR d.filename ILIKE '%debt%'
   OR d.filename ILIKE '%settlement%'
GROUP BY d.id, d.filename, d.province, d.processing_status;

-- Test 2: Check if chunks exist for this document
SELECT 
    kb.id,
    kb.title,
    LEFT(kb.content, 150) as content_preview,
    d.province as doc_province
FROM knowledge_base kb
LEFT JOIN documents d ON kb.document_id = d.id
WHERE kb.content ILIKE '%Director%'
   AND kb.content ILIKE '%Collection%'
LIMIT 5;

-- Test 3: Test the hybrid_search function directly with province filter
-- First, get an embedding from a chunk that mentions Director
WITH test_embedding AS (
    SELECT embedding FROM knowledge_base 
    WHERE content ILIKE '%Director%' 
      AND content ILIKE '%Collection%'
    LIMIT 1
)
SELECT 
    kb.title,
    LEFT(kb.content, 150) as preview,
    d.province,
    similarity
FROM hybrid_search(
    query_embedding := (SELECT embedding FROM test_embedding),
    query_text := 'Director Collection and Debt Settlement Services Act',
    match_threshold := 0.01,  -- Very low to see ANY results
    match_count := 10,
    filter_province := 'ON'
) kb
LEFT JOIN documents d ON kb.id::text = d.id::text
LIMIT 5;

-- Test 4: Test WITHOUT province filter (to see if chunks exist at all)
WITH test_embedding AS (
    SELECT embedding FROM knowledge_base 
    WHERE content ILIKE '%Director%' 
    LIMIT 1
)
SELECT 
    kb.title,
    LEFT(kb.content, 150) as preview,
    d.province,
    similarity
FROM hybrid_search(
    query_embedding := (SELECT embedding FROM test_embedding),
    query_text := 'Director',
    match_threshold := 0.01,
    match_count := 10,
    filter_province := NULL  -- No filter
) kb
LEFT JOIN documents d ON kb.id::text = d.id::text
LIMIT 5;

