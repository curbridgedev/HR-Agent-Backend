-- Verify province filtering is working correctly
-- Run this in Supabase SQL Editor to check:

-- 1. Check if hybrid_search function exists with province filter
SELECT 
    p.proname as function_name,
    pg_get_function_arguments(p.oid) as arguments
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE p.proname = 'hybrid_search'
AND n.nspname = 'public';

-- 2. Check document province distribution
SELECT 
    province,
    COUNT(*) as document_count
FROM documents
GROUP BY province
ORDER BY document_count DESC;

-- 3. Check if any documents have NULL province (these shouldn't be included when filtering)
SELECT 
    COUNT(*) as null_province_count
FROM documents
WHERE province IS NULL;

-- 4. Test the province filter directly
-- Replace 'ON' with the province you want to test
-- This should ONLY return documents with province='ON' or province='ALL'
SELECT 
    d.id,
    d.title,
    d.province,
    COUNT(kb.id) as chunk_count
FROM documents d
LEFT JOIN knowledge_base kb ON kb.document_id = d.id
WHERE d.province = 'ON' OR d.province = 'ALL'
GROUP BY d.id, d.title, d.province
ORDER BY chunk_count DESC
LIMIT 10;

-- 5. Check for Manitoba documents (should NOT appear when filtering for Ontario)
SELECT 
    d.id,
    d.title,
    d.province,
    COUNT(kb.id) as chunk_count
FROM documents d
LEFT JOIN knowledge_base kb ON kb.document_id = d.id
WHERE d.province = 'MB'
GROUP BY d.id, d.title, d.province
ORDER BY chunk_count DESC
LIMIT 10;

