# Telegram Error Notification System

## Overview

The Compaytence Backend includes an automated Telegram error notification system that sends formatted error alerts to a specified Telegram chat thread whenever the backend encounters any unhandled exception.

**Key Features:**
- 🚨 **Automatic error detection** via FastAPI global exception handlers
- 📱 **Real-time Telegram notifications** with formatted MarkdownV2 messages
- 🎯 **Thread-based organization** for easy error tracking
- 🔒 **Environment-aware** formatting (production vs development)
- 📊 **Rich context** including request details, user info, and full tracebacks
- ⚡ **Non-blocking** notifications that don't affect API response times

## Architecture

### Components

1. **`app/utils/telegram_notifier.py`** - Core notification service
   - `TelegramNotifier` class for managing bot and sending messages
   - MarkdownV2 escaping and formatting
   - Async and sync wrapper methods

2. **`app/core/error_handler.py`** - FastAPI middleware and exception handlers
   - `ErrorHandlerMiddleware` for catching all exceptions
   - `setup_exception_handlers()` for specific exception types
   - `setup_error_monitoring()` for complete integration

3. **`app/core/config.py`** - Configuration settings
   - Telegram bot token, chat ID, thread ID
   - Feature flag for enabling/disabling notifications

4. **`app/main.py`** - Integration point
   - Registers error monitoring during app startup

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Telegram Error Notifications (for backend error alerts)
TELEGRAM_ERROR_BOT_TOKEN=7851252299:AAFhfCl2eNoFsktjaTYviue7Lec9pmoLVRo
TELEGRAM_ERROR_CHAT_ID=-1002386016697
TELEGRAM_ERROR_THREAD_ID=8393
TELEGRAM_ERROR_NOTIFICATIONS_ENABLED=true
```

**Configuration Parameters:**

- **`TELEGRAM_ERROR_BOT_TOKEN`** - Bot token from @BotFather
- **`TELEGRAM_ERROR_CHAT_ID`** - Chat/group ID (negative for groups)
- **`TELEGRAM_ERROR_THREAD_ID`** - Message thread ID within the chat
- **`TELEGRAM_ERROR_NOTIFICATIONS_ENABLED`** - Feature flag (true/false)

### Setup Steps

1. **Create a Telegram Bot** (if not already done):
   ```
   1. Message @BotFather on Telegram
   2. Use /newbot command
   3. Follow prompts to create bot
   4. Save the bot token
   ```

2. **Get Chat ID**:
   ```
   1. Add your bot to the group/channel
   2. Send a message in the group
   3. Visit: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   4. Find "chat":{"id":-1234567890} in the JSON
   ```

3. **Get Thread ID**:
   ```
   1. Create a topic/thread in your Telegram group
   2. Send a message in that thread
   3. Visit: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   4. Find "message_thread_id": 8393 in the JSON
   ```

4. **Update `.env` file** with the values above

5. **Test the configuration**:
   ```bash
   uv run python scripts/test_telegram_notifier.py
   ```

## Message Format

### Structure

Error notifications are sent in MarkdownV2 format with the following structure:

```
🚨 *Error in Compaytence AI Agent*

🟢 *Environment:* `development`
⏰ *Time:* `2025-01-27 10:30:45 UTC`

❌ *Error Type:* `ValueError`

*Message:*
```
Error message content here
```

*Context:*
  • *endpoint:* `/api/v1/chat`
  • *method:* `POST`
  • *user_id:* `user-123`
  • *session_id:* `session-456`

*Traceback:*
```python
Traceback (most recent call last):
  File "...", line 123, in process_chat
    result = risky_operation()
ValueError: Invalid input
```
```

### Environment Indicators

- 🟢 **Development** - Green badge
- 🟡 **UAT** - Yellow badge
- 🔴 **Production** - Red badge (high priority!)

### Automatic Truncation

- Error messages truncated to 500 characters
- Context values truncated to 100 characters
- Tracebacks truncated to last 1000 characters
- Prevents hitting Telegram message size limits

## Usage

### Automatic (Recommended)

The error notification system works automatically via global exception handlers. No code changes needed - just configure the environment variables.

**What gets notified:**
- All unhandled exceptions in API endpoints
- Middleware errors
- Background task failures
- Any uncaught Python exceptions

**What doesn't get notified:**
- Expected validation errors (400 errors)
- Authentication failures (401 errors)
- Not found errors (404 errors)
- These are logged but not sent to Telegram

### Manual Notifications

You can also manually send error notifications from your code:

```python
from app.utils.telegram_notifier import notify_error, notify_error_sync

