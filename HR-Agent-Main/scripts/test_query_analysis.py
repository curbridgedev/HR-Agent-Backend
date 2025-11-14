"""
Test Query Analysis System

Comprehensive tests for query analysis node including intent classification,
entity extraction, complexity assessment, and routing decisions.
"""

import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_query_analysis_node():
    """Test the analyze_query_node with various query types."""

    print("=" * 70)
    print("Test 1: Query Analysis Node - Various Query Types")
    print("=" * 70)
    print()

    from app.agents.nodes import analyze_query_node
    from app.agents.state import AgentState

    # Test queries covering different intents and complexity levels
    test_queries = [
        {
            "query": "What is Compaytence?",
            "expected_intent": "factual",
            "expected_complexity": "simple",
        },
        {
            "query": "How do I integrate the Compaytence payment API into my application?",
            "expected_intent": "procedural",
            "expected_complexity": "moderate",
        },
        {
            "query": "Why is my credit card payment failing with error code 402?",
            "expected_intent": "troubleshooting",
            "expected_complexity": "moderate",
        },
        {
            "query": "What's the difference between ACH and wire transfer?",
            "expected_intent": "comparison",
            "expected_complexity": "moderate",
        },
        {
            "query": "Explain how PCI DSS compliance works in payment processing",
            "expected_intent": "conceptual",
            "expected_complexity": "complex",
        },
        {
            "query": "What does tokenization mean in the context of payment security?",
            "expected_intent": "definition",
            "expected_complexity": "simple",
        },
    ]

    for i, test_case in enumerate(test_queries, 1):
        print(f">> Test Query {i}: {test_case['query']}")
        print(f"   Expected Intent: {test_case['expected_intent']}")
        print(f"   Expected Complexity: {test_case['expected_complexity']}")
        print()

        # Create minimal state
        state: AgentState = {
            "query": test_case["query"],
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

        # Run analysis
        result = await analyze_query_node(state)
        analysis = result.get("query_analysis")

        if analysis:
            print(f"   [OK] Analysis Complete:")
            print(f"      Intent: {analysis.intent} (confidence: {analysis.intent_confidence:.2f})")
            print(f"      Complexity: {analysis.complexity} (score: {analysis.complexity_score:.2f})")
            print(f"      Routing: {analysis.routing}")
            print(f"      Entities Extracted: {len(analysis.entities)}")

            if analysis.entities:
                print(f"      Key Entities:")
                for entity in analysis.entities[:5]:
                    print(f"        - {entity.text} ({entity.type})")

            if analysis.key_concepts:
                print(f"      Key Concepts: {', '.join(analysis.key_concepts[:5])}")

            print(f"      Search Config:")
            print(f"        - Doc Count: {analysis.suggested_doc_count}")
            print(f"        - Similarity Threshold: {analysis.suggested_similarity_threshold:.2f}")

            print(f"      Analysis Time: {analysis.analysis_time_ms:.0f}ms")
            print()

            # Verify expectations
            if analysis.intent.value == test_case["expected_intent"]:
                print(f"   [PASS] Intent matches expected: {analysis.intent}")
            else:
                print(f"   [INFO] Intent mismatch: got {analysis.intent}, expected {test_case['expected_intent']}")

            if analysis.complexity.value == test_case["expected_complexity"]:
                print(f"   [PASS] Complexity matches expected: {analysis.complexity}")
            else:
                print(f"   [INFO] Complexity: got {analysis.complexity}, expected {test_case['expected_complexity']}")
        else:
            print(f"   [ERROR] Analysis failed: {result.get('error', 'Unknown error')}")

        print()
        print("-" * 70)
        print()


async def test_entity_extraction():
    """Test entity extraction capabilities."""

    print("=" * 70)
    print("Test 2: Entity Extraction")
    print("=" * 70)
    print()

    from app.agents.nodes import analyze_query_node
    from app.agents.state import AgentState

    # Queries with specific entities
    test_queries = [
        "I need to process a $500 credit card payment through your API",
        "How do I set up ACH payments for my customers in the United States?",
        "What are the PCI DSS compliance requirements for storing payment data?",
        "Can I integrate with Stripe, Square, and PayPal using Compaytence?",
    ]

    for query in test_queries:
        print(f">> Query: {query}")
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

        if analysis and analysis.entities:
            print(f"   Extracted {len(analysis.entities)} entities:")
            for entity in analysis.entities:
                print(f"      - {entity.text} (type: {entity.type}, confidence: {entity.confidence:.2f})")
        else:
            print("   No entities extracted")

        print()


async def test_routing_decisions():
    """Test routing decision logic."""

    print("=" * 70)
    print("Test 3: Routing Decisions")
    print("=" * 70)
    print()

    from app.agents.nodes import analyze_query_node
    from app.agents.state import AgentState

    # Queries that should trigger different routing
    test_queries = [
        ("What is Compaytence?", "standard_rag"),
        ("What's 15% of $1,250.50?", "tool_invocation"),
        ("Explain the full process of how international wire transfers work with currency conversion and compliance", "multi_step_reasoning"),
    ]

    for query, expected_routing in test_queries:
        print(f">> Query: {query}")
        print(f"   Expected Routing: {expected_routing}")
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

        if analysis:
            print(f"   Actual Routing: {analysis.routing} (confidence: {analysis.routing_confidence:.2f})")
            print(f"   Reasoning: {analysis.analysis_reasoning[:150]}...")

            if analysis.routing.value == expected_routing:
                print(f"   [PASS] Routing matches expected")
            else:
                print(f"   [INFO] Routing differs from expected (LLM decision may vary)")
        else:
            print(f"   [ERROR] Analysis failed")

        print()


async def test_end_to_end_with_analysis():
    """Test complete agent flow with query analysis."""

    print("=" * 70)
    print("Test 4: End-to-End Agent Flow with Query Analysis")
    print("=" * 70)
    print()

    from app.models.chat import ChatRequest
    from app.services.chat import process_chat

    # Test different query types
    test_queries = [
        "What is Compaytence?",
        "How do I integrate the payment API?",
        "Why might a credit card payment fail?",
    ]

    for query in test_queries:
        print(f">> Testing: {query}")
        print()

        request = ChatRequest(
            message=query,
            session_id="test-e2e-analysis",
            user_id="test-user",
        )

        try:
            response = await process_chat(request)

            print(f"   Response Preview: {response.message[:200]}...")
            print(f"   Confidence: {response.confidence:.2%}")
            print(f"   Escalated: {response.escalated}")
            print(f"   Tokens Used: {response.tokens_used}")
            print(f"   Response Time: {response.response_time_ms}ms")
            print()
            print(f"   [OK] Agent executed successfully with query analysis")
            print(f"   (Check logs for 'Query analysis complete' messages)")
            print()

        except Exception as e:
            print(f"   [ERROR] Error: {e}")
            import traceback
            traceback.print_exc()

        print()


async def test_analysis_performance():
    """Test query analysis performance and consistency."""

    print("=" * 70)
    print("Test 5: Analysis Performance & Consistency")
    print("=" * 70)
    print()

    from app.agents.nodes import analyze_query_node
    from app.agents.state import AgentState

    test_query = "What is Compaytence?"
    iterations = 3

    print(f">> Running analysis {iterations} times to check consistency")
    print(f">> Query: {test_query}")
    print()

    results = []

    for i in range(iterations):
        state: AgentState = {
            "query": test_query,
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

        if analysis:
            results.append({
                "intent": analysis.intent,
                "complexity": analysis.complexity,
                "routing": analysis.routing,
                "time_ms": analysis.analysis_time_ms,
                "entity_count": len(analysis.entities),
            })
            print(f"   Run {i+1}: intent={analysis.intent}, time={analysis.analysis_time_ms:.0f}ms")

    if results:
        # Check consistency
        intents = [r["intent"] for r in results]
        complexities = [r["complexity"] for r in results]
        routings = [r["routing"] for r in results]

        print()
        print(f"   Consistency Check:")
        print(f"      - Intent: {len(set(intents))} unique values - {set(intents)}")
        print(f"      - Complexity: {len(set(complexities))} unique values - {set(complexities)}")
        print(f"      - Routing: {len(set(routings))} unique values - {set(routings)}")

        avg_time = sum(r["time_ms"] for r in results) / len(results)
        print(f"      - Average Analysis Time: {avg_time:.0f}ms")

        if len(set(intents)) == 1:
            print(f"   [PASS] Intent classification is consistent")
        else:
            print(f"   [INFO] Intent classification varies (expected some variation with LLM)")


if __name__ == "__main__":
    print()
    print("=" * 70)
    print(" " * 20 + "QUERY ANALYSIS SYSTEM TEST")
    print("=" * 70)
    print()

    # Run all tests
    asyncio.run(test_query_analysis_node())
    asyncio.run(test_entity_extraction())
    asyncio.run(test_routing_decisions())
    asyncio.run(test_analysis_performance())
    asyncio.run(test_end_to_end_with_analysis())

    print("=" * 70)
    print(">> All Tests Complete!")
    print("=" * 70)
