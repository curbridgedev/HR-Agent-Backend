# Complete Prompt Usage in Compaytence AI Agent

Comprehensive documentation of all prompts used in the Compaytence AI Agent system.

## 📊 Summary

**Total Prompts: 5**
- **Database-managed:** 3 prompts (2 actively used, 1 defined but unused)
- **Hardcoded in code:** 2 prompts

---

## 1️⃣ Database-Managed Prompts

### Location: `supabase/migrations/003_system_prompts.sql`
### Service: `app/services/prompts.py`

### **Prompt 1: `main_system_prompt`** ✅ ACTIVE
- **Type:** `system`
- **Version:** 1
- **Usage Location:** `app/agents/nodes.py:411-430`
- **Used in:** `generate_response_node()` function
- **Purpose:** Main system identity and guidelines for the AI assistant

**Loading Logic:**
```python
system_prompt_obj = await get_active_prompt(
    name="main_system_prompt",
    prompt_type="system",
)

if system_prompt_obj:
    system_prompt = system_prompt_obj.content  # Load from DB
    logger.info(f"Using database system prompt: v{system_prompt_obj.version}")
else:
    # Fallback to hardcoded default
    system_prompt = """You are a finance and payment expert assistant..."""
```

**Content (v1):**
```
You are Compaytence AI, an intelligent assistant specialized in finance and payment operations. Your role is to provide accurate, helpful information about payment processing, transaction details, refund policies, and payment methods.

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

Remember: Your responses must be based on the provided context. If the context doesn't contain enough information to answer confidently, escalate to a human agent.
```

---

### **Prompt 2: `retrieval_context_prompt`** ✅ ACTIVE
- **Type:** `retrieval`
- **Version:** 1
- **Usage Location:** `app/agents/nodes.py:433-454`
- **Used in:** `generate_response_node()` function for RAG responses
- **Purpose:** Template for formatting retrieved context with user query

**Loading Logic:**
```python
retrieval_prompt_obj = await get_active_prompt(
    name="retrieval_context_prompt",
    prompt_type="retrieval",
)

if retrieval_prompt_obj:
    user_prompt = retrieval_prompt_obj.content.format(
        context=state['context_text'],
        query=state['query']
    )
else:
    # Fallback
    user_prompt = f"""Context information: {state['context_text']}
User question: {state['query']}"""
```

**Content (v1):**
```
Based on the following context from our knowledge base, please answer the user's question.

Context:
{context}

User Question: {query}

Instructions:
1. Answer based ONLY on the provided context
2. Be specific and cite relevant details from the context
3. If the context doesn't contain enough information, say so clearly
4. Maintain a professional and helpful tone
```

**Template Variables:**
- `{context}` - Retrieved documents from vector search
- `{query}` - User's original question

---

### **Prompt 3: `confidence_evaluation_prompt`** ⚠️ DEFINED BUT NOT USED
- **Type:** `confidence`
- **Version:** 1
- **Storage:** Database only
- **Usage:** **NONE** - Confidence is calculated algorithmically instead
- **Location in DB:** `supabase/migrations/003_system_prompts.sql:224-244`

**Content (v1):**
```
Evaluate your confidence in the response you just generated.

Consider:
1. How much relevant context was available?
2. How directly does the context answer the question?
3. Are there any gaps or ambiguities?
4. Would a human expert be able to provide a better answer?

Provide a confidence score between 0 and 1, where:
- 0.95-1.0: Highly confident, comprehensive context, direct answer
- 0.80-0.94: Confident, good context, minor gaps acceptable
- 0.50-0.79: Moderate confidence, some context, recommend escalation
- 0.00-0.49: Low confidence, insufficient context, escalate to human
```

**Why Not Used:**
- Confidence is calculated using algorithmic scoring in `calculate_confidence_node()` at `app/agents/nodes.py:547-647`
- Algorithm uses semantic similarity, response quality, retrieval scores, and response completeness
- This is more deterministic and cost-effective than LLM-based evaluation

