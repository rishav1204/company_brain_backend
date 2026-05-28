-- Module 4: Audit, Compliance & Governance Core

CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS governance;
CREATE SCHEMA IF NOT EXISTS compliance;

-- Extend legacy append-only audit_logs (public) with enterprise columns
ALTER TABLE audit_logs
    ADD COLUMN IF NOT EXISTS entity_type VARCHAR(64),
    ADD COLUMN IF NOT EXISTS entity_id UUID,
    ADD COLUMN IF NOT EXISTS action VARCHAR(128),
    ADD COLUMN IF NOT EXISTS before_state JSONB,
    ADD COLUMN IF NOT EXISTS after_state JSONB,
    ADD COLUMN IF NOT EXISTS request_id UUID,
    ADD COLUMN IF NOT EXISTS trace_id UUID,
    ADD COLUMN IF NOT EXISTS ip_address INET,
    ADD COLUMN IF NOT EXISTS user_agent TEXT,
    ADD COLUMN IF NOT EXISTS source_service VARCHAR(128);

CREATE INDEX IF NOT EXISTS idx_audit_entity_timeline
    ON audit_logs (org_id, entity_type, entity_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_trace
    ON audit_logs (org_id, trace_id, created_at DESC)
    WHERE trace_id IS NOT NULL;

-- Canonical view for audit schema namespace
CREATE OR REPLACE VIEW audit.audit_logs AS
SELECT
    id,
    org_id,
    actor_id,
    actor_type,
    COALESCE(action, event_type) AS action,
    entity_type,
    entity_id,
    event_type,
    object_ref,
    before_state,
    after_state,
    payload_jsonb,
    request_id,
    trace_id,
    ip_address,
    user_agent,
    source_service,
    created_at AS timestamp
FROM public.audit_logs;

-- AI explainability (summaries + hashes only — no raw chain-of-thought)
CREATE TABLE IF NOT EXISTS audit.ai_reasoning_traces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    agent_run_id UUID,
    workflow_id UUID,
    step_id UUID,
    prompt_hash TEXT NOT NULL,
    retrieved_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    reasoning_summary TEXT NOT NULL,
    confidence_score NUMERIC(5, 4),
    decision JSONB NOT NULL DEFAULT '{}'::jsonb,
    policy_checks JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS audit_ai_traces_org_idx
    ON audit.ai_reasoning_traces (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS audit_ai_traces_workflow_idx
    ON audit.ai_reasoning_traces (org_id, workflow_id, created_at DESC)
    WHERE workflow_id IS NOT NULL;

-- Evidence chain linking
CREATE TABLE IF NOT EXISTS audit.evidence_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    entity_type VARCHAR(64) NOT NULL,
    entity_id UUID NOT NULL,
    evidence_type VARCHAR(64) NOT NULL,
    evidence_ref UUID NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS audit_evidence_entity_idx
    ON audit.evidence_links (org_id, entity_type, entity_id, created_at DESC);

-- Policy rules (governance runtime)
CREATE TABLE IF NOT EXISTS governance.policy_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    policy_key VARCHAR(128) NOT NULL,
    policy_type VARCHAR(64) NOT NULL,
    conditions JSONB NOT NULL DEFAULT '{}'::jsonb,
    actions JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    priority INT NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, policy_key)
);

CREATE INDEX IF NOT EXISTS governance_policy_org_active_idx
    ON governance.policy_rules (org_id, is_active, policy_type);

-- Governance violations (maker-checker, limits, SoD)
CREATE TABLE IF NOT EXISTS governance.violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    violation_type VARCHAR(128) NOT NULL,
    severity VARCHAR(32) NOT NULL DEFAULT 'high',
    entity_type VARCHAR(64),
    entity_id UUID,
    detected_by VARCHAR(128) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS governance_violations_org_open_idx
    ON governance.violations (org_id, resolved, created_at DESC);

-- Compliance events (GST, TDS, approval trails)
CREATE TABLE IF NOT EXISTS compliance.compliance_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    compliance_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    severity VARCHAR(32) NOT NULL DEFAULT 'info',
    related_entity_type VARCHAR(64),
    related_entity_id UUID,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS compliance_events_org_type_idx
    ON compliance.compliance_events (org_id, compliance_type, created_at DESC);

