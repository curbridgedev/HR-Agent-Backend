-- Standalone SQL to create user_api_keys and user_settings tables
-- Run this in Supabase Dashboard → SQL Editor if migration 030 was not applied

-- user_api_keys
CREATE TABLE IF NOT EXISTS user_api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  key_hash VARCHAR(128) NOT NULL UNIQUE,
  key_prefix VARCHAR(20) NOT NULL,
  name VARCHAR(255) DEFAULT 'Personal API Key',
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  enabled BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_user_api_keys_user_id ON user_api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_user_api_keys_key_hash ON user_api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_user_api_keys_enabled ON user_api_keys(enabled);

GRANT ALL ON user_api_keys TO service_role;
GRANT ALL ON user_api_keys TO authenticated;

-- user_settings
CREATE TABLE IF NOT EXISTS user_settings (
  user_id TEXT PRIMARY KEY,
  model_override VARCHAR(128),
  system_prompt_override TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

GRANT ALL ON user_settings TO service_role;
GRANT ALL ON user_settings TO authenticated;