# Async context
async def my_function():
    try:
        risky_operation()
    except Exception as e:
        await notify_error(
            error=e,
            context={
                "function": "my_function",
                "user_id": "user-123",
                "operation": "risky_operation",
            },
            include_traceback=True,
        )

# Sync context (creates event loop if needed)
def my_sync_function():
    try:
        risky_operation()
    except Exception as e:
        notify_error_sync(
            error=e,
            context={"function": "my_sync_function"},
            include_traceback=True,
        )
```

### Custom Context

Include relevant context to help with debugging:

```python
context = {
    "endpoint": request.url.path,
    "method": request.method,
    "user_id": current_user.id,
    "session_id": session_id,
    "request_id": request_id,
    "operation": "vector_search",
    "query": query[:50],  # First 50 chars
    "parameters": str(params),
}

await notify_error(error, context=context)
```

## Exception Handlers

### Registered Handlers

The system registers handlers for specific exception types:

1. **`Exception`** (catch-all)
   - Catches all unhandled exceptions
   - Sends full notification with traceback
   - Returns 500 Internal Server Error

2. **`ValueError`**
   - Validation errors
   - Returns 400 Bad Request
   - NOT sent to Telegram (too noisy)

3. **`KeyError`**
   - Missing required fields
   - Sends notification (might indicate bugs)
   - Returns 400 Bad Request

### Middleware

`ErrorHandlerMiddleware` catches exceptions before they reach the client:

- Extracts request context (method, URL, headers, user)
- Logs the error
- Sends Telegram notification (non-blocking)
- Returns appropriate HTTP response

**Production vs Development:**
- **Production**: Generic error messages to users, full details to Telegram
- **Development**: Full error details to both users and Telegram

## Testing

### Test Script

Run the comprehensive test suite:

```bash
uv run python scripts/test_telegram_notifier.py
```

**Tests included:**
1. Simple error notification
2. Complex nested exceptions
3. KeyError handling
4. Long message truncation
5. Special character escaping (MarkdownV2)
6. Environment-specific formatting

**Expected output:**
```
============================================================
TELEGRAM ERROR NOTIFICATION SYSTEM TEST
============================================================

[TEST 1] Testing simple error notification...
[OK] Simple error notification sent successfully!

[TEST 2] Testing complex error with nested exceptions...
[OK] Complex error notification sent successfully!

...

Tests passed: 6/6

[SUCCESS] All tests passed! Error notifications are working correctly.
```

### Manual Testing

Trigger a test error via the API:

```bash
# This endpoint doesn't exist, will trigger error handler
curl http://localhost:8000/api/v1/nonexistent

