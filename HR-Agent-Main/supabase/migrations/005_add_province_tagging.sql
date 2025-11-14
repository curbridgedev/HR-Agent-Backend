-- HR Agent - Province Tagging System
-- This migration adds Canadian province-specific tagging to documents

-- Add province column (Canadian provinces where HR agent operates)
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS province TEXT DEFAULT 'ALL' CHECK (
    province IN ('MB', 'ON', 'SK', 'AB', 'BC', 'ALL')
);

-- Add document type classification
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS document_type TEXT DEFAULT 'other' CHECK (
    document_type IN ('employment_standard', 'policy', 'template', 'sop', 'other')
);

-- Add topic/category for better organization
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS topic TEXT;

-- Add version tracking for document updates
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;

-- Add original filename (useful for admin console)
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS original_filename TEXT;

-- Add approval status for admin review workflow
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS approval_status TEXT DEFAULT 'pending' CHECK (
    approval_status IN ('pending', 'approved', 'banned', 'flagged')
);

-- Create indexes for efficient filtering
CREATE INDEX IF NOT EXISTS idx_documents_province ON documents(province);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_topic ON documents(topic);
CREATE INDEX IF NOT EXISTS idx_documents_approval ON documents(approval_status);

-- Create composite index for common query patterns (province + approval)
CREATE INDEX IF NOT EXISTS idx_documents_province_approval ON documents(province, approval_status);

-- Update the hybrid_search function to support province filtering
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text TEXT,
    query_embedding VECTOR(1536),
    match_count INT DEFAULT 10,
    filter_province TEXT DEFAULT NULL,
    filter_approval TEXT DEFAULT 'approved'
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    content TEXT,
    source TEXT,
    province TEXT,
    document_type TEXT,
    topic TEXT,
    similarity FLOAT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.title,
        d.content,
        d.source,
        d.province,
        d.document_type,
        d.topic,
        (
            -- Vector similarity (70% weight)
            (1 - (d.embedding <=> query_embedding)) * 0.7 +
            -- Text similarity (30% weight)
            SIMILARITY(d.content, query_text) * 0.3
        ) AS similarity,
        d.created_at
    FROM documents d
    WHERE 
        d.approval_status = filter_approval
        AND (filter_province IS NULL OR d.province = filter_province OR d.province = 'ALL')
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

-- Comment on new columns
COMMENT ON COLUMN documents.province IS 'Canadian province code: MB, ON, SK, AB, BC, or ALL for federal/multi-province documents';
COMMENT ON COLUMN documents.document_type IS 'Type of document: employment_standard, policy, template, sop, or other';
COMMENT ON COLUMN documents.topic IS 'Topic/category for organization (e.g., vacation, termination, overtime)';
COMMENT ON COLUMN documents.version IS 'Version number for tracking document updates';
COMMENT ON COLUMN documents.approval_status IS 'Admin review status: pending, approved, banned, or flagged for review';

