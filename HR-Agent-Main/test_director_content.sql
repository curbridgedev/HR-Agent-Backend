-- Check if chunks exist with "Director" and "Collection" content
SELECT 
    kb.id,
    kb.title,
    LEFT(kb.content, 200) as content_preview,
    d.province,
    d.filename
FROM knowledge_base kb
LEFT JOIN documents d ON kb.document_id = d.id
WHERE kb.content ILIKE '%Director%'
  AND (kb.content ILIKE '%Collection%' OR kb.content ILIKE '%Debt%' OR kb.content ILIKE '%Settlement%')
LIMIT 10;

-- Check similarity scores for the query
-- This will show what the actual similarity scores are
WITH query_embedding AS (
    SELECT embedding FROM knowledge_base 
    WHERE content ILIKE '%Director%' 
    LIMIT 1
)
SELECT 
    kb.title,
    LEFT(kb.content, 150) as preview,
    d.province,
    1 - (kb.embedding <=> qe.embedding) AS similarity_score
FROM knowledge_base kb
CROSS JOIN query_embedding qe
LEFT JOIN documents d ON kb.document_id = d.id
WHERE kb.content ILIKE '%Director%'
  AND (kb.content ILIKE '%Collection%' OR kb.content ILIKE '%Debt%')
ORDER BY similarity_score DESC
LIMIT 10;

