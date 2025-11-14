"""
Test script for Telegram error notification system.

This script tests the Telegram notifier by triggering various types of errors
and verifying they are sent to the configured Telegram chat thread.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.telegram_notifier import telegram_notifier


async def test_simple_error():
    """Test sending a simple error notification."""
    print("\n[TEST 1] Testing simple error notification...")

    try:
        # Trigger a simple error
        raise ValueError("This is a test error message for Telegram notifications")
    except ValueError as e:
        success = await telegram_notifier.send_error_notification(
            error=e,
            context={
                "test_name": "simple_error",
                "endpoint": "/api/v1/test",
                "user_id": "test-user-123",
            },
            include_traceback=True,
        )

        if success:
            print("[OK] Simple error notification sent successfully!")
        else:
            print("[ERROR] Failed to send simple error notification")

        return success


async def test_complex_error():
    """Test sending a complex error with nested exceptions."""
    print("\n[TEST 2] Testing complex error with nested exceptions...")

    try:
        # Trigger a nested error
        try:
            result = 10 / 0
        except ZeroDivisionError as inner_error:
            raise RuntimeError(f"Failed to calculate result: {inner_error}") from inner_error
    except RuntimeError as e:
        success = await telegram_notifier.send_error_notification(
            error=e,
            context={
                "test_name": "complex_error",
                "endpoint": "/api/v1/chat",
                "method": "POST",
                "user_id": "user-456",
                "session_id": "session-789",
                "request_id": "req-abc123",
            },
            include_traceback=True,
        )

        if success:
            print("[OK] Complex error notification sent successfully!")
        else:
            print("[ERROR] Failed to send complex error notification")

        return success


async def test_key_error():
    """Test sending a KeyError notification."""
    print("\n[TEST 3] Testing KeyError notification...")

    try:
        data = {"name": "John"}
        missing = data["age"]  # This will raise KeyError
    except KeyError as e:
        success = await telegram_notifier.send_error_notification(
            error=e,
            context={
                "test_name": "key_error",
                "endpoint": "/api/v1/process",
                "data_keys": list(data.keys()),
                "missing_key": "age",
            },
            include_traceback=True,
        )

        if success:
            print("[OK] KeyError notification sent successfully!")
        else:
            print("[ERROR] Failed to send KeyError notification")

        return success


async def test_long_error_message():
    """Test error with very long message (truncation)."""
    print("\n[TEST 4] Testing error with long message (truncation test)...")

    try:
        long_message = "Error: " + "A" * 1000  # Very long error message
        raise Exception(long_message)
    except Exception as e:
        success = await telegram_notifier.send_error_notification(
            error=e,
            context={
                "test_name": "long_message",
                "note": "Testing message truncation for very long errors",
            },
            include_traceback=False,
        )

        if success:
            print("[OK] Long error notification sent successfully!")
        else:
            print("[ERROR] Failed to send long error notification")

        return success


async def test_special_characters():
    """Test error message with special MarkdownV2 characters."""
    print("\n[TEST 5] Testing error with special characters (escaping test)...")

    try:
        # Error with special characters that need escaping in MarkdownV2
        raise ValueError("Error: Failed to parse JSON with characters like _underscore_, *asterisk*, [brackets], (parentheses), `backticks`, and more!")
    except ValueError as e:
        success = await telegram_notifier.send_error_notification(
            error=e,
            context={
                "test_name": "special_characters",
                "note": "Testing MarkdownV2 character escaping",
                "symbols": "_ * [ ] ( ) ~ ` > # + - = | { } . !",
            },
            include_traceback=False,
        )

        if success:
            print("[OK] Special characters notification sent successfully!")
        else:
            print("[ERROR] Failed to send special characters notification")

        return success


async def test_production_vs_dev():
    """Test notification formatting differences between production and dev."""
    print("\n[TEST 6] Testing environment-specific formatting...")

    try:
        raise ConnectionError("Database connection timeout after 30 seconds")
    except ConnectionError as e:
        success = await telegram_notifier.send_error_notification(
            error=e,
            context={
                "test_name": "environment_test",
                "current_environment": telegram_notifier.environment,
                "database": "postgresql://localhost:5432/compaytence",
                "timeout": "30s",
            },
            include_traceback=True,
        )

        if success:
            print(f"[OK] Environment notification sent (env: {telegram_notifier.environment})!")
        else:
            print("[ERROR] Failed to send environment notification")

        return success


async def main():
    """Run all tests."""
    print("=" * 60)
    print("TELEGRAM ERROR NOTIFICATION SYSTEM TEST")
    print("=" * 60)

    # Check if notifier is enabled
    if not telegram_notifier.enabled:
        print("\n[ERROR] Telegram notifier is not enabled!")
        print("Please check your .env configuration:")
        print("  - TELEGRAM_ERROR_NOTIFICATIONS_ENABLED=true")
        print("  - TELEGRAM_ERROR_BOT_TOKEN=<your-bot-token>")
        print("  - TELEGRAM_ERROR_CHAT_ID=<your-chat-id>")
        print("  - TELEGRAM_ERROR_THREAD_ID=<your-thread-id>")
        return

    print(f"\nNotifier Configuration:")
    print(f"  Project: {telegram_notifier.project_name}")
    print(f"  Environment: {telegram_notifier.environment}")
    print(f"  Chat ID: {telegram_notifier.chat_id}")
    print(f"  Thread ID: {telegram_notifier.thread_id}")
    print(f"  Enabled: {telegram_notifier.enabled}")

    # Run all tests
    tests = [
        test_simple_error,
        test_complex_error,
        test_key_error,
        test_long_error_message,
        test_special_characters,
        test_production_vs_dev,
    ]

    results = []
    for test_func in tests:
        try:
            result = await test_func()
            results.append(result)
            # Wait between tests to avoid rate limiting
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[ERROR] Test {test_func.__name__} failed with exception: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("\n[SUCCESS] All tests passed! Error notifications are working correctly.")
        print("\nPlease check your Telegram chat thread to see the formatted error messages.")
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed. Check the logs above for details.")


if __name__ == "__main__":
    asyncio.run(main())
