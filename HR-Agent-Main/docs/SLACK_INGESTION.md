# Slack Knowledge Base Ingestion Guide

Complete guide for ingesting Slack messages and files into the Compaytence AI Agent knowledge base.

## Overview

The Slack integration serves as a **DATA SOURCE** for the knowledge base. It captures messages, threads, and file attachments from your Slack workspace to build the agent's knowledge.

**Important**: The agent does **NOT** respond to messages in Slack. Slack is purely for knowledge gathering. Users interact with the agent through the web portal or embeddable widget.

## Features

✅ **Real-time Message Capture**: Automatically ingests new messages via webhooks
✅ **Historical Backfill**: Fetch and ingest past conversations
✅ **File Processing**: Automatically processes PDF, DOCX, and other documents
✅ **Thread Support**: Captures full thread context
✅ **Channel Filtering**: Select specific channels to monitor

## Prerequisites

- Slack workspace with admin permissions
- Compaytence Backend running and accessible via public URL
- OpenAI API key configured for embeddings

## Step 1: Create Slack App

1. Go to [Slack API](https://api.slack.com/apps)
2. Click **Create New App**
3. Choose **From scratch**
4. Enter:
   - **App Name**: `Compaytence Knowledge Base` (or your preferred name)
   - **Workspace**: Select your workspace
5. Click **Create App**

## Step 2: Configure Bot Scopes

1. In your app settings, go to **OAuth & Permissions**
2. Scroll to **Scopes** → **Bot Token Scopes**
3. Add the following scopes:

   **Message Reading:**
   - `channels:history` - Read public channel messages
   - `groups:history` - Read private channel messages
   - `im:history` - Read direct messages
   - `mpim:history` - Read group DMs

   **Channel Information:**
   - `channels:read` - View basic channel info
   - `groups:read` - View private channel info

   **File Access:**
   - `files:read` - Access file content and metadata

   **User Information** (optional, for better context):
   - `users:read` - Get user information

## Step 3: Enable Event Subscriptions

1. Go to **Event Subscriptions**
2. Toggle **Enable Events** to **On**
3. Set **Request URL** to:
   ```
   https://your-domain.com/api/v1/webhooks/slack
   ```

   **For local development with ngrok:**
   ```bash
   # Start ngrok
   ngrok http 8000

   # Use the HTTPS URL
   https://abc123.ngrok.io/api/v1/webhooks/slack
   ```

4. Wait for Slack to verify the URL (you'll see a green checkmark)

5. Under **Subscribe to bot events**, add:
   - `message.channels` - Messages in public channels
   - `message.groups` - Messages in private channels
   - `message.im` - Direct messages
   - `message.mpim` - Group DMs
   - `file_shared` - Files shared in channels

6. Click **Save Changes**

## Step 4: Install App to Workspace

1. Go to **OAuth & Permissions**
2. Click **Install to Workspace**
3. Review permissions and click **Allow**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

## Step 5: Get Signing Secret

1. Go to **Basic Information**
2. Scroll to **App Credentials**
3. Copy the **Signing Secret**

## Step 6: Configure Backend

Add the following to your `.env` file:

```env
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here

# Feature Flag
FEATURE_SLACK_INTEGRATION=true
```

Restart your backend:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Step 7: Initial Historical Ingestion

After setting up the webhook, ingest historical messages to populate your knowledge base:

### Get Channel IDs

1. Open Slack
2. Right-click on a channel → View channel details
3. Scroll down to find the Channel ID (e.g., `C01234ABC56`)

### Trigger Historical Ingestion

**Using API:**

```bash
curl -X POST "http://localhost:8000/api/v1/sources/slack/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_ids": ["C01234ABC56", "C06789DEF12"],
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": null,
    "limit_per_channel": null
  }'
```

**Response:**

```json
{
  "total_channels": 2,
  "total_ingested": 1547,
  "total_failed": 3,
  "results": [
    {
      "channel_id": "C01234ABC56",
      "ingested": 823,
      "failed": 2
    },
    {
      "channel_id": "C06789DEF12",
      "ingested": 724,
      "failed": 1
    }
  ]
}
```

### Monitor Progress

Check backend logs to see ingestion progress:

```bash
tail -f logs/app.log | grep "Slack"
```

You'll see logs like:

```
2024-01-15 10:30:00 - app.services.slack - INFO - Fetched 1000 messages from channel general
2024-01-15 10:30:15 - app.services.slack - INFO - Ingested Slack message: 1705318200.123456 from channel general
```

## Step 8: Verify Ingestion

### Check Document Count

```bash
curl "http://localhost:8000/api/v1/documents/?source=slack"
```

### Test Agent Query

Ask the agent a question that should be answerable from Slack content:

```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What did we discuss about the Q1 roadmap?",
    "session_id": "test-session"
  }'
```

The agent should reference Slack messages in its sources.

## How It Works

### Real-Time Ingestion

```
Slack Channel (new message posted)
    ↓
Slack Events API (webhook triggers)
    ↓
POST /api/v1/webhooks/slack
    ↓
SlackIngestionService.process_message_event()
    ↓
Generate Embedding
    ↓
Store in Supabase Vector Database
```

### Historical Ingestion

```
Admin Triggers Ingestion
    ↓
POST /api/v1/sources/slack/ingest
    ↓
SlackIngestionService.fetch_historical_messages()
    ↓
Slack Web API (conversations.history)
    ↓
Paginate through all messages
    ↓
Generate Embeddings (batch)
    ↓
Store in Supabase Vector Database
```

## Monitoring

### Check Slack Event Deliveries

1. Go to **Event Subscriptions** in your Slack app settings
2. Scroll to **Request Log**
3. View recent webhook deliveries and status codes

All should show `200 OK`

### Backend Health

```bash
# Check server logs
tail -f logs/app.log

# Check source status
curl "http://localhost:8000/api/v1/sources/status"
```

## Troubleshooting

### Webhook Returns 401 Unauthorized

**Cause**: Invalid signing secret

**Solution**:
1. Verify `SLACK_SIGNING_SECRET` in `.env` matches Slack app settings
2. Restart backend after changing `.env`

### Messages Not Being Ingested

**Possible causes:**

1. **Event not subscribed**: Verify you've subscribed to `message.channels` and `file_shared`
2. **Bot not in channel**: Invite bot to channel: `/invite @Your Bot Name`
3. **Missing scopes**: Check bot has all required scopes
4. **Webhook URL incorrect**: Verify URL in Event Subscriptions

**Debug steps:**

```bash
# Check recent webhook logs
tail -f logs/app.log | grep "Slack webhook"

# Check Slack Request Log for errors
# Go to Event Subscriptions → Request Log
```

### Historical Ingestion Returns Empty Results

**Cause**: Bot doesn't have access to channel history before it was added

**Solution**: The bot can only read messages from the time it was added to the channel onwards. To ingest older messages, you need to use a user token with appropriate permissions (advanced setup).

### File Downloads Fail

**Cause**: Missing `files:read` scope or invalid bot token

**Solution**:
1. Add `files:read` scope in OAuth & Permissions
2. Reinstall app to workspace to get updated scopes
3. Update `SLACK_BOT_TOKEN` in `.env` with new token

## Advanced Configuration

### Selective Channel Monitoring

You can control which channels the bot monitors by only inviting it to specific channels:

```
/invite @Your Bot Name
```

The bot will only receive events from channels it's a member of.

### Rate Limits

Slack enforces rate limits:

- **Webhook responses**: Must respond within 3 seconds (handled automatically)
- **API calls**: ~1 request per second (historical ingestion is throttled automatically)

The backend handles this with:
- Immediate 200 OK responses to webhooks
- Async background processing
- Automatic pagination and throttling for historical ingestion

### Data Privacy

**What gets ingested:**
- Message text content
- File attachments (processed and chunked)
- Timestamp and channel metadata
- User IDs (not names, for privacy)

**What doesn't get ingested:**
- Bot messages
- Message edits/deletions
- Reactions and emoji
- User profiles or personal data

## Security Best Practices

1. **Rotate secrets regularly**: Update `SLACK_SIGNING_SECRET` and `SLACK_BOT_TOKEN` periodically
2. **Use HTTPS only**: Never expose webhook over HTTP
3. **Validate signatures**: Always verify Slack request signatures (implemented by default)
4. **Limit scopes**: Only request OAuth scopes you actually need
5. **Monitor activity**: Watch for unusual patterns in webhook logs
6. **Channel access**: Only invite bot to channels with relevant knowledge

## Next Steps

- **Query Your Knowledge**: Test the agent with questions about Slack content
- **Set up WhatsApp**: `docs/WHATSAPP_INGESTION.md` (coming soon)
- **Set up Telegram**: `docs/TELEGRAM_INGESTION.md` (coming soon)
- **Configure Frontend**: Build the chat portal for users to query the knowledge

## API Reference

### POST /api/v1/webhooks/slack

Webhook endpoint for real-time message capture.

**Headers:**
- `X-Slack-Request-Timestamp`: Request timestamp
- `X-Slack-Signature`: HMAC SHA256 signature

**Body**: Slack event payload

**Response**: 200 OK

### POST /api/v1/sources/slack/ingest

Trigger historical message ingestion.

**Body:**
```json
{
  "channel_ids": ["C01234ABC56"],
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": null,
  "limit_per_channel": 1000
}
```

**Response:**
```json
{
  "total_channels": 1,
  "total_ingested": 823,
  "total_failed": 2,
  "results": [...]
}
```

### GET /api/v1/sources/status

Get status of all connected data sources.

**Response:**
```json
{
  "sources": [
    {
      "source_type": "slack",
      "connected": true,
      "last_sync": "2024-01-15T10:30:00Z",
      "total_documents": 1547,
      "health_status": "healthy"
    }
  ]
}
```

## Support

For issues with:
- **Slack App Configuration**: Check [Slack API docs](https://api.slack.com/docs)
- **Backend Integration**: Check backend logs and GitHub issues
- **Webhook Delivery**: Use Slack's Request Log feature
