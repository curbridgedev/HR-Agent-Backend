# Confidence System Design Updates

**Date**: 2025-01-08
**Summary**: Updated confidence system design based on user feedback

---

## Changes Made

### 1. Simplified Hybrid Method

**Before** (Conditional LLM):
- Only invoked LLM for "borderline" scores (0.85-0.95)
- Required borderline_min and borderline_max configuration
- Complex conditional logic
- Unpredictable cost (30% of queries)

**After** (Always Combine):
- Always calculates both formula and LLM scores
- Combines with configurable weights (default 60/40)
- Simple, consistent logic
- Predictable cost (100% of queries = same as LLM-only)

**Benefits**:
- ✅ Simpler implementation (no borderline thresholds)
- ✅ Consistent behavior (every query gets both perspectives)
- ✅ Better accuracy (always combines retrieval + semantic quality)
- ✅ Predictable cost model

### 2. Admin-Configurable LLM Provider

**Added to Configuration**:
```json
{
  "llm_settings": {
    "provider": "openai",  // NEW: "openai" | "anthropic" | "azure"
    "model": "gpt-4o-mini",
    "temperature": 0.1,
    "max_tokens": 100,
    "timeout_ms": 2000
  }
}
```

**Supported Providers**:
- **OpenAI**: GPT-4, GPT-4o, GPT-4o-mini, GPT-3.5-turbo
- **Anthropic**: Claude 3.5 Sonnet, Claude 3 Haiku
- **Azure**: GPT-4o, GPT-4o-mini

**UI Integration**:
- Reuses existing `/api/v1/admin/llm/models?provider={provider}` endpoint
- Same model selector component as system prompt configuration
- Auto-updates model list when provider changes

### 3. Editable Confidence Prompt

**New Admin UI Component**:
- Full prompt editor with syntax highlighting
- Version management (create, activate, view history)
- Preview with sample data
- Template variable support: `{query}`, `{context}`, `{response}`

**Backend Integration**:
- Reuses existing prompt management system
- Same endpoints as other prompts (query_analysis, retrieval_context, etc.)
- Version tracking and usage analytics
- Database-driven with fallback to hardcoded default

**Prompt Management Endpoints** (already exist):
- `GET /api/v1/admin/prompts/confidence_evaluation_prompt` - All versions
- `GET /api/v1/admin/prompts/confidence_evaluation_prompt/active` - Active version
- `POST /api/v1/admin/prompts/confidence_evaluation_prompt` - Create version
- `PUT /api/v1/admin/prompts/confidence_evaluation_prompt/{id}/activate` - Activate
- `POST /api/v1/admin/prompts/confidence_evaluation_prompt/preview` - Preview

---

## Updated Configuration Structure

### Pydantic Models

```python
class HybridConfidenceSettings(BaseModel):
    """Settings for hybrid confidence calculation."""
    formula_weight: float = 0.60
    llm_weight: float = 0.40

class LLMConfidenceSettings(BaseModel):
    """Settings for LLM-based confidence calculation."""
    provider: Literal["openai", "anthropic", "azure"] = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 100
    timeout_ms: int = 2000

class ConfidenceCalculationConfig(BaseModel):
    """Configuration for confidence calculation method."""
    method: Literal["formula", "llm", "hybrid"] = "formula"
    hybrid_settings: HybridConfidenceSettings
    llm_settings: LLMConfidenceSettings
    formula_weights: FormulaWeights
```

### Database Migration Changes

**File**: `supabase/migrations/005_confidence_method_config.sql`

**Added**:
- `provider` field to all `llm_settings`
- Comment documenting the config structure

**Example**:
```sql
UPDATE agent_configs
SET config = jsonb_set(
    config,
    '{confidence_calculation}',
    '{
        "method": "hybrid",
        "llm_settings": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            ...
        }
    }'::jsonb
)
WHERE name = 'default_agent_config';
```

---

## Implementation Summary

### Code Changes Required

1. **`app/models/config.py`**:
   - Add `provider` field to `LLMConfidenceSettings`
   - Remove `borderline_min` and `borderline_max` from `HybridConfidenceSettings`

2. **`app/agents/nodes.py`**:
   - Update `_calculate_llm_confidence()` to use `provider` parameter
   - Simplify `_calculate_hybrid_confidence()` to always combine scores
   - Update logging to include provider info

3. **`app/core/llm.py`** (if needed):
   - Ensure `get_chat_model()` supports `provider` parameter
   - Handle provider-specific initialization

