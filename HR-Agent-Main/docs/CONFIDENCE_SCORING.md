# Confidence Scoring System - How Agent Confidence is Calculated

This document explains how the AI agent calculates confidence scores for its responses and decides whether to answer or escalate to human support.

---

## Overview

The confidence score is a **numerical value between 0.0 and 1.0** that represents how confident the agent is in its response quality.

**Key Components:**
- **Calculation**: Multi-factor weighted scoring in `calculate_confidence_node()`
- **Decision**: Threshold-based escalation in `decision_node()`
- **Default Threshold**: 0.95 (95% confidence required)

---

## Confidence Calculation Formula

**File**: `app/agents/nodes.py:514` - `calculate_confidence_node()`

The confidence score is calculated using a **retrieval-quality focused model**:

```python
confidence = (
    similarity_score * 0.80 +   # PRIMARY: Retrieval quality (80%)
    source_boost * 0.10 +        # BOOST: Source diversity (10%)
    length_boost * 0.10          # BOOST: Response completeness (10%)
)
```

**Total**: 100% (0.80 + 0.10 + 0.10 = 1.0)

**Core Principle**: Confidence represents the **probability that retrieved documents properly address the user query**. High similarity = high confidence.

---

## Factor 1: Similarity Score (80% Weight - PRIMARY)

**What it measures**: How relevant the **best** retrieved KB documents are to the query

**Why Primary**: This is the **actual indicator** of retrieval quality. High similarity means the KB contains content that addresses the query.

**Calculation**:
```python
# Get top 3 document similarities
similarities = [doc.get("similarity", 0) for doc in context_docs[:3]]

# Weighted average favoring best matches
if len(similarities) >= 3:
    # 60% best, 30% second, 10% third
    similarity_score = (
        similarities[0] * 0.6 +
        similarities[1] * 0.3 +
        similarities[2] * 0.1
    )
elif len(similarities) == 2:
    # 70% best, 30% second
    similarity_score = similarities[0] * 0.7 + similarities[1] * 0.3
else:
    # Single document
    similarity_score = similarities[0]

# Apply 80% weight
confidence += similarity_score * 0.80
```

**Example**:
```python
# Retrieved documents with similarity scores
documents = [
    {"content": "...", "similarity": 0.92},  # Best match
    {"content": "...", "similarity": 0.85},  # Second best
    {"content": "...", "similarity": 0.78},  # Third best
]

# Weighted calculation (favoring top results)
similarity_score = (0.92 * 0.6) + (0.85 * 0.3) + (0.78 * 0.1)
similarity_score = 0.552 + 0.255 + 0.078 = 0.885

# Apply 80% weight
contribution = 0.885 * 0.80 = 0.708  # 70.8% contribution to final confidence
```

**What affects this score**:
- ✅ **Best match quality** = Highest impact (60% of similarity score)
- ✅ **Hybrid search effectiveness** = Better matching documents
- ✅ **KB content quality** = More relevant documents in database
- ✅ **Query clarity** = Well-formed queries get better matches
- ❌ **Poor query-document match** = Lower similarity scores
- ❌ **Missing KB content** = No relevant documents found

**Similarity Score Range**:
- **0.9-1.0**: Excellent match (near-duplicate content)
- **0.8-0.9**: Very good match (highly relevant)
- **0.7-0.8**: Good match (relevant with some differences)
- **0.6-0.7**: Moderate match (somewhat relevant)
- **<0.6**: Weak match (low relevance)

**Why Weighted Average?**:
- One perfect match (0.95) is better than three mediocre ones (0.70 each)
- Favoring top results aligns with how users consume search results
- Reflects actual retrieval quality better than simple average

---

## Factor 2: Source Boost (10% Weight - BOOST)

**What it measures**: Presence of multiple **high-quality** sources (similarity > 0.75)

**Why a Boost**: Having multiple high-quality sources increases confidence, but only if they're actually relevant. Low-quality sources don't help.

