-- Module 35: Multi-Entity & Consolidation Engine

-- A. Extend IAM legal entities (canonical — do not duplicate erp.entities)
ALTER TABLE core.companies
  ADD COLUMN IF NOT EXISTS entity_code varchar(50),
  ADD COLUMN IF NOT EXISTS is_consolidation_parent boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS consolidation_method varchar(32) DEFAULT 'full';

ALTER TABLE core.branches
  ADD COLUMN IF NOT EXISTS gstin varchar(20);

CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_org_entity_code
  ON core.companies (org_id, entity_code) WHERE entity_code IS NOT NULL;

-- B. Consolidation domain tables
CREATE TABLE IF NOT EXISTS erp.entity_hierarchy (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  parent_company_id uuid NOT NULL REFERENCES core.companies(id) ON DELETE CASCADE,
  child_company_id uuid NOT NULL REFERENCES core.companies(id) ON DELETE CASCADE,
  ownership_percent numeric(5,2) NOT NULL DEFAULT 100.00,
  effective_from date,
  effective_to date,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, parent_company_id, child_company_id)
);

ALTER TABLE erp.entity_hierarchy ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='entity_hierarchy'
      AND policyname='entity_hierarchy_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY entity_hierarchy_org ON erp.entity_hierarchy
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_entity_hierarchy_parent ON erp.entity_hierarchy (org_id, parent_company_id);
CREATE INDEX IF NOT EXISTS idx_entity_hierarchy_child ON erp.entity_hierarchy (org_id, child_company_id);

CREATE TABLE IF NOT EXISTS erp.intercompany_account_mappings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  company_id uuid REFERENCES core.companies(id) ON DELETE CASCADE,
  mapping_role varchar(64) NOT NULL,
  account_id uuid REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, company_id, mapping_role)
);

ALTER TABLE erp.intercompany_account_mappings ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='intercompany_account_mappings'
      AND policyname='ic_account_mappings_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY ic_account_mappings_org ON erp.intercompany_account_mappings
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.intercompany_transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  source_company_id uuid NOT NULL REFERENCES core.companies(id) ON DELETE CASCADE,
  target_company_id uuid NOT NULL REFERENCES core.companies(id) ON DELETE CASCADE,
  transaction_type varchar(100) NOT NULL,
  amount numeric(18,2) NOT NULL,
  currency varchar(10) NOT NULL DEFAULT 'INR',
  source_document_type varchar(64),
  source_document_id uuid,
  status varchar(32) NOT NULL DEFAULT 'open',
  matched_transaction_id uuid REFERENCES erp.intercompany_transactions(id) ON DELETE SET NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.intercompany_transactions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='intercompany_transactions'
      AND policyname='intercompany_tx_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY intercompany_tx_org ON erp.intercompany_transactions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_ic_tx_source_target
  ON erp.intercompany_transactions (org_id, source_company_id, target_company_id, status);

CREATE TABLE IF NOT EXISTS erp.intercompany_balances (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  source_company_id uuid NOT NULL REFERENCES core.companies(id) ON DELETE CASCADE,
  target_company_id uuid NOT NULL REFERENCES core.companies(id) ON DELETE CASCADE,
  balance_type varchar(64) NOT NULL DEFAULT 'due_to_due_from',
  amount numeric(18,2) NOT NULL DEFAULT 0,
  currency varchar(10) NOT NULL DEFAULT 'INR',
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, source_company_id, target_company_id, balance_type)
);

ALTER TABLE erp.intercompany_balances ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='intercompany_balances'
      AND policyname='intercompany_balances_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY intercompany_balances_org ON erp.intercompany_balances
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.consolidation_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  group_company_id uuid NOT NULL REFERENCES core.companies(id) ON DELETE CASCADE,
  fiscal_period_id uuid NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'queued',
  company_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  started_by uuid,
  error_message text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

ALTER TABLE erp.consolidation_runs ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='consolidation_runs'
      AND policyname='consolidation_runs_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY consolidation_runs_org ON erp.consolidation_runs
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_consolidation_runs_org_period
  ON erp.consolidation_runs (org_id, fiscal_period_id, started_at DESC);

CREATE TABLE IF NOT EXISTS erp.elimination_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  consolidation_run_id uuid NOT NULL REFERENCES erp.consolidation_runs(id) ON DELETE CASCADE,
  elimination_type varchar(64) NOT NULL,
  source_company_id uuid REFERENCES core.companies(id) ON DELETE SET NULL,
  target_company_id uuid REFERENCES core.companies(id) ON DELETE SET NULL,
  account_id uuid REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  debit_amount numeric(18,2) NOT NULL DEFAULT 0,
  credit_amount numeric(18,2) NOT NULL DEFAULT 0,
  journal_id uuid,
  description text,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.elimination_entries ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='elimination_entries'
      AND policyname='elimination_entries_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY elimination_entries_org ON erp.elimination_entries
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_elimination_run ON erp.elimination_entries (org_id, consolidation_run_id);

