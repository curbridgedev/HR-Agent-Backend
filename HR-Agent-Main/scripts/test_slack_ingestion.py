"""
Test Slack ingestion functionality.
"""

import asyncio
import httpx
import sys
from datetime import datetime, timedelta

# Fix Unicode encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')


async def test_slack_ingestion():
    """Test Slack historical ingestion endpoint."""

    print("🧪 Testing Slack Ingestion\n")
    print("=" * 60)

    # Test 1: Check server is running
    print("\n1. Checking server status...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("   ✅ Server is running")
            else:
                print(f"   ❌ Server returned {response.status_code}")
                return
    except Exception as e:
        print(f"   ❌ Server not accessible: {e}")
        print("\n   Start the server with:")
        print("   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
        return

    # Test 2: Check Slack credentials are configured
    print("\n2. Checking Slack configuration...")
    import os
    from dotenv import load_dotenv

    load_dotenv()

    slack_token = os.getenv("SLACK_BOT_TOKEN")
    slack_secret = os.getenv("SLACK_SIGNING_SECRET")

    if not slack_token or not slack_secret:
        print("   ❌ Slack credentials not configured")
        print("\n   Add to .env:")
        print("   SLACK_BOT_TOKEN=xoxb-your-token")
        print("   SLACK_SIGNING_SECRET=your-secret")
        return

    if slack_token == "xoxb-your-token":
        print("   ⚠️  Using placeholder token - replace with real token")
        print("\n   Get your token from:")
        print("   https://api.slack.com/apps → Your App → OAuth & Permissions")
        return

    print(f"   ✅ Bot Token: {slack_token[:15]}...")
    print(f"   ✅ Signing Secret: {slack_secret[:8]}...")

    # Test 3: Check sources endpoint
    print("\n3. Checking sources status endpoint...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/api/v1/sources/status")
            if response.status_code == 200:
                data = response.json()
                print("   ✅ Sources endpoint working")
                print(f"   Sources: {', '.join([s['source_type'] for s in data['sources']])}")
            else:
                print(f"   ❌ Sources endpoint returned {response.status_code}")
    except Exception as e:
        print(f"   ❌ Failed to check sources: {e}")

    # Test 4: Test historical ingestion (dry run)
    print("\n4. Testing historical ingestion endpoint...")
    print("\n   ⚠️  Before running this test, you need:")
    print("   - A Slack app with proper OAuth scopes")
    print("   - Bot added to at least one channel")
    print("   - Channel ID from Slack")

    print("\n   To get a channel ID:")
    print("   1. Right-click channel in Slack → View channel details")
    print("   2. Scroll down to find Channel ID (e.g., C01234ABC56)")

    channel_id = input("\n   Enter a Slack channel ID to test (or press Enter to skip): ").strip()

    if not channel_id:
        print("   ⏭️  Skipping historical ingestion test")
        print("\n" + "=" * 60)
        print("\n✅ Basic tests passed!")
        print("\n📝 Next steps:")
        print("   1. Create a Slack app and get credentials")
        print("   2. Add bot to a Slack channel")
        print("   3. Run this script again with a channel ID")
        print("   4. Check backend logs to see ingestion progress")
        return

    # Test historical ingestion
    print(f"\n   Testing ingestion for channel: {channel_id}")

    # Use last 7 days as test range
    start_date = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"

    payload = {
        "channel_ids": [channel_id],
        "start_date": start_date,
        "limit_per_channel": 10  # Limit to 10 messages for testing
    }

    print(f"   Fetching last 7 days (max 10 messages)...")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://localhost:8000/api/v1/sources/slack/ingest",
                json=payload
            )

            print(f"\n   Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print("\n   ✅ Ingestion successful!")
                print(f"   Total ingested: {data['total_ingested']}")
                print(f"   Total failed: {data['total_failed']}")

                for result in data['results']:
                    print(f"\n   Channel: {result['channel_id']}")
                    print(f"   - Ingested: {result.get('ingested', 0)}")
                    print(f"   - Failed: {result.get('failed', 0)}")
                    if 'error' in result:
                        print(f"   - Error: {result['error']}")

                # Verify in database
                print("\n5. Verifying messages in database...")
                try:
                    response = await client.get(
                        "http://localhost:8000/api/v1/documents/?source=slack&page_size=5"
                    )
                    if response.status_code == 200:
                        docs = response.json()
                        print(f"   ✅ Found {docs['total']} Slack documents in database")

                        if docs['documents']:
                            print("\n   Recent Slack documents:")
                            for doc in docs['documents'][:3]:
                                print(f"   - {doc['title']}")
                    else:
                        print(f"   ⚠️  Could not verify documents: {response.status_code}")
                except Exception as e:
                    print(f"   ⚠️  Could not verify documents: {e}")

            else:
                print(f"\n   ❌ Ingestion failed")
                print(f"   Response: {response.text}")

                # Common errors
                if "Invalid credentials" in response.text or "not_authed" in response.text:
                    print("\n   💡 This looks like an authentication error")
                    print("   Check that SLACK_BOT_TOKEN is correct and not expired")
                elif "channel_not_found" in response.text:
                    print("\n   💡 Channel not found")
                    print("   Make sure:")
                    print("   - The channel ID is correct")
                    print("   - The bot has been added to the channel (/invite @BotName)")
                elif "missing_scope" in response.text:
                    print("\n   💡 Missing OAuth scope")
                    print("   Add these scopes in Slack App settings:")
                    print("   - channels:history")
                    print("   - groups:history")
                    print("   - files:read")

    except Exception as e:
        print(f"\n   ❌ Request failed: {e}")
        print("\n   Check backend logs for details:")
        print("   tail -f logs/app.log")

    print("\n" + "=" * 60)
    print("\n✅ Testing complete!")
    print("\n📝 Next steps:")
    print("   1. Check backend logs: tail -f logs/app.log")
    print("   2. Test a query that should match Slack content")
    print("   3. Set up webhook for real-time ingestion")


if __name__ == "__main__":
    asyncio.run(test_slack_ingestion())
