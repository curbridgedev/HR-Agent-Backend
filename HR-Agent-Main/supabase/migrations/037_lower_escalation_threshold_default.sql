-- Lower the default escalation threshold to 0.75 for better resolve rate.
-- Responses with confidence >= 0.75 will now count as "resolved" instead of escalated.
-- Updates configs that have the previous defaults (0.95 or 0.88).

UPDATE agent_configs
SET config = jsonb_set(
    COALESCE(config, '{}'::jsonb),
    '{confidence_thresholds,escalation}',
    '0.75'::jsonb,
    true
)
WHERE config->'confidence_thresholds'->>'escalation' IN ('0.95', '0.88');