**Calculation**:
```python
# Only count high-quality sources
high_quality_sources = [
    doc for doc in context_docs
    if doc.get("similarity", 0) > 0.75
]

if len(high_quality_sources) >= 3:
    source_boost = 1.0  # Full 10% boost
elif len(high_quality_sources) == 2:
    source_boost = 0.6  # 6% boost
elif len(high_quality_sources) == 1:
    source_boost = 0.3  # 3% boost
else:
    source_boost = 0.0  # No boost

# Apply 10% weight
confidence += source_boost * 0.10
```

**Scoring Table**:
| High-Quality Sources (>0.75) | Source Boost | Contribution to Confidence |
|------------------------------|--------------|----------------------------|
| 0 sources                    | 0.0          | 0%                         |
| 1 source                     | 0.3          | 3% (0.3 * 0.10)            |
| 2 sources                    | 0.6          | 6% (0.6 * 0.10)            |
| 3+ sources                   | 1.0          | 10% (1.0 * 0.10)           |

**Example**:
```python
# Scenario 1: 3 documents but only 1 is high-quality
documents = [
    {"similarity": 0.82},  # High quality ✓
    {"similarity": 0.68},  # Low quality ✗
    {"similarity": 0.71},  # Low quality ✗
]
source_boost = 0.3  # Only 3% boost (1 high-quality source)

# Scenario 2: 2 high-quality sources
documents = [
    {"similarity": 0.89},  # High quality ✓
    {"similarity": 0.81},  # High quality ✓
]
source_boost = 0.6  # 6% boost

# Scenario 3: 3+ high-quality sources
documents = [
    {"similarity": 0.92},  # High quality ✓
    {"similarity": 0.85},  # High quality ✓
    {"similarity": 0.78},  # High quality ✓
]
source_boost = 1.0  # Full 10% boost
```

**Rationale**:
- **Quality over quantity**: 3 mediocre docs (0.70) don't help confidence
- **Consensus matters**: Multiple high-quality sources = stronger signal
- **Boost, not primary**: This enhances confidence but doesn't drive it

---

## Factor 3: Length Boost (10% Weight - BOOST)

**What it measures**: Whether the response is sufficiently complete (not too short)

**Why a Boost**: Ensures the response has enough detail, but doesn't penalize concise answers. A 200-char response can be perfect for simple queries.

**Calculation**:
```python
# Get response length in characters
response_length = len(state.get("response", ""))

# Two-tier boost system
if response_length >= 200:
    length_boost = 1.0  # Full 10% boost (sufficient detail)
elif response_length >= 100:
    length_boost = 0.5  # 5% boost (moderate detail)
else:
    length_boost = 0.0  # No boost (too short)

# Apply 10% weight
confidence += length_boost * 0.10
```

**Scoring Table**:
| Response Length | Length Boost | Contribution to Confidence |
|-----------------|--------------|----------------------------|
| 0-99 characters | 0.0          | 0%                         |
| 100-199 chars   | 0.5          | 5% (0.5 * 0.10)            |
| 200+ characters | 1.0          | 10% (1.0 * 0.10)           |

**Example**:
```python
# Scenario 1: Too short (80 chars)
response_length = 80
length_boost = 0.0
contribution = 0.0 * 0.10 = 0.00  # No boost

# Scenario 2: Moderate (150 chars)
response_length = 150
length_boost = 0.5
contribution = 0.5 * 0.10 = 0.05  # 5% boost

# Scenario 3: Sufficient (250 chars)
response_length = 250
length_boost = 1.0
contribution = 1.0 * 0.10 = 0.10  # Full 10% boost

# Scenario 4: Very long (1500 chars)
response_length = 1500
length_boost = 1.0
contribution = 1.0 * 0.10 = 0.10  # Still 10% (no extra benefit)
```

**Rationale**:
- **Short responses** (<100 chars): May be incomplete
- **Moderate responses** (100-199 chars): Acceptable for simple queries
- **Sufficient responses** (200+ chars): Likely complete
- **No penalty for conciseness**: Long ≠ better, avoiding gaming the metric

---

## Complete Confidence Calculation Example

Let's calculate confidence for a real-world scenario:

### Scenario: User asks "What are payment processing fees?"

**Retrieved Context Documents**:
```python
context_docs = [
    {"content": "Payment fees are 2.9% + $0.30...", "similarity": 0.89},
    {"content": "ACH transfers cost $0.50...", "similarity": 0.82},
    {"content": "International fees vary...", "similarity": 0.76},
]
```

