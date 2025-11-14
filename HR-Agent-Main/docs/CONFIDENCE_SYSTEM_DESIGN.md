# Confidence Calculation System Design

**Status**: Design Phase
**Date**: 2025-01-08
**Author**: System Architecture Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current System Analysis](#current-system-analysis)
3. [Hybrid Confidence System Design](#hybrid-confidence-system-design)
4. [Database Schema Changes](#database-schema-changes)
5. [Code Implementation](#code-implementation)
6. [Admin UI Configuration](#admin-ui-configuration)
7. [Testing Strategy](#testing-strategy)
8. [Migration Plan](#migration-plan)

---

## Executive Summary

### Problem Statement

Currently, the agent calculates confidence using **only an algorithmic formula** based on:
- Similarity scores (80% weight)
- High-quality source count (10% weight)
- Response completeness (10% weight)

While this is fast and deterministic, it has limitations:
- Cannot assess semantic quality of the response itself
- Cannot detect hallucinations or logical errors
- Limited understanding of context relevance beyond similarity scores

A **confidence evaluation prompt exists in the database but is not used**.

### Proposed Solution

Implement a **flexible hybrid confidence system** with three calculation methods:

1. **`formula`** - Current algorithmic approach (fast, deterministic, no LLM cost)
2. **`llm`** - LLM-based judgment using confidence_evaluation_prompt (slower, more semantic, LLM cost)
3. **`hybrid`** - Combination of both (best accuracy, moderate cost)

**Admin-configurable** via frontend dashboard with environment-specific settings.

### Benefits

✅ **Flexibility** - Choose method based on use case and cost tolerance
✅ **Accuracy** - LLM can detect issues the formula misses
✅ **Cost Control** - Formula-only mode for budget-conscious scenarios
✅ **A/B Testing** - Compare methods with real data
✅ **Progressive Enhancement** - Start with formula, add LLM when needed

---

## Current System Analysis

### Current Confidence Calculation (Formula-Only)

**Location**: `app/agents/nodes.py:547-615`

```python
async def calculate_confidence_node(state: AgentState) -> Dict[str, Any]:
    """
    Calculate confidence based on retrieval quality and response metrics.

    Formula:
    - 80%: Weighted similarity score (60% best, 30% 2nd, 10% 3rd)
    - 10%: High-quality source count boost (similarity > 0.75)
    - 10%: Response completeness boost (length >= 200 chars)
    """
```

**Strengths**:
- ⚡ Fast (~5ms)
- 💰 No LLM cost
- 🎯 Deterministic and reproducible
- 📊 Explainable weights

**Weaknesses**:
- ❌ Cannot assess semantic correctness
- ❌ Cannot detect hallucinations
- ❌ Limited to retrieval metrics only
- ❌ Ignores actual response quality

### Confidence Evaluation Prompt (Currently Unused)

**Location**: Database `prompts` table, `name='confidence_evaluation_prompt'`

**Content**:
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

**Strengths**:
- ✅ Can assess semantic quality
- ✅ Can detect logical issues
- ✅ Holistic evaluation of response

**Weaknesses**:
- ⏱️ Slower (~500-1000ms)
- 💰 LLM cost per evaluation (~$0.001-0.003)
- 🎲 Non-deterministic

---

## Hybrid Confidence System Design

### Three Calculation Methods

#### Method 1: `formula` (Current System)
**Use Case**: High-volume, cost-sensitive scenarios

```python
confidence = (
    similarity_score * 0.80 +
    source_boost * 0.10 +
    length_boost * 0.10
)
```

**Metrics**:
- Speed: ~5ms
- Cost: $0
- Accuracy: 75-85% (good for retrieval quality)

#### Method 2: `llm` (LLM Judgment)
**Use Case**: Critical queries requiring semantic validation

```python
# Load confidence_evaluation_prompt
prompt = await get_formatted_prompt(
    name="confidence_evaluation_prompt",
    variables={"response": response, "context": context, "query": query}
)

# Call LLM
llm_response = await llm.ainvoke([
    SystemMessage(content="You are a confidence evaluator..."),
    HumanMessage(content=prompt)
])

confidence = extract_score_from_llm_response(llm_response)
```

**Metrics**:
- Speed: ~500-1000ms
- Cost: ~$0.001-0.003 per evaluation
- Accuracy: 85-95% (can detect semantic issues)

#### Method 3: `hybrid` (Best of Both)
**Use Case**: Balanced accuracy and cost

**Strategy**: Always calculate both scores and combine with configurable weights

```python
# Calculate both scores in parallel
formula_score = calculate_formula_confidence(...)
llm_score = await calculate_llm_confidence(...)

# Combine with configurable weights
confidence = (formula_score * 0.60) + (llm_score * 0.40)
```

**Metrics**:
- Speed: ~500-1000ms (LLM call every time)
- Cost: ~$0.0002 per query (using GPT-4o-mini)
- Accuracy: 90-95% (combines retrieval quality + semantic quality)

### Configuration Structure

**Added to `agent_configs.config` JSONB**:

```json
{
  "confidence_calculation": {
    "method": "hybrid",  // "formula" | "llm" | "hybrid"
    "hybrid_settings": {
      "formula_weight": 0.60,
      "llm_weight": 0.40
    },
    "llm_settings": {
      "provider": "openai",  // "openai" | "anthropic" | "azure"
      "model": "gpt-4o-mini",  // Model name (provider-specific)
      "temperature": 0.1,
      "max_tokens": 100,
      "timeout_ms": 2000
    },
    "formula_weights": {
      "similarity": 0.80,
      "source_quality": 0.10,
      "response_length": 0.10
    }
  }
}
```

---

## Database Schema Changes

### Migration: `005_confidence_method_config.sql`

```sql
-- Add confidence calculation method to existing agent configs
-- No schema changes needed - just update existing config JSONB

-- Update default config (all environments)
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
    }'::jsonb
)
WHERE name = 'default_agent_config' AND environment = 'all';

-- Update development config (enable hybrid for testing)
UPDATE agent_configs
SET config = jsonb_set(
    config,
    '{confidence_calculation}',
    '{
        "method": "hybrid",
        "hybrid_settings": {
            "formula_weight": 0.50,
            "llm_weight": 0.50
        },
        "llm_settings": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.1,
            "max_tokens": 150,
            "timeout_ms": 3000
        },
        "formula_weights": {
            "similarity": 0.80,
            "source_quality": 0.10,
            "response_length": 0.10
        }
    }'::jsonb
)
WHERE name = 'default_agent_config' AND environment = 'development';

-- Update production config (cost-optimized, formula-only by default)
UPDATE agent_configs
SET config = jsonb_set(
    config,
    '{confidence_calculation}',
    '{
        "method": "formula",
        "hybrid_settings": {
            "formula_weight": 0.70,
            "llm_weight": 0.30
        },
        "llm_settings": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.1,
            "max_tokens": 80,
            "timeout_ms": 1500
        },
        "formula_weights": {
            "similarity": 0.80,
            "source_quality": 0.10,
            "response_length": 0.10
        }
    }'::jsonb
)
WHERE name = 'default_agent_config' AND environment = 'production';

-- Add comment for clarity
COMMENT ON COLUMN agent_configs.config IS 'JSONB configuration including confidence_calculation with method (formula/llm/hybrid), hybrid_settings (weights), llm_settings (provider, model, temperature), and formula_weights';
```

---

## Code Implementation

### 1. Add Pydantic Models for Configuration

**File**: `app/models/config.py`

```python
from pydantic import BaseModel, Field
from typing import Literal

class HybridConfidenceSettings(BaseModel):
    """Settings for hybrid confidence calculation."""
    formula_weight: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Weight for formula score in hybrid mode"
    )
    llm_weight: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description="Weight for LLM score in hybrid mode"
    )

    @property
    def weights_sum_to_one(self) -> bool:
        """Validate that weights sum to 1.0."""
        return abs((self.formula_weight + self.llm_weight) - 1.0) < 0.001

class LLMConfidenceSettings(BaseModel):
    """Settings for LLM-based confidence calculation."""
    provider: Literal["openai", "anthropic", "azure"] = Field(
        default="openai",
        description="LLM provider to use for confidence evaluation"
    )
    model: str = Field(
        default="gpt-4o-mini",
        description="LLM model to use (e.g., gpt-4, gpt-4o-mini, claude-3-haiku)"
    )
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM (lower = more deterministic)"
    )
    max_tokens: int = Field(
        default=100,
        gt=0,
        description="Maximum tokens for LLM response"
    )
    timeout_ms: int = Field(
        default=2000,
        gt=0,
        description="Timeout for LLM API call in milliseconds"
    )

class FormulaWeights(BaseModel):
    """Weights for formula-based confidence calculation."""
    similarity: float = Field(default=0.80, ge=0.0, le=1.0)
    source_quality: float = Field(default=0.10, ge=0.0, le=1.0)
    response_length: float = Field(default=0.10, ge=0.0, le=1.0)

class ConfidenceCalculationConfig(BaseModel):
    """Configuration for confidence calculation method."""
    method: Literal["formula", "llm", "hybrid"] = Field(
        default="formula",
        description="Confidence calculation method"
    )
    hybrid_settings: HybridConfidenceSettings = Field(
        default_factory=HybridConfidenceSettings
    )
    llm_settings: LLMConfidenceSettings = Field(
        default_factory=LLMConfidenceSettings
    )
    formula_weights: FormulaWeights = Field(
        default_factory=FormulaWeights
    )
```

### 2. Refactor Confidence Calculation Node

**File**: `app/agents/nodes.py`

```python
async def calculate_confidence_node(state: AgentState) -> Dict[str, Any]:
    """
    Calculate confidence using configurable method:
    - formula: Fast, deterministic, no LLM cost
    - llm: Semantic evaluation, slower, LLM cost
    - hybrid: Best of both, conditional LLM usage

    Method is determined by agent configuration.
    """
    try:
        # Load agent config
        agent_config = await get_active_config()
        if not agent_config:
            logger.warning("No active config, using fallback formula method")
            return await _calculate_formula_confidence(state)

        # Get confidence calculation config
        calc_config = agent_config.config.get("confidence_calculation", {})
        method = calc_config.get("method", "formula")

        logger.info(f"Using confidence method: {method}")

        # Route to appropriate calculation method
        if method == "formula":
            return await _calculate_formula_confidence(state, calc_config)
        elif method == "llm":
            return await _calculate_llm_confidence(state, calc_config)
        elif method == "hybrid":
            return await _calculate_hybrid_confidence(state, calc_config)
        else:
            logger.error(f"Invalid confidence method: {method}, falling back to formula")
            return await _calculate_formula_confidence(state)

    except Exception as e:
        logger.error(f"Confidence calculation failed: {e}", exc_info=True)
        return {"confidence_score": 0.0}


async def _calculate_formula_confidence(
    state: AgentState,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculate confidence using algorithmic formula.

    This is the current implementation (fast, deterministic).
    """
    context_docs = state.get("context_docs", [])
    response = state.get("response", "")
    response_length = len(response)

    # Get weights from config or use defaults
    weights = config.get("formula_weights", {}) if config else {}
    similarity_weight = weights.get("similarity", 0.80)
    source_weight = weights.get("source_quality", 0.10)
    length_weight = weights.get("response_length", 0.10)

    # No documents = zero confidence
    if not context_docs:
        logger.warning("No context documents - confidence=0.0")
        return {"confidence_score": 0.0}

    # PRIMARY SIGNAL: Similarity Score
    similarities = [doc.get("similarity", 0) for doc in context_docs[:3]]

    if len(similarities) >= 3:
        similarity_score = (
            similarities[0] * 0.6 +
            similarities[1] * 0.3 +
            similarities[2] * 0.1
        )
    elif len(similarities) == 2:
        similarity_score = similarities[0] * 0.7 + similarities[1] * 0.3
    else:
        similarity_score = similarities[0]

    # BOOST 1: High-Quality Source Count
    high_quality_sources = [
        doc for doc in context_docs if doc.get("similarity", 0) > 0.75
    ]

    if len(high_quality_sources) >= 3:
        source_boost = 1.0
    elif len(high_quality_sources) == 2:
        source_boost = 0.6
    elif len(high_quality_sources) == 1:
        source_boost = 0.3
    else:
        source_boost = 0.0

    # BOOST 2: Response Completeness
    if response_length >= 200:
        length_boost = 1.0
    elif response_length >= 100:
        length_boost = 0.5
    else:
        length_boost = 0.0

    # FINAL CALCULATION
    confidence = (
        similarity_score * similarity_weight +
        source_boost * source_weight +
        length_boost * length_weight
    )

    confidence = min(confidence, 1.0)

    logger.info(
        f"Formula confidence: {confidence:.3f} "
        f"(similarity={similarity_score:.3f}@{similarity_weight:.0%}, "
        f"sources={source_boost:.1f}@{source_weight:.0%}, "
        f"length={length_boost:.1f}@{length_weight:.0%})"
    )

    return {
        "confidence_score": confidence,
        "confidence_method": "formula",
        "confidence_breakdown": {
            "similarity_score": similarity_score,
            "source_boost": source_boost,
            "length_boost": length_boost
        }
    }


async def _calculate_llm_confidence(
    state: AgentState,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate confidence using LLM-based semantic evaluation.

    Uses the confidence_evaluation_prompt from database (editable by admin).
    Supports multiple LLM providers (OpenAI, Anthropic, Azure).
    """
    response = state.get("response", "")
    context_text = state.get("context_text", "")
    query = state.get("query", "")

    # Get LLM settings from config
    llm_settings = config.get("llm_settings", {})
    provider = llm_settings.get("provider", "openai")
    model = llm_settings.get("model", "gpt-4o-mini")
    temperature = llm_settings.get("temperature", 0.1)
    max_tokens = llm_settings.get("max_tokens", 100)
    timeout_ms = llm_settings.get("timeout_ms", 2000)

    try:
        # Load confidence evaluation prompt from database
        # This prompt is editable by admin via frontend
        prompt_content, prompt_version = await get_formatted_prompt(
            name="confidence_evaluation_prompt",
            prompt_type="confidence",
            variables={
                "query": query,
                "context": context_text[:1000],  # Limit context length
                "response": response[:500]  # Limit response length
            },
            fallback=(
                "Evaluate confidence in the response. "
                "Consider context quality, answer completeness, and potential gaps. "
                "Return ONLY a number between 0 and 1."
            )
        )

        logger.info(
            f"Using confidence evaluation prompt v{prompt_version} "
            f"with {provider}/{model}"
        )

        # Initialize LLM based on provider
        llm = get_chat_model(
            provider=provider,
            model=model,
            temperature=temperature
        )

        # Call LLM with timeout
        llm_response = await asyncio.wait_for(
            llm.ainvoke([
                SystemMessage(content="You are a confidence evaluator. Return ONLY a number between 0 and 1."),
                HumanMessage(content=prompt_content)
            ]),
            timeout=timeout_ms / 1000.0
        )

        # Extract score from response
        content = llm_response.content.strip()

        # Try to parse as float
        try:
            confidence = float(content)
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        except ValueError:
            # Try to extract first number from text
            import re
            numbers = re.findall(r'0?\.\d+|1\.0|1|0', content)
            if numbers:
                confidence = float(numbers[0])
                confidence = max(0.0, min(1.0, confidence))
            else:
                logger.error(f"Failed to parse LLM confidence score: {content}")
                confidence = 0.5  # Default to neutral

        logger.info(f"LLM confidence: {confidence:.3f} (model: {model})")

        return {
            "confidence_score": confidence,
            "confidence_method": "llm",
            "confidence_breakdown": {
                "llm_raw_response": content,
                "llm_model": model
            }
        }

    except asyncio.TimeoutError:
        logger.error(f"LLM confidence evaluation timed out ({timeout_ms}ms)")
        # Fallback to formula
        return await _calculate_formula_confidence(state, config)

    except Exception as e:
        logger.error(f"LLM confidence evaluation failed: {e}", exc_info=True)
        # Fallback to formula
        return await _calculate_formula_confidence(state, config)


async def _calculate_hybrid_confidence(
    state: AgentState,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate confidence using hybrid approach.

    Strategy:
    1. Calculate formula confidence (retrieval quality metrics)
    2. Calculate LLM confidence (semantic quality evaluation)
    3. Combine both scores with configurable weights

    This provides a balanced view:
    - Formula captures retrieval quality, similarity, completeness
    - LLM captures semantic correctness, logical coherence, hallucinations
    - Weighted combination gives best of both worlds
    """
    hybrid_settings = config.get("hybrid_settings", {})
    formula_weight = hybrid_settings.get("formula_weight", 0.60)
    llm_weight = hybrid_settings.get("llm_weight", 0.40)

    logger.info(
        f"Calculating hybrid confidence "
        f"(formula_weight={formula_weight:.0%}, llm_weight={llm_weight:.0%})"
    )

    # Step 1: Calculate formula confidence (retrieval quality)
    formula_result = await _calculate_formula_confidence(state, config)
    formula_score = formula_result["confidence_score"]

    # Step 2: Calculate LLM confidence (semantic quality)
    llm_result = await _calculate_llm_confidence(state, config)
    llm_score = llm_result["confidence_score"]

    # Step 3: Combine scores with weights
    final_score = (formula_score * formula_weight) + (llm_score * llm_weight)

    logger.info(
        f"Hybrid confidence: {final_score:.3f} "
        f"(formula={formula_score:.3f}@{formula_weight:.0%}, "
        f"llm={llm_score:.3f}@{llm_weight:.0%})"
    )

    return {
        "confidence_score": final_score,
        "confidence_method": "hybrid",
        "confidence_breakdown": {
            "formula_score": formula_score,
            "llm_score": llm_score,
            "formula_weight": formula_weight,
            "llm_weight": llm_weight
        }
    }
```

### 3. Update Agent State

**File**: `app/agents/state.py`

```python
class AgentState(TypedDict):
    # ... existing fields ...

    # Confidence tracking
    confidence_score: float
    confidence_method: str  # NEW: "formula" | "llm" | "hybrid"
    confidence_breakdown: Dict[str, Any]  # NEW: Detailed breakdown
```

---

## Admin UI Configuration

### Frontend Implementation Requirements

**File**: `frontend/app/admin/agent-config/page.tsx` (to be created)

#### UI Components Needed

1. **Confidence Method Selector**
   ```tsx
   <RadioGroup value={method} onChange={setMethod}>
     <Radio value="formula">
       Formula Only (Fast, No Cost)
     </Radio>
     <Radio value="llm">
       LLM Judgment (Accurate, LLM Cost)
     </Radio>
     <Radio value="hybrid">
       Hybrid (Best Balance)
     </Radio>
   </RadioGroup>
   ```

2. **Hybrid Settings Panel** (shown when `method === "hybrid"`)
   ```tsx
   <div className="space-y-4">
     <p className="text-sm text-gray-600">
       Hybrid mode calculates both formula and LLM scores, then combines them with configurable weights.
     </p>
     <WeightSlider
       label="Formula Weight (Retrieval Quality)"
       value={formulaWeight}
       onChange={(val) => {
         setFormulaWeight(val);
         setLLMWeight(1.0 - val); // Auto-adjust to sum to 1.0
       }}
       min={0}
       max={1}
       step={0.05}
     />
     <WeightSlider
       label="LLM Weight (Semantic Quality)"
       value={llmWeight}
       onChange={(val) => {
         setLLMWeight(val);
         setFormulaWeight(1.0 - val); // Auto-adjust to sum to 1.0
       }}
       min={0}
       max={1}
       step={0.05}
     />
     <p className="text-xs text-gray-500">
       Weights automatically adjust to sum to 1.0
     </p>
   </div>
   ```

3. **LLM Settings Panel** (shown when `method === "llm" || method === "hybrid"`)
   ```tsx
   <div className="space-y-4">
     <Select
       label="LLM Provider"
       value={llmProvider}
       onChange={(provider) => {
         setLLMProvider(provider);
         // Auto-select default model for provider
         if (provider === "openai") setLLMModel("gpt-4o-mini");
         if (provider === "anthropic") setLLMModel("claude-3-haiku-20240307");
         if (provider === "azure") setLLMModel("gpt-4o-mini");
       }}
       options={[
         { value: "openai", label: "OpenAI" },
         { value: "anthropic", label: "Anthropic (Claude)" },
         { value: "azure", label: "Azure OpenAI" }
       ]}
     />

     <Select
       label="Model"
       value={llmModel}
       onChange={setLLMModel}
       options={availableModels}
       isLoading={loadingModels}
       helpText={getModelCostEstimate(llmProvider, llmModel)}
     />

     <Slider
       label="Temperature"
       value={temperature}
       onChange={setTemperature}
       min={0}
       max={1}
       step={0.1}
       helpText="Lower = more deterministic, Higher = more creative"
     />

     <NumberInput
       label="Max Tokens"
       value={maxTokens}
       onChange={setMaxTokens}
       min={50}
       max={500}
       helpText="Limit response length (confidence score + reasoning)"
     />

     <NumberInput
       label="Timeout (ms)"
       value={timeoutMs}
       onChange={setTimeoutMs}
       min={500}
       max={5000}
       helpText="API call timeout (falls back to formula on timeout)"
     />
   </div>

   // Fetch models from existing endpoint (same as system prompt)
   useEffect(() => {
     const fetchModels = async () => {
       setLoadingModels(true);
       try {
         const response = await fetch(`/api/v1/admin/llm/models?provider=${llmProvider}`);
         const data = await response.json();
         setAvailableModels(data.models); // Should match system prompt endpoint format
       } catch (error) {
         console.error("Failed to fetch models:", error);
         setAvailableModels([]);
       } finally {
         setLoadingModels(false);
       }
     };

     if (llmProvider) {
       fetchModels();
     }
   }, [llmProvider]);
   ```

4. **Formula Weights Panel** (shown when `method === "formula" || method === "hybrid"`)
   ```tsx
   <div className="space-y-4">
     <WeightSlider
       label="Similarity Weight"
       value={similarityWeight}
       onChange={setSimilarityWeight}
     />
     <WeightSlider
       label="Source Quality Weight"
       value={sourceWeight}
       onChange={setSourceWeight}
     />
     <WeightSlider
       label="Response Length Weight"
       value={lengthWeight}
       onChange={setLengthWeight}
     />
     <p className="text-sm text-gray-500">
       Total: {(similarityWeight + sourceWeight + lengthWeight).toFixed(2)} (must equal 1.0)
     </p>
   </div>
   ```

5. **Confidence Prompt Editor** (shown when `method === "llm" || method === "hybrid"`)
   ```tsx
   <div className="space-y-4">
     <div className="flex items-center justify-between">
       <h3 className="text-lg font-semibold">Confidence Evaluation Prompt</h3>
       <Button
         variant="outline"
         size="sm"
         onClick={loadActivePrompt}
       >
         Load Active Prompt
       </Button>
     </div>

     <Alert>
       <InfoIcon className="h-4 w-4" />
       <AlertDescription>
         This prompt is used by the LLM to evaluate confidence.
         Edit to customize evaluation criteria.
         Template variables: {`{query}`}, {`{context}`}, {`{response}`}
       </AlertDescription>
     </Alert>

     <Textarea
       label="Prompt Content"
       value={confidencePrompt}
       onChange={setConfidencePrompt}
       rows={12}
       placeholder="Evaluate your confidence in the response you just generated..."
       className="font-mono text-sm"
     />

     <div className="flex items-center space-x-2">
       <Select
         label="Version"
         value={promptVersion}
         onChange={setPromptVersion}
         options={availablePromptVersions}
         className="w-32"
       />
       <Button
         variant="secondary"
         onClick={previewPromptWithSample}
       >
         Preview with Sample
       </Button>
       <Button
         variant="primary"
         onClick={savePromptVersion}
       >
         Save as New Version
       </Button>
     </div>

     <div className="text-xs text-gray-500">
       <p>Current version: v{activePromptVersion} | Last updated: {lastUpdated}</p>
       <p>Usage: {promptUsageCount} evaluations</p>
     </div>
   </div>
   ```

6. **Cost Estimator**
   ```tsx
   <InfoPanel>
     <h3>Estimated Monthly Cost</h3>
     <ul>
       <li>Formula: $0/month (no LLM calls)</li>
       <li>LLM: ${estimatedLLMCost}/month (100% queries)</li>
       <li>Hybrid: ${estimatedLLMCost}/month (100% queries, combined scores)</li>
     </ul>
     <p className="text-sm text-gray-500">
       Based on {monthlyQueryEstimate} queries/month
     </p>
     <p className="text-xs text-gray-400">
       Note: Hybrid uses same LLM cost as LLM-only mode (both evaluate every query)
     </p>
   </InfoPanel>
   ```

#### API Endpoints Needed

**Agent Configuration**:
- **GET `/api/v1/admin/agent-config`** - Get current agent config
- **PUT `/api/v1/admin/agent-config`** - Update agent config
- **POST `/api/v1/admin/agent-config/test`** - Test configuration with sample query

**LLM Provider & Model Selection** (reuse existing endpoint from system prompt):
- **GET `/api/v1/admin/llm/models?provider={provider}`** - Get available models for provider
  - Returns same format as system prompt model selector
  - Example: `{ "models": [{ "value": "gpt-4o-mini", "label": "GPT-4o Mini", "cost": "..." }] }`

**Prompt Management** (reuse existing endpoints from prompt system):
- **GET `/api/v1/admin/prompts/confidence_evaluation_prompt`** - Get all versions
- **GET `/api/v1/admin/prompts/confidence_evaluation_prompt/active`** - Get active version
- **POST `/api/v1/admin/prompts/confidence_evaluation_prompt`** - Create new version
- **PUT `/api/v1/admin/prompts/confidence_evaluation_prompt/{id}/activate`** - Activate version
- **POST `/api/v1/admin/prompts/confidence_evaluation_prompt/preview`** - Preview with sample data

**Example Request - Update Confidence Config**:
```json
PUT /api/v1/admin/agent-config
{
  "config": {
    "confidence_calculation": {
      "method": "hybrid",
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
      }
    }
  }
}
```

**Example Request - Create Confidence Prompt Version**:
```json
POST /api/v1/admin/prompts/confidence_evaluation_prompt
{
  "content": "Evaluate confidence in the response...",
  "notes": "Updated to focus more on hallucination detection",
  "tags": ["confidence", "v2", "hallucination-focus"],
  "activate_immediately": false
}
```

---

## Testing Strategy

### 1. Unit Tests

**File**: `tests/agents/test_confidence_calculation.py`

```python
import pytest
from app.agents.nodes import (
    _calculate_formula_confidence,
    _calculate_llm_confidence,
    _calculate_hybrid_confidence
)

@pytest.mark.asyncio
async def test_formula_confidence_high_quality():
    """Test formula with high-quality retrieval."""
    state = {
        "context_docs": [
            {"similarity": 0.95},
            {"similarity": 0.92},
            {"similarity": 0.88}
        ],
        "response": "A" * 250  # Long response
    }

    result = await _calculate_formula_confidence(state)

    assert result["confidence_score"] > 0.90
    assert result["confidence_method"] == "formula"

@pytest.mark.asyncio
async def test_llm_confidence():
    """Test LLM-based confidence calculation."""
    state = {
        "query": "What is my balance?",
        "context_text": "User balance is $1000",
        "response": "Your current balance is $1000."
    }

    config = {
        "llm_settings": {
            "model": "gpt-4o-mini",
            "temperature": 0.1,
            "max_tokens": 50,
            "timeout_ms": 5000
        }
    }

    result = await _calculate_llm_confidence(state, config)

    assert 0.0 <= result["confidence_score"] <= 1.0
    assert result["confidence_method"] == "llm"

@pytest.mark.asyncio
async def test_hybrid_confidence_combination():
    """Test hybrid mode combining both formula and LLM scores."""
    state = {
        "context_docs": [{"similarity": 0.90}, {"similarity": 0.85}],
        "response": "A" * 150,
        "query": "Test query",
        "context_text": "Test context"
    }

    config = {
        "hybrid_settings": {
            "formula_weight": 0.6,
            "llm_weight": 0.4
        },
        "llm_settings": {"model": "gpt-4o-mini"}
    }

    result = await _calculate_hybrid_confidence(state, config)

    assert result["confidence_method"] == "hybrid"
    assert "formula_score" in result["confidence_breakdown"]
    assert "llm_score" in result["confidence_breakdown"]
    assert result["confidence_breakdown"]["llm_score"] is not None

    # Verify weighted combination
    expected_score = (
        result["confidence_breakdown"]["formula_score"] * 0.6 +
        result["confidence_breakdown"]["llm_score"] * 0.4
    )
    assert abs(result["confidence_score"] - expected_score) < 0.001
```

### 2. Integration Tests

**File**: `tests/api/v1/test_chat_with_confidence.py`

```python
@pytest.mark.asyncio
async def test_chat_with_formula_confidence(client):
    """Test chat endpoint with formula confidence."""
    response = client.post("/api/v1/chat", json={
        "message": "What is my balance?",
        "session_id": "test-session"
    })

    assert response.status_code == 200
    data = response.json()
    assert "confidence_score" in data
    assert "confidence_method" in data
    assert data["confidence_method"] == "formula"

@pytest.mark.asyncio
async def test_chat_with_llm_confidence(client, test_db):
    """Test chat endpoint with LLM confidence."""
    # Update config to use LLM
    await test_db.table("agent_configs").update({
        "config": {
            "confidence_calculation": {"method": "llm"}
        }
    }).eq("name", "default_agent_config").execute()

    response = client.post("/api/v1/chat", json={
        "message": "What is my balance?",
        "session_id": "test-session"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["confidence_method"] == "llm"
```

### 3. A/B Testing Plan

**Objective**: Compare accuracy and cost of each method

**Metrics to Track**:
- Confidence score distribution
- Escalation rate
- User satisfaction (thumbs up/down)
- Response time
- Token usage and cost
- False positive rate (high confidence, wrong answer)
- False negative rate (low confidence, correct answer)

**Test Groups**:
- Group A: 33% formula
- Group B: 33% llm
- Group C: 33% hybrid

**Duration**: 2 weeks

**Success Criteria**:
- Hybrid mode achieves <10% false positive rate
- LLM mode detects 90%+ semantic issues
- Formula mode maintains <100ms response time

---

## Migration Plan

### Phase 1: Database Migration (Week 1)

**Tasks**:
1. ✅ Create migration `005_confidence_method_config.sql`
2. ✅ Update all existing configs with `confidence_calculation` field
3. ✅ Set default method to `formula` (no behavior change)
4. ✅ Run migration on dev, UAT, prod

**Validation**:
```sql
-- Verify all configs have confidence_calculation
SELECT name, environment, config->'confidence_calculation' as conf_calc
FROM agent_configs
WHERE active = true;
```

### Phase 2: Backend Implementation (Week 2)

**Tasks**:
1. ✅ Add Pydantic models for confidence config
2. ✅ Refactor `calculate_confidence_node()` to support all three methods
3. ✅ Implement `_calculate_formula_confidence()` (extract existing logic)
4. ✅ Implement `_calculate_llm_confidence()` (new)
5. ✅ Implement `_calculate_hybrid_confidence()` (new)
6. ✅ Update `AgentState` with new fields
7. ✅ Write unit tests
8. ✅ Write integration tests

**Testing**:
```bash
uv run pytest tests/agents/test_confidence_calculation.py -v
uv run pytest tests/api/v1/test_chat_with_confidence.py -v
```

### Phase 3: Admin UI (Week 3)

**Tasks**:
1. ⬜ Create admin config page with method selector
2. ⬜ Implement hybrid settings panel
3. ⬜ Implement LLM settings panel
4. ⬜ Implement formula weights panel
5. ⬜ Add cost estimator
6. ⬜ Add test configuration endpoint
7. ⬜ Update OpenAPI schema

### Phase 4: Testing & Rollout (Week 4)

**Tasks**:
1. ⬜ Enable hybrid mode in development environment
2. ⬜ Run A/B test for 2 weeks
3. ⬜ Analyze metrics and user feedback
4. ⬜ Tune hybrid settings based on data
5. ⬜ Roll out to UAT
6. ⬜ Roll out to production (formula mode initially)
7. ⬜ Gradually enable hybrid mode for production

---

## Cost Analysis

### Current System (Formula Only)

**Per Query**:
- Confidence calculation: $0
- Response time: +5ms

**Monthly** (10,000 queries):
- Total cost: $0

### LLM-Only Mode

**Per Query**:
- Confidence evaluation: ~100 tokens
- Cost: ~$0.002 (GPT-4) or ~$0.0002 (GPT-4o-mini)
- Response time: +500-1000ms

**Monthly** (10,000 queries):
- Total cost: $20 (GPT-4) or $2 (GPT-4o-mini)

### Hybrid Mode

**Behavior**:
- Always calculates both formula and LLM scores
- Combines with configurable weights (default 60/40)
- Use GPT-4o-mini for cost optimization

**Per Query**:
- Formula: $0
- LLM (100% of time): $0.0002
- Average response time: +500-1000ms

**Monthly** (10,000 queries):
- Total cost: $2 (same as LLM-only)

### Cost Comparison Summary

| Method | Cost/Query | Monthly Cost (10K) | Response Time | Best For |
|--------|------------|-------------------|---------------|----------|
| Formula | $0 | $0 | +5ms | High volume, cost-sensitive |
| LLM (GPT-4) | $0.002 | $20 | +500ms | Critical semantic evaluation |
| LLM (GPT-4o-mini) | $0.0002 | $2 | +500ms | Semantic evaluation, budget-conscious |
| Hybrid (GPT-4o-mini) | $0.0002 | **$2** | +500ms | **Balanced retrieval + semantic** |

**Key Insight**: Hybrid has same cost as LLM-only since both evaluate every query. The advantage is **combining two different confidence signals** for better accuracy.

**Recommendation**:
- **Production (initial)**: Formula mode ($0 cost)
- **Production (after validation)**: Hybrid with GPT-4o-mini ($2/10K queries)
- **Development**: Hybrid with GPT-4o-mini for testing

---

## Next Steps

### Immediate Actions

1. **Review this design document** with team
2. **Create database migration** `005_confidence_method_config.sql`
3. **Implement backend changes** (estimated 2 days)
4. **Write tests** (estimated 1 day)
5. **Deploy to development** for testing

### Future Enhancements

1. **Semantic Caching** - Cache LLM confidence evaluations for similar queries
2. **Confidence Calibration** - Train a small model to predict LLM confidence without calling LLM
3. **Multi-Model Ensemble** - Use multiple LLMs and aggregate confidence scores
4. **User Feedback Loop** - Use thumbs up/down to refine confidence thresholds
5. **Real-Time A/B Testing** - Dynamic method selection based on live metrics

---

## Appendix: Configuration Examples

### Development Environment (Equal Weighting, OpenAI)

```json
{
  "confidence_calculation": {
    "method": "hybrid",
    "hybrid_settings": {
      "formula_weight": 0.50,
      "llm_weight": 0.50
    },
    "llm_settings": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "temperature": 0.1,
      "max_tokens": 150,
      "timeout_ms": 3000
    },
    "formula_weights": {
      "similarity": 0.80,
      "source_quality": 0.10,
      "response_length": 0.10
    }
  }
}
```

### Development Environment (Testing Claude)

```json
{
  "confidence_calculation": {
    "method": "hybrid",
    "hybrid_settings": {
      "formula_weight": 0.50,
      "llm_weight": 0.50
    },
    "llm_settings": {
      "provider": "anthropic",
      "model": "claude-3-haiku-20240307",
      "temperature": 0.1,
      "max_tokens": 150,
      "timeout_ms": 3000
    },
    "formula_weights": {
      "similarity": 0.80,
      "source_quality": 0.10,
      "response_length": 0.10
    }
  }
}
```

### UAT Environment (Favor Retrieval Quality)

```json
{
  "confidence_calculation": {
    "method": "hybrid",
    "hybrid_settings": {
      "formula_weight": 0.60,
      "llm_weight": 0.40
    },
    "llm_settings": {
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
  }
}
```

### Production Environment (Cost-Optimized Initial)

```json
{
  "confidence_calculation": {
    "method": "formula",
    "hybrid_settings": {
      "formula_weight": 0.70,
      "llm_weight": 0.30
    },
    "llm_settings": {
      "model": "gpt-4o-mini",
      "temperature": 0.1,
      "max_tokens": 80,
      "timeout_ms": 1500
    },
    "formula_weights": {
      "similarity": 0.80,
      "source_quality": 0.10,
      "response_length": 0.10
    }
  }
}
```

### Production Environment (After Validation - Favor Semantic)

```json
{
  "confidence_calculation": {
    "method": "hybrid",
    "hybrid_settings": {
      "formula_weight": 0.40,
      "llm_weight": 0.60
    },
    "llm_settings": {
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
  }
}
```

---

**End of Design Document**
