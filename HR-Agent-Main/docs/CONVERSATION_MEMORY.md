# Conversation Memory Implementation

## Overview

This document describes the conversation memory system that enables the Compaytence AI Agent to maintain context across multi-turn conversations.

## Architecture

### Database Schema

The conversation memory uses two PostgreSQL tables:

1. **`chat_sessions`** - Session metadata
   - `session_id` (TEXT, UNIQUE) - Unique identifier for the conversation
   - `user_id` (TEXT) - Optional user identifier
   - `title` (TEXT) - First user message (truncated, for UI)
   - `last_message` (TEXT) - Most recent message (truncated, for UI)
   - `message_count` (INTEGER) - Total messages in session
   - `active` (BOOLEAN) - Whether session is active
   - `created_at` / `updated_at` (TIMESTAMPTZ)

2. **`chat_messages`** - Individual messages
   - `id` (UUID) - Primary key
   - `session_id` (TEXT) - Foreign key to `chat_sessions`
   - `role` (TEXT) - Message role: `user`, `assistant`, or `system`
   - `content` (TEXT) - Message content
   - `confidence` (FLOAT) - Agent confidence score (for assistant messages)
   - `escalated` (BOOLEAN) - Whether query was escalated
   - `metadata` (JSONB) - Additional metadata (tokens, response time, etc.)
   - `created_at` (TIMESTAMPTZ)

### State Flow

```
1. User sends message → ChatRequest(message, session_id)
2. Backend retrieves conversation history from DB
3. Conversation history added to AgentState
4. LangGraph agent processes with full context
5. Agent generates response with conversation awareness
6. Both user message and assistant response saved to DB
7. Session metadata updated (title, last_message, message_count)
```

## Implementation Details

### 1. AgentState Extension

**File:** `app/agents/state.py`

Added `conversation_history` field to maintain previous messages:

```python
class AgentState(TypedDict):
    query: str
    session_id: str
    user_id: str | None
    conversation_history: list[dict[str, Any]]  # NEW: Previous messages
    # ... other fields
```

### 2. Configuration Settings

**File:** `app/core/config.py`

Added three configuration parameters:

```python
# Conversation Memory Configuration
conversation_history_enabled: bool = True
conversation_history_max_messages: int = 20  # Max messages to include
conversation_history_max_tokens: int = 4000  # Token limit for history
```

**Environment Variables:**
- `CONVERSATION_HISTORY_ENABLED` - Enable/disable conversation memory
- `CONVERSATION_HISTORY_MAX_MESSAGES` - Maximum messages to retrieve
- `CONVERSATION_HISTORY_MAX_TOKENS` - Approximate token budget for history

### 3. History Retrieval Function

**File:** `app/services/chat.py`

Created `get_conversation_history_for_agent()`:

**Features:**
- Retrieves messages from database in chronological order
- Filters to only user/assistant messages (excludes system)
- Implements **sliding window** based on token limits
- Processes newest messages first to fit within token budget
- Estimates tokens: ~4 characters per token (English)

**Example:**
```python
history = await get_conversation_history_for_agent(
    session_id="session-123",
    max_messages=20,
    max_tokens=4000,
)
# Returns: [{"role": "user", "content": "..."},
#           {"role": "assistant", "content": "..."}]
```

### 4. Chat Service Integration

**File:** `app/services/chat.py`

Updated `process_chat()` and `process_chat_stream()`:

```python
# Retrieve conversation history before agent invocation
conversation_history = await get_conversation_history_for_agent(
    request.session_id
)

# Pass to agent in initial state
initial_state = {
    "query": request.message,
    "session_id": request.session_id,
    "conversation_history": conversation_history,  # NEW
    # ... other fields
}
```

### 5. LLM Prompt Integration

**File:** `app/agents/nodes.py`

Updated `generate_response_node()` to include conversation history in LLM context:

**Formatting:**
```python
# Format conversation history
conversation_lines = []
for msg in conversation_history:
    role_label = "User" if msg["role"] == "user" else "Assistant"
    conversation_lines.append(f"{role_label}: {msg['content']}")
conversation_context = "\n".join(conversation_lines)
```

