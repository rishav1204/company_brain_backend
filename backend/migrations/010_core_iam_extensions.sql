-- IAM v2: invites, field permissions, role aliases

INSERT INTO core.permissions (resource, action, description) VALUES
    ('field', 'bank', 'View bank account fields'),
    ('field', 'tax', 'View tax identifier fields'),
    ('field', 'payroll', 'View payroll fields'),
    ('field', 'pii', 'View PII fields')
ON CONFLICT (resource, action) DO NOTHING;

INSERT INTO core.roles (id, org_id, name, description, system_role, policy_context)
VALUES
    ('b0000001-0001-4001-8001-00000000000b'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'super_admin', 'Alias of tenant_admin', TRUE, '{"max_approve_amount": null}'::jsonb),
    ('b0000001-0001-4001-8001-00000000000c'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'finance_admin', 'Finance platform administrator', TRUE, '{"max_approve_amount": null}'::jsonb),
    ('b0000001-0001-4001-8001-00000000000d'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'finance_manager', 'Finance operations manager', TRUE, '{"max_approve_amount": 1000000}'::jsonb),
    ('b0000001-0001-4001-8001-00000000000e'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'approver', 'Payment and journal approver', TRUE, '{"max_approve_amount": 500000, "mfa_required": true}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
CROSS JOIN core.permissions p
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('super_admin', 'finance_admin')
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource = 'field'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('tenant_admin', 'cfo', 'controller', 'governance_admin')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS core.user_invites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    role_id UUID REFERENCES core.roles(id) ON DELETE SET NULL,
    company_id UUID REFERENCES core.companies(id) ON DELETE SET NULL,
    branch_id UUID REFERENCES core.branches(id) ON DELETE SET NULL,
    token_hash TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    expires_at TIMESTAMPTZ NOT NULL,
    invited_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    accepted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS core_user_invites_org_idx ON core.user_invites (org_id);
CREATE UNIQUE INDEX IF NOT EXISTS core_user_invites_pending_email
    ON core.user_invites (org_id, lower(email))
    WHERE status = 'pending';

ALTER TABLE core.user_invites ENABLE ROW LEVEL SECURITY;

-- Dev tenant_admin: global scope (not branch-locked)
UPDATE core.user_roles
SET company_id = NULL, branch_id = NULL
WHERE user_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid
  AND role_id = 'b0000001-0001-4001-8001-000000000001'::uuid;

CREATE POLICY core_user_invites_tenant ON core.user_invites
    FOR ALL
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());
