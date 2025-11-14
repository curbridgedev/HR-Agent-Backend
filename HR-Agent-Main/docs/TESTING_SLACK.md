# Testing Slack Ingestion

Quick testing guide for Slack knowledge base ingestion.

## Testing Options

You have two approaches:

### Option A: Quick Test with Test Slack Workspace (Recommended)

Create a free test Slack workspace for safe testing.

### Option B: Test with Real Workspace

Test directly with your production Slack workspace (requires admin permissions).

---

## Option A: Quick Test (Test Workspace)

### 1. Create Test Slack Workspace

1. Go to https://slack.com/create
2. Sign up with your email
3. Create a workspace named "Compaytence Test"
4. Create a test channel: #test-knowledge

### 2. Create Slack App

1. Go to https://api.slack.com/apps
2. Click **Create New App** → **From scratch**
3. App Name: `Compaytence Test`
4. Workspace: Select your test workspace
5. Click **Create App**

### 3. Add OAuth Scopes

1. Go to **OAuth & Permissions**
2. Under **Bot Token Scopes**, add:
   - `channels:history`
   - `channels:read`
   - `files:read`
   - `users:read`

3. Click **Install to Workspace** → **Allow**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 4. Get Signing Secret

1. Go to **Basic Information**
2. Under **App Credentials**, copy the **Signing Secret**

### 5. Configure Backend

Add to `.env`:

```env
SLACK_BOT_TOKEN=xoxb-paste-your-token-here
SLACK_SIGNING_SECRET=paste-your-secret-here
```

### 6. Add Bot to Channel

1. In Slack, go to #test-knowledge
2. Type: `/invite @Compaytence Test`
3. Press Enter

### 7. Post Some Test Messages

Post a few test messages in #test-knowledge:

```
Hey team, our payment processing fees are 2.5% for credit cards.

For bank transfers, we charge a flat $5 fee.

Refunds are processed within 5-7 business days.
```

### 8. Get Channel ID

1. Right-click on #test-knowledge → **View channel details**
2. Scroll down to find the **Channel ID** (e.g., `C01234ABC56`)
3. Copy it

### 9. Run Test Script

```bash
uv run python scripts/test_slack_ingestion.py
```

When prompted, paste your channel ID.

**Expected Output:**

```
🧪 Testing Slack Ingestion
============================================================

1. Checking server status...
   ✅ Server is running

2. Checking Slack configuration...
   ✅ Bot Token: xoxb-12345678...
   ✅ Signing Secret: abc12345...

3. Checking sources status endpoint...
   ✅ Sources endpoint working
   Sources: slack, admin_upload

4. Testing historical ingestion endpoint...
   Enter a Slack channel ID to test: C01234ABC56

   Testing ingestion for channel: C01234ABC56
   Fetching last 7 days (max 10 messages)...

   Status: 200

   ✅ Ingestion successful!
   Total ingested: 3
   Total failed: 0

   Channel: C01234ABC56
   - Ingested: 3
   - Failed: 0

5. Verifying messages in database...
   ✅ Found 3 Slack documents in database

   Recent Slack documents:
   - Slack: test-knowledge - Hey team, our payment processing...
   - Slack: test-knowledge - For bank transfers, we charge...
   - Slack: test-knowledge - Refunds are processed within...

============================================================

✅ Testing complete!
```

### 10. Test Agent Query

Now test if the agent can answer from Slack content:

```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the payment processing fees?",
    "session_id": "test-123"
  }' | jq
```

**Expected**: Agent should reference the Slack messages about 2.5% credit card fees.

---

## Option B: Test with Real Workspace

**⚠️ Warning**: This will ingest real messages. Make sure you:
- Have admin permissions
- Are okay with ingesting production messages
- Understand data privacy implications

Follow the same steps as Option A, but use your real workspace and select specific channels carefully.

---

## Manual Testing via API

### Test 1: Webhook Endpoint

```bash
# This won't work without Slack's signature, but tests the endpoint exists
curl -X POST "http://localhost:8000/api/v1/webhooks/slack" \
  -H "Content-Type: application/json" \
  -H "X-Slack-Request-Timestamp: 1234567890" \
  -H "X-Slack-Signature: v0=test"

# Expected: 401 Unauthorized (invalid signature)
```

