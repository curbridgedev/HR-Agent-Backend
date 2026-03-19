-- Chat attachments: files attached to chat messages
-- Files are stored in Supabase Storage (chat-attachments bucket or hr-agent-documents/chat-attachments/)
-- Create bucket via Supabase Dashboard if not exists: Storage > New bucket > chat-attachments (private)

CREATE TABLE IF NOT EXISTS public.chat_attachments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
  session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  file_type TEXT NOT NULL,
  file_size_bytes BIGINT NOT NULL,
  storage_path TEXT NOT NULL,
  mime_type TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_attachments_message_id ON chat_attachments(message_id);
CREATE INDEX IF NOT EXISTS idx_chat_attachments_session_id ON chat_attachments(session_id);

COMMENT ON TABLE chat_attachments IS 'Files attached to chat messages; stored in Supabase Storage';
