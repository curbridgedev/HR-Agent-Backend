# Knowledge Base Context Flow - How KB Context is Passed to the Agent

This document explains the complete flow of how knowledge base (KB) context is retrieved and passed to the AI agent in the Compaytence backend.

---

## Overview

The system uses a **RAG (Retrieval-Augmented Generation)** architecture powered by **LangGraph**, **Supabase pgvector**, and **OpenAI embeddings**.

**High-Level Flow**:
```
User Query → Agent Graph → Retrieve Context (RAG) → Generate Response → Return to User
```

---

## Detailed Flow

### 1. **Chat Request Entry Point**

**File**: `app/api/v1/chat.py` → `app/services/chat.py`

When a user sends a chat message:

```python
# User sends POST /api/v1/chat
{
  "message": "What are payment processing fees?",
  "session_id": "abc-123",
  "user_id": "user-456"
}
```

The request flows to `process_chat()` in `app/services/chat.py:21`:

```python
async def process_chat(request: ChatRequest) -> ChatResponse:
    # Prepare initial state for agent
    initial_state = {
        "query": request.message,
        "session_id": request.session_id,
        "user_id": request.user_id,
        "context_documents": [],  # Will be populated by RAG
        "context_text": "",       # Will be populated by RAG
        "confidence_score": 0.0,
        "response": "",
        # ... other fields
    }

    # Invoke LangGraph agent
    final_state = await agent_graph.ainvoke(initial_state)
```

---

### 2. **LangGraph Agent Workflow**

**File**: `app/agents/graph.py`

The agent follows a state machine with conditional routing:

```
1. analyze_query
       ↓
2. route_decision (conditional)
       ↓
   ┌──────────────┬──────────────────┬─────────────────┐
   ↓              ↓                  ↓                 ↓
invoke_tools   retrieve_context   direct_response   escalation
   ↓              ↓                  ↓                 ↓
   └──────────────┴──────────────────┴─────────────────┘
                         ↓
              3. generate_response
                         ↓
              4. calculate_confidence
                         ↓
              5. decision (check confidence)
                         ↓
              6. format_output
                         ↓
                       END
```

**For standard RAG queries** (most common), the flow goes:
```
analyze_query → retrieve_context → generate_response → calculate_confidence → decision → format_output
```

---

### 3. **Context Retrieval (RAG Core)**

**File**: `app/agents/nodes.py:274` - `retrieve_context_node()`

This is where the **KB context is retrieved**:

#### Step 3.1: Load Search Configuration

```python
# Load agent config from database (dynamic settings)
agent_config = await get_active_config()
search_settings = agent_config.config.search_settings

# Settings include:
# - similarity_threshold: 0.7 (how similar documents must be)
# - max_results: 5 (number of documents to retrieve)
# - use_hybrid_search: true (combine vector + keyword search)
```

#### Step 3.2: Generate Query Embedding

```python
# Convert user query to vector using OpenAI text-embedding-3-small
query_embedding = await generate_embedding(state["query"])
# Returns: [0.123, -0.456, 0.789, ...] (1536 dimensions)
```

**File**: `app/db/embeddings.py`

The embedding is generated using OpenAI's embedding model:
```python
response = await openai_client.embeddings.create(
    input=query_text,
    model="text-embedding-3-small",
    dimensions=1536
)
```

#### Step 3.3: Hybrid Search in Supabase

**File**: `app/db/vector.py:105` - `hybrid_search()`

The system performs **hybrid search** (vector + keyword):

```python
# Call Supabase RPC function for hybrid search
response = db.rpc(
    "hybrid_search",  # PostgreSQL function
    {
        "query_embedding": query_embedding,  # Vector similarity
        "query_text": sanitized_query,       # Keyword search
        "match_threshold": 0.7,              # Similarity threshold
        "match_count": 5,                    # Max results
    }
).execute()
```

**Supabase `hybrid_search()` RPC Function** (PostgreSQL):
- Performs **vector similarity search** using `pgvector` extension
- Performs **full-text search** using PostgreSQL `tsvector`
- Combines results with weighted scoring
- Returns documents sorted by relevance

**Returns**:
```python
documents = [
  {
    "id": "doc-1",
    "content": "Payment processing fees are typically 2.9% + $0.30...",
    "source": "payments_guide.pdf",
    "similarity_score": 0.85,
    "metadata": {...}
  },
  {
    "id": "doc-2",
    "content": "For ACH transfers, the fee structure is different...",
    "source": "ach_documentation.pdf",
    "similarity_score": 0.78,
    "metadata": {...}
  },
  # ... up to 5 documents
]
```

#### Step 3.4: Format Context Text