---

## 2️⃣ Hardcoded Prompts

### **Prompt 4: Query Analysis Prompt** (Hardcoded)
- **Location:** `app/agents/nodes.py:167-168`
- **Used in:** `analyze_query_node()` function
- **Purpose:** Analyze user intent and determine routing strategy

**Code:**
```python
analysis_prompt = f"""Analyze the following user query for a finance/payment AI assistant.

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
{{"query_type": "...", "strategy": "...", "urgency": "...", "topics": [...], "reasoning": "..."}}"""

response = await chat_model.ainvoke([
    SystemMessage(content="You are an expert query analyzer for a finance/payment AI system. Analyze queries precisely and return ONLY valid JSON - no other text, no markdown formatting, just raw JSON."),
    HumanMessage(content=analysis_prompt),
])
```

**Output Structure:**
```json
{
  "query_type": "direct_question | calculation | multi_part | clarification_needed",
  "strategy": "standard_rag | invoke_tools | direct_escalation",
  "urgency": "high | medium | low",
  "topics": ["payment", "transaction", "refund", ...],
  "reasoning": "Why this classification was chosen"
}
```

---

### **Prompt 5: Tool Invocation Prompt** (Hardcoded)
- **Location:** `app/agents/nodes.py:758-765`
- **Used in:** `invoke_tools_node()` function
- **Purpose:** Guide LLM to select and call appropriate tools

**Code:**
```python
system_prompt = """You are a helpful assistant with access to tools.
Analyze the user's query and determine which tools to use, if any.
Call the appropriate tools with the correct arguments."""

response = await model_with_tools.ainvoke([
    SystemMessage(content=system_prompt),
    HumanMessage(content=query)
])
```

**Available Tools (bound to model):**
- Calculator tool
- Web search tool
- MCP tools (dynamically loaded from enabled servers)

---

## 📋 Prompt Management System

### Database Schema
```sql
CREATE TABLE prompts (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,                    -- 'main_system_prompt', etc.
    prompt_type TEXT NOT NULL,             -- 'system', 'retrieval', 'confidence'
    version INTEGER NOT NULL DEFAULT 1,    -- Auto-incremented
    content TEXT NOT NULL,
    active BOOLEAN DEFAULT false,          -- Only one active per name+type
    tags TEXT[],                           -- For A/B testing
    metadata JSONB,                        -- Model settings, parameters
    usage_count INTEGER DEFAULT 0,
    avg_confidence FLOAT,
    escalation_rate FLOAT,
    created_by TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    UNIQUE(name, prompt_type, version)
);
```

### Service Functions
**File:** `app/services/prompts.py`

- `get_active_prompt(name, prompt_type)` - Load active prompt version
- `create_prompt_version()` - Create new version (auto-increments)
- `activate_prompt(prompt_id)` - Activate specific version
- `get_prompt_history()` - Get all versions
- `increment_prompt_usage()` - Track usage statistics

---

## 🔄 Prompt Flow in Agent Execution

```
1. User Query
   ↓
2. analyze_query_node()
   → Uses: Hardcoded Query Analysis Prompt (#4)
   → Determines: routing strategy
   ↓
3. Route to:
   a) invoke_tools_node()
      → Uses: Hardcoded Tool Invocation Prompt (#5)
   b) retrieve_context_node()
      → Retrieves documents from vector store
   c) Direct to response generation
   ↓
4. generate_response_node()
   → Uses: main_system_prompt (DB) (#1)
   → Uses: retrieval_context_prompt (DB) (#2)
   → Generates response
   ↓
5. calculate_confidence_node()
   → Uses: Algorithmic scoring (NOT confidence_evaluation_prompt)
   ↓
6. decision_node()
   → Checks: confidence >= 0.95 threshold
   ↓
7. format_output_node()
   → Returns response or escalates
```

---

## 📊 Prompt Type Definitions

