# Slack Integration Setup Guide

Complete guide for setting up the Compaytence AI Agent Slack integration.

## Features

- **Direct Messages**: Users can DM the bot for private AI assistance
- **@Mentions**: Mention the bot in channels to get responses in threads
- **File Processing**: Automatically ingest documents shared with the bot
- **Thread Replies**: Bot responds in threads to keep channels organized
- **Signature Verification**: Secure webhook validation using Slack's signing secret

## Prerequisites

- Slack workspace with admin permissions
- Compaytence Backend running and accessible via public URL (use ngrok for local development)
- OpenAI API key configured

## Step 1: Create Slack App

1. Go to [Slack API](https://api.slack.com/apps)
2. Click **Create New App**
3. Choose **From scratch**
4. Enter:
   - **App Name**: `Compaytence Agent` (or your preferred name)
   - **Workspace**: Select your workspace
5. Click **Create App**

## Step 2: Configure Bot Scopes

1. In your app settings, go to **OAuth & Permissions**
2. Scroll to **Scopes** → **Bot Token Scopes**
3. Add the following scopes:

   **Required for basic functionality:**
   - `chat:write` - Send messages
   - `im:history` - Read DM history
   - `im:read` - Read DM info
   - `channels:history` - Read channel messages (for @mentions)
   - `groups:history` - Read private channel messages
   - `mpim:history` - Read group DM messages

   **Required for file processing:**
   - `files:read` - Read file metadata
   - `files:write` - Upload files (if bot needs to share files)

   **Required for user context:**
   - `users:read` - Get user information

   **Required for app mentions:**
   - `app_mentions:read` - Read @mentions of the bot

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
   - `message.im` - Direct messages to the bot
   - `app_mention` - @mentions of the bot
   - `file_shared` - Files shared with the bot

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
SLACK_APP_TOKEN=xapp-your-app-token-here  # Optional: for Socket Mode

# Feature Flag
FEATURE_SLACK_INTEGRATION=true
```

## Step 7: Test Integration

### Test 1: URL Verification

Slack should have automatically verified your webhook URL when you enabled Event Subscriptions. If you see a green checkmark, this test passed.

### Test 2: Direct Message

1. In Slack, find your bot in the Apps section
2. Send a direct message: `Hello, what is Compaytence?`
3. The bot should respond with an AI-generated answer

### Test 3: Channel Mention

1. Invite the bot to a channel: `/invite @Compaytence Agent`
2. Mention the bot: `@Compaytence Agent What are your payment processing fees?`
3. The bot should respond in a thread

### Test 4: File Upload

1. In a DM with the bot, upload a document (PDF, DOCX, etc.)
2. Check your backend logs to see the file being processed
3. Ask a question about the document content
4. The bot should be able to answer based on the uploaded document

## Troubleshooting

### Webhook Returns 401 Unauthorized

**Cause**: Invalid signing secret or timestamp issues

**Solution**:
1. Verify `SLACK_SIGNING_SECRET` matches the value in Slack app settings
2. Check your server time is synchronized (signing verification rejects old requests)
3. Check backend logs for specific error messages

### Bot Doesn't Respond to Messages

**Possible causes:**

1. **Event not subscribed**: Verify you've subscribed to `message.im` and `app_mention` events
2. **Missing scopes**: Check bot has `chat:write` scope
3. **Webhook URL incorrect**: Verify URL in Event Subscriptions matches your backend
4. **Backend error**: Check backend logs for errors

### File Downloads Fail

**Cause**: Missing `files:read` scope or invalid bot token

**Solution**:
1. Add `files:read` scope in OAuth & Permissions
2. Reinstall the app to workspace to get new scopes
3. Update `SLACK_BOT_TOKEN` in `.env` with new token

### Bot Responds to Its Own Messages (Loop)

**Cause**: Not filtering bot messages

**Solution**: This is already handled in the code - bot messages are ignored based on `bot_id` field. If you still see loops, check your Slack app settings.

## Advanced Configuration

### Custom Bot Name and Icon

1. Go to **Basic Information** → **Display Information**
2. Set:
   - **Display Name**: Your bot's name (shown in Slack)
   - **Default Username**: Bot username
   - **App Icon**: Upload a logo (512x512px recommended)
3. Click **Save Changes**

### Add Slash Commands

1. Go to **Slash Commands**
2. Click **Create New Command**
3. Example command:
   - **Command**: `/ask-compaytence`
   - **Request URL**: `https://your-domain.com/api/v1/webhooks/slack/commands`
   - **Short Description**: Ask Compaytence AI a question
4. Click **Save**

### Interactive Components

1. Go to **Interactivity & Shortcuts**
2. Toggle **Interactivity** to **On**
3. Set **Request URL**: `https://your-domain.com/api/v1/webhooks/slack/interactive`
4. This enables buttons, select menus, and other interactive elements

## Monitoring

### Check Webhook Logs

View recent webhook deliveries:
1. Go to **Event Subscriptions**
2. Scroll to **Request Log**
3. View status codes and response times

### Backend Logs

Monitor backend logs for processing status:

```bash
# View live logs
tail -f logs/app.log

# Filter for Slack events
tail -f logs/app.log | grep "Slack"
```

### Test with curl

Test webhook endpoint directly:

```bash
# This will fail signature verification, but tests endpoint is reachable
curl -X POST https://your-domain.com/api/v1/webhooks/slack \
  -H "Content-Type: application/json" \
  -H "X-Slack-Request-Timestamp: $(date +%s)" \
  -H "X-Slack-Signature: v0=test" \
  -d '{"type": "url_verification", "challenge": "test123"}'

# Expected response (if signature check was valid):
# test123
```

## Rate Limits

Slack enforces rate limits on API calls:

- **Message posting**: 1 request per second per channel
- **Webhook responses**: Must respond within 3 seconds

The Compaytence backend handles this by:
- Responding to webhooks immediately with 200 OK
- Processing events asynchronously
- Posting responses after processing completes

## Security Best Practices

1. **Rotate secrets regularly**: Update `SLACK_SIGNING_SECRET` and `SLACK_BOT_TOKEN` periodically
2. **Use HTTPS only**: Never expose webhook over HTTP
3. **Validate signatures**: Always verify Slack request signatures (already implemented)
4. **Limit scopes**: Only request OAuth scopes you actually need
5. **Monitor activity**: Watch for unusual patterns in webhook logs

## Architecture

```
Slack User
    ↓
Slack API (Event)
    ↓
POST /api/v1/webhooks/slack
    ↓
Signature Verification
    ↓
Event Processing
    ↓
    ├─→ Message Event → Generate AI Response → Post to Slack
    ├─→ File Shared → Download → Ingest → Confirm
    └─→ App Mention → Generate AI Response → Reply in Thread
```

## Next Steps

- Set up WhatsApp integration: `docs/WHATSAPP_SETUP.md` (coming soon)
- Set up Telegram integration: `docs/TELEGRAM_SETUP.md` (coming soon)
- Configure observability: `docs/LANGFUSE_SETUP.md` (coming soon)

## Support

For issues with:
- **Slack App Configuration**: Check [Slack API docs](https://api.slack.com/docs)
- **Backend Integration**: Check backend logs and GitHub issues
- **Webhook Delivery**: Use Slack's Request Log feature
