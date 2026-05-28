-- IAM hardening: per-org email, explicit RLS, business units, fiscal periods

-- Per-tenant email uniqueness (multi-tenant SaaS)
DROP INDEX IF EXISTS core_users_email_lower_key;
CREATE UNIQUE INDEX IF NOT EXISTS core_users_org_email_key ON core.users (org_id, lower(email));

-- Explicit RLS on core.users and user_roles (after schema move)
ALTER TABLE core.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.user_roles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS core_users_org_isolation ON core.users;
CREATE POLICY core_users_org_isolation ON core.users
    FOR ALL
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

DROP POLICY IF EXISTS core_user_roles_org_isolation ON core.user_roles;
CREATE POLICY core_user_roles_org_isolation ON core.user_roles
    FOR ALL
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

-- Business units (org structure)
CREATE TABLE IF NOT EXISTS core.business_units (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    company_id UUID REFERENCES core.companies(id) ON DELETE SET NULL,
    unit_code VARCHAR(64) NOT NULL,
    unit_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, unit_code)
);

CREATE INDEX IF NOT EXISTS core_business_units_org_idx ON core.business_units (org_id);

ALTER TABLE core.business_units ENABLE ROW LEVEL SECURITY;

CREATE POLICY core_business_units_tenant ON core.business_units
    FOR ALL
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

-- Fiscal periods for journal posting gates
CREATE TABLE IF NOT EXISTS core.fiscal_periods (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    company_id UUID REFERENCES core.companies(id) ON DELETE CASCADE,
    period_key VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    starts_on DATE NOT NULL,
    ends_on DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, company_id, period_key)
);

CREATE INDEX IF NOT EXISTS core_fiscal_periods_org_idx ON core.fiscal_periods (org_id);

ALTER TABLE core.fiscal_periods ENABLE ROW LEVEL SECURITY;

CREATE POLICY core_fiscal_periods_tenant ON core.fiscal_periods
    FOR ALL
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

-- Default open fiscal period for benchmark org
INSERT INTO core.fiscal_periods (org_id, company_id, period_key, status, starts_on, ends_on)
VALUES (
    '11111111-1111-4111-8111-111111111111'::uuid,
    'c0000001-0001-4001-8001-000000000001'::uuid,
    '2025-04',
    'open',
    '2025-04-01',
    '2026-03-31'
)
ON CONFLICT DO NOTHING;

-- ABAC policy rules on seeded roles (amount_lt, fiscal_period_open, branch 10L rule)
UPDATE core.roles
SET policy_context = policy_context || jsonb_build_object(
    'rules', jsonb_build_array(
        jsonb_build_object(
            'resource', 'payment',
            'action', 'approve',
            'condition', jsonb_build_object('amount_lte', 500000)
        ),
        jsonb_build_object(
            'resource', 'journal',
            'action', 'post',
            'condition', jsonb_build_object('fiscal_period_open', true)
        ),
        jsonb_build_object(
            'resource', 'payment',
            'action', 'approve',
            'condition', jsonb_build_object('branch_amount_outside_limit', 1000000)
        )
    )
)
WHERE org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND name = 'ap_executive';

UPDATE core.roles
SET policy_context = policy_context || '{"mfa_required": true}'::jsonb
WHERE org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND name IN ('cfo', 'tenant_admin', 'finance_admin');
