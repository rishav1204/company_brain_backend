-- M11 voucher workflow definitions

INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
    (
        'd0000001-0001-4001-8001-000000000064'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'VOUCHER_APPROVAL',
        'Voucher Approval',
        'Manual voucher entry approval before journal generation',
        1,
        '{"steps": [{"key": "approval", "type": "human_approval", "sla_hours": 24}, {"key": "post", "type": "validation"}]}'::jsonb
    ),
    (
        'd0000001-0001-4001-8001-000000000065'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'AP_CREDIT_NOTE_APPROVAL',
        'AP Credit Note Approval',
        'Vendor credit note approval',
        1,
        '{"steps": [{"key": "approval", "type": "human_approval", "sla_hours": 24}]}'::jsonb
    ),
    (
        'd0000001-0001-4001-8001-000000000066'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'AP_DEBIT_NOTE_APPROVAL',
        'AP Debit Note Approval',
        'Vendor debit note approval',
        1,
        '{"steps": [{"key": "approval", "type": "human_approval", "sla_hours": 24}]}'::jsonb
    ),
    (
        'd0000001-0001-4001-8001-000000000067'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'AR_CREDIT_NOTE_APPROVAL',
        'AR Credit Note Approval',
        'Customer credit note approval',
        1,
        '{"steps": [{"key": "approval", "type": "human_approval", "sla_hours": 24}]}'::jsonb
    )
ON CONFLICT DO NOTHING;

ALTER TABLE erp.ap_payments ADD COLUMN IF NOT EXISTS voucher_id uuid NULL REFERENCES erp.vouchers(id) ON DELETE SET NULL;