**Supported Types (from migration):**
- `system` ✅ - Main system identity and guidelines (USED)
- `retrieval` ✅ - RAG context formatting (USED)
- `generation` ⚠️ - Response generation templates (NOT DEFINED)
- `confidence` ⚠️ - Confidence evaluation (DEFINED, NOT USED)
- `escalation` ⚠️ - Escalation messaging (NOT DEFINED)

---

## 🎯 Recommendations

### ✅ Working Well
1. Database-managed prompts for easy versioning
2. Fallback to hardcoded defaults for reliability
3. Usage tracking for prompt analytics

### ⚠️ Potential Improvements

#### 1. Migrate Hardcoded Prompts to Database
Currently hardcoded prompts should be moved to database for better management:

**Query Analysis Prompt:**
```sql
INSERT INTO prompts (name, prompt_type, version, content, active, tags, notes) VALUES
(
    'query_analysis_prompt',
    'system',
    1,
    'You are an expert query analyzer for a finance/payment AI system. Analyze queries precisely and return ONLY valid JSON - no other text, no markdown formatting, just raw JSON.',
    true,
    ARRAY['query_analysis', 'routing'],
    'System prompt for query classification and routing'
);
```

**Tool Invocation Prompt:**
```sql
INSERT INTO prompts (name, prompt_type, version, content, active, tags, notes) VALUES
(
    'tool_invocation_prompt',
    'system',
    1,
    'You are a helpful assistant with access to tools. Analyze the user''s query and determine which tools to use, if any. Call the appropriate tools with the correct arguments.',
    true,
    ARRAY['tool_calling', 'function_calling'],
    'System prompt for tool selection and invocation'
);
```

#### 2. Define Missing Prompt Types

**Generation Prompt (for style variations):**
```sql
INSERT INTO prompts (name, prompt_type, version, content, active, tags, notes) VALUES
(
    'response_generation_style',
    'generation',
    1,
    'Generate responses that are:
- Professional and clear
- Concise but comprehensive
- Structured with bullet points when appropriate
- Include specific numbers and details from context
- End with an offer to help further if needed',
    true,
    ARRAY['style', 'tone'],
    'Style guidelines for response generation'
);
```

**Escalation Prompt (for handoff messaging):**
```sql
INSERT INTO prompts (name, prompt_type, version, content, active, tags, notes) VALUES
(
    'escalation_message',
    'escalation',
    1,
    'I need to connect you with a human specialist to better assist you with this request.

Based on my analysis:
- Query complexity: {complexity}
- Confidence score: {confidence}
- Reason for escalation: {reason}

A team member will be with you shortly. They will have full context of our conversation.',
    true,
    ARRAY['escalation', 'handoff'],
    'Template for human escalation messaging'
);
```

#### 3. Consider LLM-Based Confidence Evaluation

While algorithmic confidence scoring works well, consider using the `confidence_evaluation_prompt` as a **fallback or validation mechanism**:

```python
# In calculate_confidence_node()
algorithmic_score = calculate_algorithmic_confidence(...)

# If score is borderline (0.85-0.95), validate with LLM
if 0.85 <= algorithmic_score <= 0.95:
    llm_evaluation = await evaluate_with_llm(confidence_evaluation_prompt)
    final_score = (algorithmic_score + llm_evaluation) / 2
else:
    final_score = algorithmic_score
```

---

## 📍 File Reference Map

| Prompt | File Location | Line Numbers |
|--------|---------------|--------------|
| **main_system_prompt** (DB) | `app/agents/nodes.py` | 411-430 |
| **retrieval_context_prompt** (DB) | `app/agents/nodes.py` | 433-454 |
| **confidence_evaluation_prompt** (DB) | `supabase/migrations/003_system_prompts.sql` | 224-244 |
| **Query Analysis** (hardcoded) | `app/agents/nodes.py` | 71, 167-168 |
| **Tool Invocation** (hardcoded) | `app/agents/nodes.py` | 758-765 |
| **Prompt Service** | `app/services/prompts.py` | 1-412 |
| **Prompt Models** | `app/models/prompts.py` | - |
| **Database Migration** | `supabase/migrations/003_system_prompts.sql` | 1-257 |