### Frontend Changes Required

**File**: `frontend/app/admin/agent-config/confidence/page.tsx` (to be created)

**Components**:
1. **Method Selector**: Radio group (formula/llm/hybrid)
2. **Provider Selector**: Dropdown (OpenAI/Anthropic/Azure)
3. **Model Selector**: Dynamic dropdown (fetches from existing endpoint)
4. **Weight Sliders**: Formula/LLM weights (auto-adjust to sum to 1.0)
5. **Prompt Editor**: Full editor with version management
6. **Cost Estimator**: Monthly cost calculation

**API Integration**:
- Reuse `/api/v1/admin/llm/models?provider={provider}` for model list
- Reuse prompt management endpoints for confidence prompt
- New endpoint: `/api/v1/admin/agent-config` for config updates

---

## Testing Checklist

### Unit Tests

- ✅ Test `_calculate_formula_confidence()` with various scenarios
- ✅ Test `_calculate_llm_confidence()` with all providers
- ✅ Test `_calculate_hybrid_confidence()` always combines scores
- ✅ Test weighted combination math (formula * 0.6 + llm * 0.4)
- ✅ Test LLM timeout handling (falls back to formula)
- ✅ Test prompt loading with template variables

### Integration Tests

- ✅ Test confidence calculation via chat endpoint
- ✅ Test switching between methods (formula/llm/hybrid)
- ✅ Test switching between providers (OpenAI/Anthropic/Azure)
- ✅ Test prompt version activation and usage
- ✅ Test config update endpoint

### Cost Validation

| Method | Provider | Model | Expected Cost/10K |
|--------|----------|-------|-------------------|
| Formula | N/A | N/A | $0 |
| LLM | OpenAI | gpt-4 | ~$20 |
| LLM | OpenAI | gpt-4o-mini | ~$2 |
| LLM | Anthropic | claude-3-haiku | ~$1.50 |
| Hybrid | OpenAI | gpt-4o-mini | ~$2 (same as LLM) |

---

## Migration Path

### Phase 1: Backend (Week 1)
1. ✅ Update Pydantic models
2. ✅ Refactor confidence calculation nodes
3. ✅ Add provider support to LLM initialization
4. ✅ Write unit tests
5. ✅ Create database migration

### Phase 2: Database (Week 1)
1. ⬜ Apply migration to development
2. ⬜ Verify config structure
3. ⬜ Test provider switching
4. ⬜ Validate prompt editing

### Phase 3: Frontend (Week 2)
1. ⬜ Create confidence config page
2. ⬜ Integrate provider/model selectors
3. ⬜ Build prompt editor component
4. ⬜ Add cost estimator
5. ⬜ Test E2E workflows

### Phase 4: Rollout (Week 3)
1. ⬜ Deploy to development
2. ⬜ A/B test methods and providers
3. ⬜ Analyze metrics
4. ⬜ Deploy to production (formula mode)
5. ⬜ Gradually enable hybrid mode

---

## Key Decisions

### 1. Why Always-Combine Hybrid?

**Considered**:
- Conditional LLM (only for borderline scores)
- Always-combine (every query)

**Chosen**: Always-combine

**Rationale**:
- Simpler implementation (no threshold logic)
- More consistent behavior (predictable cost)
- Better accuracy (two perspectives on every query)
- Same cost as LLM-only (no cost advantage to conditional)

### 2. Why Multi-Provider Support?

**Rationale**:
- Different providers excel at different tasks
- Cost optimization (Claude Haiku vs GPT-4)
- Redundancy (fallback if one provider down)
- Flexibility for future providers

### 3. Why Editable Confidence Prompt?

**Rationale**:
- Different use cases need different evaluation criteria
- A/B testing prompt variations for accuracy
- Consistency with other prompt management
- No code deployment for prompt changes

---

## Next Steps

1. **Review this design** with team
2. **Implement backend changes** (estimated 2-3 days)
3. **Write comprehensive tests** (estimated 1-2 days)
4. **Deploy to development** for testing
5. **Build frontend UI** (estimated 3-4 days, frontend team)
6. **A/B test** methods and providers (2 weeks)
7. **Production rollout** (phased, formula → hybrid)

---

## Questions for Review

1. Should we add more providers (e.g., Gemini, Mistral)?
2. Should we allow multiple LLM evaluations and ensemble them?
3. Should we cache LLM confidence scores for similar queries?
4. Should we add confidence calibration (train model to predict LLM score)?

---

**End of Update Summary**