# Or create a test endpoint that raises an exception
```

Then check your Telegram thread for the formatted error message.

## Monitoring & Alerting

### What to Monitor

1. **Notification Failures**
   - Check logs for "Failed to send Telegram notification"
   - Could indicate bot token issues or network problems

2. **Rate Limiting**
   - Telegram has rate limits (20 messages/minute to groups)
   - Script includes 2-second delays between test messages

3. **Error Patterns**
   - High frequency of same error type
   - Production errors with red badge
   - Critical path failures (authentication, database, etc.)

### Alert Response

**When you receive an error notification:**

1. **Check environment badge** - Production errors need immediate attention
2. **Review error type and message** - Understand what failed
3. **Examine context** - Identify affected user, endpoint, request
4. **Check traceback** - Locate the exact line causing the issue
5. **Verify in logs** - Check LangFuse/Sentry for more details
6. **Fix and deploy** - Resolve the issue and monitor for recurrence

## Best Practices

### Do's ✅

- **Enable in all environments** (dev, UAT, production) for consistent monitoring
- **Use separate Telegram threads** for dev/UAT/prod to reduce noise
- **Include relevant context** when manually sending notifications
- **Review error patterns** regularly to identify systemic issues
- **Set up alerts** for critical production errors
- **Test after deployment** to ensure notifications are working

### Don'ts ❌

- **Don't disable in production** - You need to know about errors immediately
- **Don't include sensitive data** in context (passwords, API keys, PII)
- **Don't send expected errors** (validation failures, 404s) to reduce noise
- **Don't ignore production errors** - Red badge = high priority
- **Don't exceed rate limits** - Add delays between manual notifications
- **Don't hardcode credentials** - Always use environment variables

## Troubleshooting

### "Telegram notifier is not enabled"

**Cause:** Missing or incorrect environment variables

**Solution:**
1. Check `.env` file has all required variables
2. Verify `TELEGRAM_ERROR_NOTIFICATIONS_ENABLED=true`
3. Ensure bot token is valid (format: `123456:ABC-DEF...`)
4. Restart the application after changes

### "Failed to send Telegram notification"

**Causes:**
- Invalid bot token
- Bot not added to chat/group
- Network connectivity issues
- Rate limiting (too many messages)

**Solutions:**
1. Verify bot token with BotFather
2. Ensure bot is member of the chat/group
3. Check bot has permission to send messages
4. Verify chat ID and thread ID are correct
5. Test with: `uv run python scripts/test_telegram_notifier.py`

### "Telegram API returned error 400: Bad Request"

**Causes:**
- Invalid MarkdownV2 formatting
- Unescaped special characters
- Message too long (>4096 characters)

**Solutions:**
1. Check error message for special characters
2. Escaping is automatic, but verify with test script
3. System automatically truncates long messages
4. Review `_escape_markdown_v2()` method if issues persist

### Messages not appearing in thread

**Causes:**
- Wrong thread ID
- Thread was deleted
- Bot doesn't have thread access

**Solutions:**
1. Get fresh thread ID from Telegram API
2. Ensure thread still exists
3. Test sending to main chat (thread_id=0) first

## Performance Impact

### Async Design

- Notifications are **non-blocking** - API responses not affected
- Uses `asyncio.create_task()` for fire-and-forget sending
- Error in notification won't crash the application

### Overhead

- **Minimal latency**: <10ms to queue notification task
- **No blocking**: Client receives response immediately
- **Failure isolation**: Notification failure logged but doesn't affect API

### Cost

- **Telegram API**: Free, unlimited messages
- **Network**: ~1KB per notification
- **Compute**: Negligible CPU/memory usage

## Security Considerations

### Sensitive Data

- **Never include** passwords, API keys, tokens in context
- **Sanitize** user input before including in notifications
- **Redact** PII if enabled in config
- **Review** error messages for accidental data exposure

### Bot Token Security

- **Store** in environment variables only, never commit to git
- **Rotate** tokens periodically (quarterly recommended)
- **Limit** bot permissions to minimum required (send messages only)
- **Monitor** bot usage in Telegram Bot Settings

### Access Control

- **Restrict** Telegram chat/group access to team members only
- **Use private groups** not public channels for sensitive errors
- **Enable** two-factor authentication for Telegram accounts
- **Audit** group membership regularly

## Integration with Other Tools

### LangFuse Integration

Error notifications complement LangFuse tracing:
- **Telegram**: Real-time alerts for immediate attention
- **LangFuse**: Detailed traces, metrics, and historical analysis

### Sentry Integration

If Sentry is configured, errors are sent to both:
- **Telegram**: Quick notifications for on-call team
- **Sentry**: Advanced error grouping, release tracking, performance monitoring

### Logging Integration

All notified errors are also logged:
- **Structured logs**: JSON format with full context
- **Log levels**: ERROR for unhandled exceptions
- **Correlation**: Same request_id in logs and Telegram

## Future Enhancements

Potential improvements for future versions:

1. **Error Grouping** - Suppress duplicate errors within time window
2. **Severity Levels** - Different notification channels based on severity
3. **On-Call Integration** - Tag specific team members for urgent errors
4. **Error Statistics** - Daily/weekly error summaries
5. **Auto-Resolution** - Mark errors as resolved when fix is deployed
6. **Custom Filters** - User-defined rules for which errors to notify
7. **Multiple Channels** - Support Discord, Slack, email notifications

## Support

For issues or questions:

1. Check this documentation first
2. Run test script: `uv run python scripts/test_telegram_notifier.py`
3. Review application logs for error details
4. Check Telegram Bot API documentation: https://core.telegram.org/bots/api
5. Contact DevOps team for infrastructure issues

---

**Last Updated:** 2025-01-27
**Version:** 1.0.0
**Author:** Compaytence Backend Team
