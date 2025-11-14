-- Migration: Add Confidence Calculation Configuration
-- Created: 2025-01-08
-- Purpose: Add confidence_calculation config to agent_configs with three methods (formula/llm/hybrid)

-- =====================================================
-- Add confidence_calculation configuration to all existing agent configs
-- =====================================================

-- Comment documenting the confidence_calculation config structure
COMMENT ON COLUMN agent_configs.config IS 'Agent configuration JSON with thresholds, model settings, tools, confidence calculation, etc.

Confidence Calculation Structure:
{
  "confidence_calculation": {
    "method": "formula" | "llm" | "hybrid",
    "hybrid_settings": {
      "formula_weight": 0.60,  // Weight for formula score (0.0-1.0, must sum to 1.0 with llm_weight)
      "llm_weight": 0.40       // Weight for LLM score (0.0-1.0, must sum to 1.0 with formula_weight)
    },
    "llm_settings": {
      "provider": "openai" | "anthropic" | "azure",  // LLM provider for confidence evaluation
      "model": "gpt-4o-mini",   // Model ID (provider-specific)
      "temperature": 0.1,       // LLM temperature (0.0-2.0, lower = more deterministic)
      "max_tokens": 100,        // Max response tokens
      "timeout_ms": 2000        // Timeout in milliseconds (fallback to formula on timeout)
    },
    "formula_weights": {
      "similarity": 0.80,       // Weight for similarity score (0.0-1.0)
      "source_quality": 0.10,   // Weight for high-quality source count (0.0-1.0)
      "response_length": 0.10   // Weight for response completeness (0.0-1.0)
    }
  }
}

Methods:
- "formula": Algorithmic calculation (fast, no cost, based on retrieval metrics)
- "llm": Semantic evaluation using LLM (accurate, LLM cost per query)
- "hybrid": Combination of both (always calculates both and combines with weights)
';

-- =====================================================
-- Update default config (all environments)
-- =====================================================
UPDATE agent_configs
SET config = jsonb_set(
    config,
    '{confidence_calculation}',
    '{
        "method": "formula",
        "hybrid_settings": {
            "formula_weight": 0.60,
            "llm_weight": 0.40
        },
        "llm_settings": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.1,
            "max_tokens": 100,
            "timeout_ms": 2000
        },
        "formula_weights": {
            "similarity": 0.80,
            "source_quality": 0.10,
            "response_length": 0.10
        }
    }'::jsonb,
    true  -- create if not exists
)
WHERE name = 'default_agent_config' AND environment = 'all';

-- =====================================================
-- Update development config (lower thresholds for testing)
-- =====================================================
UPDATE agent_configs
SET config = jsonb_set(
    config,
    '{confidence_calculation}',
    '{
        "method": "formula",
        "hybrid_settings": {
            "formula_weight": 0.60,
            "llm_weight": 0.40
        },
        "llm_settings": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.1,
            "max_tokens": 150,
            "timeout_ms": 3000
        },
        "formula_weights": {
            "similarity": 0.75,
            "source_quality": 0.15,
            "response_length": 0.10
        }
    }'::jsonb,
    true
)
WHERE name = 'default_agent_config' AND environment = 'development';

-- =====================================================
-- Update production config (optimized for cost and reliability)
-- =====================================================
UPDATE agent_configs
SET config = jsonb_set(
    config,
    '{confidence_calculation}',
    '{
        "method": "formula",
        "hybrid_settings": {
            "formula_weight": 0.60,
            "llm_weight": 0.40
        },
        "llm_settings": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.1,
            "max_tokens": 100,
            "timeout_ms": 2000
        },
        "formula_weights": {
            "similarity": 0.80,
            "source_quality": 0.10,
            "response_length": 0.10
        }
    }'::jsonb,
    true
)
WHERE name = 'default_agent_config' AND environment = 'production';

-- =====================================================
-- Insert confidence_evaluation_prompt (for LLM and Hybrid modes)
-- =====================================================
-- This prompt is used by the LLM to evaluate confidence in the AI's response
INSERT INTO prompts (
    id,
    name,
    prompt_type,
    version,
    content,
    active,
    tags,
    notes,
    created_by,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    'confidence_evaluation_prompt',
    'confidence',
    1,
    'You are a confidence evaluator for an AI-powered Q&A system.

Your task is to evaluate the confidence in the AI''s response based on:
1. **Query Understanding**: How well does the response address the user''s query?
2. **Context Relevance**: How relevant is the retrieved context to the query?
3. **Response Quality**: How accurate, complete, and well-structured is the response?
4. **Knowledge Gaps**: Are there any obvious gaps or uncertainties in the response?

**Query**: {query}

**Retrieved Context** (first 1000 chars):
{context}

**AI Response** (first 500 chars):
{response}

**Instructions**:
- Provide a confidence score between 0.0 and 1.0
- 1.0 = Extremely confident (complete, accurate, directly addresses query)
- 0.8-0.9 = High confidence (accurate but minor gaps)
- 0.6-0.7 = Moderate confidence (mostly accurate but some uncertainties)
- 0.4-0.5 = Low confidence (significant gaps or uncertainties)
- 0.0-0.3 = Very low confidence (inaccurate or doesn''t address query)

Respond with ONLY a number between 0.0 and 1.0 (e.g., "0.85").',
    true,
    ARRAY['confidence', 'evaluation', 'llm_based'],
    'Default confidence evaluation prompt for LLM-based and hybrid confidence calculation',
    'system',
    NOW(),
    NOW()
) ON CONFLICT (name, prompt_type, version) DO NOTHING;

-- =====================================================
-- Add index for confidence evaluation prompt lookups
-- =====================================================
-- This index helps with fast lookups of active confidence prompts
CREATE INDEX IF NOT EXISTS idx_prompts_confidence_active
    ON prompts(name, active)
    WHERE name = 'confidence_evaluation_prompt' AND active = true;

-- =====================================================
-- Verification query (optional - for manual testing)
-- =====================================================
-- SELECT
--     name,
--     environment,
--     version,
--     config->'confidence_calculation' as confidence_config,
--     updated_at
-- FROM agent_configs
-- WHERE name = 'default_agent_config'
-- ORDER BY environment;

-- =====================================================
-- Comments for documentation
-- =====================================================
COMMENT ON INDEX idx_prompts_confidence_active IS 'Fast lookup for active confidence evaluation prompt';
