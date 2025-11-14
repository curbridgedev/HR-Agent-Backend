# Telegram Integration Testing Guide

Comprehensive testing guide for Telegram integration using Telethon.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Scripts](#test-scripts)
3. [API Endpoint Testing](#api-endpoint-testing)
4. [Real-Time Sync Testing](#real-time-sync-testing)
5. [Integration Testing](#integration-testing)
6. [Performance Testing](#performance-testing)
7. [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites

```bash
# 1. Ensure environment is configured
cat .env | grep TELEGRAM

# Expected output:
# TELEGRAM_API_ID=12345678
# TELEGRAM_API_HASH=abc123def456...
# TELEGRAM_SESSION_STRING=1AbCd...
# TELEGRAM_PHONE_NUMBER=+1234567890

# 2. Install dependencies
uv sync

# 3. Start the server
uv run uvicorn app.main:app --reload
```

### Quick Smoke Test

```bash
# Check integration status
curl http://localhost:8000/api/v1/telegram/status | jq

# Expected: status = "configured"
```

## Test Scripts

### 1. Authentication Test

**Script:** `scripts/telegram_auth.py`

**Purpose:** Generate session string for new account or re-authenticate.

**Usage:**
```bash
uv run python scripts/telegram_auth.py
```

**Test Cases:**

| Test Case | Input | Expected Output | Status |
|-----------|-------|-----------------|--------|
| New authentication | Phone number, code, 2FA password | Session string generated | ✅ |
| Re-authentication | Existing session string | "Already authenticated" | ✅ |
| Invalid phone | Wrong format | Error message | ⚠️ |
| Invalid code | Wrong code | Error message | ⚠️ |
| Invalid 2FA | Wrong password | Error message | ⚠️ |

**Validation:**
```bash
# Copy session string to .env
export TELEGRAM_SESSION_STRING="<generated_string>"

# Verify authentication
uv run python -c "
from app.services.telethon_service import get_telethon_service
from app.core.config import settings
import asyncio

async def test():
    service = get_telethon_service()
    await service.initialize(session_string=settings.telegram_session_string)
    me = await service.client.get_me()
    print(f'✅ Authenticated as: {me.first_name} (@{me.username})')
    await service.client.disconnect()

asyncio.run(test())
"
```

### 2. Connection and Dialog Test

**Script:** `scripts/test_telegram.py` (Mode 1)

**Purpose:** Test Telegram connection and list accessible dialogs.

**Usage:**
```bash
uv run python scripts/test_telegram.py
# Select option: 1
```

**Test Cases:**

| Test Case | Expected Output | Status |
|-----------|-----------------|--------|
| Connect to Telegram | "✅ Connected!" | ✅ |
| Get user info | Display username, first name | ✅ |
| List dialogs | Display 10-20 chats | ✅ |
| Dialog metadata | ID, name, type, peer_ref | ✅ |
| Disconnect | Clean disconnect | ✅ |

**Expected Output:**
```
=============================================================
TELEGRAM CONNECTION TEST
=============================================================

1. Connecting to Telegram...
✅ Connected to Telegram!

2. Getting user information...
Logged in as: John Doe
Username: @johndoe
User ID: 123456789

3. Listing your dialogs (chats/channels/groups)...
Found 10 dialogs:

#    Type       Name                                     ID
------------------------------------------------------------
1    User       Jane Smith                               987654321
2    Group      Dev Team                                 -100123456789
3    Channel    Announcements                            -100987654321
4    User       Bob Johnson                              111222333
...

✅ Connection test completed successfully!
```

**Validation Checklist:**
- [ ] Connection established without errors
- [ ] User information displayed correctly
- [ ] At least 1 dialog returned
- [ ] Each dialog has: id, name, type, peer_ref
- [ ] Peer references in correct format (u:/c:/ch:)
- [ ] Clean disconnection

### 3. Historical Ingestion Test

**Script:** `scripts/test_telegram.py` (Mode 2)

**Purpose:** Test historical message fetching and ingestion.

**Usage:**
```bash
uv run python scripts/test_telegram.py
# Select option: 2
# Choose a chat from the list
```

**Test Cases:**

| Test Case | Limit | Expected Result | Status |
|-----------|-------|-----------------|--------|
| Small batch | 5 | Fetch 5 messages | ✅ |
| Medium batch | 50 | Fetch 50 messages | ✅ |
| Large batch | 500 | Fetch 500+ messages | ⚠️ |
| All messages | None | Fetch all available | ⚠️ |
| Empty chat | 10 | 0 messages fetched | ✅ |
| Media-only chat | 10 | Skipped (no text) | ✅ |

**Expected Output:**
```
=============================================================
TELEGRAM HISTORICAL INGESTION TEST
=============================================================

1. Connecting to Telegram...
✅ Connected to Telegram!

2. Listing your dialogs...
[Dialogs listed]

Enter chat number to test (1-10): 2

You selected: Dev Team (ID: -100123456789)
How many messages to fetch? (press Enter for default 5): 10

3. Fetching historical messages...
Chat: Dev Team
Limit: 10 messages
Date range: Last 30 days (2024-01-01 to 2024-01-31)

Progress:
[████████████████████████████████] 100% (10/10 messages)

4. Ingestion Results:
=====================================
Total fetched:    10
Messages ingested: 8
Messages skipped:  2 (no text content)
Messages failed:   0

✅ Historical ingestion test completed!

5. Verifying in database...
SELECT COUNT(*) FROM documents WHERE source = 'telegram'
  AND source_metadata->>'chat_id' = '-100123456789'
Result: 8 messages found

✅ Verification completed!
```

**Validation Checklist:**
- [ ] Messages fetched successfully
- [ ] `total_fetched` matches expected count
- [ ] Messages with text content ingested
- [ ] Media-only messages skipped
- [ ] Embeddings generated for each message
- [ ] Documents stored in Supabase
- [ ] `source_metadata` contains all expected fields
- [ ] No errors in server logs

### 4. Real-Time Sync Test

**Script:** `scripts/test_telegram_realtime.py`

**Purpose:** Test real-time message capture and ingestion.

**Usage:**
```bash
uv run python scripts/test_telegram_realtime.py
# Select chats to monitor or press Enter for ALL
# Send test messages from another device
# Press Ctrl+C to stop
```

**Test Cases:**

| Test Case | Action | Expected Result | Status |
|-----------|--------|-----------------|--------|
| Single chat monitoring | Select 1 chat | Only messages from that chat | ✅ |
| Multiple chat monitoring | Select 2-3 chats | Messages from selected chats | ✅ |
| All chats monitoring | Press Enter (no selection) | Messages from all chats | ✅ |
| Incoming message | Send test message | Message captured and ingested | ✅ |
| Outgoing message | Send from monitored account | Should be ignored (incoming=True) | ✅ |
| Media message | Send image/video | Skipped (no text) | ✅ |
| Text + media | Send text with image | Text ingested, media skipped | ⚠️ |
| Long running | Let run for 10+ minutes | No memory leaks or crashes | ⚠️ |
| Graceful shutdown | Press Ctrl+C | Clean disconnect | ✅ |

**Expected Output:**
```
=============================================================
TELEGRAM REAL-TIME SYNC TEST
=============================================================

This will listen for new messages and automatically ingest them.
Press Ctrl+C to stop.

1. Connecting to Telegram...
✅ Connected to Telegram!

2. Fetching your chats...
Found 10 recent chats:

#    Type       Name
------------------------------------------------------------
1    User       Jane Smith
2    Group      Dev Team
3    Channel    Announcements

Enter chat numbers to monitor (comma-separated, e.g., '1,2,3')
Or press Enter to monitor ALL chats: 1,2

✅ Monitoring 2 selected chat(s)

=============================================================
REAL-TIME LISTENER ACTIVE
=============================================================

Waiting for new messages...
All new messages will be automatically ingested into the knowledge base.

Press Ctrl+C to stop.

[14:32:15] New message from Jane Smith: "Hey, testing the listener!"
           ✅ Ingested message (ID: 12345)

[14:33:02] New message from Dev Team: "Deployment successful!"
           ✅ Ingested message (ID: 12346)

[14:35:20] Media message from Jane Smith (no text content)
           ⏭️  Skipped (media only)

^C
⏹️  Stopping listener...
✅ Listener stopped.
Disconnected from Telegram.

Test cancelled.
```

**Validation Checklist:**
- [ ] Listener starts without errors
- [ ] Messages captured in real-time (<1s delay)
- [ ] Only monitored chats produce events
- [ ] Messages ingested immediately
- [ ] Embeddings generated correctly
- [ ] No memory leaks after long running
- [ ] Clean shutdown on Ctrl+C
- [ ] Verify messages in Supabase

**Real-Time Testing Procedure:**

1. **Start listener:**
   ```bash
   uv run python scripts/test_telegram_realtime.py
   ```

2. **Send test messages from another device:**
   - Open Telegram on phone/another computer
   - Send test messages to monitored chats
   - Watch terminal for ingestion confirmations

3. **Verify in database:**
   ```sql
   -- In Supabase SQL Editor
   SELECT
     title,
     content,
     source_metadata->>'sender_name' as sender,
     created_at
   FROM documents
   WHERE source = 'telegram'
   ORDER BY created_at DESC
   LIMIT 10;
   ```

4. **Monitor performance:**
   ```bash
   # Watch memory usage
   ps aux | grep python

   # Watch logs
   tail -f logs/app.log
   ```

5. **Stop listener:**
   - Press `Ctrl+C`
   - Verify clean shutdown
   - Check no zombie processes

## API Endpoint Testing

### Test Environment Setup

```bash
# Start server
uv run uvicorn app.main:app --reload

# In another terminal, export base URL
export API_BASE="http://localhost:8000/api/v1"
```

### Endpoint 1: GET /telegram/status

**Purpose:** Check configuration status

**Test Cases:**

```bash
# 1. Configured state (all env vars set)
curl -X GET "$API_BASE/telegram/status" | jq

# Expected:
{
  "status": "configured",
  "api_id_set": true,
  "api_hash_set": true,
  "session_string_set": true,
  "phone_number_set": true,
  "message": "Telegram integration is ready"
}

# 2. Unconfigured state (missing session string)
unset TELEGRAM_SESSION_STRING
curl -X GET "$API_BASE/telegram/status" | jq

# Expected:
{
  "status": "not_configured",
  "session_string_set": false,
  "message": "Please run authentication script to get session string"
}
```

### Endpoint 2: GET /telegram/dialogs

**Purpose:** List accessible chats

**Test Cases:**

```bash
# 1. Default limit (50)
curl -X GET "$API_BASE/telegram/dialogs" | jq

# 2. Custom limit
curl -X GET "$API_BASE/telegram/dialogs?limit=10" | jq

# 3. Large limit
curl -X GET "$API_BASE/telegram/dialogs?limit=200" | jq

# Expected response structure:
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
      "peer_ref": "u:123456789:abc123def"
    }
  ]
}
```

**Validation:**
- [ ] Status code: 200
- [ ] Response matches schema
- [ ] `total` matches array length
- [ ] Each dialog has valid peer_ref
- [ ] Dialog types correctly identified
- [ ] Response time <2s

### Endpoint 3: POST /telegram/ingest-historical

**Purpose:** Fetch and ingest historical messages

**Test Cases:**

```bash
# Get peer_ref from /dialogs first
export CHAT_PEER_REF="u:123456789:abc123def"

# 1. Small batch (recommended for testing)
curl -X POST "$API_BASE/telegram/ingest-historical" \
  -H "Content-Type: application/json" \
  -d "{
    \"chat_id\": \"$CHAT_PEER_REF\",
    \"limit\": 10
  }" | jq

# 2. With date range
curl -X POST "$API_BASE/telegram/ingest-historical" \
  -H "Content-Type: application/json" \
  -d "{
    \"chat_id\": \"$CHAT_PEER_REF\",
    \"start_date\": \"2024-01-01T00:00:00Z\",
    \"end_date\": \"2024-01-31T23:59:59Z\"
  }" | jq

# 3. All messages (no limit, last 30 days)
curl -X POST "$API_BASE/telegram/ingest-historical" \
  -H "Content-Type: application/json" \
  -d "{
    \"chat_id\": \"$CHAT_PEER_REF\"
  }" | jq

# 4. Using username instead of peer_ref
curl -X POST "$API_BASE/telegram/ingest-historical" \
  -H "Content-Type: application/json" \
  -d "{
    \"chat_id\": \"@username\",
    \"limit\": 10
  }" | jq

# Expected response:
{
  "status": "success",
  "message": "Fetched 150 messages: 100 ingested, 45 skipped (no text), 5 failed",
  "chat_id": "u:123456789:abc123def",
  "messages_ingested": 100,
  "messages_failed": 5,
  "messages_skipped": 45,
  "total_fetched": 150
}
```

**Validation:**
- [ ] Status code: 200
- [ ] `total_fetched` = `ingested + skipped + failed`
- [ ] Messages appear in Supabase
- [ ] Embeddings generated
- [ ] `source_metadata` complete
- [ ] Response time reasonable (<30s for 100 messages)

**Error Cases:**

```bash
# 1. Invalid chat_id
curl -X POST "$API_BASE/telegram/ingest-historical" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "invalid_id"}' | jq

# Expected: 500 error with message

# 2. Missing session string
unset TELEGRAM_SESSION_STRING
curl -X POST "$API_BASE/telegram/ingest-historical" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\": \"$CHAT_PEER_REF\"}" | jq

# Expected: 400 error, "Configuration error"

# 3. Unauthorized (invalid session)
export TELEGRAM_SESSION_STRING="invalid"
curl -X POST "$API_BASE/telegram/ingest-historical" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\": \"$CHAT_PEER_REF\"}" | jq

# Expected: 400 error, "Client not authorized"
```

### Endpoint 4: POST /upload/telegram-export

**Purpose:** Upload manual Telegram Desktop export

**Test Cases:**

```bash
# 1. Valid export file
curl -X POST "$API_BASE/upload/telegram-export" \
  -F "file=@telegram_export.txt" | jq

# Expected:
{
  "status": "success",
  "messages_ingested": 25,
  "messages_failed": 0
}

# 2. Invalid file format
echo "not a telegram export" > test.txt
curl -X POST "$API_BASE/upload/telegram-export" \
  -F "file=@test.txt" | jq

# Expected: Partial success or error

# 3. Wrong file extension
curl -X POST "$API_BASE/upload/telegram-export" \
  -F "file=@export.pdf" | jq

# Expected: 400 error, "Only .txt files supported"
```

## Integration Testing

### End-to-End Test

**Scenario:** Complete integration flow from authentication to message retrieval

```bash
#!/bin/bash
# test_e2e_telegram.sh

set -e

echo "=== Telegram Integration E2E Test ==="

# 1. Check configuration
echo "1. Checking configuration..."
STATUS=$(curl -s "$API_BASE/telegram/status" | jq -r '.status')
if [ "$STATUS" != "configured" ]; then
  echo "❌ Not configured"
  exit 1
fi
echo "✅ Configuration valid"

# 2. List dialogs
echo "2. Listing dialogs..."
DIALOGS=$(curl -s "$API_BASE/telegram/dialogs?limit=5")
DIALOG_COUNT=$(echo "$DIALOGS" | jq '.total')
echo "✅ Found $DIALOG_COUNT dialogs"

# 3. Get first dialog peer_ref
PEER_REF=$(echo "$DIALOGS" | jq -r '.dialogs[0].peer_ref')
echo "Testing with: $PEER_REF"

# 4. Ingest historical messages
echo "3. Ingesting historical messages..."
RESULT=$(curl -s -X POST "$API_BASE/telegram/ingest-historical" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\": \"$PEER_REF\", \"limit\": 5}")

INGESTED=$(echo "$RESULT" | jq '.messages_ingested')
echo "✅ Ingested $INGESTED messages"

# 5. Verify in database (requires psql or Supabase client)
echo "4. Verifying in database..."
# Add database verification here

echo "=== E2E Test Complete ==="
```

Run with:
```bash
chmod +x test_e2e_telegram.sh
./test_e2e_telegram.sh
```

## Performance Testing

### Load Testing

**Tool:** Apache Bench (ab) or k6

```bash
# Install k6
# brew install k6  # macOS
# apt-get install k6  # Linux

# Create load test script
cat > load_test_telegram.js <<'EOF'
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 10 },  // Ramp up to 10 users
    { duration: '1m', target: 10 },   // Stay at 10 users
    { duration: '30s', target: 0 },   // Ramp down
  ],
};

export default function () {
  // Test /status endpoint
  let res = http.get('http://localhost:8000/api/v1/telegram/status');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });

  sleep(1);
}
EOF

# Run load test
k6 run load_test_telegram.js
```

**Expected Results:**
- 95th percentile response time <500ms
- Zero errors under 10 concurrent users
- No memory leaks

### Benchmark: Message Ingestion Rate

```python
# scripts/benchmark_ingestion.py
import asyncio
import time
from app.services.telethon_service import get_telethon_service
from app.core.config import settings

async def benchmark():
    service = get_telethon_service()
    await service.initialize(session_string=settings.telegram_session_string)

    # Get a chat with many messages
    dialogs = await service.list_dialogs(limit=10)
    chat_id = dialogs[0]["peer_ref"]

    # Benchmark 100 messages
    start_time = time.time()
    result = await service.fetch_historical_messages(chat_id=chat_id, limit=100)
    end_time = time.time()

    elapsed = end_time - start_time
    rate = result["messages_ingested"] / elapsed

    print(f"Ingested: {result['messages_ingested']} messages")
    print(f"Time: {elapsed:.2f}s")
    print(f"Rate: {rate:.2f} messages/second")

    await service.client.disconnect()

asyncio.run(benchmark())
```

**Expected Rate:** 10-30 messages/second (depends on embedding generation)

## Troubleshooting

### Common Test Failures

**1. Authentication Failures**

```
ValueError: Telethon client not authorized
```

**Debug steps:**
```bash
# Check session string
echo $TELEGRAM_SESSION_STRING | wc -c
# Should be >100 characters

# Re-authenticate
uv run python scripts/telegram_auth.py

# Update .env with new session string
```

**2. Entity Resolution Errors**

```
ValueError: Could not find the input entity for PeerUser
```

**Debug steps:**
```bash
# Always use peer_ref from /dialogs
curl "$API_BASE/telegram/dialogs" | jq '.dialogs[0].peer_ref'

# Don't use bare IDs
# ❌ Bad: "chat_id": 123456789
# ✅ Good: "chat_id": "u:123456789:abc123def"
```

**3. No Messages Fetched**

```json
{
  "total_fetched": 0,
  "messages_ingested": 0
}
```

**Debug steps:**
```bash
# Check if chat has messages in date range
# Default is last 30 days

# Try without date filter
curl -X POST "$API_BASE/telegram/ingest-historical" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "PEER_REF", "limit": 10}' | jq

# Check server logs for detailed processing
tail -f logs/app.log | grep -i telegram
```

**4. Real-Time Listener Not Receiving**

```
Listener active but no messages captured
```

**Debug steps:**
1. Verify listener is running (should block)
2. Send test message from another device to monitored chat
3. Check if message has text content (media-only skipped)
4. Verify chat is in monitored list
5. Check server logs for event processing

**5. Embedding Generation Failures**

```
Error generating embedding: ...
```

**Debug steps:**
```bash
# Check OpenAI API key
echo $OPENAI_API_KEY

# Test embedding service directly
uv run python -c "
from app.services.embedding import generate_embedding
import asyncio

async def test():
    embedding = await generate_embedding('test message')
    print(f'Generated embedding with {len(embedding)} dimensions')

asyncio.run(test())
"
```

### Test Logs and Debugging

**Enable debug logging:**

```python
# Add to .env
LOG_LEVEL=DEBUG

# Or in code:
import logging
logging.getLogger('app.services.telethon_service').setLevel(logging.DEBUG)
```

**Watch logs during testing:**

```bash
# Watch all logs
tail -f logs/app.log

# Filter for Telegram
tail -f logs/app.log | grep -i telegram

# Filter for errors
tail -f logs/app.log | grep ERROR
```

## Test Coverage Checklist

### Functional Tests
- [x] Authentication (session string generation)
- [x] Connection establishment
- [x] Dialog listing
- [x] Historical message fetching
- [x] Real-time message capture
- [x] Message ingestion
- [x] Embedding generation
- [x] Database storage
- [x] Export file parsing

### API Tests
- [x] GET /telegram/status
- [x] GET /telegram/dialogs
- [x] POST /telegram/ingest-historical
- [x] POST /upload/telegram-export

### Edge Cases
- [x] Empty chats
- [x] Media-only messages
- [x] Large message batches
- [x] Invalid chat IDs
- [x] Expired session strings
- [x] Network interruptions
- [x] Concurrent ingestion

### Performance Tests
- [ ] Load testing (API endpoints)
- [ ] Ingestion rate benchmarking
- [ ] Memory leak detection
- [ ] Long-running listener stability

### Security Tests
- [ ] Session string security
- [ ] API authentication
- [ ] Rate limiting
- [ ] Input validation

## Continuous Testing

### CI/CD Integration

```yaml
# .github/workflows/test_telegram.yml
name: Telegram Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install dependencies
        run: uv sync

      - name: Run tests
        env:
          TELEGRAM_API_ID: ${{ secrets.TELEGRAM_API_ID }}
          TELEGRAM_API_HASH: ${{ secrets.TELEGRAM_API_HASH }}
          TELEGRAM_SESSION_STRING: ${{ secrets.TELEGRAM_SESSION_STRING }}
        run: |
          uv run pytest tests/services/test_telethon_service.py -v
```

### Automated Monitoring

```python
# scripts/monitor_telegram.py
"""
Continuous monitoring script for production
Checks health every 5 minutes
"""
import asyncio
import httpx
from datetime import datetime

async def check_health():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("https://api.compaytence.com/api/v1/telegram/status")
            status = response.json()["status"]

            timestamp = datetime.now().isoformat()
            if status == "configured":
                print(f"[{timestamp}] ✅ Telegram integration healthy")
            else:
                print(f"[{timestamp}] ⚠️ Telegram integration degraded: {status}")
                # Send alert
        except Exception as e:
            print(f"[{timestamp}] ❌ Health check failed: {e}")
            # Send alert

async def monitor():
    while True:
        await check_health()
        await asyncio.sleep(300)  # 5 minutes

if __name__ == "__main__":
    asyncio.run(monitor())
```

## Summary

This testing guide covers:
- ✅ All test scripts and their usage
- ✅ Complete API endpoint testing
- ✅ Real-time sync testing procedures
- ✅ Integration and E2E testing
- ✅ Performance benchmarking
- ✅ Troubleshooting common issues
- ✅ CI/CD integration examples

For more details, see:
- **TELEGRAM_INGESTION.md** - Implementation guide
- **PROJECT_CHECKLIST.md** - Development progress
- **Telethon Docs** - https://docs.telethon.dev/