### Test 2: Historical Ingestion

```bash
# Replace with your channel ID
curl -X POST "http://localhost:8000/api/v1/sources/slack/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_ids": ["C01234ABC56"],
    "start_date": "2024-01-01T00:00:00Z",
    "limit_per_channel": 10
  }' | jq
```

### Test 3: Check Ingested Documents

```bash
# List Slack documents
curl "http://localhost:8000/api/v1/documents/?source=slack" | jq

# Response shows:
{
  "documents": [
    {
      "id": "uuid",
      "title": "Slack: test-knowledge - Hey team...",
      "source": "slack",
      "processing_status": "completed",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 3,
  "page": 1
}
```

### Test 4: Query Agent

```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What did we discuss about payment fees?",
    "session_id": "test-456"
  }' | jq '.sources'
```

Should return sources from Slack with similarity scores.

---

## Webhook Testing (Real-Time Ingestion)

To test real-time message capture, you need a public URL for Slack webhooks.

### Using ngrok (Local Testing)

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from ngrok.com

# Start ngrok
ngrok http 8000

# You'll see:
# Forwarding: https://abc123.ngrok.io -> http://localhost:8000
```

### Configure Slack Webhook

1. In Slack App settings, go to **Event Subscriptions**
2. Enable Events
3. Set Request URL: `https://abc123.ngrok.io/api/v1/webhooks/slack`
4. Wait for verification ✅
5. Under **Subscribe to bot events**, add:
   - `message.channels`
   - `file_shared`
6. Save Changes

### Test Real-Time

1. Post a new message in your test channel
2. Check backend logs:
   ```bash
   tail -f logs/app.log | grep Slack
   ```

3. You should see:
   ```
   INFO - Ingesting Slack message from user U123456 in channel C789012
   INFO - Ingested Slack message: 1705318200.123456 from channel test-knowledge
   ```

4. Verify in database:
   ```bash
   curl "http://localhost:8000/api/v1/documents/?source=slack" | jq '.total'
   ```

---

## Troubleshooting

### Error: "Invalid signature"

**Cause**: Slack signing secret doesn't match

**Fix**:
1. Check `SLACK_SIGNING_SECRET` in `.env`
2. Restart backend after changing `.env`

### Error: "channel_not_found"

**Cause**: Bot not in channel or wrong channel ID

**Fix**:
1. Invite bot to channel: `/invite @YourBotName`
2. Verify channel ID (right-click channel → View details)

### Error: "missing_scope"

**Cause**: Missing OAuth permissions

**Fix**:
1. Add scopes in **OAuth & Permissions**:
   - `channels:history`
   - `channels:read`
   - `files:read`
2. **Reinstall app to workspace** to get new scopes
3. Copy the new bot token
4. Update `SLACK_BOT_TOKEN` in `.env`

### Error: "not_authed" or "invalid_auth"

**Cause**: Invalid or expired bot token

**Fix**:
1. Go to **OAuth & Permissions**
2. Reinstall app if needed
3. Copy new bot token
4. Update `.env`
5. Restart backend

### No messages ingested

**Check**:
1. Bot added to channel? `/invite @BotName`
2. Messages posted AFTER bot was added? (bot can't see old messages without user token)
3. Bot has `channels:history` scope?
4. Check backend logs for errors

---

## Success Criteria

✅ Historical ingestion returns `total_ingested > 0`
✅ Documents appear in `/api/v1/documents/?source=slack`
✅ Agent can answer questions using Slack content
✅ Real-time webhook receives 200 OK from Slack
✅ New messages auto-ingest within seconds

---

## Next Steps After Successful Test

1. ✅ **Slack working** - Messages ingesting successfully
2. **Scale up**: Add more channels for full knowledge base
3. **WhatsApp**: Implement similar ingestion for WhatsApp
4. **Telegram**: Add Telegram ingestion
5. **Production**: Deploy with real Slack workspace

---

## Need Help?

**Check logs**:
```bash
tail -f logs/app.log | grep Slack
```

**Common issues**: See Troubleshooting section above

**Slack API errors**: https://api.slack.com/methods/conversations.history#errors
