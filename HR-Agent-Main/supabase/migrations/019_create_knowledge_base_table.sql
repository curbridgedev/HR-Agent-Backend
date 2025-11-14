-- Create knowledge_base table for document chunks
-- This table stores individual chunks of documents with their embeddings

CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Link to parent document
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Chunk metadata
    title TEXT,
    content TEXT NOT NULL,
    
    -- Vector embedding for semantic search
    embedding vector(1536),
    
    -- Source information (to match documents table structure)
    source_type TEXT,
    source_id TEXT,
    
    -- Chunk metadata
    chunk_index INTEGER NOT NULL,
    tokens INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_knowledge_base_document_id ON knowledge_base(document_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_chunk_index ON knowledge_base(chunk_index);

-- HNSW index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_knowledge_base_embedding ON knowledge_base
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- GIN index for full-text search
CREATE INDEX IF NOT EXISTS idx_knowledge_base_content_gin ON knowledge_base
USING gin(to_tsvector('english', content));

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_knowledge_base_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_knowledge_base_updated_at
    BEFORE UPDATE ON knowledge_base
    FOR EACH ROW
    EXECUTE FUNCTION update_knowledge_base_updated_at();

