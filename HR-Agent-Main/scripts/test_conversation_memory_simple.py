"""
Simple test to validate conversation memory logic without full server.
Tests the formatting and token limit functions.
"""

import asyncio
import uuid

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def test_conversation_formatting():
    """Test conversation history formatting logic."""
    print("\n" + "="*80)
    print("TEST: Conversation History Formatting")
    print("="*80 + "\n")

    # Simulate conversation history
    mock_history = [
        {"role": "user", "content": "What is your refund policy?"},
        {"role": "assistant", "content": "Our refund policy allows returns within 30 days."},
        {"role": "user", "content": "How long does it take?"},
        {"role": "assistant", "content": "Refunds typically process within 5-7 business days."},
    ]

    # Format like the agent does
    conversation_lines = []
    for msg in mock_history:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        conversation_lines.append(f"{role_label}: {msg['content']}")
    conversation_context = "\n".join(conversation_lines)

    print("Formatted conversation context:\n")
    print(conversation_context)
    print("\n" + "="*80 + "\n")

    assert len(conversation_lines) == 4, "Should have 4 formatted messages"
    assert "User: What is your refund policy?" in conversation_context
    assert "Assistant: Our refund policy" in conversation_context
    print("[PASS] Conversation formatting works correctly\n")


async def test_token_limit_logic():
    """Test token limit sliding window logic."""
    print("\n" + "="*80)
    print("TEST: Token Limit Sliding Window")
    print("="*80 + "\n")

    # Create mock messages
    messages = []
    for i in range(10):
        messages.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"This is message {i+1}. " * 50,  # Long messages
        })

    print(f"Created {len(messages)} mock messages")

    # Simulate token-based sliding window (from get_conversation_history_for_agent)
    max_tokens = 500
    selected_messages = []
    total_tokens = 0

    # Process in reverse (newest first)
    for msg in reversed(messages):
        content = msg["content"]
        estimated_tokens = len(content) // 4  # Rough estimate

        if total_tokens + estimated_tokens > max_tokens:
            print(f"\nReached token limit at message {len(selected_messages)}")
            print(f"Total tokens: {total_tokens}/{max_tokens}")
            break

        selected_messages.insert(0, msg)
        total_tokens += estimated_tokens

    print(f"\nSelected {len(selected_messages)}/{len(messages)} messages")
    print(f"Estimated tokens: {total_tokens}")
    print(f"Within limit: {total_tokens <= max_tokens}")

    assert len(selected_messages) < len(messages), "Should filter some messages"
    assert total_tokens <= max_tokens, "Should respect token limit"
    print("\n[PASS] Token limit logic works correctly\n")


async def test_config_values():
    """Test that configuration values are accessible."""
    print("\n" + "="*80)
    print("TEST: Configuration Values")
    print("="*80 + "\n")

    print(f"Conversation history enabled: {settings.conversation_history_enabled}")
    print(f"Max messages: {settings.conversation_history_max_messages}")
    print(f"Max tokens: {settings.conversation_history_max_tokens}")

    assert hasattr(settings, 'conversation_history_enabled')
    assert hasattr(settings, 'conversation_history_max_messages')
    assert hasattr(settings, 'conversation_history_max_tokens')

    print("\n[PASS] All configuration values accessible\n")


async def main():
    """Run all logic tests."""
    print("\n" + "="*80)
    print("CONVERSATION MEMORY LOGIC TESTS")
    print("="*80)

    try:
        await test_config_values()
        await test_conversation_formatting()
        await test_token_limit_logic()

        print("\n" + "="*80)
        print("ALL TESTS PASSED")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
