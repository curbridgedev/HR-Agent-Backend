-- Migration: 009_create_customer_api_keys_table.sql
-- Created: 2025-01-27
-- Purpose: Create customer_api_keys table for widget authentication
-- Reference: BACKEND_ADMIN_REQUIREMENTS.md - Section: Database Schema Requirements
-- Security: Stores SHA-256 hash of API keys, NEVER stores raw keys

CREATE TABLE IF NOT EXISTS customer_api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,

  -- Security: Hash and prefix storage
  key_hash VARCHAR(128) NOT NULL UNIQUE, -- SHA-256 hash of full API key
  key_prefix VARCHAR(16) NOT NULL,       -- First 16 chars for display (e.g., "cp_live_abc12345")

  -- Metadata
  name VARCHAR(255),                     -- User-defined key description
  last_used_at TIMESTAMPTZ,              -- Track last usage for security auditing
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ,                -- NULL = never expires
  enabled BOOLEAN DEFAULT TRUE,

  -- Rate limiting per API key
  rate_limit_per_minute INTEGER DEFAULT 60 CHECK (rate_limit_per_minute > 0),
  rate_limit_per_day INTEGER DEFAULT 10000 CHECK (rate_limit_per_day > 0)
);

-- Indexes for performance
CREATE INDEX idx_api_keys_customer_id ON customer_api_keys(customer_id);
CREATE INDEX idx_api_keys_key_hash ON customer_api_keys(key_hash);  -- Fast auth lookup
CREATE INDEX idx_api_keys_enabled ON customer_api_keys(enabled);
CREATE INDEX idx_api_keys_last_used ON customer_api_keys(last_used_at DESC);

-- Table and column comments
COMMENT ON TABLE customer_api_keys IS 'API keys for authenticating widget requests (stores SHA-256 hashes only)';
COMMENT ON COLUMN customer_api_keys.key_hash IS 'SHA-256 hash of API key (NEVER store raw key for security)';
COMMENT ON COLUMN customer_api_keys.key_prefix IS 'First 16 chars of API key for display purposes (e.g., "cp_live_abc12345")';
COMMENT ON COLUMN customer_api_keys.name IS 'User-defined description for the API key (e.g., "Production Widget")';
COMMENT ON COLUMN customer_api_keys.last_used_at IS 'Last time this API key was used (for security auditing)';
COMMENT ON COLUMN customer_api_keys.expires_at IS 'Expiration timestamp (NULL = never expires)';
COMMENT ON COLUMN customer_api_keys.rate_limit_per_minute IS 'Rate limit for this API key (requests per minute)';
COMMENT ON COLUMN customer_api_keys.rate_limit_per_day IS 'Rate limit for this API key (requests per day)';
