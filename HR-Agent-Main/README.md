# HR Agent - Backend

Canadian Employment Standards Q&A AI Assistant with RAG capabilities. Helps HR teams navigate provincial employment standards and internal policies. Built with FastAPI, LangGraph, and OpenAI.

## 🏗️ Architecture Overview

### Technology Stack

- **Framework**: FastAPI (Python 3.11+)
- **Agent**: LangGraph + OpenAI GPT-4
- **Database**: Supabase (PostgreSQL + pgvector)
- **Background Jobs**: Inngest
- **Observability**: LangFuse
- **Document Processing**: Docling
- **Package Manager**: uv (ultra-fast, 10-100x faster than pip)
- **Deployment**: Railway

### Key Features

- ✅ **Province-specific RAG**: Canadian employment standards (MB, ON, SK, AB, BC) + internal policies
- ✅ **Citation-based answers**: Always cite specific sections and clauses
- ✅ **Confidence-based routing**: 95% threshold for direct answers, low-confidence escalation to human
- ✅ **Streaming responses**: Server-Sent Events (SSE) for real-time answers
- ✅ **Airtable integration**: Escalation tickets and analytics tracking
- ✅ **Legal disclaimers**: "Informational only, not legal advice" guardrails
- ✅ **Document approval workflow**: Admin review for uploaded content
- ✅ **Structure-aware chunking**: Preserves tables and formatting from employment standards
- ✅ **Async-first architecture**: All operations non-blocking
- ✅ **Environment-aware config**: Zero code changes between Dev/UAT/Prod

## 📁 Project Structure

```
compaytence-backend/
├── app/
│   ├── api/
│   │   └── v1/              # API v1 endpoints
│   │       ├── chat.py      # Chat endpoints
│   │       ├── sources.py   # Source management
│   │       ├── documents.py # Document upload
│   │       ├── webhooks.py  # Platform webhooks
│   │       └── admin.py     # Admin operations
│   ├── agents/              # LangGraph agents
│   │   ├── graph.py         # Agent state machine
│   │   ├── nodes.py         # Agent nodes
│   │   └── tools.py         # Agent tools
│   ├── core/                # Core configuration
│   │   ├── config.py        # Settings management
│   │   ├── logging.py       # Logging setup
│   │   └── security.py      # Auth & security
│   ├── db/                  # Database utilities
│   │   ├── supabase.py      # Supabase client
│   │   └── vector.py        # Vector operations
│   ├── models/              # Pydantic models
│   │   ├── base.py          # Base models
│   │   ├── chat.py          # Chat models
│   │   └── documents.py     # Document models
│   ├── services/            # Business logic
│   │   ├── chat.py          # Chat service
│   │   ├── ingestion.py     # Data ingestion
│   │   ├── embedding.py     # Embedding generation
│   │   └── cache.py         # Semantic caching
│   └── utils/               # Utilities
│       ├── docling.py       # Document processing
│       └── chunking.py      # Text chunking
├── tests/                   # Test suite
├── .env.example             # Environment template
├── pyproject.toml           # Dependencies
├── railway.json             # Railway config
└── README.md                # This file
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (ultra-fast Python package manager)
- Supabase account
- OpenAI API key
- Inngest account (for background jobs)

### Installation

1. **Install uv** (if not already installed)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

2. **Clone the repository**

```bash
git clone <repository-url>
cd compaytence-backend
```

3. **Install dependencies with uv**

```bash
# Install all dependencies (production + dev)
uv sync

# Production dependencies only
uv sync --no-dev
```

> **Why uv?** uv is 10-100x faster than pip, has better dependency resolution, and automatically manages virtual environments. No need to manually create venv!

### uv Quick Reference

```bash
# Install/update dependencies
uv sync                    # Install all deps (prod + dev)
uv sync --no-dev           # Install prod deps only
uv sync --frozen           # Use exact versions from lockfile

# Add new dependencies
uv add fastapi             # Add to production deps
uv add --dev pytest        # Add to dev deps
uv add "fastapi>=0.109.0"  # Add with version constraint

# Remove dependencies
uv remove package-name     # Remove package

# Run commands in uv environment
uv run python script.py    # Run Python script
uv run uvicorn app.main:app  # Run server
uv run pytest              # Run tests

# Update dependencies
uv lock --upgrade          # Update lockfile
uv sync                    # Install updated deps

# Show installed packages
uv pip list                # List all packages
uv pip show package-name   # Show package details

# Cache management
uv cache clean             # Clear cache
uv cache dir               # Show cache directory
```

4. **Set up environment variables**

```bash
cp .env.example .env
```

Edit `.env` and fill in your configuration values. See [Environment Configuration](#environment-configuration) below.

5. **Run the application**

```bash
# Development mode (with hot reload)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python directly
uv run python -m app.main

# Alternative: using uv's built-in runner
uv run app/main.py
```

6. **Access the API**

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

## ⚙️ Environment Configuration

### Critical Environment Variables

All environment-specific configuration is in `.env`. **Zero code changes** required when promoting between environments.

#### Required Variables

```bash
# Application
ENVIRONMENT=development  # development | uat | production
SECRET_KEY=<generate-with-openssl-rand-hex-32>

# Database - Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# AI - OpenAI
OPENAI_API_KEY=sk-your-api-key
OPENAI_MODEL=gpt-4

