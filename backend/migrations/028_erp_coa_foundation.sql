-- Module 8: Chart of Accounts (COA) + Accounting Foundation Engine

CREATE SCHEMA IF NOT EXISTS erp;

-- 1) Account groups (hierarchical)
CREATE TABLE IF NOT EXISTS erp.account_groups (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  group_name varchar(256) NOT NULL,
  group_code varchar(64) NOT NULL,
  parent_group_id uuid NULL REFERENCES erp.account_groups(id) ON DELETE SET NULL,
  group_type varchar(32) NOT NULL, -- asset|liability|equity|revenue|expense
  nature varchar(16) NOT NULL,     -- debit|credit
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.account_groups ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='account_groups' AND policyname='account_groups_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY account_groups_org_isolation
      ON erp.account_groups
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_group_code_org_company
  ON erp.account_groups(org_id, COALESCE(company_id, '00000000-0000-0000-0000-000000000000'::uuid), group_code);

CREATE INDEX IF NOT EXISTS idx_erp_account_groups_org ON erp.account_groups(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_erp_account_groups_parent ON erp.account_groups(org_id, parent_group_id);

-- 2) Chart of accounts (hierarchical)
CREATE TABLE IF NOT EXISTS erp.chart_of_accounts (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  account_code varchar(64) NOT NULL,
  account_name varchar(256) NOT NULL,
  account_type varchar(32) NOT NULL,
  group_id uuid NOT NULL REFERENCES erp.account_groups(id) ON DELETE RESTRICT,
  parent_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  is_postable boolean NOT NULL DEFAULT true,
  is_active boolean NOT NULL DEFAULT true,
  currency_code varchar(8) NOT NULL DEFAULT 'INR',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.chart_of_accounts ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='chart_of_accounts' AND policyname='chart_of_accounts_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY chart_of_accounts_org_isolation
      ON erp.chart_of_accounts
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_account_code_org_company
  ON erp.chart_of_accounts(org_id, COALESCE(company_id, '00000000-0000-0000-0000-000000000000'::uuid), account_code);

CREATE INDEX IF NOT EXISTS idx_erp_coa_org ON erp.chart_of_accounts(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_erp_coa_parent ON erp.chart_of_accounts(org_id, parent_account_id);
CREATE INDEX IF NOT EXISTS idx_erp_coa_group ON erp.chart_of_accounts(org_id, group_id);

-- 3) Cost centers (hierarchical)
CREATE TABLE IF NOT EXISTS erp.cost_centers (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  cost_center_code varchar(64) NOT NULL,
  cost_center_name varchar(256) NOT NULL,
  parent_cost_center_id uuid NULL REFERENCES erp.cost_centers(id) ON DELETE SET NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.cost_centers ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='cost_centers' AND policyname='cost_centers_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY cost_centers_org_isolation
      ON erp.cost_centers
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_cost_center_code_org_company
  ON erp.cost_centers(org_id, COALESCE(company_id, '00000000-0000-0000-0000-000000000000'::uuid), cost_center_code);

CREATE INDEX IF NOT EXISTS idx_erp_cost_centers_org ON erp.cost_centers(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_erp_cost_centers_parent ON erp.cost_centers(org_id, parent_cost_center_id);

-- 4) Financial statement mappings
CREATE TABLE IF NOT EXISTS erp.financial_statement_mappings (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  account_id uuid NOT NULL REFERENCES erp.chart_of_accounts(id) ON DELETE CASCADE,
  statement_type varchar(32) NOT NULL, -- balance_sheet|profit_loss|cash_flow
  reporting_category varchar(128) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.financial_statement_mappings ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='financial_statement_mappings' AND policyname='financial_statement_mappings_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY financial_statement_mappings_org_isolation
      ON erp.financial_statement_mappings
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_stmt_map_org_account_stmt
  ON erp.financial_statement_mappings(org_id, account_id, statement_type);

-- 5) GST account mappings
CREATE TABLE IF NOT EXISTS erp.gst_account_mappings (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  account_id uuid NOT NULL REFERENCES erp.chart_of_accounts(id) ON DELETE CASCADE,
  gst_type varchar(32) NOT NULL,
  itc_eligible boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.gst_account_mappings ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='gst_account_mappings' AND policyname='gst_account_mappings_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY gst_account_mappings_org_isolation
      ON erp.gst_account_mappings
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_gst_map_org_account
  ON erp.gst_account_mappings(org_id, account_id);

