"""
Test script to verify LangGraph agent works end-to-end.

This tests the complete agent flow:
1. Retrieve context from vector store
2. Generate response with OpenAI
3. Calculate confidence score
4. Make escalation decision
5. Format output with sources
"""

import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_agent_with_real_data():
    """Test agent with a real query against ingested data."""

    print("=" * 60)
    print("Testing LangGraph Agent End-to-End")
    print("=" * 60)
    print()

    # Import after loading env
    from app.agents.graph import get_agent_graph
    from app.core.config import settings

    # Test query
    test_query = "What is Compaytence?"

    print(f"Query: {test_query}")
    print(f"Confidence Threshold: {settings.agent_confidence_threshold}")
    print()

    # Prepare initial state
    initial_state = {
        "query": test_query,
        "session_id": "test-session-123",
        "user_id": "test-user",
        "context_documents": [],
        "context_text": "",
        "confidence_score": 0.0,
        "reasoning": "",
        "response": "",
        "sources": [],
        "escalated": False,
        "escalation_reason": None,
        "tokens_used": 0,
        "error": None,
    }

    try:
        # Get agent graph
        print(">> Initializing agent graph...")
        agent_graph = get_agent_graph()
        print("   Agent graph ready")
        print()

        # Invoke agent
        print(">> Invoking agent...")
        final_state = await agent_graph.ainvoke(initial_state)
        print("   Agent execution complete")
        print()

        # Display results
        print("=" * 60)
        print("AGENT RESULTS")
        print("=" * 60)
        print()

        print(f">> Response ({len(final_state.get('response', ''))} chars):")
        print(f"   {final_state.get('response', 'No response generated')}")
        print()

        print(f">> Confidence Score: {final_state.get('confidence_score', 0.0):.2%}")
        print()

        print(f">> Escalated: {final_state.get('escalated', False)}")
        if final_state.get('escalation_reason'):
            print(f"   Reason: {final_state.get('escalation_reason')}")
        print()

        print(f">> Context Documents Retrieved: {len(final_state.get('context_documents', []))}")
        print()

        print(f">> Tokens Used: {final_state.get('tokens_used', 0)}")
        print()

        if final_state.get('sources'):
            print(f">> Sources ({len(final_state.get('sources', []))}):")
            for i, source in enumerate(final_state.get('sources', []), 1):
                print(f"   {i}. {source.get('source', 'unknown')} (similarity: {source.get('similarity_score', 0):.2%})")
                print(f"      {source.get('content', '')[:100]}...")
            print()

        if final_state.get('error'):
            print(f">> Error: {final_state.get('error')}")
            print()

        # Test result
        print("=" * 60)
        if final_state.get('response') and not final_state.get('error'):
            print(">> TEST RESULT: SUCCESS")
            print("   The agent is working correctly!")
        else:
            print(">> TEST RESULT: FAILED")
            print("   Check error details above")
        print("=" * 60)

    except Exception as e:
        print()
        print("=" * 60)
        print(">> TEST RESULT: ERROR")
        print(f"   {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()


async def test_chat_endpoint():
    """Test the chat endpoint wrapper."""

    print()
    print("=" * 60)
    print("Testing Chat Service (API wrapper)")
    print("=" * 60)
    print()

    from app.models.chat import ChatRequest
    from app.services.chat import process_chat

    request = ChatRequest(
        message="What payment methods does Compaytence support?",
        session_id="test-session-456",
        user_id="test-user",
    )

    print(f"Message: {request.message}")
    print()

    try:
        print(">> Processing chat request...")
        response = await process_chat(request)
        print("   Chat processing complete")
        print()

        print("=" * 60)
        print("CHAT RESPONSE")
        print("=" * 60)
        print()

        print(f">> Message: {response.message}")
        print()
        print(f">> Confidence: {response.confidence:.2%}")
        print(f">> Escalated: {response.escalated}")
        print(f">> Response Time: {response.response_time_ms}ms")
        print(f">> Tokens Used: {response.tokens_used}")
        print(f">> Sources: {len(response.sources)}")
        print()

        print("=" * 60)
        if response.message and response.confidence > 0:
            print(">> TEST RESULT: SUCCESS")
        else:
            print(">> TEST RESULT: FAILED")
        print("=" * 60)

    except Exception as e:
        print()
        print("=" * 60)
        print(">> TEST RESULT: ERROR")
        print(f"   {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print()
    print("=" * 60)
    print("COMPAYTENCE AGENT TEST SUITE")
    print("=" * 60)
    print()

    # Run tests
    asyncio.run(test_agent_with_real_data())
    print()
    asyncio.run(test_chat_endpoint())
