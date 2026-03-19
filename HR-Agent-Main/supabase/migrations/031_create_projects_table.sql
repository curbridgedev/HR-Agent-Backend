-- Curbridge HR-Agent - Projects table for project-based chats (Gemini-style)
-- Projects are user-owned containers with their own documents and multiple chats

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for listing user's projects by most recently updated
CREATE INDEX IF NOT EXISTS idx_projects_user_id_updated ON projects(user_id, updated_at DESC);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_projects_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_projects_updated_at();

-- Row Level Security: users can only access their own projects
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own projects"
    ON projects FOR SELECT
    USING (user_id = auth.uid()::text);

CREATE POLICY "Users can insert own projects"
    ON projects FOR INSERT
    WITH CHECK (user_id = auth.uid()::text);

CREATE POLICY "Users can update own projects"
    ON projects FOR UPDATE
    USING (user_id = auth.uid()::text);

CREATE POLICY "Users can delete own projects"
    ON projects FOR DELETE
    USING (user_id = auth.uid()::text);
