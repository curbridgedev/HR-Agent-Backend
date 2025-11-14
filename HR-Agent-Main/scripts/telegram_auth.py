"""
Helper script for initial Telegram authentication.

This script will:
1. Connect to Telegram using your API credentials
2. Send you an authentication code
3. Generate a session string
4. Display the session string to add to Railway

Run this once to get your TELEGRAM_SESSION_STRING.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient
from telethon.sessions import StringSession

from app.core.config import settings


async def authenticate():
    """Run interactive Telegram authentication."""
    print("=" * 60)
    print("TELEGRAM AUTHENTICATION")
    print("=" * 60)
    print()
    print(f"API ID: {settings.telegram_api_id}")
    print(f"API Hash: {settings.telegram_api_hash[:8]}...")
    print()

    # Get phone number
    if settings.telegram_phone_number:
        phone = settings.telegram_phone_number
        print(f"Using phone from .env: {phone}")
    else:
        phone = input("Enter your phone number (with country code, e.g., +1234567890): ")

    print()
    print("Connecting to Telegram...")

    # Create client with empty StringSession
    client = TelegramClient(
        StringSession(), settings.telegram_api_id, settings.telegram_api_hash
    )

    await client.connect()

    if not await client.is_user_authorized():
        print()
        print("Sending authentication code to your Telegram...")
        await client.send_code_request(phone)

        print()
        print("Check your Telegram app for the code!")
        code = input("Enter the code you received: ")

        try:
            await client.sign_in(phone, code)
        except Exception as e:
            if "password" in str(e).lower():
                print()
                print("Two-factor authentication enabled.")
                password = input("Enter your 2FA password: ")
                await client.sign_in(password=password)
            else:
                raise

    print()
    print("✅ Successfully authenticated!")
    print()

    # Get session string
    session_string = client.session.save()

    print("=" * 60)
    print("YOUR SESSION STRING")
    print("=" * 60)
    print()
    print(session_string)
    print()
    print("=" * 60)
    print()
    print("📋 NEXT STEPS:")
    print()
    print("1. Copy the session string above")
    print("2. Add it to your .env file:")
    print(f'   TELEGRAM_SESSION_STRING="{session_string}"')
    print()
    print("3. Add it to Railway environment variables:")
    print("   - Go to Railway dashboard")
    print("   - Variables tab")
    print(f'   - Add: TELEGRAM_SESSION_STRING={session_string}')
    print()
    print("4. You can now use Telethon for historical and real-time sync!")
    print()

    # Get user info to confirm
    me = await client.get_me()
    print(f"Authenticated as: {me.first_name} {me.last_name or ''} (@{me.username})")
    print(f"Phone: {me.phone}")
    print()

    await client.disconnect()
    print("✅ Done! Session saved.")


if __name__ == "__main__":
    try:
        asyncio.run(authenticate())
    except KeyboardInterrupt:
        print("\n\nAuthentication cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print()
        print("Make sure you have set in .env:")
        print("  - TELEGRAM_API_ID")
        print("  - TELEGRAM_API_HASH")
        print("  - TELEGRAM_PHONE_NUMBER (optional)")
        sys.exit(1)