**Prompt Structure:**
```
Conversation History:
User: What is your refund policy?
Assistant: Our refund policy allows returns within 30 days.

Knowledge Base Context:
[Retrieved documents from vector search]

Current User Question: How long does it take?
```

## Usage Examples

### Example 1: Basic Follow-up

```
User: "What is your refund policy?"
→ Agent searches vector store
→ Response: "Our refund policy allows returns within 30 days..."

User: "How long does the process take?"
→ Agent receives conversation history
→ Understands "the process" refers to refunds
→ Response: "Refund processing typically takes 5-7 business days..."
```

### Example 2: Pronoun Resolution

```
User: "Tell me about your shipping options"
→ Response: "We offer standard (5-7 days) and express (1-2 days) shipping..."

User: "Which one is cheaper?"
→ Agent uses conversation history
→ Understands "one" refers to shipping options
→ Response: "Standard shipping is cheaper at $5.99 vs express at $15.99..."
```

### Example 3: Context Maintenance

```
User: "What payment methods do you accept?"
→ Response: "We accept Visa, Mastercard, PayPal, and Apple Pay..."

User: "Are there any fees?"
→ Agent maintains payment context
→ Response: "There are no additional fees for credit cards or PayPal..."

User: "What about international cards?"
→ Agent still maintains payment context
→ Response: "International cards are accepted with a 2.5% foreign transaction fee..."
```

## Token Management

### Sliding Window Algorithm

The system implements a **token-based sliding window** to prevent context overflow:

1. **Retrieve** most recent N messages from database
2. **Estimate** tokens for each message (chars ÷ 4)
3. **Process** messages in reverse (newest first)
4. **Accumulate** until token limit reached
5. **Return** messages that fit within budget

**Example with 500-token limit:**
```
Messages in DB: 10 messages (chronological order)
Token limit: 500 tokens

Processing (newest first):
- Message 10: 180 tokens → Total: 180 ✓ Include
- Message 9:  150 tokens → Total: 330 ✓ Include
- Message 8:  200 tokens → Total: 530 ✗ Exceeds limit, stop

Result: Include messages 9 and 10 only
```

### Default Limits

- **Max Messages:** 20 (configurable via `CONVERSATION_HISTORY_MAX_MESSAGES`)
- **Max Tokens:** 4000 (configurable via `CONVERSATION_HISTORY_MAX_TOKENS`)

**Token Budget Breakdown:**
- Total GPT-4 context: 8,192 tokens
- System prompt: ~200 tokens
- Retrieved documents: ~1,500 tokens
- Conversation history: ~4,000 tokens
- User query: ~100 tokens
- Response buffer: ~2,392 tokens

## Performance Considerations

### Database Queries

Each chat request executes:
1. **SELECT** from `chat_messages` (1 query)
   - Indexed by `session_id` for fast retrieval
   - Limited to max_messages (default: 20)
   - Query time: <10ms

### Memory Overhead

- **Per message:** ~100-500 bytes (JSON format)
- **20 messages:** ~2-10 KB in memory
- **Negligible impact** on response time

### Cost Optimization

Conversation history increases token usage:
- **Without history:** ~2,000 tokens/request
- **With history:** ~4,000-6,000 tokens/request
- **Cost impact:** +50-100% per request

**Mitigation strategies:**
1. Token-based sliding window (implemented)
2. Configurable limits per environment
3. Disable for simple queries (future: query analysis)

## Configuration

### Development Environment

```env
CONVERSATION_HISTORY_ENABLED=true
CONVERSATION_HISTORY_MAX_MESSAGES=20
CONVERSATION_HISTORY_MAX_TOKENS=4000
```

### Production Environment

Recommended production settings:

```env
CONVERSATION_HISTORY_ENABLED=true
CONVERSATION_HISTORY_MAX_MESSAGES=10  # Reduce for cost
CONVERSATION_HISTORY_MAX_TOKENS=2000  # Tighter limit
```

### Disable Conversation Memory

To disable (fallback to stateless mode):

```env
CONVERSATION_HISTORY_ENABLED=false
```

## Testing

### Unit Tests

**File:** `scripts/test_conversation_memory_simple.py`

Tests:
- Configuration values accessible
- Conversation formatting logic
- Token limit sliding window algorithm

**Run:**
```bash
uv run python scripts/test_conversation_memory_simple.py
```

