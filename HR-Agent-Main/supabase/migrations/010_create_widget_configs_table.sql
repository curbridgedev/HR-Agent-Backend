-- Migration: 010_create_widget_configs_table.sql
-- Created: 2025-01-27
-- Purpose: Create widget_configs table for widget appearance and behavior customization
-- Reference: BACKEND_ADMIN_REQUIREMENTS.md - Section: Database Schema Requirements

CREATE TABLE IF NOT EXISTS widget_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID NOT NULL UNIQUE REFERENCES customers(id) ON DELETE CASCADE,

  -- Position & Behavior
  position VARCHAR(20) DEFAULT 'bottom-right' CHECK (
    position IN ('bottom-right', 'bottom-left', 'top-right', 'top-left')
  ),
  auto_open BOOLEAN DEFAULT FALSE,
  auto_open_delay INTEGER DEFAULT 0 CHECK (auto_open_delay >= 0), -- Seconds before auto-open

  -- Appearance (JSONB for flexibility)
  theme_config JSONB DEFAULT '{
    "primaryColor": "#0066cc",
    "fontFamily": "system-ui",
    "borderRadius": "12px",
    "chatBubbleColor": "#f3f4f6"
  }'::jsonb NOT NULL,

  -- Content
  greeting_message TEXT DEFAULT 'Hi! How can I help you today?',
  placeholder_text TEXT DEFAULT 'Type your message...',

  -- Branding
  logo_url TEXT,               -- URL to customer's logo
  company_name VARCHAR(255),

  -- Advanced Settings
  allowed_domains TEXT[],      -- CORS whitelist (NULL = allow all origins for dev)
  max_history_messages INTEGER DEFAULT 50 CHECK (max_history_messages > 0),
  show_confidence_scores BOOLEAN DEFAULT TRUE,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for customer_id lookup
CREATE INDEX idx_widget_configs_customer_id ON widget_configs(customer_id);

-- Table and column comments
COMMENT ON TABLE widget_configs IS 'Widget appearance and behavior configuration per customer (1:1 with customers)';
COMMENT ON COLUMN widget_configs.customer_id IS 'Foreign key to customers table (UNIQUE constraint = one config per customer)';
COMMENT ON COLUMN widget_configs.position IS 'Widget position on page: bottom-right, bottom-left, top-right, top-left';
COMMENT ON COLUMN widget_configs.auto_open IS 'Whether widget should automatically open on page load';
COMMENT ON COLUMN widget_configs.auto_open_delay IS 'Seconds to wait before auto-opening widget (if auto_open=true)';
COMMENT ON COLUMN widget_configs.theme_config IS 'JSONB theme configuration with primaryColor, fontFamily, borderRadius, etc.';
COMMENT ON COLUMN widget_configs.greeting_message IS 'Initial greeting message shown to users';
COMMENT ON COLUMN widget_configs.placeholder_text IS 'Placeholder text for message input';
COMMENT ON COLUMN widget_configs.logo_url IS 'URL to customer logo displayed in widget';
COMMENT ON COLUMN widget_configs.company_name IS 'Customer company name displayed in widget header';
COMMENT ON COLUMN widget_configs.allowed_domains IS 'CORS whitelist array (NULL = allow all origins, useful for development)';
COMMENT ON COLUMN widget_configs.max_history_messages IS 'Maximum number of chat messages to display in history';
COMMENT ON COLUMN widget_configs.show_confidence_scores IS 'Whether to show AI confidence scores to end users';
