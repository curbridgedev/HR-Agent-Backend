"""
Check database contents and test RPC functions directly.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.supabase import get_supabase_client
from app.services.embedding import generate_embedding
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def check_database():
    """Check database state and test RPC functions."""

    db = get_supabase_client()

    print("\n1. Checking if documents exist in database...")
    print("=" * 80)

    try:
        # Check documents table
        result = db.table("documents").select("id, title, source").execute()

        if result.data:
            print(f"Found {len(result.data)} documents:\n")
            for doc in result.data:
                print(f"  - {doc['title']} (source: {doc['source']})")
        else:
            print("No documents found in database!")
            print("Run: uv run python scripts/seed_database.py")
            return

    except Exception as e:
        print(f"Error querying documents: {e}")
        return

    print("\n2. Testing RPC function directly...")
    print("=" * 80)

    try:
        # Generate a test embedding
        query = "What is Compaytence?"
        print(f"Query: {query}")
        query_embedding = await generate_embedding(query)
        print(f"Embedding generated: {len(query_embedding)} dimensions\n")

        # Test match_documents function
        print("Testing match_documents RPC function:")
        rpc_result = db.rpc(
            "match_documents",
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.0,
                "match_count": 10,
            },
        ).execute()

        print(f"RPC Response data: {rpc_result.data}")
        print(f"RPC Response count: {len(rpc_result.data) if rpc_result.data else 0}")

        if rpc_result.data:
            print(f"\nFound {len(rpc_result.data)} results:")
            for doc in rpc_result.data:
                print(f"\n  Title: {doc['title']}")
                print(f"  Similarity: {doc.get('similarity', 'N/A')}")
        else:
            print("\nNo results from RPC function!")
            print("Possible issues:")
            print("  1. RPC function not created properly")
            print("  2. Vector dimensions mismatch")
            print("  3. Embeddings not stored correctly")

    except Exception as e:
        print(f"Error calling RPC function: {e}")
        print(f"Error type: {type(e)}")

        # Check if function exists
        print("\n3. Checking if RPC functions exist...")
        try:
            funcs = db.rpc(
                "pg_get_functiondef",
                {"funcid": "match_documents::regproc"},
            ).execute()
            print(f"Function check result: {funcs}")
        except Exception as fe:
            print(f"Could not check function: {fe}")


if __name__ == "__main__":
    print("Database Debug Tool")
    print("=" * 80)
    asyncio.run(check_database())
