-- Migration: Add Row Level Security (RLS) to database tables
-- Purpose: Enforce user-scoped access for multi-tenant data; system tables for admin/backend only
-- Note: Backend uses service_role key which bypasses RLS; these policies protect direct Supabase access

-- ============================================================================
-- chat_sessions: Users can only access their own sessions
-- ============================================================================
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own chat sessions" ON chat_sessions;
CREATE POLICY "Users can view own chat sessions"
    ON chat_sessions FOR SELECT
    TO authenticated
    USING (user_id = auth.uid()::text);

DROP POLICY IF EXISTS "Users can insert own chat sessions" ON chat_sessions;
CREATE POLICY "Users can insert own chat sessions"
    ON chat_sessions FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid()::text);

DROP POLICY IF EXISTS "Users can update own chat sessions" ON chat_sessions;
CREATE POLICY "Users can update own chat sessions"
    ON chat_sessions FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid()::text);

DROP POLICY IF EXISTS "Users can delete own chat sessions" ON chat_sessions;
CREATE POLICY "Users can delete own chat sessions"
    ON chat_sessions FOR DELETE
    TO authenticated
    USING (user_id = auth.uid()::text);

-- ============================================================================
-- chat_messages: Users can access messages in their own sessions
-- ============================================================================
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view messages in own sessions" ON chat_messages;
CREATE POLICY "Users can view messages in own sessions"
    ON chat_messages FOR SELECT
    TO authenticated
    USING (
        session_id IN (SELECT session_id FROM chat_sessions WHERE user_id = auth.uid()::text)
    );

DROP POLICY IF EXISTS "Users can insert messages in own sessions" ON chat_messages;
CREATE POLICY "Users can insert messages in own sessions"
    ON chat_messages FOR INSERT
    TO authenticated
    WITH CHECK (
        session_id IN (SELECT session_id FROM chat_sessions WHERE user_id = auth.uid()::text)
    );

DROP POLICY IF EXISTS "Users can update messages in own sessions" ON chat_messages;
CREATE POLICY "Users can update messages in own sessions"
    ON chat_messages FOR UPDATE
    TO authenticated
    USING (
        session_id IN (SELECT session_id FROM chat_sessions WHERE user_id = auth.uid()::text)
    );

DROP POLICY IF EXISTS "Users can delete messages in own sessions" ON chat_messages;
CREATE POLICY "Users can delete messages in own sessions"
    ON chat_messages FOR DELETE
    TO authenticated
    USING (
        session_id IN (SELECT session_id FROM chat_sessions WHERE user_id = auth.uid()::text)
    );

-- ============================================================================
-- chat_attachments: Users can access attachments in their own sessions
-- ============================================================================
ALTER TABLE chat_attachments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view attachments in own sessions" ON chat_attachments;
CREATE POLICY "Users can view attachments in own sessions"
    ON chat_attachments FOR SELECT
    TO authenticated
    USING (
        session_id IN (SELECT session_id FROM chat_sessions WHERE user_id = auth.uid()::text)
    );

DROP POLICY IF EXISTS "Users can insert attachments in own sessions" ON chat_attachments;
CREATE POLICY "Users can insert attachments in own sessions"
    ON chat_attachments FOR INSERT
    TO authenticated
    WITH CHECK (
        session_id IN (SELECT session_id FROM chat_sessions WHERE user_id = auth.uid()::text)
    );

DROP POLICY IF EXISTS "Users can delete attachments in own sessions" ON chat_attachments;
CREATE POLICY "Users can delete attachments in own sessions"
    ON chat_attachments FOR DELETE
    TO authenticated
    USING (
        session_id IN (SELECT session_id FROM chat_sessions WHERE user_id = auth.uid()::text)
    );

-- ============================================================================
-- documents: Users can access documents in their projects or global (project_id null)
-- ============================================================================
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view documents in own projects or global" ON documents;
CREATE POLICY "Users can view documents in own projects or global"
    ON documents FOR SELECT
    TO authenticated
    USING (
        project_id IS NULL
        OR project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text)
    );

DROP POLICY IF EXISTS "Users can insert documents in own projects" ON documents;
CREATE POLICY "Users can insert documents in own projects"
    ON documents FOR INSERT
    TO authenticated
    WITH CHECK (
        project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text)
    );

