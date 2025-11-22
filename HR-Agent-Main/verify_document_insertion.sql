-- Verify documents are being inserted correctly
-- Run this after uploading a new document to check all fields are populated

-- Check recent documents (last 24 hours)
SELECT 
    id,
    title,
    COALESCE(LEFT(content, 50), 'NULL') as content_preview,
    source,
    province,
    document_type,
    approval_status,
    filename,
    file_type,
    chunk_count,
    processing_status,
    created_at
FROM documents
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC
LIMIT 10;

-- Check for documents with missing required fields
SELECT 
    COUNT(*) as documents_with_missing_fields,
    COUNT(CASE WHEN title IS NULL OR title = '' THEN 1 END) as missing_title,
    COUNT(CASE WHEN source IS NULL OR source = '' THEN 1 END) as missing_source,
    COUNT(CASE WHEN province IS NULL THEN 1 END) as missing_province,
    COUNT(CASE WHEN filename IS NULL THEN 1 END) as missing_filename
FROM documents;

-- Verify chunks are linked correctly
SELECT 
    d.id as doc_id,
    d.title,
    d.province,
    COUNT(kb.id) as chunk_count,
    d.chunk_count as doc_chunk_count,
    CASE 
        WHEN COUNT(kb.id) = d.chunk_count THEN '✅ Match'
        ELSE '⚠️ Mismatch'
    END as status
FROM documents d
LEFT JOIN knowledge_base kb ON kb.document_id = d.id
GROUP BY d.id, d.title, d.province, d.chunk_count
ORDER BY d.created_at DESC
LIMIT 10;

