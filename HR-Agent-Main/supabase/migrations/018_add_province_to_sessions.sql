-- Add province tracking to chat sessions and messages
-- This enables province-specific context throughout conversations

-- Add province column to chat_sessions
ALTER TABLE chat_sessions
ADD COLUMN IF NOT EXISTS province TEXT DEFAULT 'MB';

-- Add province column to chat_messages for message-level tracking
ALTER TABLE chat_messages
ADD COLUMN IF NOT EXISTS province TEXT;

-- Create index for province filtering on sessions
CREATE INDEX IF NOT EXISTS idx_chat_sessions_province ON chat_sessions(province);

-- Create index for province filtering on messages (for analytics)
CREATE INDEX IF NOT EXISTS idx_chat_messages_province ON chat_messages(province);

-- Add comment for documentation
COMMENT ON COLUMN chat_sessions.province IS 
'Canadian province context for the session: MB (Manitoba), ON (Ontario), SK (Saskatchewan), AB (Alberta), BC (British Columbia)';

COMMENT ON COLUMN chat_messages.province IS 
'Province context when the message was sent (allows tracking province changes within a session)';

-- Update existing sessions to have default province (Manitoba)
UPDATE chat_sessions
SET province = 'MB'
WHERE province IS NULL;

-- Add check constraint to ensure valid provinces
ALTER TABLE chat_sessions
ADD CONSTRAINT check_valid_province 
CHECK (province IN ('MB', 'ON', 'SK', 'AB', 'BC') OR province IS NULL);

ALTER TABLE chat_messages
ADD CONSTRAINT check_valid_province_message
CHECK (province IN ('MB', 'ON', 'SK', 'AB', 'BC') OR province IS NULL);

