-- Check if the hybrid_search function exists and what its signature is
SELECT 
    routine_name,
    routine_type,
    data_type,
    array_agg(parameter_name || ' ' || data_type ORDER BY ordinal_position) as parameters
FROM information_schema.routines r
LEFT JOIN information_schema.parameters p 
    ON r.specific_name = p.specific_name
WHERE routine_name IN ('hybrid_search', 'match_documents')
GROUP BY routine_name, routine_type, data_type;

-- Test if hybrid_search works at all with existing data
-- This will tell us if the function is correctly querying knowledge_base
SELECT COUNT(*) as total_results
FROM hybrid_search(
    query_embedding := (SELECT embedding FROM knowledge_base LIMIT 1),
    query_text := 'employee',
    match_threshold := 0.01,  -- Super low threshold
    match_count := 10
);

