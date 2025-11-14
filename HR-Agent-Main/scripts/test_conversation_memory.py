"""
Test script for conversation memory functionality.

Tests multi-turn conversations to ensure agent remembers context.
"""

import asyncio
import uuid
from datetime import datetime

from app.services.chat import (
    process_chat,
    get_conversation_history_for_agent,
    save_chat_message,
    ensure_chat_session,
)
from app.models.chat import ChatRequest
from app.core.logging import get_logger

logger = get_logger(__name__)


async def test_conversation_memory():
    """
    Test conversation memory with multi-turn scenario.

    Simulates:
    1. User asks about refund policy
    2. User asks follow-up question using "it" (requires context)
    3. User asks about international orders (requires remembering refund context)
    """
    print("\n" + "="*80)
    print("CONVERSATION MEMORY TEST")
    print("="*80 + "\n")

    # Generate unique session ID for this test
    session_id = f"test-memory-{uuid.uuid4()}"
    user_id = "test-user-memory"

    print(f" Session ID: {session_id}")
    print(f" User ID: {user_id}\n")

    # Ensure session exists
    await ensure_chat_session(session_id, user_id)

    # Test Case 1: Initial question
    print("="*80)
    print("TEST 1: Initial Question (No History)")
    print("="*80)
    query_1 = "What is your refund policy?"
    print(f"\n  User: {query_1}\n")

    request_1 = ChatRequest(
        message=query_1,
        session_id=session_id,
        user_id=user_id,
    )

    response_1 = await process_chat(request_1)
    print(f" Assistant: {response_1.message}\n")
    print(f" Confidence: {response_1.confidence:.2f}")
    print(f" Sources: {len(response_1.sources)} documents")
    print(f"  Response time: {response_1.response_time_ms}ms\n")

    # Wait a moment to ensure messages are saved
    await asyncio.sleep(1)

    # Check conversation history
    history_1 = await get_conversation_history_for_agent(session_id)
    print(f" Conversation history: {len(history_1)} messages")
    for i, msg in enumerate(history_1, 1):
        print(f"   {i}. [{msg['role']}]: {msg['content'][:60]}...")

    # Test Case 2: Follow-up with pronoun reference
    print("\n" + "="*80)
    print("TEST 2: Follow-up Question (Should Remember 'Refund Policy')")
    print("="*80)
    query_2 = "How long does it take?"
    print(f"\n  User: {query_2}")
    print("   (Agent should understand 'it' refers to refund from previous context)\n")

    request_2 = ChatRequest(
        message=query_2,
        session_id=session_id,
        user_id=user_id,
    )

    response_2 = await process_chat(request_2)
    print(f" Assistant: {response_2.message}\n")
    print(f" Confidence: {response_2.confidence:.2f}")
    print(f" Sources: {len(response_2.sources)} documents")
    print(f"  Response time: {response_2.response_time_ms}ms\n")

    # Wait a moment
    await asyncio.sleep(1)

    # Check updated history
    history_2 = await get_conversation_history_for_agent(session_id)
    print(f" Conversation history: {len(history_2)} messages")
    for i, msg in enumerate(history_2, 1):
        print(f"   {i}. [{msg['role']}]: {msg['content'][:60]}...")

    # Test Case 3: Related follow-up
    print("\n" + "="*80)
    print("TEST 3: Related Follow-up (Should Maintain Context)")
    print("="*80)
    query_3 = "What about international orders?"
    print(f"\n  User: {query_3}")
    print("   (Agent should connect this to refund policy from earlier)\n")

    request_3 = ChatRequest(
        message=query_3,
        session_id=session_id,
        user_id=user_id,
    )

    response_3 = await process_chat(request_3)
    print(f" Assistant: {response_3.message}\n")
    print(f" Confidence: {response_3.confidence:.2f}")
    print(f" Sources: {len(response_3.sources)} documents")
    print(f"  Response time: {response_3.response_time_ms}ms\n")

    # Wait a moment
    await asyncio.sleep(1)

    # Final history check
    history_3 = await get_conversation_history_for_agent(session_id)
    print(f" Final conversation history: {len(history_3)} messages")
    for i, msg in enumerate(history_3, 1):
        role_emoji = "" if msg['role'] == "user" else ""
        print(f"   {i}. {role_emoji} [{msg['role']}]: {msg['content'][:80]}...")

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f" Total messages in conversation: {len(history_3)}")
    print(f" User messages: {sum(1 for m in history_3 if m['role'] == 'user')}")
    print(f" Assistant messages: {sum(1 for m in history_3 if m['role'] == 'assistant')}")
    print(f"\n Expected behavior:")
    print("   - First query: No history, purely retrieval-based")
    print("   - Second query: Agent uses 'refund policy' from conversation history")
    print("   - Third query: Agent connects to refund context from history")
    print(f"\n Conversation memory is {'WORKING' if len(history_3) >= 4 else 'NOT WORKING'}!")
    print("="*80 + "\n")


async def test_token_limit():
    """Test that conversation history respects token limits."""
    print("\n" + "="*80)
    print("TOKEN LIMIT TEST")
    print("="*80 + "\n")

    session_id = f"test-tokens-{uuid.uuid4()}"
    user_id = "test-user-tokens"

    print(f" Session ID: {session_id}\n")

    # Create session
    await ensure_chat_session(session_id, user_id)

    # Add many messages to test sliding window
    print("Adding 15 messages to test token limit...\n")
    for i in range(15):
        await save_chat_message(
            session_id=session_id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"This is test message number {i+1}. " * 20,  # Long message
            user_id=user_id,
        )

    # Retrieve with token limit
    history = await get_conversation_history_for_agent(
        session_id=session_id,
        max_messages=20,
        max_tokens=500,  # Very low limit
    )

    print(f" Messages saved: 15")
    print(f" Messages retrieved (with 500 token limit): {len(history)}")
    print(f" Token limit correctly enforced: {len(history) < 15}")

    # Calculate approximate tokens
    total_chars = sum(len(msg['content']) for msg in history)
    estimated_tokens = total_chars // 4
    print(f" Estimated tokens in retrieved history: ~{estimated_tokens}")
    print(f" Within limit: {estimated_tokens <= 500}\n")

    print("="*80 + "\n")


async def main():
    """Run all tests."""
    print("\n[*] Starting Conversation Memory Tests\n")

    try:
        # Test 1: Multi-turn conversation
        await test_conversation_memory()

        # Test 2: Token limits
        await test_token_limit()

        print("\n[SUCCESS] All tests completed!\n")

    except Exception as e:
        print(f"\n[ERROR] Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
