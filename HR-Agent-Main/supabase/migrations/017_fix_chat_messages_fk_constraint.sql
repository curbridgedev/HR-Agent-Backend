-- Fix FK constraint: chat_messages should reference chat_sessions.session_id not chat_sessions.id
-- This fixes the issue where messages cannot be saved because the FK points to the wrong column

-- Drop the existing FK constraint
ALTER TABLE chat_messages
DROP CONSTRAINT IF EXISTS chat_messages_session_id_fkey;

-- Add the correct FK constraint pointing to session_id
ALTER TABLE chat_messages
ADD CONSTRAINT chat_messages_session_id_fkey
FOREIGN KEY (session_id)
REFERENCES chat_sessions(session_id)
ON DELETE CASCADE;

-- Create index on chat_sessions.session_id for FK performance (if not exists)
CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_id_fk
ON chat_sessions(session_id);

-- Verify the fix
COMMENT ON CONSTRAINT chat_messages_session_id_fkey ON chat_messages IS
'FK constraint pointing to chat_sessions.session_id (not id). Fixed in migration 017.';
