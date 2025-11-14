-- Migration: 008_create_customers_table.sql
-- Created: 2025-01-27
-- Purpose: Create customers table for widget embedding organizations
-- Reference: BACKEND_ADMIN_REQUIREMENTS.md - Section: Database Schema Requirements

CREATE TABLE IF NOT EXISTS customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE,
  company VARCHAR(255),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  enabled BOOLEAN DEFAULT TRUE,
  metadata JSONB DEFAULT '{}'::jsonb,

  -- Email validation constraint
  CONSTRAINT customers_email_check CHECK (
    email IS NULL OR email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
  )
);

-- Indexes for performance
CREATE INDEX idx_customers_email ON customers(email) WHERE email IS NOT NULL;
CREATE INDEX idx_customers_enabled ON customers(enabled);
CREATE INDEX idx_customers_created_at ON customers(created_at DESC);

-- Table and column comments
COMMENT ON TABLE customers IS 'Customer organizations that embed the Compaytence widget';
COMMENT ON COLUMN customers.name IS 'Customer organization name (required)';
COMMENT ON COLUMN customers.email IS 'Optional email address for customer contact';
COMMENT ON COLUMN customers.company IS 'Optional company name';
COMMENT ON COLUMN customers.enabled IS 'Whether customer can use the widget (soft delete support)';
COMMENT ON COLUMN customers.metadata IS 'Flexible JSONB field for custom customer data';
