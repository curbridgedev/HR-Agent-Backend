-- Migration: 011_add_analytics_indexes.sql
-- Created: 2025-01-27
-- Purpose: Add indexes for analytics query performance optimization
-- Reference: BACKEND_ADMIN_REQUIREMENTS.md - Analytics Aggregation requirements

-- Index for session aggregation queries (date-based grouping)
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at
ON chat_sessions(created_at DESC);

-- Index for message aggregation queries (date-based grouping)
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at
ON chat_messages(created_at DESC);

-- Index for confidence score filtering (deflection rate calculations)
CREATE INDEX IF NOT EXISTS idx_chat_messages_confidence
ON chat_messages(confidence)
WHERE confidence IS NOT NULL;

-- Index for role filtering (user vs assistant messages)
CREATE INDEX IF NOT EXISTS idx_chat_messages_role
ON chat_messages(role);

-- Composite index for analytics queries (optimizes most common analytics patterns)
CREATE INDEX IF NOT EXISTS idx_chat_messages_analytics
ON chat_messages(role, created_at DESC, confidence)
WHERE role = 'assistant';

-- Index comments
COMMENT ON INDEX idx_chat_messages_analytics IS 'Optimizes analytics queries filtering by role and date with confidence scores';
COMMENT ON INDEX idx_chat_sessions_created_at IS 'Optimizes session count aggregation by date';
COMMENT ON INDEX idx_chat_messages_created_at IS 'Optimizes message aggregation and time-series queries';
COMMENT ON INDEX idx_chat_messages_confidence IS 'Optimizes deflection rate calculations (filters by confidence threshold)';
COMMENT ON INDEX idx_chat_messages_role IS 'Optimizes queries filtering by message role (user/assistant)';
