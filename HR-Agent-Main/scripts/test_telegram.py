"""
Test script for Telegram integration.

This script will:
1. Connect to Telegram using your session string
2. List your chats/channels/groups
3. Fetch recent messages from a selected chat
4. Test ingestion into the knowledge base

Run this to verify your Telegram setup works!
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.telethon_service import get_telethon_service


async def test_connection():
    """Test Telegram connection and list chats."""
    print("=" * 60)
    print("TELEGRAM INTEGRATION TEST")
    print("=" * 60)
    print()

    # Initialize service
    print("1. Initializing Telethon service...")
    service = get_telethon_service()

    try:
        await service.initialize(session_string=settings.telegram_session_string)
        print("✅ Connected to Telegram!")
        print()

        # Get current user info
        if service.client:
            me = await service.client.get_me()
            print(f"Logged in as: {me.first_name} {me.last_name or ''}")
            print(f"Username: @{me.username}")
            print(f"Phone: {me.phone}")
            print()

        # List dialogs
        print("2. Fetching your chats/channels/groups...")
        dialogs = await service.list_dialogs(limit=20)

        if not dialogs:
            print("No dialogs found.")
            return

        print(f"Found {len(dialogs)} dialogs:\n")

        print(f"{'#':<4} {'Type':<10} {'Name':<40} {'Unread':<8} {'ID':<15}")
        print("-" * 80)

        for i, dialog in enumerate(dialogs, 1):
            dialog_type = (
                "User" if dialog["is_user"] else
                "Group" if dialog["is_group"] else
                "Channel" if dialog["is_channel"] else
                "Unknown"
            )
            print(
                f"{i:<4} {dialog_type:<10} {dialog['name'][:38]:<40} "
                f"{dialog['unread_count']:<8} {dialog['id']:<15}"
            )

        print()
        print("-" * 80)
        print()

        # Ask user to test message fetching
        print("3. Test message fetching (optional)")
        print()
        choice = input("Enter chat number to fetch messages (or press Enter to skip): ").strip()

        if choice and choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(dialogs):
                selected = dialogs[index]
                print()
                print(f"Fetching messages from: {selected['name']}")
                print()

                # Fetch recent messages
                result = await service.fetch_historical_messages(
                    chat_id=selected["id"],
                    limit=5,
                )

                print(f"Status: {result['status']}")
                print(f"Messages ingested: {result['ingested']}")
                print(f"Messages failed: {result['failed']}")

                if result['status'] == 'success' and result['ingested'] > 0:
                    print()
                    print("✅ Successfully ingested messages into knowledge base!")
                    print()
                    print("You can now query these messages through the chat API.")
                elif result['failed'] > 0:
                    print()
                    print("⚠️ Some messages failed to ingest. Check logs for details.")
            else:
                print("Invalid choice.")
        else:
            print("Skipped message fetching.")

        print()
        print("=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        print()
        print("✅ Your Telegram integration is working!")
        print()
        print("Next steps:")
        print("1. Set up the same TELEGRAM_SESSION_STRING on Railway")
        print("2. Create Inngest workflow for continuous sync")
        print("3. Start ingesting historical data from important chats")
        print()

    except ValueError as e:
        print(f"❌ Error: {e}")
        print()
        print("Make sure you have set in .env:")
        print("  - TELEGRAM_API_ID")
        print("  - TELEGRAM_API_HASH")
        print("  - TELEGRAM_SESSION_STRING")
        print()
        print("Run scripts/telegram_auth.py first if you haven't authenticated yet.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if service.client and service.client.is_connected():
            await service.client.disconnect()
            print("Disconnected from Telegram.")


async def test_export_parser():
    """Test Telegram export parser with sample data."""
    print()
    print("=" * 60)
    print("TELEGRAM EXPORT PARSER TEST")
    print("=" * 60)
    print()

    sample_export = """[29.10.25 17:30:45] John Doe:
Hello, this is a test message

[29.10.25 17:31:12] Jane Smith:
This is a reply message
with multiple lines

[29.10.25 17:32:00] John Doe:
Another message here"""

    from app.services.telegram_export_parser import get_telegram_export_parser

    parser = get_telegram_export_parser()
    result = await parser.parse_and_ingest(
        file_content=sample_export,
        source_metadata={
            "file_name": "test_export.txt",
            "uploaded_by": "test_user",
        }
    )

    print(f"Status: {result['status']}")
    print(f"Messages found: {result['messages_found']}")
    print(f"Messages ingested: {result['messages_ingested']}")
    print(f"Messages failed: {result['messages_failed']}")

    if result['status'] == 'success':
        print()
        print("✅ Export parser is working!")
    else:
        print()
        print(f"⚠️ Parser test had issues: {result.get('message')}")


if __name__ == "__main__":
    print()
    print("Select test to run:")
    print("1. Test Telegram connection and fetch messages")
    print("2. Test export parser with sample data")
    print("3. Both")
    print()

    choice = input("Enter choice (1-3): ").strip()

    try:
        if choice == "1":
            asyncio.run(test_connection())
        elif choice == "2":
            asyncio.run(test_export_parser())
        elif choice == "3":
            asyncio.run(test_connection())
            asyncio.run(test_export_parser())
        else:
            print("Invalid choice. Exiting.")
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
        sys.exit(1)
