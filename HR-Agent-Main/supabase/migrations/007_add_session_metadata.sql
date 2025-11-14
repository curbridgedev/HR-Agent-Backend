-- Add session metadata fields for frontend sessions list
-- This enables the sidebar chat history feature

-- Add new columns to chat_sessions table
ALTER TABLE chat_sessions
ADD COLUMN IF NOT EXISTS title TEXT,
ADD COLUMN IF NOT EXISTS last_message TEXT,
ADD COLUMN IF NOT EXISTS message_count INTEGER DEFAULT 0;

-- Create index for faster sorting by updated_at (most recent first)
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions(updated_at DESC);

-- Create index for user_id filtering
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id_updated ON chat_sessions(user_id, updated_at DESC)
WHERE user_id IS NOT NULL;

-- Update existing sessions with initial data (if any exist)
UPDATE chat_sessions cs
SET
    title = COALESCE(
        LEFT((SELECT content FROM chat_messages WHERE session_id = cs.session_id AND role = 'user' ORDER BY created_at ASC LIMIT 1), 50) ||
        CASE
            WHEN LENGTH((SELECT content FROM chat_messages WHERE session_id = cs.session_id AND role = 'user' ORDER BY created_at ASC LIMIT 1)) > 50
            THEN '...'
            ELSE ''
        END,
        'Untitled Conversation'
    ),
    last_message = COALESCE(
        LEFT((SELECT content FROM chat_messages WHERE session_id = cs.session_id ORDER BY created_at DESC LIMIT 1), 100) ||
        CASE
            WHEN LENGTH((SELECT content FROM chat_messages WHERE session_id = cs.session_id ORDER BY created_at DESC LIMIT 1)) > 100
            THEN '...'
            ELSE ''
        END,
        ''
    ),
    message_count = (SELECT COUNT(*) FROM chat_messages WHERE session_id = cs.session_id)
WHERE title IS NULL;
