-- Migration: Fix main_system_prompt corruption
-- Created: 2025-11-08
-- Description: Deactivate the corrupted evaluator prompt (v2) and reactivate the correct assistant prompt (v1)
--              The v2 prompt was accidentally created with an evaluator prompt instead of the assistant prompt,
--              causing the AI to respond with evaluation text instead of answering user questions.

-- =====================================================
-- Fix: Deactivate corrupted main_system_prompt version 2
-- =====================================================
UPDATE prompts
SET active = false,
    notes = 'CORRUPTED: This version contained an evaluator prompt instead of assistant prompt. Deactivated 2025-11-08.',
    tags = ARRAY['corrupted', 'evaluator', 'deprecated']
WHERE name = 'main_system_prompt'
  AND prompt_type = 'system'
  AND version = 2;

-- =====================================================
-- Fix: Reactivate correct main_system_prompt version 1
-- =====================================================
UPDATE prompts
SET active = true,
    updated_at = NOW()
WHERE name = 'main_system_prompt'
  AND prompt_type = 'system'
  AND version = 1;

-- =====================================================
-- Add constraint to prevent multiple active versions
-- =====================================================
-- Note: This constraint ensures only one version per (name, prompt_type) can be active
-- The constraint already exists, but adding comment for clarity
COMMENT ON CONSTRAINT prompts_name_type_active_unique ON prompts IS
    'Ensures only one version per (name, prompt_type) can be active. Prevents accidental activation of wrong prompts.';

-- =====================================================
-- Verification
-- =====================================================
DO $$
DECLARE
    v_active_count INTEGER;
    v_active_version INTEGER;
    v_active_content TEXT;
BEGIN
    -- Check active version
    SELECT version, content, COUNT(*) OVER ()
    INTO v_active_version, v_active_content, v_active_count
    FROM prompts
    WHERE name = 'main_system_prompt'
      AND prompt_type = 'system'
      AND active = true;

    -- Verify exactly one active version
    IF v_active_count != 1 THEN
        RAISE EXCEPTION 'Expected exactly 1 active main_system_prompt, found %', v_active_count;
    END IF;

    -- Verify it's version 1
    IF v_active_version != 1 THEN
        RAISE EXCEPTION 'Expected version 1 to be active, found version %', v_active_version;
    END IF;

    -- Verify it starts with correct text
    IF v_active_content NOT LIKE 'You are Compaytence AI%' THEN
        RAISE EXCEPTION 'Active prompt has unexpected content: %', LEFT(v_active_content, 50);
    END IF;

    RAISE NOTICE 'Verification passed: main_system_prompt version 1 is active and correct';
END $$;
