-- Module 1: Identity & Access Management (core schema)
-- Moves legacy IAM tables into core.* and adds enterprise IAM structures.

CREATE SCHEMA IF NOT EXISTS core;

-- ---------------------------------------------------------------------------
-- Move existing public IAM tables into core (FKs from finance tables follow)
-- ---------------------------------------------------------------------------
ALTER TABLE organizations SET SCHEMA core;
ALTER TABLE users SET SCHEMA core;
ALTER TABLE roles SET SCHEMA core;
ALTER TABLE user_roles SET SCHEMA core;

-- ---------------------------------------------------------------------------
-- core.organizations
-- ---------------------------------------------------------------------------
ALTER TABLE core.organizations
    ADD COLUMN IF NOT EXISTS slug VARCHAR(128),
    ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS country_code VARCHAR(8) NOT NULL DEFAULT 'IN',
    ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata',
    ADD COLUMN IF NOT EXISTS currency VARCHAR(8) NOT NULL DEFAULT 'INR',
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE core.organizations
SET slug = lower(regexp_replace(trim(name), '[^a-zA-Z0-9]+', '-', 'g'))
WHERE slug IS NULL OR trim(slug) = '';

ALTER TABLE core.organizations ALTER COLUMN slug SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS core_organizations_slug_key ON core.organizations (slug);

-- ---------------------------------------------------------------------------
-- core.users
-- ---------------------------------------------------------------------------
ALTER TABLE core.users
    ADD COLUMN IF NOT EXISTS phone VARCHAR(32),
    ADD COLUMN IF NOT EXISTS password_hash TEXT,
    ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS mfa_secret TEXT,
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE UNIQUE INDEX IF NOT EXISTS core_users_email_lower_key ON core.users (lower(email));

-- ---------------------------------------------------------------------------
-- core.roles
-- ---------------------------------------------------------------------------
ALTER TABLE core.roles
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS system_role BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS policy_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE UNIQUE INDEX IF NOT EXISTS core_roles_org_name_key ON core.roles (org_id, lower(name));

-- ---------------------------------------------------------------------------
-- core.user_roles (branch/company scoped assignments)
-- ---------------------------------------------------------------------------
ALTER TABLE core.user_roles
    ADD COLUMN IF NOT EXISTS id UUID DEFAULT uuid_generate_v4(),
    ADD COLUMN IF NOT EXISTS company_id UUID,
    ADD COLUMN IF NOT EXISTS branch_id UUID,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- ---------------------------------------------------------------------------
-- core.companies
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS core.companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    legal_name VARCHAR(255) NOT NULL,
    gstin VARCHAR(32),
    pan VARCHAR(16),
    tan VARCHAR(16),
    cin VARCHAR(32),
    base_currency VARCHAR(8) NOT NULL DEFAULT 'INR',
    financial_year_start DATE NOT NULL DEFAULT '2025-04-01',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS core_companies_org_idx ON core.companies (org_id);

-- ---------------------------------------------------------------------------
-- core.branches
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS core.branches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES core.companies(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    branch_code VARCHAR(64) NOT NULL,
    branch_name VARCHAR(255) NOT NULL,
    state_code VARCHAR(8),
    address JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, branch_code)
);

CREATE INDEX IF NOT EXISTS core_branches_org_idx ON core.branches (org_id);

ALTER TABLE core.user_roles
    ADD CONSTRAINT user_roles_company_fk FOREIGN KEY (company_id) REFERENCES core.companies(id) ON DELETE SET NULL,
    ADD CONSTRAINT user_roles_branch_fk FOREIGN KEY (branch_id) REFERENCES core.branches(id) ON DELETE SET NULL;

-- ---------------------------------------------------------------------------
-- core.permissions (global catalog)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS core.permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    permission_key VARCHAR(128) GENERATED ALWAYS AS (resource || '.' || action) STORED,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (resource, action)
);

-- ---------------------------------------------------------------------------
-- core.role_permissions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS core.role_permissions (
    role_id UUID NOT NULL REFERENCES core.roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES core.permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (role_id, permission_id)
);

-- ---------------------------------------------------------------------------
-- core.sessions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS core.sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    refresh_token_hash TEXT NOT NULL,
    device_info JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address INET,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    rotated_from UUID REFERENCES core.sessions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS core_sessions_user_idx ON core.sessions (user_id);
CREATE INDEX IF NOT EXISTS core_sessions_org_idx ON core.sessions (org_id);
CREATE INDEX IF NOT EXISTS core_sessions_refresh_hash_idx ON core.sessions (refresh_token_hash);

-- ---------------------------------------------------------------------------
-- core.api_keys
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS core.api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    hashed_key TEXT NOT NULL,
    scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
    expires_at TIMESTAMPTZ,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS core_api_keys_org_idx ON core.api_keys (org_id);

-- ---------------------------------------------------------------------------
-- Row level security
-- ---------------------------------------------------------------------------
ALTER TABLE core.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY core_organizations_tenant ON core.organizations
    FOR ALL
    USING (id = app_current_org_id())
    WITH CHECK (id = app_current_org_id());

CREATE POLICY core_companies_tenant ON core.companies
    FOR ALL
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

CREATE POLICY core_branches_tenant ON core.branches
    FOR ALL
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

CREATE POLICY core_roles_tenant ON core.roles
    FOR ALL
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

CREATE POLICY core_api_keys_tenant ON core.api_keys
    FOR ALL
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

CREATE POLICY core_sessions_tenant ON core.sessions
    FOR ALL
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

-- permissions catalog is global (read by authenticated services outside RLS context)

