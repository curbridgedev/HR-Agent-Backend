# Testing PII Detection and Anonymization

This guide explains how to test the PII detection, anonymization, and data retention features.

## Prerequisites

Ensure dependencies are installed:
```bash
uv sync
```

The following packages should be installed:
- `presidio-analyzer>=2.2.0`
- `presidio-anonymizer>=2.2.0`
- `spacy>=3.7.0`
- `en-core-web-sm==3.8.0` (spaCy model)

## Method 1: Interactive Python REPL Testing

### Step 1: Start Python REPL

```bash
cd A:\Techify\Compaytence-Agent
.venv\Scripts\python.exe
```

### Step 2: Test PII Detection

```python
import asyncio
import sys
sys.path.insert(0, '.')

from app.services.pii import detect_pii

# Test email detection
async def test():
    text = "Contact me at john@example.com"
    results = await detect_pii(text)

    print(f"Found {len(results)} PII entities:")
    for entity in results:
        print(f"  - {entity.entity_type.value}: '{entity.text}' (score={entity.score:.4f})")

    return results

# Run test
results = asyncio.run(test())
```

**Expected Output:**
```
Found 1 PII entities:
  - EMAIL_ADDRESS: 'john@example.com' (score=1.0000)
```

### Step 3: Test Anonymization

```python
from app.services.pii import anonymize_text
from app.models.pii import AnonymizationStrategy

async def test_anon():
    text = "My email is john@example.com and phone is 212-555-5555"

    result = await anonymize_text(
        text=text,
        strategy=AnonymizationStrategy.REPLACE,
        placeholder="[REDACTED]"
    )

    print(f"Original: {result.original_text}")
    print(f"Anonymized: {result.anonymized_text}")
    print(f"Entities found: {len(result.entities_found)}")
    print(f"Processing time: {result.processing_time_ms:.2f}ms")

    return result

result = asyncio.run(test_anon())
```

**Expected Output:**
```
Original: My email is john@example.com and phone is 212-555-5555
Anonymized: My email is [REDACTED] and phone is [REDACTED]
Entities found: 2
Processing time: 45.23ms
```

### Step 4: Test Different Anonymization Strategies

```python
from app.models.pii import AnonymizationStrategy

async def test_strategies():
    text = "Call me at 212-555-5555"

    strategies = [
        AnonymizationStrategy.REDACT,
        AnonymizationStrategy.REPLACE,
        AnonymizationStrategy.MASK,
        AnonymizationStrategy.HASH,
    ]

    for strategy in strategies:
        result = await anonymize_text(text, strategy=strategy)
        print(f"{strategy.value}: {result.anonymized_text}")

asyncio.run(test_strategies())
```

**Expected Output:**
```
redact: Call me at
replace: Call me at [REDACTED]
mask: Call me at ************
hash: Call me at 8d5e9571...
```

## Method 2: Run Test Scripts

### Simple Test (Quick Validation)

```bash
uv run python scripts/test_pii_simple.py
```

**Expected Output:**
```
============================================================
SIMPLE PII TEST
============================================================

[TEST 1] Email Detection
Text: Contact me at john@example.com
✓ Detected 1 entities
  - EMAIL_ADDRESS: 'john@example.com' (score=1.0000)

[TEST 2] Anonymization
Text: My email is john@example.com and phone is 212-555-5555
✓ Anonymized: My email is [REDACTED] and phone is [REDACTED]
✓ Entities found: 2
✓ Processing time: 45.23ms

✅ Basic PII functionality working!
```

### Comprehensive Test Suite

```bash
uv run python scripts/test_pii.py
```

This runs 8 comprehensive tests:
1. PII Detection Accuracy (email, phone, credit card, multiple types)
2. Anonymization Strategies (redact, replace, mask, hash)
3. Custom PII Patterns (company IDs, etc.)
4. Batch Anonymization
5. Document Content Anonymization
6. Data Retention Policies
7. GDPR Right to be Forgotten
8. Retention Statistics

## Method 3: Unit Tests with Pytest

Create a test file `tests/test_pii_unit.py`:

