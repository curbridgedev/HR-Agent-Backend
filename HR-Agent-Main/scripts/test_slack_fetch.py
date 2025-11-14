"""
Test fetching messages directly from Slack API to debug ingestion.
"""

import asyncio
import httpx
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


async def test_slack_fetch():
    """Test fetching messages directly from Slack."""

    print("🔍 Testing Slack Message Fetching\n")
    print("=" * 60)

    bot_token = os.getenv("SLACK_BOT_TOKEN")

    if not bot_token:
        print("❌ No SLACK_BOT_TOKEN found")
        return

    channel_id = input("\nEnter channel ID: ").strip()

    if not channel_id:
        print("❌ No channel ID provided")
        return

    # Calculate date range (last 7 days)
    start_date = datetime.utcnow() - timedelta(days=7)
    oldest = start_date.timestamp()

    print(f"\n📅 Fetching messages from: {start_date.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"   Unix timestamp: {oldest}")

    # Fetch messages from Slack
    print(f"\n🔄 Calling Slack API: conversations.history")
    print(f"   Channel: {channel_id}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {bot_token}"},
                params={
                    "channel": channel_id,
                    "oldest": oldest,
                    "limit": 100  # Fetch up to 100 messages
                },
                timeout=30.0
            )

            data = response.json()

            if not data.get("ok"):
                print(f"\n❌ Slack API Error: {data.get('error')}")

                error = data.get('error')
                if error == "channel_not_found":
                    print("\n💡 Channel not found or bot not invited")
                    print("   Invite bot: /invite @YourBotName")
                elif error == "missing_scope":
                    print("\n💡 Missing scope: channels:history")
                    print("   Add scope and reinstall app")
                elif error == "not_in_channel":
                    print("\n💡 Bot not in channel")
                    print("   Invite bot: /invite @YourBotName")

                return

            messages = data.get("messages", [])

            print(f"\n✅ Fetched {len(messages)} messages from Slack\n")

            if len(messages) == 0:
                print("ℹ️  No messages found in this channel for the last 7 days")
                print("\nPossible reasons:")
                print("1. Channel has no messages in last 7 days")
                print("2. Bot can only see messages after it was added to channel")
                print("3. Try posting a new message in the channel and test again")
                return

            # Analyze messages
            print("📊 Message Analysis:\n")

            user_messages = []
            bot_messages = []
            other_subtypes = []

            for msg in messages:
                # Check if it's a bot message
                if msg.get("bot_id"):
                    bot_messages.append(msg)
                # Check for message subtypes (edits, deletes, etc.)
                elif msg.get("subtype") in ["message_changed", "message_deleted"]:
                    other_subtypes.append(msg)
                # Regular user message
                else:
                    user_messages.append(msg)

            print(f"   Total messages fetched: {len(messages)}")
            print(f"   User messages: {len(user_messages)} ✅ (will be ingested)")
            print(f"   Bot messages: {len(bot_messages)} ❌ (filtered out)")
            print(f"   Message edits/deletes: {len(other_subtypes)} ❌ (filtered out)")

            # Show sample user messages
            if user_messages:
                print(f"\n📝 Sample user messages that WILL be ingested:\n")

                for i, msg in enumerate(user_messages[:5], 1):
                    text = msg.get("text", "")
                    timestamp = datetime.fromtimestamp(float(msg.get("ts"))).strftime("%Y-%m-%d %H:%M:%S")
                    user = msg.get("user", "unknown")

                    print(f"   {i}. [{timestamp}] User {user}")
                    print(f"      {text[:80]}{'...' if len(text) > 80 else ''}")
                    print()

                if len(user_messages) > 5:
                    print(f"   ... and {len(user_messages) - 5} more user messages\n")

            # Show why some messages were filtered
            if bot_messages:
                print(f"🤖 {len(bot_messages)} bot messages (filtered out):")
                for msg in bot_messages[:3]:
                    text = msg.get("text", "")
                    print(f"   - {text[:60]}...")

            if other_subtypes:
                print(f"\n✏️  {len(other_subtypes)} message edits/deletes (filtered out)")

            # Recommendation
            print("\n" + "=" * 60)
            print("\n💡 Recommendation:")

            if len(user_messages) == 0:
                print("\n   No user messages to ingest!")
                print("\n   Steps to test:")
                print("   1. Post a new message in the Slack channel")
                print("   2. Run this script again")
                print("   3. Then run the full ingestion test")
            else:
                print(f"\n   ✅ Found {len(user_messages)} user messages ready to ingest")
                print("\n   Run the ingestion test:")
                print("   uv run python scripts/test_slack_ingestion.py")
                print("\n   Expected result:")
                print(f"   Total ingested: {len(user_messages)}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_slack_fetch())
