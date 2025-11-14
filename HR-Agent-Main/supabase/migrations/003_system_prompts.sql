-- Compaytence AI Agent - System Prompts Management
-- This migration adds database-driven prompt management with versioning

-- Prompts table - stores all system prompts with versioning
CREATE TABLE IF NOT EXISTS prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identification
    name TEXT NOT NULL, -- e.g., 'system_prompt', 'retrieval_prompt', 'generation_prompt'
    prompt_type TEXT NOT NULL, -- 'system', 'retrieval', 'generation', 'confidence', 'escalation'
    version INTEGER NOT NULL DEFAULT 1,

    -- Content
    content TEXT NOT NULL,

    -- Status
    active BOOLEAN DEFAULT false, -- Only one version can be active per name+type

    -- Categorization & Testing
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- Configuration & Metadata
    metadata JSONB DEFAULT '{}'::jsonb, -- temperature, max_tokens, model, etc.

    -- Performance tracking (will be populated by LangFuse metrics)
    usage_count INTEGER DEFAULT 0,
    avg_confidence FLOAT,
    escalation_rate FLOAT,

    -- Audit
    created_by TEXT, -- User who created this version
    notes TEXT, -- Change notes/description

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure unique name+type+version combination
    UNIQUE(name, prompt_type, version)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_prompts_name_type ON prompts(name, prompt_type);
CREATE INDEX IF NOT EXISTS idx_prompts_active ON prompts(active) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_prompts_type ON prompts(prompt_type);
CREATE INDEX IF NOT EXISTS idx_prompts_created_at ON prompts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_prompts_tags ON prompts USING gin(tags);

-- Add updated_at trigger
CREATE TRIGGER update_prompts_updated_at
    BEFORE UPDATE ON prompts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function: Get active prompt by name and type
CREATE OR REPLACE FUNCTION get_active_prompt(
    prompt_name TEXT,
    prompt_type_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    prompt_type TEXT,
    version INTEGER,
    content TEXT,
    metadata JSONB,
    tags TEXT[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        prompts.id,
        prompts.name,
        prompts.prompt_type,
        prompts.version,
        prompts.content,
        prompts.metadata,
        prompts.tags
    FROM prompts
    WHERE
        prompts.name = prompt_name
        AND prompts.active = true
        AND (prompt_type_filter IS NULL OR prompts.prompt_type = prompt_type_filter)
    LIMIT 1;
END;
$$;

-- Function: Activate a prompt version (deactivates others)
CREATE OR REPLACE FUNCTION activate_prompt_version(
    prompt_id_to_activate UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    target_name TEXT;
    target_type TEXT;
BEGIN
    -- Get the name and type of the prompt to activate
    SELECT name, prompt_type INTO target_name, target_type
    FROM prompts
    WHERE id = prompt_id_to_activate;

    IF target_name IS NULL THEN
        RAISE EXCEPTION 'Prompt with id % not found', prompt_id_to_activate;
    END IF;

    -- Deactivate all prompts with the same name and type
    UPDATE prompts
    SET active = false
    WHERE name = target_name AND prompt_type = target_type;

    -- Activate the target prompt
    UPDATE prompts
    SET active = true
    WHERE id = prompt_id_to_activate;
END;
$$;

-- Function: Create new prompt version
CREATE OR REPLACE FUNCTION create_prompt_version(
    prompt_name TEXT,
    prompt_type_input TEXT,
    content_input TEXT,
    tags_input TEXT[] DEFAULT ARRAY[]::TEXT[],
    metadata_input JSONB DEFAULT '{}'::jsonb,
    created_by_input TEXT DEFAULT NULL,
    notes_input TEXT DEFAULT NULL,
    activate_immediately BOOLEAN DEFAULT false
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    new_version INTEGER;
    new_prompt_id UUID;
BEGIN
    -- Get the next version number
    SELECT COALESCE(MAX(version), 0) + 1 INTO new_version
    FROM prompts
    WHERE name = prompt_name AND prompt_type = prompt_type_input;

    -- Insert new prompt version
    INSERT INTO prompts (
        name,
        prompt_type,
        version,
        content,
        tags,
        metadata,
        created_by,
        notes,
        active
    ) VALUES (
        prompt_name,
        prompt_type_input,
        new_version,
        content_input,
        tags_input,
        metadata_input,
        created_by_input,
        notes_input,
        false -- Not active by default
    )
    RETURNING id INTO new_prompt_id;

    -- Activate immediately if requested
    IF activate_immediately THEN
        PERFORM activate_prompt_version(new_prompt_id);
    END IF;

    RETURN new_prompt_id;
END;
$$;

-- Insert default prompts
INSERT INTO prompts (name, prompt_type, version, content, active, tags, notes) VALUES
(
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
    ARRAY['default', 'v1'],
    'Initial default system prompt'
),
(
    'retrieval_context_prompt',
    'retrieval',
    1,
    'Based on the following context from our knowledge base, please answer the user''s question.

Context:
{context}

User Question: {query}

Instructions:
1. Answer based ONLY on the provided context
2. Be specific and cite relevant details from the context
3. If the context doesn''t contain enough information, say so clearly
4. Maintain a professional and helpful tone',
    true,
    ARRAY['default', 'v1'],
    'Initial retrieval prompt for RAG'
),
(
    'confidence_evaluation_prompt',
    'confidence',
    1,
    'Evaluate your confidence in the response you just generated.

Consider:
1. How much relevant context was available?
2. How directly does the context answer the question?
3. Are there any gaps or ambiguities?
4. Would a human expert be able to provide a better answer?

Provide a confidence score between 0 and 1, where:
- 0.95-1.0: Highly confident, comprehensive context, direct answer
- 0.80-0.94: Confident, good context, minor gaps acceptable
- 0.50-0.79: Moderate confidence, some context, recommend escalation
- 0.00-0.49: Low confidence, insufficient context, escalate to human',
    true,
    ARRAY['default', 'v1'],
    'Initial confidence scoring prompt'
);

-- Grant permissions (adjust based on your auth setup)
-- For now, using service role which has full access
-- TODO: Add RLS policies when authentication is implemented

COMMENT ON TABLE prompts IS 'System prompts with versioning for LLM agent control';
COMMENT ON COLUMN prompts.name IS 'Unique identifier for the prompt (e.g., main_system_prompt)';
COMMENT ON COLUMN prompts.prompt_type IS 'Category of prompt: system, retrieval, generation, confidence, escalation';
COMMENT ON COLUMN prompts.version IS 'Version number, auto-incremented per name+type';
COMMENT ON COLUMN prompts.active IS 'Only one version per name+type can be active';
COMMENT ON COLUMN prompts.tags IS 'Tags for categorization and A/B testing';
COMMENT ON COLUMN prompts.metadata IS 'Additional config: model settings, parameters, etc.';
