-- Fix existing documents that have empty title, content, or source
-- This migration updates documents that were created before the ingestion service was fixed

-- Update documents with empty title to use filename
UPDATE documents
SET title = COALESCE(
    NULLIF(title, ''),
    NULLIF(filename, ''),
    original_filename,
    'Untitled Document'
)
WHERE title IS NULL OR title = '';

-- Update documents with empty source to use 'admin_upload' (most common)
UPDATE documents
SET source = COALESCE(
    NULLIF(source, ''),
    'admin_upload'
)
WHERE source IS NULL OR source = '';

-- Update documents with empty content to use a placeholder
-- (Content is stored in chunks, so this is just for the preview)
UPDATE documents
SET content = COALESCE(
    NULLIF(content, ''),
    'Document content is stored in knowledge_base chunks. Use search to retrieve specific sections.'
)
WHERE content IS NULL OR content = '';

-- Set default province to 'ALL' for documents without province
UPDATE documents
SET province = 'ALL'
WHERE province IS NULL;

-- Set default approval_status to 'approved' for existing documents
-- (They were uploaded before approval workflow, so auto-approve them)
UPDATE documents
SET approval_status = 'approved'
WHERE approval_status IS NULL OR approval_status = 'pending'
  AND created_at < NOW() - INTERVAL '1 day';  -- Only auto-approve old documents

-- Add comments
COMMENT ON COLUMN documents.title IS 'Document title (from filename if not provided)';
COMMENT ON COLUMN documents.content IS 'Content preview/summary (full content in knowledge_base chunks)';
COMMENT ON COLUMN documents.source IS 'Source of document (admin_upload, api_upload, etc.)';
COMMENT ON COLUMN documents.province IS 'Canadian province (MB, ON, SK, AB, BC, or ALL for federal/multi-province)';

