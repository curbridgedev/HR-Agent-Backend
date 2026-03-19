-- Add project_id to documents for project-scoped documents
-- project_id = NULL -> global KB (current behavior)
-- project_id = X -> project-scoped document

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id);