---

## 🔧 How to Update Prompts

### Via API (Recommended)

**Create New Version:**
```bash
POST /api/v1/prompts/
{
  "name": "main_system_prompt",
  "prompt_type": "system",
  "content": "Updated prompt content...",
  "activate_immediately": true,
  "notes": "Improved clarity and added examples",
  "created_by": "admin@example.com"
}
```

**Activate Existing Version:**
```bash
POST /api/v1/prompts/{prompt_id}/activate
```

**View History:**
```bash
GET /api/v1/prompts/history?name=main_system_prompt&prompt_type=system
```

### Via Database

**Create New Version:**
```sql
SELECT create_prompt_version(
    prompt_name := 'main_system_prompt',
    prompt_type_input := 'system',
    content_input := 'New prompt content...',
    activate_immediately := true,
    notes_input := 'Description of changes',
    created_by_input := 'admin@example.com'
);
```

**Activate Version:**
```sql
SELECT activate_prompt_version(prompt_id_to_activate := 'uuid-here');
```

---

## 📈 Usage Analytics

The system automatically tracks:
- **usage_count**: How many times each prompt version is used
- **avg_confidence**: Average confidence score of responses using this prompt
- **escalation_rate**: Percentage of conversations that escalated to humans

**View Performance:**
```sql
SELECT
    name,
    version,
    usage_count,
    ROUND(avg_confidence::numeric, 3) as avg_confidence,
    ROUND((escalation_rate * 100)::numeric, 2) || '%' as escalation_rate
FROM prompts
WHERE active = true
ORDER BY name, version DESC;
```

**Compare Versions:**
```sql
SELECT
    version,
    usage_count,
    avg_confidence,
    escalation_rate,
    created_at
FROM prompts
WHERE name = 'main_system_prompt' AND prompt_type = 'system'
ORDER BY version DESC;
```

---

## 🔐 Security Considerations

1. **Prompt Injection Protection:**
   - All prompts use structured templates
   - User input is always passed as separate message, never interpolated into system prompts
   - Context is clearly separated from instructions

2. **Access Control:**
   - Only admin users can create/modify prompts (TODO: implement RLS policies)
   - Prompt changes are audited with `created_by` and timestamps
   - Version history is immutable

3. **Validation:**
   - Template variables are validated before formatting
   - Prompt content is sanitized for special characters
   - Length limits enforced (max 32KB per prompt)

---

## 🧪 Testing Prompts

### A/B Testing Setup

**Create Two Versions:**
```sql
-- Version A
INSERT INTO prompts (...) VALUES (..., tags := ARRAY['test_group_a']);

-- Version B
INSERT INTO prompts (...) VALUES (..., tags := ARRAY['test_group_b']);
```

**Split Traffic:**
```python
# In agent code
import random

if random.random() < 0.5:
    prompt = await get_active_prompt("test_prompt", tags=["test_group_a"])
else:
    prompt = await get_active_prompt("test_prompt", tags=["test_group_b"])
```

**Compare Results:**
```sql
SELECT
    tags[1] as test_group,
    COUNT(*) as samples,
    AVG(avg_confidence) as avg_confidence,
    AVG(escalation_rate) as avg_escalation_rate
FROM prompts
WHERE name = 'test_prompt'
GROUP BY tags[1];
```

---

## 📚 Related Documentation

- **Technical Spec:** `Compaytence Technical Specification.md`
- **Agent Graph:** `docs/AGENT_GRAPH_VISUALIZATION.md`
- **KB Context Flow:** `docs/KB_CONTEXT_FLOW.md`
- **API Documentation:** `/docs` (Swagger UI)

---

**Last Updated:** 2025-11-07
**Maintainer:** Backend Team
