-- Migration: Reset all prompts to clean state
-- Created: 2025-11-08
-- Description: Delete all corrupted/duplicate prompts and create ONE clean active prompt per type
--              This fixes the issue where main_system_prompt v2 was corrupted with an evaluator prompt

-- =====================================================
-- Step 1: Clean slate - delete ALL existing prompts
-- =====================================================
DELETE FROM prompts;

-- =====================================================
-- Step 2: Insert clean prompts - ONE per type, all active
-- =====================================================

-- 1. SYSTEM PROMPT: Main assistant identity (CRITICAL)
INSERT INTO prompts (name, prompt_type, version, content, active, tags, notes, created_by) VALUES (
    'main_system_prompt',
    'system',
    1,
    'You are Compaytence AI, an intelligent assistant specialized in finance and payment operations. Your role is to provide accurate, helpful information about payment processing, transaction details, refund policies, and payment methods.

Key responsibilities:
- Answer questions about payment status, transaction details, and refunds
- Provide information about supported payment methods
- Explain payment policies and procedures
- Assist with payment-related troubleshooting

Guidelines:
- Be concise and professional
- Only answer questions you have context for
- If you lack sufficient context, acknowledge it clearly
- Cite your sources when providing information
- Never make up information or guess

Remember: Your responses must be based on the provided context. If the context doesn''t contain enough information to answer confidently, escalate to a human agent.',
    true,
    ARRAY['production', 'v1', 'clean'],
    'Clean main system prompt - defines AI assistant identity',
    'system'
);

-- 2. RETRIEVAL PROMPT: Format context for response generation
INSERT INTO prompts (name, prompt_type, version, content, active, tags, notes, created_by) VALUES (
    'retrieval_context_prompt',
    'retrieval',
    1,
    'Based on the following context from our knowledge base, please answer the user''s question.

Context:
{context}

User Question:
{query}

Please provide a comprehensive answer based on the context above. If the context doesn''t contain enough information, clearly state what is missing.',
    true,
    ARRAY['production', 'v1', 'clean'],
    'Clean retrieval prompt - formats context and query for LLM',
    'system'
);

-- 3. CONFIDENCE PROMPT: Evaluate response quality (returns 0.0-1.0 only)
INSERT INTO prompts (name, prompt_type, version, content, active, tags, notes, created_by) VALUES (
    'confidence_evaluation_prompt',
    'confidence',
    1,
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
    ARRAY['production', 'v1', 'clean', 'strict'],
    'Clean confidence prompt - forces numeric-only output',
    'system'
);

-- 4. ANALYSIS PROMPT: Query classification
INSERT INTO prompts (name, prompt_type, version, content, active, tags, notes, created_by) VALUES (
    'query_analysis_user',
    'analysis',
    1,
    'Analyze the following user query for a finance/payment AI assistant.

Query: {query}

Classify the query intent and extract key information. Return a JSON object with:
- intent: The primary user intent (e.g., "check_payment_status", "request_refund", "payment_method_info")
- category: Broad category (e.g., "payments", "refunds", "support")
- entities: Extracted entities (e.g., transaction IDs, amounts, dates)
- urgency: How urgent is this query? (low/medium/high)
- requires_context: Does this need RAG retrieval? (true/false)',
    true,
    ARRAY['production', 'v1', 'clean'],
    'Clean analysis prompt - classifies user queries',
    'system'
);

-- 5. QUERY ANALYSIS SYSTEM PROMPT: System identity for query analyzer
INSERT INTO prompts (name, prompt_type, version, content, active, tags, notes, created_by) VALUES (
    'query_analysis_system',
    'query_analysis_system',
    1,
    'You are an expert query analyzer for a finance/payment AI system. Analyze queries precisely and return ONLY valid JSON - no other text, no markdown formatting, just raw JSON.',
    true,
    ARRAY['production', 'v1', 'clean', 'query_analysis'],
    'System prompt for query classification and routing',
    'system'
);

-- 6. TOOL INVOCATION SYSTEM PROMPT: System identity for tool selection
INSERT INTO prompts (name, prompt_type, version, content, active, tags, notes, created_by) VALUES (
    'tool_invocation_system',
    'tool_invocation',
    1,
    'You are a helpful assistant with access to tools. Analyze the user''s query and determine which tools to use, if any. Call the appropriate tools with the correct arguments.',
    true,
    ARRAY['production', 'v1', 'clean', 'tool_calling'],
    'System prompt for tool selection and invocation',
    'system'
);

-- =====================================================
-- Step 3: Verification
-- =====================================================
DO $$
DECLARE
    v_prompt_count INTEGER;
    v_active_count INTEGER;
    v_types_count INTEGER;
BEGIN
    -- Count total prompts
    SELECT COUNT(*) INTO v_prompt_count FROM prompts;

    -- Count active prompts
    SELECT COUNT(*) INTO v_active_count FROM prompts WHERE active = true;

    -- Count distinct types
    SELECT COUNT(DISTINCT prompt_type) INTO v_types_count FROM prompts;

    -- Verify we have exactly 6 prompts
    IF v_prompt_count != 6 THEN
        RAISE EXCEPTION 'Expected 6 prompts, found %', v_prompt_count;
    END IF;

    -- Verify all 6 are active
    IF v_active_count != 6 THEN
        RAISE EXCEPTION 'Expected 6 active prompts, found %', v_active_count;
    END IF;

    -- Verify we have 6 distinct types (system, retrieval, confidence, analysis, query_analysis_system, tool_invocation)
    IF v_types_count != 6 THEN
        RAISE EXCEPTION 'Expected 6 prompt types, found %', v_types_count;
    END IF;

    -- Verify main_system_prompt is correct (not evaluator)
    IF EXISTS (
        SELECT 1 FROM prompts
        WHERE name = 'main_system_prompt'
          AND content LIKE '%impartial evaluator%'
    ) THEN
        RAISE EXCEPTION 'main_system_prompt still contains evaluator text!';
    END IF;

    -- Verify main_system_prompt is correct (is assistant)
    IF NOT EXISTS (
        SELECT 1 FROM prompts
        WHERE name = 'main_system_prompt'
          AND content LIKE '%Compaytence AI%'
    ) THEN
        RAISE EXCEPTION 'main_system_prompt does not contain correct assistant identity!';
    END IF;

    RAISE NOTICE 'Verification passed: 6 clean prompts, all active, main_system_prompt is correct';
END $$;

-- =====================================================
-- Comments for documentation
-- =====================================================
COMMENT ON TABLE prompts IS 'System prompts with versioning. CLEAN STATE: 6 active prompts with 6 distinct types (system, retrieval, confidence, analysis, query_analysis_system, tool_invocation)';
