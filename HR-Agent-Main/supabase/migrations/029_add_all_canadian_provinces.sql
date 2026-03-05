-- Add all Canadian provinces and "All" option for province filtering
-- Enables general questions across provinces and support for NB, NL, NS, PE, QC

-- Documents table: drop old constraint and add new one with all provinces
ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_province_check;
ALTER TABLE documents ADD CONSTRAINT documents_province_check
  CHECK (province IN ('AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'ON', 'PE', 'QC', 'SK', 'ALL'));

-- Chat sessions: drop old constraint and add new one
ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS check_valid_province;
ALTER TABLE chat_sessions ADD CONSTRAINT check_valid_province
  CHECK (province IN ('AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'ON', 'PE', 'QC', 'SK', 'ALL') OR province IS NULL);

-- Chat messages: drop old constraint and add new one
ALTER TABLE chat_messages DROP CONSTRAINT IF EXISTS check_valid_province_message;
ALTER TABLE chat_messages ADD CONSTRAINT check_valid_province_message
  CHECK (province IN ('AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'ON', 'PE', 'QC', 'SK', 'ALL') OR province IS NULL);

COMMENT ON COLUMN documents.province IS 'Canadian province code: AB, BC, MB, NB, NL, NS, ON, PE, QC, SK, or ALL for federal/multi-province documents';
