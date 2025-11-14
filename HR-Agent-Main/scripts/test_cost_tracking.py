"""
Test cost tracking with text-embedding-3-large model.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.embedding import generate_embedding
from app.core.config import settings


async def test_cost_tracking():
    """Test that cost is calculated correctly for the large model."""
    print("=" * 80)
    print(f"COST TRACKING TEST WITH {settings.openai_embedding_model.upper()}")
    print("=" * 80)
    print()

    text = "This is a test message for cost tracking verification"
    print(f"Input: '{text}'")
    print()

    # Generate embedding (this will log the cost)
    embedding = await generate_embedding(text)

    print(f"\n[OK] Embedding generated successfully!")
    print(f"Dimension: {len(embedding)}")
    print()
    print("Check the logs above for cost tracking:")
    print("  - Should show model=text-embedding-3-large")
    print("  - Should show cost calculated at $0.13 per 1M tokens")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_cost_tracking())
