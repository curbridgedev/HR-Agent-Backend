-- SUPER SIMPLE TEST: Just count chunks
SELECT COUNT(*) as total_chunks 
FROM knowledge_base;

-- If you get 0, the problem is no data uploaded
-- If you get > 0, then we have a search function issue

-- Test 2: Show me what's in there
SELECT 
    title,
    LEFT(content, 200) as preview,
    CASE WHEN embedding IS NOT NULL THEN 'HAS EMBEDDING' ELSE 'NO EMBEDDING' END as embedding_status
FROM knowledge_base
LIMIT 3;