```python
# Combine all retrieved documents into context text
context_text = "\n\n".join([
    f"Source: {doc.get('source', 'unknown')}\n{doc.get('content', '')}"
    for doc in documents
])

# Example result:
# """
# Source: payments_guide.pdf
# Payment processing fees are typically 2.9% + $0.30...
#
# Source: ach_documentation.pdf
# For ACH transfers, the fee structure is different...
# """
```

#### Step 3.5: Update Agent State

```python
return {
    "context_documents": documents,  # Full document objects with metadata
    "context_text": context_text,    # Formatted text for LLM
}
```

---

### 4. **Response Generation with Context**

**File**: `app/agents/nodes.py:371` - `generate_response_node()`

Now the retrieved KB context is passed to the LLM:

#### Step 4.1: Load System Prompt

```python
# Load from database (dynamic prompt management)
system_prompt_obj = await get_active_prompt(
    name="main_system_prompt",
    prompt_type="system"
)

system_prompt = system_prompt_obj.content
# Example: "You are a finance and payment expert assistant..."
```

#### Step 4.2: Format User Prompt with Context

**This is where the KB context is injected into the prompt**:

```python
# Load retrieval prompt template from database
retrieval_prompt_obj = await get_active_prompt(
    name="retrieval_context_prompt",
    prompt_type="retrieval"
)

# Format template with actual context and query
user_prompt = retrieval_prompt_obj.content.format(
    context=state['context_text'],  # KB CONTEXT INJECTED HERE
    query=state['query']
)
```

**Example formatted user_prompt**:
```
Context information:
Source: payments_guide.pdf
Payment processing fees are typically 2.9% + $0.30 per transaction for credit cards.
ACH transfers have different fee structures...

Source: ach_documentation.pdf
For ACH transfers, the fee structure is different. Standard ACH costs $0.50 per transaction...

User question: What are payment processing fees?

Please provide a comprehensive answer based on the context above.
```

#### Step 4.3: Call LLM with Context

```python
# Create LangChain chat model (OpenAI GPT-4)
chat_model = get_chat_model(
    provider="openai",
    model="gpt-4",
    temperature=0.7,
    max_tokens=1000,
)

# Call LLM with system prompt + context + query
response = await chat_model.ainvoke([
    SystemMessage(content=system_prompt),
    HumanMessage(content=user_prompt),  # Contains KB context!
])

generated_text = response.content
```

**What the LLM receives**:
1. **System Prompt**: "You are a finance expert..."
2. **User Prompt**:
   - **Context**: Retrieved KB documents (formatted)
   - **Query**: User's question

The LLM generates a response **grounded in the KB context**.

---

### 5. **Confidence Scoring**

**File**: `app/agents/nodes.py` - `calculate_confidence_node()`

After generation, the system scores the response quality:

```python
# Analyze response quality based on:
# - Context relevance
# - Response completeness
# - Answer clarity

confidence_score = 0.92  # Score 0-1
```

If `confidence_score >= threshold` (default 0.95), the response is returned.
If `confidence_score < threshold`, the query is escalated to human support.

---

### 6. **Response Return**

The final state flows back through the graph:

```python
{
  "query": "What are payment processing fees?",
  "response": "Payment processing fees typically include...",
  "confidence_score": 0.92,
  "sources": [
    {
      "content": "Payment processing fees are...",
      "source": "payments_guide.pdf",
      "similarity_score": 0.85
    },
    # ... more sources
  ],
  "escalated": false
}
```

This is converted to `ChatResponse` and returned to the user via the API.

---

