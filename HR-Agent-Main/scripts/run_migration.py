"""
Run a specific migration file against Supabase database.

Usage:
    python scripts/run_migration.py supabase/migrations/019_create_knowledge_base_table.sql
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.supabase import get_supabase_client
from app.core.config import settings


def run_migration(migration_file: str):
    """Run a SQL migration file."""
    migration_path = Path(migration_file)
    
    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return False
    
    print(f"📄 Reading migration: {migration_path.name}")
    sql_content = migration_path.read_text()
    
    print(f"🔗 Connecting to Supabase: {settings.supabase_url}")
    supabase = get_supabase_client()
    
    print("🚀 Executing migration...")
    try:
        # Execute the SQL using Supabase's rpc function
        # Note: This uses PostgREST which may have limitations with DDL
        # For complex migrations, use Supabase dashboard SQL editor
        
        # Split into individual statements
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        print(f"   Found {len(statements)} SQL statements")
        
        for i, statement in enumerate(statements, 1):
            if not statement:
                continue
            
            print(f"   [{i}/{len(statements)}] Executing...")
            
            # Use the supabase client to execute raw SQL
            # This requires the PostgREST `rpc` endpoint
            result = supabase.rpc('exec_sql', {'sql': statement}).execute()
            
            if result.data:
                print(f"   ✅ Statement {i} executed successfully")
            else:
                print(f"   ⚠️  Statement {i} returned no data")
        
        print("✅ Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print("\n💡 Try running the migration via Supabase Dashboard SQL Editor instead:")
        print(f"   1. Go to: https://supabase.com/dashboard/project/[your-project-id]/sql")
        print(f"   2. Paste contents of: {migration_path}")
        print(f"   3. Click 'Run'")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_migration.py <migration_file>")
        print("\nExample:")
        print("  python scripts/run_migration.py supabase/migrations/019_create_knowledge_base_table.sql")
        sys.exit(1)
    
    migration_file = sys.argv[1]
    success = run_migration(migration_file)
    
    sys.exit(0 if success else 1)
