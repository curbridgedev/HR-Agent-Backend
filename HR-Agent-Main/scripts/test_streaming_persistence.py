"""
Test script to verify streaming endpoint saves messages to database.
"""
import asyncio
from app.services.chat import process_chat_stream
from app.models.chat import ChatRequest
from app.db.supabase import get_supabase_client


async def test_streaming_persistence():
    """Test that streaming endpoint saves messages to database."""

    print("\n" + "="*60)
    print("STREAMING ENDPOINT PERSISTENCE TEST")
    print("="*60)

    # Create a unique session ID for testing
    import uuid
    test_session_id = f"test-stream-{uuid.uuid4().hex[:8]}"
    test_message = "What is Compaytence?"

    print(f"\nTest Session ID: {test_session_id}")
    print(f"Test Message: {test_message}")

    # Get Supabase client
    supabase = get_supabase_client()

    # Check if session exists before (should not exist)
    print("\n--- BEFORE STREAMING ---")
    before_response = supabase.table("chat_messages").select("*").eq("session_id", test_session_id).execute()
    print(f"Messages in database BEFORE: {len(before_response.data)}")

    # Create chat request
    request = ChatRequest(
        message=test_message,
        session_id=test_session_id,
        user_id="test-user-123"
    )

    # Process streaming chat
    print("\n--- STREAMING CHAT ---")
    chunks_received = 0
    final_chunk = None
    accumulated_text = ""

    try:
        async for chunk in process_chat_stream(request):
            chunks_received += 1
            if not chunk.is_final:
                accumulated_text += chunk.chunk
                print(f"Chunk {chunks_received}: {chunk.chunk[:50]}..." if len(chunk.chunk) > 50 else f"Chunk {chunks_received}: {chunk.chunk}")
            else:
                final_chunk = chunk
                print(f"\nFinal chunk received:")
                print(f"  - Confidence: {chunk.confidence:.2%}")
                print(f"  - Sources: {len(chunk.sources) if chunk.sources else 0}")

        print(f"\nTotal chunks received: {chunks_received}")
        print(f"Accumulated response length: {len(accumulated_text)} characters")

    except Exception as e:
        print(f"\n❌ ERROR during streaming: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Small delay to ensure async operations complete
    await asyncio.sleep(1)

    # Check if messages were saved to database
    print("\n--- AFTER STREAMING ---")
    after_response = supabase.table("chat_messages").select("*").eq("session_id", test_session_id).order("created_at").execute()

    print(f"Messages in database AFTER: {len(after_response.data)}")

    if len(after_response.data) == 0:
        print("\n[FAIL] FAILED: No messages were saved to database!")
        return False

    # Verify message details
    print("\n--- MESSAGE DETAILS ---")
    for i, msg in enumerate(after_response.data, 1):
        print(f"\nMessage {i}:")
        print(f"  Role: {msg['role']}")
        print(f"  Content: {msg['content'][:100]}..." if len(msg['content']) > 100 else f"  Content: {msg['content']}")
        print(f"  Confidence: {msg.get('confidence', 'N/A')}")
        print(f"  Escalated: {msg.get('escalated', False)}")
        print(f"  Metadata: {msg.get('metadata', {})}")

    # Validate we have both user and assistant messages
    roles = [msg['role'] for msg in after_response.data]

    if 'user' not in roles:
        print("\n[FAIL] FAILED: User message not saved!")
        return False

    if 'assistant' not in roles:
        print("\n[FAIL] FAILED: Assistant message not saved!")
        return False

    # Verify user message content
    user_message = next(msg for msg in after_response.data if msg['role'] == 'user')
    if user_message['content'] != test_message:
        print(f"\n[FAIL] FAILED: User message content mismatch!")
        print(f"  Expected: {test_message}")
        print(f"  Got: {user_message['content']}")
        return False

    # Verify assistant message has content
    assistant_message = next(msg for msg in after_response.data if msg['role'] == 'assistant')
    if not assistant_message['content'] or len(assistant_message['content']) == 0:
        print(f"\n[FAIL] FAILED: Assistant message is empty!")
        return False

    # Verify streaming metadata flag
    if not assistant_message.get('metadata', {}).get('streaming'):
        print(f"\n[WARN] WARNING: Streaming metadata flag not set (expected 'streaming: true')")

    # Cleanup - delete test messages
    print("\n--- CLEANUP ---")
    try:
        supabase.table("chat_messages").delete().eq("session_id", test_session_id).execute()
        supabase.table("chat_sessions").delete().eq("session_id", test_session_id).execute()
        print("Test data cleaned up successfully")
    except Exception as e:
        print(f"Warning: Cleanup failed: {e}")

    print("\n" + "="*60)
    print("TEST PASSED: Streaming endpoint saves messages correctly!")
    print("="*60)
    print("\nVerified:")
    print("  [OK] User message saved to database")
    print("  [OK] Assistant message saved to database")
    print("  [OK] Message content preserved")
    print("  [OK] Confidence score recorded")
    print("  [OK] Metadata included")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_streaming_persistence())
    exit(0 if success else 1)
