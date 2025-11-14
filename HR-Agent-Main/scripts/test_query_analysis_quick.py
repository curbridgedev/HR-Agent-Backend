"""
Quick Query Analysis Test - Single query validation
"""

import asyncio
from dotenv import load_dotenv

load_dotenv()


async def test_single_query():
    """Test query analysis with a single query."""

    print("=" * 70)
    print("Quick Query Analysis Test")
    print("=" * 70)
    print()

    from app.agents.nodes import analyze_query_node
    from app.agents.state import AgentState

    query = "What is Compaytence?"
    print(f">> Testing Query: {query}")
    print()

    state: AgentState = {
        "query": query,
        "session_id": "test-session",
        "user_id": "test-user",
        "query_analysis": None,
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

    result = await analyze_query_node(state)
    analysis = result.get("query_analysis")
    error = result.get("error")

    if error:
        print(f"[ERROR] {error}")
        return

    if analysis:
        print(f"[SUCCESS] Query Analysis Complete")
        print()
        print(f"Intent: {analysis.intent} (confidence: {analysis.intent_confidence:.2f})")
        print(f"Complexity: {analysis.complexity} (score: {analysis.complexity_score:.2f})")
        print(f"Routing: {analysis.routing} (confidence: {analysis.routing_confidence:.2f})")
        print()
        print(f"Entities Extracted: {len(analysis.entities)}")
        for entity in analysis.entities:
            print(f"  - {entity.text} (type: {entity.type}, conf: {entity.confidence:.2f})")
        print()
        print(f"Key Concepts: {', '.join(analysis.key_concepts) if analysis.key_concepts else 'None'}")
        print(f"Topics: {', '.join(analysis.query_topics) if analysis.query_topics else 'None'}")
        print()
        print(f"Search Configuration:")
        print(f"  - Document Count: {analysis.suggested_doc_count}")
        print(f"  - Similarity Threshold: {analysis.suggested_similarity_threshold:.2f}")
        print(f"  - Requires Tools: {analysis.requires_tools}")
        print()
        print(f"Analysis Time: {analysis.analysis_time_ms:.0f}ms")
        print()
        print(f"Reasoning: {analysis.analysis_reasoning[:200]}...")
        print()
        print("[OK] All fields populated correctly")
    else:
        print("[ERROR] No analysis result returned")


if __name__ == "__main__":
    asyncio.run(test_single_query())
