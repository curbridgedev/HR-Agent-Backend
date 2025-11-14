# Prompt Storage Architecture in Supabase

## Database Schema

### Table: `prompts`

All prompts are stored in a **single table** with differentiation through composite keys.

```sql
CREATE TABLE prompts (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Composite Identifier (what makes each prompt unique)
    name TEXT NOT NULL,           -- e.g., 'main_system_prompt', 'confidence_evaluation_prompt'
    prompt_type TEXT NOT NULL,    -- e.g., 'system', 'confidence', 'retrieval', 'analysis'
    version INTEGER NOT NULL,     -- e.g., 1, 2, 3 (auto-incremented per name+type)

    -- Content
    content TEXT NOT NULL,        -- The actual prompt text with {template} variables

    -- Status
    active BOOLEAN DEFAULT false, -- Only ONE version can be active per (name, prompt_type)

    -- Categorization
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],  -- e.g., ['production', 'v2', 'testing']
    metadata JSONB DEFAULT '{}'::jsonb,   -- Extra config like temperature, max_tokens

    -- Performance Metrics (populated by usage)
    usage_count INTEGER DEFAULT 0,
    avg_confidence FLOAT,
    escalation_rate FLOAT,

    -- Audit
    created_by TEXT,
    notes TEXT,               -- Why this version was created
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    UNIQUE(name, prompt_type, version)  -- Each version is unique per (name, type)
);
```

---

## How We Differentiate Between Prompts

### 1. By Prompt Type (`prompt_type` column)

This is the **primary differentiator**. It defines the role/purpose of the prompt.

| prompt_type | Purpose | Example Names |
|-------------|---------|---------------|
| `system` | AI identity and behavior | `main_system_prompt`, `query_analysis_system`, `tool_invocation_system` |
| `analysis` | Query understanding | `query_analysis_user` |
| `retrieval` | Context formatting | `retrieval_context_prompt` |
| `confidence` | Quality evaluation | `confidence_evaluation_prompt` |
| `generation` | Response formatting | (future use) |
| `escalation` | Human handoff messages | (future use) |

**Example Query**:
```sql
-- Get all system prompts
SELECT name, version, active FROM prompts WHERE prompt_type = 'system';

-- Get all confidence prompts
SELECT name, version, active FROM prompts WHERE prompt_type = 'confidence';
```

---

### 2. By Name (`name` column)

Within a prompt type, different prompts have different names.

**Example: Multiple `system` type prompts**:
```
prompt_type='system' + name='main_system_prompt'        → The AI assistant identity
prompt_type='system' + name='query_analysis_system'     → Query analyzer identity
prompt_type='system' + name='tool_invocation_system'    → Tool selector identity
```

**Example Query**:
```sql
-- Get a specific prompt
SELECT * FROM prompts
WHERE name = 'main_system_prompt'
  AND prompt_type = 'system';
```

---

### 3. By Version (`version` column)

Each (name, prompt_type) combination can have multiple versions for A/B testing and rollback.

**Example: Version history for `main_system_prompt`**:
```
name='main_system_prompt' + prompt_type='system' + version=1  → Original prompt
name='main_system_prompt' + prompt_type='system' + version=2  → Updated prompt
name='main_system_prompt' + prompt_type='system' + version=3  → Latest prompt
```

**Only ONE version can be active** per (name, prompt_type) at a time.

**Example Query**:
```sql
-- Get version history
SELECT version, active, notes, created_at
FROM prompts
WHERE name = 'main_system_prompt' AND prompt_type = 'system'
ORDER BY version DESC;

-- Get active version only
SELECT * FROM prompts
WHERE name = 'main_system_prompt'
  AND prompt_type = 'system'
  AND active = true;
```

---

