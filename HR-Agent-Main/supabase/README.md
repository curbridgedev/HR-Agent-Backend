# Supabase Database Setup

This directory contains database migrations and setup instructions for the Compaytence AI Agent backend.

## Quick Setup

### 1. Run Migration in Supabase

**Option A: Via Supabase Dashboard (Recommended)**

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Click **New Query**
4. Copy the entire contents of `migrations/001_initial_schema.sql`
5. Paste into the SQL editor
6. Click **Run** or press `Ctrl+Enter`

**Option B: Via Supabase CLI**

```bash
# Install Supabase CLI if not already installed
npm install -g supabase

# Link to your project
supabase link --project-ref your-project-ref

# Run migration
supabase db push
```

### 2. Verify Setup

Run this query in the SQL Editor to verify:

```sql
-- Check if tables exist
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Check if pgvector extension is enabled
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Check if functions exist
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_name IN ('match_documents', 'hybrid_search');
```

You should see:
- Tables: `documents`, `chat_sessions`, `chat_messages`, `sources`
- Extension: `vector`
- Functions: `match_documents`, `hybrid_search`

### 3. Seed Sample Data (Optional but Recommended)

```bash
# From project root
uv run python scripts/seed_database.py
```

This will insert 5 sample documents about Compaytence to test the RAG system.

## Database Schema

### Tables

**documents**
- Stores processed documents with vector embeddings
- Supports vector similarity search with pgvector
- Full-text search with pg_trgm
- Metadata for source tracking

**chat_sessions**
- Tracks user chat sessions
- Links messages to sessions

**chat_messages**
- Stores chat history
- Tracks confidence scores and escalations

**sources**
- Manages connected chat platforms (Slack, WhatsApp, Telegram)
- Stores connection status and credentials

### Functions

**match_documents(query_embedding, match_threshold, match_count)**
- Pure vector similarity search
- Returns documents sorted by cosine similarity

**hybrid_search(query_embedding, query_text, match_threshold, match_count)**
- Combines vector similarity (70%) + text similarity (30%)
- Best results for complex queries

## Testing Vector Search

After seeding, test the functions:

```sql
-- Example: Search for documents (you'll need a real embedding vector)
SELECT * FROM match_documents(
    '[0.1, 0.2, ...]'::vector(1536),  -- Replace with real embedding
    0.75,  -- Threshold
    5      -- Limit
);
```

## Troubleshooting

### "Extension vector does not exist"

Enable pgvector in Supabase:
1. Go to **Database** → **Extensions**
2. Search for "vector"
3. Enable it

### "Function match_documents does not exist"

Re-run the migration SQL. Make sure you copied the entire file.

### "Permission denied for table documents"

Check Row Level Security (RLS) settings. For development, you can disable RLS:

```sql
ALTER TABLE documents DISABLE ROW LEVEL SECURITY;
```

**Note:** Re-enable RLS in production with proper policies!

## Migration History

- `001_initial_schema.sql` - Initial schema with pgvector, documents table, search functions

## Next Steps

After setup:
1. ✅ Run migration
2. ✅ Seed sample data
3. ✅ Test chat endpoint: `POST /api/v1/chat`
4. ✅ Verify vector search is working
5. Add your own documents via upload endpoint