-- Retention policies (archival — never hard-delete audit)
CREATE TABLE IF NOT EXISTS governance.retention_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    resource_type VARCHAR(64) NOT NULL,
    retain_years INT NOT NULL DEFAULT 8,
    archive_after_days INT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, resource_type)
);

-- Append-only triggers for new governance tables (violations allow resolve flag only via dedicated function)
CREATE OR REPLACE FUNCTION governance.prevent_violation_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'governance.violations records cannot be deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER governance_violations_no_delete
BEFORE DELETE ON governance.violations
FOR EACH ROW EXECUTE FUNCTION governance.prevent_violation_delete();

CREATE OR REPLACE FUNCTION audit.prevent_ai_trace_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit.ai_reasoning_traces is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_ai_traces_no_update
BEFORE UPDATE ON audit.ai_reasoning_traces
FOR EACH ROW EXECUTE FUNCTION audit.prevent_ai_trace_mutation();

CREATE TRIGGER audit_ai_traces_no_delete
BEFORE DELETE ON audit.ai_reasoning_traces
FOR EACH ROW EXECUTE FUNCTION audit.prevent_ai_trace_mutation();

CREATE OR REPLACE FUNCTION audit.prevent_evidence_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit.evidence_links is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_evidence_no_update
BEFORE UPDATE ON audit.evidence_links
FOR EACH ROW EXECUTE FUNCTION audit.prevent_evidence_delete();

CREATE TRIGGER audit_evidence_no_delete
BEFORE DELETE ON audit.evidence_links
FOR EACH ROW EXECUTE FUNCTION audit.prevent_evidence_delete();

-- RLS
ALTER TABLE audit.ai_reasoning_traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit.ai_reasoning_traces FORCE ROW LEVEL SECURITY;
ALTER TABLE audit.evidence_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit.evidence_links FORCE ROW LEVEL SECURITY;
ALTER TABLE governance.policy_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE governance.policy_rules FORCE ROW LEVEL SECURITY;
ALTER TABLE governance.violations ENABLE ROW LEVEL SECURITY;
ALTER TABLE governance.violations FORCE ROW LEVEL SECURITY;
ALTER TABLE compliance.compliance_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance.compliance_events FORCE ROW LEVEL SECURITY;
ALTER TABLE governance.retention_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE governance.retention_policies FORCE ROW LEVEL SECURITY;

CREATE POLICY audit_ai_traces_org ON audit.ai_reasoning_traces
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY audit_evidence_org ON audit.evidence_links
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY governance_policy_org ON governance.policy_rules
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY governance_violations_org ON governance.violations
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY compliance_events_org ON compliance.compliance_events
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY governance_retention_org ON governance.retention_policies
    USING (org_id = current_setting('app.current_org', true)::UUID);

-- Seed default retention (8 years — India finance)
INSERT INTO governance.retention_policies (org_id, resource_type, retain_years, archive_after_days)
SELECT o.id, r.resource_type, 8, 365
FROM core.organizations o
CROSS JOIN (
    VALUES ('audit_logs'), ('gst_records'), ('financial_records'), ('ai_traces')
) AS r(resource_type)
ON CONFLICT (org_id, resource_type) DO NOTHING;

-- Seed platform governance policies per org
INSERT INTO governance.policy_rules (org_id, policy_key, policy_type, conditions, actions, priority)
SELECT o.id, p.policy_key, p.policy_type, p.conditions::jsonb, p.actions::jsonb, p.priority
FROM core.organizations o
CROSS JOIN (
    VALUES
        ('maker_checker_required', 'segregation', '{"enforce": true}', '{"block": true, "audit": true}', 10),
        ('payment_threshold_cfo', 'approval', '{"amount_gt": 1000000}', '{"require_role": "cfo"}', 50),
        ('fiscal_period_lock', 'fiscal', '{"closed_period": true}', '{"block": true}', 20),
        ('gst_filing_deadline', 'compliance', '{"day_of_month_gt": 20}', '{"alert": true}', 30)
) AS p(policy_key, policy_type, conditions, actions, priority)
ON CONFLICT (org_id, policy_key) DO NOTHING;