**Generated Response**:
```
"Payment processing fees typically include credit card fees of 2.9% + $0.30 per
transaction, ACH transfer fees of $0.50 per transaction, and international
processing fees which vary by country and payment method. For detailed pricing,
please refer to our fee schedule documentation."
```
(Length: 280 characters)

**Confidence Calculation (NEW MODEL)**:

1. **Factor 1: Similarity Score (80% - PRIMARY)**
   ```python
   # Weighted average favoring top results
   similarities = [0.89, 0.82, 0.76]
   similarity_score = (0.89 * 0.6) + (0.82 * 0.3) + (0.76 * 0.1)
   similarity_score = 0.534 + 0.246 + 0.076 = 0.856

   # Apply 80% weight
   similarity_contribution = 0.856 * 0.80 = 0.685  # 68.5%
   ```

2. **Factor 2: Source Boost (10% - BOOST)**
   ```python
   # Count high-quality sources (similarity > 0.75)
   high_quality_sources = [0.89, 0.82, 0.76]  # All 3 qualify!
   source_boost = 1.0  # Full boost (3+ high-quality sources)

   # Apply 10% weight
   source_contribution = 1.0 * 0.10 = 0.10  # 10%
   ```

3. **Factor 3: Length Boost (10% - BOOST)**
   ```python
   response_length = 280
   # >= 200 chars → full boost
   length_boost = 1.0

   # Apply 10% weight
   length_contribution = 1.0 * 0.10 = 0.10  # 10%
   ```

**Total Confidence**:
```python
confidence = 0.685 + 0.10 + 0.10 = 0.885 (88.5%)
```

**Result**: **Confidence = 0.885 (88.5%)**

**Analysis**:
- **Old Model** would have given ~0.78 (78%)
- **New Model** gives 0.885 (88.5%) - **10% higher!**
- Why? Strong retrieval quality (0.89 best match) now properly weighted at 80%
- All 3 sources are high-quality (>0.75), earning full 10% boost
- Response length sufficient for full 10% boost

---

## Decision Logic: Escalate or Respond?

**File**: `app/agents/nodes.py:565` - `decision_node()`

After calculating confidence, the agent decides whether to respond or escalate:

```python
# Load threshold from database configuration
agent_config = await get_active_config()
threshold = agent_config.config.confidence_thresholds.escalation
# Default: 0.95 (95%)

# Decision
if confidence >= threshold:
    # HIGH CONFIDENCE: Return response to user
    return {
        "escalated": False,
        "escalation_reason": None
    }
else:
    # LOW CONFIDENCE: Escalate to human support
    return {
        "escalated": True,
        "escalation_reason": f"Confidence score ({confidence:.2f}) below threshold ({threshold:.2f})"
    }
```

**Using Our Example**:
```python
confidence = 0.781  # 78.1%
threshold = 0.95    # 95% (default)

# Decision
0.781 < 0.95  # True

# Result: ESCALATED to human support
# Reason: "Confidence score (0.78) below threshold (0.95)"
```

---

## Confidence Score Interpretation

### Score Ranges and Meanings

| Confidence Score | Interpretation | Typical Action |
|------------------|----------------|----------------|
| **0.95 - 1.00**  | Excellent - High quality context, multiple sources, detailed response | ✅ Return to user |
| **0.85 - 0.94**  | Good - Relevant context, adequate sources, reasonable detail | ⚠️ Escalate (below default threshold) |
| **0.70 - 0.84**  | Fair - Some relevant context, limited sources, basic response | ⚠️ Escalate |
| **0.50 - 0.69**  | Poor - Weak context, few sources, short response | ⚠️ Escalate |
| **0.00 - 0.49**  | Very Poor - No relevant context, no sources, minimal response | ⚠️ Escalate |

### What Confidence Score Means

**High Confidence (≥0.95)** indicates:
- ✅ Strong KB document matches (high similarity)
- ✅ Multiple supporting sources (3+ documents)
- ✅ Comprehensive response (500+ characters)
- ✅ Agent is confident the answer is accurate

