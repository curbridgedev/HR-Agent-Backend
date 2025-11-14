# Prompt Management System Documentation

## Overview

The Compaytence AI Agent uses a **database-driven prompt system** with versioning, allowing dynamic prompt updates without code changes. This document explains the prompt types, their purposes, and how to manage them safely.

## Prompt Types

The system uses **5 distinct prompt types**, each serving a specific purpose in the agent workflow:

### 1. System Prompts (`prompt_type: 'system'`)

**Purpose**: Define the AI's identity, role, and behavior guidelines.

**When Used**: Loaded at the beginning of every LLM interaction to set the AI's persona.

**Critical Prompts**:

| Name | Description | Used By |
|------|-------------|---------|
| `main_system_prompt` | **PRIMARY ASSISTANT IDENTITY** - Defines the AI as "Compaytence AI, a finance/payment specialist". This is what makes the AI answer user questions. | `generate_response_node` |
| `query_analysis_system` | Query classification specialist - analyzes user intent | `analyze_query_node` |
| `tool_invocation_system` | Tool selection specialist - determines which tools to use | Tool routing logic |

**⚠️ CRITICAL**: `main_system_prompt` must ALWAYS define the AI as an assistant that **answers user questions**. NEVER replace it with an evaluator, analyzer, or any other role.

**Example of CORRECT `main_system_prompt`**:
```
You are Compaytence AI, an intelligent assistant specialized in finance and payment operations.
Your role is to provide accurate, helpful information about payment processing, transaction details, refund policies, and payment methods.

Key responsibilities:
- Answer questions about payment status, transaction details, and refunds
- Provide information about supported payment methods
- Explain payment policies and procedures
- Assist with payment-related troubleshooting
...
```

**Example of WRONG `main_system_prompt` (NEVER DO THIS)**:
```
You are an impartial evaluator. Assess the quality of the response...
```
☝️ This would make the AI evaluate instead of answer questions!

---

### 2. Analysis Prompts (`prompt_type: 'analysis'`)

**Purpose**: Query understanding and classification prompts.

**When Used**: During query analysis phase to understand user intent.

| Name | Description | Template Variables |
|------|-------------|--------------------|
| `query_analysis_user` | Analyzes and classifies user queries | `{query}` |

---

### 3. Retrieval Prompts (`prompt_type: 'retrieval'`)

**Purpose**: Format retrieved context and user query for response generation.

**When Used**: After RAG retrieval, before LLM generates response.

| Name | Description | Template Variables |
|------|-------------|--------------------|
| `retrieval_context_prompt` | Presents context and query to LLM for answering | `{context}`, `{query}` |

**Example**:
```
Based on the following context from our knowledge base, please answer the user's question.

Context:
{context}

User Question:
{query}

Please provide a comprehensive answer based on the context above.
```

---

### 4. Confidence Prompts (`prompt_type: 'confidence'`)

**Purpose**: Evaluate confidence in AI-generated responses.

**When Used**: After response generation, to calculate confidence score (LLM or hybrid mode only).

| Name | Description | Template Variables |
|------|-------------|--------------------|
| `confidence_evaluation_prompt` | Evaluates response quality and returns a 0.0-1.0 confidence score | `{query}`, `{context}`, `{response}` |

**⚠️ IMPORTANT**: This prompt must instruct the LLM to return **ONLY a number between 0.0 and 1.0**. Verbose evaluation text will cause parsing errors.

**Example**:
```
You are a confidence evaluator. You must respond with ONLY a single decimal number between 0.0 and 1.0.

Query: {query}
Context: {context}
Response: {response}

Respond with ONLY a number (e.g., "0.85"):
```

---

### 5. Other Prompts

Additional prompt types can be added for:
- `generation`: Response formatting templates
- `escalation`: Human escalation messages
- `fallback`: Error handling messages

---

## Prompt Versioning

### How Versioning Works

1. **Auto-Increment**: Version numbers auto-increment per `(name, prompt_type)` combination
2. **Single Active**: Only ONE version can be active per `(name, prompt_type)`
3. **Immutable History**: Old versions are preserved for rollback and A/B testing

### Creating a New Version

**Via API** (Recommended):
```bash
POST /api/v1/prompts/versions
{
  "name": "main_system_prompt",
  "prompt_type": "system",
  "content": "You are Compaytence AI...",
  "notes": "Improved clarity and added compliance guidelines",
  "activate_immediately": true  # Set to false to test before activation
}
```

**Via Database**:
```sql
-- Use the RPC function for automatic version increment
SELECT create_prompt_version(
  'main_system_prompt',
  'system',
  'You are Compaytence AI...',
  ARRAY['v3', 'production'],
  NULL,  -- metadata
  'admin',
  'Added compliance guidelines',
  true  -- activate immediately
);
```

### Activating a Version

**Via API**:
```bash
POST /api/v1/prompts/{prompt_id}/activate
```

**Via Database**:
```sql
-- Use the RPC function to handle deactivation of other versions
SELECT activate_prompt_version('{prompt_id}');
```

---

## Prompt Safety Rules

### ❌ DO NOT

1. **NEVER replace `main_system_prompt` with an evaluator/analyzer prompt**
   - This causes the AI to evaluate instead of answer questions
   - Always ensure it defines the AI as an assistant

2. **NEVER have multiple active versions** of the same `(name, prompt_type)`
   - Database constraint prevents this, but be aware

3. **NEVER delete prompts** - deactivate them instead
   - Preserves history and allows rollback

4. **NEVER hardcode prompts in application code**
   - Always use database prompts for dynamic management

### ✅ DO

1. **Always test new versions** before activating in production
   - Use `activate_immediately: false` when creating
   - Test in development environment first