```python
import pytest
from app.services.pii import detect_pii, anonymize_text
from app.models.pii import AnonymizationStrategy, PIIEntityType


@pytest.mark.asyncio
async def test_email_detection():
    """Test that emails are detected correctly."""
    text = "Contact john@example.com"
    results = await detect_pii(text)

    assert len(results) == 1
    assert results[0].entity_type == PIIEntityType.EMAIL
    assert results[0].text == "john@example.com"
    assert results[0].score > 0.9


@pytest.mark.asyncio
async def test_phone_detection():
    """Test that phone numbers are detected."""
    text = "Call 212-555-5555"
    results = await detect_pii(text)

    assert len(results) == 1
    assert results[0].entity_type == PIIEntityType.PHONE


@pytest.mark.asyncio
async def test_anonymization_replace():
    """Test REPLACE anonymization strategy."""
    text = "Email: john@example.com"
    result = await anonymize_text(
        text=text,
        strategy=AnonymizationStrategy.REPLACE,
        placeholder="[REDACTED]"
    )

    assert "[REDACTED]" in result.anonymized_text
    assert "john@example.com" not in result.anonymized_text
    assert result.anonymization_applied is True
    assert len(result.entities_found) == 1


@pytest.mark.asyncio
async def test_no_pii_detected():
    """Test text with no PII."""
    text = "This is a simple sentence with no personal information."
    result = await anonymize_text(text)

    assert result.anonymized_text == text
    assert result.anonymization_applied is False
    assert len(result.entities_found) == 0
```

Run tests:
```bash
uv run pytest tests/test_pii_unit.py -v
```

## Method 4: Manual Testing via API (Future)

Once API endpoints are created, test via HTTP:

### Detect PII Endpoint

```bash
POST /api/v1/pii/detect
Content-Type: application/json

{
  "text": "Contact me at john@example.com or call 212-555-5555",
  "min_score": 0.6
}
```

**Response:**
```json
{
  "entities": [
    {
      "entity_type": "EMAIL_ADDRESS",
      "text": "john@example.com",
      "start": 14,
      "end": 31,
      "score": 1.0
    },
    {
      "entity_type": "PHONE_NUMBER",
      "text": "212-555-5555",
      "start": 40,
      "end": 52,
      "score": 0.95
    }
  ]
}
```

### Anonymize Text Endpoint

```bash
POST /api/v1/pii/anonymize
Content-Type: application/json

{
  "text": "Email me at john@example.com",
  "strategy": "replace",
  "placeholder": "[REDACTED]"
}
```

**Response:**
```json
{
  "original_text": "Email me at john@example.com",
  "anonymized_text": "Email me at [REDACTED]",
  "entities_found": [
    {
      "entity_type": "EMAIL_ADDRESS",
      "text": "john@example.com",
      "start": 12,
      "end": 29,
      "score": 1.0
    }
  ],
  "anonymization_applied": true,
  "processing_time_ms": 45.23
}
```

## Testing Data Retention

### Test Retention Policy Query

```python
import asyncio
from app.services.retention import get_documents_for_deletion, DEFAULT_POLICIES

async def test_retention():
    # Get chat messages policy (365 days)
    policy = DEFAULT_POLICIES[0]

    # Find documents eligible for deletion (dry run)
    documents = await get_documents_for_deletion(policy, dry_run=True)

    print(f"Policy: {policy.name}")
    print(f"Retention: {policy.retention_days} days")
    print(f"Eligible for deletion: {len(documents)} documents")

asyncio.run(test_retention())
```

### Test GDPR Deletion (Dry Run)

```python
from app.services.retention import delete_user_data

async def test_gdpr():
    result = await delete_user_data(
        user_identifier="test_user@example.com",
        identifier_type="author_id",
        dry_run=True
    )

    print(f"Documents found: {result['documents_found']}")
    print(f"Would delete: {result['documents_deleted']}")
    print(f"Legal basis: {result['legal_basis']}")

asyncio.run(test_gdpr())
```

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'presidio_analyzer'`

**Solution:** Install dependencies
```bash
uv sync
```

### Issue: `OSError: [E050] Can't find model 'en_core_web_sm'`

**Solution:** Download spaCy model
```bash
uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
```

### Issue: File lock errors on Windows

**Solution:** Close any running Python processes or IDE that might be holding file handles, then retry.

### Issue: Slow first run

**Solution:** First run loads spaCy model which can take 5-10 seconds. Subsequent runs are much faster due to caching.

## Expected Performance

- **Email detection:** ~20-50ms
- **Phone detection:** ~20-50ms
- **Batch (10 texts):** ~200-500ms
- **Document anonymization:** ~50-150ms depending on length

## Verification Checklist

- [ ] Dependencies installed (`presidio-analyzer`, `presidio-anonymizer`, `spacy`)
- [ ] spaCy model downloaded (`en_core_web_sm`)
- [ ] Email detection working
- [ ] Phone detection working
- [ ] Credit card detection working
- [ ] Anonymization strategies working (REDACT, REPLACE, MASK, HASH)
- [ ] Custom patterns can be added
- [ ] Batch processing working
- [ ] Retention policies defined
- [ ] GDPR deletion workflow functional

## Next Steps

After verifying PII functionality:
1. Create API endpoints for PII detection/anonymization
2. Integrate PII anonymization into document ingestion pipeline
3. Set up scheduled retention policy execution
4. Configure monitoring for PII detection accuracy
5. Set up GDPR deletion request workflow in admin dashboard
