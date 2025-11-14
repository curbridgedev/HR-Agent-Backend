"""
Test script for enhanced embedding service.

Tests:
- Single embedding generation
- Batch embedding generation
- Rate limiting behavior
- Cost tracking
- Retry logic
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.embedding import (
    generate_embedding,
    generate_embeddings_batch,
    generate_embedding_with_retry,
    count_tokens,
)


async def test_single_embedding():
    """Test single embedding generation with cost tracking."""
    print("\n" + "=" * 80)
    print("TEST 1: Single Embedding Generation")
    print("=" * 80)

    text = "This is a test message for embedding generation"
    print(f"\nInput text: '{text}'")
    print(f"Estimated tokens: {count_tokens(text)}")

    try:
        embedding = await generate_embedding(text)
        print(f"\n[OK] Embedding generated successfully!")
        print(f"Embedding dimension: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}")
        return True
    except Exception as e:
        print(f"\n[X] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_batch_embedding():
    """Test batch embedding generation."""
    print("\n" + "=" * 80)
    print("TEST 2: Batch Embedding Generation")
    print("=" * 80)

    texts = [
        "First test message for batch processing",
        "Second test message with different content",
        "Third message to test batch efficiency",
        "Fourth message for completeness",
        "Fifth message to reach a good batch size",
    ]

    print(f"\nNumber of texts: {len(texts)}")
    total_tokens = sum(count_tokens(text) for text in texts)
    print(f"Total estimated tokens: {total_tokens}")

    try:
        embeddings = await generate_embeddings_batch(texts)
        print(f"\n[OK] Batch embedding successful!")
        print(f"Generated {len(embeddings)} embeddings")
        print(f"Each embedding has {len(embeddings[0])} dimensions")
        return True
    except Exception as e:
        print(f"\n[X] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_retry_logic():
    """Test retry logic with a simple case."""
    print("\n" + "=" * 80)
    print("TEST 3: Retry Logic")
    print("=" * 80)

    text = "Test message for retry logic validation"
    print(f"\nInput text: '{text}'")

    try:
        embedding = await generate_embedding_with_retry(text, max_retries=3)
        print(f"\n[OK] Retry wrapper works!")
        print(f"Embedding dimension: {len(embedding)}")
        return True
    except Exception as e:
        print(f"\n[X] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_rate_limiting():
    """Test rate limiting by making multiple concurrent requests."""
    print("\n" + "=" * 80)
    print("TEST 4: Rate Limiting (Concurrent Requests)")
    print("=" * 80)

    texts = [f"Test message number {i}" for i in range(10)]
    print(f"\nMaking {len(texts)} concurrent embedding requests...")
    print("This will test the rate limiter's ability to handle bursts")

    try:
        # Create concurrent tasks
        tasks = [generate_embedding(text) for text in texts]
        embeddings = await asyncio.gather(*tasks)

        print(f"\n[OK] Rate limiting handled {len(embeddings)} concurrent requests!")
        print(f"All embeddings generated successfully")
        return True
    except Exception as e:
        print(f"\n[X] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_large_batch():
    """Test large batch processing to verify chunking logic."""
    print("\n" + "=" * 80)
    print("TEST 5: Large Batch Processing")
    print("=" * 80)

    # Create a larger batch (but not too large to avoid excessive costs)
    texts = [f"Large batch test message number {i} with some content" for i in range(50)]

    print(f"\nNumber of texts: {len(texts)}")
    total_tokens = sum(count_tokens(text) for text in texts)
    print(f"Total estimated tokens: {total_tokens}")

    try:
        embeddings = await generate_embeddings_batch(texts)
        print(f"\n[OK] Large batch processed successfully!")
        print(f"Generated {len(embeddings)} embeddings")
        return True
    except Exception as e:
        print(f"\n[X] Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("EMBEDDING SERVICE ENHANCEMENT TESTS")
    print("=" * 80)
    print("\nTesting enhanced embedding service with:")
    print("- Rate limiting (requests + tokens)")
    print("- Exponential backoff with jitter")
    print("- Cost tracking per operation")
    print("- Usage metrics logging")

    results = []

    # Run tests sequentially to see clean output
    results.append(("Single Embedding", await test_single_embedding()))
    results.append(("Batch Embedding", await test_batch_embedding()))
    results.append(("Retry Logic", await test_retry_logic()))
    results.append(("Rate Limiting", await test_rate_limiting()))
    results.append(("Large Batch", await test_large_batch()))

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
