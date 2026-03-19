-- Migration: 030_user_api_keys_and_settings.sql
-- Purpose: User API keys for programmatic access + user settings (model, system prompt overrides)
-- Run this in Supabase SQL Editor if migrations are not auto-applied.

-- ============================================================================
-- user_api_keys: Personal API keys for authenticated users
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,  -- Supabase auth.users.id (UUID as text)

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

-- Allow service_role (backend) full access
GRANT ALL ON user_api_keys TO service_role;
GRANT ALL ON user_api_keys TO authenticated;

COMMENT ON TABLE user_api_keys IS 'Personal API keys for users to access chat API programmatically';
COMMENT ON COLUMN user_api_keys.key_hash IS 'SHA-256 hash of API key (NEVER store raw key)';
COMMENT ON COLUMN user_api_keys.key_prefix IS 'First 20 chars for display (e.g., hr_abc123...)';

-- ============================================================================
-- user_settings: Per-user overrides for model and system prompt
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_settings (
  user_id TEXT PRIMARY KEY,  -- Supabase auth.users.id
  model_override VARCHAR(128),
  system_prompt_override TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Allow service_role (backend) full access
GRANT ALL ON user_settings TO service_role;
GRANT ALL ON user_settings TO authenticated;

COMMENT ON TABLE user_settings IS 'User preferences: model and system prompt overrides for chat';
COMMENT ON COLUMN user_settings.model_override IS 'Override default AI model for this user';
COMMENT ON COLUMN user_settings.system_prompt_override IS 'Override system prompt for this user (null = use default)';
