-- Check what parameters the hybrid_search function actually expects
SELECT 
    p.parameter_name,
    p.data_type,
    p.parameter_mode,
    p.ordinal_position
FROM information_schema.parameters p
JOIN information_schema.routines r ON r.specific_name = p.specific_name
WHERE r.routine_name = 'hybrid_search'
ORDER BY p.ordinal_position;

-- Also check if there are multiple versions (function overloading)
SELECT 
    routine_name,
    routine_definition,
    specific_name
FROM information_schema.routines
WHERE routine_name = 'hybrid_search';

