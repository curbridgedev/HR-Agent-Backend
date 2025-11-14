-- Migration: Fix confidence evaluation prompt to force numeric-only output
-- Created: 2025-11-08
-- Description: Update confidence evaluation prompt with stronger instructions and examples

-- =====================================================
-- Update confidence_evaluation_prompt for stricter numeric output
-- =====================================================

-- Deactivate all existing versions
UPDATE prompts
SET active = false
WHERE name = 'confidence_evaluation_prompt' AND prompt_type = 'confidence';

-- Insert new version with stricter instructions
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
    2,  -- New version
    'You are a confidence evaluator. You must respond with ONLY a single decimal number between 0.0 and 1.0. NO explanations, NO text, NO reasoning - ONLY the number.

Evaluate the AI''s response quality based on:
- How well it addresses the query
- How relevant the retrieved context is
- Response completeness and accuracy
- Any knowledge gaps or uncertainties

Scoring guide:
1.0 = Perfect: Complete, accurate, directly answers query
0.8-0.9 = Good: Accurate with minor gaps
0.6-0.7 = Moderate: Mostly accurate, some uncertainties
0.4-0.5 = Low: Significant gaps or uncertainties
0.0-0.3 = Poor: Inaccurate or doesn''t address query

Query: {query}
Context (first 1000 chars): {context}
Response (first 500 chars): {response}

IMPORTANT: Respond with ONLY a number. Examples of correct responses:
0.85
0.72
0.95
0.43

Your response (number only):',
    true,
    ARRAY['confidence', 'evaluation', 'llm_based', 'v2', 'strict'],
    'Strict numeric-only confidence prompt to prevent LLM from generating verbose evaluations',
    'system',
    NOW(),
    NOW()
) ON CONFLICT (name, prompt_type, version) DO UPDATE
  SET content = EXCLUDED.content,
      active = EXCLUDED.active,
      tags = EXCLUDED.tags,
      notes = EXCLUDED.notes,
      updated_at = NOW();

-- =====================================================
-- Verification
-- =====================================================
-- Check active version
-- SELECT name, prompt_type, version, active, tags
-- FROM prompts
-- WHERE name = 'confidence_evaluation_prompt'
-- ORDER BY version DESC;
