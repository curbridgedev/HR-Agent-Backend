"""
Debug Slack authentication and permissions.
"""

import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()


async def debug_slack_auth():
    """Debug Slack authentication issues."""

    print("🔍 Debugging Slack Authentication\n")
    print("=" * 60)

    bot_token = os.getenv("SLACK_BOT_TOKEN")

    if not bot_token:
        print("❌ No SLACK_BOT_TOKEN found in .env")
        return

    print(f"\n✅ Bot Token: {bot_token[:15]}...\n")

    # Test 1: Verify token with auth.test
    print("1. Testing token validity with auth.test...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {bot_token}"}
            )

            data = response.json()

            if data.get("ok"):
                print(f"   ✅ Token is valid!")
                print(f"   Team: {data.get('team')}")
                print(f"   User: {data.get('user')}")
                print(f"   User ID: {data.get('user_id')}")
                print(f"   Team ID: {data.get('team_id')}")
            else:
                print(f"   ❌ Token validation failed: {data.get('error')}")
                print(f"\n   This usually means:")
                if data.get('error') == 'invalid_auth':
                    print("   - Token is expired or invalid")
                    print("   - Go to https://api.slack.com/apps")
                    print("   - Select your app → OAuth & Permissions")
                    print("   - Click 'Reinstall to Workspace'")
                    print("   - Copy the NEW bot token")
                elif data.get('error') == 'token_revoked':
                    print("   - Token has been revoked")
                    print("   - Reinstall the app to get a new token")
                return

    except Exception as e:
        print(f"   ❌ Request failed: {e}")
        return

    # Test 2: Check bot's OAuth scopes
    print("\n2. Checking OAuth scopes...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {bot_token}"}
            )

            # Note: auth.test doesn't return scopes, but we can infer from error messages
            print("   ℹ️  To check scopes, go to:")
            print("   https://api.slack.com/apps → Your App → OAuth & Permissions")
            print("\n   Required Bot Token Scopes:")
            print("   ✓ channels:history - Read messages in public channels")
            print("   ✓ groups:history   - Read messages in private channels")
            print("   ✓ channels:read    - View basic channel info")
            print("   ✓ files:read       - Access file content")
            print("   ✓ users:read       - Get user information")

    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # Test 3: Try to list conversations
    print("\n3. Testing conversations.list (list channels bot can see)...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://slack.com/api/conversations.list",
                headers={"Authorization": f"Bearer {bot_token}"},
                params={"types": "public_channel,private_channel"}
            )

            data = response.json()

            if data.get("ok"):
                channels = data.get("channels", [])
                print(f"   ✅ Bot can see {len(channels)} channels:")

                for channel in channels[:5]:  # Show first 5
                    is_member = "✓" if channel.get("is_member") else "✗"
                    print(f"   {is_member} #{channel.get('name')} (ID: {channel.get('id')})")

                if len(channels) > 5:
                    print(f"   ... and {len(channels) - 5} more")

                # Check if bot is member of any channel
                member_channels = [c for c in channels if c.get("is_member")]
                if not member_channels:
                    print("\n   ⚠️  Bot is not a member of any channels!")
                    print("   Add bot to a channel: /invite @YourBotName")

            else:
                error = data.get("error")
                print(f"   ❌ Failed: {error}")

                if error == "missing_scope":
                    print("\n   Missing required scope!")
                    print("   Add these scopes in OAuth & Permissions:")
                    print("   - channels:read")
                    print("   - groups:read")
                    print("   Then REINSTALL the app to workspace")
                elif error == "invalid_auth":
                    print("\n   Invalid authentication!")
                    print("   Your token may be expired or from wrong workspace")
                    print("   Reinstall app and get a fresh token")

    except Exception as e:
        print(f"   ❌ Request failed: {e}")

    # Test 4: Try to read a specific channel (the one user provided)
    channel_id = input("\n4. Enter a channel ID to test reading history (or press Enter to skip): ").strip()

    if channel_id:
        print(f"\n   Testing conversations.history for {channel_id}...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://slack.com/api/conversations.history",
                    headers={"Authorization": f"Bearer {bot_token}"},
                    params={"channel": channel_id, "limit": 1}
                )

                data = response.json()

                if data.get("ok"):
                    messages = data.get("messages", [])
                    print(f"   ✅ Successfully read channel!")
                    print(f"   Messages found: {len(messages)}")

                    if messages:
                        print(f"   Latest message: {messages[0].get('text', '')[:50]}...")
                else:
                    error = data.get("error")
                    print(f"   ❌ Failed: {error}")

                    if error == "missing_scope":
                        print("\n   💡 Missing scope: channels:history")
                        print("   Steps to fix:")
                        print("   1. Go to https://api.slack.com/apps")
                        print("   2. Select your app → OAuth & Permissions")
                        print("   3. Add scope: channels:history")
                        print("   4. Click 'Reinstall to Workspace'")
                        print("   5. Copy the NEW bot token")
                        print("   6. Update SLACK_BOT_TOKEN in .env")
                    elif error == "channel_not_found":
                        print("\n   💡 Channel not found")
                        print("   - Check the channel ID is correct")
                        print("   - Make sure bot is invited: /invite @BotName")
                    elif error == "not_in_channel":
                        print("\n   💡 Bot is not in this channel")
                        print("   Invite bot: /invite @YourBotName")

        except Exception as e:
            print(f"   ❌ Request failed: {e}")

    print("\n" + "=" * 60)
    print("\n📝 Summary:")
    print("\nIf you see 'invalid_auth' errors:")
    print("1. Go to https://api.slack.com/apps")
    print("2. Select your app")
    print("3. Go to OAuth & Permissions")
    print("4. Verify these scopes are added:")
    print("   - channels:history")
    print("   - groups:history")
    print("   - channels:read")
    print("   - files:read")
    print("   - users:read")
    print("5. Click 'Reinstall to Workspace'")
    print("6. Copy the NEW Bot User OAuth Token")
    print("7. Update SLACK_BOT_TOKEN in .env")
    print("8. Restart the backend")
    print("\nThen run this debug script again!")


if __name__ == "__main__":
    asyncio.run(debug_slack_auth())