## Visual Example: Current Database State

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PROMPTS TABLE                                     │
├──────────┬─────────────────────────┬──────────────┬─────────┬────────┬──────┤
│ id (UUID)│ name                    │ prompt_type  │ version │ active │ notes│
├──────────┼─────────────────────────┼──────────────┼─────────┼────────┼──────┤
│ abc-123  │ main_system_prompt      │ system       │    1    │  ✓ YES │ Orig │
│ abc-456  │ main_system_prompt      │ system       │    2    │    NO  │ CORR │
│ def-789  │ query_analysis_system   │ system       │    1    │  ✓ YES │ Orig │
│ ghi-012  │ tool_invocation_system  │ system       │    1    │  ✓ YES │ Orig │
├──────────┼─────────────────────────┼──────────────┼─────────┼────────┼──────┤
│ jkl-345  │ query_analysis_user     │ analysis     │    1    │  ✓ YES │ Orig │
├──────────┼─────────────────────────┼──────────────┼─────────┼────────┼──────┤
│ mno-678  │ retrieval_context_prompt│ retrieval    │    1    │  ✓ YES │ Orig │
├──────────┼─────────────────────────┼──────────────┼─────────┼────────┼──────┤
│ pqr-901  │ confidence_evaluation_..│ confidence   │    1    │  ✓ YES │ Orig │
│ stu-234  │ confidence_evaluation_..│ confidence   │    2    │    NO  │ Test │
└──────────┴─────────────────────────┴──────────────┴─────────┴────────┴──────┘
```

**Key Points**:
- `main_system_prompt` has 2 versions, but only v1 is active
- Each `prompt_type` groups related prompts together
- Each `name` identifies a specific prompt's purpose
- Each `version` tracks changes over time

---

## How the Backend Retrieves Prompts

### Method 1: Using `get_active_prompt()` Function

This is the **recommended method** used throughout the codebase.

```python
from app.services.prompts import get_active_prompt

# Get active main system prompt
prompt = await get_active_prompt(
    name="main_system_prompt",
    prompt_type="system"
)

# Returns PromptResponse object with:
# - id, name, prompt_type, version
# - content, metadata, tags
# - usage stats
```

**SQL Behind the Scenes**:
```sql
CREATE OR REPLACE FUNCTION get_active_prompt(
    prompt_name TEXT,
    prompt_type_filter TEXT DEFAULT NULL
)
RETURNS TABLE (...)
AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM prompts
    WHERE
        prompts.name = prompt_name
        AND prompts.active = true
        AND (prompt_type_filter IS NULL OR prompts.prompt_type = prompt_type_filter)
    LIMIT 1;
END;
$$;
```

### Method 2: Using `get_formatted_prompt()` Helper

This **retrieves AND formats** the prompt with template variables.

```python
from app.services.prompts import get_formatted_prompt

# Get and format confidence prompt
formatted_prompt, version = await get_formatted_prompt(
    name="confidence_evaluation_prompt",
    prompt_type="confidence",
    variables={
        "query": "How do I refund?",
        "context": "Refund policy: ...",
        "response": "To refund, go to..."
    },
    fallback="Default prompt if not found"
)

# Returns:
# - formatted_prompt: "Evaluate this response: ..." (with variables replaced)
# - version: 1 (the version number that was used)
```

---

## How Prompt Types Are Used in Agent Flow

### Agent Execution Flow with Prompts

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AGENT EXECUTION FLOW                            │
└─────────────────────────────────────────────────────────────────────────┘

1. USER QUERY
   └─> "How can I recover funds being held by my payment processor?"

2. ANALYZE QUERY NODE
   ├─> Loads: prompt_type='system' + name='query_analysis_system'
   └─> Loads: prompt_type='analysis' + name='query_analysis_user'
   └─> Output: Intent, category, confidence

3. RETRIEVE CONTEXT NODE
   └─> Searches vector DB for relevant documents
   └─> Output: Context documents

4. GENERATE RESPONSE NODE
   ├─> Loads: prompt_type='system' + name='main_system_prompt'  ⚠️ CRITICAL
   └─> Loads: prompt_type='retrieval' + name='retrieval_context_prompt'
   └─> LLM Call: System + Retrieval prompts + Context
   └─> Output: Generated response text

5. CALCULATE CONFIDENCE NODE
   └─> Loads: prompt_type='confidence' + name='confidence_evaluation_prompt'
   └─> LLM Call: Confidence prompt + Query + Context + Response
   └─> Output: Confidence score (0.0-1.0)

6. DECISION NODE
   └─> If confidence >= threshold: Return response
   └─> If confidence < threshold: Escalate to human

7. FORMAT OUTPUT NODE
   └─> Combines response + confidence + sources
   └─> Output: Final response to user
```

