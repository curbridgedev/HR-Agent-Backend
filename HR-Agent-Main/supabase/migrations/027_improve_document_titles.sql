-- Improve document titles for better source display
-- This migration updates document titles to be more readable

-- Update documents with temporary filenames to use better names
UPDATE documents
SET title = COALESCE(
    -- Use original_filename if it's better than current title
    CASE 
        WHEN original_filename IS NOT NULL 
             AND original_filename NOT LIKE 'tmp%' 
             AND original_filename NOT LIKE 'temp%'
        THEN original_filename
        ELSE NULL
    END,
    -- Use filename if it's better
    CASE 
        WHEN filename IS NOT NULL 
             AND filename NOT LIKE 'tmp%' 
             AND filename NOT LIKE 'temp%'
        THEN filename
        ELSE NULL
    END,
    -- Keep existing title if it's good
    CASE 
        WHEN title IS NOT NULL 
             AND title != '' 
             AND title NOT LIKE 'tmp%'
        THEN title
        ELSE NULL
    END,
    -- Final fallback
    'Uploaded Document'
)
WHERE title IS NULL 
   OR title = ''
   OR title LIKE 'tmp%'
   OR title LIKE 'temp%';

-- Clean up titles: remove file extensions, replace underscores
UPDATE documents
SET title = REGEXP_REPLACE(
    REGEXP_REPLACE(title, '\.(pdf|docx|doc|txt|md)$', '', 'i'),  -- Remove extensions
    '_', ' ', 'g'  -- Replace underscores with spaces
)
WHERE title IS NOT NULL;

-- Capitalize first letter of each word for better readability
UPDATE documents
SET title = INITCAP(title)
WHERE title IS NOT NULL;

-- Add comment
COMMENT ON COLUMN documents.title IS 'Human-readable document title (cleaned filename without extension)';

