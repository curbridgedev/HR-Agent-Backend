-- Migration: Add Query Analysis and Tool Invocation Prompts
-- Created: 2025-11-07
-- Purpose: Make all agent prompts database-manageable for dynamic configuration

-- =====================================================
-- Prompt 1: Query Analysis System Prompt
-- =====================================================
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
    'query_analysis_system',
    'system',
    1,
    'You are an expert query analyzer for a finance/payment AI system. Analyze queries precisely and return ONLY valid JSON - no other text, no markdown formatting, just raw JSON.',
    true,
    ARRAY['query_analysis', 'routing', 'classification'],
    'System identity prompt for query classification node - used to ensure JSON-only responses',
    'system',
    NOW(),
    NOW()
) ON CONFLICT (name, prompt_type, version) DO NOTHING;

-- =====================================================
-- Prompt 2: Query Analysis User Prompt (Template)
-- =====================================================
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
    'query_analysis_user',
    'analysis',
    1,
    'Analyze the following user query for a finance/payment AI assistant.

Query: {query}

Classify the query into one of these types:
1. "direct_question" - Specific question requiring factual answer
2. "calculation" - Requires mathematical calculation
3. "multi_part" - Complex query with multiple questions
4. "clarification_needed" - Query is unclear or ambiguous

Determine the best strategy:
- "standard_rag" - Query knowledge base for information
- "invoke_tools" - Use tools (calculator, web search, MCP)
- "direct_escalation" - Too complex, escalate to human

Also determine:
- Urgency: "high", "medium", or "low"
- Topics: List of relevant topics (payment, transaction, refund, etc.)

Return ONLY a valid JSON object with this structure:
{{"query_type": "...", "strategy": "...", "urgency": "...", "topics": [...], "reasoning": "..."}}',
    true,
    ARRAY['query_analysis', 'routing', 'classification', 'json_output'],
    'Template for query analysis - requires {query} variable',
    'system',
    NOW(),
    NOW()
) ON CONFLICT (name, prompt_type, version) DO NOTHING;

-- =====================================================
-- Prompt 3: Tool Invocation System Prompt
-- =====================================================
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
    'tool_invocation_system',
    'system',
    1,
    'You are a helpful assistant with access to tools. Analyze the user''s query and determine which tools to use, if any. Call the appropriate tools with the correct arguments.',
    true,
    ARRAY['tool_calling', 'function_calling'],
    'System identity for tool invocation node - guides tool selection',
    'system',
    NOW(),
    NOW()
) ON CONFLICT (name, prompt_type, version) DO NOTHING;

-- =====================================================
-- Add indexes for performance
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_prompts_name_type_active
    ON prompts(name, prompt_type, active)
    WHERE active = true;

-- Additional GIN index for tags (if not already created in 003)
CREATE INDEX IF NOT EXISTS idx_prompts_tags
    ON prompts USING gin(tags);

-- =====================================================
-- Comments for documentation
-- =====================================================
COMMENT ON INDEX idx_prompts_name_type_active IS 'Fast lookup for active prompts by name and type';
COMMENT ON COLUMN prompts.tags IS 'Used for categorization, A/B testing, and filtering';

-- =====================================================
-- Grant permissions (adjust as needed for your auth setup)
-- =====================================================
-- Note: These are basic permissions. Adjust based on your RLS policies.
GRANT SELECT ON prompts TO authenticated;
GRANT INSERT, UPDATE, DELETE ON prompts TO service_role;
