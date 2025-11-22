-- Step 1: Verify the migration was run (check function signature)
SELECT 
    routine_name,
    array_agg(parameter_name || ' ' || data_type ORDER BY ordinal_position) as parameters
FROM information_schema.routines r
LEFT JOIN information_schema.parameters p ON r.specific_name = p.specific_name
WHERE routine_name = 'hybrid_search'
GROUP BY routine_name;

-- Step 2: Test the function directly with province filter
-- Use a real embedding from your knowledge_base
SELECT 
    kb.title,
    LEFT(kb.content, 150) as preview,
    d.province,
    similarity
FROM hybrid_search(
    query_embedding := (SELECT embedding FROM knowledge_base WHERE content ILIKE '%Director%' LIMIT 1),
    query_text := 'Director',
    match_threshold := 0.01,  -- Very low to see ANY results
    match_count := 10,
    filter_province := 'ON'
) kb
LEFT JOIN documents d ON kb.id::text = d.id::text
LIMIT 5;

-- Step 3: Check if "Collection and Debt Settlement Services Act" content exists
SELECT 
    COUNT(*) as chunks_with_collection_act
FROM knowledge_base kb
WHERE kb.content ILIKE '%Collection%'
  AND kb.content ILIKE '%Debt%'
  AND kb.content ILIKE '%Settlement%';

-- Step 4: Check similarity scores for Director queries
WITH test_query AS (
    -- Generate embedding for the actual query text
    SELECT embedding FROM knowledge_base 
    WHERE content ILIKE '%Director%' 
      AND content ILIKE '%Collection%'
    LIMIT 1
)
SELECT 
    kb.title,
    LEFT(kb.content, 100) as preview,
    1 - (kb.embedding <=> tq.embedding) AS similarity,
    CASE 
        WHEN 1 - (kb.embedding <=> tq.embedding) > 0.65 THEN '✅ Above threshold'
        WHEN 1 - (kb.embedding <=> tq.embedding) > 0.50 THEN '⚠️ Below threshold (0.65) but close'
        ELSE '❌ Too low'
    END as status
FROM knowledge_base kb
CROSS JOIN test_query tq
WHERE kb.content ILIKE '%Director%'
ORDER BY similarity DESC
LIMIT 10;

