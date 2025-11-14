"""
Test PII detection, anonymization, and data retention features.

This script tests:
1. PII detection accuracy (email, phone, credit card)
2. Anonymization strategies (redact, replace, mask, hash)
3. Custom PII patterns
4. Batch processing
5. Data retention policies
6. GDPR right-to-be-forgotten
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.pii import AnonymizationStrategy, PIIEntityType, PIIPattern
from app.services.pii import (
    add_custom_pattern,
    anonymize_document_content,
    anonymize_text,
    batch_anonymize,
    detect_pii,
)
from app.services.retention import (
    DEFAULT_POLICIES,
    delete_documents_by_retention_policy,
    delete_user_data,
    get_documents_for_deletion,
    get_retention_statistics,
)


async def test_pii_detection():
    """Test 1: PII detection for common types."""
    print("\n" + "=" * 80)
    print("TEST 1: PII Detection Accuracy")
    print("=" * 80)

    test_cases = [
        (
            "Email me at john.doe@example.com for more info.",
            [PIIEntityType.EMAIL],
            "email detection",
        ),
        (
            "Call me at 212-555-5555 or +1 (555) 123-4567.",
            [PIIEntityType.PHONE],
            "phone detection",
        ),
        (
            "My credit card is 4532-1234-5678-9010.",
            [PIIEntityType.CREDIT_CARD],
            "credit card detection",
        ),
        (
            "Contact John Smith at john@example.com or 555-1234.",
            [PIIEntityType.PERSON, PIIEntityType.EMAIL, PIIEntityType.PHONE],
            "multiple PII types",
        ),
    ]

    results = []

    for text, expected_types, description in test_cases:
        print(f"\n[TEST] {description}")
        print(f"Text: {text}")

        detected = await detect_pii(text, min_score=0.6)

        print(f"✓ Detected {len(detected)} entities:")
        for entity in detected:
            print(
                f"  - {entity.entity_type.value}: '{entity.text}' "
                f"(score={entity.score:.4f}, pos={entity.start}-{entity.end})"
            )

        # Check if expected types were found
        detected_types = {e.entity_type for e in detected}
        expected_set = set(expected_types)

        if expected_set.issubset(detected_types):
            print(f"✅ PASS: All expected types found")
            results.append(True)
        else:
            missing = expected_set - detected_types
            print(f"❌ FAIL: Missing types: {missing}")
            results.append(False)

    passed = sum(results)
    total = len(results)
    print(f"\n[SUMMARY] PII Detection: {passed}/{total} tests passed")

    return passed == total


async def test_anonymization_strategies():
    """Test 2: Different anonymization strategies."""
    print("\n" + "=" * 80)
    print("TEST 2: Anonymization Strategies")
    print("=" * 80)

    original_text = "Contact John at john@example.com or call 212-555-5555."
    print(f"\nOriginal text: {original_text}")

    strategies = [
        (AnonymizationStrategy.REDACT, "Redact (remove completely)"),
        (AnonymizationStrategy.REPLACE, "Replace (with placeholder)"),
        (AnonymizationStrategy.MASK, "Mask (with asterisks)"),
        (AnonymizationStrategy.HASH, "Hash (SHA-256)"),
    ]

    results = []

    for strategy, description in strategies:
        print(f"\n[TEST] {description}")

        try:
            result = await anonymize_text(
                text=original_text, strategy=strategy, placeholder="[REDACTED]"
            )

            print(f"Anonymized: {result.anonymized_text}")
            print(
                f"✓ Entities found: {len(result.entities_found)}, "
                f"Applied: {result.anonymization_applied}"
            )
            print(f"✓ Processing time: {result.processing_time_ms:.2f}ms")

            # Verify that original PII is not in anonymized text
            if strategy in [
                AnonymizationStrategy.REDACT,
                AnonymizationStrategy.REPLACE,
                AnonymizationStrategy.MASK,
            ]:
                has_pii = (
                    "john@example.com" in result.anonymized_text.lower()
                    or "212-555-5555" in result.anonymized_text
                )
                if has_pii:
                    print(f"❌ FAIL: Original PII still present in anonymized text")
                    results.append(False)
                else:
                    print(f"✅ PASS: Original PII successfully removed")
                    results.append(True)
            else:
                # For HASH, just check that text was modified
                if result.anonymized_text != original_text:
                    print(f"✅ PASS: Text was modified")
                    results.append(True)
                else:
                    print(f"❌ FAIL: Text was not modified")
                    results.append(False)

        except Exception as e:
            print(f"❌ FAIL: {e}")
            results.append(False)

    passed = sum(results)
    total = len(results)
    print(f"\n[SUMMARY] Anonymization Strategies: {passed}/{total} tests passed")

    return passed == total


async def test_custom_patterns():
    """Test 3: Custom PII patterns."""
    print("\n" + "=" * 80)
    print("TEST 3: Custom PII Patterns")
    print("=" * 80)

    # Add custom pattern for company IDs
    pattern = PIIPattern(
        name="company_id",
        entity_type="COMPANY_ID",
        pattern_type="regex",
        pattern=r"COMP-\d{6}",
        score=0.9,
    )

    print(f"\n[TEST] Adding custom pattern: {pattern.name}")
    add_custom_pattern(pattern)
    print(f"✓ Custom pattern added")

    # Test detection with custom pattern
    text = "My company ID is COMP-123456 and email is support@company.com."
    print(f"\nText: {text}")

    detected = await detect_pii(text, min_score=0.6)

    print(f"✓ Detected {len(detected)} entities:")
    for entity in detected:
        print(f"  - {entity.entity_type.value}: '{entity.text}' (score={entity.score:.4f})")

    # Check if custom entity was detected
    has_company_id = any(
        "COMP-123456" in entity.text for entity in detected
    )

    if has_company_id:
        print(f"✅ PASS: Custom COMPANY_ID pattern detected")
        return True
    else:
        print(f"❌ FAIL: Custom COMPANY_ID pattern not detected")
        return False


async def test_batch_anonymization():
    """Test 4: Batch anonymization."""
    print("\n" + "=" * 80)
    print("TEST 4: Batch Anonymization")
    print("=" * 80)

    texts = [
        "Email: john@example.com",
        "Phone: 212-555-5555",
        "Credit Card: 4532-1234-5678-9010",
        "Contact Jane Smith at jane@company.com or 555-7890",
        "No PII in this text",
    ]

    print(f"\n[TEST] Anonymizing {len(texts)} texts in batch")

    try:
        results = await batch_anonymize(
            texts=texts, strategy=AnonymizationStrategy.REPLACE, placeholder="[REDACTED]"
        )

        print(f"✓ Batch complete: {len(results)} results")

        for i, result in enumerate(results):
            print(f"\n{i+1}. Original: {result.original_text}")
            print(f"   Anonymized: {result.anonymized_text}")
            print(
                f"   Entities: {len(result.entities_found)}, "
                f"Applied: {result.anonymization_applied}"
            )

        # Check that all texts were processed
        if len(results) == len(texts):
            print(f"\n✅ PASS: All texts processed")
            return True
        else:
            print(f"\n❌ FAIL: Not all texts processed")
            return False

    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_document_anonymization():
    """Test 5: Document content anonymization."""
    print("\n" + "=" * 80)
    print("TEST 5: Document Content Anonymization")
    print("=" * 80)

    document_id = "test_doc_123"
    title = "Contact Information for John Smith"
    content = """
    Dear Team,

    Please contact our support team at support@company.com or call 212-555-5555.
    For urgent matters, reach out to Jane Doe at jane.doe@example.com or 555-1234.

    Our office is located at 123 Main Street.

    Best regards,
    Customer Support
    """

    print(f"\n[TEST] Anonymizing document: {document_id}")
    print(f"Title: {title}")
    print(f"Content length: {len(content)} characters")

    try:
        result = await anonymize_document_content(
            document_id=document_id, content=content, title=title
        )

        print(f"\n✓ Document anonymized successfully")
        print(f"  - Title entities: {result['title_entities_found']}")
        print(f"  - Content entities: {result['content_entities_found']}")
        print(f"  - Total entities: {result['total_entities_found']}")
        print(f"  - Processing time: {result['processing_time_ms']:.2f}ms")

        print(f"\nAnonymized title: {result['anonymized_title']}")
        print(f"\nAnonymized content preview:")
        print(result["anonymized_content"][:200] + "...")

        if result["total_entities_found"] > 0:
            print(f"\n✅ PASS: PII detected and anonymized")
            return True
        else:
            print(f"\n❌ FAIL: No PII detected")
            return False

    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_retention_policies():
    """Test 6: Data retention policies."""
    print("\n" + "=" * 80)
    print("TEST 6: Data Retention Policies")
    print("=" * 80)

    print(f"\n[TEST] Listing default retention policies")

    for policy in DEFAULT_POLICIES:
        print(f"\n  Policy: {policy.name}")
        print(f"    Description: {policy.description}")
        print(f"    Retention days: {policy.retention_days}")
        print(f"    Applies to: {policy.applies_to_sources or 'all sources'}")
        print(f"    Auto-delete: {policy.auto_delete}")

    # Test getting documents for deletion (dry run)
    print(f"\n[TEST] Finding documents eligible for deletion (dry run)")

    try:
        policy = DEFAULT_POLICIES[0]  # chat_messages policy
        documents = await get_documents_for_deletion(policy, dry_run=True)

        print(f"✓ Found {len(documents)} documents eligible for deletion")
        print(f"  Policy: {policy.name}")
        print(f"  Retention: {policy.retention_days} days")

        print(f"\n✅ PASS: Retention policy check successful")
        return True

    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_gdpr_deletion():
    """Test 7: GDPR right-to-be-forgotten."""
    print("\n" + "=" * 80)
    print("TEST 7: GDPR Right to be Forgotten")
    print("=" * 80)

    user_identifier = "test_user@example.com"
    identifier_type = "author_id"

    print(f"\n[TEST] GDPR deletion request (dry run)")
    print(f"User: {user_identifier}")
    print(f"Type: {identifier_type}")

    try:
        result = await delete_user_data(
            user_identifier=user_identifier, identifier_type=identifier_type, dry_run=True
        )

        print(f"\n✓ GDPR deletion simulation complete")
        print(f"  Documents found: {result['documents_found']}")
        print(f"  Documents to delete: {result['documents_deleted']}")
        print(f"  Legal basis: {result['legal_basis']}")
        print(f"  Processing time: {result['processing_time_ms']:.2f}ms")

        print(f"\n✅ PASS: GDPR deletion workflow functional")
        return True

    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_retention_statistics():
    """Test 8: Retention statistics."""
    print("\n" + "=" * 80)
    print("TEST 8: Retention Statistics")
    print("=" * 80)

    print(f"\n[TEST] Getting retention statistics")

    try:
        stats = await get_retention_statistics()

        print(f"\n✓ Retention statistics retrieved")
        print(f"  Total documents: {stats['total_documents']}")
        print(f"  Eligible for deletion: {stats['eligible_for_deletion']}")
        print(f"  Retrieved at: {stats['retrieved_at']}")

        print(f"\n  Policy breakdown:")
        for policy_stat in stats["policies"]:
            print(f"    - {policy_stat['policy_name']}: {policy_stat['eligible_for_deletion']} documents")

        print(f"\n✅ PASS: Retention statistics working")
        return True

    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all PII and retention tests."""
    print("\n" + "=" * 80)
    print("PII & DATA RETENTION TEST SUITE")
    print("=" * 80)
    print("\nTesting PII detection, anonymization, and GDPR compliance features")

    results = []

    # Run tests sequentially
    results.append(("PII Detection", await test_pii_detection()))
    results.append(("Anonymization Strategies", await test_anonymization_strategies()))
    results.append(("Custom Patterns", await test_custom_patterns()))
    results.append(("Batch Anonymization", await test_batch_anonymization()))
    results.append(("Document Anonymization", await test_document_anonymization()))
    results.append(("Retention Policies", await test_retention_policies()))
    results.append(("GDPR Deletion", await test_gdpr_deletion()))
    results.append(("Retention Statistics", await test_retention_statistics()))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")

    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✅ SUCCESS: All tests passed!")
    else:
        print(f"\n❌ FAILURE: {total - passed} test(s) failed")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
