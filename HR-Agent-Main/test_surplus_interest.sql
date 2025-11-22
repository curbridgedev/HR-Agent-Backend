-- Test 1: Does "surplus interest" exist in your knowledge base?
SELECT 
    title,
    LEFT(content, 200) as preview,
    chunk_index
FROM knowledge_base
WHERE content ILIKE '%surplus interest%'
LIMIT 5;

-- Test 2: Try broader search for "surplus" or "interest"
SELECT 
    title,
    LEFT(content, 150) as preview
FROM knowledge_base
WHERE content ILIKE '%surplus%'
   OR content ILIKE '%Director may use%'
LIMIT 5;

-- Test 3: What's the actual similarity score for "surplus interest" query?
-- (Using a test embedding from the knowledge base)
WITH test_query AS (
    SELECT embedding FROM knowledge_base 
    WHERE content ILIKE '%surplus interest%' 
    LIMIT 1
)
SELECT 
    title,
    LEFT(content, 150) as preview,
    1 - (kb.embedding <=> tq.embedding) AS similarity
FROM knowledge_base kb, test_query tq
WHERE content ILIKE '%surplus interest%'
LIMIT 1;

