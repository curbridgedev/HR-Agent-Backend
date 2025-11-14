"""
Test LangFuse session tracking with multiple traces in the same session.

This demonstrates how multiple chat interactions are grouped together
in a single session for conversation replay and analysis.
"""

import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_session_tracking():
    """Test session tracking with multiple queries in the same session."""

    print("=" * 70)
    print("Testing LangFuse Session Tracking")
    print("=" * 70)
    print()

    from app.models.chat import ChatRequest
    from app.services.chat import process_chat

    # Same session for all queries
    session_id = "test-conversation-123"
    user_id = "user-alice"

    # Simulate a multi-turn conversation
    queries = [
        "What is Compaytence?",
        "What payment methods does it support?",
        "How does the confidence scoring work?",
    ]

    print(f"Session ID: {session_id}")
    print(f"User ID: {user_id}")
    print(f"Number of queries: {len(queries)}")
    print()

    for i, query in enumerate(queries, 1):
        print("-" * 70)
        print(f"Query {i}/{len(queries)}: {query}")
        print("-" * 70)

        request = ChatRequest(
            message=query,
            session_id=session_id,  # Same session for all
            user_id=user_id,
        )

        try:
            response = await process_chat(request)

            print(f"Response: {response.message[:200]}...")
            print(f"Confidence: {response.confidence:.2%}")
            print(f"Escalated: {response.escalated}")
            print(f"Tokens: {response.tokens_used}")
            print(f"Response time: {response.response_time_ms}ms")
            print()

        except Exception as e:
            print(f"Error: {e}")
            print()

    print("=" * 70)
    print(">> Test Complete!")
    print()
    print("Check your LangFuse dashboard:")
    print("1. Go to https://cloud.langfuse.com")
    print("2. Navigate to 'Sessions' tab")
    print(f"3. Look for session: {session_id}")
    print("4. You should see all 3 traces grouped together!")
    print("=" * 70)


async def test_multiple_sessions():
    """Test with multiple different sessions to show session grouping."""

    print()
    print("=" * 70)
    print("Testing Multiple Sessions")
    print("=" * 70)
    print()

    from app.models.chat import ChatRequest
    from app.services.chat import process_chat

    # Different sessions and users
    sessions = [
        {
            "session_id": "session-bob-1",
            "user_id": "user-bob",
            "query": "How does Compaytence handle refunds?",
        },
        {
            "session_id": "session-carol-1",
            "user_id": "user-carol",
            "query": "What are the supported payment methods?",
        },
    ]

    for i, session_data in enumerate(sessions, 1):
        print(f"Session {i}: {session_data['session_id']} (User: {session_data['user_id']})")

        request = ChatRequest(
            message=session_data["query"],
            session_id=session_data["session_id"],
            user_id=session_data["user_id"],
        )

        try:
            response = await process_chat(request)
            print(f"  Response: {response.message[:100]}...")
            print(f"  Confidence: {response.confidence:.2%}")
            print()
        except Exception as e:
            print(f"  Error: {e}")
            print()

    print("=" * 70)
    print(">> Multiple sessions created!")
    print("Each session should appear separately in the LangFuse dashboard.")
    print("=" * 70)


if __name__ == "__main__":
    print()
    print("=" * 70)
    print(" " * 15 + "LANGFUSE SESSION TRACKING TEST")
    print("=" * 70)
    print()

    # Test 1: Single session with multiple traces
    asyncio.run(test_session_tracking())

    # Test 2: Multiple different sessions
    asyncio.run(test_multiple_sessions())
