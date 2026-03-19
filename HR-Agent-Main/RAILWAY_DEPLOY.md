# Railway Deployment Guide

Deploy the HR Agent (backend + frontend) to Railway. You'll create **two services** from the same monorepo.

---

## 1. Prerequisites

- [Railway account](https://railway.app)
- GitHub repo connected to Railway
- Supabase project (for auth, DB, storage)
- OpenAI API key

---

## 2. Create a New Project

1. Go to [railway.app](https://railway.app) → **New Project**
2. Choose **Deploy from GitHub repo**
3. Select your `HR-Agent` repository

---

## 3. Deploy the Backend

### 3.1 Add Backend Service

1. In your Railway project, click **+ New** → **GitHub Repo**
2. Select the same repo
3. Railway creates a new service

### 3.2 Configure Backend

1. Click the new service → **Settings**
2. Set **Root Directory** to:
   ```
   HR-Agent-Backend/HR-Agent-Main
   ```
3. Railway will auto-detect Nixpacks from `railway.json` and `nixpacks.toml`

### 3.3 Backend Environment Variables

In **Variables**, add (or use **Raw Editor** to paste):

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | ✅ | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Supabase service role key |
| `OPENAI_API_KEY` | ✅ | OpenAI API key |
| `OPENAI_MODEL` | | Default: `gpt-5` (or gpt-5-mini for lower cost) |
| `COHERE_API_KEY` | ✅ | Cohere API key (reranking) |
| `CORS_ORIGINS` | ✅ | **Exact** frontend URL, e.g. `https://hr-agent-frontend-production-xxxx.up.railway.app` (no trailing slash) |
| `ENVIRONMENT` | | `production` |
| `LANGFUSE_PUBLIC_KEY` | | Langfuse (optional) |
| `LANGFUSE_SECRET_KEY` | | Langfuse (optional) |

**CORS**: After deploying the frontend, add its Railway URL to `CORS_ORIGINS`:
```
https://your-frontend-service.up.railway.app
```

### 3.4 Generate Backend Domain

1. **Settings** → **Networking** → **Generate Domain**
2. Copy the URL (e.g. `https://hr-agent-backend-production-xxxx.up.railway.app`)

---

## 4. Deploy the Frontend

### 4.1 Add Frontend Service

1. In the same project, click **+ New** → **GitHub Repo**
2. Select the same repo again

### 4.2 Configure Frontend

1. Click the frontend service → **Settings**
2. Set **Root Directory** to:
   ```
   HR-Agent-Frontend/hr-agent-frontend
   ```

### 4.3 Frontend Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | ✅ | Backend Railway URL (e.g. `https://hr-agent-backend-production-xxxx.up.railway.app`) |
| `NEXT_PUBLIC_API_PREFIX` | | `/api/v1` |
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ | Supabase anon key |
| `NEXT_PUBLIC_ENVIRONMENT` | | `production` |

**Important**: `NEXT_PUBLIC_API_URL` must be the **backend** Railway URL (no trailing slash).

### 4.4 Generate Frontend Domain

1. **Settings** → **Networking** → **Generate Domain**
2. Copy the URL

### 4.5 Update Backend CORS

1. Go back to the **backend** service
2. Variables → Edit `CORS_ORIGINS` to include the frontend URL:
   ```
   https://your-frontend-service.up.railway.app
   ```
3. Redeploy the backend

---

## 5. Root Directory Summary

| Service | Root Directory |
|---------|-----------------|
| Backend | `HR-Agent-Backend/HR-Agent-Main` |
| Frontend | `HR-Agent-Frontend/hr-agent-frontend` |

---

## 6. Build Configuration (Auto-detected)

**Backend**
- Builder: Nixpacks
- Start: `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`

**Frontend**
- Builder: Nixpacks
- Build: `npm run build`
- Start: `npm start`

---

## 7. Verify Deployment

1. **Backend**: Visit `https://your-backend-url/health` → should return `{"status":"healthy"}`
2. **Frontend**: Visit `https://your-frontend-url` → should load the app
3. Test chat: send a message and confirm it reaches the backend

---

## 8. Troubleshooting

| Issue | Fix |
|-------|-----|
| **OPTIONS 400 / CORS errors** | Set `CORS_ORIGINS` on backend to your **exact** frontend URL (e.g. `https://hr-agent-frontend-production-xxxx.up.railway.app`). No trailing slash. Redeploy backend after changing. |
| Backend build fails | Ensure `uv.lock` exists; check `nixpacks.toml` |
| 502 Bad Gateway | Check backend logs; verify `/health` responds |
| Frontend can't reach API | Verify `NEXT_PUBLIC_API_URL` is correct and has no trailing slash |

---

## 9. Optional: Use Railway CLI

```bash
# Install
npm i -g @railway/cli

# Login
railway login

# Link project
railway link

# Deploy
railway up
```

For monorepos, set root directory per service in the Railway dashboard.

