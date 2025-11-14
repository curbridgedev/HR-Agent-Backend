"""
Test chat endpoint to verify end-to-end functionality.
"""

import asyncio
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.chat import process_chat
from app.models.chat import ChatRequest
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def test_chat():
    """Test the chat service with sample queries."""

    test_queries = [
        "What is Compaytence?",
        "How does Compaytence work?",
        "What features does Compaytence offer?",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"Test {i}: {query}")
        print(f"{'='*80}\n")

        # Create request
        request = ChatRequest(
            message=query,
            session_id=f"test-session-{i}",
            user_id="test-user",
        )

        # Process chat
        response = await process_chat(request)

        # Display results
        print(f"Response: {response.message[:200]}...")
        print(f"\nConfidence: {response.confidence:.2%}")
        print(f"Escalated: {response.escalated}")
        print(f"Sources: {len(response.sources)} documents")
        print(f"Response Time: {response.response_time_ms}ms")
        print(f"Tokens Used: {response.tokens_used}")

        if response.sources:
            print("\nTop Sources:")
            for j, source in enumerate(response.sources[:3], 1):
                print(f"  {j}. {source.source} - Similarity: {source.similarity_score:.2%}")

        if response.escalated:
            print(f"\nEscalation Reason: {response.escalation_reason}")

        # Check if successful
        if not response.escalated and response.confidence >= 0.5:
            print("\n✓ Test PASSED")
        else:
            print("\n✗ Test needs review")


if __name__ == "__main__":
    print("Chat Endpoint Test")
    print("=" * 80)
    asyncio.run(test_chat())
