-- Add LLM Provider Support to Agent Configurations
-- This migration adds provider field to model_settings for multi-provider LLM support

-- Add provider field to all existing configs (default to "openai")
UPDATE agent_configs
SET config = jsonb_set(
    config,
    '{model_settings, provider}',
    '"openai"'::jsonb
)
WHERE config -> 'model_settings' ->> 'provider' IS NULL;

-- Add comment explaining the provider field
COMMENT ON TABLE agent_configs IS 'Agent configurations with versioning, environment support, and multi-provider LLM support';

-- Log the migration
DO $$
DECLARE
    updated_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO updated_count
    FROM agent_configs
    WHERE config -> 'model_settings' ->> 'provider' = 'openai';

    RAISE NOTICE 'Migration 005: Added provider field to % configs', updated_count;
END $$;