CREATE TABLE IF NOT EXISTS erp.ownership_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  consolidation_run_id uuid NOT NULL REFERENCES erp.consolidation_runs(id) ON DELETE CASCADE,
  subsidiary_company_id uuid NOT NULL REFERENCES core.companies(id) ON DELETE CASCADE,
  ownership_percent numeric(5,2) NOT NULL,
  subsidiary_profit numeric(18,2) NOT NULL DEFAULT 0,
  parent_share numeric(18,2) NOT NULL DEFAULT 0,
  minority_interest numeric(18,2) NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.ownership_snapshots ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='ownership_snapshots'
      AND policyname='ownership_snapshots_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY ownership_snapshots_org ON erp.ownership_snapshots
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- C. Entity/branch dimensions on ERP transactional tables
ALTER TABLE erp.journals ADD COLUMN IF NOT EXISTS branch_id uuid REFERENCES core.branches(id) ON DELETE SET NULL;
ALTER TABLE erp.journal_lines ADD COLUMN IF NOT EXISTS branch_id uuid REFERENCES core.branches(id) ON DELETE SET NULL;
ALTER TABLE erp.journal_lines ADD COLUMN IF NOT EXISTS company_id uuid REFERENCES core.companies(id) ON DELETE SET NULL;

ALTER TABLE erp.ledger_entries ADD COLUMN IF NOT EXISTS company_id uuid REFERENCES core.companies(id) ON DELETE SET NULL;
ALTER TABLE erp.ledger_entries ADD COLUMN IF NOT EXISTS branch_id uuid REFERENCES core.branches(id) ON DELETE SET NULL;
ALTER TABLE erp.account_balances ADD COLUMN IF NOT EXISTS company_id uuid REFERENCES core.companies(id) ON DELETE SET NULL;
ALTER TABLE erp.account_balances ADD COLUMN IF NOT EXISTS branch_id uuid REFERENCES core.branches(id) ON DELETE SET NULL;

ALTER TABLE erp.gst_registrations ADD COLUMN IF NOT EXISTS company_id uuid REFERENCES core.companies(id) ON DELETE SET NULL;
ALTER TABLE erp.gst_transactions ADD COLUMN IF NOT EXISTS company_id uuid REFERENCES core.companies(id) ON DELETE SET NULL;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='erp' AND table_name='gst_returns') THEN
    EXECUTE 'ALTER TABLE erp.gst_returns ADD COLUMN IF NOT EXISTS company_id uuid REFERENCES core.companies(id) ON DELETE SET NULL';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_journals_company ON erp.journals (org_id, company_id) WHERE company_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_erp_ledger_entries_company ON erp.ledger_entries (org_id, company_id, fiscal_period_id) WHERE company_id IS NOT NULL;

-- D. Reporting MV company dimension
ALTER TABLE erp_reporting.trial_balance_mv ADD COLUMN IF NOT EXISTS company_id uuid;
ALTER TABLE erp_reporting.pnl_mv ADD COLUMN IF NOT EXISTS company_id uuid;
ALTER TABLE erp_reporting.balance_sheet_mv ADD COLUMN IF NOT EXISTS company_id uuid;

CREATE TABLE IF NOT EXISTS erp_reporting.consolidated_trial_balance_mv (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  consolidation_run_id uuid NOT NULL,
  group_company_id uuid NOT NULL,
  fiscal_period_id uuid NOT NULL,
  account_id uuid NOT NULL,
  account_code varchar(64),
  account_name varchar(256),
  debit_total numeric(18,2) NOT NULL DEFAULT 0,
  credit_total numeric(18,2) NOT NULL DEFAULT 0,
  balance numeric(18,2) NOT NULL DEFAULT 0,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, consolidation_run_id, account_id)
);

ALTER TABLE erp_reporting.consolidated_trial_balance_mv ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp_reporting' AND tablename='consolidated_trial_balance_mv'
      AND policyname='consolidated_tb_mv_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY consolidated_tb_mv_org ON erp_reporting.consolidated_trial_balance_mv
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- E. M34 entity-scoped approval matrix
ALTER TABLE governance.approval_matrix ADD COLUMN IF NOT EXISTS company_id uuid REFERENCES core.companies(id) ON DELETE SET NULL;

-- F. Forecasting company dimension
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='finance_os' AND table_name='forecasts') THEN
    EXECUTE 'ALTER TABLE finance_os.forecasts ADD COLUMN IF NOT EXISTS company_id uuid';
  END IF;
END $$;
