# Telegram Integration Guide

This guide covers the Telegram integration implementation for the Compaytence AI Agent, which uses **Telethon** (MTProto API) for both historical data ingestion and real-time message sync.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Setup Guide](#setup-guide)
4. [API Endpoints](#api-endpoints)
5. [Real-Time Sync](#real-time-sync)
6. [Testing](#testing)
7. [Production Deployment](#production-deployment)

## Overview

**Implementation:** Telethon v1.41.2 with user account authentication (phone + 2FA)

**Capabilities:**
- ✅ Historical message ingestion from chats, groups, and channels
- ✅ Real-time message capture via event listener
- ✅ Automatic embedding generation and vector storage
- ✅ Dialog discovery (list all accessible conversations)
- ✅ Peer reference system for reliable entity resolution
- ✅ Manual export file parsing (Telegram Desktop format)

**Why Telethon over Bot API:**
- Full access to chat history (Bot API only sees messages after bot joins)
- Access to private chats and groups
- User-level permissions for comprehensive data access
- Real-time event listening without webhooks

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Integration                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     TelethonService                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Initialize  │→│ List Dialogs │→│Fetch History │     │
│  │ (StringSession)│  │   (Chats)   │  │  (Messages)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Event Listener│→│Ingest Message│→│  Embedding   │     │
│  │  (Real-time)  │  │   (Text)    │  │  Generation  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Supabase (documents table)                      │
│  - content: Message text                                     │
│  - embedding: OpenAI vector (text-embedding-3-small)        │
│  - source: "telegram"                                        │
│  - source_metadata: Platform-specific metadata              │
└─────────────────────────────────────────────────────────────┘
```

## Setup Guide

### Step 1: Get Telegram API Credentials

1. Visit https://my.telegram.org/auth
2. Log in with your phone number
3. Go to "API development tools"
4. Create a new application:
   - App title: `Compaytence AI Agent`
   - Short name: `compaytence`
   - Platform: `Other`
5. Copy your `API ID` and `API Hash`

### Step 2: Configure Environment Variables

Add to your `.env` file:

```bash
# Telegram Configuration (Telethon)
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_PHONE_NUMBER=+1234567890  # Your phone number
TELEGRAM_SESSION_STRING=  # Generated in next step
```

### Step 3: Generate Session String

Run the interactive authentication script:

```bash
uv run python scripts/telegram_auth.py
```

Follow the prompts:
1. Enter your phone number (if not in .env)
2. Enter the verification code sent to Telegram
3. Enter 2FA password (if enabled)
4. Copy the generated session string
5. Add to `.env` as `TELEGRAM_SESSION_STRING`

**Example output:**
```
Enter phone number: +1234567890
Code sent to your Telegram app
Enter the code: 12345
Enter 2FA password (if enabled): ********

✅ Authentication successful!
Your session string: 1AbCdEfGh...

Add this to your .env file:
TELEGRAM_SESSION_STRING=1AbCdEfGh...
```

### Step 4: Verify Configuration

```bash
# Start the server
uv run uvicorn app.main:app --reload

# Check status
curl http://localhost:8000/api/v1/telegram/status
```

Expected response:
```json
{
  "status": "configured",
  "api_id_set": true,
  "api_hash_set": true,
  "session_string_set": true,
  "phone_number_set": true,
  "message": "Telegram integration is ready"
}
```

## API Endpoints

### 1. List Dialogs

**GET** `/api/v1/telegram/dialogs?limit=50`

Lists all accessible chats, groups, and channels.

**Response:**
```json
{
  "status": "success",
  "message": "Retrieved 10 dialogs",
  "total": 10,
  "dialogs": [
    {
      "id": 123456789,
      "name": "John Doe",
      "title": "John Doe",
      "unread_count": 0,
      "is_user": true,
      "is_group": false,
      "is_channel": false,
      "peer_ref": "u:123456789:abc123def456"
    }
  ]
}
```

**Peer Reference Format:**
- Users: `u:id:access_hash`
- Chats (small groups): `c:id`
- Channels: `ch:id:access_hash`

**Use peer_ref for reliable entity resolution** - it prevents "Could not find the input entity" errors.

### 2. Ingest Historical Messages

**POST** `/api/v1/telegram/ingest-historical`

Fetches and ingests historical messages from a chat.

**Request Body:**
```json
{
  "chat_id": "u:123456789:abc123def456",  // Preferred: peer_ref from /dialogs
  "limit": 100,                           // Optional: null = all messages
  "start_date": "2024-01-01T00:00:00Z",  // Optional: default = 30 days ago
  "end_date": "2024-01-31T23:59:59Z"     // Optional: default = now
}
```

**Alternative chat_id formats:**
- Peer reference (recommended): `"u:123456789:abc123def456"`
- Username: `"@username"` or `"@channelname"`
- Phone number: `"+1234567890"`
- Bare ID (unreliable): `123456789`

**Response:**
```json
{
  "status": "success",
  "message": "Fetched 150 messages: 100 ingested, 45 skipped (no text), 5 failed",
  "chat_id": "u:123456789:abc123def456",
  "messages_ingested": 100,
  "messages_failed": 5,
  "messages_skipped": 45,
  "total_fetched": 150
}
```

**Notes:**
- Messages without text content are automatically skipped
- Embeddings generated automatically using OpenAI
- Stored in `documents` table with `source="telegram"`
- Large chats may take several minutes

### 3. Check Integration Status

**GET** `/api/v1/telegram/status`

Returns configuration status and readiness.

### 4. Upload Telegram Desktop Export

**POST** `/api/v1/upload/telegram-export`

Uploads and parses manual Telegram Desktop export files.

**Request:**
- Content-Type: `multipart/form-data`
- Field: `file` (must be `.txt`)

**Export Format:**
```
[DD.MM.YY HH:MM:SS] Sender Name:
Message content here
Can span multiple lines

[DD.MM.YY HH:MM:SS] Another Sender:
Another message
```

**How to Export from Telegram Desktop:**
1. Open chat in Telegram Desktop
2. Click ⋮ (three dots) → Export chat history
3. Select "Text format"
4. Uncheck media/files (text only)
5. Export and upload the `.txt` file

## Real-Time Sync

### Local Testing

Run the real-time sync test script:

```bash
uv run python scripts/test_telegram_realtime.py
```

**What it does:**
1. Connects to Telegram using your session string
2. Lists your chats
3. Lets you select which chats to monitor (or ALL)
4. Starts event listener
5. Automatically ingests new messages as they arrive

**Example flow:**
```
=============================================================
TELEGRAM REAL-TIME SYNC TEST
=============================================================

1. Connecting to Telegram...
✅ Connected to Telegram!

2. Fetching your chats...
Found 10 recent chats:

#    Type       Name
------------------------------------------------------------
1    User       John Doe
2    Group      Dev Team
3    Channel    Announcements
...

Enter chat numbers to monitor (comma-separated, e.g., '1,2,3')
Or press Enter to monitor ALL chats: 1,2

✅ Monitoring 2 selected chat(s)

=============================================================
REAL-TIME LISTENER ACTIVE
=============================================================

Waiting for new messages...
All new messages will be automatically ingested into the knowledge base.

Press Ctrl+C to stop.

[New message received]
✅ Ingested: "Hey, are you there?" from John Doe in Private Chat
```

Press `Ctrl+C` to stop the listener.

### Production Deployment (Inngest)

For production, wrap the event listener in an Inngest function that runs continuously:

```python
# app/jobs/telegram_realtime.py (Future implementation)

from inngest import Inngest
from app.services.telethon_service import get_telethon_service
from app.core.config import settings

inngest_client = Inngest(app_id="compaytence")

@inngest_client.create_function(
    fn_id="telegram-realtime-listener",
    trigger=inngest.TriggerCron(cron="@startup"),  # Start once on deployment
)
async def telegram_realtime_listener(ctx, step):
    """
    Continuous Telegram message listener.
    Runs indefinitely until container restart or manual stop.
    """
    service = get_telethon_service()
    await service.initialize(session_string=settings.telegram_session_string)

    # This blocks and runs forever
    await service.start_realtime_listener(chat_ids=None)  # Monitor all chats
```

**Deployment Notes:**
- Function runs continuously (not event-triggered)
- Auto-restarts on container restart
- Monitors all connected chats by default
- Can filter to specific chat_ids if needed
- No polling required - Telegram pushes events

**See:** `Week 4: Background Processing & Inngest Integration` in PROJECT_CHECKLIST.md

## Testing

### Test Script: Connection and History

```bash
uv run python scripts/test_telegram.py
```

**Test Modes:**

1. **Connection Test** - Verify authentication and list dialogs
2. **Historical Ingestion Test** - Fetch messages from selected chat
3. **Full Integration Test** - End-to-end test with API endpoints

### Manual API Testing

```bash
# 1. List dialogs
curl http://localhost:8000/api/v1/telegram/dialogs | jq

# 2. Ingest history (use peer_ref from step 1)
curl -X POST http://localhost:8000/api/v1/telegram/ingest-historical \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "u:123456789:abc123def456",
    "limit": 10
  }' | jq

# 3. Check Supabase for ingested messages
# Visit Supabase dashboard → documents table
# Filter: source = 'telegram'
```

### Debugging Tips

**Issue:** "Could not find the input entity"
- **Solution:** Use peer_ref from `/dialogs` endpoint instead of bare ID

**Issue:** "Telethon client not authorized"
- **Solution:** Re-run `scripts/telegram_auth.py` to generate new session string

**Issue:** "0 messages ingested"
- **Check:** `total_fetched` count in API response
- **Check:** Are messages in the date range you specified?
- **Check:** Do messages have text content? (Media-only messages are skipped)
- **Check:** Server logs for detailed message-by-message processing

**Issue:** Event listener not receiving messages
- **Check:** Is listener running? (should block indefinitely)
- **Check:** Are you sending messages to monitored chats?
- **Check:** Check server logs for real-time ingestion events

## Production Deployment

### Railway Deployment

1. **Add Environment Variables** in Railway dashboard:
   ```
   TELEGRAM_API_ID=...
   TELEGRAM_API_HASH=...
   TELEGRAM_SESSION_STRING=...
   TELEGRAM_PHONE_NUMBER=...
   ```

2. **Deploy** - Railway auto-deploys on push to main/staging/dev

3. **Verify** - Check `/api/v1/telegram/status`

### Environment-Specific Configuration

**Development:**
```bash
TELEGRAM_SESSION_STRING=<dev_session>
```

**UAT:**
```bash
TELEGRAM_SESSION_STRING=<uat_session>
```

**Production:**
```bash
TELEGRAM_SESSION_STRING=<prod_session>
```

Each environment should use a separate Telegram account or session to avoid conflicts.

### Security Best Practices

1. **Never commit session strings** - Use environment variables only
2. **Rotate session strings periodically** - Re-authenticate every 90 days
3. **Use dedicated Telegram account** - Don't use personal account in production
4. **Monitor for unauthorized access** - Check Telegram Security settings regularly
5. **Implement rate limiting** - Respect Telegram API limits (30 requests/second)

## Data Model

### Documents Table Schema

```typescript
{
  id: UUID,
  title: string,  // "Telegram: John Doe in Dev Team - Hey, are you there?..."
  content: string,  // Full message text
  embedding: float[],  // OpenAI text-embedding-3-small (1536 dimensions)
  source: "telegram",
  source_id: string,  // "{chat_id}_{message_id}"
  source_metadata: {
    platform: "telegram",
    message_id: number,
    chat_id: number,
    chat_name: string,
    sender_id: number,
    sender_name: string,
    date: string,  // ISO 8601
    is_reply: boolean,
    is_forwarded: boolean,
    ingestion_type: "telethon"
  },
  metadata: {
    ingested_at: string  // ISO 8601
  },
  processing_status: "completed",
  created_at: timestamp,
  updated_at: timestamp
}
```

## Troubleshooting

### Common Issues

**1. Authentication Loops**
```
ValueError: Telethon client not authorized
```
**Solution:** Session string expired or invalid. Re-run `scripts/telegram_auth.py`

**2. Entity Resolution Failures**
```
ValueError: Could not find the input entity for PeerUser
```
**Solution:** Use `peer_ref` from `/dialogs` endpoint, not bare IDs

**3. No Messages Returned**
```
{
  "total_fetched": 0,
  "messages_ingested": 0
}
```
**Solutions:**
- Check date range (default is last 30 days)
- Verify you have access to the chat
- Check if chat has any text messages (media-only skipped)
- Try without `limit` parameter to fetch all available

**4. Real-Time Listener Stops**
```
Listener stopped unexpectedly
```
**Solutions:**
- Check network connectivity
- Verify session string is still valid
- Check Telegram Security settings for active sessions
- Review server logs for exceptions

### Support and References

- **Telethon Documentation:** https://docs.telethon.dev/
- **Telegram API:** https://core.telegram.org/api
- **Project Issues:** Check `PROJECT_CHECKLIST.md` for known issues
- **Testing Guide:** See `TESTING_TELEGRAM.md`

## Future Enhancements

- [ ] Inngest integration for production real-time sync
- [ ] Media file ingestion (images, documents, voice)
- [ ] Multi-account support for distributed ingestion
- [ ] Webhook fallback for Bot API compatibility
- [ ] Advanced filtering (keywords, senders, media types)
- [ ] Incremental sync (only new messages since last run)
- [ ] Rate limiting and backoff strategies
- [ ] Error recovery and automatic reconnection
