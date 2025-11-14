"""
Test hybrid search with vector similarity, keyword matching, and Cohere reranking.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.search import SearchFilters, SearchRequest
from app.services.search import hybrid_search, simple_vector_search


async def test_hybrid_search_basic():
    """Test basic hybrid search without filters."""
    print("\n" + "=" * 80)
    print("TEST 1: Basic Hybrid Search")
    print("=" * 80)

    query = "What are the payment fees?"
    print(f"\nQuery: '{query}'")

    request = SearchRequest(
        query=query,
        match_count=5,
        match_threshold=0.5,
        semantic_weight=0.5,
        keyword_weight=0.5,
        use_reranking=False,  # Test without reranking first
    )

    try:
        response = await hybrid_search(request)

        print(f"\n[OK] Search complete!")
        print(f"Results: {response.total_results}")
        print(f"Execution time: {response.execution_time_ms:.2f}ms")
        print(f"Reranking: {'Yes' if response.reranking_applied else 'No'}")

        print("\nTop 3 Results:")
        for i, result in enumerate(response.results[:3], 1):
            print(f"\n{i}. [{result.source}] {result.title}")
            print(f"   Author: {result.author_name or 'Unknown'}")
            print(f"   Conversation: {result.conversation_name or 'Unknown'}")
            print(f"   Semantic: {result.semantic_score:.4f} | Keyword: {result.keyword_score:.4f} | Combined: {result.combined_score:.4f}")
            print(f"   Content: {result.content[:150]}...")

        return True
    except Exception as e:
        print(f"\n[X] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_hybrid_search_with_reranking():
    """Test hybrid search with Cohere reranking."""
    print("\n" + "=" * 80)
    print("TEST 2: Hybrid Search with Cohere Reranking")
    print("=" * 80)

    query = "payment processing fees and charges"
    print(f"\nQuery: '{query}'")

    request = SearchRequest(
        query=query,
        match_count=5,
        match_threshold=0.5,
        semantic_weight=0.5,
        keyword_weight=0.5,
        use_reranking=True,  # Enable Cohere reranking
    )

    try:
        response = await hybrid_search(request)

        print(f"\n[OK] Search with reranking complete!")
        print(f"Results: {response.total_results}")
        print(f"Execution time: {response.execution_time_ms:.2f}ms")
        print(f"Reranking: {'Yes' if response.reranking_applied else 'No'}")

        print("\nTop 3 Results (After Reranking):")
        for i, result in enumerate(response.results[:3], 1):
            print(f"\n{i}. [{result.source}] {result.title}")
            print(f"   Author: {result.author_name or 'Unknown'}")
            print(f"   Semantic: {result.semantic_score:.4f} | Keyword: {result.keyword_score:.4f}")
            rerank_display = f"{result.rerank_score:.4f}" if result.rerank_score is not None else "N/A"
            print(f"   Combined: {result.combined_score:.4f} | Rerank: {rerank_display}")
            print(f"   Content: {result.content[:150]}...")

        return True
    except Exception as e:
        print(f"\n[X] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_filtered_search():
    """Test hybrid search with metadata filters."""
    print("\n" + "=" * 80)
    print("TEST 3: Filtered Hybrid Search")
    print("=" * 80)

    query = "payment"
    print(f"\nQuery: '{query}'")

    # Filter for Slack messages from last 30 days
    filters = SearchFilters(
        source="slack",
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now(),
    )

    request = SearchRequest(
        query=query,
        match_count=5,
        match_threshold=0.5,
        filters=filters,
        use_reranking=False,
    )

    try:
        response = await hybrid_search(request)

        print(f"\n[OK] Filtered search complete!")
        print(f"Results: {response.total_results}")
        print(f"Execution time: {response.execution_time_ms:.2f}ms")
        print(f"Filters: source={filters.source}, date_range={filters.start_date.date()} to {filters.end_date.date()}")

        print("\nTop 3 Filtered Results:")
        for i, result in enumerate(response.results[:3], 1):
            print(f"\n{i}. [{result.source}] {result.title}")
            print(f"   Timestamp: {result.timestamp}")
            print(f"   Semantic: {result.semantic_score:.4f} | Keyword: {result.keyword_score:.4f}")
            print(f"   Content: {result.content[:150]}...")

        return True
    except Exception as e:
        print(f"\n[X] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_simple_vector_search():
    """Test simple vector search without keyword matching."""
    print("\n" + "=" * 80)
    print("TEST 4: Simple Vector Search (Semantic Only)")
    print("=" * 80)

    query = "How do I process international payments?"
    print(f"\nQuery: '{query}'")

    try:
        results = await simple_vector_search(
            query=query,
            match_count=5,
            match_threshold=0.5,
        )

        print(f"\n[OK] Vector search complete!")
        print(f"Results: {len(results)}")

        print("\nTop 3 Semantic Matches:")
        for i, result in enumerate(results[:3], 1):
            print(f"\n{i}. [{result.source}] {result.title}")
            print(f"   Semantic score: {result.semantic_score:.4f}")
            print(f"   Content: {result.content[:150]}...")

        return True
    except Exception as e:
        print(f"\n[X] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_weight_comparison():
    """Compare different semantic/keyword weight combinations."""
    print("\n" + "=" * 80)
    print("TEST 5: Weight Comparison")
    print("=" * 80)

    query = "payment processing"
    print(f"\nQuery: '{query}'")

    weight_configs = [
        (1.0, 0.0, "Semantic Only"),
        (0.0, 1.0, "Keyword Only"),
        (0.5, 0.5, "Balanced"),
        (0.7, 0.3, "Semantic-Heavy"),
        (0.3, 0.7, "Keyword-Heavy"),
    ]

    for semantic_w, keyword_w, label in weight_configs:
        request = SearchRequest(
            query=query,
            match_count=3,
            match_threshold=0.5,
            semantic_weight=semantic_w,
            keyword_weight=keyword_w,
            use_reranking=False,
        )

        try:
            response = await hybrid_search(request)
            print(f"\n{label} (S={semantic_w}, K={keyword_w}): {response.total_results} results in {response.execution_time_ms:.2f}ms")

            if response.results:
                top = response.results[0]
                print(f"  Top result: [{top.source}] {top.title[:50]}...")
                print(f"  Scores - Semantic: {top.semantic_score:.4f}, Keyword: {top.keyword_score:.4f}, Combined: {top.combined_score:.4f}")

        except Exception as e:
            print(f"  [X] Failed: {e}")

    return True


async def main():
    """Run all hybrid search tests."""
    print("\n" + "=" * 80)
    print("HYBRID SEARCH TEST SUITE")
    print("=" * 80)
    print("\nTesting enhanced search capabilities:")
    print("- Hybrid search (vector + keyword)")
    print("- Cohere reranking (rerank-english-v3.0)")
    print("- Metadata filtering")
    print("- Performance optimization")

    results = []

    # Run tests sequentially
    results.append(("Basic Hybrid Search", await test_hybrid_search_basic()))
    results.append(("Hybrid Search with Reranking", await test_hybrid_search_with_reranking()))
    results.append(("Filtered Search", await test_filtered_search()))
    results.append(("Simple Vector Search", await test_simple_vector_search()))
    results.append(("Weight Comparison", await test_weight_comparison()))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, result in results:
        status = "[OK]" if result else "[X]"
        print(f"{status} {test_name}")

    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n[SUCCESS] All tests passed!")
    else:
        print(f"\n[FAIL] {total - passed} test(s) failed")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