**Low Confidence (<0.95)** indicates:
- ❌ Weak KB document matches (low similarity)
- ❌ Few supporting sources (1-2 documents)
- ❌ Brief response (short length)
- ❌ Agent is uncertain about answer accuracy

---

## How to Improve Confidence Scores

### 1. Improve KB Content Quality

**Action**: Add more relevant, high-quality documents to knowledge base

**Impact**:
- ✅ Increases context quality (Factor 1: 40%)
- ✅ Increases number of sources (Factor 2: 30%)

**Example**:
- Before: 1 document with 0.70 similarity
- After: 3 documents with 0.85+ similarity
- Confidence boost: ~+0.30 (30%)

### 2. Optimize Query Analysis

**Action**: Improve query understanding and search parameters

**Impact**:
- ✅ Better document retrieval
- ✅ Higher similarity scores
- ✅ More relevant sources

**Location**: `app/agents/nodes.py:274` - `retrieve_context_node()`

### 3. Adjust Similarity Threshold

**Action**: Lower `match_threshold` in search settings

**Impact**:
- ✅ More documents retrieved (increases source count)
- ⚠️ May include less relevant documents (decreases avg similarity)

**Trade-off**: Balance recall vs. precision

### 4. Adjust Confidence Threshold

**Action**: Lower escalation threshold from 0.95 to 0.85

**Impact**:
- ✅ More queries answered by agent
- ⚠️ Slightly higher risk of incorrect answers

**Configuration**: Database `agent_configurations.confidence_thresholds.escalation`

---

## Configuration

### Database Configuration

**Table**: `agent_configurations`

```json
{
  "confidence_thresholds": {
    "escalation": 0.95,
    "high_quality": 0.90,
    "acceptable": 0.75
  }
}
```

### Environment Variables (Fallback)

**File**: `.env`

```bash
# Confidence threshold for escalation (default: 0.95)
AGENT_CONFIDENCE_THRESHOLD=0.95
```

---

## Monitoring Confidence Scores

### LangFuse Integration

All confidence scores are tracked in LangFuse for analysis:

```python
# Automatically logged for each chat interaction
{
  "session_id": "abc-123",
  "confidence_score": 0.781,
  "escalated": true,
  "escalation_reason": "Confidence score (0.78) below threshold (0.95)"
}
```

**Use LangFuse to**:
- 📊 Track average confidence over time
- 📉 Identify low-confidence query patterns
- 📈 Measure KB content improvements
- 🎯 Optimize threshold settings

---

## Limitations of Current Approach

### What Confidence Score Does NOT Measure

❌ **Factual Accuracy**: Score doesn't verify if answer is actually correct
❌ **Hallucinations**: High confidence doesn't mean no hallucinations
❌ **Context Understanding**: Doesn't check if agent understood context correctly
❌ **User Satisfaction**: Doesn't predict if user will be satisfied

### Current Approach is Heuristic-Based

The confidence calculation uses **proxy metrics**:
- Document similarity ≈ relevance (not guaranteed)
- Multiple sources ≈ consensus (not verified)
- Response length ≈ completeness (not validated)

### Future Improvements

**Potential Enhancements**:
1. **LLM-based confidence**: Ask LLM to self-assess answer quality
2. **Fact verification**: Cross-reference answers with KB
3. **Uncertainty detection**: Identify hedging language ("maybe", "possibly")
4. **User feedback loop**: Adjust confidence based on user ratings
5. **Cross-encoder scoring**: Use reranking model for better relevance

---

## Summary

**How Confidence is Calculated**:
```
Confidence Score =
    (Average Similarity * 0.4) +     // Context quality (40%)
    (Source Count / 3.0 * 0.3) +     // Number of sources (30%)
    (Response Length / 500 * 0.3)    // Response detail (30%)
```

**Decision Logic**:
```
IF confidence >= 0.95:
    Return response to user
ELSE:
    Escalate to human support
```

**Key Factors**:
- **Context Quality** (40%): How relevant are KB documents?
- **Source Count** (30%): How many documents support the answer?
- **Response Length** (30%): Is the response sufficiently detailed?

**Default Threshold**: 0.95 (95% confidence required to answer)

**Configuration**: Database-driven via `agent_configurations` table

**Monitoring**: LangFuse tracks all confidence scores for analysis
