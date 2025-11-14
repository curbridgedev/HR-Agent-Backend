# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Compaytence AI Agent Backend** - Finance/Payment Q&A system with RAG capabilities using FastAPI, LangGraph, and OpenAI. This is the **backend repository only**; a separate frontend repository exists for Next.js.

**Core Technology:**
- **Package Manager:** uv (10-100x faster than pip)
- **Framework:** FastAPI with full async/await and Pydantic v2
- **Agent:** LangGraph state machine with confidence-based routing (95% threshold)
- **Database:** Supabase (PostgreSQL + pgvector for vector search)
- **Background Jobs:** Inngest for workflow orchestration
- **Observability:** LangFuse for agent tracing
- **Document Processing:** Docling for structure-preserving extraction
- **Deployment:** Railway with branch-based environments

## Essential Commands

### Setup & Dependencies
```bash
# Install dependencies (creates .venv automatically)
uv sync

# Add new dependency
uv add package-name              # Production
uv add --dev package-name        # Development

# Remove dependency
uv remove package-name
```

### Running the Application
```bash
# Development server with hot reload
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Access points
# - API: http://localhost:8000
# - Swagger docs: http://localhost:8000/docs
# - Health check: http://localhost:8000/health
```

### Testing & Quality
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test markers
uv run pytest -m unit
uv run pytest -m integration

# Code formatting
uv run black app/ tests/

# Linting
uv run ruff check app/ tests/
uv run ruff check --fix app/ tests/    # Auto-fix

# Type checking
uv run mypy app/
```

### OpenAPI Schema Generation
```bash
# Generate OpenAPI spec for frontend consumption
uv run python -c "from app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > openapi.json
```

## Development Best Practices

### Always Use Context7 MCP for Documentation

**CRITICAL:** Before implementing any library, framework, or tool feature, ALWAYS use the Context7 MCP to fetch official documentation.

**Why Context7:**
- Provides latest official documentation
- Ensures correct API usage and patterns
- Prevents outdated or incorrect implementations
- Gives version-specific guidance

**Workflow:**
```bash
# 1. Resolve library ID
Use mcp__context7__resolve-library-id with library name