DROP POLICY IF EXISTS "Users can update documents in own projects" ON documents;
CREATE POLICY "Users can update documents in own projects"
    ON documents FOR UPDATE
    TO authenticated
    USING (
        project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text)
    );

DROP POLICY IF EXISTS "Users can delete documents in own projects" ON documents;
CREATE POLICY "Users can delete documents in own projects"
    ON documents FOR DELETE
    TO authenticated
    USING (
        project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text)
    );

-- ============================================================================
-- knowledge_base: Users can access chunks for documents they can access
-- ============================================================================
ALTER TABLE knowledge_base ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view knowledge base for accessible documents" ON knowledge_base;
CREATE POLICY "Users can view knowledge base for accessible documents"
    ON knowledge_base FOR SELECT
    TO authenticated
    USING (
        document_id IN (
            SELECT id FROM documents
            WHERE project_id IS NULL
               OR project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()::text)
        )
    );

-- knowledge_base writes (ingestion) are done by backend via service_role; no direct user writes

-- ============================================================================
-- user_api_keys: Users can only access their own API keys
-- ============================================================================
ALTER TABLE user_api_keys ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own API keys" ON user_api_keys;
CREATE POLICY "Users can view own API keys"
    ON user_api_keys FOR SELECT
    TO authenticated
    USING (user_id = auth.uid()::text);

DROP POLICY IF EXISTS "Users can insert own API keys" ON user_api_keys;
CREATE POLICY "Users can insert own API keys"
    ON user_api_keys FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid()::text);

DROP POLICY IF EXISTS "Users can update own API keys" ON user_api_keys;
CREATE POLICY "Users can update own API keys"
    ON user_api_keys FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid()::text);

DROP POLICY IF EXISTS "Users can delete own API keys" ON user_api_keys;
CREATE POLICY "Users can delete own API keys"
    ON user_api_keys FOR DELETE
    TO authenticated
    USING (user_id = auth.uid()::text);

-- ============================================================================
-- user_settings: Users can only access their own settings
-- ============================================================================
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own settings" ON user_settings;
CREATE POLICY "Users can view own settings"
    ON user_settings FOR SELECT
    TO authenticated
    USING (user_id = auth.uid()::text);

DROP POLICY IF EXISTS "Users can insert own settings" ON user_settings;
CREATE POLICY "Users can insert own settings"
    ON user_settings FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid()::text);

DROP POLICY IF EXISTS "Users can update own settings" ON user_settings;
CREATE POLICY "Users can update own settings"
    ON user_settings FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid()::text);

DROP POLICY IF EXISTS "Users can delete own settings" ON user_settings;
CREATE POLICY "Users can delete own settings"
    ON user_settings FOR DELETE
    TO authenticated
    USING (user_id = auth.uid()::text);

-- ============================================================================
-- agent_configs: Admin/system table - authenticated can read for dashboard
-- Write access via backend (service_role) only
-- ============================================================================
ALTER TABLE agent_configs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated can read agent configs" ON agent_configs;
CREATE POLICY "Authenticated can read agent configs"
    ON agent_configs FOR SELECT
    TO authenticated
    USING (true);

-- ============================================================================
-- system_prompts: Admin/system table - authenticated can read for dashboard
-- Write access via backend (service_role) only
-- ============================================================================
ALTER TABLE system_prompts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated can read system prompts" ON system_prompts;
CREATE POLICY "Authenticated can read system prompts"
    ON system_prompts FOR SELECT
    TO authenticated
    USING (true);

-- ============================================================================
-- mcp_servers: Admin table - replace permissive policy with read-only for authenticated
-- Backend (service_role) bypasses RLS for full access
-- ============================================================================
-- Drop existing permissive policies if they exist (from migration 006)
DROP POLICY IF EXISTS "Service role has full access to mcp_servers" ON mcp_servers;

DROP POLICY IF EXISTS "Authenticated can read mcp servers" ON mcp_servers;
CREATE POLICY "Authenticated can read mcp servers"
    ON mcp_servers FOR SELECT
    TO authenticated
    USING (true);

-- ============================================================================
-- tools: Admin table - replace permissive policy with read-only for authenticated
-- ============================================================================
DROP POLICY IF EXISTS "Service role has full access to tools" ON tools;

DROP POLICY IF EXISTS "Authenticated can read tools" ON tools;
CREATE POLICY "Authenticated can read tools"
    ON tools FOR SELECT
    TO authenticated
    USING (true);

