-- Migration: Add tables for tool and MCP configuration persistence
-- Created: 2025-01-31
-- Description: Stores tool configurations, MCP server connections, and usage tracking

-- ============================================================================
-- Tools Configuration Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Tool identification
    name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100) NOT NULL, -- math, finance, search, utility, etc.

    -- Tool metadata
    description TEXT,
    enabled BOOLEAN DEFAULT true,

    -- Configuration
    config JSONB DEFAULT '{}'::jsonb, -- Tool-specific configuration

    -- Usage tracking
    invocation_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_invoked_at TIMESTAMP WITH TIME ZONE,

    -- Performance metrics
    avg_execution_time_ms NUMERIC(10, 2),
    last_error TEXT,
    last_error_at TIMESTAMP WITH TIME ZONE,

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255),
    updated_by VARCHAR(255)
);

-- Indexes for tools table
CREATE INDEX idx_tools_category ON tools(category);
CREATE INDEX idx_tools_enabled ON tools(enabled);
CREATE INDEX idx_tools_name ON tools(name);

-- ============================================================================
-- MCP Servers Configuration Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS mcp_servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Server identification
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    enabled BOOLEAN DEFAULT true,

    -- Connection configuration
    transport VARCHAR(50) NOT NULL, -- 'stdio' or 'streamable_http'

    -- For stdio transport
    command VARCHAR(500),
    args JSONB DEFAULT '[]'::jsonb,

    -- For HTTP transport
    url VARCHAR(500),
    headers JSONB DEFAULT '{}'::jsonb,

    -- Additional configuration
    config JSONB DEFAULT '{}'::jsonb,

    -- Connection status
    last_connected_at TIMESTAMP WITH TIME ZONE,
    last_connection_error TEXT,
    last_connection_error_at TIMESTAMP WITH TIME ZONE,
    connection_attempts INTEGER DEFAULT 0,
    successful_connections INTEGER DEFAULT 0,

    -- Tool discovery
    tools_discovered INTEGER DEFAULT 0,
    last_tool_refresh_at TIMESTAMP WITH TIME ZONE,

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255),
    updated_by VARCHAR(255),

    -- Constraints
    CONSTRAINT mcp_servers_transport_check CHECK (transport IN ('stdio', 'streamable_http', 'sse', 'http')),
    CONSTRAINT transport_validation CHECK (
        (transport = 'stdio' AND command IS NOT NULL) OR
        (transport IN ('sse', 'http', 'streamable_http') AND url IS NOT NULL)
    )
);

-- Indexes for mcp_servers table
CREATE INDEX idx_mcp_servers_enabled ON mcp_servers(enabled);
CREATE INDEX idx_mcp_servers_transport ON mcp_servers(transport);
CREATE INDEX idx_mcp_servers_name ON mcp_servers(name);

-- ============================================================================
-- MCP Server Tools Junction Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS mcp_server_tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationships
    mcp_server_id UUID NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,

    -- Tool metadata (discovered from MCP server)
    tool_name VARCHAR(255) NOT NULL,
    tool_description TEXT,
    tool_schema JSONB, -- JSON schema of tool parameters

    -- Usage tracking
    invocation_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_invoked_at TIMESTAMP WITH TIME ZONE,

    -- Performance metrics
    avg_execution_time_ms NUMERIC(10, 2),
    last_error TEXT,
    last_error_at TIMESTAMP WITH TIME ZONE,

    -- Discovery tracking
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint: one tool per server
    CONSTRAINT unique_mcp_server_tool UNIQUE(mcp_server_id, tool_name)
);

-- Indexes for mcp_server_tools table
CREATE INDEX idx_mcp_server_tools_server ON mcp_server_tools(mcp_server_id);
CREATE INDEX idx_mcp_server_tools_name ON mcp_server_tools(tool_name);

-- ============================================================================
-- Tool Invocation Logs Table (for detailed tracking)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tool_invocation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Tool reference (nullable for MCP tools)
    tool_id UUID REFERENCES tools(id) ON DELETE SET NULL,
    mcp_server_tool_id UUID REFERENCES mcp_server_tools(id) ON DELETE SET NULL,

    -- Tool identification
    tool_name VARCHAR(255) NOT NULL,
    tool_type VARCHAR(50) NOT NULL, -- 'builtin' or 'mcp'

    -- Invocation details
    session_id VARCHAR(255),
    query TEXT,
    arguments JSONB,

    -- Execution
    success BOOLEAN NOT NULL,
    result TEXT,
    error TEXT,
    execution_time_ms INTEGER,

    -- Timestamp
    invoked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Agent context
    agent_config_id UUID REFERENCES agent_configs(id) ON DELETE SET NULL,

    -- Constraint: must reference either builtin or MCP tool
    CONSTRAINT tool_reference_check CHECK (
        (tool_id IS NOT NULL AND mcp_server_tool_id IS NULL) OR
        (tool_id IS NULL AND mcp_server_tool_id IS NOT NULL)
    )
);

