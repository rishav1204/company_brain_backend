-- Module 2 extensions: holidays, additional definitions, conditional approval metadata

CREATE TABLE IF NOT EXISTS workflow.org_holidays (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    holiday_date DATE NOT NULL,
    name VARCHAR(128),
    UNIQUE (org_id, holiday_date)
);

ALTER TABLE workflow.org_holidays ENABLE ROW LEVEL SECURITY;
CREATE POLICY workflow_org_holidays_tenant ON workflow.org_holidays
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
    (
        'd0000001-0001-4001-8001-000000000004'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'GST_FILING',
        'GST Filing Approval',
        'GST return review and filing approval',
        1,
        '{"steps": [{"key": "compliance_review", "type": "human_approval", "sla_hours": 24}, {"key": "file", "type": "validation"}], "conditional_approvals": [{"when": {"vendor_risk": "HIGH"}, "role": "compliance_officer"}]}'::jsonb
    ),
    (
        'd0000001-0001-4001-8001-000000000005'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'BANK_RECONCILIATION',
        'Bank Reconciliation',
        'Bank reconciliation review workflow',
        1,
        '{"steps": [{"key": "recon", "type": "reconciliation", "sla_hours": 12}, {"key": "approval", "type": "human_approval", "sla_hours": 24}]}'::jsonb
    ),
    (
        'd0000001-0001-4001-8001-000000000006'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'VENDOR_ONBOARDING',
        'Vendor Onboarding',
        'Vendor onboarding approval chain',
        1,
        '{"steps": [{"key": "ai_review", "type": "ai_review"}, {"key": "ap_approval", "type": "human_approval", "sla_hours": 48}, {"key": "legal", "type": "human_approval", "conditions": {"vendor_risk": "HIGH"}}], "approval_chain": [{"level": 1, "role": "ap_executive"}, {"level": 2, "role": "finance_manager"}]}'::jsonb
    )
ON CONFLICT DO NOTHING;

UPDATE workflow.workflow_definitions
SET definition_json = definition_json || '{"conditional_approvals": [{"when": {"vendor_risk": "HIGH"}, "role": "legal"}]}'::jsonb
WHERE workflow_key = 'AP_INVOICE_APPROVAL' AND org_id = '11111111-1111-4111-8111-111111111111'::uuid;