## Complete Context Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER SENDS MESSAGE                                            │
│    POST /api/v1/chat                                             │
│    {"message": "What are payment fees?"}                         │
└───────────────────────┬─────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. CHAT SERVICE (app/services/chat.py)                          │
│    - Creates initial state                                       │
│    - Invokes LangGraph agent                                     │
└───────────────────────┬─────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. AGENT GRAPH (app/agents/graph.py)                            │
│    analyze_query → route_decision → retrieve_context            │
└───────────────────────┬─────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. RETRIEVE CONTEXT NODE (app/agents/nodes.py:274)             │
│    ┌──────────────────────────────────────────────────────┐    │
│    │ A. Load search config from database                   │    │
│    │    - similarity_threshold: 0.7                        │    │
│    │    - max_results: 5                                   │    │
│    └──────────────────┬───────────────────────────────────┘    │
│                       ↓                                          │
│    ┌──────────────────────────────────────────────────────┐    │
│    │ B. Generate query embedding (OpenAI)                  │    │
│    │    "What are payment fees?"                           │    │
│    │    → [0.123, -0.456, 0.789, ...] (1536 dims)         │    │
│    └──────────────────┬───────────────────────────────────┘    │
│                       ↓                                          │
│    ┌──────────────────────────────────────────────────────┐    │
│    │ C. Hybrid Search in Supabase (app/db/vector.py)      │    │
│    │    - Vector similarity search (pgvector)              │    │
│    │    - Keyword search (PostgreSQL FTS)                  │    │
│    │    - Combine & rank results                           │    │
│    └──────────────────┬───────────────────────────────────┘    │
│                       ↓                                          │
│    ┌──────────────────────────────────────────────────────┐    │
│    │ D. Format context text                                │    │
│    │    Source: payments_guide.pdf                         │    │
│    │    Payment fees are 2.9% + $0.30...                   │    │
│    │                                                        │    │
│    │    Source: ach_documentation.pdf                      │    │
│    │    ACH fees are $0.50 per transaction...              │    │
│    └──────────────────┬───────────────────────────────────┘    │
│                       ↓                                          │
│    Return: {context_documents, context_text}                    │
└───────────────────────┬─────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. GENERATE RESPONSE NODE (app/agents/nodes.py:371)            │
│    ┌──────────────────────────────────────────────────────┐    │
│    │ A. Load system prompt from database                   │    │
│    │    "You are a finance expert assistant..."            │    │
│    └──────────────────┬───────────────────────────────────┘    │
│                       ↓                                          │
│    ┌──────────────────────────────────────────────────────┐    │
│    │ B. Format user prompt with KB CONTEXT                 │    │
│    │    Context information:                                │    │
│    │    [KB CONTEXT INJECTED HERE]                         │    │
│    │                                                        │    │
│    │    User question: What are payment fees?              │    │
│    └──────────────────┬───────────────────────────────────┘    │
│                       ↓                                          │
│    ┌──────────────────────────────────────────────────────┐    │
│    │ C. Call OpenAI GPT-4                                  │    │
│    │    Messages: [SystemMessage, HumanMessage]            │    │
│    │    HumanMessage contains: KB context + query          │    │
│    └──────────────────┬───────────────────────────────────┘    │
│                       ↓                                          │
│    Return: {response: "Payment fees typically..."}              │
└───────────────────────┬─────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. CALCULATE CONFIDENCE                                          │
│    confidence_score: 0.92                                        │
└───────────────────────┬─────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. DECISION NODE                                                 │
│    if confidence >= 0.95: return response                        │
│    else: escalate to human                                       │
└───────────────────────┬─────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. FORMAT OUTPUT & RETURN TO USER                               │
│    {                                                             │
│      "response": "Payment fees typically include...",            │
│      "confidence": 0.92,                                         │
│      "sources": [...]                                            │
│    }                                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Files Reference

| Component | File Path | Purpose |
|-----------|-----------|---------|
| **Chat Entry** | `app/services/chat.py:21` | `process_chat()` - Main entry point |
| **Agent Graph** | `app/agents/graph.py` | LangGraph workflow definition |
| **Context Retrieval** | `app/agents/nodes.py:274` | `retrieve_context_node()` - RAG core |
| **Embedding Generation** | `app/db/embeddings.py` | OpenAI embedding creation |
| **Hybrid Search** | `app/db/vector.py:105` | `hybrid_search()` - Vector + keyword search |
| **Response Generation** | `app/agents/nodes.py:371` | `generate_response_node()` - LLM with context |
| **Agent State** | `app/agents/state.py` | Agent state schema (TypedDict) |

---

## Configuration

### Search Settings (Database-Driven)

Stored in `agent_configurations` table:

```json
{
  "search_settings": {
    "similarity_threshold": 0.7,
    "max_results": 5,
    "use_hybrid_search": true
  }
}
```

### Environment Variables

From `.env`:

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Vector Search
VECTOR_SIMILARITY_THRESHOLD=0.7
VECTOR_MAX_RESULTS=5
```

---

## Summary

**How KB Context is Passed to Agent**:

1. **User sends query** via chat API
2. **Agent analyzes query** and routes to RAG retrieval
3. **Query is embedded** using OpenAI embeddings (1536-dim vector)
4. **Hybrid search executes** in Supabase:
   - Vector similarity search (pgvector)
   - Keyword search (PostgreSQL FTS)
   - Results combined and ranked
5. **Top 5 documents retrieved** with similarity scores
6. **Context is formatted** into text with sources
7. **LLM receives**:
   - System prompt: "You are a finance expert..."
   - User prompt: **KB context + user query**
8. **LLM generates response** grounded in KB context
9. **Confidence is scored** (0-1 scale)
10. **Response returned** to user with sources

**The KB context is injected into the LLM prompt** at step 7, ensuring the agent's responses are grounded in your knowledge base documents.