---

## Critical Constraint: One Active Version Per (Name, Type)

### Why This Matters

If you accidentally activate multiple versions of the same prompt, the system doesn't know which one to use!

**Example of PROBLEM**:
```
name='main_system_prompt' + prompt_type='system' + version=1  → active=true
name='main_system_prompt' + prompt_type='system' + version=2  → active=true ❌
```
☝️ This would cause unpredictable behavior!

### How It's Enforced

The `activate_prompt_version()` function **automatically deactivates** all other versions:

```sql
CREATE OR REPLACE FUNCTION activate_prompt_version(
    prompt_id_to_activate UUID
)
AS $$
DECLARE
    target_name TEXT;
    target_type TEXT;
BEGIN
    -- Get name and type of prompt to activate
    SELECT name, prompt_type INTO target_name, target_type
    FROM prompts WHERE id = prompt_id_to_activate;

    -- Deactivate ALL other versions with same (name, type)
    UPDATE prompts
    SET active = false
    WHERE name = target_name AND prompt_type = target_type;

    -- Activate the target
    UPDATE prompts
    SET active = true
    WHERE id = prompt_id_to_activate;
END;
$$;
```

**This ensures**:
- Only ONE active `main_system_prompt` of type `system`
- Only ONE active `confidence_evaluation_prompt` of type `confidence`
- etc.

---

## Common Queries for Frontend

### 1. List All Prompt Types
```sql
SELECT DISTINCT prompt_type, COUNT(*) as prompt_count
FROM prompts
GROUP BY prompt_type
ORDER BY prompt_type;
```

**API Equivalent**:
```http
GET /api/v1/prompts/types
```

### 2. List All Prompts of a Type
```sql
SELECT name, version, active, notes, created_at
FROM prompts
WHERE prompt_type = 'system'
ORDER BY name, version DESC;
```

**API Equivalent**:
```http
GET /api/v1/prompts?prompt_type=system
```

### 3. Get Version History for a Prompt
```sql
SELECT version, active, notes, created_at, usage_count, avg_confidence
FROM prompts
WHERE name = 'main_system_prompt' AND prompt_type = 'system'
ORDER BY version DESC;
```

**API Equivalent**:
```http
GET /api/v1/prompts/main_system_prompt/history?prompt_type=system
```

### 4. Get Active Version Only
```sql
SELECT * FROM prompts
WHERE name = 'main_system_prompt'
  AND prompt_type = 'system'
  AND active = true;
```

**API Equivalent**:
```http
GET /api/v1/prompts/active?name=main_system_prompt&prompt_type=system
```

---

## Summary: The Three-Level Hierarchy

```
LEVEL 1: prompt_type (Purpose Category)
  ├─ system     → AI identity prompts
  ├─ analysis   → Query understanding prompts
  ├─ retrieval  → Context formatting prompts
  ├─ confidence → Quality evaluation prompts
  └─ ...

LEVEL 2: name (Specific Prompt)
  ├─ main_system_prompt
  ├─ query_analysis_system
  ├─ query_analysis_user
  ├─ retrieval_context_prompt
  ├─ confidence_evaluation_prompt
  └─ ...

LEVEL 3: version (Change History)
  ├─ version=1 (active=true)   ← Currently used
  ├─ version=2 (active=false)  ← Previous version
  └─ version=3 (active=false)  ← Testing version
```

**Differentiation Logic**:
1. **prompt_type** separates by role (system vs confidence vs retrieval)
2. **name** separates by specific purpose within that role
3. **version** tracks changes over time
4. **active** flag determines which version is currently used

**Unique Identifier**: `(name, prompt_type, version)` → Ensures no duplicates

**Active Constraint**: Only ONE `active=true` per `(name, prompt_type)` → Prevents conflicts
