-- Migration: Create user_audit_logs table for tracking admin user management actions
-- Purpose: Audit trail for all user role changes, activation/deactivation actions
-- Phase: User Management API (Admin Dashboard)

-- ============================================================================
-- User Audit Logs Table
-- ============================================================================
-- Tracks all user management actions performed by admins
-- Records role changes, activation/deactivation with full context

CREATE TABLE user_audit_logs (
    -- Primary key
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Action type (role_change, deactivate, activate)
    action VARCHAR(50) NOT NULL CHECK (action IN ('role_change', 'deactivate', 'activate', 'bulk_role_change')),

    -- Who performed the action (references Supabase Auth users)
    performed_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE SET NULL,

    -- Who was affected by the action (references Supabase Auth users)
    affected_user UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Previous value (for role_change: old role, for deactivate/activate: old status)
    old_value TEXT,

    -- New value (for role_change: new role, for deactivate/activate: new status)
    new_value TEXT,

    -- Optional reason provided by admin
    reason TEXT,

    -- Request metadata for security tracking
    ip_address INET,
    user_agent TEXT,

    -- Created timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Index on affected_user for user history queries
CREATE INDEX idx_user_audit_logs_affected_user ON user_audit_logs(affected_user);

-- Index on performed_by for admin action tracking
CREATE INDEX idx_user_audit_logs_performed_by ON user_audit_logs(performed_by);

-- Index on timestamp for time-range queries
CREATE INDEX idx_user_audit_logs_timestamp ON user_audit_logs(timestamp DESC);

-- Index on action type for filtering by action
CREATE INDEX idx_user_audit_logs_action ON user_audit_logs(action);

-- Composite index for user + action queries
CREATE INDEX idx_user_audit_logs_affected_action ON user_audit_logs(affected_user, action);

-- ============================================================================
-- Row Level Security (RLS)
-- ============================================================================

-- Enable RLS
ALTER TABLE user_audit_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Only authenticated users can view audit logs
CREATE POLICY "Authenticated users can view audit logs"
    ON user_audit_logs
    FOR SELECT
    TO authenticated
    USING (true);

-- Policy: System can insert audit logs (for service layer)
CREATE POLICY "Service role can insert audit logs"
    ON user_audit_logs
    FOR INSERT
    TO service_role
    WITH CHECK (true);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE user_audit_logs IS 'Audit trail for all user management actions (role changes, activation/deactivation)';
COMMENT ON COLUMN user_audit_logs.log_id IS 'Unique identifier for audit log entry';
COMMENT ON COLUMN user_audit_logs.timestamp IS 'When the action was performed';
COMMENT ON COLUMN user_audit_logs.action IS 'Type of action: role_change, deactivate, activate, bulk_role_change';
COMMENT ON COLUMN user_audit_logs.performed_by IS 'Admin user who performed the action (auth.users reference)';
COMMENT ON COLUMN user_audit_logs.affected_user IS 'User who was affected by the action (auth.users reference)';
COMMENT ON COLUMN user_audit_logs.old_value IS 'Previous value before action (e.g., old role)';
COMMENT ON COLUMN user_audit_logs.new_value IS 'New value after action (e.g., new role)';
COMMENT ON COLUMN user_audit_logs.reason IS 'Optional reason provided by admin for the action';
COMMENT ON COLUMN user_audit_logs.ip_address IS 'IP address of the admin who performed the action';
COMMENT ON COLUMN user_audit_logs.user_agent IS 'User agent string of the admin who performed the action';