2. **Use descriptive notes** when creating versions
   - Explain what changed and why
   - Example: "Fixed typo in compliance section" or "Improved clarity for payment refund policies"

3. **Tag prompts** appropriately
   - Use tags like: `['production']`, `['testing']`, `['v2']`, `['experiment-a']`

4. **Monitor performance metrics**
   - Check `usage_count`, `avg_confidence`, `escalation_rate`
   - Roll back if metrics degrade

---

## Frontend Prompt Management UI

### Required Features

#### 1. Prompt List View

Display all prompts grouped by type:

```
┌─ System Prompts ────────────────────────────────────┐
│ main_system_prompt                                   │
│   ● v1 (Active) - Default assistant prompt          │
│   ○ v2 (Inactive) - CORRUPTED: Evaluator prompt     │
│                                                      │
│ query_analysis_system                                │
│   ● v1 (Active) - Query analyzer prompt             │
└──────────────────────────────────────────────────────┘

┌─ Confidence Prompts ────────────────────────────────┐
│ confidence_evaluation_prompt                         │
│   ● v1 (Active) - Formula-based confidence          │
│   ○ v2 (Testing) - Strict numeric-only output       │
└──────────────────────────────────────────────────────┘
```

**API Endpoint**: `GET /api/v1/prompts?prompt_type={type}&active_only=false`

#### 2. Prompt Editor

- **View**: Display full prompt content with syntax highlighting
- **Edit**: Create new version (not edit existing)
- **Preview**: Show template variable substitution
- **Diff**: Compare versions side-by-side

#### 3. Version Management

- **Activate**: Switch active version (shows confirmation dialog)
- **Rollback**: Quick rollback to previous version
- **History**: View all versions with notes and metrics

#### 4. Safety Features

- **Warning for `main_system_prompt`**: Show big warning when editing
- **Content Validation**: Check template variables match expected format
- **Preview Mode**: Test prompt before activation
- **Confirmation Dialogs**: Require confirmation for activation

---

## API Endpoints

### List Prompts
```http
GET /api/v1/prompts?prompt_type=system&active_only=true
```

### Get Prompt History
```http
GET /api/v1/prompts/{name}/history?prompt_type=system
```

### Create New Version
```http
POST /api/v1/prompts/versions
Content-Type: application/json

{
  "name": "main_system_prompt",
  "prompt_type": "system",
  "content": "You are Compaytence AI...",
  "tags": ["v3", "production"],
  "notes": "Improved clarity",
  "activate_immediately": false
}
```

### Activate Version
```http
POST /api/v1/prompts/{prompt_id}/activate
```

### Get Active Prompt
```http
GET /api/v1/prompts/active?name=main_system_prompt&prompt_type=system
```

---

## Troubleshooting

### Problem: AI is responding with evaluation text instead of answers

**Cause**: `main_system_prompt` was replaced with an evaluator prompt

**Fix**:
```sql
-- Check active version
SELECT name, version, active, LEFT(content, 100) as preview
FROM prompts
WHERE name = 'main_system_prompt' AND prompt_type = 'system'
ORDER BY version DESC;

-- If wrong version is active, deactivate it
UPDATE prompts SET active = false
WHERE name = 'main_system_prompt' AND prompt_type = 'system' AND version = 2;

-- Activate correct version
UPDATE prompts SET active = true
WHERE name = 'main_system_prompt' AND prompt_type = 'system' AND version = 1;
```

### Problem: Confidence calculation returning verbose text

**Cause**: `confidence_evaluation_prompt` doesn't enforce numeric-only output

**Fix**: Update prompt to be more strict:
```
You must respond with ONLY a single decimal number between 0.0 and 1.0.
NO explanations, NO text, NO reasoning - ONLY the number.

Examples of correct responses:
0.85
0.72
0.95

Your response (number only):
```

### Problem: Multiple active versions

**Cause**: Database constraint violation (should not be possible)

**Fix**:
```sql
-- Find duplicates
SELECT name, prompt_type, COUNT(*) as active_count
FROM prompts
WHERE active = true
GROUP BY name, prompt_type
HAVING COUNT(*) > 1;

-- Manually deactivate all except desired version
UPDATE prompts SET active = false
WHERE name = 'problematic_prompt' AND prompt_type = 'system';

-- Activate desired version
UPDATE prompts SET active = true
WHERE name = 'problematic_prompt' AND prompt_type = 'system' AND version = 1;
```

---

## Metrics and Monitoring

Each prompt tracks:
- `usage_count`: Number of times used
- `avg_confidence`: Average confidence of responses (if applicable)
- `escalation_rate`: Percentage of responses escalated to human

**Monitor these metrics** after activating new versions to detect degradation.

---

## Best Practices

1. **Test in Development First**: Always test new prompt versions in development environment
2. **Gradual Rollout**: Use A/B testing for significant changes
3. **Document Changes**: Always add clear notes explaining what changed
4. **Monitor Metrics**: Track performance after activation
5. **Keep Backups**: Old versions are automatically preserved - don't delete them
6. **Review Regularly**: Periodically review and optimize prompts based on metrics

---

## Summary Table: What Each Prompt Type Does

| Prompt Type | Purpose | Example Name | Critical? | Used By |
|-------------|---------|--------------|-----------|---------|
| `system` | AI identity and behavior | `main_system_prompt` | ⚠️ YES | All LLM calls |
| `analysis` | Query understanding | `query_analysis_user` | No | Query analysis |
| `retrieval` | Context formatting | `retrieval_context_prompt` | No | Response generation |
| `confidence` | Quality evaluation | `confidence_evaluation_prompt` | No | Confidence calculation |

**Remember**: Only `main_system_prompt` controls what the AI actually does. Corrupting it will break the entire system!
