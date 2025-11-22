# Diagnosing Province Filter Issue

## Quick Diagnostic Steps

### Step 1: Check Document Province Tag
Run in Supabase SQL Editor:

```sql
-- Find documents mentioning "Director" or "Collection"
SELECT 
    d.id,
    d.filename,
    d.province,
    d.processing_status,
    COUNT(kb.id) as chunk_count
FROM documents d
LEFT JOIN knowledge_base kb ON kb.document_id = d.id
WHERE d.filename ILIKE '%collection%' 
   OR d.filename ILIKE '%debt%'
   OR d.filename ILIKE '%settlement%'
   OR EXISTS (
       SELECT 1 FROM knowledge_base kb2 
       WHERE kb2.document_id = d.id 
       AND kb2.content ILIKE '%Director%'
   )
GROUP BY d.id, d.filename, d.province, d.processing_status;
```

**What to look for:**
- If `province` is `NULL` → Document not tagged, won't match province filter
- If `province` is `'MB'` or other → Wrong province tag
- If `province` is `'ON'` → Should work, but threshold might be too high

### Step 2: Test Search WITHOUT Province Filter
```sql
-- Test if chunks exist at all (no province filter)
SELECT COUNT(*) 
FROM knowledge_base kb
WHERE kb.content ILIKE '%Director%'
  AND kb.content ILIKE '%Collection%';
```

If this returns > 0, chunks exist but province filter is excluding them.

### Step 3: Fix Document Province Tag
If document has wrong or NULL province:

```sql
-- Update document province to ON
UPDATE documents 
SET province = 'ON'
WHERE filename ILIKE '%collection%' 
   OR filename ILIKE '%debt%'
   OR filename ILIKE '%settlement%';
```

### Step 4: Lower Threshold (Temporary)
If document is correctly tagged but still not found, lower threshold in `.env`:

```bash
VECTOR_SIMILARITY_THRESHOLD=0.50  # Down from 0.65
```

Then restart backend.

## Most Likely Issue

**Your document probably has `province = NULL`**, which means:
- When you filter by `province = 'ON'`, it doesn't match
- The updated SQL function now includes NULL provinces for backward compatibility
- **But you should still tag your documents properly!**

## Solution

1. **Run the updated migration** (025_add_province_filter_to_search.sql) - includes NULL handling
2. **Tag your document** with province 'ON' using the UPDATE query above
3. **Restart backend**
4. **Test again**

