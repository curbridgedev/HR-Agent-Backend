"""
Test script to simulate Slack webhook call with PII locally.

This sends a fake Slack message containing PII (email and phone number)
to the local webhook endpoint to test the full ingestion flow.
"""

import hashlib
import hmac
import json
import time
from dotenv import load_dotenv
import os
import httpx

# Load environment variables
load_dotenv()

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
WEBHOOK_URL = "http://localhost:8000/api/v1/webhooks/slack"


def generate_slack_signature(timestamp: str, body: str) -> str:
    """Generate Slack signature for webhook verification."""
    sig_basestring = f"v0:{timestamp}:{body}"
    signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()
    return signature


def test_slack_message_with_pii():
    """Send a test Slack message containing PII."""

    # Slack event payload with PII
    event_data = {
        "token": "test_token",
        "team_id": "T123456",
        "api_app_id": "A123456",
        "event": {
            "type": "message",
            "user": "U092Q2NAVV4",
            "text": "Please contact me at john.doe@example.com or call +1-555-123-4567",
            "ts": str(time.time()),
            "channel": "C09Q2H6LXSL",
            "event_ts": str(time.time()),
        },
        "type": "event_callback",
        "event_id": "Ev123456",
        "event_time": int(time.time()),
    }

    # Convert to JSON string
    body = json.dumps(event_data)

    # Generate timestamp and signature
    timestamp = str(int(time.time()))
    signature = generate_slack_signature(timestamp, body)

    # Headers
    headers = {
        "Content-Type": "application/json",
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature,
    }

    print(">> Sending test Slack message with PII...")
    print(f"   Message: {event_data['event']['text']}")
    print(f"   URL: {WEBHOOK_URL}")
    print()

    try:
        # Send request
        response = httpx.post(WEBHOOK_URL, headers=headers, content=body, timeout=60.0)

        print(f">> Response Status: {response.status_code}")
        print(f">> Response Body:")
        print(json.dumps(response.json(), indent=2))

        if response.status_code == 200:
            print()
            print(">> Test successful! Check the server logs above for:")
            print("   1. PII detection (should find EMAIL and PHONE_NUMBER)")
            print("   2. Anonymization (should replace with placeholders)")
            print("   3. Embedding generation (should call OpenAI API)")
            print("   4. Database insertion (should store in Supabase)")
        else:
            print()
            print(">> Test failed - check error details above")

    except Exception as e:
        print(f">> Error sending request: {e}")


if __name__ == "__main__":
    if not SLACK_SIGNING_SECRET:
        print(">> ERROR: SLACK_SIGNING_SECRET not found in .env file")
        exit(1)

    test_slack_message_with_pii()