-- Indexes for tool_invocation_logs table
CREATE INDEX idx_tool_invocation_logs_tool ON tool_invocation_logs(tool_id);
CREATE INDEX idx_tool_invocation_logs_mcp_tool ON tool_invocation_logs(mcp_server_tool_id);
CREATE INDEX idx_tool_invocation_logs_session ON tool_invocation_logs(session_id);
CREATE INDEX idx_tool_invocation_logs_invoked_at ON tool_invocation_logs(invoked_at DESC);
CREATE INDEX idx_tool_invocation_logs_success ON tool_invocation_logs(success);

-- ============================================================================
-- Updated At Triggers
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for tools table
CREATE TRIGGER update_tools_updated_at
    BEFORE UPDATE ON tools
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Triggers for mcp_servers table
CREATE TRIGGER update_mcp_servers_updated_at
    BEFORE UPDATE ON mcp_servers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE tools ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_servers ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_server_tools ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_invocation_logs ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (for backend API)
CREATE POLICY "Service role has full access to tools"
    ON tools
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role has full access to mcp_servers"
    ON mcp_servers
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role has full access to mcp_server_tools"
    ON mcp_server_tools
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role has full access to tool_invocation_logs"
    ON tool_invocation_logs
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- Seed Data: Built-in Tools
-- ============================================================================

INSERT INTO tools (name, category, description, enabled, config) VALUES
    ('calculator', 'math', 'Evaluate mathematical expressions safely with support for basic arithmetic and math functions', true, '{"safe_mode": true}'::jsonb),
    ('get_current_time', 'utility', 'Get the current time and date in specified timezone', true, '{"default_timezone": "UTC"}'::jsonb),
    ('currency_converter', 'finance', 'Convert currency amounts between different currencies', true, '{}'::jsonb)
ON CONFLICT (name) DO NOTHING;

-- Add web search tool if Tavily is configured
INSERT INTO tools (name, category, description, enabled, config) VALUES
    ('tavily_search', 'search', 'Search the web for real-time information using Tavily API', false, '{"max_results": 5, "search_depth": "advanced"}'::jsonb)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- Helper Views
-- ============================================================================

-- View: Tool usage statistics
CREATE OR REPLACE VIEW tool_usage_stats AS
SELECT
    t.id,
    t.name,
    t.category,
    t.enabled,
    t.invocation_count,
    t.success_count,
    t.failure_count,
    CASE
        WHEN t.invocation_count > 0 THEN
            ROUND((t.success_count::NUMERIC / t.invocation_count::NUMERIC) * 100, 2)
        ELSE 0
    END AS success_rate_percent,
    t.avg_execution_time_ms,
    t.last_invoked_at,
    t.last_error_at
FROM tools t
ORDER BY t.invocation_count DESC;

-- View: MCP server health
CREATE OR REPLACE VIEW mcp_server_health AS
SELECT
    ms.id,
    ms.name,
    ms.enabled,
    ms.transport,
    ms.tools_discovered,
    ms.last_connected_at,
    ms.connection_attempts,
    ms.successful_connections,
    CASE
        WHEN ms.connection_attempts > 0 THEN
            ROUND((ms.successful_connections::NUMERIC / ms.connection_attempts::NUMERIC) * 100, 2)
        ELSE 0
    END AS connection_success_rate_percent,
    ms.last_connection_error,
    ms.last_connection_error_at,
    ms.last_tool_refresh_at
FROM mcp_servers ms
ORDER BY ms.enabled DESC, ms.name;

-- View: Recent tool invocations
CREATE OR REPLACE VIEW recent_tool_invocations AS
SELECT
    til.id,
    til.tool_name,
    til.tool_type,
    til.success,
    til.execution_time_ms,
    til.invoked_at,
    til.session_id,
    til.error,
    COALESCE(t.category, 'mcp') AS category
FROM tool_invocation_logs til
LEFT JOIN tools t ON til.tool_id = t.id
ORDER BY til.invoked_at DESC
LIMIT 100;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE tools IS 'Configuration and tracking for built-in agent tools';
COMMENT ON TABLE mcp_servers IS 'Configuration for external MCP (Model Context Protocol) servers';
COMMENT ON TABLE mcp_server_tools IS 'Tools discovered from MCP servers';
COMMENT ON TABLE tool_invocation_logs IS 'Detailed logs of all tool invocations';

COMMENT ON COLUMN tools.config IS 'Tool-specific configuration as JSON (e.g., API keys, options)';
COMMENT ON COLUMN mcp_servers.transport IS 'Transport protocol: stdio for process communication, streamable_http for HTTP';
COMMENT ON COLUMN tool_invocation_logs.tool_type IS 'Type of tool: builtin for native tools, mcp for MCP server tools';