-- ---------------------------------------------------------------------------
-- Permission catalog seed
-- ---------------------------------------------------------------------------
INSERT INTO core.permissions (resource, action, description) VALUES
    ('invoice', 'create', 'Create invoices'),
    ('invoice', 'read', 'View invoices'),
    ('invoice', 'approve', 'Approve invoices'),
    ('payment', 'create', 'Create payments'),
    ('payment', 'read', 'View payments'),
    ('payment', 'approve', 'Approve payments'),
    ('payment', 'execute', 'Execute payments'),
    ('journal', 'create', 'Create journals'),
    ('journal', 'read', 'View journals'),
    ('journal', 'post', 'Post journals to ledger'),
    ('gst', 'read', 'View GST data'),
    ('gst', 'file', 'File GST returns'),
    ('bank', 'read', 'View bank accounts'),
    ('bank', 'reconcile', 'Reconcile bank transactions'),
    ('user', 'read', 'View users'),
    ('user', 'manage', 'Manage users and invites'),
    ('role', 'read', 'View roles'),
    ('role', 'manage', 'Manage roles and assignments'),
    ('organization', 'read', 'View organization settings'),
    ('organization', 'manage', 'Manage organization settings'),
    ('session', 'read', 'View active sessions'),
    ('session', 'revoke', 'Revoke sessions')
ON CONFLICT (resource, action) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Default roles for benchmark org (backward-compatible JWT role names)
-- ---------------------------------------------------------------------------
INSERT INTO core.roles (id, org_id, name, description, system_role, policy_context)
VALUES
    ('b0000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'tenant_admin', 'Full tenant administrator', TRUE, '{"max_approve_amount": null}'::jsonb),
    ('b0000001-0001-4001-8001-000000000002'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'cfo', 'Chief Financial Officer', TRUE, '{"max_approve_amount": null, "mfa_required": true}'::jsonb),
    ('b0000001-0001-4001-8001-000000000003'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'controller', 'Financial controller', TRUE, '{"max_approve_amount": null}'::jsonb),
    ('b0000001-0001-4001-8001-000000000004'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'ap_manager', 'Accounts payable manager', TRUE, '{"max_approve_amount": 1000000}'::jsonb),
    ('b0000001-0001-4001-8001-000000000005'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'ap_executive', 'Accounts payable executive', TRUE, '{"max_approve_amount": 500000}'::jsonb),
    ('b0000001-0001-4001-8001-000000000006'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'ap_preparer', 'AP preparer (no payment approval)', TRUE, '{"max_approve_amount": 0, "disallowed_actions": ["approve_payment"]}'::jsonb),
    ('b0000001-0001-4001-8001-000000000007'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'ar_manager', 'Accounts receivable manager', TRUE, '{}'::jsonb),
    ('b0000001-0001-4001-8001-000000000008'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'auditor', 'Read-only auditor', TRUE, '{"read_only": true}'::jsonb),
    ('b0000001-0001-4001-8001-000000000009'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'analyst', 'Finance analyst', TRUE, '{"max_approve_amount": 0}'::jsonb),
    ('b0000001-0001-4001-8001-00000000000a'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'governance_admin', 'Governance and payroll access', TRUE, '{}'::jsonb)
ON CONFLICT DO NOTHING;

-- Map tenant_admin / cfo / controller to broad permissions
INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
CROSS JOIN core.permissions p
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('tenant_admin', 'cfo', 'controller')
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.permission_key IN (
    'invoice.create', 'invoice.read', 'invoice.approve',
    'payment.create', 'payment.read', 'payment.approve',
    'journal.read', 'gst.read', 'bank.read', 'bank.reconcile'
)
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name = 'ap_manager'
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.permission_key IN (
    'invoice.create', 'invoice.read', 'payment.create', 'payment.read', 'journal.read', 'gst.read', 'bank.read'
)
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name = 'ap_executive'
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.permission_key IN (
    'invoice.create', 'invoice.read', 'payment.create', 'payment.read', 'journal.read'
)
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name = 'ap_preparer'
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.permission_key LIKE '%.read'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name = 'auditor'
ON CONFLICT DO NOTHING;

-- Default company + branch for benchmark org
INSERT INTO core.companies (id, org_id, legal_name, gstin, pan, base_currency, financial_year_start)
VALUES (
    'c0000001-0001-4001-8001-000000000001'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'Benchmark Org Private Limited',
    NULL,
    NULL,
    'INR',
    '2025-04-01'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO core.branches (id, company_id, org_id, branch_code, branch_name, state_code)
VALUES (
    'd0000001-0001-4001-8001-000000000001'::uuid,
    'c0000001-0001-4001-8001-000000000001'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'HQ',
    'Head Office',
    'KA'
)
ON CONFLICT DO NOTHING;

-- Dev user (Argon2id hash for password: dev-password)
INSERT INTO core.users (id, org_id, email, display_name, status, password_hash, mfa_enabled)
VALUES (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'dev@example.com',
    'Dev User',
    'active',
    '$argon2id$v=19$m=65536,t=3,p=4$sS2i60LP2UV0HOopRaVJOw$TzqNEb1FQ+Bu8uaYgfc6CATG+JVLLwEsU8dBxxUtssU',
    FALSE
)
ON CONFLICT (id) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    status = 'active',
    email = EXCLUDED.email;

INSERT INTO core.user_roles (org_id, user_id, role_id, company_id, branch_id)
VALUES (
    '11111111-1111-4111-8111-111111111111'::uuid,
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid,
    'b0000001-0001-4001-8001-000000000001'::uuid,
    'c0000001-0001-4001-8001-000000000001'::uuid,
    'd0000001-0001-4001-8001-000000000001'::uuid
)
ON CONFLICT (user_id, role_id) DO NOTHING;
