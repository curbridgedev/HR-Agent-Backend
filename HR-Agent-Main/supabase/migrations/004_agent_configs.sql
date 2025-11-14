-- Compaytence AI Agent - Agent Configuration Management
-- This migration adds database-driven agent configuration with versioning

-- Agent configs table - stores all agent configurations with versioning
CREATE TABLE IF NOT EXISTS agent_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identification
    name TEXT NOT NULL, -- e.g., 'default_config', 'high_confidence_config', 'experimental_config'
    version INTEGER NOT NULL DEFAULT 1,
    environment TEXT NOT NULL DEFAULT 'all', -- 'development', 'uat', 'production', 'all'

    -- Status
    active BOOLEAN DEFAULT false, -- Only one version can be active per name+environment

    -- Configuration (JSONB for flexibility)
    config JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Description and metadata
    description TEXT,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- Performance tracking (will be populated by LangFuse metrics)
    usage_count INTEGER DEFAULT 0,
    avg_response_time_ms FLOAT,
    avg_confidence FLOAT,
    escalation_rate FLOAT,
    success_rate FLOAT,

    -- Audit
    created_by TEXT, -- User who created this version
    notes TEXT, -- Change notes/description

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure unique name+environment+version combination
    UNIQUE(name, environment, version)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_agent_configs_name_env ON agent_configs(name, environment);
CREATE INDEX IF NOT EXISTS idx_agent_configs_active ON agent_configs(active) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_agent_configs_environment ON agent_configs(environment);
CREATE INDEX IF NOT EXISTS idx_agent_configs_created_at ON agent_configs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_configs_tags ON agent_configs USING gin(tags);

-- Add updated_at trigger
CREATE TRIGGER update_agent_configs_updated_at
    BEFORE UPDATE ON agent_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function: Get active config by name and environment