# 2. Get documentation
Use mcp__context7__get-library-docs with:
- context7CompatibleLibraryID (from step 1)
- topic (specific feature you're implementing)
- tokens (amount of documentation needed)

# 3. Implement based on official docs
```

**Examples:**

```python
# ❌ BAD: Implementing without checking docs
# May use outdated patterns or incorrect APIs

# ✅ GOOD: Use Context7 first
# 1. Resolve: mcp__context7__resolve-library-id("langgraph")
# 2. Get docs: mcp__context7__get-library-docs("/langchain-ai/langgraph", topic="state management")
# 3. Implement using official patterns from docs
```

**When to Use:**
- Adding new dependencies (FastAPI features, LangGraph patterns, Supabase methods)
- Implementing library-specific features (OpenAI streaming, Inngest workflows)
- Debugging library behavior (check if our usage matches docs)
- Updating to new library versions (check for breaking changes)

### Always Test Your Implementations

**CRITICAL:** After implementing any feature, ALWAYS test it yourself before considering it complete.

**Testing Requirements:**

1. **Unit Tests** - Test individual functions
   ```bash
   # Write test in tests/ directory
   # Run with: uv run pytest tests/test_myfeature.py -v
   ```

2. **Integration Tests** - Test API endpoints
   ```bash
   # Test with curl or httpx
   curl -X POST "http://localhost:8000/api/v1/endpoint" \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'
   ```

3. **Manual Testing** - Verify behavior
   ```bash
   # Start server
   uv run uvicorn app.main:app --reload

   # Visit Swagger docs: http://localhost:8000/docs
   # Test endpoints interactively
   ```

**Testing Checklist:**
- [ ] Code runs without syntax errors
- [ ] Imports resolve correctly
- [ ] Type hints pass mypy check: `uv run mypy app/`
- [ ] Linting passes: `uv run ruff check app/`
- [ ] Function produces expected output
- [ ] Error cases handled gracefully
- [ ] API endpoint returns correct status codes
- [ ] Response schema matches Pydantic models

**Test Before Marking Complete:**
```bash
# Quick validation workflow
uv run black app/ tests/              # Format
uv run ruff check --fix app/ tests/   # Lint
uv run mypy app/                      # Type check
uv run pytest tests/test_feature.py   # Unit tests
curl http://localhost:8000/api/v1/endpoint  # Integration test
```

**When Tests Fail:**
- Read error messages carefully
- Check Context7 docs for correct usage
- Verify environment variables are set
- Check logs: structured logging in development shows detailed errors
- Test incrementally: break down into smaller testable pieces

## Architecture & Key Concepts

### Environment Configuration Philosophy
**Critical:** Zero code changes between Dev/UAT/Prod environments. All environment-specific settings live in `.env` files.

- Configuration: `app/core/config.py` (Pydantic Settings)
- Single source of truth: `.env` file per environment
- Validation at startup: Application fails fast on missing/invalid config
- Three environment modes: `development`, `uat`, `production`

```python
# Access settings anywhere
from app.core.config import settings
settings.openai_api_key  # Type-safe access
settings.is_production   # Helper properties
```

### Async-First Architecture
**All operations must be async** - frontend-backend communication is non-blocking.

**Backend:**
- All route handlers: `async def`
- Database calls: `await supabase.table(...)`
- LLM calls: `await agent_graph.ainvoke(...)`
- Long operations (>5s): Background job with Inngest

**Response Patterns:**
- Quick APIs (<500ms): Direct async response
- Medium APIs (500ms-5s): Async with loading state
- Long operations (>5s): Background job + job ID + polling endpoint
- Streaming: Server-Sent Events (SSE) for agent responses

### Agent Architecture (LangGraph)
The agent uses LangGraph state machine for decision-making:

1. **Query Analysis** → Determine intent and required tools
2. **RAG Retrieval** → Vector search in Supabase (hybrid: vector + keyword)
3. **Confidence Scoring** → Calculate response confidence (0-1 scale)
4. **Decision Node:**
   - If confidence ≥ 0.95 → Generate response
   - If confidence < 0.95 → Escalate to human
5. **Response Generation** → Stream response via SSE

**Key Files (to be implemented):**
- `app/agents/graph.py` - LangGraph state machine definition
- `app/agents/nodes.py` - Individual agent nodes (retrieval, scoring, generation)
- `app/agents/tools.py` - Agent tools (vector search, API calls)

### Document Processing Pipeline (Docling)
Structure-preserving extraction for finance documents with tables:

1. **Upload** → File validation and virus scanning
2. **Docling Processing** → Extract tables, headings, lists with structure
3. **Markdown/JSON Conversion** → Structured output with metadata
4. **Structure-Aware Chunking** → Respect document semantics (tables stay intact)
5. **Embedding Generation** → OpenAI text-embedding-3-small
6. **Vector Storage** → Supabase with structural metadata

### API Layer Structure
**Pattern:** Models → Services → API Endpoints

1. **Models** (`app/models/`): Pydantic v2 models for request/response
   - Inherit from `BaseRequest` or `BaseResponse`
   - Full type hints required
   - Validation happens automatically

2. **Services** (`app/services/`): Business logic layer
   - All async functions
   - No direct FastAPI dependencies
   - Returns Pydantic models

3. **API Endpoints** (`app/api/v1/`): FastAPI routers
   - Thin layer, delegates to services
   - Uses dependency injection for auth, DB connections
   - Registers in `app/api/v1/__init__.py`

**Example:**
```python
# app/models/chat.py
class ChatRequest(BaseRequest):
    message: str
    session_id: str

# app/services/chat.py
async def process_chat(request: ChatRequest) -> ChatResponse:
    # Business logic
    pass

# app/api/v1/chat.py
@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await process_chat(request)
```

### Background Jobs (Inngest)
Use Inngest for operations >5s:

- Historical data ingestion (Slack, WhatsApp, Telegram via Telethon)
- Document processing pipelines
- Embedding generation for large batches
- Periodic cleanup and maintenance tasks

**Pattern:**
```python
# Trigger job from API
job_id = await inngest_client.send({
    "name": "source.connected",
    "data": source.dict()
})
return JobResponse(job_id=job_id, status="started")

# Define job handler
@inngest_client.create_function(
    fn_id="ingest-slack-history",
    trigger=inngest.TriggerEvent(event="source.connected")
)
async def ingest_slack_history(ctx, step):
    # Long-running ingestion logic
    pass
```

### Observability (LangFuse)
All agent interactions automatically traced:

- Request/response pairs
- Token usage and costs
- Latency metrics
- Confidence scores
- Tool/function calls
- Error tracking

Environment-specific sampling:
- Development: 100% (trace everything)
- UAT: 50% (trace half)
- Production: 10% (cost optimization)

### Semantic Caching Strategy
40-60% cost reduction through intelligent caching:

1. **Vector Similarity Cache** → Cache similar queries (≥0.98 similarity)
2. **Confidence Threshold** → Skip LLM for high-confidence cached answers
3. **TTL Management** → 1-hour cache expiry (configurable)
4. **Cost Tracking** → Monitor cache hit rates in LangFuse

## Development Workflow

### Adding a New API Endpoint

1. **Define Pydantic models** in `app/models/[domain].py`
2. **Implement service logic** in `app/services/[domain].py`
3. **Create API router** in `app/api/v1/[domain].py`
4. **Register router** in `app/api/v1/__init__.py`:
   ```python
   from app.api.v1 import chat
   api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
   ```
5. **Write tests** in `tests/api/v1/test_[domain].py`
6. **Generate OpenAPI schema** for frontend

### Working with Environment Variables

1. **Add to `.env.example`** with documentation
2. **Add to `app/core/config.py`** with type and validation:
   ```python
   new_config: str = Field(..., description="Description")
   ```
3. **Use in code:**
   ```python
   from app.core.config import settings
   value = settings.new_config
   ```

### Branch Strategy & Deployment

- `dev` → Dev environment (Railway auto-deploys)
- `staging` → UAT environment (Railway auto-deploys)
- `main` → Production environment (Railway auto-deploys)

Each branch has its own `.env` configuration on Railway.

## Project Structure

```
app/
├── api/v1/          # API endpoints (routers)
├── agents/          # LangGraph agent logic
├── core/            # Config, logging, security
├── db/              # Database utilities (Supabase client)
├── models/          # Pydantic models
├── services/        # Business logic
└── utils/           # Helper utilities

tests/               # Test suite (mirrors app/ structure)
```

## Important Technical Constraints

1. **Always use Context7 MCP for library documentation** (mandatory before implementing any library feature)
2. **Always test implementations yourself** (run tests and verify functionality before marking complete)
3. **All functions must have type hints** (enforced by mypy strict mode)
4. **All API operations must be async** (no blocking calls)
5. **All secrets in environment variables** (never hardcode)
6. **Agent confidence threshold is 95%** (business requirement)
7. **OpenAPI schema must be kept up-to-date** (frontend dependency)
8. **Structured logging in production** (key=value format)
9. **CORS origins must be explicitly whitelisted** (security)

## Reference Documentation

- **Technical Spec:** `Compaytence Technical Specification.md` (architecture details)
- **Project Overview:** `Compaytence Project Breakdown_ AI Agent.md` (functional requirements)
- **Cost Analysis:** `Compaytence Cost Breakdown.md` (budget and optimization)
- **README:** Comprehensive setup and deployment guide
