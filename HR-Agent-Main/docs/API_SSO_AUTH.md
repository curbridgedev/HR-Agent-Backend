# API Behind SSO - Authentication Requirements

All API endpoints (except those listed below) now require authentication via Supabase. Users must sign in with **Google SSO** or **email/password** before calling the API.

## How It Works

1. **Frontend**: User signs in via Supabase (Google or email/password)
2. **Token**: Supabase returns a JWT (`access_token`)
3. **Requests**: Frontend sends `Authorization: Bearer <token>` on every API call
4. **Backend**: Validates the token with Supabase; returns 401 if invalid or missing

## Protected Endpoints

All of these require a valid Supabase JWT:

| Router | Endpoints |
|--------|-----------|
| **Chat** | POST `/chat`, POST `/chat/stream`, POST `/chat/transcribe`, GET `/chat/history/*`, GET `/chat/sessions`, DELETE `/chat/session/*` |
| **Documents** | GET `/documents`, POST `/documents/upload`, POST `/documents/upload/bulk`, GET `/documents/{id}`, DELETE `/documents/{id}` |
| **Projects** | All project CRUD and sessions |
| **Settings** | User settings, API keys |
| **Upload** | WhatsApp, Telegram, Slack export uploads |
| **Models** | Provider/model discovery |
| **Admin** | LLM models with pricing |
| **Agent** | Agent config, prompts |
| **Analytics** | Session analytics |
| **Prompts** | Prompt management |
| **Tools** | Tool management |
| **MCP Servers** | MCP server management |
| **Agent Graph** | Graph visualization |
| **Customers** | Customer management |
| **Escalate** | Escalation endpoints |
| **Users** | User management (admin role required) |

## Public Endpoints (No Auth Required)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/ping` | Health check |
| `POST /api/v1/auth/token` | OAuth token - exchange email/password for bearer token |
| `GET /widget-config/by-api-key/{api_key}` | Embedded widget config (uses API key for auth) |

## Unauthenticated Requests

If a request is made without a valid token (or with an invalid/expired token):

- **401 Unauthorized** with message: `"Not authenticated. Please provide authentication token."` or `"Invalid or expired authentication token"`

## Token Sources

The backend accepts the token from:

1. **Authorization header**: `Authorization: Bearer <access_token>`
2. **Cookie**: `sb-access-token` (Supabase session cookie)

## Programmatic Access

Two options for programmatic access:

1. **Bearer token (OAuth)**: `POST /api/v1/auth/token` with `{"email": "...", "password": "..."}` returns `{ "access_token": "...", "token_type": "bearer", "expires_in": 3600 }`. Use in `Authorization: Bearer <access_token>` header. Only works for email/password users (not Google SSO).

2. **API key**: Use the **X-API-Key** header with a user API key (created in Settings). This allows authenticated access without a session token.
