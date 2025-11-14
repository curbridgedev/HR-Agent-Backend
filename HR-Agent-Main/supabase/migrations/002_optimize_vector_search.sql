-- Optimization: Improve HNSW search recall
-- This migration adds recommended configuration for better vector search results

-- Increase HNSW search quality (default is 40, increasing to 100)
-- This improves recall at the cost of slightly slower queries
ALTER DATABASE postgres SET hnsw.ef_search = 100;

-- For the current session, apply immediately
SET hnsw.ef_search = 100;

-- Optional: Enable iterative scan for better filtered query performance
-- Uncomment if you frequently use WHERE clauses with vector search
-- ALTER DATABASE postgres SET hnsw.iterative_scan = 'relaxed_order';

-- Note: These settings can also be set per-query using SET LOCAL in a transaction
-- Example:
-- BEGIN;
-- SET LOCAL hnsw.ef_search = 200;  -- Even higher recall for important queries
-- SELECT * FROM documents ORDER BY embedding <=> query_vector LIMIT 5;
-- COMMIT;
