"""
Test script for message normalization service.

Tests normalization across all 4 sources: Slack, WhatsApp, Telegram, Admin Upload.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.supabase import get_supabase_client
from app.services.normalization import get_normalizer


async def test_normalization():
    """Test normalization service with real data from all sources."""
    print("=" * 80)
    print("TESTING MESSAGE NORMALIZATION SERVICE")
    print("=" * 80)
    print()

    supabase = get_supabase_client()
    normalizer = get_normalizer()

    # Get sample documents from each source
    sources = ["slack", "whatsapp", "whatsapp_export", "telegram", "admin_upload"]

    for source in sources:
        print(f"\n{'=' * 80}")
        print(f"Testing Source: {source.upper()}")
        print("=" * 80)

        try:
            # Get one document from this source
            response = (
                supabase.table("documents")
                .select("*")
                .eq("source", source)
                .limit(1)
                .execute()
            )

            if not response.data:
                print(f"[!]  No documents found for source: {source}")
                continue

            document = response.data[0]

            print(f"\n[*] Original Document:")
            print(f"  ID: {document['id']}")
            print(f"  Source: {document['source']}")
            print(f"  Source ID: {document.get('source_id', 'N/A')}")
            print(f"  Content (first 100 chars): {document['content'][:100]}...")
            print(f"  Source Metadata: {document.get('source_metadata', {})}")

            # Test normalization
            print(f"\n[>] Normalizing...")
            result = normalizer.normalize_document(document, skip_deduplication=False)

            if not result.success:
                print(f"  [X] Normalization FAILED: {result.error}")
                if result.warnings:
                    for warning in result.warnings:
                        print(f"  [!] Warning: {warning}")
                continue

            normalized = result.normalized_message
            dedup = result.deduplication_result

            print(f"  [OK] Normalization SUCCESSFUL!")
            print(f"\n[*] Normalized Message:")
            print(f"  ID: {normalized.id}")
            print(f"  Source: {normalized.source}")
            print(f"  Source Message ID: {normalized.source_message_id}")
            print(f"  Content Hash: {normalized.content_hash}")
            print(f"  Timestamp (UTC): {normalized.timestamp}")
            print(f"  Ingested At: {normalized.ingested_at}")
            print(f"\n[USER] Author:")
            print(f"  ID: {normalized.author.id}")
            print(f"  Name: {normalized.author.name or 'N/A'}")
            print(f"\n[CHAT] Conversation:")
            print(f"  ID: {normalized.conversation.id}")
            print(f"  Name: {normalized.conversation.name or 'N/A'}")
            print(f"  Type: {normalized.conversation.type or 'N/A'}")

            if normalized.thread:
                print(f"\n[THREAD] Thread:")
                print(f"  Is Reply: {normalized.thread.is_thread_reply}")
                print(f"  Parent ID: {normalized.thread.parent_message_id or 'N/A'}")

            print(f"\n[DEDUP] Deduplication:")
            if dedup:
                print(f"  Is Duplicate: {dedup.is_duplicate}")
                if dedup.is_duplicate:
                    print(f"  Duplicate Of: {dedup.duplicate_of_id}")
                    print(f"  Match Type: {dedup.match_type}")
                    print(f"  Confidence: {dedup.confidence}")
            else:
                print(f"  Skipped (bulk mode)")

            # Test storage update
            print(f"\n[SAVE] Testing storage update...")
            store_result = await normalizer.normalize_and_store(document)
            if store_result.success:
                print(f"  [OK] Storage update SUCCESSFUL")
            else:
                print(f"  [X] Storage update FAILED: {store_result.error}")

        except Exception as e:
            print(f"[X] Error testing {source}: {e}")
            import traceback

            traceback.print_exc()

    print(f"\n{'=' * 80}")
    print("TESTING COMPLETE")
    print("=" * 80)


async def test_deduplication():
    """Test deduplication logic with known duplicates."""
    print("\n" + "=" * 80)
    print("TESTING DEDUPLICATION LOGIC")
    print("=" * 80)

    supabase = get_supabase_client()
    normalizer = get_normalizer()

    # Get documents with same content to test deduplication
    print("\n[SEARCH] Looking for potential duplicates (same content)...")

    response = supabase.table("documents").select("*").limit(50).execute()

    if not response.data:
        print("  [!]  No documents found")
        return

    documents = response.data

    # Group by content hash
    content_groups: dict[str, list] = {}
    for doc in documents:
        content_hash = normalizer._generate_content_hash(doc.get("content", ""))
        if content_hash not in content_groups:
            content_groups[content_hash] = []
        content_groups[content_hash].append(doc)

    # Find duplicates
    duplicates_found = False
    for content_hash, docs in content_groups.items():
        if len(docs) > 1:
            duplicates_found = True
            print(f"\n[BOX] Found {len(docs)} documents with same content hash:")
            print(f"  Content Hash: {content_hash}")
            for i, doc in enumerate(docs, 1):
                print(f"\n  Document {i}:")
                print(f"    ID: {doc['id']}")
                print(f"    Source: {doc['source']}")
                print(f"    Source ID: {doc.get('source_id', 'N/A')}")
                print(f"    Content (first 50 chars): {doc['content'][:50]}...")
                print(f"    Created: {doc.get('created_at', 'N/A')}")

            # Test deduplication logic
            print(f"\n  [>] Testing deduplication logic...")
            result = normalizer.normalize_document(docs[0], skip_deduplication=False)
            if result.deduplication_result:
                dedup = result.deduplication_result
                print(f"    Is Duplicate: {dedup.is_duplicate}")
                if dedup.duplicate_of_id:
                    print(f"    Duplicate Of: {dedup.duplicate_of_id}")
                    print(f"    Match Type: {dedup.match_type}")

    if not duplicates_found:
        print("  [i]  No duplicates found (all documents have unique content)")

    print(f"\n{'=' * 80}")


async def test_edit_detection():
    """Test edit detection logic."""
    print("\n" + "=" * 80)
    print("TESTING EDIT DETECTION")
    print("=" * 80)

    supabase = get_supabase_client()
    normalizer = get_normalizer()

    print("\n[SEARCH] Looking for documents with same source_id (potential edits)...")

    # Get all documents
    response = supabase.table("documents").select("*").limit(100).execute()

    if not response.data:
        print("  [!]  No documents found")
        return

    documents = response.data

    # Group by source_id
    source_id_groups: dict[str, list] = {}
    for doc in documents:
        source_id = doc.get("source_id")
        if source_id:
            if source_id not in source_id_groups:
                source_id_groups[source_id] = []
            source_id_groups[source_id].append(doc)

    # Find potential edits
    edits_found = False
    for source_id, docs in source_id_groups.items():
        if len(docs) > 1:
            # Check if content is different (indicating edit)
            hashes = set()
            for doc in docs:
                content_hash = normalizer._generate_content_hash(doc.get("content", ""))
                hashes.add(content_hash)

            if len(hashes) > 1:
                edits_found = True
                print(f"\n[EDIT] Found potential edit:")
                print(f"  Source ID: {source_id}")
                print(f"  {len(docs)} versions, {len(hashes)} unique content hashes")

                # Sort by created_at
                sorted_docs = sorted(
                    docs, key=lambda x: x.get("created_at", ""), reverse=False
                )

                for i, doc in enumerate(sorted_docs, 1):
                    content_hash = normalizer._generate_content_hash(doc.get("content", ""))
                    print(f"\n  Version {i}:")
                    print(f"    ID: {doc['id']}")
                    print(f"    Content Hash: {content_hash}")
                    print(f"    Content (first 50 chars): {doc['content'][:50]}...")
                    print(f"    Created: {doc.get('created_at', 'N/A')}")

                print(f"\n  [OK] Strategy: Keep latest version only")

    if not edits_found:
        print("  [i]  No edited messages found")

    print(f"\n{'=' * 80}")


async def main():
    """Run all tests."""
    await test_normalization()
    await test_deduplication()
    await test_edit_detection()

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
