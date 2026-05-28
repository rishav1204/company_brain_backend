-- Module 2 v3: immutable approvals, step DLQ, scheduled workflows, latency tracking

-- Immutable approvals (cannot change decision after leave pending)
CREATE OR REPLACE FUNCTION workflow.enforce_approval_immutability()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.decision IS DISTINCT FROM 'pending' AND NEW.decision IS DISTINCT FROM OLD.decision THEN
        RAISE EXCEPTION 'workflow.approvals are immutable after decision';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS workflow_approvals_immutable ON workflow.approvals;
CREATE TRIGGER workflow_approvals_immutability
    BEFORE UPDATE ON workflow.approvals
    FOR EACH ROW EXECUTE FUNCTION workflow.enforce_approval_immutability();

-- Dead-letter queue for failed steps
CREATE TABLE IF NOT EXISTS workflow.step_failures (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    workflow_instance_id UUID NOT NULL REFERENCES workflow.workflow_instances(id) ON DELETE CASCADE,
    workflow_step_id UUID NOT NULL REFERENCES workflow.workflow_steps(id) ON DELETE CASCADE,
    error_code VARCHAR(64) NOT NULL,
    error_detail TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS workflow_step_failures_open_idx
    ON workflow.step_failures (org_id, workflow_instance_id) WHERE resolved_at IS NULL;

ALTER TABLE workflow.step_failures ENABLE ROW LEVEL SECURITY;
CREATE POLICY workflow_step_failures_tenant ON workflow.step_failures
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

-- Scheduled system workflow triggers
CREATE TABLE IF NOT EXISTS workflow.scheduled_workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    workflow_key VARCHAR(128) NOT NULL,
    cron_expression VARCHAR(64) NOT NULL DEFAULT '0 6 * * 1-5',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, workflow_key)
);

ALTER TABLE workflow.scheduled_workflows ENABLE ROW LEVEL SECURITY;
CREATE POLICY workflow_scheduled_tenant ON workflow.scheduled_workflows
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

INSERT INTO workflow.scheduled_workflows (org_id, workflow_key, cron_expression, metadata)
VALUES
    (
        '11111111-1111-4111-8111-111111111111'::uuid,
        'BANK_RECONCILIATION',
        '0 6 * * 1-5',
        '{"system": true, "description": "Daily bank reconciliation"}'::jsonb
    )
ON CONFLICT DO NOTHING;

-- Latency samples for observability
CREATE TABLE IF NOT EXISTS workflow.latency_samples (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    workflow_instance_id UUID,
    metric_type VARCHAR(64) NOT NULL,
    duration_ms INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS workflow_latency_samples_org_type_idx
    ON workflow.latency_samples (org_id, metric_type, recorded_at DESC);

ALTER TABLE workflow.latency_samples ENABLE ROW LEVEL SECURITY;
CREATE POLICY workflow_latency_samples_tenant ON workflow.latency_samples
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());
