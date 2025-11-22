-- Let's manually test the exact search that's failing
-- We'll use an actual embedding from your knowledge_base

-- Step 1: Get a real embedding to test with
WITH test_embedding AS (
    SELECT embedding FROM knowledge_base LIMIT 1
)
-- Step 2: Test the hybrid_search function with that embedding
SELECT 
    title,
    LEFT(content, 100) as content_preview,
    similarity
FROM hybrid_search(
    query_embedding := (SELECT embedding FROM test_embedding),
    query_text := 'employer',
    match_threshold := 0.01,  -- Very low threshold
    match_count := 10
);

-- If this returns 0 rows, there's still a problem with the function
-- If this returns rows, then the issue is with the parameters being passed from the backend