### Integration Tests

**File:** `scripts/test_conversation_memory.py`

Tests:
- Multi-turn conversations with real DB
- Token limit enforcement
- Message persistence and retrieval

**Run:**
```bash
uv run python scripts/test_conversation_memory.py
```

**Note:** Requires valid `.env` with database credentials.

## API Endpoints

### Chat with History

**POST** `/api/v1/chat`

```json
{
  "message": "How long does it take?",
  "session_id": "session-123",
  "user_id": "user-456"
}
```

**Behavior:**
- Automatically retrieves conversation history for `session-123`
- Includes previous messages in LLM context
- Saves both user message and assistant response

### Retrieve History

**GET** `/api/v1/chat/history/{session_id}?limit=50`

**Response:**
```json
{
  "session_id": "session-123",
  "messages": [
    {
      "role": "user",
      "content": "What is your refund policy?",
      "timestamp": "2024-01-15T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Our refund policy...",
      "confidence": 0.92,
      "timestamp": "2024-01-15T10:00:01Z"
    }
  ],
  "count": 2
}
```

## Future Enhancements

### 1. Semantic Summarization

For very long conversations (>20 messages), implement:
- Conversation summarization using LLM
- Store summary instead of full history
- Reduces token usage for long sessions

### 2. Selective History

Intelligent selection based on:
- Semantic relevance to current query
- Recency and importance scoring
- Query type (simple vs complex)

### 3. Multi-Session Context

Link related sessions:
- Same user across devices
- Topic-based session grouping
- Cross-session knowledge transfer

### 4. Memory Pruning

Automatic cleanup:
- Remove irrelevant exchanges
- Compress repetitive content
- Archive old sessions

## Troubleshooting

### Issue: Agent not using conversation context

**Symptoms:**
- Agent treats each message independently
- No reference to previous questions

**Solutions:**
1. Check `CONVERSATION_HISTORY_ENABLED=true` in `.env`
2. Verify messages are being saved: `SELECT * FROM chat_messages WHERE session_id = '...'`
3. Check logs for "Retrieved X conversation messages"
4. Ensure `session_id` is consistent across requests

### Issue: Token limit errors

**Symptoms:**
- `400 Bad Request` from OpenAI
- Error: "This model's maximum context length is..."

**Solutions:**
1. Reduce `CONVERSATION_HISTORY_MAX_TOKENS` (e.g., 2000)
2. Reduce `CONVERSATION_HISTORY_MAX_MESSAGES` (e.g., 10)
3. Check retrieved document count (may be too high)

### Issue: Slow response times

**Symptoms:**
- Response time >5s
- Increased database load

**Solutions:**
1. Verify `idx_chat_messages_session_id` index exists
2. Reduce `CONVERSATION_HISTORY_MAX_MESSAGES`
3. Check database query performance: `EXPLAIN ANALYZE SELECT ...`

## Monitoring

### Key Metrics

Track via LangFuse or application logs:

1. **Conversation History Size**
   - Avg messages per request
   - Avg tokens in history
   - Distribution of history sizes

2. **Token Usage**
   - Total tokens per request
   - Breakdown: system + history + retrieval + response
   - Cost per request with history

3. **Response Quality**
   - Confidence scores with vs without history
   - Escalation rate comparison
   - User satisfaction (if available)

### Logging

Example log output:
```
INFO: Retrieved 4 conversation messages for agent (~850 tokens) from session abc-123
DEBUG: Including 4 previous messages in context
INFO: Response generated: 250 chars, 1200 tokens
```

## Summary

The conversation memory system enables **true multi-turn conversations** by:

✅ **Storing** all messages in PostgreSQL with session grouping
✅ **Retrieving** relevant history with token-based sliding window
✅ **Passing** conversation context to LangGraph agent
✅ **Formatting** history for LLM prompt injection
✅ **Managing** token limits to prevent context overflow
✅ **Configuring** behavior via environment variables

This allows the agent to:
- Answer follow-up questions naturally
- Resolve pronouns and references
- Maintain topic context across turns
- Provide more relevant responses

**Trade-offs:**
- ⬆️ Token usage (50-100% increase)
- ⬆️ Cost per request
- ⬆️ Context window usage
- ⬆️ Database queries (+1 per request)
