CREATE TABLE qa_gold_examples (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    org_scope TEXT NOT NULL DEFAULT 'tenant',
    question TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    expected_citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE retrieval_judgments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    query TEXT NOT NULL,
    candidate_ref TEXT NOT NULL,
    relevance_label INT NOT NULL CHECK (relevance_label BETWEEN 0 AND 3),
    judged_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE safety_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    request_id TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE feedback_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    event_type TEXT NOT NULL,
    payload_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE eval_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    metrics_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_qa_gold_org ON qa_gold_examples(org_id, created_at);
CREATE INDEX idx_retrieval_judgments_org ON retrieval_judgments(org_id, created_at);
CREATE INDEX idx_safety_events_org ON safety_events(org_id, created_at);
CREATE INDEX idx_feedback_events_org ON feedback_events(org_id, created_at);
CREATE INDEX idx_eval_runs_org ON eval_runs(org_id, started_at);

ALTER TABLE qa_gold_examples ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrieval_judgments ENABLE ROW LEVEL SECURITY;
ALTER TABLE safety_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE eval_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY qa_gold_examples_org_isolation ON qa_gold_examples
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY retrieval_judgments_org_isolation ON retrieval_judgments
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY safety_events_org_isolation ON safety_events
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY feedback_events_org_isolation ON feedback_events
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY eval_runs_org_isolation ON eval_runs
    USING (org_id = current_setting('app.current_org', true)::UUID);
