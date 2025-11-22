"""
Quick test to verify embedding format matches what Supabase expects
Run this with: uv run python test_embedding_format.py
"""
import asyncio
from app.services.embedding import generate_embedding
from app.db.supabase import get_supabase_client

async def test_embedding_format():
    # Generate a test embedding
    test_query = "What is vacation pay?"
    embedding = await generate_embedding(test_query)
    
    print(f"✅ Generated embedding:")
    print(f"   Type: {type(embedding)}")
    print(f"   Length: {len(embedding)}")
    print(f"   First 3 values: {embedding[:3]}")
    print(f"   All floats?: {all(isinstance(x, (float, int)) for x in embedding)}")
    
    # Try to call the hybrid_search function
    db = get_supabase_client()
    
    print(f"\n🔍 Testing hybrid_search RPC call...")
    try:
        response = db.rpc(
            "hybrid_search",
            {
                "query_embedding": embedding,
                "query_text": "vacation pay",
                "match_threshold": 0.01,  # Very low
                "match_count": 5,
            },
        ).execute()
        
        print(f"✅ RPC call succeeded!")
        print(f"   Results: {len(response.data) if response.data else 0}")
        
        if response.data and len(response.data) > 0:
            print(f"   First result title: {response.data[0].get('title', 'N/A')}")
            print(f"   First result similarity: {response.data[0].get('similarity', 'N/A')}")
        else:
            print(f"   ⚠️ No results returned!")
            
    except Exception as e:
        print(f"❌ RPC call failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_embedding_format())

