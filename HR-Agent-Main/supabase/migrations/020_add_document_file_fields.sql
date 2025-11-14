-- Add missing file-related columns to documents table
-- These are needed by the ingestion service

-- First, make title, content, and source nullable since chunks are stored separately
-- and source is derived from source_type for document chunks
ALTER TABLE documents 
ALTER COLUMN title DROP NOT NULL;

ALTER TABLE documents 
ALTER COLUMN content DROP NOT NULL;

ALTER TABLE documents 
ALTER COLUMN source DROP NOT NULL;

-- Add file-related columns
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS filename TEXT;

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS file_type TEXT;

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS storage_path TEXT;

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS chunk_count INTEGER DEFAULT 0;

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS total_tokens INTEGER DEFAULT 0;

-- Create index for filename searches
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);

-- Comments
COMMENT ON COLUMN documents.filename IS 'Original filename of the uploaded document';
COMMENT ON COLUMN documents.file_type IS 'File extension/type (pdf, docx, etc.)';
COMMENT ON COLUMN documents.file_size_bytes IS 'File size in bytes';
COMMENT ON COLUMN documents.storage_path IS 'Path where the file is stored';
COMMENT ON COLUMN documents.chunk_count IS 'Number of chunks created from this document';
COMMENT ON COLUMN documents.total_tokens IS 'Total token count across all chunks';

