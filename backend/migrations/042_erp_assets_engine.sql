-- Module 17: Fixed Assets Management Engine

CREATE SCHEMA IF NOT EXISTS erp;

-- 1) Asset categories
CREATE TABLE IF NOT EXISTS erp.asset_categories (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  category_code varchar(50) NOT NULL,
  category_name varchar(255) NOT NULL,
  depreciation_method varchar(50) NOT NULL DEFAULT 'straight_line',
  default_useful_life_months integer NOT NULL DEFAULT 36,
  default_salvage_percent numeric(5,2) NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.asset_categories ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='asset_categories' AND policyname='asset_categories_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY asset_categories_org_isolation ON erp.asset_categories
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_asset_category_code ON erp.asset_categories(org_id, category_code);

-- 2) Asset policies
CREATE TABLE IF NOT EXISTS erp.asset_policies (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  policy_name varchar(100) NOT NULL DEFAULT 'default',
  capitalization_threshold numeric(18,2) NOT NULL DEFAULT 50000,
  depreciation_frequency varchar(20) NOT NULL DEFAULT 'monthly',
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.asset_policies ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='asset_policies' AND policyname='asset_policies_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY asset_policies_org_isolation ON erp.asset_policies
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- 3) Assets register
CREATE TABLE IF NOT EXISTS erp.assets (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  asset_code varchar(50) NOT NULL,
  asset_name varchar(255) NOT NULL,
  asset_category_id uuid NULL REFERENCES erp.asset_categories(id) ON DELETE SET NULL,
  purchase_date date NULL,
  capitalization_date date NULL,
  cost numeric(18,2) NOT NULL DEFAULT 0,
  salvage_value numeric(18,2) NOT NULL DEFAULT 0,
  useful_life_months integer NOT NULL DEFAULT 36,
  depreciation_method varchar(50) NOT NULL DEFAULT 'straight_line',
  accumulated_depreciation numeric(18,2) NOT NULL DEFAULT 0,
  impairment_amount numeric(18,2) NOT NULL DEFAULT 0,
  book_value numeric(18,2) NOT NULL DEFAULT 0,
  status varchar(30) NOT NULL DEFAULT 'draft',
  workflow_approved boolean NOT NULL DEFAULT false,
  fixed_asset_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  accumulated_depreciation_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  depreciation_expense_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  capitalization_journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  location varchar(255) NULL,
  department_id uuid NULL,
  custodian_id uuid NULL,
  cost_center_id uuid NULL REFERENCES erp.cost_centers(id) ON DELETE SET NULL,
  source_type varchar(50) NULL,
  source_id uuid NULL,
  purchase_order_id uuid NULL,
  ap_invoice_id uuid NULL,
  ap_invoice_line_id uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  approved_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.assets ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='assets' AND policyname='assets_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY assets_org_isolation ON erp.assets
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.assets
  ADD CONSTRAINT chk_erp_asset_status
  CHECK (status IN ('draft','active','under_transfer','fully_depreciated','impaired','disposed'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_asset_code ON erp.assets(org_id, asset_code);
CREATE INDEX IF NOT EXISTS idx_erp_assets_status ON erp.assets(org_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_erp_assets_category ON erp.assets(org_id, asset_category_id);

-- 4) Depreciation history
CREATE TABLE IF NOT EXISTS erp.asset_depreciation (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  asset_id uuid NOT NULL REFERENCES erp.assets(id) ON DELETE CASCADE,
  depreciation_date date NOT NULL,
  period_key varchar(20) NOT NULL,
  opening_book_value numeric(18,2) NOT NULL DEFAULT 0,
  depreciation_amount numeric(18,2) NOT NULL DEFAULT 0,
  closing_book_value numeric(18,2) NOT NULL DEFAULT 0,
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.asset_depreciation ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='asset_depreciation' AND policyname='asset_depreciation_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY asset_depreciation_org_isolation ON erp.asset_depreciation
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_asset_depr_period ON erp.asset_depreciation(org_id, asset_id, period_key);

-- 5) Transfers
CREATE TABLE IF NOT EXISTS erp.asset_transfers (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  asset_id uuid NOT NULL REFERENCES erp.assets(id) ON DELETE CASCADE,
  from_department_id uuid NULL,
  to_department_id uuid NULL,
  from_location varchar(255) NULL,
  to_location varchar(255) NULL,
  from_custodian_id uuid NULL,
  to_custodian_id uuid NULL,
  transfer_date date NOT NULL DEFAULT CURRENT_DATE,
  reason text NULL,
  created_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.asset_transfers ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='asset_transfers' AND policyname='asset_transfers_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY asset_transfers_org_isolation ON erp.asset_transfers
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- 6) Impairments
CREATE TABLE IF NOT EXISTS erp.asset_impairments (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  asset_id uuid NOT NULL REFERENCES erp.assets(id) ON DELETE CASCADE,
  impairment_date date NOT NULL DEFAULT CURRENT_DATE,
  impairment_amount numeric(18,2) NOT NULL DEFAULT 0,
  book_value_before numeric(18,2) NOT NULL DEFAULT 0,
  book_value_after numeric(18,2) NOT NULL DEFAULT 0,
  reason text NULL,
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  created_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.asset_impairments ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='asset_impairments' AND policyname='asset_impairments_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY asset_impairments_org_isolation ON erp.asset_impairments
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- 7) Disposals
CREATE TABLE IF NOT EXISTS erp.asset_disposals (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  asset_id uuid NOT NULL REFERENCES erp.assets(id) ON DELETE CASCADE,
  disposal_date date NOT NULL DEFAULT CURRENT_DATE,
  sale_amount numeric(18,2) NOT NULL DEFAULT 0,
  book_value numeric(18,2) NOT NULL DEFAULT 0,
  gain_loss numeric(18,2) NOT NULL DEFAULT 0,
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  reason text NULL,
  created_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.asset_disposals ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='asset_disposals' AND policyname='asset_disposals_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY asset_disposals_org_isolation ON erp.asset_disposals
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- 8) Capitalization candidates
CREATE TABLE IF NOT EXISTS erp.asset_capitalization_candidates (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  source_type varchar(50) NOT NULL,
  source_id uuid NOT NULL,
  amount numeric(18,2) NOT NULL DEFAULT 0,
  description text NULL,
  suggested_category_id uuid NULL REFERENCES erp.asset_categories(id) ON DELETE SET NULL,
  status varchar(30) NOT NULL DEFAULT 'pending',
  asset_id uuid NULL REFERENCES erp.assets(id) ON DELETE SET NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.asset_capitalization_candidates ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='asset_capitalization_candidates' AND policyname='asset_capitalization_candidates_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY asset_capitalization_candidates_org_isolation ON erp.asset_capitalization_candidates
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.asset_capitalization_candidates
  ADD CONSTRAINT chk_erp_asset_candidate_status
  CHECK (status IN ('pending','converted','rejected','pending_reclass'));

CREATE INDEX IF NOT EXISTS idx_erp_asset_candidates_source ON erp.asset_capitalization_candidates(org_id, source_type, source_id);

-- IAM permissions
INSERT INTO core.permissions (resource, action, description) VALUES
    ('asset', 'read', 'View fixed assets'),
    ('asset', 'create', 'Create draft assets'),
    ('asset', 'capitalize', 'Capitalize fixed assets'),
    ('asset', 'depreciate', 'Run depreciation'),
    ('asset', 'transfer', 'Transfer asset ownership'),
    ('asset', 'dispose', 'Dispose fixed assets'),
    ('asset', 'impair', 'Record asset impairment'),
    ('asset', 'policy', 'Manage asset policies'),
    ('asset', 'admin', 'Asset administration')
ON CONFLICT (resource, action) DO NOTHING;

INSERT INTO core.roles (id, org_id, name, description, policy_context)
VALUES
  ('d1000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'asset_manager', 'Fixed asset lifecycle manager', '{}'::jsonb),
  ('d1000001-0001-4001-8001-000000000002'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'finance_controller', 'Finance controller for assets', '{"max_approve_amount": 5000000}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource = 'asset'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('asset_manager', 'finance_controller', 'finance_manager', 'controller', 'cfo', 'tenant_admin')
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource = 'asset' AND p.action = 'read'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('auditor', 'analyst')
ON CONFLICT DO NOTHING;

-- Workflows
INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
  (
    'd2000001-0001-4001-8001-000000000001'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'ASSET_CAPITALIZATION_APPROVAL',
    'Asset Capitalization Approval',
    'Approve fixed asset capitalization',
    1,
    '{"steps": [{"key": "finance_review", "type": "human_approval", "sla_hours": 48}, {"key": "validate", "type": "validation"}]}'::jsonb
  ),
  (
    'd2000001-0001-4001-8001-000000000002'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'ASSET_DISPOSAL_APPROVAL',
    'Asset Disposal Approval',
    'Approve asset disposal',
    1,
    '{"steps": [{"key": "controller_review", "type": "human_approval", "sla_hours": 48}, {"key": "validate", "type": "validation"}]}'::jsonb
  ),
  (
    'd2000001-0001-4001-8001-000000000003'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'ASSET_IMPAIRMENT_APPROVAL',
    'Asset Impairment Approval',
    'Approve asset impairment',
    1,
    '{"steps": [{"key": "finance_review", "type": "human_approval", "sla_hours": 48}, {"key": "validate", "type": "validation"}]}'::jsonb
  )
ON CONFLICT DO NOTHING;

-- Default categories
INSERT INTO erp.asset_categories (id, org_id, category_code, category_name, depreciation_method, default_useful_life_months, default_salvage_percent)
VALUES
  ('d3000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'COMPUTERS', 'Computers', 'straight_line', 36, 5),
  ('d3000001-0001-4001-8001-000000000002'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'FURNITURE', 'Furniture', 'straight_line', 60, 5),
  ('d3000001-0001-4001-8001-000000000003'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'VEHICLES', 'Vehicles', 'straight_line', 60, 10),
  ('d3000001-0001-4001-8001-000000000004'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'BUILDINGS', 'Buildings', 'straight_line', 240, 5),
  ('d3000001-0001-4001-8001-000000000005'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'MACHINERY', 'Machinery', 'straight_line', 120, 5),
  ('d3000001-0001-4001-8001-000000000006'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'SOFTWARE', 'Software', 'straight_line', 36, 0)
ON CONFLICT DO NOTHING;

INSERT INTO erp.asset_policies (id, org_id, policy_name, capitalization_threshold, depreciation_frequency)
VALUES
  ('d4000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'default', 50000, 'monthly')
ON CONFLICT DO NOTHING;
