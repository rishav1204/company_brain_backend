-- Module 2: Enterprise workflow engine (workflow.* schema)
-- Operational execution state — separate from ERP financial truth.

CREATE SCHEMA IF NOT EXISTS workflow;

-- ---------------------------------------------------------------------------
-- 1. workflow_definitions (versioned templates)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow.workflow_definitions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    workflow_key VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    definition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, workflow_key, version)
);

CREATE INDEX IF NOT EXISTS workflow_definitions_org_key_idx
    ON workflow.workflow_definitions (org_id, workflow_key);

-- ---------------------------------------------------------------------------
-- 2. workflow_instances (runtime)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow.workflow_instances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    workflow_definition_id UUID REFERENCES workflow.workflow_definitions(id),
    entity_type VARCHAR(64) NOT NULL DEFAULT 'workflow',
    entity_id UUID,
    legacy_workflow_id UUID,
    workflow_type VARCHAR(128) NOT NULL,
    status VARCHAR(64) NOT NULL DEFAULT 'draft',
    priority VARCHAR(32) NOT NULL DEFAULT 'normal',
    started_by UUID,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    current_step_id UUID,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS workflow_instances_legacy_uidx
    ON workflow.workflow_instances (org_id, legacy_workflow_id)
    WHERE legacy_workflow_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS workflow_instances_org_status_idx
    ON workflow.workflow_instances (org_id, status);

CREATE INDEX IF NOT EXISTS workflow_instances_entity_idx
    ON workflow.workflow_instances (org_id, entity_type, entity_id);

-- ---------------------------------------------------------------------------
-- 3. workflow_steps
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow.workflow_steps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    workflow_instance_id UUID NOT NULL REFERENCES workflow.workflow_instances(id) ON DELETE CASCADE,
    step_key VARCHAR(128) NOT NULL,
    step_type VARCHAR(64) NOT NULL,
    status VARCHAR(64) NOT NULL DEFAULT 'pending',
    assigned_to UUID,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    retry_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS workflow_steps_instance_idx
    ON workflow.workflow_steps (workflow_instance_id, status);

-- ---------------------------------------------------------------------------
-- 4. approvals
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow.approvals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    workflow_instance_id UUID NOT NULL REFERENCES workflow.workflow_instances(id) ON DELETE CASCADE,
    workflow_step_id UUID NOT NULL REFERENCES workflow.workflow_steps(id) ON DELETE CASCADE,
    approver_user_id UUID,
    requested_from_user_id UUID,
    decision VARCHAR(32) NOT NULL DEFAULT 'pending',
    decision_reason TEXT,
    amount_threshold NUMERIC(18, 2),
    level INTEGER NOT NULL DEFAULT 1,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS workflow_approvals_pending_idx
    ON workflow.approvals (org_id, decision) WHERE decision = 'pending';

-- ---------------------------------------------------------------------------
-- 5. escalations
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow.escalations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    workflow_instance_id UUID NOT NULL REFERENCES workflow.workflow_instances(id) ON DELETE CASCADE,
    step_id UUID REFERENCES workflow.workflow_steps(id),
    escalation_type VARCHAR(64) NOT NULL,
    escalated_to UUID,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- 6. workflow_tasks (unified task inbox)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow.workflow_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    workflow_instance_id UUID NOT NULL REFERENCES workflow.workflow_instances(id) ON DELETE CASCADE,
    workflow_step_id UUID REFERENCES workflow.workflow_steps(id),
    task_type VARCHAR(64) NOT NULL,
    assigned_to UUID,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    due_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS workflow_tasks_assignee_idx
    ON workflow.workflow_tasks (org_id, assigned_to, status);

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
ALTER TABLE workflow.workflow_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.workflow_instances ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.workflow_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.escalations ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.workflow_tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY workflow_definitions_tenant ON workflow.workflow_definitions
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());
CREATE POLICY workflow_instances_tenant ON workflow.workflow_instances
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());
CREATE POLICY workflow_steps_tenant ON workflow.workflow_steps
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());
CREATE POLICY workflow_approvals_tenant ON workflow.approvals
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());
CREATE POLICY workflow_escalations_tenant ON workflow.escalations
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());
CREATE POLICY workflow_tasks_tenant ON workflow.workflow_tasks
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

-- ---------------------------------------------------------------------------
-- Seed default definitions (benchmark org)
-- ---------------------------------------------------------------------------
INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
    (
        'd0000001-0001-4001-8001-000000000001'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'AP_INVOICE_APPROVAL',
        'AP Invoice Approval',
        'Multi-step AP invoice approval with threshold routing',
        1,
        '{
          "steps": [
            {"key": "ai_review", "type": "ai_review", "optional": true},
            {"key": "manager_approval", "type": "human_approval", "sla_hours": 24},
            {"key": "payment_execution", "type": "payment_execution"}
          ],
          "thresholds": [
            {"max_amount": 100000, "role": "ap_executive"},
            {"max_amount": 1000000, "role": "finance_manager"},
            {"max_amount": null, "role": "cfo"}
          ]
        }'::jsonb
    ),
    (
        'd0000001-0001-4001-8001-000000000002'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'PAYMENT_APPROVAL',
        'Payment Approval',
        'Payment release approval workflow',
        1,
        '{"steps": [{"key": "approval", "type": "human_approval", "sla_hours": 12}, {"key": "execute", "type": "payment_execution"}]}'::jsonb
    ),
    (
        'd0000001-0001-4001-8001-000000000003'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'JOURNAL_APPROVAL',
        'Journal Approval',
        'Journal posting approval',
        1,
        '{"steps": [{"key": "approval", "type": "human_approval", "sla_hours": 24}, {"key": "post", "type": "validation"}]}'::jsonb
    )
ON CONFLICT DO NOTHING;

-- Migrate existing public.workflows into workflow_instances (backward link)
INSERT INTO workflow.workflow_instances (
    org_id, workflow_type, status, started_by, started_at, completed_at,
    legacy_workflow_id, metadata, entity_type, entity_id
)
SELECT
    w.org_id,
    w.workflow_type,
    CASE w.state
        WHEN 'pending_approval' THEN 'waiting_approval'
        WHEN 'blocked' THEN 'running'
        WHEN 'executed' THEN 'completed'
        ELSE COALESCE(w.state, 'running')
    END,
    w.owner_user_id,
    w.started_at,
    w.closed_at,
    w.id,
    '{}'::jsonb,
    'workflow',
    w.id
FROM workflows w
WHERE NOT EXISTS (
    SELECT 1 FROM workflow.workflow_instances wi
    WHERE wi.legacy_workflow_id = w.id
);

-- Add workflow permissions to IAM catalog
INSERT INTO core.permissions (resource, action, description) VALUES
    ('workflow', 'read', 'View workflows and tasks'),
    ('workflow', 'write', 'Execute workflow actions'),
    ('workflow', 'manage', 'Manage workflow definitions'),
    ('approval', 'read', 'View approval requests'),
    ('approval', 'decide', 'Approve or reject workflow steps'),
    ('task', 'read', 'View assigned tasks'),
    ('task', 'assign', 'Assign workflow tasks')
ON CONFLICT (resource, action) DO NOTHING;
