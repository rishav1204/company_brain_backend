CREATE TABLE learning_labeling_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    feedback_event_id UUID REFERENCES feedback_events(id),
    triage_category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_review',
    payload_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewer_id TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE learning_governance_cycles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    candidate_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'feedback_triage',
    baseline_eval_run_id UUID REFERENCES eval_runs(id),
    shadow_eval_run_id UUID REFERENCES eval_runs(id),
    promotion_decision TEXT NOT NULL DEFAULT 'pending',
    governance_approver TEXT,
    canary_percent INT NOT NULL DEFAULT 0,
    metrics_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_learning_labeling_tasks_org_status ON learning_labeling_tasks(org_id, status, created_at DESC);
CREATE INDEX idx_learning_governance_cycles_org_status ON learning_governance_cycles(org_id, status, updated_at DESC);

ALTER TABLE learning_labeling_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_labeling_tasks FORCE ROW LEVEL SECURITY;
ALTER TABLE learning_governance_cycles ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_governance_cycles FORCE ROW LEVEL SECURITY;

CREATE POLICY learning_labeling_tasks_org_isolation ON learning_labeling_tasks
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

CREATE POLICY learning_governance_cycles_org_isolation ON learning_governance_cycles
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());
