"""
Simple PII detection and anonymization test.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.pii import AnonymizationStrategy
from app.services.pii import anonymize_text, detect_pii


async def main():
    print("\n" + "=" * 60)
    print("SIMPLE PII TEST")
    print("=" * 60)

    # Test 1: Email detection
    print("\n[TEST 1] Email Detection")
    text1 = "Contact me at john@example.com"
    print(f"Text: {text1}")

    detected = await detect_pii(text1)
    print(f"✓ Detected {len(detected)} entities")
    for entity in detected:
        print(f"  - {entity.entity_type.value}: '{entity.text}' (score={entity.score:.4f})")

    # Test 2: Anonymization
    print("\n[TEST 2] Anonymization")
    text2 = "My email is john@example.com and phone is 212-555-5555"
    print(f"Text: {text2}")

    result = await anonymize_text(text2, strategy=AnonymizationStrategy.REPLACE)
    print(f"✓ Anonymized: {result.anonymized_text}")
    print(f"✓ Entities found: {len(result.entities_found)}")
    print(f"✓ Processing time: {result.processing_time_ms:.2f}ms")

    print("\n✅ Basic PII functionality working!\n")


if __name__ == "__main__":
    asyncio.run(main())
