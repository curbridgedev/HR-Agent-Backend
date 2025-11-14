"""
Test script for Telegram real-time message sync.

This script will:
1. Connect to Telegram using your session string
2. Start listening for new messages in specified chats
3. Automatically ingest them into the knowledge base

Press Ctrl+C to stop.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.telethon_service import get_telethon_service


async def test_realtime_sync() -> None:
    """Test real-time message sync."""
    print("=" * 60)
    print("TELEGRAM REAL-TIME SYNC TEST")
    print("=" * 60)
    print()
    print("This will listen for new messages and automatically ingest them.")
    print("Press Ctrl+C to stop.")
    print()

    service = get_telethon_service()

    try:
        # Initialize service
        print("1. Connecting to Telegram...")
        await service.initialize(session_string=settings.telegram_session_string)
        print("✅ Connected to Telegram!")
        print()

        # Get dialogs to show user their chats
        print("2. Fetching your chats...")
        dialogs = await service.list_dialogs(limit=10)

        print(f"Found {len(dialogs)} recent chats:\n")
        print(f"{'#':<4} {'Type':<10} {'Name':<40}")
        print("-" * 60)

        for i, dialog in enumerate(dialogs, 1):
            dialog_type = (
                "User"
                if dialog["is_user"]
                else (
                    "Group"
                    if dialog["is_group"]
                    else "Channel" if dialog["is_channel"] else "Unknown"
                )
            )
            print(f"{i:<4} {dialog_type:<10} {dialog['name'][:38]:<40}")

        print()
        print("-" * 60)
        print()

        # Ask user which chats to monitor
        choice = input(
            "Enter chat numbers to monitor (comma-separated, e.g., '1,2,3')\n"
            "Or press Enter to monitor ALL chats: "
        ).strip()

        chat_ids = None
        if choice:
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            chat_ids = [dialogs[i]["id"] for i in indices if 0 <= i < len(dialogs)]
            print(f"\n✅ Monitoring {len(chat_ids)} selected chat(s)")
        else:
            print("\n✅ Monitoring ALL chats")

        print()
        print("=" * 60)
        print("REAL-TIME LISTENER ACTIVE")
        print("=" * 60)
        print()
        print("Waiting for new messages...")
        print("All new messages will be automatically ingested into the knowledge base.")
        print()
        print("Press Ctrl+C to stop.")
        print()

        # Start the listener (this will run until Ctrl+C)
        await service.start_realtime_listener(chat_ids=chat_ids)

    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping listener...")
        await service.stop_realtime_listener()
        print("✅ Listener stopped.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Cleanup
        if service.client and service.client.is_connected():
            await service.client.disconnect()
            print("Disconnected from Telegram.")


if __name__ == "__main__":
    try:
        asyncio.run(test_realtime_sync())
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
        sys.exit(0)
