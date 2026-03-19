-- Add project_id to chat_sessions for project-based chats
-- project_id = NULL -> individual chat (current behavior)
-- project_id = X -> project chat

ALTER TABLE chat_sessions
ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_project_id ON chat_sessions(project_id);
