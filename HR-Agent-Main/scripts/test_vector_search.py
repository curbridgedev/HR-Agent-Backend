"""
Debug script to test vector search and similarity scores.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.supabase import get_supabase_client
from app.services.embedding import generate_embedding
from app.db.vector import hybrid_search, vector_search
from app.core.config import settings
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def test_search():
    """Test vector search with different queries and thresholds."""

    test_queries = [
        "What is Compaytence?",
        "How does Compaytence work?",
        "What are the features of Compaytence?",
    ]

    db = get_supabase_client()

    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}\n")

        # Generate embedding
        query_embedding = await generate_embedding(query)
        print(f"Generated embedding: {len(query_embedding)} dimensions\n")

        # Test with low threshold to see all results
        print("Testing with threshold=0.0 (show all results):")
        results = await hybrid_search(
            db=db,
            query_embedding=query_embedding,
            query_text=query,
            match_threshold=0.0,  # Show everything
            match_count=10,
        )

        if results:
            print(f"Found {len(results)} results:\n")
            for i, doc in enumerate(results, 1):
                print(f"{i}. Title: {doc['title']}")
                print(f"   Similarity: {doc['similarity']:.4f}")
                print(f"   Source: {doc['source']}")
                print(f"   Content preview: {doc['content'][:100]}...")
                print()
        else:
            print("No results found!\n")

        # Test with default threshold
        print(f"Testing with threshold={settings.vector_similarity_threshold}:")
        results_filtered = await hybrid_search(
            db=db,
            query_embedding=query_embedding,
            query_text=query,
            match_threshold=settings.vector_similarity_threshold,
            match_count=5,
        )

        if results_filtered:
            print(f"Found {len(results_filtered)} results above threshold\n")
        else:
            print(f"No results above threshold {settings.vector_similarity_threshold}\n")
            print("Try lowering VECTOR_SIMILARITY_THRESHOLD in .env")


if __name__ == "__main__":
    print("Vector Search Debug Tool")
    print(f"Config: model={settings.openai_embedding_model}, dimensions={settings.openai_embedding_dimensions}")
    print(f"Threshold: {settings.vector_similarity_threshold}\n")

    asyncio.run(test_search())
