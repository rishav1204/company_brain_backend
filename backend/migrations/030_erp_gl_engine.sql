-- Module 9: General Ledger (GL) Engine

CREATE SCHEMA IF NOT EXISTS erp;

-- Fiscal periods (erp-scoped for GL engine)
CREATE TABLE IF NOT EXISTS erp.fiscal_periods (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  period_name varchar(128) NOT NULL,
  start_date date NOT NULL,
  end_date date NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'open', -- open|closed|locked|archived|soft_locked|hard_locked
  is_locked boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.fiscal_periods ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='fiscal_periods' AND policyname='fiscal_periods_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY fiscal_periods_org_isolation
      ON erp.fiscal_periods
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_erp_fiscal_periods_org ON erp.fiscal_periods(org_id, start_date, end_date);

-- Ledger batches (atomic posting groups)
CREATE TABLE IF NOT EXISTS erp.ledger_batches (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  batch_number varchar(64) NOT NULL,
  posting_status varchar(32) NOT NULL DEFAULT 'draft', -- draft|posted|reversed|failed
  posted_by uuid NULL,
  posted_at timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.ledger_batches ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='ledger_batches' AND policyname='ledger_batches_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY ledger_batches_org_isolation
      ON erp.ledger_batches
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_ledger_batches_org_batch_number ON erp.ledger_batches(org_id, batch_number);
CREATE INDEX IF NOT EXISTS idx_erp_ledger_batches_org_created ON erp.ledger_batches(org_id, created_at DESC);

-- Ledger entries (immutable truth)
CREATE TABLE IF NOT EXISTS erp.ledger_entries (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  batch_id uuid NOT NULL REFERENCES erp.ledger_batches(id) ON DELETE RESTRICT,
  journal_id uuid NULL,
  account_id uuid NOT NULL REFERENCES erp.chart_of_accounts(id) ON DELETE RESTRICT,
  entry_type varchar(32) NOT NULL, -- journal|voucher|opening|closing|reversal|adjustment
  debit_amount numeric(18,2) NOT NULL DEFAULT 0,
  credit_amount numeric(18,2) NOT NULL DEFAULT 0,
  currency_code varchar(8) NOT NULL DEFAULT 'INR',
  exchange_rate numeric(18,6) NOT NULL DEFAULT 1,
  posting_date date NOT NULL,
  fiscal_period_id uuid NOT NULL REFERENCES erp.fiscal_periods(id) ON DELETE RESTRICT,
  reference_type varchar(64) NULL,
  reference_id uuid NULL,
  cost_center_id uuid NULL REFERENCES erp.cost_centers(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.ledger_entries ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='ledger_entries' AND policyname='ledger_entries_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY ledger_entries_org_isolation
      ON erp.ledger_entries
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

-- Basic invariants
ALTER TABLE erp.ledger_entries
  ADD CONSTRAINT chk_erp_ledger_entries_non_negative
  CHECK (debit_amount >= 0 AND credit_amount >= 0);

ALTER TABLE erp.ledger_entries
  ADD CONSTRAINT chk_erp_ledger_entries_not_both_sides
  CHECK ((debit_amount = 0 AND credit_amount > 0) OR (credit_amount = 0 AND debit_amount > 0));

CREATE INDEX IF NOT EXISTS idx_erp_ledger_entries_org_date ON erp.ledger_entries(org_id, posting_date DESC);
CREATE INDEX IF NOT EXISTS idx_erp_ledger_entries_org_account ON erp.ledger_entries(org_id, account_id, posting_date DESC);
CREATE INDEX IF NOT EXISTS idx_erp_ledger_entries_batch ON erp.ledger_entries(org_id, batch_id);
CREATE INDEX IF NOT EXISTS idx_erp_ledger_entries_reference ON erp.ledger_entries(org_id, reference_type, reference_id);

-- Account balances (projection)
CREATE TABLE IF NOT EXISTS erp.account_balances (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  account_id uuid NOT NULL REFERENCES erp.chart_of_accounts(id) ON DELETE CASCADE,
  fiscal_period_id uuid NOT NULL REFERENCES erp.fiscal_periods(id) ON DELETE CASCADE,
  debit_total numeric(18,2) NOT NULL DEFAULT 0,
  credit_total numeric(18,2) NOT NULL DEFAULT 0,
  closing_balance numeric(18,2) NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.account_balances ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='account_balances' AND policyname='account_balances_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY account_balances_org_isolation
      ON erp.account_balances
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_account_balances_org_account_period
  ON erp.account_balances(org_id, account_id, fiscal_period_id);

CREATE INDEX IF NOT EXISTS idx_erp_account_balances_org_period ON erp.account_balances(org_id, fiscal_period_id);

-- Closing entries
CREATE TABLE IF NOT EXISTS erp.closing_entries (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  fiscal_period_id uuid NOT NULL REFERENCES erp.fiscal_periods(id) ON DELETE RESTRICT,
  closing_batch_id uuid NOT NULL REFERENCES erp.ledger_batches(id) ON DELETE RESTRICT,
  closed_by uuid NULL,
  closed_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.closing_entries ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='closing_entries' AND policyname='closing_entries_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY closing_entries_org_isolation
      ON erp.closing_entries
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

