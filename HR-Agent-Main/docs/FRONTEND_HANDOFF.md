# Frontend Development Handoff Document

## Overview

This document provides all information needed for the frontend team working in the **separate `compaytence-frontend` repository** to integrate with this backend system.

**Backend Repository:** `compaytence-agent` (this repo)
**Frontend Repository:** `compaytence-frontend` (separate repo)
**Backend Status:** ✅ Week 2 Complete - Production-ready with 1,801 lines of agent code

---

## Table of Contents

1. [Project Context](#project-context)
2. [Architecture Overview](#architecture-overview)
3. [Backend API Contracts](#backend-api-contracts)
4. [Environment Configuration](#environment-configuration)
5. [Authentication & Authorization](#authentication--authorization)
6. [Three Frontend Surfaces](#three-frontend-surfaces)
7. [Technology Stack Requirements](#technology-stack-requirements)
8. [OpenAPI Contract Management](#openapi-contract-management)
9. [Streaming Implementation (SSE)](#streaming-implementation-sse)
10. [Error Handling Patterns](#error-handling-patterns)
11. [Deployment](#deployment)

---

## Project Context

### Business Objective
Reduce repetitive Q&A volume by ≥40-60% within 30 days through AI-powered finance/payment assistance.

### Timeline
- **Week 1-2:** Backend (✅ Complete)
- **Week 3-4:** Frontend (Current Phase)

### Key Requirements
- **95% Confidence Threshold:** Agent must escalate queries with confidence <95% to human support
- **Four Data Sources:** Slack, WhatsApp, Telegram, Admin Upload
- **Hybrid Search:** Vector similarity (pgvector) + keyword matching + Cohere reranking
- **Real-time Streaming:** Server-Sent Events (SSE) for chat responses
- **Observability:** All interactions traced via LangFuse

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Separate Repo)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ White-Label  │  │  Embeddable  │  │    Admin     │      │
│  │   Portal     │  │    Widget    │  │  Dashboard   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            │                                 │
└────────────────────────────┼─────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  FastAPI Backend │
                    │   (This Repo)    │
                    └────────┬─────────┘
                             │
          ┏━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━┓
          ┃                                     ┃
    ┌─────▼──────┐                    ┌────────▼────────┐
    │ LangGraph  │                    │    Supabase     │
    │   Agent    │                    │ (PostgreSQL +   │
    │  System    │◄───────────────────│    pgvector)    │
    └─────┬──────┘                    └─────────────────┘
          │
          ├─► LangFuse (Observability)
          ├─► OpenAI/Anthropic/Google (LLMs)
          ├─► Cohere (Reranking)
          └─► Tools (Calculator, Web Search, MCP)
```

### Data Flow
1. **User Query** → Frontend → `POST /api/v1/chat` or `POST /api/v1/chat/stream`
2. **Agent Processing:**
   - Query Analysis (intent, complexity, entities)
   - Tool Invocation (if needed) OR Retrieval (hybrid search)
   - Response Generation (LLM with context)
   - Confidence Scoring (multi-factor algorithm)
   - Decision: confidence ≥95% → Respond | <95% → Escalate
3. **Response** → Streaming (SSE) or JSON → Frontend → User

---

## Backend API Contracts

### Base URLs

| Environment | URL                                    | Purpose                          |
|-------------|----------------------------------------|----------------------------------|
| Development | `http://localhost:8000`                | Local development                |
| Staging     | `https://api-staging.compaytence.com`  | UAT testing (Railway)            |
| Production  | `https://api.compaytence.com`          | Live production (Railway)        |

**All endpoints prefixed with:** `/api/v1`

### Core Endpoints

#### 1. Chat API

**POST `/api/v1/chat`** - Non-streaming chat
```typescript
// Request
interface ChatRequest {
  message: string;        // Max 4000 chars
  session_id: string;     // UUID for session tracking
  user_id?: string;       // Optional user ID
  context?: ChatMessage[]; // Previous messages
  stream: boolean;        // false for JSON response
}

interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string; // ISO 8601
}

// Response
interface ChatResponse {
  message: string;
  confidence: number;     // 0-1 scale
  sources: SourceReference[];
  escalated: boolean;
  escalation_reason?: string;
  session_id: string;
  response_time_ms?: number;
  tokens_used?: number;
}

interface SourceReference {
  content: string;        // Relevant snippet
  source: string;         // "slack", "whatsapp", "telegram", "admin_upload"
  timestamp?: string;
  metadata?: Record<string, any>;
  similarity_score: number; // 0-1
}
```

**POST `/api/v1/chat/stream`** - Streaming chat (SSE)
```typescript
// Request: Same as ChatRequest with stream: true
// Response: Server-Sent Events stream

interface ChatStreamChunk {
  chunk: string;
  is_final: boolean;
  confidence?: number;    // Only in final chunk
  sources?: SourceReference[]; // Only in final chunk
}

// SSE Format:
// data: {"chunk": "Hello", "is_final": false}\n\n
// data: {"chunk": " world", "is_final": false}\n\n
// data: {"chunk": "", "is_final": true, "confidence": 0.97, "sources": [...]}\n\n
```

**GET `/api/v1/chat/history/{session_id}?limit=50`**
```typescript
// Response
interface ChatHistoryResponse {
  session_id: string;
  messages: ChatMessage[];
  count: number;
}
```

**DELETE `/api/v1/chat/session/{session_id}`**
```typescript
// Response
interface SessionClearResponse {
  success: boolean;
  message: string;
}
```

#### 2. Documents API

**POST `/api/v1/documents/upload`** - Single document upload
```typescript
// Request: multipart/form-data
// - file: File (PDF, DOCX, XLSX, PPTX, TXT, MD)
// - title?: string
// - source: string (default: "admin_upload")

// Response
interface DocumentUploadResponse {
  document_id: string;
  title: string;
  source: string;
  file_path: string;
  status: "processing" | "completed" | "failed";
  created_at: string;
}
```

**POST `/api/v1/documents/upload/bulk`** - Bulk upload (max 10 files)
```typescript
// Request: multipart/form-data
// - files: File[] (max 10)
// - source: string

// Response
interface BulkUploadResponse {
  total: number;
  successful: number;
  failed: number;
  documents: DocumentUploadResponse[];
}
```

**GET `/api/v1/documents?source=&status=&page=1&page_size=20`**
```typescript
// Response
interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface Document {
  document_id: string;
  title: string;
  source: string;
  status: string;
  created_at: string;
  updated_at: string;
}
```

**GET `/api/v1/documents/{document_id}`**
```typescript
// Response: Document (detailed)
```

**DELETE `/api/v1/documents/{document_id}`**
```typescript
// Response
interface DeleteResponse {
  success: boolean;
  message: string;
}
```

#### 3. Tools API

**GET `/api/v1/tools?category=&enabled=`**
```typescript
// Response
interface ToolListResponse {
  tools: ToolInfo[];
  total_count: number;
  enabled_count: number;
  disabled_count: number;
}

interface ToolInfo {
  name: string;
  description: string;
  category: "math" | "finance" | "search" | "utility";
  enabled: boolean;
  config: Record<string, any>;
  usage_count: number;
  last_used?: string;
  requires_config: boolean; // True if needs API keys
}
```

**GET `/api/v1/tools/{tool_name}`**
```typescript
// Response: ToolInfo (detailed)
```

**PATCH `/api/v1/tools/{tool_name}`** - Update tool config
```typescript
// Request
interface ToolUpdateRequest {
  enabled?: boolean;
  config?: Record<string, any>; // e.g., { "api_key": "encrypted_value" }
  description?: string;
}

// Response: ToolInfo
```

**POST `/api/v1/tools/{tool_name}/enable`**
**POST `/api/v1/tools/{tool_name}/disable`**
```typescript
// Response: ToolInfo
```

**GET `/api/v1/tools/analytics/usage`**
```typescript
// Response
interface ToolAnalytics {
  total_invocations: number;
  unique_tools_used: number;
  most_used_tools: Array<{
    tool_name: string;
    usage_count: number;
  }>;
  by_category: Record<string, number>;
}
```

#### 4. MCP Servers API

**GET `/api/v1/mcp-servers?enabled=`**
```typescript
// Response
interface MCPServerListResponse {
  servers: MCPServerInfo[];
  total_count: number;
  enabled_count: number;
  disabled_count: number;
}

interface MCPServerInfo {
  name: string;
  url: string;
  description?: string;
  enabled: boolean;
  health_status: "healthy" | "unhealthy" | "unknown";
  tools_discovered: number;
  last_health_check?: string;
  config?: Record<string, any>;
}
```

**POST `/api/v1/mcp-servers`** - Register remote MCP server
```typescript
// Request
interface MCPServerCreateRequest {
  config: {
    name: string;          // Unique name
    url: string;           // http:// or https://
    description?: string;
    enabled?: boolean;     // Default: true
    headers?: Record<string, string>; // Auth headers
    config?: Record<string, any>;
  };
}

// Response: MCPServerInfo
```

**PATCH `/api/v1/mcp-servers/{server_name}`**
```typescript
// Request
interface MCPServerUpdateRequest {
  enabled?: boolean;
  description?: string;
  config?: Record<string, any>;
}

// Response: MCPServerInfo
```

**DELETE `/api/v1/mcp-servers/{server_name}`**
**POST `/api/v1/mcp-servers/{server_name}/enable`**
**POST `/api/v1/mcp-servers/{server_name}/disable`**
**POST `/api/v1/mcp-servers/{server_name}/refresh-tools`**

#### 5. Sources API

**POST `/api/v1/sources/slack/ingest`** - Trigger Slack historical ingestion
```typescript
// Request
interface SlackIngestionRequest {
  channel_ids: string[];
  start_date?: string; // ISO 8601
  end_date?: string;
  limit_per_channel?: number;
}

// Response
interface SlackIngestionResponse {
  total_channels: number;
  total_ingested: number;
  total_failed: number;
  results: Array<{
    channel_id: string;
    ingested: number;
    failed: number;
  }>;
}
```

**GET `/api/v1/sources/status`**
```typescript
// Response
interface SourcesStatusResponse {
  sources: Array<{
    source_type: "slack" | "whatsapp" | "telegram" | "admin_upload";
    connected: boolean;
    last_sync?: string;
    total_documents: number;
    health_status: "healthy" | "degraded" | "unhealthy";
  }>;
}
```

#### 6. Webhooks (Background)

**POST `/api/v1/webhooks/slack`** - Slack events (not called by frontend)
**POST `/api/v1/webhooks/whatsapp`** - WhatsApp events
**POST `/api/v1/webhooks/telegram`** - Telegram events

#### 7. Health & Meta

**GET `/health`**
```typescript
// Response
interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  timestamp: string;
  version: string;
  environment: "development" | "uat" | "production";
}
```

**GET `/api/v1/models`** - List available LLM models
```typescript
// Response
interface ModelsResponse {
  models: Array<{
    provider: "openai" | "anthropic" | "google";
    name: string;
    context_window: number;
  }>;
}
```

---

## Environment Configuration

### Frontend Environment Variables

```bash
# .env.local (Development)
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_PREFIX=/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://pmtrmcafcxuyumkgmynx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
NEXT_PUBLIC_BETTER_AUTH_URL=https://your-auth-domain.com
NEXT_PUBLIC_ENVIRONMENT=development

# .env.staging (UAT)
NEXT_PUBLIC_API_URL=https://api-staging.compaytence.com
NEXT_PUBLIC_API_PREFIX=/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://pmtrmcafcxuyumkgmynx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
NEXT_PUBLIC_BETTER_AUTH_URL=https://staging-auth.compaytence.com
NEXT_PUBLIC_ENVIRONMENT=uat

# .env.production (Production)
NEXT_PUBLIC_API_URL=https://api.compaytence.com
NEXT_PUBLIC_API_PREFIX=/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://pmtrmcafcxuyumkgmynx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
NEXT_PUBLIC_BETTER_AUTH_URL=https://auth.compaytence.com
NEXT_PUBLIC_ENVIRONMENT=production
```

### Backend URLs by Environment

| Environment | Backend URL                           | Purpose                     |
|-------------|---------------------------------------|-----------------------------|
| Development | `http://localhost:8000`               | Local backend               |
| Staging     | `https://api-staging.compaytence.com` | UAT testing (Railway)       |
| Production  | `https://api.compaytence.com`         | Production (Railway)        |

---

## Authentication & Authorization

### Better Auth Integration

**Authentication Provider:** Better Auth (separate auth service)
**Backend Auth:** JWT tokens via HTTP-only cookies
**RBAC Roles:** Super Admin, Admin, Viewer

#### Authentication Flow

1. **User Login:** Frontend → Better Auth → JWT token (HTTP-only cookie)
2. **Authenticated Requests:** Frontend → Backend (cookie sent automatically)
3. **Backend Validation:** Verify JWT signature, check role/permissions
4. **Protected Routes:** Redirect to login if unauthorized

#### RBAC Permissions

| Role         | Permissions                                                       |
|--------------|-------------------------------------------------------------------|
| Super Admin  | Full access: chat, documents, tools, MCP, sources, admin portal  |
| Admin        | Chat, document management, view analytics (no tool/MCP config)   |
| Viewer       | Chat only (read-only access)                                      |

#### Frontend Implementation

```typescript
// Example: Protected API call with authentication
const chatWithAgent = async (message: string, sessionId: string) => {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include', // CRITICAL: Send HTTP-only cookies
    body: JSON.stringify({
      message,
      session_id: sessionId,
      stream: false,
    }),
  });

  if (response.status === 401) {
    // Redirect to login
    window.location.href = '/login';
    return;
  }

  return response.json();
};
```

#### Protected Route Pattern (Next.js)

```typescript
// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const authCookie = request.cookies.get('auth-token');

  if (!authCookie && request.nextUrl.pathname.startsWith('/admin')) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/admin/:path*', '/chat/:path*'],
};
```

---

## Three Frontend Surfaces

### 1. White-Label Portal (Full-Page Chat Interface)

**Purpose:** Standalone chat application for internal teams or customers
**URL Pattern:** `https://portal.compaytence.com` or `https://your-company.com/chat`

#### Key Features
- Full-screen chat interface
- Session history sidebar
- Source citations display
- Confidence score indicator
- Escalation notices
- Customizable branding (logo, colors, font)

#### Required Pages
- `/chat` - Main chat interface
- `/chat/history` - Past conversations
- `/chat/session/{session_id}` - Specific session view

#### Component Requirements
```typescript
// Chat Interface Components
<ChatContainer>
  <SessionSidebar sessions={sessions} onSelectSession={handleSelect} />
  <ChatWindow>
    <MessageList messages={messages} />
    <MessageInput onSend={handleSend} isLoading={isLoading} />
    <ConfidenceIndicator score={confidence} />
    <SourcesList sources={sources} />
  </ChatWindow>
</ChatContainer>
```

#### Branding Customization
```typescript
interface BrandingConfig {
  logo: string;          // URL to logo image
  primaryColor: string;  // Hex color
  secondaryColor: string;
  fontFamily: string;
  name: string;          // Company name
}
```

### 2. Embeddable Widget (Minimized/Expanded States)

**Purpose:** Embed chat in any website (e.g., support pages, documentation)
**Integration:** `<script>` tag or React component

#### Widget States
1. **Minimized:** Floating button (bottom-right corner, customizable position)
2. **Expanded:** Chat window overlay (400x600px default, responsive)

#### Integration Methods

**Option A: Script Tag (Universal)**
```html
<!-- Customer website -->
<script src="https://cdn.compaytence.com/widget.js"></script>
<script>
  CompaytenceWidget.init({
    apiUrl: 'https://api.compaytence.com',
    position: 'bottom-right', // bottom-left, top-right, top-left
    theme: {
      primaryColor: '#0066cc',
      logo: 'https://your-company.com/logo.png',
    },
    customFields: {
      companyId: 'your-company-id',
    },
  });
</script>
```

**Option B: React Component (React Apps)**
```tsx
import { CompaytenceWidget } from '@compaytence/react-widget';

function App() {
  return (
    <div>
      {/* Your app */}
      <CompaytenceWidget
        apiUrl="https://api.compaytence.com"
        position="bottom-right"
        theme={{ primaryColor: '#0066cc' }}
      />
    </div>
  );
}
```

#### Widget Component Requirements
```typescript
<Widget>
  <MinimizedButton onClick={handleExpand}>
    <Icon /> {/* Chat bubble icon */}
    <Badge count={unreadCount} />
  </MinimizedButton>

  <ExpandedWindow isOpen={isExpanded}>
    <WidgetHeader onClose={handleMinimize}>
      <Logo />
      <CloseButton />
    </WidgetHeader>
    <ChatWindow>
      <MessageList messages={messages} compact />
      <MessageInput onSend={handleSend} placeholder="Ask a question..." />
    </ChatWindow>
  </ExpandedWindow>
</Widget>
```

#### Widget Customization Options
- Position (bottom-right, bottom-left, top-right, top-left)
- Theme (primary color, logo, font)
- Initial state (minimized, expanded)
- z-index control (avoid conflicts)
- Custom greeting message
- Pre-fill user info (email, name)

### 3. Admin Dashboard (Analytics & Management)

**Purpose:** Backend management for admins (Super Admin, Admin roles)
**URL Pattern:** `https://admin.compaytence.com` or `https://portal.compaytence.com/admin`

#### Required Pages & Features

**A. Analytics Dashboard (`/admin/dashboard`)**
- Total conversations count
- Average confidence score
- Escalation rate (% queries escalated)
- Top sources used (Slack, WhatsApp, Telegram, Upload)
- Query volume over time (chart)
- Most common intents
- Response time distribution
- Token usage & cost tracking (via LangFuse)

**Components Needed:**
```typescript
<AdminDashboard>
  <StatsGrid>
    <StatCard title="Total Conversations" value={totalConvos} />
    <StatCard title="Avg Confidence" value={avgConfidence} />
    <StatCard title="Escalation Rate" value={escalationRate} />
    <StatCard title="Token Usage" value={totalTokens} />
  </StatsGrid>

  <ChartSection>
    <TimeSeriesChart data={queryVolumeData} title="Query Volume" />
    <PieChart data={sourceDistribution} title="Sources Used" />
  </ChartSection>

  <IntentsTable intents={topIntents} />
</AdminDashboard>
```

**B. Knowledge Base Management (`/admin/knowledge`)**
- Document list (source, status, created date)
- Upload new documents (single + bulk)
- Processing status tracking (real-time)
- Delete documents
- Re-index documents
- Search documents
- View document details

**Components Needed:**
```typescript
<KnowledgeBase>
  <UploadSection>
    <DragDropUpload onUpload={handleUpload} maxFiles={10} />
    <ProcessingQueue items={processingItems} />
  </UploadSection>

  <DocumentTable>
    <DataTable
      columns={[
        { key: 'title', label: 'Title' },
        { key: 'source', label: 'Source' },
        { key: 'status', label: 'Status' },
        { key: 'created_at', label: 'Created' },
        { key: 'actions', label: 'Actions' },
      ]}
      data={documents}
      pagination
      filters={['source', 'status']}
    />
  </DocumentTable>
</KnowledgeBase>
```

**C. Agent Configuration (`/admin/agent`)**
- Model selection (OpenAI GPT-4, Anthropic Claude, Google Gemini)
- Confidence threshold adjustment (default 95%)
- System prompt customization
- Enable/disable tools
- Enable/disable MCP servers
- Tool usage statistics
- Test agent (chat sandbox)

**Components Needed:**
```typescript
<AgentConfig>
  <ModelSelector
    models={availableModels}
    selected={currentModel}
    onChange={handleModelChange}
  />

  <ConfidenceSlider
    value={confidenceThreshold}
    min={0.5}
    max={1.0}
    step={0.05}
    onChange={handleThresholdChange}
  />

  <SystemPromptEditor
    value={systemPrompt}
    onChange={handlePromptChange}
  />

  <ToolsManager>
    <ToolCard
      name="Calculator"
      enabled={true}
      onToggle={handleToggle}
      onConfigure={handleConfigure}
    />
    {/* Repeat for all tools */}
  </ToolsManager>

  <MCPServersManager>
    <ServerCard
      name="Weather Service"
      url="https://weather.example.com/mcp"
      health="healthy"
      onEdit={handleEdit}
      onDelete={handleDelete}
    />
    <AddServerButton onClick={handleAddServer} />
  </MCPServersManager>

  <TestSandbox>
    <ChatInterface testMode />
  </TestSandbox>
</AgentConfig>
```

**D. Data Sources (`/admin/sources`)**
- Slack: Connected channels, sync status, trigger historical ingestion
- WhatsApp: Business account status, message count
- Telegram: Bot status, chat count
- Admin Upload: Upload history, processing queue
- Connection health indicators

**Components Needed:**
```typescript
<DataSources>
  <SourceCard
    type="slack"
    connected={true}
    lastSync={lastSyncTime}
    documentCount={5432}
  >
    <ChannelList channels={slackChannels} />
    <IngestButton onClick={handleSlackIngest} />
  </SourceCard>

  <SourceCard
    type="admin_upload"
    connected={true}
    lastSync={lastSyncTime}
    documentCount={53}
  >
    <UploadHistory uploads={recentUploads} />
  </SourceCard>
</DataSources>
```

**E. User Management (`/admin/users`)** *(if needed)*
- User list (name, email, role)
- Add/edit/delete users
- Role assignment (Super Admin, Admin, Viewer)

---

## Technology Stack Requirements

### Mandatory Technologies

**Framework:** Next.js 14+ with App Router
**Language:** TypeScript (strict mode)
**State Management:**
  - **Server State:** React Query (TanStack Query v5)
  - **Client State:** Zustand or Jotai (lightweight)
**Styling:** Tailwind CSS
**Component Library:** Shadcn UI (recommended for admin dashboard)
**Icons:** Lucide React or Heroicons
**Charts:** Recharts or Chart.js
**Forms:** React Hook Form + Zod validation
**HTTP Client:** Fetch API (native) or Axios
**WebSocket/SSE:** EventSource API (native)

### Project Structure (Recommended)

```
compaytence-frontend/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── (portal)/           # White-label portal routes
│   │   │   ├── chat/
│   │   │   └── history/
│   │   ├── (admin)/            # Admin dashboard routes
│   │   │   ├── dashboard/
│   │   │   ├── knowledge/
│   │   │   ├── agent/
│   │   │   ├── sources/
│   │   │   └── users/
│   │   └── api/                # Next.js API routes (if needed)
│   ├── components/
│   │   ├── chat/               # Chat UI components
│   │   ├── widget/             # Embeddable widget
│   │   ├── admin/              # Admin dashboard components
│   │   └── common/             # Shared components
│   ├── lib/
│   │   ├── api.ts              # API client functions
│   │   ├── types.ts            # TypeScript types (from OpenAPI)
│   │   ├── hooks/              # Custom React hooks
│   │   └── utils/              # Utility functions
│   ├── hooks/
│   │   ├── useChat.ts
│   │   ├── useDocuments.ts
│   │   └── useTools.ts
│   └── styles/
│       └── globals.css
├── public/
│   └── widget.js               # Embeddable widget bundle
├── .env.local
├── .env.staging
├── .env.production
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

---

## OpenAPI Contract Management

### Workflow

1. **Backend Generates OpenAPI Spec:**
   ```bash
   # In backend repo (compaytence-agent)
   uv run python -c "from app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > openapi.json
   ```

2. **Frontend Consumes OpenAPI Spec:**
   ```bash
   # In frontend repo (compaytence-frontend)
   npx openapi-typescript https://api.compaytence.com/openapi.json -o src/lib/api-types.ts
   ```

3. **Use Generated Types:**
   ```typescript
   import type { paths } from '@/lib/api-types';

   type ChatRequest = paths['/api/v1/chat']['post']['requestBody']['content']['application/json'];
   type ChatResponse = paths['/api/v1/chat']['post']['responses']['200']['content']['application/json'];

   async function chat(request: ChatRequest): Promise<ChatResponse> {
     const response = await fetch(`${API_URL}/api/v1/chat`, {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       credentials: 'include',
       body: JSON.stringify(request),
     });
     return response.json();
   }
   ```

### CI/CD Integration

**Backend:** Automatically publish OpenAPI spec on deploy
**Frontend:** Regenerate types before build in CI/CD

```yaml
# .github/workflows/deploy-frontend.yml
steps:
  - name: Generate API Types
    run: |
      npx openapi-typescript ${{ secrets.API_URL }}/openapi.json -o src/lib/api-types.ts
  - name: Build
    run: npm run build
```

---

## Streaming Implementation (SSE)

### Server-Sent Events (SSE) Pattern

Backend streams responses via **Server-Sent Events** for real-time chat.

#### Frontend Implementation

```typescript
'use client'; // Client component for SSE

import { useState, useEffect } from 'react';

function useChatStream(sessionId: string) {
  const [messages, setMessages] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [sources, setSources] = useState<SourceReference[]>([]);

  const sendMessage = async (message: string) => {
    setIsStreaming(true);
    setMessages((prev) => [...prev, '']); // Add empty message for streaming

    const eventSource = new EventSource(
      `${API_URL}/api/v1/chat/stream?` +
      new URLSearchParams({
        message,
        session_id: sessionId,
        stream: 'true',
      }),
      { withCredentials: true } // Include cookies
    );

    eventSource.onmessage = (event) => {
      const chunk: ChatStreamChunk = JSON.parse(event.data);

      if (chunk.is_final) {
        // Final chunk: update confidence and sources
        setConfidence(chunk.confidence || null);
        setSources(chunk.sources || []);
        setIsStreaming(false);
        eventSource.close();
      } else {
        // Append chunk to current message
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] += chunk.chunk;
          return updated;
        });
      }
    };

    eventSource.onerror = () => {
      console.error('SSE connection error');
      setIsStreaming(false);
      eventSource.close();
    };
  };

  return { messages, isStreaming, confidence, sources, sendMessage };
}
```

#### React Query + SSE Integration

```typescript
import { useMutation } from '@tanstack/react-query';

function useChatMutation() {
  return useMutation({
    mutationFn: async ({ message, sessionId }: { message: string; sessionId: string }) => {
      return new Promise<ChatResponse>((resolve, reject) => {
        const eventSource = new EventSource(
          `${API_URL}/api/v1/chat/stream?message=${encodeURIComponent(message)}&session_id=${sessionId}`,
          { withCredentials: true }
        );

        let fullMessage = '';
        let finalChunk: ChatStreamChunk | null = null;

        eventSource.onmessage = (event) => {
          const chunk: ChatStreamChunk = JSON.parse(event.data);

          if (chunk.is_final) {
            finalChunk = chunk;
            eventSource.close();
            resolve({
              message: fullMessage,
              confidence: chunk.confidence || 0,
              sources: chunk.sources || [],
              escalated: (chunk.confidence || 1) < 0.95,
              session_id: sessionId,
            });
          } else {
            fullMessage += chunk.chunk;
          }
        };

        eventSource.onerror = () => {
          eventSource.close();
          reject(new Error('Streaming failed'));
        };
      });
    },
  });
}
```

---

## Error Handling Patterns

### HTTP Status Codes

| Code | Meaning            | Frontend Action                              |
|------|--------------------|----------------------------------------------|
| 200  | Success            | Display response                             |
| 201  | Created            | Show success message                         |
| 400  | Bad Request        | Display validation errors                    |
| 401  | Unauthorized       | Redirect to login                            |
| 403  | Forbidden          | Show "Access Denied" message                 |
| 404  | Not Found          | Display "Not Found" message                  |
| 409  | Conflict           | Display error (e.g., duplicate MCP server)   |
| 500  | Internal Error     | Show generic error + retry option            |

### Error Response Format

```typescript
interface ErrorResponse {
  detail: string; // Human-readable error message
  status_code: number;
  error_code?: string; // Optional machine-readable code
}
```

### Frontend Error Handling

```typescript
async function apiCall<T>(url: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(url, {
      ...options,
      credentials: 'include',
    });

    if (!response.ok) {
      const error: ErrorResponse = await response.json();

      if (response.status === 401) {
        // Redirect to login
        window.location.href = '/login';
        throw new Error('Unauthorized');
      }

      if (response.status === 403) {
        throw new Error('Access Denied: Insufficient permissions');
      }

      throw new Error(error.detail || 'Request failed');
    }

    return response.json();
  } catch (error) {
    // Log to error tracking (e.g., Sentry)
    console.error('API Error:', error);
    throw error;
  }
}
```

### React Query Error Handling

```typescript
import { useQuery } from '@tanstack/react-query';

function useDocuments() {
  return useQuery({
    queryKey: ['documents'],
    queryFn: () => apiCall<DocumentListResponse>(`${API_URL}/api/v1/documents`),
    retry: (failureCount, error) => {
      // Retry 3 times for network errors, but not for 4xx errors
      if ((error as any).status >= 400 && (error as any).status < 500) {
        return false;
      }
      return failureCount < 3;
    },
    onError: (error) => {
      // Show toast notification
      toast.error(error.message);
    },
  });
}
```

---

## Deployment

### Frontend (Vercel)

**Repository:** `compaytence-frontend` (separate repo)
**Platform:** Vercel
**Domains:**
  - Production: `https://portal.compaytence.com`
  - Staging: `https://staging.compaytence.com`

**Environment Variables (Vercel):**
```
# Production
NEXT_PUBLIC_API_URL=https://api.compaytence.com
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_BETTER_AUTH_URL=https://auth.compaytence.com

# Staging
NEXT_PUBLIC_API_URL=https://api-staging.compaytence.com
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_BETTER_AUTH_URL=https://staging-auth.compaytence.com
```

**Build Command:** `npm run build`
**Output Directory:** `.next`

### Backend (Railway) - Already Deployed

**Repository:** `compaytence-agent` (this repo)
**Platform:** Railway
**Branches:**
  - `main` → Production (`https://api.compaytence.com`)
  - `staging` → Staging (`https://api-staging.compaytence.com`)
  - `dev` → Development (`https://api-dev.compaytence.com`)

---

## Key Backend Insights

### Agent Behavior
- **95% Confidence Threshold:** Queries with confidence <95% are escalated to human support
- **Hybrid Search:** Vector similarity (pgvector) + keyword matching (tsvector) + Cohere reranking
- **Multi-Provider LLMs:** Supports OpenAI, Anthropic, Google (configurable in admin dashboard)
- **Tool Invocation:** Agent can use calculator, web search (Tavily), and custom MCP tools
- **Response Time:** Target <3s for simple queries, <10s for complex queries

### Data Processing
- **Docling:** Structure-preserving document extraction (tables, headings, lists)
- **PII Detection:** Microsoft Presidio anonymizes sensitive data before storage
- **Chunking Strategy:** Structure-aware chunking (1000 tokens, 200 overlap)
- **Embedding Model:** OpenAI text-embedding-3-large (1536 dimensions)

### Observability
- **LangFuse:** All agent interactions traced (request/response, token usage, latency)
- **Sampling Rates:**
  - Development: 100% (trace everything)
  - UAT: 50%
  - Production: 10% (cost optimization)

### Security
- **Encryption:** All tool API keys encrypted with Fernet (SHA-256 key derivation)
- **MCP Servers:** Remote HTTP-only (no local stdio for security)
- **CORS:** Explicit origin whitelisting (no wildcards)
- **Rate Limiting:** Configurable per-user limits

---

## Testing Recommendations

### Unit Tests
- **Component Testing:** Jest + React Testing Library
- **API Client Testing:** Mock fetch responses with MSW (Mock Service Worker)

### Integration Tests
- **E2E Testing:** Playwright or Cypress
- **Critical Flows:**
  - User login → chat → response received
  - Admin upload document → processing complete
  - Configure tool → save → verify enabled

### Performance Testing
- **Lighthouse:** Target scores >90 for Performance, Accessibility, Best Practices
- **SSE Streaming:** Test with 10+ concurrent streams
- **Widget Load Time:** <500ms to render minimized button

---

## Questions & Support

### Backend Team Contact
- **Repository:** `compaytence-agent`
- **Slack Channel:** `#backend-team` (example)
- **API Documentation:** `https://api.compaytence.com/docs` (Swagger UI)

### API Changes
- All breaking changes will be communicated via Slack + updated OpenAPI spec
- Backend maintains backward compatibility for 30 days after deprecation notice

### Debugging
- **Structured Logging:** All backend logs include `request_id` for tracing
- **LangFuse:** View agent traces for any session_id in LangFuse dashboard
- **Health Endpoint:** `GET /health` for backend status

---

## Appendix: Example Code Snippets

### A. React Query Setup

```typescript
// src/lib/query-client.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute
      retry: 1,
    },
  },
});

// src/app/layout.tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/query-client';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      </body>
    </html>
  );
}
```

### B. API Client Utilities

```typescript
// src/lib/api.ts
const API_URL = process.env.NEXT_PUBLIC_API_URL;
const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1';

class APIClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseURL}${API_PREFIX}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      credentials: 'include', // Include cookies
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Request failed');
    }

    return response.json();
  }

  // Chat API
  async chat(request: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Documents API
  async listDocuments(params?: { source?: string; status?: string; page?: number }): Promise<DocumentListResponse> {
    const query = new URLSearchParams(params as any).toString();
    return this.request<DocumentListResponse>(`/documents?${query}`);
  }

  async uploadDocument(file: File, title?: string): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);

    const url = `${this.baseURL}${API_PREFIX}/documents/upload`;
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Upload failed');
    }

    return response.json();
  }

  // Tools API
  async listTools(params?: { category?: string; enabled?: boolean }): Promise<ToolListResponse> {
    const query = new URLSearchParams(params as any).toString();
    return this.request<ToolListResponse>(`/tools?${query}`);
  }

  async updateTool(toolName: string, update: ToolUpdateRequest): Promise<ToolInfo> {
    return this.request<ToolInfo>(`/tools/${toolName}`, {
      method: 'PATCH',
      body: JSON.stringify(update),
    });
  }

  // MCP Servers API
  async listMCPServers(params?: { enabled?: boolean }): Promise<MCPServerListResponse> {
    const query = new URLSearchParams(params as any).toString();
    return this.request<MCPServerListResponse>(`/mcp-servers?${query}`);
  }

  async createMCPServer(request: MCPServerCreateRequest): Promise<MCPServerInfo> {
    return this.request<MCPServerInfo>('/mcp-servers', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }
}

export const apiClient = new APIClient(API_URL || 'http://localhost:8000');
```

### C. Custom React Hooks

```typescript
// src/hooks/useChat.ts
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';

export function useChat(sessionId: string) {
  const chatMutation = useMutation({
    mutationFn: (message: string) =>
      apiClient.chat({
        message,
        session_id: sessionId,
        stream: false,
      }),
  });

  const historyQuery = useQuery({
    queryKey: ['chat-history', sessionId],
    queryFn: () => apiClient.request(`/chat/history/${sessionId}`),
    enabled: !!sessionId,
  });

  return {
    sendMessage: chatMutation.mutate,
    isLoading: chatMutation.isPending,
    response: chatMutation.data,
    error: chatMutation.error,
    history: historyQuery.data,
  };
}

// src/hooks/useDocuments.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';

export function useDocuments(filters?: { source?: string; status?: string }) {
  const queryClient = useQueryClient();

  const documentsQuery = useQuery({
    queryKey: ['documents', filters],
    queryFn: () => apiClient.listDocuments(filters),
  });

  const uploadMutation = useMutation({
    mutationFn: ({ file, title }: { file: File; title?: string }) =>
      apiClient.uploadDocument(file, title),
    onSuccess: () => {
      // Invalidate documents query to refetch
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  return {
    documents: documentsQuery.data?.documents || [],
    isLoading: documentsQuery.isLoading,
    upload: uploadMutation.mutate,
    isUploading: uploadMutation.isPending,
  };
}

// src/hooks/useTools.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';

export function useTools() {
  const queryClient = useQueryClient();

  const toolsQuery = useQuery({
    queryKey: ['tools'],
    queryFn: () => apiClient.listTools(),
  });

  const updateMutation = useMutation({
    mutationFn: ({ toolName, update }: { toolName: string; update: ToolUpdateRequest }) =>
      apiClient.updateTool(toolName, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tools'] });
    },
  });

  return {
    tools: toolsQuery.data?.tools || [],
    isLoading: toolsQuery.isLoading,
    updateTool: updateMutation.mutate,
    isUpdating: updateMutation.isPending,
  };
}
```

---

## Summary

This handoff document provides everything the frontend team needs to:

1. **Understand the backend architecture** (LangGraph agent, hybrid search, 95% confidence threshold)
2. **Integrate with all backend APIs** (chat, documents, tools, MCP servers, sources)
3. **Implement three frontend surfaces** (portal, widget, admin dashboard)
4. **Handle authentication** (Better Auth + JWT cookies + RBAC)
5. **Stream responses** (Server-Sent Events for real-time chat)
6. **Manage types** (OpenAPI → TypeScript type generation)
7. **Deploy independently** (Vercel frontend, Railway backend)

**Backend Status:** ✅ Production-ready with 1,801 lines of agent code
**Next Steps:** Frontend team can begin development in `compaytence-frontend` repo

**Questions?** Refer to backend Swagger docs at `https://api.compaytence.com/docs`