CREATE OR REPLACE FUNCTION get_active_config(
    config_name TEXT,
    config_environment TEXT DEFAULT 'all'
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    version INTEGER,
    environment TEXT,
    config JSONB,
    active BOOLEAN,
    description TEXT,
    tags TEXT[],
    usage_count INTEGER,
    avg_response_time_ms FLOAT,
    avg_confidence FLOAT,
    escalation_rate FLOAT,
    success_rate FLOAT,
    created_by TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        agent_configs.id,
        agent_configs.name,
        agent_configs.version,
        agent_configs.environment,
        agent_configs.config,
        agent_configs.active,
        agent_configs.description,
        agent_configs.tags,
        agent_configs.usage_count,
        agent_configs.avg_response_time_ms,
        agent_configs.avg_confidence,
        agent_configs.escalation_rate,
        agent_configs.success_rate,
        agent_configs.created_by,
        agent_configs.notes,
        agent_configs.created_at,
        agent_configs.updated_at
    FROM agent_configs
    WHERE
        agent_configs.name = config_name
        AND agent_configs.active = true
        AND (
            agent_configs.environment = config_environment
            OR agent_configs.environment = 'all'
        )
    ORDER BY
        -- Prefer environment-specific config over 'all'
        CASE WHEN agent_configs.environment = config_environment THEN 0 ELSE 1 END,
        agent_configs.created_at DESC
    LIMIT 1;
END;
$$;

-- Function: Activate a config version (deactivates others)
CREATE OR REPLACE FUNCTION activate_config_version(
    config_id_to_activate UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    target_name TEXT;
    target_environment TEXT;
BEGIN
    -- Get the name and environment of the config to activate
    SELECT name, environment INTO target_name, target_environment
    FROM agent_configs
    WHERE id = config_id_to_activate;

    IF target_name IS NULL THEN
        RAISE EXCEPTION 'Config with id % not found', config_id_to_activate;
    END IF;

    -- Deactivate all configs with the same name and environment
    UPDATE agent_configs
    SET active = false
    WHERE name = target_name AND environment = target_environment;

    -- Activate the target config
    UPDATE agent_configs
    SET active = true
    WHERE id = config_id_to_activate;
END;
$$;

-- Function: Create new config version
CREATE OR REPLACE FUNCTION create_config_version(
    config_name TEXT,
    config_environment TEXT,
    config_data JSONB,
    description_input TEXT DEFAULT NULL,
    tags_input TEXT[] DEFAULT ARRAY[]::TEXT[],
    created_by_input TEXT DEFAULT NULL,
    notes_input TEXT DEFAULT NULL,
    activate_immediately BOOLEAN DEFAULT false
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    new_version INTEGER;
    new_config_id UUID;
BEGIN
    -- Get the next version number for this name+environment
    SELECT COALESCE(MAX(version), 0) + 1 INTO new_version
    FROM agent_configs
    WHERE name = config_name AND environment = config_environment;

    -- Insert new config version
    INSERT INTO agent_configs (
        name,
        environment,
        version,
        config,
        description,
        tags,
        created_by,
        notes,
        active
    ) VALUES (
        config_name,
        config_environment,
        new_version,
        config_data,
        description_input,
        tags_input,
        created_by_input,
        notes_input,
        false -- Not active by default
    )
    RETURNING id INTO new_config_id;

    -- Activate immediately if requested
    IF activate_immediately THEN
        PERFORM activate_config_version(new_config_id);
    END IF;

    RETURN new_config_id;
END;
$$;

-- Insert default configurations

-- Default config for all environments
INSERT INTO agent_configs (name, environment, version, config, description, active, tags, notes) VALUES
(
    'default_agent_config',
    'all',
    1,
    '{
        "confidence_thresholds": {
            "escalation": 0.95,
            "high": 0.85,
            "medium": 0.70,
            "low": 0.50
        },
        "model_settings": {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        },
        "search_settings": {
            "similarity_threshold": 0.7,
            "max_results": 5,
            "use_hybrid_search": true
        },
        "tool_registry": {
            "enabled_tools": ["vector_search", "web_search"],
            "tool_configs": {
                "vector_search": {
                    "timeout_ms": 5000
                },
                "web_search": {
                    "timeout_ms": 10000,
                    "max_results": 3
                }
            }
        },
        "feature_flags": {
            "enable_pii_anonymization": true,
            "enable_semantic_cache": false,
            "enable_query_rewriting": false,
            "enable_confidence_calibration": true
        },
        "rate_limits": {
            "max_requests_per_minute": 60,
            "max_tokens_per_minute": 90000
        }
    }'::jsonb,
    'Default agent configuration for all environments',
    true,
    ARRAY['default', 'v1', 'production-ready'],
    'Initial default configuration with conservative settings'
);

-- Development-specific config (more verbose, lower thresholds for testing)
INSERT INTO agent_configs (name, environment, version, config, description, active, tags, notes) VALUES
(
    'default_agent_config',
    'development',
    1,
    '{
        "confidence_thresholds": {
            "escalation": 0.90,
            "high": 0.80,
            "medium": 0.65,
            "low": 0.45
        },
        "model_settings": {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 1500,
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        },
        "search_settings": {
            "similarity_threshold": 0.65,
            "max_results": 10,
            "use_hybrid_search": true
        },
        "tool_registry": {
            "enabled_tools": ["vector_search", "web_search"],
            "tool_configs": {
                "vector_search": {
                    "timeout_ms": 10000
                },
                "web_search": {
                    "timeout_ms": 15000,
                    "max_results": 5
                }
            }
        },
        "feature_flags": {
            "enable_pii_anonymization": true,
            "enable_semantic_cache": false,
            "enable_query_rewriting": true,
            "enable_confidence_calibration": true,
            "enable_debug_logging": true
        },
        "rate_limits": {
            "max_requests_per_minute": 120,
            "max_tokens_per_minute": 150000
        }
    }'::jsonb,
    'Development environment config with relaxed thresholds',
    true,
    ARRAY['development', 'v1', 'debug'],
    'Development config with more lenient settings for testing'
);

-- Production-specific config (strict thresholds, optimized for cost)
INSERT INTO agent_configs (name, environment, version, config, description, active, tags, notes) VALUES
(
    'default_agent_config',
    'production',
    1,
    '{
        "confidence_thresholds": {
            "escalation": 0.95,
            "high": 0.85,
            "medium": 0.70,
            "low": 0.50
        },
        "model_settings": {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 800,
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        },
        "search_settings": {
            "similarity_threshold": 0.75,
            "max_results": 5,
            "use_hybrid_search": true
        },
        "tool_registry": {
            "enabled_tools": ["vector_search"],
            "tool_configs": {
                "vector_search": {
                    "timeout_ms": 3000
                }
            }
        },
        "feature_flags": {
            "enable_pii_anonymization": true,
            "enable_semantic_cache": true,
            "enable_query_rewriting": false,
            "enable_confidence_calibration": true
        },
        "rate_limits": {
            "max_requests_per_minute": 60,
            "max_tokens_per_minute": 90000
        }
    }'::jsonb,
    'Production environment config with strict thresholds',
    true,
    ARRAY['production', 'v1', 'cost-optimized'],
    'Production config with strict thresholds and cost optimization'
);

COMMENT ON TABLE agent_configs IS 'Agent configurations with versioning and environment support';
COMMENT ON COLUMN agent_configs.name IS 'Unique identifier for the configuration';
COMMENT ON COLUMN agent_configs.environment IS 'Target environment: development, uat, production, or all';
COMMENT ON COLUMN agent_configs.version IS 'Version number, auto-incremented per name+environment';
COMMENT ON COLUMN agent_configs.active IS 'Only one version per name+environment can be active';
COMMENT ON COLUMN agent_configs.config IS 'Configuration JSON with thresholds, model settings, tools, etc.';
