"""
Test Dynamic Model Discovery

Tests the dynamic model discovery system for all LLM providers.
"""

import asyncio
from dotenv import load_dotenv

load_dotenv()


async def test_model_discovery():
    """Test dynamic model discovery for all providers."""

    print("=" * 70)
    print("Dynamic Model Discovery Test")
    print("=" * 70)
    print()

    from app.utils.llm_client import get_available_models

    providers = ["openai", "anthropic", "google"]

    for provider in providers:
        print(f">> Testing {provider.upper()} Model Discovery")
        print()

        try:
            models = await get_available_models(provider)

            print(f"[SUCCESS] Fetched {len(models)} models from {provider}")
            print()
            print("Available Models:")
            for i, model in enumerate(models[:10], 1):  # Show first 10
                print(f"  {i}. {model}")

            if len(models) > 10:
                print(f"  ... and {len(models) - 10} more")

            print()

        except Exception as e:
            print(f"[ERROR] Failed to fetch {provider} models: {e}")
            print()

        print("-" * 70)
        print()

    # Test caching
    print(">> Testing Cache Performance")
    print()

    import time
    from app.utils.llm_client import get_available_models

    provider = "openai"

    # First call (uncached)
    start = time.time()
    models1 = await get_available_models(provider)
    elapsed1 = (time.time() - start) * 1000

    # Second call (cached)
    start = time.time()
    models2 = await get_available_models(provider)
    elapsed2 = (time.time() - start) * 1000

    print(f"First call (uncached): {elapsed1:.0f}ms")
    print(f"Second call (cached): {elapsed2:.0f}ms")
    if elapsed2 > 0:
        print(f"Speed improvement: {elapsed1/elapsed2:.1f}x faster")
    else:
        print("Speed improvement: Both calls completed in <1ms (too fast to measure)")
    print()

    if models1 == models2:
        print("[OK] Cache returned same models")
    else:
        print("[ERROR] Cache returned different models!")

    print()
    print("=" * 70)
    print("Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_model_discovery())