# Observability - LangFuse
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
```

#### Environment-Specific Settings

**Development:**
```bash
DEBUG=true
LOG_LEVEL=DEBUG
CORS_ORIGINS=http://localhost:3000
ENABLE_API_DOCS=true
LANGFUSE_SAMPLE_RATE=1.0  # Trace everything
```

**UAT:**
```bash
DEBUG=false
LOG_LEVEL=INFO
CORS_ORIGINS=https://uat.compaytence.com
ENABLE_API_DOCS=true
LANGFUSE_SAMPLE_RATE=0.5  # Trace 50%
```

**Production:**
```bash
DEBUG=false
LOG_LEVEL=WARNING
CORS_ORIGINS=https://app.compaytence.com
ENABLE_API_DOCS=false  # Disable for security
LANGFUSE_SAMPLE_RATE=0.1  # Trace 10%
```

See `.env.example` for complete configuration reference.

## 🧪 Testing

### Run Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=app --cov-report=html

# Specific test types
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m e2e

# Watch mode (for development)
uv run pytest-watch
```

### Code Quality

```bash
# Format code
uv run black app/ tests/

# Lint
uv run ruff check app/ tests/

# Fix linting issues automatically
uv run ruff check --fix app/ tests/

# Type checking
uv run mypy app/
```

## 📦 Deployment

### Railway Deployment

1. **Install Railway CLI**

```bash
npm install -g @railway/cli
```

2. **Login to Railway**

```bash
railway login
```

3. **Initialize project**

```bash
railway init
```

4. **Set environment variables**

```bash
railway variables set ENVIRONMENT=production
railway variables set SECRET_KEY=<your-secret-key>
# ... add all other variables
```

Or import from `.env.production`:

```bash
railway variables set --from .env.production
```

5. **Deploy**

```bash
railway up
```

### Branch-Based Deployments

- `dev` branch → Dev environment
- `staging` branch → UAT environment
- `main` branch → Production environment

Railway automatically deploys on push to these branches.

## 🔧 Development Workflow

### Adding a New Endpoint

1. **Create Pydantic models** in `app/models/`
2. **Create service logic** in `app/services/`
3. **Create API endpoint** in `app/api/v1/`
4. **Register router** in `app/api/v1/__init__.py`
5. **Write tests** in `tests/api/v1/`

### Example: Chat Endpoint

```python
# app/models/chat.py
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    session_id: str

class ChatResponse(BaseModel):
    response: str
    confidence: float
    sources: list

# app/services/chat.py
async def process_chat(request: ChatRequest) -> ChatResponse:
    # Business logic here
    pass

# app/api/v1/chat.py
from fastapi import APIRouter
from app.models.chat import ChatRequest, ChatResponse
from app.services.chat import process_chat

router = APIRouter()

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await process_chat(request)
```

## 📊 Monitoring & Observability

### LangFuse Integration

All agent interactions are traced in LangFuse:

- Request/response pairs
- Token usage
- Latency metrics
- Confidence scores
- Tool calls

Access LangFuse dashboard at: https://cloud.langfuse.com (or your self-hosted URL)

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Response
{
  "status": "healthy",
  "service": "Compaytence AI Agent",
  "version": "0.1.0",
  "environment": "development"
}
```

### Logs

Structured logging in production:

```
timestamp=2024-01-15T10:30:00 level=INFO logger=app.main message="Request processed" request_id=abc123 user_id=user456 duration_ms=150
```

## 🔐 Security

### Authentication

- Better Auth integration for user authentication
- JWT tokens for API access
- API keys for service-to-service communication

### Rate Limiting

- Per-user rate limits
- Per-endpoint throttling
- Cost-based limits (OpenAI API usage)

### Best Practices

- All secrets in environment variables
- No hardcoded credentials
- HTTPS in production
- CORS properly configured
- Input validation with Pydantic
- SQL injection prevention (Supabase handles this)

## 📚 API Documentation

### OpenAPI Schema

Interactive API documentation available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

To generate OpenAPI schema file:

```bash
uv run python -c "from app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > openapi.json
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/chat` | POST | Chat with agent |
| `/api/v1/chat/stream` | POST | Streaming chat (SSE) |
| `/api/v1/sources/connect` | POST | Connect data source |
| `/api/v1/documents/upload` | POST | Upload document |
| `/api/v1/webhooks/slack` | POST | Slack webhook |
| `/api/v1/webhooks/whatsapp` | POST | WhatsApp webhook |
| `/api/v1/webhooks/telegram` | POST | Telegram webhook |

## 🐛 Troubleshooting

### Common Issues

**Import errors:**
```bash
# Ensure dependencies are installed
uv sync

# If still having issues, try reinstalling
rm -rf .venv uv.lock
uv sync
```

**Module not found:**
```bash
# uv automatically handles PYTHONPATH, but if needed:
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use uv run to ensure proper environment
uv run python -m app.main
```

**uv-specific issues:**
```bash
# Update uv to latest version
uv self update

# Clear uv cache
uv cache clean

# Check uv version
uv --version
```

**Database connection issues:**
- Verify Supabase credentials in `.env`
- Check network connectivity
- Ensure pgvector extension is enabled

**OpenAI API errors:**
- Verify API key is valid
- Check rate limits and quotas
- Review token usage

## 📞 Support

For issues and questions:
- Technical Specification: See `Compaytence Technical Specification.md`
- Project Overview: See `Compaytence Project Breakdown_ AI Agent.md`
- Cost Analysis: See `Compaytence Cost Breakdown.md`

## 📝 License

[Your License Here]

---

**Built with ❤️ using FastAPI, LangGraph, and OpenAI**
