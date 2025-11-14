"""Quick test to verify vector search is working."""
import asyncio
from app.agents.graph import get_agent_graph


async def test_vector_search():
    """Test vector search with query."""
    graph = get_agent_graph()

    state = {
        "query": "What is Compaytence?",
        "session_id": "test",
        "user_id": "test",
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

    result = await graph.ainvoke(state)

    docs = result.get("context_documents", [])

    print("\n" + "="*60)
    print("VECTOR SEARCH VERIFICATION")
    print("="*60)
    print(f"\nQuery: {state['query']}")
    print(f"Documents retrieved: {len(docs)}")
    print(f"Confidence score: {result.get('confidence_score', 0.0):.2%}")
    print(f"Escalated: {result.get('escalated', False)}")

    if docs:
        print(f"\nDocument details:")
        for i, doc in enumerate(docs, 1):
            similarity = doc.get("similarity_score", 0.0)
            source = doc.get("source", "unknown")
            content = doc.get("content", "")[:150]

            print(f"\n  {i}. Similarity: {similarity:.4f}")
            print(f"     Source: {source}")
            print(f"     Content: {content}...")

    print(f"\nResponse preview:")
    response = result.get("response", "")
    print(f"  {response[:300]}...")

    print("\n" + "="*60)
    print("✅ Vector search is working!" if docs else "❌ No documents retrieved")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_vector_search())
