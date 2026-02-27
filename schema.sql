-- NovaOS v0.1 Database Schema

CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notion_page_id TEXT NOT NULL UNIQUE,
    notion_url TEXT,
    state TEXT NOT NULL CHECK (state IN ('PENDING', 'CLAIMED', 'WORKING', 'VALIDATING', 'MERGING', 'DONE', 'FAILED', 'BLOCKED')),
    title TEXT,
    description TEXT,
    repo TEXT NOT NULL,
    branch TEXT,
    risk_level TEXT CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    claimed_by TEXT,
    claimed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE run_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
    issue_number INTEGER,
    issue_url TEXT,
    title TEXT NOT NULL,
    description TEXT,
    worker_type TEXT CHECK (worker_type IN ('goose', 'image', 'copy', 'code')),
    status TEXT DEFAULT 'open',
    pr_url TEXT,
    pr_branch TEXT,
    worktree_path TEXT,
    result_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE run_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
    from_state TEXT,
    to_state TEXT NOT NULL,
    triggered_by TEXT,
    reason TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE validations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
    issue_id UUID REFERENCES run_issues(id) ON DELETE CASCADE,
    linter_passed BOOLEAN,
    typecheck_passed BOOLEAN,
    tests_passed BOOLEAN,
    tests_existed BOOLEAN,
    overall_result TEXT,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    conditions JSONB NOT NULL,
    auto_merge_allowed BOOLEAN DEFAULT false,
    require_approval_from TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
    channel TEXT,
    message_type TEXT,
    message TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    delivered BOOLEAN DEFAULT false
);

CREATE INDEX idx_runs_state ON runs(state);
CREATE INDEX idx_runs_notion_page_id ON runs(notion_page_id);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_runs_updated_at BEFORE UPDATE ON runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
